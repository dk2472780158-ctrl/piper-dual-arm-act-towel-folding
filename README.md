<div align="center">

# Dual-Arm ACT Towel Folding

**Vision-language-free imitation learning for bi-manual soft-object manipulation on real dual-AgileX-Piper arms.**

ACT (Action Chunking Transformer) · LeRobot · gRPC async inference · 30 Hz real-time control · full safety layer

**中文版**：[README_zh-CN.md](README_zh-CN.md)

</div>

---

## What this project shows

A real towel-folding skill that runs on two physical AgileX Piper arms, end to end:

- **Imitation learning & ACT** — CVAE + Transformer policy that predicts whole action chunks.
- **Bi-manual coordination** — one 14-D action vector drives both arms and both grippers from a single model.
- **Soft-object manipulation** — folding a deformable towel, not rigid pick-and-place.
- **Full data → train → inference → real-robot loop** — teleop collection, LeRobot dataset, training, gRPC async deployment, 30 Hz control.
- **Real-time control & safety** — a dependency-free safety layer validates every action before it is sent; dry-run by default.
- **Quantified evaluation & failure analysis** — results reported as **10/10 consecutive trials** from one continuous take, not a fabricated success rate.
- **Engineering & reproducibility** — runnable scripts, unit-testable safety code, config contract tests, result templates that must be backfilled from real runs.

> 🎬 Hero demo — Trial 01 of the continuous 10-trial recording:

![Hero demo](assets/demo_hero.gif)

---

## Result card: 10/10 consecutive trials

> In one continuous recorded experiment, the system completed **10 trials and succeeded 10 times (10/10 consecutive trials)**.

| Item | Value |
|---|---|
| Recording | one continuous take, no internal cuts |
| Trial span | 1.5 – 314.0 s (≈34 s per trial) |
| Trials completed / succeeded | 10 / 10 |
| Manual reset | yes — before every trial the operator repositions the towel |
| Timing precision | ±0.5 s |
| Checkpoint | v4 · 040000 (= last) |
| Per-stage outcome | approach · left/right grasp · lift · fold · release all visible and successful in every trial |

Per-trial timestamps and stage flags: `results/consecutive_10_trials.csv` · full frame-by-frame review: `results/consecutive_10_trials_review.md`

---

## Dataset and checkpoint

The consecutive-trial evaluation uses the ACT checkpoint at global step
`040000` (identical to `last`) from the `towel_fold_act_v4_scratch60k` run,
trained from scratch (target 60,000 steps, batch size 8).

The policy was trained on 120 real dual-arm demonstrations
(`local/towel_fold_dataset_aug_v1`) containing 85,187 frames at 30 FPS.
Image augmentation was disabled for this run.

- Robot: dual AgileX Piper
- Cameras: three RGB views (`left`, `middle`, `right`)
- State dimension: 28
- Action dimension: 14
- ACT chunk size: 100
- Training batch size: 8
- Piper SDK: 0.6.2
- Checkpoint SHA256: `e118230cb7be20e307a64598fced077f50c631651b243deb2cf0db8366a4c28c`

In one continuous recording, the system completed 10 tests and succeeded in
all 10 (`10/10 consecutive trials`). This is a result for that recording,
not a general success-rate estimate.

> `towel_fold_act_v1/v2/v3` and `cube_r2l_act_v1` are earlier training runs on
> this rig (v2 used the 60-demonstration `towel_fold_dataset`); they are
> **not** the model in the 10/10 recording claim above.

---

## Architecture

![Architecture](assets/architecture.svg)

```
teleop collection → LeRobot dataset → ACT training → checkpoint
        → gRPC policy_server (CUDA) → robot_client (CPU) → 2 × Piper (CAN)
        → 30 Hz observation feedback → next chunk
```

The safety layer runs on **every** control step: start-pose validation (0.15 rad / 0.02 m), per-command step limits (0.10 rad / 0.01 m), tracking error (0.35 rad / 0.03 m), hardware joint limits, gripper clip to [0, 0.08] m, and **never sending a disable command** (arms stay ENABLED to prevent falling).

---

## Key numbers (read from the real run, not guessed)

| Dimension | Value |
|---|---|
| Observation `observation.state` | 28 (2 arms × 7 motors × position+effort) |
| Action | 14 = [left j1..j6, left gripper, right j1..j6, right gripper], position control |
| Cameras | 3 × 640×480 @ 30 fps |
| ACT chunk | chunk 100 · train-exec 50 · deploy-exec 30 |
| Asynchronous inference | gRPC, `weighted_average` (0.3·old + 0.7·new), `chunk_size_threshold=0.6` |
| Control loop | 30 Hz |
| Checkpoint | `pretrained_model/` (deployment used global step 040000) |

> ⚠️ Items not confirmed by an audited log are explicitly marked **待确认 (TBC)** in `docs/` — nothing is fabricated.

---

## Repository layout

```
assets/   architecture.svg + hero GIF
configs/  training / eval / robot example configs
docs/     architecture · data collection · training · deployment ·
          safety system · environment setup · reproducibility · engineering · roadmap
lerobot_piper/  the `piper_dual` LeRobot robot type (vendored from the reference fork)
results/  backfill-only templates (evaluation_summary.json, trial_results.csv,
          latency_results.csv, consecutive_10_trials.csv)
scripts/  setup_piper_dual · train · evaluate · run_act · dry_run · check_environment
src/      safety.py (pure-numpy validators) · reset_pose · eval_rollout · piper drivers
tests/    safety behavior, action-shape, config-contract, checkpoint-load
```

## Getting started (no hardware needed)

```bash
pip install -e ".[dev]"

./scripts/check_environment.sh     # deps / CUDA / CAN / cameras / checkpoint
python -m pytest tests/ -q         # safety + config unit tests
```

`check_environment.sh` and `pytest` need no robot, no CAN bus and no checkpoint.
`dry_run.sh` additionally needs `POLICY_CHECKPOINT` pointing at an exported
`pretrained_model/` dir (it proves the ACT policy loads and the whole stack is
wired), but still moves nothing:

```bash
POLICY_CHECKPOINT=/path/to/pretrained_model ./scripts/dry_run.sh
```

Real execution is **never the default**: it requires `--execute`, typing
`EXECUTE`, and an explicit `--max-steps` budget. See
`docs/inference-deployment.md` and `docs/safety-system.md`.

## Environment (hardware)

| Component | Spec | Notes |
|---|---|---|
| Arms | 2 × AgileX Piper (6-DoF + gripper) | left on `can1`, right on `can0` |
| Cameras | 3 × 640×480 @ 30 fps | `/dev/camera_{left,middle,right}` udev symlinks |
| Host | Ubuntu + NVIDIA A10 (24 GB) | training + CUDA inference |
| Driver / CUDA | 595.84 / 13.2 (confirmed) | — |

```bash
# one-time, per machine: install the piper_dual robot type into LeRobot
./scripts/setup_piper_dual.sh
```

Full CAN / udev / camera / piper-sdk details (serial numbers sanitized):
`docs/environment-setup.md`.

## End-to-end pipeline (the full loop this repo reproduces)

**1. Collect** — teleoperate the leader arms; `lerobot-record` writes LeRobot
episodes (parquet + mp4). See `docs/data-collection.md`:

```bash
lerobot-record --robot.type=piper_dual --robot.left_port=can1 --robot.right_port=can0 \
  --robot.cameras="{left: {type: opencv, index_or_path: /dev/camera_left, width: 640, height: 480, fps: 30}, \
    middle: {type: opencv, index_or_path: /dev/camera_middle, width: 640, height: 480, fps: 30}, \
    right: {type: opencv, index_or_path: /dev/camera_right, width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id=local/towel_fold_dataset_aug_v1 --dataset.num_episodes=120 \
  --dataset.single_task="Fold the towel with both Piper arms."
```

**2. Train** — `lerobot-train` with ACT (chunk 100, ResNet18, VAE 32, kl 10.0). See `docs/training.md`:

```bash
DATASET_ROOT="$DATASET_ROOT" ./scripts/train_act.sh
```

**3. Deploy** — async gRPC: `policy_server` (CUDA) holds the model,
`robot_client` (CPU) drives the arms at 30 Hz. See `docs/inference-deployment.md`:

```bash
./scripts/run_act.sh --server      # terminal A: gRPC policy server
./scripts/run_act.sh --client      # terminal B: robot + cameras, 30 Hz loop
```

**4. Evaluate** — `results/` templates are backfilled from a real recorded run
(see below). The reference result is a single continuous 10/10 take.

## Reproduction checklist

- [ ] `./scripts/setup_piper_dual.sh` → `piper_dual` registered
- [ ] `./scripts/check_environment.sh` → all hard requirements OK
- [ ] `./scripts/dry_run.sh` → full pipeline dry-run passes, no motion
- [ ] `python -m pytest tests/ -q` → all green
- [ ] CAN `can0`/`can1` up; `/dev/camera_*` symlinks resolve
- [ ] `POLICY_CHECKPOINT` set to an exported `pretrained_model/` dir
- [ ] arms reset to the training start pose (`piper-towel-reset`)
- [ ] `./scripts/run_act.sh --server` + `--client` (or `evaluate_act.sh --execute`)

Anything not yet confirmable from an audited log is marked **待确认 (TBC)** in
`docs/` — nothing is fabricated.

## FAQ

**Why "10/10 consecutive trials" instead of a success rate?** One continuous,
internally-unedited recording with every reset visible is more credible than an
aggregated percentage, and it cannot be inflated by cherry-picking. The full
frame-by-frame review is in `results/consecutive_10_trials_review.md`.

**Where are the weights and the dataset?** Not in git — the repo ships
export/install instructions and result templates that must be backfilled from a
real run (`docs/reproducibility.md`). GitHub is for code, not hundreds of MB of
weights.

**Is a GPU required?** Only for training and CUDA inference. The safety layer,
config-contract tests and dry-run all run on CPU.

**Do I need the original ACT project to use this?** No. `lerobot_piper/` +
`scripts/setup_piper_dual.sh` make a stock LeRobot install understand
`piper_dual`. This repo is standalone; the original project is never modified.

**Are the camera serial numbers published?** No — device serials are privacy
sensitive and machine-specific. Docs use placeholders; you fill in yours
(`docs/environment-setup.md`).

**Is anything ever sent to the arms without explicit confirmation?** No.
Real execution requires `--execute` + typing `EXECUTE` + an explicit
`--max-steps` budget, and the arms stay ENABLED after Ctrl+C (never
auto-disabled, to prevent dropping the load).

## Downloads (data & weights — never in git)

- **Dataset** (LeRobot episodes, the 120 demos behind the 10/10 video,
  `local/towel_fold_dataset_aug_v1`): export from the collection host — see
  `docs/reproducibility.md`. Published on Hugging Face:
  <https://huggingface.co/datasets/d1112222/towel_fold_dataset_aug_v1>
- **Checkpoint** (`pretrained_model/`, v4 040000 = last): export from the
  training host — set `POLICY_CHECKPOINT`. Published:
  <https://huggingface.co/d1112222/towel_fold_act_v4_040000>
- **Videos**: GIF/covers/links only in the repo; raw footage stays local.

## Safety & red lines (verbatim)

1. The original ACT project may only be read, never modified.
2. All releases happen in a new, independent directory.
3. Original training configs, inference code, models and data must not be overwritten.
4. The in-use ACT checkpoint must not be modified.
5. No unconfirmed robot connection or control.
6. No unconfirmed CAN commands.
7. No unconfirmed push to GitHub.
8. All changes are staged in the release directory and reviewed before upload.

## Acknowledgements & license

- LeRobot / ACTPolicy — Apache 2.0, based on Tony Z. Zhao's ALOHA work. See `NOTICE` and `CITATION.cff`.
- AgileX Piper SDK — per its own license (see `NOTICE`).
- This repository is released under Apache 2.0 (`LICENSE`).

**待确认 (TBC) audit items** and honest boundaries are documented in `docs/evaluation.md` and `docs/roadmap.md`.
