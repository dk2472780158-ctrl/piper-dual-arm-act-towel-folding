# `lerobot_piper/` — the `piper_dual` LeRobot robot type

This folder is the **exact LeRobot-side module** that makes a stock LeRobot
install understand two AgileX Piper arms on CAN plus three cameras. The
reference stack runs on a LeRobot fork that carries this module; this folder
vendors it so anyone can reproduce the setup from upstream LeRobot instead of
a private fork.

## What each file is

```
robots/piper_dual/__init__.py         package marker (exports PIPERDual + PIPERDualConfig)
robots/piper_dual/config_piper_dual.py  PIPERDualConfig — CAN ports, cameras, `@register_subclass("piper_dual")`
robots/piper_dual/piper_dual.py         PIPERDual — observation/action contract, connect/send_action
motors/piper/piper_slave.py             PiperMotorsBus (follower) — reads joint/gripper state, writes position commands
motors/piper/piper_master.py            PiperMotorsBus (master) — read-only leader bus for teleop collection
```

### The observation / action contract (must match the trained ACT config)

| field | shape | meaning |
|---|---|---|
| `observation.state` | 28 | 2 arms × 7 motors × (position, effort) |
| `observation.images.{left,middle,right}` | 3 × 480×640×3 | three RGB cameras |
| `action` | 14 | `[left j1..j6, left gripper, right j1..j6, right gripper]`, position control, gripper in meters |

## How `--robot.type=piper_dual` resolves

LeRobot's `RobotConfig` is a `draccus.ChoiceRegistry`:

1. Importing `lerobot.robots.piper_dual` runs `@RobotConfig.register_subclass("piper_dual")` (in `config_piper_dual.py`), registering `PIPERDualConfig` under the name `"piper_dual"`.
2. `make_robot_from_config()` falls through its known-robot branches to `make_device_from_device_class(config)`, which instantiates the registered class.
3. `lerobot/async_inference/robot_client.py` and `lerobot/scripts/lerobot_record.py` import `piper_dual` in their robot-import list, which is exactly why the one-line import patch is needed.

## Install

Requires a stock LeRobot install (same minor version family as the fork this
was extracted from) and the AgileX `piper_sdk` package. Run once per install:

```bash
./scripts/setup_piper_dual.sh            # uses `python` and the default env
./scripts/setup_piper_dual.sh --python /path/to/venv/bin/python
```

The script copies these files into the installed `lerobot/` package, appends
`piper_dual` to the two import lists (with a `.bak.piper_dual` backup), and
smoke-tests that the type imports and registers.

> Red-line note: this edits the LeRobot install **on your own machine**. It
> never touches the original ACT project, training configs, checkpoints, or
> datasets, and never enables motors or sends CAN commands.

## Not in this folder

The fork's other diffs (e.g. `lerobot/teleoperators/` for leader-arm
teleoperation during collection, transport/ gRPC protos) are not vendored
here because the collection host carries the full fork. For a from-scratch
collection pipeline, start from `docs/data-collection.md` and confirm the
teleop type name on your host (marked 待确认 there).
