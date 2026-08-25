"""Dual Piper robot wrapper.

Faithful re-implementation of the in-house ``piper_dual`` robot used for the
towel-folding setup. It composes two :class:`PiperMotorsBus` (one per CAN
bus) with three RGB cameras and exposes the exact observation/action
contract the ACT policy expects:

* ``observation.state`` — 28 dims
  ``[left 7 motors x (pos, effort)] + [right 7 motors x (pos, effort)]``
* ``action`` — 14 dims
  ``[left j1..j6, left gripper, right j1..j6, right gripper]`` (position control)

Two deliberate safety choices (see docs/safety.md):
* Connecting never commands the all-zero calibration pose. After
  ``connect()`` the arms hold whatever pose they were in; move them to the
  demonstrated start pose explicitly with ``reset_pose.py``.
* On exit this wrapper does not send a disable command, so the arms remain
  ENABLED and hold the last commanded pose instead of dropping under gravity.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from piper_towel_folding.piper.motors import MOTOR_ORDER, PiperMotorsBus, PiperMotorsBusConfig

POSITION_KEYS = [f"{motor}_pos" for motor in MOTOR_ORDER]
STATE_KEYS = [f"{arm}_{motor}.{field}" for arm in ("left", "right") for motor in MOTOR_ORDER for field in ("pos", "effort")]


@dataclass
class OpenCVCameraConfig:
    index_or_path: int | str
    width: int = 640
    height: int = 480
    fps: int = 30


class OpenCVCamera:
    """Minimal OpenCV camera with a background read thread.

    Mirrors the behavior of the LeRobot OpenCV camera used in production:
    a daemon thread continuously reads frames so that ``async_read()`` never
    blocks on the hardware. Raises after 10 consecutive read failures.
    """

    def __init__(self, config: OpenCVCameraConfig):
        self.config = config
        self._capture = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._latest_timestamp: float | None = None
        self._new_frame_event = threading.Event()

    def connect(self, warmup_s: float = 1.0) -> None:
        import cv2

        self._capture = cv2.VideoCapture(self.config.index_or_path)
        if not self._capture.isOpened():
            raise RuntimeError(f"Failed to open camera {self.config.index_or_path}")
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._capture.set(cv2.CAP_PROP_FPS, float(self.config.fps))

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, name="camera_read", daemon=True)
        self._thread.start()

        # Warm up so the first policy inference never sees a stale frame.
        deadline = time.time() + warmup_s
        while time.time() < deadline:
            if self._latest_frame is not None:
                return
            time.sleep(0.05)
        raise RuntimeError(f"Camera {self.config.index_or_path} produced no frame during warmup")

    def _read_loop(self) -> None:
        import cv2

        failures = 0
        while not self._stop_event.is_set():
            try:
                ok, frame = self._capture.read()
                if not ok:
                    raise RuntimeError("read returned False")
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                with self._frame_lock:
                    self._latest_frame = frame
                    self._latest_timestamp = time.time()
                self._new_frame_event.set()
                failures = 0
            except Exception as exc:  # noqa: BLE001
                failures += 1
                if failures > 10:
                    raise RuntimeError(
                        f"Camera {self.config.index_or_path} exceeded consecutive read failures"
                    ) from exc

    def async_read(self, timeout_ms: float = 200) -> np.ndarray:
        if not self._new_frame_event.wait(timeout_ms / 1000.0):
            raise TimeoutError(f"Timed out waiting for frame from {self.config.index_or_path}")
        with self._frame_lock:
            frame = self._latest_frame
            self._new_frame_event.clear()
        if frame is None:
            raise RuntimeError(f"No frame available for {self.config.index_or_path}")
        return frame

    @property
    def is_connected(self) -> bool:
        return self._capture is not None and self._thread is not None and self._thread.is_alive()

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._capture is not None:
            self._capture.release()
        self._thread = None
        self._capture = None


@dataclass
class PIPERDualConfig:
    left_port: str = "can1"
    right_port: str = "can0"
    read_only: bool = False
    cameras: dict[str, OpenCVCameraConfig] = field(default_factory=dict)


class PIPERDual:
    """Two Piper arms (follower buses) plus three RGB cameras."""

    name = "piper_dual"

    def __init__(self, config: PIPERDualConfig):
        self.config = config
        self.left_bus = PiperMotorsBus(PiperMotorsBusConfig(can_name=config.left_port))
        self.right_bus = PiperMotorsBus(PiperMotorsBusConfig(can_name=config.right_port))
        self.cameras: dict[str, OpenCVCamera] = {
            name: OpenCVCamera(cam_config) for name, cam_config in config.cameras.items()
        }
        self._is_connected = False

    # ------------------------------------------------------------------
    # Feature contract.
    # ------------------------------------------------------------------
    @property
    def action_features(self) -> dict[str, type]:
        return {f"{arm}_{motor}.pos": float for arm in ("left", "right") for motor in MOTOR_ORDER}

    @property
    def observation_features(self) -> dict[str, type | tuple]:
        features: dict[str, type | tuple] = {
            key: float for key in STATE_KEYS
        }
        for name, cam in self.cameras.items():
            features[f"observation.images.{name}"] = (cam.config.height, cam.config.width, 3)
        return features

    @property
    def is_connected(self) -> bool:
        return (
            self._is_connected
            and self.left_bus.is_connected
            and self.right_bus.is_connected
            and all(cam.is_connected for cam in self.cameras.values())
        )

    # ------------------------------------------------------------------
    # Connection.
    # ------------------------------------------------------------------
    def connect(self) -> None:
        if self._is_connected:
            raise RuntimeError("PIPERDual is already connected; do not call connect() twice.")

        if not self.config.read_only:
            if not self.left_bus.connect(enable=True):
                raise RuntimeError("Failed to enable left Piper arm.")
            if not self.right_bus.connect(enable=True):
                raise RuntimeError("Failed to enable right Piper arm.")
            print("Both arms enabled WITHOUT sending the zero calibration pose.")
        else:
            print("DRY-RUN: CAN connected for state reading; arms were not enabled.")

        for name, cam in self.cameras.items():
            cam.connect()
            print(f"camera {name} connected")

        self._is_connected = True

    def disconnect(self) -> None:
        for cam in self.cameras.values():
            cam.disconnect()
        self._is_connected = False
        # Deliberately no disable command: the arms stay ENABLED and hold
        # their last commanded pose (see docs/safety.md).

    # ------------------------------------------------------------------
    # Observation / action.
    # ------------------------------------------------------------------
    def get_observation(self) -> dict:
        if not self._is_connected:
            raise RuntimeError("PIPERDual is not connected. Run connect() first.")

        obs: dict = {}
        for arm, bus in (("left", self.left_bus), ("right", self.right_bus)):
            state = bus.read()
            for motor in MOTOR_ORDER:
                obs[f"{arm}_{motor}.pos"] = float(state[f"{motor}_pos"])
                obs[f"{arm}_{motor}.effort"] = float(state[f"{motor}_effort"])
        for name, cam in self.cameras.items():
            obs[name] = cam.async_read()
        return obs

    def send_action(self, action: dict[str, float] | np.ndarray) -> dict | np.ndarray:
        """Accept a 14-dim position action (array or keyed dict) and write it."""
        if isinstance(action, np.ndarray):
            if action.shape != (14,):
                raise ValueError(f"Expected action shape (14,), got {action.shape}")
            left = action[:7].tolist()
            right = action[7:].tolist()
        else:
            left = [float(action[f"left_{motor}.pos"]) for motor in MOTOR_ORDER]
            right = [float(action[f"right_{motor}.pos"]) for motor in MOTOR_ORDER]

        if not self.config.read_only:
            self.left_bus.write(left)
            self.right_bus.write(right)
        return action
