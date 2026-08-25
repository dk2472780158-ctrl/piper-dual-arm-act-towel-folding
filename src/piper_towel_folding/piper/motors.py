"""Piper CAN bus wrappers (follower + master).

A thin, faithful re-implementation of the in-house driver used for the
towel-folding setup. It depends only on the AgileX ``piper_sdk`` package and
adds two safety-relevant behaviors on top of the raw SDK:

* The SDK is opened with its built-in joint and gripper hardware limits
  enabled (``start_sdk_joint_limit`` / ``start_sdk_gripper_limit``).
* An optional first-order low-pass filter can smooth the six arm joints
  (never the gripper), controlled by the environment variable
  ``PIPER_ACTION_FILTER_ALPHA``. Default ``1.0`` disables the filter; keep it
  at ``1.0`` when the async inference client already blends action chunks.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

# Unit conversion factors used by the Piper SDK frames.
JOINT_FACTOR = 57324.840764  # 0.001 deg -> rad
GRIPPER_POS_SCALE = 1_000_000.0  # SDK gripper units -> meters

MOTOR_ORDER = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6", "gripper"]
MOTOR_IDS = list(range(1, 8))  # CAN node ids 1..7 per arm


@dataclass
class PiperMotorsBusConfig:
    can_name: str
    motors: dict[str, tuple[int, str]] | None = None


class PiperMotorsBus:
    """Follower (slave) bus: reads state and writes position commands."""

    def __init__(self, config: PiperMotorsBusConfig):
        from piper_sdk import C_PiperInterface_V2

        # Hardware limit layer from the SDK (final backstop on top of the
        # software validators in piper_towel_folding.safety).
        self.piper = C_PiperInterface_V2(
            config.can_name,
            start_sdk_joint_limit=True,
            start_sdk_gripper_limit=True,
        )
        self.piper.ConnectPort()
        self._is_connected = True

        self.motors = config.motors or {
            name: (idx, "agilex_piper") for name, idx in zip(MOTOR_ORDER, MOTOR_IDS, strict=True)
        }

        # Optional joint low-pass. Disabled by default so data collection and
        # replay stay unchanged; set PIPER_ACTION_FILTER_ALPHA<1.0 only for
        # policy inference (and not when the async client already aggregates).
        self.action_filter_alpha = float(os.environ.get("PIPER_ACTION_FILTER_ALPHA", "1.0"))
        if not 0.0 < self.action_filter_alpha <= 1.0:
            raise ValueError("PIPER_ACTION_FILTER_ALPHA must be in the range (0, 1]")
        self._filtered_joint_target: list[float] | None = None
        if self.action_filter_alpha < 1.0:
            print(
                f"Piper joint filter enabled on {config.can_name}: "
                f"alpha={self.action_filter_alpha:.3f}"
            )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def motor_names(self) -> list[str]:
        return list(self.motors.keys())

    def connect(self, enable: bool) -> bool:
        """Enable (or disable) the arm and wait up to five seconds for the state to settle."""
        timeout = 5.0
        start_time = time.time()
        loop_flag = False
        while not loop_flag:
            enable_list = [
                bool(
                    self.piper.GetArmLowSpdInfoMsgs()
                    .motor_1.foc_status.driver_enable_status
                ),
                bool(
                    self.piper.GetArmLowSpdInfoMsgs()
                    .motor_2.foc_status.driver_enable_status
                ),
                bool(
                    self.piper.GetArmLowSpdInfoMsgs()
                    .motor_3.foc_status.driver_enable_status
                ),
                bool(
                    self.piper.GetArmLowSpdInfoMsgs()
                    .motor_4.foc_status.driver_enable_status
                ),
                bool(
                    self.piper.GetArmLowSpdInfoMsgs()
                    .motor_5.foc_status.driver_enable_status
                ),
                bool(
                    self.piper.GetArmLowSpdInfoMsgs()
                    .motor_6.foc_status.driver_enable_status
                ),
            ]
            if enable:
                enable_flag = all(enable_list)
                while not self.piper.EnablePiper():
                    time.sleep(0.1)
                self.piper.GripperCtrl(0, 1000, 0x01, 0)
            else:
                enable_flag = any(enable_list)
                self.piper.DisableArm(7)
                self.piper.GripperCtrl(0, 1000, 0x02, 0)

            if enable_flag == enable:
                loop_flag = True
                enable_flag = True
            else:
                loop_flag = False
                enable_flag = False

            if time.time() - start_time > timeout:
                enable_flag = False
                loop_flag = True
                break
            time.sleep(0.5)

        self._is_connected = enable_flag
        return enable_flag

    def _filter_target(self, target_joint: list) -> list[float]:
        """Low-pass only the six arm joints; never delay the gripper."""
        if len(target_joint) != 7:
            raise ValueError(f"Expected 7 Piper targets, got {len(target_joint)}")
        target = [float(value) for value in target_joint]
        new_joints = target[:6]
        previous = self._filtered_joint_target
        if previous is None or self.action_filter_alpha >= 1.0:
            filtered_joints = new_joints
        else:
            alpha = self.action_filter_alpha
            filtered_joints = [
                alpha * new + (1.0 - alpha) * old
                for new, old in zip(new_joints, previous, strict=True)
            ]
        self._filtered_joint_target = filtered_joints.copy()
        return filtered_joints + [target[6]]

    def write(self, target_joint: list) -> None:
        """Send a 7-dim position target in radians (joints) / meters (gripper)."""
        target_joint = self._filter_target(target_joint)
        joints = [round(value * JOINT_FACTOR) for value in target_joint[:6]]
        gripper = round(target_joint[6] * 1000 * 1000)

        # Position-control mode with acceleration 0x00 (as used by the SDK).
        self.piper.MotionCtrl_2(0x01, 0x01, 50, 0x00)
        self.piper.JointCtrl(*joints)
        self.piper.GripperCtrl(abs(gripper), 1000, 0x01, 0)

    def read(self) -> dict:
        """Read joint/gripper positions and efforts (7 x {pos, effort})."""
        joint_state = self.piper.GetArmJointMsgs().joint_state
        gripper_state = self.piper.GetArmGripperMsgs().gripper_state
        high_spd = self.piper.GetArmHighSpdInfoMsgs()

        return {
            "joint_1_pos": joint_state.joint_1 / JOINT_FACTOR,
            "joint_2_pos": joint_state.joint_2 / JOINT_FACTOR,
            "joint_3_pos": joint_state.joint_3 / JOINT_FACTOR,
            "joint_4_pos": joint_state.joint_4 / JOINT_FACTOR,
            "joint_5_pos": joint_state.joint_5 / JOINT_FACTOR,
            "joint_6_pos": joint_state.joint_6 / JOINT_FACTOR,
            "gripper_pos": gripper_state.grippers_angle / GRIPPER_POS_SCALE,
            "joint_1_effort": high_spd.motor_1.effort / 1000.0,
            "joint_2_effort": high_spd.motor_2.effort / 1000.0,
            "joint_3_effort": high_spd.motor_3.effort / 1000.0,
            "joint_4_effort": high_spd.motor_4.effort / 1000.0,
            "joint_5_effort": high_spd.motor_5.effort / 1000.0,
            "joint_6_effort": high_spd.motor_6.effort / 1000.0,
            "gripper_effort": gripper_state.grippers_effort / 1000.0,
        }

    def safe_disconnect(self) -> None:
        """Write the configured zero pose. NOTE: this project intentionally
        avoids sending a disable command on normal exit (see docs/safety.md)."""
        self.write(target_joint=[0.0] * 7)


class PiperMasterBus:
    """Master (leader) bus used for teleoperation during data collection.

    Read-only: connects to the CAN port but never enables motors. Reads the
    master's control frames (operator intent) with the SDK's
    ``GetArmJointCtrl`` / ``GetArmGripperCtrl``.
    """

    def __init__(self, config: PiperMotorsBusConfig):
        from piper_sdk import C_PiperInterface_V2

        self.piper = C_PiperInterface_V2(config.can_name)
        self.piper.ConnectPort()
        self._is_connected = False
        self.motors = config.motors or {
            name: (idx, "agilex_piper") for name, idx in zip(MOTOR_ORDER, MOTOR_IDS, strict=True)
        }

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def motor_names(self) -> list[str]:
        return list(self.motors.keys())

    def connect(self) -> None:
        self._is_connected = True

    def read(self) -> dict:
        joint_ctrl = self.piper.GetArmJointCtrl().joint_ctrl
        gripper_ctrl = self.piper.GetArmGripperCtrl().gripper_ctrl
        return {
            "joint_1_pos": joint_ctrl.joint_1 / JOINT_FACTOR,
            "joint_2_pos": joint_ctrl.joint_2 / JOINT_FACTOR,
            "joint_3_pos": joint_ctrl.joint_3 / JOINT_FACTOR,
            "joint_4_pos": joint_ctrl.joint_4 / JOINT_FACTOR,
            "joint_5_pos": joint_ctrl.joint_5 / JOINT_FACTOR,
            "joint_6_pos": joint_ctrl.joint_6 / JOINT_FACTOR,
            "gripper_pos": gripper_ctrl.grippers_angle / GRIPPER_POS_SCALE,
            "joint_1_effort": 0.0,
            "joint_2_effort": 0.0,
            "joint_3_effort": 0.0,
            "joint_4_effort": 0.0,
            "joint_5_effort": 0.0,
            "joint_6_effort": 0.0,
            "gripper_effort": 0.0,
        }

    def disconnect(self) -> None:
        self._is_connected = False
