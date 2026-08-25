#!/usr/bin/env bash
# ------------------------------------------------------------------
# Safety-first synchronous ACT rollout on the dual Piper arms.
#
# Default is a DRY-RUN (arms are read but never enabled). To really move
# the arms you must pass --execute, and the runner additionally requires
# you to type EXECUTE and to give a positive --max-steps budget.
#
# Usage:
#   # dry-run (safe, no motion)
#   ./scripts/evaluate_act.sh
#
#   # real execution, 600 steps = 20 s at 30 Hz
#   ./scripts/evaluate_act.sh --execute --max-steps 600
#
# ⚠️  REAL-ROBOT WARNING ⚠️
#   - The arms must ALREADY be at the training start pose (run reset_pose first).
#   - Keep the hardware emergency stop in your hand.
#   - An assistant should watch the workspace and the cable management.
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
  "$@"
