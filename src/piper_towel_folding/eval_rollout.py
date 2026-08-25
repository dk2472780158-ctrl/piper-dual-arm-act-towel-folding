"""Safety-first ACT rollout on the dual Piper arms (synchronous path).

This is the reference single-process runner: it loads an ACT checkpoint,
captures three RGB cameras + the 28-dim joint state, runs ACT inference with
action chunking, and executes each action on the arms at ``--fps`` while
applying every validator in :mod:`piper_towel_folding.safety` on each step.

Real execution is refused unless every gate passes:
* arms are already near the training start pose (``validate_start_pose``),
* you type ``EXECUTE`` after checking the workspace,
* ``--max-steps`` is a positive budget (hard safety refusal otherwise).

For the deployed asynchronous gRPC setup (policy server + robot client) used
for the 10/10 consecutive-trials video, see ``docs/deployment.md`` and
``scripts/run_act.sh``.
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from pathlib import Path

import numpy as np
import torch

from piper_towel_folding.piper.dual_robot import (
    PIPERDual,
    PIPERDualConfig,
    OpenCVCameraConfig,
    STATE_KEYS,
)
from piper_towel_folding.safety import (
    RolloutConfig,
    TRAINING_START_ACTION,
    normalize_gripper_commands,
    validate_action_shape,
    validate_command_step,
    validate_hardware_limits,
    validate_start_pose,
    validate_tracking_error,
)

stop_requested = False


def request_stop(_signum=None, _frame=None) -> None:
    global stop_requested
    stop_requested = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe ACT rollout for dual Piper arms.")
    parser.add_argument("--checkpoint", type=Path, required=True, help="LeRobot `pretrained_model` directory.")
    parser.add_argument("--device", default="cuda", choices=("cuda", "cpu"))
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--left-can", default="can1")
    parser.add_argument("--right-can", default="can0")
    parser.add_argument("--camera-left", default="/dev/camera_left")
    parser.add_argument("--camera-middle", default="/dev/camera_middle")
    parser.add_argument("--camera-right", default="/dev/camera_right")
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--camera-fps", type=int, default=30)
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--n-action-steps", type=int, default=5, help="Actions executed before ACT replans.")
    parser.add_argument("--max-steps", type=int, default=0, help="0 means run until Ctrl+C.")
    parser.add_argument("--start-joint-tolerance", type=float, default=0.15)
    parser.add_argument("--start-gripper-tolerance", type=float, default=0.02)
    parser.add_argument("--max-joint-step", type=float, default=0.10)
    parser.add_argument("--max-gripper-step", type=float, default=0.01)
    parser.add_argument("--max-tracking-error", type=float, default=0.35)
    parser.add_argument("--max-gripper-tracking-error", type=float, default=0.03)
    parser.add_argument("--shutdown", choices=("hold", "disable"), default="hold",
                        help="What to do on exit: `hold` keeps arms ENABLED at last pose (prevents drops); "
                             "`disable` releases both arms.")
    parser.add_argument("--execute", action="store_true", help="Actually send actions to Piper. Default is dry-run.")
    parser.add_argument("--latency-csv", type=Path, default=Path("results/latency_results.csv"),
                        help="Write per-metric mean/p95 latency (ms) to this CSV.")
    parser.add_argument("--latency-warmup", type=int, default=10,
                        help="Loops to skip before collecting latency samples.")
    return parser.parse_args()


def build_robot(args: argparse.Namespace, read_only: bool) -> PIPERDual:
    cameras = {
        "left": OpenCVCameraConfig(args.camera_left, args.camera_width, args.camera_height, args.camera_fps),
        "middle": OpenCVCameraConfig(args.camera_middle, args.camera_width, args.camera_height, args.camera_fps),
        "right": OpenCVCameraConfig(args.camera_right, args.camera_width, args.camera_height, args.camera_fps),
    }
    robot = PIPERDual(PIPERDualConfig(left_port=args.left_can, right_port=args.right_can, read_only=read_only, cameras=cameras))
    # The wrapper enables motors during connect() only when not read_only.
    robot.connect()
    return robot


def build_state(raw_observation: dict) -> np.ndarray:
    missing = [key for key in STATE_KEYS if key not in raw_observation]
    if missing:
        raise KeyError(f"Piper observation is missing state keys: {missing}")
    state = np.asarray([raw_observation[key] for key in STATE_KEYS], dtype=np.float32)
    if state.shape != (28,):
        raise RuntimeError(f"Expected state shape (28,), got {state.shape}")
    return state


def state_positions(state: np.ndarray) -> np.ndarray:
    # STATE_KEYS alternate pos/effort per motor; positions are at even offsets.
    return state[0::2]


def build_policy_observation(
    raw_observation: dict,
    images: dict[str, np.ndarray],
    device: torch.device,
) -> tuple[dict[str, torch.Tensor], np.ndarray]:
    state = build_state(raw_observation)
    obs: dict[str, torch.Tensor] = {
        "observation.state": torch.from_numpy(state).unsqueeze(0).to(device),
    }
    for name, image in images.items():
        # H,W,C uint8 -> 1,C,H,W float32 in [0,1] (ImageNet mean/std applied by the preprocessor).
        tensor = torch.from_numpy(np.ascontiguousarray(image)).permute(2, 0, 1).float().div(255.0)
        obs[f"observation.images.{name}"] = tensor.unsqueeze(0).to(device)
    return obs, state


def read_all_images(robot: PIPERDual) -> dict[str, np.ndarray]:
    raw = robot.get_observation()
    return {name: raw[name] for name in ("left", "middle", "right")}


def load_policy(checkpoint: Path, device: torch.device, n_action_steps: int):
    """Load a LeRobot ACT checkpoint and its pre/post processors."""
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.policies.factory import make_pre_post_processors

    checkpoint = checkpoint.expanduser().resolve()
    if not checkpoint.is_dir():
        raise FileNotFoundError(f"Checkpoint directory not found: {checkpoint}")

    required_files = ("config.json", "model.safetensors", "policy_preprocessor.json", "policy_postprocessor.json")
    missing = [name for name in required_files if not (checkpoint / name).exists()]
    if missing:
        raise FileNotFoundError(f"Checkpoint is missing files: {missing}")

    print(f"Loading ACT checkpoint: {checkpoint}")
    policy = ACTPolicy.from_pretrained(str(checkpoint))

    chunk_size = int(policy.config.chunk_size)
    if not 1 <= n_action_steps <= chunk_size:
        raise ValueError(f"--n-action-steps must be between 1 and {chunk_size}, got {n_action_steps}")

    # Keep the trained chunk_size; only shorten how many actions run before replanning.
    policy.config.n_action_steps = n_action_steps
    policy.config.device = str(device)
    policy.to(device)
    policy.eval()
    policy.reset()

    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=str(checkpoint),
        preprocessor_overrides={"device_processor": {"device": str(device)}},
    )
    preprocessor.reset()
    postprocessor.reset()

    print(f"ACT policy loaded on {device}. chunk_size={chunk_size}, n_action_steps={n_action_steps}")
    return policy, preprocessor, postprocessor


def infer_action(policy, preprocessor, postprocessor, obs: dict[str, torch.Tensor], device: torch.device) -> np.ndarray:
    with torch.inference_mode():
        processed = preprocessor(obs)
        action_tensor = policy.select_action(processed)
        action_tensor = postprocessor(action_tensor)

    action = action_tensor.detach().to("cpu", dtype=torch.float32).numpy().reshape(-1)
    validate_action_shape(action)
    action = normalize_gripper_commands(action)
    validate_hardware_limits(action)
    return action


def write_latency_csv(path: Path, samples: dict[str, list[float]]) -> None:
    """Write mean/p95 latency per metric.

    The sync runner measures the first three metrics on the single-process
    path; ``chunk_encode`` / ``grpc_roundtrip`` are async-gRPC-path metrics
    and stay empty (marked 待确认) until measured with a client-side timer.
    """
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("policy_inference", samples["policy_inference"], "ACT forward + pre/post processors (CUDA)"),
        ("chunk_encode", samples.get("chunk_encode", []), "async gRPC path — 待确认 (needs async client timer)"),
        ("grpc_roundtrip", samples.get("grpc_roundtrip", []), "async gRPC path — 待确认 (needs async client timer)"),
        ("observation_capture", samples["observation_capture"], "3 cams + 28-dim state read + tensor build"),
        ("control_loop_period", samples["control_loop_period"], "wall time between loop iterations incl. sleep"),
    ]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value_ms", "notes"])
        for name, values, note in rows:
            if values:
                writer.writerow([f"{name}_mean", f"{float(np.mean(values)):.3f}", note])
                writer.writerow([f"{name}_p95", f"{float(np.percentile(values, 95)):.3f}", note])
            else:
                writer.writerow([f"{name}_mean", "", note])
                writer.writerow([f"{name}_p95", "", note])
    print(f"Latency CSV written: {path}")


def run(args: argparse.Namespace) -> None:
    global stop_requested
    stop_requested = False

    if args.fps <= 0:
        raise ValueError("--fps must be greater than zero.")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable.")

    device = torch.device(args.device)
    safety = RolloutConfig(
        start_joint_tolerance=args.start_joint_tolerance,
        start_gripper_tolerance=args.start_gripper_tolerance,
        max_joint_step=args.max_joint_step,
        max_gripper_step=args.max_gripper_step,
        max_tracking_error=args.max_tracking_error,
        max_gripper_tracking_error=args.max_gripper_tracking_error,
    )

    policy, preprocessor, postprocessor = load_policy(args.checkpoint, device, args.n_action_steps)

    robot: PIPERDual | None = None
    was_executing = False
    latency_samples: dict[str, list[float]] = {
        "observation_capture": [],
        "policy_inference": [],
        "control_loop_period": [],
    }
    try:
        robot = build_robot(args, read_only=not args.execute)
        was_executing = args.execute

        if args.execute:
            print("\nWARNING: REAL ROBOT EXECUTION IS ENABLED.")
            print("The arms must already be in the training start pose.")
            print("Keep the hardware emergency stop in your hand.")
            if input("Type EXECUTE to continue: ").strip() != "EXECUTE":
                print("Cancelled.")
                return

        # Read the initial measured state WITHOUT sending any position command.
        raw = robot.get_observation()
        initial_positions = state_positions(build_state(raw))
        print("Measured start:\n", np.array2string(initial_positions, precision=6, separator=", "))
        print("Training start:\n", np.array2string(TRAINING_START_ACTION, precision=6, separator=", "))
        validate_start_pose(initial_positions, safety.start_joint_tolerance, safety.start_gripper_tolerance)

        policy.reset()
        preprocessor.reset()
        postprocessor.reset()

        period = 1.0 / args.fps
        step = 0
        previous_action: np.ndarray | None = None
        prev_loop_start: float | None = None

        print("\n" + ("REAL ACT rollout started. Press Ctrl+C or emergency stop to stop.\n"
                       if args.execute else "DRY-RUN started. No actions will be sent to Piper.\n"))

        while not stop_requested:
            loop_start = time.perf_counter()
            steady = step >= args.latency_warmup

            t_obs_start = time.perf_counter()
            raw_robot = robot.get_observation()
            images = read_all_images(robot)
            obs, state = build_policy_observation(raw_robot, images, device)
            measured_positions = state_positions(state)
            t_obs_end = time.perf_counter()

            if args.execute and previous_action is not None:
                validate_tracking_error(
                    measured_positions, previous_action, safety.max_tracking_error, safety.max_gripper_tracking_error
                )

            t_inf_start = time.perf_counter()
            action = infer_action(policy, preprocessor, postprocessor, obs, device)
            t_inf_end = time.perf_counter()

            if steady:
                latency_samples["observation_capture"].append((t_obs_end - t_obs_start) * 1000.0)
                latency_samples["policy_inference"].append((t_inf_end - t_inf_start) * 1000.0)
                if prev_loop_start is not None:
                    latency_samples["control_loop_period"].append((loop_start - prev_loop_start) * 1000.0)
            prev_loop_start = loop_start

            command_reference = measured_positions if previous_action is None else previous_action
            validate_command_step(action, command_reference, safety.max_joint_step, safety.max_gripper_step)

            print(f"step={step:06d} action={np.array2string(action, precision=4, separator=', ')}", flush=True)

            if args.execute:
                robot.send_action(action)
                previous_action = action.copy()

            step += 1
            if args.max_steps > 0 and step >= args.max_steps:
                print(f"Reached --max-steps={args.max_steps}.")
                break

            elapsed = time.perf_counter() - loop_start
            remaining = period - elapsed
            if remaining > 0:
                time.sleep(remaining)
            elif step % 30 == 0:
                print(f"WARNING: control loop overrun: {elapsed * 1000.0:.1f} ms, target={period * 1000.0:.1f} ms",
                      file=sys.stderr)

    finally:
        print("\nStopping rollout...")
        if robot is not None:
            if was_executing and args.shutdown == "disable":
                robot.left_bus.connect(enable=False)
                robot.right_bus.connect(enable=False)
                print("Both arms disabled.")
            else:
                print("Arms remain ENABLED holding the last commanded pose. "
                      "Physically support them before any later power-off.")
            robot.disconnect()
        if any(latency_samples.values()):
            write_latency_csv(args.latency_csv, latency_samples)
        else:
            print("No latency samples collected (warmup only?) — CSV not written.")
        print("Rollout stopped.")


def main() -> None:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    args = parse_args()

    # Real execution always needs a finite command budget: the ACT policy has
    # no learned task-completion signal to end a rollout by itself.
    if args.execute and args.max_steps <= 0:
        raise SystemExit("Safety refusal: --execute requires an explicit positive --max-steps value.")

    try:
        run(args)
    except KeyboardInterrupt:
        request_stop()
    except Exception as error:  # noqa: BLE001
        print(f"\nFATAL: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
