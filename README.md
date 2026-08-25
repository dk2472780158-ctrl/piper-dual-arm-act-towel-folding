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

> 🎬 Hero demo: `![Hero demo](assets/demo_hero.gif)` *(placeholder — added in the media pack, see below)*

---

## Result card: 10/10 consecutive trials

> In one continuous recorded experiment, the system completed **10 trials and succeeded 10 times (10/10 consecutive trials)**.

| Trial | Video timestamps | Final success | Manual reset |
|---|---|---|---|
| 01 – 10 | see `results/consecutive_10_trials.csv` | backfilled from footage | backfilled |

- Full 10-trial continuous video (untrimmed, Trial 01–10 labeled): **link to be added** (stays out of git; see Downloads).
- Technical analysis video (60–90 s, stage-marked, with real failures): `docs/video-script.md`.

**Reporting rule:** we write *10/10 consecutive trials*, never "99%" or "100% success". A single continuous take is more credible than an aggregated percentage.

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
assets/   architecture.svg (+ hero GIF placeholder)
configs/  training / eval / robot example configs
docs/     architecture · data collection · training · deployment ·
          safety system · evaluation · reproducibility · engineering · roadmap
results/  backfill-only templates (evaluation_summary.json, trial_results.csv,
          latency_results.csv, consecutive_10_trials.csv)
scripts/  train · evaluate · run_act · dry_run · check_environment
src/      safety.py (pure-numpy validators) · reset_pose · eval_rollout · piper drivers
tests/    safety behavior, action-shape, config-contract, checkpoint-load
```

## Getting started

```bash
pip install -e ".[dev]"

./scripts/check_environment.sh     # deps / CUDA / CAN / cameras / checkpoint
./scripts/dry_run.sh               # full dry-run, no motion
python -m pytest tests/ -q         # safety + config unit tests
```

Real execution is **never the default**: it requires `--execute`, typing `EXECUTE`, and an explicit `--max-steps` budget. See `docs/inference-deployment.md` and `docs/safety-system.md`.

## Downloads (data & weights — never in git)

- **Dataset** (LeRobot episodes): exported from the collection host — see `docs/reproducibility.md`.
- **Checkpoint** (`pretrained_model/`): exported from the training host — set `POLICY_CHECKPOINT`.
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
