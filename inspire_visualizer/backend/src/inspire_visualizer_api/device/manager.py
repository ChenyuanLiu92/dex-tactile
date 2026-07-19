from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic, time
from typing import Literal, Protocol

from inspire_visualizer_api.config import EndpointConfig, HandsConfig
from inspire_visualizer_api.device.mapping import HandSide
from inspire_visualizer_api.device.modbus import InspireModbusClient
from inspire_visualizer_api.device.tactile import TactileProfile, TactileRegion

ConnectionState = Literal["offline", "connecting", "online"]
TactileState = Literal["off", "waiting", "live", "degraded"]


class DeviceUnavailable(RuntimeError):
    pass


class NotArmed(RuntimeError):
    pass


class ControlSessionBusy(RuntimeError):
    pass


class TactileUnavailable(RuntimeError):
    pass


class DeviceClient(Protocol):
    def connect(self) -> bool: ...

    def close(self) -> None: ...

    def read_angles(self) -> tuple[int, ...]: ...

    def read_tactile(self, profile: TactileProfile) -> tuple[TactileRegion, ...]: ...

    def execute_pose(
        self,
        *,
        angles: Sequence[int],
        speeds: Sequence[int],
        forces: Sequence[int],
    ) -> None: ...


@dataclass(frozen=True)
class TactileStatus:
    profile: TactileProfile
    state: TactileState
    target_hz: int
    sample_hz: float
    updated_at: float | None
    error: str | None


@dataclass(frozen=True)
class TactileFrame:
    side: HandSide
    profile: TactileProfile
    sequence: int
    captured_at: float
    regions: tuple[TactileRegion, ...]


@dataclass(frozen=True)
class HandSnapshot:
    side: HandSide
    connection: ConnectionState
    actual_angles: tuple[int, ...] | None
    armed: bool
    updated_at: float | None
    error: str | None
    tactile: TactileStatus


@dataclass
class _HandSession:
    side: HandSide
    endpoint: EndpointConfig
    lock: Lock = field(default_factory=Lock)
    device: DeviceClient | None = None
    connection: ConnectionState = "offline"
    actual_angles: tuple[int, ...] | None = None
    armed_session: str | None = None
    updated_at: float | None = None
    updated_monotonic: float | None = None
    error: str | None = None
    tactile_state: TactileState = "off"
    tactile_sequence: int = 0
    tactile_updated_at: float | None = None
    tactile_error: str | None = None
    tactile_sample_hz: float = 0.0
    tactile_sample_times: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    tactile_frame: TactileFrame | None = None


def _default_device_factory(_side: HandSide, endpoint: EndpointConfig) -> DeviceClient:
    return InspireModbusClient(str(endpoint.host), endpoint.port)


class DeviceManager:
    def __init__(
        self,
        config: HandsConfig,
        *,
        device_factory: Callable[[HandSide, EndpointConfig], DeviceClient] = _default_device_factory,
        stale_after: float = 1.0,
    ) -> None:
        self._device_factory = device_factory
        self._stale_after = stale_after
        self._sessions = self._build_sessions(config)

    def discover(self) -> None:
        for side in ("left", "right"):
            self.discover_side(side)

    def discover_side(self, side: HandSide) -> None:
        session = self._sessions[side]
        with session.lock:
            if not session.endpoint.enabled or session.connection == "online":
                return
            session.connection = "connecting"
            session.error = None
            device = self._device_factory(side, session.endpoint)
            try:
                device.connect()
                angles = device.read_angles()
            except Exception as error:
                device.close()
                session.device = None
                session.connection = "offline"
                session.error = str(error)
                session.armed_session = None
                return
            session.device = device
            session.connection = "online"
            self._update_angles(session, angles)

    def poll(self, side: HandSide) -> tuple[int, ...]:
        session = self._sessions[side]
        with session.lock:
            if session.connection != "online" or session.device is None:
                raise DeviceUnavailable(f"{side} hand is offline")
            try:
                angles = session.device.read_angles()
            except Exception as error:
                self._take_offline(session, error)
                raise DeviceUnavailable(f"{side} hand polling failed") from error
            self._update_angles(session, angles)
            return angles

    def poll_tactile(self, side: HandSide) -> TactileFrame:
        session = self._sessions[side]
        with session.lock:
            profile = session.endpoint.tactile_profile
            if profile == "disabled":
                raise TactileUnavailable(f"{side} hand tactile sensing is disabled")
            if session.connection != "online" or session.device is None:
                raise TactileUnavailable(f"{side} hand is offline")
            try:
                regions = session.device.read_tactile(profile)
            except Exception as error:
                session.tactile_state = "degraded"
                session.tactile_error = str(error)
                raise TactileUnavailable(f"{side} hand tactile polling failed") from error

            captured_at = time()
            sampled_at = monotonic()
            session.tactile_sequence += 1
            session.tactile_sample_times.append(sampled_at)
            if len(session.tactile_sample_times) > 1:
                elapsed = session.tactile_sample_times[-1] - session.tactile_sample_times[0]
                if elapsed > 0:
                    session.tactile_sample_hz = (len(session.tactile_sample_times) - 1) / elapsed
            frame = TactileFrame(
                side=side,
                profile=profile,
                sequence=session.tactile_sequence,
                captured_at=captured_at,
                regions=regions,
            )
            session.tactile_frame = frame
            session.tactile_updated_at = captured_at
            session.tactile_state = "live"
            session.tactile_error = None
            return frame

    def set_armed(self, side: HandSide, session_id: str, armed: bool) -> None:
        session = self._sessions[side]
        with session.lock:
            if armed:
                if session.connection != "online" or self._is_stale(session):
                    raise DeviceUnavailable(f"{side} hand has no fresh device state")
                if (
                    session.armed_session is not None
                    and session.armed_session != session_id
                ):
                    raise ControlSessionBusy(
                        f"{side} hand is armed by another browser session"
                    )
                session.armed_session = session_id
            elif session.armed_session == session_id:
                session.armed_session = None

    def execute_pose(
        self,
        side: HandSide,
        session_id: str,
        *,
        angles: Sequence[int],
        speeds: Sequence[int],
        forces: Sequence[int],
    ) -> tuple[int, ...]:
        session = self._sessions[side]
        with session.lock:
            if session.armed_session != session_id:
                raise NotArmed(f"{side} hand is not armed by this control session")
            if session.connection != "online" or session.device is None or self._is_stale(session):
                session.armed_session = None
                raise DeviceUnavailable(f"{side} hand has no fresh device state")
            try:
                session.device.execute_pose(angles=angles, speeds=speeds, forces=forces)
                actual_angles = session.device.read_angles()
            except Exception as error:
                self._take_offline(session, error)
                raise DeviceUnavailable(f"{side} hand command failed") from error
            self._update_angles(session, actual_angles)
            return actual_angles

    def disarm_session(self, session_id: str) -> None:
        for session in self._sessions.values():
            with session.lock:
                if session.armed_session == session_id:
                    session.armed_session = None

    def disarm_all(self) -> None:
        """Release every browser control session without moving the hand."""
        for session in self._sessions.values():
            with session.lock:
                session.armed_session = None

    def reconfigure(self, config: HandsConfig) -> None:
        self.close()
        self._sessions = self._build_sessions(config)

    def snapshots(self) -> dict[HandSide, HandSnapshot]:
        result: dict[HandSide, HandSnapshot] = {}
        for side, session in self._sessions.items():
            with session.lock:
                if session.armed_session is not None and self._is_stale(session):
                    session.armed_session = None
                result[side] = HandSnapshot(
                    side=side,
                    connection=session.connection,
                    actual_angles=session.actual_angles,
                    armed=session.armed_session is not None,
                    updated_at=session.updated_at,
                    error=session.error,
                    tactile=TactileStatus(
                        profile=session.endpoint.tactile_profile,
                        state=session.tactile_state,
                        target_hz=session.endpoint.tactile_target_hz,
                        sample_hz=session.tactile_sample_hz,
                        updated_at=session.tactile_updated_at,
                        error=session.tactile_error,
                    ),
                )
        return result

    def close(self) -> None:
        for session in self._sessions.values():
            with session.lock:
                if session.device is not None:
                    session.device.close()
                session.device = None
                session.connection = "offline"
                session.armed_session = None
                session.tactile_state = (
                    "off" if session.endpoint.tactile_profile == "disabled" else "waiting"
                )

    def _build_sessions(self, config: HandsConfig) -> dict[HandSide, _HandSession]:
        return {
            "left": _HandSession(
                side="left",
                endpoint=config.left,
                tactile_state="off" if config.left.tactile_profile == "disabled" else "waiting",
            ),
            "right": _HandSession(
                side="right",
                endpoint=config.right,
                tactile_state="off" if config.right.tactile_profile == "disabled" else "waiting",
            ),
        }

    def _is_stale(self, session: _HandSession) -> bool:
        return (
            session.updated_monotonic is None
            or monotonic() - session.updated_monotonic > self._stale_after
        )

    @staticmethod
    def _update_angles(session: _HandSession, angles: Sequence[int]) -> None:
        session.actual_angles = tuple(int(value) for value in angles)
        session.updated_at = time()
        session.updated_monotonic = monotonic()
        session.error = None

    @staticmethod
    def _take_offline(session: _HandSession, error: Exception) -> None:
        if session.device is not None:
            session.device.close()
        session.device = None
        session.connection = "offline"
        session.armed_session = None
        session.error = str(error)
        session.tactile_state = (
            "off" if session.endpoint.tactile_profile == "disabled" else "degraded"
        )
