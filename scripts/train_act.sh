#!/usr/bin/env bash
# ------------------------------------------------------------------
# Train an ACT policy on the towel-folding dataset (single GPU).
#
# Prerequisites:
#   - LeRobot installed (see README) with the torchcodec video backend
#   - the LeRobot-format dataset available at $DATASET_ROOT
#
# Usage:
#   DATASET_ROOT=/path/to/dataset ./scripts/train_act.sh
#   DATASET_ROOT=/path/to/dataset OUTPUT_DIR=outputs/train/myrun ./scripts/train_act.sh
#
# Checkpoints are written to $OUTPUT_DIR/checkpoints/ at every 10k steps.
# Resume with:  lerobot-train --config configs/train_example.yaml --resume true
# ------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

DATASET_ROOT="${DATASET_ROOT:?Set DATASET_ROOT to the LeRobot dataset directory}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/train/towel_fold_act}"
STEPS="${STEPS:-50000}"
BATCH_SIZE="${BATCH_SIZE:-8}"

# Guard: the reference run was on a single GPU.
if [ "$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)" -gt 1 ]; then
  echo "WARNING: multiple GPUs detected. This script is single-GPU; use accelerate for DDP." >&2
fi

exec python -m lerobot.scripts.lerobot_train \
  --config configs/train_example.yaml \
  --dataset.root "${DATASET_ROOT}" \
  --output_dir "${OUTPUT_DIR}" \
  --steps "${STEPS}" \
  --batch_size "${BATCH_SIZE}"
