"""Safety validators for dual-Piper ACT rollout.

This module is the safety layer that guards every action sent to the arms
during real-robot evaluation. It is intentionally dependency-free (numpy
only) so it can be unit-tested in isolation and reused by any runner.

The limits below are taken from the physical joint ranges reported by the
AgileX Piper SDK (v0.6.2) and from the demonstrated training start pose of
the towel-folding dataset. They are hardware limits, not task-workspace
limits.

Action layout
-------------
A 14-dimensional action is ordered as::

    [left_j1 .. left_j6, left_gripper, right_j1 .. right_j6, right_gripper]

Gripper commands are in meters in [0.0, 0.08]. Joints are in radians.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ------------------------------------------------------------------
# Indices into the 14-dim action vector.
# ------------------------------------------------------------------
ARM_JOINT_INDICES = np.asarray([0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], dtype=np.int64)
GRIPPER_INDICES = np.asarray([6, 13], dtype=np.int64)


# ------------------------------------------------------------------
# Piper hardware limits (AgileX Piper SDK v0.6.2 physical limits).
# ------------------------------------------------------------------
SINGLE_ARM_LOWER_LIMITS = np.asarray(
    [
        -2.6179,  # joint_1
        0.0,  # joint_2
        -2.967,  # joint_3
        -1.745,  # joint_4
        -1.22,  # joint_5
        -2.09439,  # joint_6
        0.0,  # gripper
    ],
    dtype=np.float32,
)

SINGLE_ARM_UPPER_LIMITS = np.asarray(
    [
        2.6179,  # joint_1
        3.14,  # joint_2
        0.0,  # joint_3
        1.745,  # joint_4
        1.22,  # joint_5
        2.09439,  # joint_6
        0.08,  # gripper
    ],
    dtype=np.float32,
)

ACTION_LOWER_LIMITS = np.concatenate([SINGLE_ARM_LOWER_LIMITS, SINGLE_ARM_LOWER_LIMITS])
ACTION_UPPER_LIMITS = np.concatenate([SINGLE_ARM_UPPER_LIMITS, SINGLE_ARM_UPPER_LIMITS])


# ------------------------------------------------------------------
# Training start pose.
#
# The frame-0 action of the reference dataset, used as the canonical
# "demonstrated initial pose". The arms must already be close to this
# pose before real execution starts. The reset tool (reset_pose.py) moves
# the arms here slowly.
# ------------------------------------------------------------------
TRAINING_START_ACTION = np.asarray(
    [
        0.1322,  # left j1
        0.0,
        0.0,
        -0.3772,
        0.2701,
        0.4532,
        0.0,  # left gripper
        -0.1117,  # right j1
        0.0,
        0.0,
        0.2554,
        0.3608,
        -0.2034,
        0.0,  # right gripper
    ],
    dtype=np.float32,
)


def validate_action_shape(action: np.ndarray) -> None:
    """A valid action is a 14-vector with only finite values."""
    if action.shape != (14,):
        raise ValueError(f"Expected action shape (14,), got {action.shape}")
    if not np.isfinite(action).all():
        raise ValueError(f"Action contains NaN or Inf: {action}")


def normalize_gripper_commands(action: np.ndarray) -> np.ndarray:
    """Clip gripper predictions to [0, 0.08] m.

    The Piper bus applies ``abs()`` to the gripper target, so a negative
    prediction would silently become an opening command. Explicit clipping
    makes the behavior deterministic and safe.
    """
    result = action.copy()
    result[GRIPPER_INDICES] = np.clip(result[GRIPPER_INDICES], 0.0, 0.08)
    return result


def validate_hardware_limits(action: np.ndarray) -> None:
    """Reject any action outside the Piper physical joint limits."""
    # Tiny epsilon only avoids false positives at exact float32/float64
    # boundaries (e.g. float64(0.08) vs float32(0.08)); it does not
    # materially expand the limits.
    limit_epsilon = 1e-6
    below = action < (ACTION_LOWER_LIMITS - limit_epsilon)
    above = action > (ACTION_UPPER_LIMITS + limit_epsilon)
    invalid = np.flatnonzero(below | above)
    if invalid.size == 0:
        return

    details = [
        f"index={i}, value={action[i]:.6f}, "
        f"range=[{ACTION_LOWER_LIMITS[i]:.6f}, {ACTION_UPPER_LIMITS[i]:.6f}]"
        for i in invalid
    ]
    raise ValueError("Safety stop: action exceeds Piper hardware limits: " + "; ".join(details))


def validate_command_step(
    action: np.ndarray,
    reference: np.ndarray,
    max_joint_step: float,
    max_gripper_step: float,
) -> None:
    """Reject commands that would jump too far between consecutive steps.

    This guards against a single bad policy output yanking an arm, which is
    the most common catastrophic failure in imitation-learning rollouts.
    """
    delta = np.abs(action - reference)

    if max_joint_step > 0:
        joint_delta = delta[ARM_JOINT_INDICES]
        largest_offset = int(joint_delta.argmax())
        largest = float(joint_delta[largest_offset])
        if largest > max_joint_step:
            index = int(ARM_JOINT_INDICES[largest_offset])
            raise ValueError(
                "Safety stop: consecutive joint command change is too large: "
                f"index={index}, previous={reference[index]:.6f}, "
                f"action={action[index]:.6f}, delta={largest:.6f} rad, "
                f"limit={max_joint_step:.6f} rad"
            )

    if max_gripper_step > 0:
        gripper_delta = delta[GRIPPER_INDICES]
        largest_offset = int(gripper_delta.argmax())
        largest = float(gripper_delta[largest_offset])
        if largest > max_gripper_step:
            index = int(GRIPPER_INDICES[largest_offset])
            raise ValueError(
                "Safety stop: consecutive gripper command change is too large: "
                f"index={index}, previous={reference[index]:.6f}, "
                f"action={action[index]:.6f}, delta={largest:.6f} m, "
                f"limit={max_gripper_step:.6f} m"
            )


def validate_tracking_error(
    measured_positions: np.ndarray,
    previous_action: np.ndarray,
    max_joint_error: float,
    max_gripper_error: float,
) -> None:
    """Reject rollouts where the arm stops following its own commands.

    A large measured-vs-commanded error means the arm is stalled against an
    obstacle or has been manually blocked; continuing would push excessive
    torque. Stop instead.
    """
    error = np.abs(measured_positions - previous_action)

    if max_joint_error > 0:
        joint_error = error[ARM_JOINT_INDICES]
        largest_offset = int(joint_error.argmax())
        largest = float(joint_error[largest_offset])
        if largest > max_joint_error:
            index = int(ARM_JOINT_INDICES[largest_offset])
            raise ValueError(
                "Safety stop: arm is not tracking its command: "
                f"index={index}, measured={measured_positions[index]:.6f}, "
                f"commanded={previous_action[index]:.6f}, "
                f"error={largest:.6f} rad, limit={max_joint_error:.6f} rad"
            )

    if max_gripper_error > 0:
        gripper_error = error[GRIPPER_INDICES]
        largest_offset = int(gripper_error.argmax())
        largest = float(gripper_error[largest_offset])
        if largest > max_gripper_error:
            index = int(GRIPPER_INDICES[largest_offset])
            raise ValueError(
                "Safety stop: gripper is not tracking its command: "
                f"index={index}, measured={measured_positions[index]:.6f}, "
                f"commanded={previous_action[index]:.6f}, "
                f"error={largest:.6f} m, limit={max_gripper_error:.6f} m"
            )


def validate_start_pose(
    current_positions: np.ndarray,
    joint_tolerance: float = 0.15,
    gripper_tolerance: float = 0.02,
    start_pose: np.ndarray | None = None,
) -> None:
    """Reject rollout if the measured pose is out of the training distribution.

    The model was trained from one demonstrated initial pose. Starting far
    from it produces out-of-distribution observations and erratic behavior,
    so we refuse to start rather than fight a bad rollout.
    """
    start_pose = TRAINING_START_ACTION if start_pose is None else start_pose
    error = np.abs(current_positions - start_pose)

    max_joint_error = float(error[ARM_JOINT_INDICES].max())
    max_gripper_error = float(error[GRIPPER_INDICES].max())

    if max_joint_error > joint_tolerance:
        raise ValueError(
            "Current pose is outside the training start distribution: "
            f"maximum joint error={max_joint_error:.6f} rad, "
            f"limit={joint_tolerance:.6f} rad. Move the arms to the "
            "demonstrated initial pose before rollout."
        )
    if max_gripper_error > gripper_tolerance:
        raise ValueError(
            "Current gripper pose is outside the training start distribution: "
            f"maximum gripper error={max_gripper_error:.6f} m, "
            f"limit={gripper_tolerance:.6f} m."
        )


@dataclass(frozen=True)
class RolloutConfig:
    """Typed safety parameters shared by every real-robot runner."""

    start_joint_tolerance: float = 0.15
    start_gripper_tolerance: float = 0.02
    max_joint_step: float = 0.10
    max_gripper_step: float = 0.01
    max_tracking_error: float = 0.35
    max_gripper_tracking_error: float = 0.03
