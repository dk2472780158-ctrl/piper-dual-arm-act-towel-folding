#!/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig
from lerobot.cameras.realsense import RealSenseCameraConfig

from ..config import RobotConfig


@RobotConfig.register_subclass("piper_dual")
@dataclass
class PIPERDualConfig(RobotConfig):
    """Dual-Piper robot configuration.

    CAN ports follow the physical wiring of the reference rig:
    the RIGHT arm is on ``can0``, the LEFT arm on ``can1``.
    """

    left_port: str = "can_left"
    right_port: str = "can_right"
    read_only: bool = False

    # Camera defaults are for the recording path (LeRobot RealSense
    # backend). Serial numbers are machine-specific and must be filled in
    # for YOUR rig — none are published in this repo. The deployment path
    # (scripts/run_act.sh) overrides cameras entirely with the OpenCV
    # backend via `--robot.cameras`, addressed by stable udev symlinks
    # (/dev/camera_{left,middle,right}), so no serial is needed there.
    cameras: dict[str, CameraConfig] = field(
        default_factory=lambda: {
            "left": RealSenseCameraConfig(
                serial_number_or_name="<REALSENSE_SERIAL_LEFT>",
                fps=30,
                width=640,
                height=480,
                use_depth=False,
                warmup_s=1,
            ),
            "right": RealSenseCameraConfig(
                serial_number_or_name="<REALSENSE_SERIAL_RIGHT>",
                fps=30,
                width=640,
                height=480,
                use_depth=False,
                warmup_s=1,
            ),
            "middle": RealSenseCameraConfig(
                serial_number_or_name="<REALSENSE_SERIAL_MIDDLE>",
                fps=30,
                width=640,
                height=480,
                use_depth=False,
                warmup_s=1,
            ),
        }
    )
