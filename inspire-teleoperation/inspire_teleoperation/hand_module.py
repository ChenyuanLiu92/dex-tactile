"""Adapter exposing the existing dexterous-hand controller as a module."""

from __future__ import annotations

from multiprocessing import Array, Lock, Value
from typing import Any, Callable

from .api import ModuleStatus, TeleopFrame


def _read_shared(values: Any) -> tuple[float, ...]:
    lock = getattr(values, "get_lock", lambda: None)()
    if lock is None:
        return tuple(values[:])
    with lock:
        return tuple(values[:])


class HandTeleopModule:
    """Lifecycle and frame adapter for one or two Inspire hands."""

    name = "hands"

    def __init__(
        self,
        *,
        left_host: str | None,
        right_host: str | None,
        open_on_exit: bool = False,
        controller_factory: Callable[..., Any] | None = None,
        **controller_options: Any,
    ) -> None:
        if not left_host and not right_host:
            raise ValueError("at least one hand host must be configured")
        self.left_enabled = bool(left_host)
        self.right_enabled = bool(right_host)
        self.open_on_exit = open_on_exit
        self._controller_factory = controller_factory
        self._options = {
            "left_host": left_host,
            "right_host": right_host,
            **controller_options,
        }
        self._left_landmarks = Array("d", 75, lock=True)
        self._right_landmarks = Array("d", 75, lock=True)
        self._data_lock = Lock()
        self._state = Array("d", 12, lock=False)
        self._action = Array("d", 12, lock=False)
        self._ready = Value("b", False, lock=True)
        self._sequence = Value("L", 0, lock=True)
        self._frame_accepted = False
        self.controller: Any | None = None

    def start(self) -> None:
        if self.controller is not None:
            return
        factory = self._controller_factory
        if factory is None:
            from .hand_controller import HandController

            factory = HandController
        self.controller = factory(
            self._left_landmarks,
            self._right_landmarks,
            self._data_lock,
            self._state,
            self._action,
            xr_motion_data_ready_in=self._ready,
            xr_motion_data_sequence_in=self._sequence,
            **self._options,
        )

    @staticmethod
    def _copy(shared: Any, landmarks: Any) -> None:
        with shared.get_lock():
            shared[:] = landmarks.ravel()

    def update(self, frame: TeleopFrame, *, enabled: bool) -> None:
        if self.controller is None:
            raise RuntimeError("hand module has not been started")
        self.controller.raise_if_failed()
        valid = enabled and frame.motion_data_ready
        with self._ready.get_lock():
            self._ready.value = False
        if valid:
            with self._data_lock:
                if self.left_enabled:
                    if frame.left_hand is None:
                        valid = False
                    else:
                        self._copy(self._left_landmarks, frame.left_hand.landmarks)
                if self.right_enabled:
                    if frame.right_hand is None:
                        valid = False
                    else:
                        self._copy(self._right_landmarks, frame.right_hand.landmarks)
            if valid:
                with self._sequence.get_lock():
                    self._sequence.value += 1
        with self._ready.get_lock():
            self._ready.value = valid
        self._frame_accepted = valid

    def toggle_speed_mode(self) -> str:
        if self.controller is None:
            raise RuntimeError("hand module has not been started")
        return self.controller.toggle_speed_mode()

    def toggle_motion_filter(self) -> bool:
        if self.controller is None:
            raise RuntimeError("hand module has not been started")
        return self.controller.toggle_motion_filter()

    def calibrate_force_sensors(self) -> tuple[str, ...]:
        """Calibrate force sensors on all connected hands."""

        if self.controller is None:
            raise RuntimeError("hand module has not been started")
        return self.controller.calibrate_force_sensors()

    def set_tactile_sides(self, sides: tuple[str, ...]) -> None:
        if self.controller is None:
            raise RuntimeError("hand module has not been started")
        self.controller.set_tactile_sides(sides)

    def status(self) -> ModuleStatus:
        if self.controller is None:
            return ModuleStatus(name=self.name, ready=False, detail="not started")
        action = _read_shared(self._action)
        tactile_snapshot = getattr(self.controller, "tactile_snapshot", None)
        return ModuleStatus(
            name=self.name,
            ready=True,
            telemetry={
                "left_enabled": self.left_enabled,
                "right_enabled": self.right_enabled,
                "motion_data_ready": self._frame_accepted,
                "left_state": _read_shared(self.controller.left_hand_state_array),
                "right_state": _read_shared(self.controller.right_hand_state_array),
                "left_target": action[:6],
                "right_target": action[6:],
                "speed_mode": self.controller.speed_mode,
                "motion_filter_enabled": bool(
                    getattr(self.controller, "motion_filter_enabled", False)
                ),
                "left_speed": _read_shared(self.controller.left_hand_speed_array),
                "right_speed": _read_shared(self.controller.right_hand_speed_array),
                "tactile": (
                    tactile_snapshot()
                    if tactile_snapshot is not None
                    else {
                        "sample_hz": 0.0,
                        "target_hz": 0.0,
                        "selection": [],
                        "hands": {},
                    }
                ),
            },
        )

    def close(self) -> None:
        with self._ready.get_lock():
            self._ready.value = False
        self._frame_accepted = False
        if self.controller is not None:
            self.controller.stop(open_hand=self.open_on_exit)
            self.controller = None
