"""Shape and finiteness contract of the 14-dim dual-arm action vector."""

from __future__ import annotations

import numpy as np
import pytest

from piper_towel_folding.safety import (
    GRIPPER_INDICES,
    normalize_gripper_commands,
    validate_action_shape,
)


def test_valid_action_shape_passes():
    action = np.zeros(14, dtype=np.float32)
    validate_action_shape(action)  # must not raise


def test_wrong_ndim_raises():
    with pytest.raises(ValueError, match="Expected action shape"):
        validate_action_shape(np.zeros((14, 1), dtype=np.float32))


def test_wrong_length_raises():
    for length in (13, 15, 0):
        with pytest.raises(ValueError, match="Expected action shape"):
            validate_action_shape(np.zeros(length, dtype=np.float32))


def test_nan_raises():
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_action_shape(np.array([np.nan] * 14, dtype=np.float32))


def test_inf_raises():
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_action_shape(np.array([np.inf] * 14, dtype=np.float32))


def test_gripper_indices_are_6_and_13():
    # The layout is [left j1..j6, left_gripper, right j1..j6, right_gripper].
    assert list(GRIPPER_INDICES) == [6, 13]


def test_normalize_gripper_clips_negatives_and_overshoots():
    action = np.zeros(14, dtype=np.float32)
    action[6] = -0.5  # would become a full open command on the Piper bus
    action[13] = 0.2  # above the 0.08 m physical limit
    normalized = normalize_gripper_commands(action)

    assert normalized[6] == 0.0
    assert normalized[13] == 0.08


def test_normalize_gripper_keeps_joints_unchanged():
    action = np.zeros(14, dtype=np.float32)
    action[:6] = np.linspace(-1.0, 1.0, 6)
    normalized = normalize_gripper_commands(action)
    np.testing.assert_array_equal(normalized[:6], action[:6])


def test_normalize_does_not_mutate_input():
    action = np.zeros(14, dtype=np.float32)
    action[6] = -0.5
    original = action.copy()
    normalize_gripper_commands(action)
    np.testing.assert_array_equal(action, original)
