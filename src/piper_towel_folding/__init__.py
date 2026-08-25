"""piper-dual-arm-act-towel-folding.

End-to-end imitation learning for real-time bimanual towel folding using the
Action Chunking Transformer, three RGB cameras, and dual AgileX Piper arms.
"""

__version__ = "0.1.0"

from piper_towel_folding.safety import (
    ARM_JOINT_INDICES,
    GRIPPER_INDICES,
    SINGLE_ARM_LOWER_LIMITS,
    SINGLE_ARM_UPPER_LIMITS,
    TRAINING_START_ACTION,
    normalize_gripper_commands,
    validate_action_shape,
    validate_command_step,
    validate_hardware_limits,
    validate_start_pose,
    validate_tracking_error,
)

__all__ = [
    "ARM_JOINT_INDICES",
    "GRIPPER_INDICES",
    "SINGLE_ARM_LOWER_LIMITS",
    "SINGLE_ARM_UPPER_LIMITS",
    "TRAINING_START_ACTION",
    "normalize_gripper_commands",
    "validate_action_shape",
    "validate_command_step",
    "validate_hardware_limits",
    "validate_start_pose",
    "validate_tracking_error",
]
