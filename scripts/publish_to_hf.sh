#!/usr/bin/env bash
# ------------------------------------------------------------------
# Publish the 120-demo dataset and the v4 040000 checkpoint to Hugging Face.
#
# Runs on the CONTROL HOST — that is where the LeRobot dataset cache, the
# trained weights and the lerobot_v30 conda env (with huggingface-cli) live.
#
# Default is a DRY-RUN: validates source paths and shows the plan, then
# stops. To actually publish you must pass --publish AND type REVIEWED and
# PUBLISH (the repo's no-unconfirmed-push red line applies to HF too).
#
# What this script publishes:
#   dataset  ->  HF dataset repo (LeRobot layout: meta/ + episodes/ + videos/)
#   model    ->  HF model repo    (pretrained_model/: config + safetensors + processors)
# It does NOT publish: the earlier runs (v1/v2/v3, cube_r2l_act_v1; v2 used
# the 60-demo towel_fold_dataset), raw videos, camera serials, or any
# lab/identifiable-person footage. Review every episode for faces before
# publishing (see docs/publishing.md).
#
# Usage:
#   DATASET_SOURCE="$HOME/.cache/huggingface/lerobot/local/towel_fold_dataset_aug_v1" \
#   MODEL_SOURCE="/path/to/towel_fold_act_v4_scratch60k/checkpoints/040000/pretrained_model" \
#   HF_DATASET_REPO="1goldexperience1/towel_fold_dataset_aug_v1" \
#   HF_MODEL_REPO="1goldexperience1/towel_fold_act_v4_040000" \
#   HF_TOKEN="hf_..." ./scripts/publish_to_hf.sh --publish
# ------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

DATASET_SOURCE="${DATASET_SOURCE:-$HOME/.cache/huggingface/lerobot/local/towel_fold_dataset_aug_v1}"
MODEL_SOURCE="${MODEL_SOURCE:?Set MODEL_SOURCE to the v4 040000 pretrained_model directory}"
HF_DATASET_REPO="${HF_DATASET_REPO:-1goldexperience1/towel_fold_dataset_aug_v1}"
HF_MODEL_REPO="${HF_MODEL_REPO:-1goldexperience1/towel_fold_act_v4_040000}"

echo "Publish plan"
echo "  dataset source : $DATASET_SOURCE"
echo "  dataset target : https://huggingface.co/datasets/$HF_DATASET_REPO"
echo "  model source   : $MODEL_SOURCE"
echo "  model target   : https://huggingface.co/$HF_MODEL_REPO"
echo

# --- Validate sources (cheap sanity before any network) ---
[ -d "$DATASET_SOURCE/meta" ] || {
  echo "ERROR: expected LeRobot dataset layout (meta/) at $DATASET_SOURCE" >&2; exit 1; }
[ -f "$MODEL_SOURCE/model.safetensors" ] && [ -f "$MODEL_SOURCE/config.json" ] || {
  echo "ERROR: model.safetensors / config.json not found in $MODEL_SOURCE" >&2; exit 1; }

if [ "${1:-}" != "--publish" ]; then
  echo "DRY-RUN: nothing uploaded. Re-run with --publish after you have:"
  echo "  - reviewed episodes for faces / identifiable people / lab identity"
  echo "  - set HF_TOKEN (export HF_TOKEN=... or run huggingface-cli login)"
  exit 0
fi

command -v huggingface-cli >/dev/null 2>&1 || {
  echo "ERROR: huggingface-cli not found. Use the lerobot_v30 conda env:" >&2
  echo "  conda activate lerobot_v30" >&2; exit 1; }
[ -n "${HF_TOKEN:-}" ] || {
  echo "ERROR: HF_TOKEN is not set (huggingface-cli login or export HF_TOKEN=...)" >&2; exit 1; }

read -r -p "Type REVIEWED if you inspected every episode for faces/identifiable people: " reviewed
[ "$reviewed" = "REVIEWED" ] || { echo "Cancelled."; exit 1; }
read -r -p "Type PUBLISH to upload to Hugging Face (public, effectively permanent): " ok
[ "$ok" = "PUBLISH" ] || { echo "Cancelled."; exit 1; }

# --- Create repos (ignore 'already exists') ---
huggingface-cli repo create "$HF_DATASET_REPO" --type dataset || true
huggingface-cli repo create "$HF_MODEL_REPO" --type model || true

# --- Upload ---
huggingface-cli upload "$HF_DATASET_REPO" "$DATASET_SOURCE" --repo-type dataset
huggingface-cli upload "$HF_MODEL_REPO" "$MODEL_SOURCE" --repo-type model

cat <<EOF
Published:
  https://huggingface.co/datasets/$HF_DATASET_REPO
  https://huggingface.co/$HF_MODEL_REPO
Next: paste these URLs into docs/publishing.md, .env.example and the README
download section, then reword docs/reproducibility.md to say data/weights are
downloadable (no longer 待确认).
EOF
