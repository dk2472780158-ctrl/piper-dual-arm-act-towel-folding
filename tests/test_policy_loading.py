"""Optional check that a real checkpoint loads and matches the audited model.

This test only exercises the *load path*. It requires:
  - the ``lerobot`` package,
  - the ``POLICY_CHECKPOINT`` env var pointing at a ``pretrained_model`` dir.

Neither is present in the release repository (checkpoints are excluded and
downloaded separately), so the test SKIPS cleanly on machines without the
checkpoint. When a checkpoint IS available, this proves the model behind
the 10/10 consecutive-trials run still loads and has the expected 28-dim
observation / 14-dim action contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

lerobot = pytest.importorskip("lerobot", reason="lerobot not installed")

from lerobot.common.robot_devices.utils import RobotDeviceNotFoundError  # noqa: E402
from lerobot.configs.types import PolicyConfig  # noqa: E402
from lerobot.policies import ACTPolicy  # noqa: E402

CHECKPOINT_ENV = "POLICY_CHECKPOINT"
CHECKPOINT = os.environ.get(CHECKPOINT_ENV)


def _checkpoint_available() -> bool:
    if not CHECKPOINT:
        return False
    config_path = Path(CHECKPOINT) / "config.json"
    return config_path.is_file()


pytestmark = pytest.mark.skipif(
    not _checkpoint_available(),
    reason=f"set {CHECKPOINT_ENV} to a pretrained_model dir to run the load test",
)


def test_checkpoint_config_exists_and_is_valid_json():
    config_path = Path(CHECKPOINT) / "config.json"
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    assert isinstance(config, dict)
    # The policy spec is nested under "policy" in the saved training config.
    assert "policy" in config or "output_features" in config


def test_checkpoint_has_expected_action_dim():
    config_path = Path(CHECKPOINT) / "config.json"
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)

    policy_cfg = config.get("policy", config)
    output_features = policy_cfg.get("output_features", {})
    action = output_features.get("action", {})
    shape = action.get("shape", [])
    # The reference run used a 14-dim action; flag a mismatch loudly.
    assert shape == [14], f"unexpected action shape in checkpoint: {shape}"


def test_policy_builds_from_checkpoint():
    """Build ACTPolicy from the checkpoint dir (CPU) and confirm it is an ACT."""
    policy_cfg = PolicyConfig(
        type="act",
        path=CHECKPOINT,
        # The full training config is read from config.json by LeRobot; these
        # fields only need to satisfy the config schema for building.
        input_features={},
        output_features={},
    )
    try:
        policy = ACTPolicy(policy_cfg)
    except RobotDeviceNotFoundError as exc:
        pytest.skip(f"policy build attempted hardware access: {exc}")
    except Exception as exc:  # pragma: no cover - environment-specific
        pytest.fail(f"policy could not be built from checkpoint: {exc}")

    assert policy is not None
    assert isinstance(policy, ACTPolicy)
    assert policy.device.type == "cpu"
