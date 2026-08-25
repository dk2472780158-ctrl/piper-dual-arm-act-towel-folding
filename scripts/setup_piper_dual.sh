#!/usr/bin/env bash
# ------------------------------------------------------------------
# Install the `piper_dual` robot type into an existing LeRobot install.
#
# WHY THIS EXISTS
#   The reference stack runs on a LeRobot fork that adds a `piper_dual`
#   robot (two AgileX Piper arms on CAN + 3 cameras). Stock LeRobot has no
#   such robot type, so `python -m lerobot.async_inference.robot_client
#   --robot.type=piper_dual` (see scripts/run_act.sh) would fail on a stock
#   install. This script vendors the exact module into YOUR LeRobot install.
#
# WHAT IT DOES
#   1. Locates the installed lerobot package.
#   2. Copies in:
#        lerobot/robots/piper_dual/   (PIPERDual + PIPERDualConfig)
#        lerobot/motors/piper/        (slave follower bus + read-only master bus)
#   3. Appends `piper_dual` to the robot-import list of:
#        lerobot/async_inference/robot_client.py   (async deployment)
#        lerobot/scripts/lerobot_record.py         (data collection)
#      Every patched file is backed up to <file>.bak.piper_dual first.
#   4. Smoke-checks that the type now imports and registers.
#
# ⚠️  RED-LINE NOTE
#   This edits the LeRobot install ON YOUR OWN machine (a fresh / dev env is
#   recommended). It does NOT touch the original ACT project, training
#   configs, checkpoints, or datasets, and it never enables motors or sends
#   CAN commands. Run it once per (re)install.
#
# USAGE
#   ./scripts/setup_piper_dual.sh [--lerobot-dir /path/to/lerobot] [--python python]
#
# EXIT CODES
#   0  done (or already applied, idempotent)
#   1  hard error (missing install / unexpected layout / smoke test failed)
# ------------------------------------------------------------------
set -uo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
VENDOR_DIR="${REPO_ROOT}/lerobot_piper"

say()  { printf '\033[1m[%s]\033[0m %s\n' "$1" "$2"; }
ok()   { printf '  \033[32mOK\033[0m     %s\n' "$1"; }
warnf(){ printf '  \033[33mWARN\033[0m   %s\n' "$1"; }
bad()  { printf '  \033[31mMISSING\033[0m %s\n' "$1"; }

PYTHON_BIN="${PYTHON_BIN:-python}"
LEROBOT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --lerobot-dir) LEROBOT_DIR="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# --- 1. locate lerobot ----------------------------------------------------
if [ -z "$LEROBOT_DIR" ]; then
  LEROBOT_DIR="$("$PYTHON_BIN" -c "import lerobot, pathlib; print(pathlib.Path(lerobot.__path__[0]))" 2>/dev/null)"
fi
if [ -z "$LEROBOT_DIR" ] || [ ! -d "$LEROBOT_DIR" ]; then
  bad "could not locate the installed lerobot package (is 'lerobot' importable via ${PYTHON_BIN}?)"
  echo "       hint: activate the target env first, then run this script again."
  exit 1
fi
LEROBOT_DIR="$(cd "$LEROBOT_DIR" && pwd)"
say "lerobot" "$LEROBOT_DIR"

# --- 2. verify expected layout -------------------------------------------
need() {
  if [ ! -e "$1" ]; then
    bad "unexpected layout: expected $1 (does this lerobot version match the fork layout?)"
    exit 1
  fi
}
need "$LEROBOT_DIR/robots/config.py"
need "$LEROBOT_DIR/robots/utils.py"
need "$LEROBOT_DIR/motors"
need "$LEROBOT_DIR/async_inference/robot_client.py"
need "$LEROBOT_DIR/scripts/lerobot_record.py"
ok "expected layout found (robots/config.py, async_inference, scripts/lerobot_record.py)"

# --- 3. copy vendored modules ---------------------------------------------
cp -r "${VENDOR_DIR}/robots/piper_dual" "$LEROBOT_DIR/robots/"
ok "copied robots/piper_dual/"
mkdir -p "$LEROBOT_DIR/motors/piper"
cp -r "${VENDOR_DIR}/motors/piper/." "$LEROBOT_DIR/motors/piper/"
ok "copied motors/piper/"

# --- 4. patch the robot-import lists (idempotent, with backup) -----------
patch_import() {
  local f="$1"
  if grep -q '^    piper_dual,' "$f"; then
    ok "already patched: ${f#$LEROBOT_DIR/}"
    return 0
  fi
  if ! grep -q 'from lerobot.robots import (' "$f"; then
    bad "could not find the 'from lerobot.robots import (' block in ${f#$LEROBOT_DIR/}"
    return 1
  fi
  cp "$f" "$f.bak.piper_dual"
  # Insert `    piper_dual,` on the line right after the import opener.
  sed -i '/^from lerobot\.robots import ($/a\    piper_dual,' "$f"
  ok "patched ${f#$LEROBOT_DIR/} (backup: ${f#$LEROBOT_DIR/}.bak.piper_dual)"
}

patch_import "$LEROBOT_DIR/async_inference/robot_client.py" || exit 1
patch_import "$LEROBOT_DIR/scripts/lerobot_record.py" || exit 1

# --- 5. smoke test ---------------------------------------------------------
say "smoke test" "import + registration"
if "$PYTHON_BIN" -c "import lerobot.robots.piper_dual  # registers PIPERDualConfig
from lerobot.robots.config import RobotConfig
assert 'piper_dual' in RobotConfig.get_known_choices(), 'piper_dual not registered'
print('  OK     piper_dual registered as a robot type')" ; then
  ok "piper_dual imports and registers"
else
  bad "smoke test failed — piper_dual did not import/register"
  echo "       check that piper_sdk is installed in this env (import piper_sdk)."
  exit 1
fi

echo
say "done" "piper_dual is ready. Next: ./scripts/check_environment.sh"
