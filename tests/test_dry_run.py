"""Behavior of the safety layer that guards every real-robot rollout.

These tests run on any machine (numpy only, no robot, no GPU). They prove
the guards that sit between the policy output and the arm commands behave
the way the paper/report claims.
"""

from __future__ import annotations

import numpy as np
import pytest

from piper_towel_folding.safety import (
    TRAINING_START_ACTION,
    RolloutConfig,
    validate_command_step,
    validate_hardware_limits,
    validate_start_pose,
    validate_tracking_error,
)


# ------------------------------------------------------------------
# validate_hardware_limits
# ------------------------------------------------------------------
def test_hardware_limits_accept_start_pose():
    validate_hardware_limits(TRAINING_START_ACTION)  # must not raise


def test_hardware_limits_reject_out_of_range_joint():
    action = TRAINING_START_ACTION.copy()
    action[0] = 3.0  # joint_1 upper limit is 2.6179
    with pytest.raises(ValueError, match="exceeds Piper hardware limits"):
        validate_hardware_limits(action)


def test_hardware_limits_reject_negative_gripper():
    action = TRAINING_START_ACTION.copy()
    action[6] = -0.01  # below 0.0 m
    with pytest.raises(ValueError, match="exceeds Piper hardware limits"):
        validate_hardware_limits(action)


# ------------------------------------------------------------------
# validate_command_step
# ------------------------------------------------------------------
def test_small_step_passes():
    ref = TRAINING_START_ACTION.copy()
    action = ref.copy()
    action[0] += 0.02  # well under the 0.10 rad limit
    validate_command_step(action, ref, max_joint_step=0.10, max_gripper_step=0.01)


def test_big_joint_jump_rejected():
    ref = TRAINING_START_ACTION.copy()
    action = ref.copy()
    action[0] += 0.30  # 3x the step limit
    with pytest.raises(ValueError, match="consecutive joint command change is too large"):
        validate_command_step(action, ref, max_joint_step=0.10, max_gripper_step=0.01)


def test_big_gripper_jump_rejected():
    ref = TRAINING_START_ACTION.copy()
    action = ref.copy()
    action[13] = 0.08  # jump of 0.08 m against a 0.01 m limit
    with pytest.raises(ValueError, match="consecutive gripper command change is too large"):
        validate_command_step(action, ref, max_joint_step=0.10, max_gripper_step=0.01)


def test_step_check_disabled_with_zero_limit():
    # A limit of 0 disables the check (used when configs wish to turn it off).
    ref = TRAINING_START_ACTION.copy()
    action = ref.copy()
    action[0] += 1.0
    validate_command_step(action, ref, max_joint_step=0.0, max_gripper_step=0.0)


# ------------------------------------------------------------------
# validate_tracking_error
# ------------------------------------------------------------------
def test_well_tracked_pose_passes():
    measured = TRAINING_START_ACTION.copy()
    commanded = TRAINING_START_ACTION.copy()
    validate_tracking_error(
        measured,
        commanded,
        max_joint_error=0.35,
        max_gripper_error=0.03,
    )


def test_stalled_arm_rejected():
    # Measured pose is far from the commanded pose: arm is blocked/stalled.
    measured = TRAINING_START_ACTION.copy()
    commanded = TRAINING_START_ACTION.copy()
    commanded[0] += 0.5
    with pytest.raises(ValueError, match="not tracking its command"):
        validate_tracking_error(
            measured,
            commanded,
            max_joint_error=0.35,
            max_gripper_error=0.03,
        )


def test_stalled_gripper_rejected():
    measured = TRAINING_START_ACTION.copy()
    commanded = TRAINING_START_ACTION.copy()
    commanded[13] = 0.08
    with pytest.raises(ValueError, match="gripper is not tracking its command"):
        validate_tracking_error(
            measured,
            commanded,
            max_joint_error=0.35,
            max_gripper_error=0.03,
        )


# ------------------------------------------------------------------
# validate_start_pose
# ------------------------------------------------------------------
def test_start_pose_within_tolerance_passes():
    pose = TRAINING_START_ACTION.copy()
    pose[0] += 0.10  # under 0.15 rad
    validate_start_pose(pose)


def test_start_pose_too_far_rejected():
    pose = TRAINING_START_ACTION.copy()
    pose[0] += 0.30  # over 0.15 rad
    with pytest.raises(ValueError, match="outside the training start distribution"):
        validate_start_pose(pose)


def test_gripper_start_pose_too_far_rejected():
    pose = TRAINING_START_ACTION.copy()
    pose[6] = 0.05  # 0.05 m from 0.0, over the 0.02 m gripper tolerance
    with pytest.raises(ValueError, match="gripper pose is outside"):
        validate_start_pose(pose)


def test_custom_start_pose_is_used_when_given():
    custom = TRAINING_START_ACTION.copy()
    custom[0] += 0.4  # a genuinely different canonical start
    pose = custom.copy()
    pose[0] += 0.05  # 0.05 rad from custom -> within the 0.15 rad tolerance
    validate_start_pose(pose, start_pose=custom)  # passes against custom
    with pytest.raises(ValueError):
        validate_start_pose(pose)  # 0.45 rad from the default -> refuses


# ------------------------------------------------------------------
# RolloutConfig
# ------------------------------------------------------------------
def test_rollout_config_defaults_match_documented_limits():
    cfg = RolloutConfig()
    assert cfg.start_joint_tolerance == 0.15
    assert cfg.start_gripper_tolerance == 0.02
    assert cfg.max_joint_step == 0.10
    assert cfg.max_gripper_step == 0.01
    assert cfg.max_tracking_error == 0.35
    assert cfg.max_gripper_tracking_error == 0.03
