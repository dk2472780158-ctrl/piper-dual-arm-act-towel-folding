#!/usr/bin/env bash
# ------------------------------------------------------------------
# Deploy the async gRPC ACT inference stack used for the real trials:
#   policy_server (CUDA)  <-- gRPC -->  robot_client (robot + cameras)
#
# This mirrors the reference deployment: ACT on cuda, chunk truncated to
# ACTIONS_PER_CHUNK steps, weighted_average blending of overlapping chunks,
# 30 Hz control. This is the exact configuration behind the 10/10
# consecutive-trials video.
#
# Usage:
#   ./scripts/run_act.sh                    # terminal A (server) then terminal B (client)
#   ./scripts/run_act.sh --client           # run the client in this terminal
#   ./scripts/run_act.sh --server           # run the server in this terminal
#
# ⚠️  REAL-ROBOT WARNING ⚠️
#   - Move the arms to the start pose first:  python -m piper_towel_folding.reset_pose --arm both --execute
#   - Keep the hardware emergency stop in your hand.
#   - Arms stay ENABLED after Ctrl+C and hold their last pose — do not walk
#     away or power off without physically supporting them.
# ------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a; source .env; set +a
fi

SERVER_ADDRESS="${SERVER_ADDRESS:-127.0.0.1:8082}"
HOST="${SERVER_ADDRESS%%:*}"
PORT="${SERVER_ADDRESS##*:}"

POLICY_TYPE="${POLICY_TYPE:-act}"
CHECKPOINT="${POLICY_CHECKPOINT:?Set POLICY_CHECKPOINT to the pretrained_model directory}"
POLICY_DEVICE="${POLICY_DEVICE:-cuda}"
CLIENT_DEVICE="${CLIENT_DEVICE:-cpu}"
FPS="${CONTROL_FPS:-30}"

run_server() {
  echo "Starting policy server on ${SERVER_ADDRESS} ..."
  exec python -m lerobot.async_inference.policy_server \
    --host "${HOST}" --port "${PORT}" --fps "${FPS}"
}

run_client() {
  LEFT_IDX="$(readlink -f "${CAMERA_LEFT:-/dev/camera_left}")"
  MIDDLE_IDX="$(readlink -f "${CAMERA_MIDDLE:-/dev/camera_middle}")"
  RIGHT_IDX="$(readlink -f "${CAMERA_RIGHT:-/dev/camera_right}")"
  for dev in "$LEFT_IDX" "$MIDDLE_IDX" "$RIGHT_IDX"; do
    if ! [[ "$dev" =~ ^/dev/video[0-9]+$ ]]; then
      echo "ERROR: invalid camera device: $dev" >&2
      exit 1
    fi
  done

  CAMERAS="{\"left\":{\"type\":\"opencv\",\"index_or_path\":${LEFT_IDX##/dev/video},\"width\":640,\"height\":480,\"fps\":30,\"rotation\":0},\
\"middle\":{\"type\":\"opencv\",\"index_or_path\":${MIDDLE_IDX##/dev/video},\"width\":640,\"height\":480,\"fps\":30,\"rotation\":0},\
\"right\":{\"type\":\"opencv\",\"index_or_path\":${RIGHT_IDX##/dev/video},\"width\":640,\"height\":480,\"fps\":30,\"rotation\":0}}"

  # No extra Piper joint filter: the client already blends chunks, and a
  # second low-pass would add double latency.
  export PIPER_ACTION_FILTER_ALPHA=1.0

  echo "Starting robot client against ${SERVER_ADDRESS} ..."
  exec python -m lerobot.async_inference.robot_client \
    --server_address="${SERVER_ADDRESS}" \
    --robot.type=piper_dual \
    --robot.left_port="${ROBOT_LEFT_CAN:-can1}" \
    --robot.right_port="${ROBOT_RIGHT_CAN:-can0}" \
    --robot.cameras="${CAMERAS}" \
    --task="${TASK_TEXT:-Fold the towel with both Piper arms.}" \
    --policy_type="${POLICY_TYPE}" \
    --pretrained_name_or_path="${CHECKPOINT}" \
    --policy_device="${POLICY_DEVICE}" \
    --client_device="${CLIENT_DEVICE}" \
    --actions_per_chunk="${ACTIONS_PER_CHUNK:-30}" \
    --chunk_size_threshold="${CHUNK_SIZE_THRESHOLD:-0.6}" \
    --aggregate_fn_name="${AGGREGATE_FN:-weighted_average}" \
    --fps="${FPS}" \
    --debug_visualize_queue_size=false
}

case "${1:-}" in
  --server) run_server ;;
  --client) run_client ;;
  "")
    echo "Run the server and the client in two terminals:"
    echo "  terminal A:  ./scripts/run_act.sh --server"
    echo "  terminal B:  ./scripts/run_act.sh --client"
    ;;
  *) echo "Usage: $0 [--server|--client]" >&2; exit 2 ;;
esac
