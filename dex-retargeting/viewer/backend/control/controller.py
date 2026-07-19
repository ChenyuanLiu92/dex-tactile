from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from viewer.backend.state import TrackingSnapshot, TrackingStatus

from .driver import RH56Driver
from .motion import AdaptiveMotion


class Preset(StrEnum):
    HOME = "HOME"
    OPEN = "OPEN"


PRESET_POSES = {
    Preset.HOME: (120, 120, 120, 120, 180, 480),
    Preset.OPEN: (1000, 1000, 1000, 1000, 1000, 1000),
}
POSITIONING_TIMEOUT_SECONDS = 20.0
PRESET_REACHED_TOLERANCE = 15
PRESET_STEPS = (15, 40, 80)
PRESET_SPEEDS = (80, 180, 300)
VISION_CHANNEL_STEP_SCALES = (1, 1, 1, 1, 1.5, 2.0)
VISION_CHANNEL_SPEED_SCALES = (1, 1, 1, 1, 1.5, 2.0)


class ControlState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    DISARMED = "DISARMED"
    ARMING = "ARMING"
    ARMED = "ARMED"
    POSITIONING = "POSITIONING"
    HOLDING = "HOLDING"
    ESTOPPED = "ESTOPPED"
    FAULT = "FAULT"


class TransitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlSnapshot:
    state: ControlState = ControlState.DISCONNECTED
    connected: bool = False
    host: str = "192.0.2.10"
    port: int = 6000
    actual: list[int] | None = None
    targets: list[int] | None = None
    commanded: list[int] | None = None
    speeds: list[int] | None = None
    last_write_at: float | None = None
    error: str | None = None
    preset: Preset | None = None
    tracking_hold: bool = False
    tracking_loss_ms: float | None = None

    def to_payload(self) -> dict:
        return {
            "state": self.state.value,
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "actual": self.actual,
            "targets": self.targets,
            "commanded": self.commanded,
            "speeds": self.speeds,
            "last_write_at": self.last_write_at,
            "error": self.error,
            "preset": self.preset.value if self.preset is not None else None,
            "tracking_hold": self.tracking_hold,
            "tracking_loss_ms": self.tracking_loss_ms,
            "modbus_output": self.state in {
                ControlState.ARMED,
                ControlState.POSITIONING,
            },
            "software_hold_only": True,
        }


class VisionHandController:
    def __init__(
        self,
        driver: RH56Driver | None = None,
        motion: AdaptiveMotion | None = None,
        preset_motion: AdaptiveMotion | None = None,
        control_frequency: int = 30,
        stale_after: float = 0.15,
        clock: Callable[[], float] = time.time,
        start_worker: bool = True,
    ):
        self.driver = driver or RH56Driver()
        self.motion = motion or AdaptiveMotion(
            channel_step_scales=VISION_CHANNEL_STEP_SCALES,
            channel_speed_scales=VISION_CHANNEL_SPEED_SCALES,
        )
        self.preset_motion = preset_motion or AdaptiveMotion(
            steps=PRESET_STEPS,
            speeds=PRESET_SPEEDS,
        )
        self.period = 1 / control_frequency
        self.stale_after = stale_after
        self.clock = clock
        self.start_worker = start_worker
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._tracking = TrackingSnapshot()
        self._snapshot = ControlSnapshot(host=self.driver.host, port=self.driver.port)
        self._positioning_started_at: float | None = None
        self._tracking_loss_started_at: float | None = None

    def snapshot(self) -> ControlSnapshot:
        with self._lock:
            return self._snapshot

    def start(self) -> None:
        with self._lock:
            if self._snapshot.state is not ControlState.DISCONNECTED:
                return
            self._connect_read_only()
        self._start_control_thread()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._lock:
            if self._snapshot.state in {
                ControlState.ARMED,
                ControlState.POSITIONING,
            }:
                self._hold(ControlState.DISARMED)
            self.driver.close()
            self._replace(state=ControlState.DISCONNECTED, connected=False)

    def update_tracking(self, snapshot: TrackingSnapshot) -> None:
        with self._lock:
            self._tracking = snapshot

    def arm(self, now: float | None = None) -> ControlSnapshot:
        with self._lock:
            self._require(ControlState.DISARMED)
            current_time = self.clock() if now is None else now
            if not self._fresh_tracking(current_time):
                raise TransitionError("Fresh right-hand tracking is required to ARM")
            self._replace(state=ControlState.ARMING, error=None)
            try:
                actual = self.driver.read_positions()
            except Exception as error:
                self._fault(error)
                raise TransitionError(str(error)) from error
            self.motion.reset()
            self._tracking_loss_started_at = None
            values = actual.tolist()
            self._replace(
                state=ControlState.ARMED,
                connected=True,
                actual=values,
                targets=list(self._tracking.actuators or []),
                commanded=values,
                speeds=None,
                error=None,
                tracking_hold=False,
                tracking_loss_ms=None,
            )
            return self._snapshot

    def disarm(self) -> ControlSnapshot:
        with self._lock:
            self._require(ControlState.ARMED)
            self._hold(ControlState.DISARMED)
            return self._snapshot

    def home(self, now: float | None = None) -> ControlSnapshot:
        return self.move_to_preset(Preset.HOME, now=now)

    def open(self, now: float | None = None) -> ControlSnapshot:
        return self.move_to_preset(Preset.OPEN, now=now)

    def move_to_preset(
        self, preset: Preset, now: float | None = None
    ) -> ControlSnapshot:
        with self._lock:
            self._require(ControlState.DISARMED)
            current_time = self.clock() if now is None else now
            try:
                actual = self.driver.read_positions()
            except Exception as error:
                self._fault(error)
                raise TransitionError(str(error)) from error
            self.preset_motion.reset()
            values = actual.tolist()
            target = PRESET_POSES[preset]
            self._positioning_started_at = current_time
            self._replace(
                state=ControlState.POSITIONING,
                connected=True,
                actual=values,
                targets=list(target),
                commanded=values,
                speeds=None,
                error=None,
                preset=preset,
            )
            return self._snapshot

    def estop(self) -> ControlSnapshot:
        with self._lock:
            if self._snapshot.state in {
                ControlState.DISCONNECTED,
                ControlState.ESTOPPED,
            }:
                if self._snapshot.state is ControlState.ESTOPPED:
                    return self._snapshot
                raise TransitionError("E-STOP requires a connected hand")
            self._hold(ControlState.ESTOPPED, latch_on_error=True)
            return self._snapshot

    def reset(self) -> ControlSnapshot:
        with self._lock:
            self._require(ControlState.ESTOPPED)
            try:
                actual = self.driver.read_positions().tolist()
            except Exception as error:
                self._fault(error)
                raise TransitionError(str(error)) from error
            self._replace(
                state=ControlState.DISARMED,
                connected=True,
                actual=actual,
                commanded=actual,
                speeds=None,
                error=None,
            )
            return self._snapshot

    def reconnect(self) -> ControlSnapshot:
        with self._lock:
            if self._snapshot.state not in {
                ControlState.DISCONNECTED,
                ControlState.FAULT,
            }:
                raise TransitionError(
                    "Reconnect is only allowed after disconnect or fault"
                )
            self.driver.close()
            self._connect_read_only()
            snapshot = self._snapshot
        self._start_control_thread()
        return snapshot

    def tick(self, now: float | None = None) -> ControlSnapshot:
        with self._lock:
            if self._snapshot.state is ControlState.POSITIONING:
                current_time = self.clock() if now is None else now
                return self._tick_positioning(current_time)
            if self._snapshot.state is not ControlState.ARMED:
                return self._snapshot
            current_time = self.clock() if now is None else now
            if not self._fresh_tracking(current_time):
                if self._recoverable_tracking_loss(current_time):
                    self._tick_tracking_loss(current_time)
                else:
                    self._hold(ControlState.DISARMED)
                return self._snapshot
            if self._tracking_loss_started_at is not None:
                self._tracking_loss_started_at = None
                self.motion.reset()
                self._replace(tracking_hold=False, tracking_loss_ms=None)
            try:
                actual = self.driver.read_positions()
                reference = self._snapshot.commanded or actual.tolist()
                command = self.motion.command(
                    self._tracking.actuators or [], reference, feedback=actual
                )
                self.driver.write_motion(command.positions, command.speeds)
            except Exception as error:
                self._fault(error)
                return self._snapshot
            self._replace(
                actual=actual.tolist(),
                targets=command.targets.tolist(),
                commanded=command.positions.tolist(),
                speeds=command.speeds.tolist(),
                last_write_at=current_time,
                error=None,
                tracking_hold=False,
                tracking_loss_ms=None,
            )
            return self._snapshot

    def _tick_positioning(self, current_time: float) -> ControlSnapshot:
        preset = self._snapshot.preset
        if preset is None:
            self._fault(RuntimeError("Positioning preset is missing"))
            return self._snapshot
        target_positions = PRESET_POSES[preset]
        if (
            self._positioning_started_at is not None
            and current_time - self._positioning_started_at
            > POSITIONING_TIMEOUT_SECONDS
        ):
            self._hold(ControlState.FAULT)
            self._replace(
                error=f"{preset.value} positioning timed out after 20 seconds",
                speeds=None,
            )
            return self._snapshot
        try:
            actual = self.driver.read_positions()
            if all(
                abs(int(current) - target) <= PRESET_REACHED_TOLERANCE
                for current, target in zip(actual, target_positions)
            ):
                self._hold(ControlState.DISARMED)
                return self._snapshot
            command = self.preset_motion.command(target_positions, actual)
            self.driver.write_motion(command.positions, command.speeds)
        except Exception as error:
            self._fault(error)
            return self._snapshot
        self._replace(
            actual=actual.tolist(),
            targets=command.targets.tolist(),
            commanded=command.positions.tolist(),
            speeds=command.speeds.tolist(),
            last_write_at=current_time,
            error=None,
        )
        return self._snapshot

    def _fresh_tracking(self, now: float) -> bool:
        return (
            self._tracking.status is TrackingStatus.TRACKING
            and self._tracking.actuators is not None
            and len(self._tracking.actuators) == 6
            and 0 <= now - self._tracking.published_at <= self.stale_after
        )

    def _recoverable_tracking_loss(self, now: float) -> bool:
        if self._tracking.status is not TrackingStatus.TRACKING:
            return True
        return (
            self._tracking.actuators is not None
            and len(self._tracking.actuators) == 6
            and now - self._tracking.published_at > self.stale_after
        )

    def _tick_tracking_loss(self, current_time: float) -> None:
        if self._tracking_loss_started_at is None:
            self._tracking_loss_started_at = current_time
            try:
                actual = self.driver.hold_current().tolist()
            except Exception as error:
                self._fault(error)
                return
            self._replace(
                actual=actual,
                commanded=actual,
                speeds=None,
                last_write_at=current_time,
                error=None,
                tracking_hold=True,
                tracking_loss_ms=0.0,
            )
            return

        elapsed = current_time - self._tracking_loss_started_at
        self._replace(
            tracking_hold=True,
            tracking_loss_ms=max(0.0, elapsed * 1000),
        )

    def _connect_read_only(self) -> None:
        try:
            self.driver.connect()
            actual = self.driver.read_positions().tolist()
        except Exception as error:
            self.driver.close()
            self._replace(
                state=ControlState.DISCONNECTED,
                connected=False,
                error=str(error),
            )
            return
        self._replace(
            state=ControlState.DISARMED,
            connected=True,
            actual=actual,
            commanded=actual,
            speeds=None,
            error=None,
            tracking_hold=False,
            tracking_loss_ms=None,
        )

    def _hold(self, final_state: ControlState, latch_on_error: bool = False) -> None:
        self._replace(state=ControlState.HOLDING)
        try:
            actual = self.driver.hold_current().tolist()
        except Exception as error:
            if latch_on_error:
                self._replace(state=final_state, error=str(error), speeds=None)
            else:
                self._fault(error)
            return
        self._positioning_started_at = None
        self._tracking_loss_started_at = None
        self._replace(
            state=final_state,
            actual=actual,
            commanded=actual,
            speeds=None,
            last_write_at=self.clock(),
            error=None,
            preset=None,
            tracking_hold=False,
            tracking_loss_ms=None,
        )

    def _fault(self, error: Exception) -> None:
        self._positioning_started_at = None
        self._tracking_loss_started_at = None
        self._replace(
            state=ControlState.FAULT,
            error=str(error),
            speeds=None,
            preset=None,
            tracking_hold=False,
            tracking_loss_ms=None,
        )

    def _require(self, state: ControlState) -> None:
        if self._snapshot.state is not state:
            raise TransitionError(
                f"Expected {state.value}, current state is {self._snapshot.state.value}"
            )

    def _replace(self, **changes) -> None:
        values = self._snapshot.__dict__ | changes
        self._snapshot = ControlSnapshot(**values)

    def _control_loop(self) -> None:
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            self.tick()
            next_tick += self.period
            self._stop_event.wait(max(0.0, next_tick - time.monotonic()))

    def _start_control_thread(self) -> None:
        if (
            not self.start_worker
            or self._snapshot.state is not ControlState.DISARMED
            or (self._thread is not None and self._thread.is_alive())
        ):
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._control_loop, name="rh56-control", daemon=True
        )
        self._thread.start()
