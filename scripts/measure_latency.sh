#!/usr/bin/env bash
# ------------------------------------------------------------------
# Measure per-step latency on the reference single-process rollout and
# write results/latency_results.csv (mean & p95 per metric).
#
# Runs on the CONTROL HOST (arms + cameras + CUDA + POLICY_CHECKPOINT).
# Default is a DRY-RUN: cameras and joint state are still read and ACT
# inference still runs, so observation_capture / policy_inference /
# control_loop_period are representative WITHOUT moving the arms. For a
# real (moving) run, pass --execute --max-steps <budget> after reviewing
# the warnings in evaluate_act.sh.
#
# The async-gRPC metrics (chunk_encode / grpc_roundtrip) cannot be measured
# here — the sync runner has no gRPC boundary — so those rows stay 待确认
# until measured with a client-side timer on the deployed async stack.
#
# Usage:
#   ./scripts/measure_latency.sh                       # dry-run, ~30 s of samples
#   ./scripts/measure_latency.sh --execute --max-steps 900   # real rollout 30 s
#   ./scripts/measure_latency.sh --latency-csv out.csv # custom output path
# ------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

# Load .env if present (never committed).
if [ -f .env ]; then
  set -a; source .env; set +a
fi

CHECKPOINT="${POLICY_CHECKPOINT:?Set POLICY_CHECKPOINT (or pass --checkpoint)}"

exec python -m piper_towel_folding.eval_rollout \
  --checkpoint "${CHECKPOINT}" \
  --device "${POLICY_DEVICE:-cuda}" \
  --fps "${CONTROL_FPS:-30}" \
  --left-can "${ROBOT_LEFT_CAN:-can1}" \
  --right-can "${ROBOT_RIGHT_CAN:-can0}" \
  --camera-left "${CAMERA_LEFT:-/dev/camera_left}" \
  --camera-middle "${CAMERA_MIDDLE:-/dev/camera_middle}" \
  --camera-right "${CAMERA_RIGHT:-/dev/camera_right}" \
  --latency-csv results/latency_results.csv \
  "$@"
