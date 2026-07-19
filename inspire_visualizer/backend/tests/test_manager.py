from collections.abc import Sequence

import pytest

from inspire_visualizer_api.config import EndpointConfig, HandsConfig
from inspire_visualizer_api.device.manager import (
    ControlSessionBusy,
    DeviceManager,
    DeviceUnavailable,
    NotArmed,
    TactileUnavailable,
)
from inspire_visualizer_api.device.tactile import TactileRegion


class FakeDevice:
    def __init__(self, *, available: bool, angles: Sequence[int] = (1000,) * 6) -> None:
        self.available = available
        self.angles = tuple(angles)
        self.commands: list[tuple[list[int], list[int], list[int]]] = []
        self.closed = False
        self.tactile_available = True

    def connect(self) -> bool:
        if not self.available:
            raise RuntimeError("offline")
        return True

    def close(self) -> None:
        self.closed = True

    def read_angles(self) -> tuple[int, ...]:
        if not self.available:
            raise RuntimeError("offline")
        return self.angles

    def execute_pose(
        self,
        *,
        angles: Sequence[int],
        speeds: Sequence[int],
        forces: Sequence[int],
    ) -> None:
        if not self.available:
            raise RuntimeError("offline")
        self.commands.append((list(angles), list(speeds), list(forces)))
        self.angles = tuple(angles)

    def read_tactile(self, _profile: str) -> tuple[TactileRegion, ...]:
        if not self.tactile_available:
            raise RuntimeError("tactile timeout")
        return (TactileRegion(id="palm", rows=1, columns=2, values=(10, 20)),)


def test_discovery_reports_only_the_available_hand() -> None:
    devices = {
        "left": FakeDevice(available=True),
        "right": FakeDevice(available=False),
    }
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(host="192.0.2.10", port=6000),
        ),
        device_factory=lambda side, _endpoint: devices[side],
    )

    manager.discover()
    snapshots = manager.snapshots()

    assert snapshots["left"].connection == "online"
    assert snapshots["left"].actual_angles == (1000,) * 6
    assert snapshots["right"].connection == "offline"


def test_pose_execution_requires_the_session_that_armed_the_hand() -> None:
    left = FakeDevice(available=True)
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        ),
        device_factory=lambda _side, _endpoint: left,
    )
    manager.discover()
    manager.set_armed("left", "session-a", True)

    with pytest.raises(NotArmed):
        manager.execute_pose(
            "left",
            "session-b",
            angles=[900] * 6,
            speeds=[100] * 6,
            forces=[500] * 6,
        )

    manager.execute_pose(
        "left",
        "session-a",
        angles=[900] * 6,
        speeds=[100] * 6,
        forces=[500] * 6,
    )
    assert left.commands == [([900] * 6, [100] * 6, [500] * 6)]


def test_second_session_cannot_steal_an_armed_hand() -> None:
    left = FakeDevice(available=True)
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        ),
        device_factory=lambda _side, _endpoint: left,
    )
    manager.discover()
    manager.set_armed("left", "session-a", True)

    with pytest.raises(ControlSessionBusy):
        manager.set_armed("left", "session-b", True)

    manager.execute_pose(
        "left",
        "session-a",
        angles=[850] * 6,
        speeds=[100] * 6,
        forces=[500] * 6,
    )
    assert left.commands == [([850] * 6, [100] * 6, [500] * 6)]


def test_disarming_a_websocket_session_locks_its_hand() -> None:
    left = FakeDevice(available=True)
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        ),
        device_factory=lambda _side, _endpoint: left,
    )
    manager.discover()
    manager.set_armed("left", "session-a", True)

    manager.disarm_session("session-a")

    assert manager.snapshots()["left"].armed is False


def test_disarm_all_releases_every_browser_session() -> None:
    devices = {"left": FakeDevice(available=True), "right": FakeDevice(available=True)}
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(host="192.0.2.12", port=6000),
        ),
        device_factory=lambda side, _endpoint: devices[side],
    )
    manager.discover()
    manager.set_armed("left", "session-a", True)
    manager.set_armed("right", "session-b", True)

    manager.disarm_all()

    assert manager.snapshots()["left"].armed is False
    assert manager.snapshots()["right"].armed is False


def test_poll_failure_takes_the_hand_offline_and_clears_arming() -> None:
    left = FakeDevice(available=True)
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        ),
        device_factory=lambda _side, _endpoint: left,
    )
    manager.discover()
    manager.set_armed("left", "session-a", True)
    left.available = False

    with pytest.raises(DeviceUnavailable):
        manager.poll("left")

    snapshot = manager.snapshots()["left"]
    assert snapshot.connection == "offline"
    assert snapshot.armed is False


def test_tactile_failure_does_not_take_motion_control_offline() -> None:
    left = FakeDevice(available=True)
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(
                host="192.0.2.11",
                port=6000,
                tactile_profile="piezoresistive_v1",
            ),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        ),
        device_factory=lambda _side, _endpoint: left,
    )
    manager.discover()
    left.tactile_available = False

    with pytest.raises(TactileUnavailable):
        manager.poll_tactile("left")

    snapshot = manager.snapshots()["left"]
    assert snapshot.connection == "online"
    assert snapshot.tactile.state == "degraded"
    assert snapshot.tactile.error == "tactile timeout"


def test_successful_tactile_poll_publishes_a_sequenced_frame() -> None:
    left = FakeDevice(available=True)
    manager = DeviceManager(
        HandsConfig(
            left=EndpointConfig(
                host="192.0.2.11",
                port=6000,
                tactile_profile="piezoresistive_v1",
            ),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        ),
        device_factory=lambda _side, _endpoint: left,
    )
    manager.discover()

    first = manager.poll_tactile("left")
    second = manager.poll_tactile("left")

    assert first.sequence == 1
    assert second.sequence == 2
    assert second.side == "left"
    assert second.profile == "piezoresistive_v1"
    assert second.regions[0].values == (10, 20)
    assert manager.snapshots()["left"].tactile.state == "live"
