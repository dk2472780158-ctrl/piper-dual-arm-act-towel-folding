#!/usr/bin/env bash
# ------------------------------------------------------------------
# Verify the software and hardware prerequisites for this project.
#
#   ./scripts/check_environment.sh
#
# Exits non-zero if a hard requirement is missing. Prints WARNINGS for
# optional items.
# ------------------------------------------------------------------
set -uo pipefail

cd "$(dirname "$0")/.."

fail=0
warn=0

say()  { printf '\033[1m[%s]\033[0m %s\n' "$1" "$2"; }
ok()   { printf '  \033[32mOK\033[0m     %s\n' "$1"; }
bad()  { printf '  \033[31mMISSING\033[0m %s\n' "$1"; }
warnf(){ printf '  \033[33mWARN\033[0m   %s\n' "$1"; }

say "python" ">= 3.10"
if command -v python >/dev/null 2>&1 && python -c 'import sys; exit(0 if sys.version_info >= (3,10) else 1)'; then
  ok "python $(python --version 2>&1)"
else
  bad "python >= 3.10"; fail=1
fi

say "pip packages"
for pkg in torch lerobot piper_sdk numpy opencv-python; do
  if python -c "import importlib.util; s=importlib.util.find_spec('$pkg')" >/dev/null 2>&1; then
    ok "$pkg"
  else
    bad "$pkg (pip install $pkg)"; fail=1
  fi
done

say "lerobot piper_dual type"
if python -c "
import lerobot.robots.piper_dual  # noqa: F401  (registers PIPERDualConfig)
from lerobot.robots.config import RobotConfig
assert 'piper_dual' in RobotConfig.get_known_choices(), 'not registered'
" >/dev/null 2>&1; then
  ok "piper_dual registered — run_act.sh --client will resolve --robot.type=piper_dual"
else
  warnf "piper_dual not registered — run ./scripts/setup_piper_dual.sh"
  warn=$((warn+1))
fi

say "CUDA"
if python -c "import torch; assert torch.cuda.is_available()" >/dev/null 2>&1; then
  ok "cuda $(python -c 'import torch; print(torch.version.cuda)')"
else
  warnf "CUDA unavailable — training and cuda inference need a GPU"
  warn=$((warn+1))
fi

say "CAN buses"
for can in "${ROBOT_LEFT_CAN:-can1}" "${ROBOT_RIGHT_CAN:-can0}"; do
  if [ -e "/dev/$can" ]; then
    ok "/dev/$can"
  else
    warnf "/dev/$can not present — expected on the real robot host"
    warn=$((warn+1))
  fi
done

say "cameras"
for cam in left middle right; do
  dev="${CAMERA_$(echo "$cam" | tr '[:lower:]' '[:upper:]'):-/dev/camera_$cam}"
  if [ -L "$dev" ] && [ -e "$dev" ]; then
    ok "$dev -> $(readlink -f "$dev")"
  else
    warnf "$dev missing — set up udev symlinks (see README)"
    warn=$((warn+1))
  fi
done

say "checkpoint"
if [ -n "${POLICY_CHECKPOINT:-}" ] && [ -f "$POLICY_CHECKPOINT/config.json" ]; then
  ok "checkpoint at $POLICY_CHECKPOINT"
else
  warnf "POLICY_CHECKPOINT not set or missing config.json"
  warn=$((warn+1))
fi

echo
if [ "$fail" -gt 0 ]; then
  echo "❌  $fail hard requirement(s) missing."
  exit 1
fi
echo "✅  all hard requirements met ($warn warning(s))."
