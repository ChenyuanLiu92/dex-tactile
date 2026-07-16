from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from inspire_visualizer_api.app import _tactile_payload, create_app
from inspire_visualizer_api.config import ConfigStore, EndpointConfig, HandsConfig
from inspire_visualizer_api.device.manager import DeviceManager
from inspire_visualizer_api.device.manager import TactileFrame
from inspire_visualizer_api.device.tactile import TactileRegion


class FakeDevice:
    def __init__(self) -> None:
        self.angles = (1000,) * 6

    def connect(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def read_angles(self) -> tuple[int, ...]:
        return self.angles

    def execute_pose(
        self,
        *,
        angles: Sequence[int],
        speeds: Sequence[int],
        forces: Sequence[int],
    ) -> None:
        self.angles = tuple(angles)


def make_app(config_path: Path, *, allow_control: bool = True):
    ConfigStore(config_path).save(
        HandsConfig(
            left=EndpointConfig(host="192.0.2.11", port=6000),
            right=EndpointConfig(enabled=False, host="192.0.2.10", port=6000),
        )
    )
    device = FakeDevice()
    return create_app(
        config_path=config_path,
        tactile_calibration_path=config_path.with_name("tactile_calibration.json"),
        manager_factory=lambda config: DeviceManager(
            config,
            device_factory=lambda _side, _endpoint: device,
        ),
        start_background=False,
        allow_control=allow_control,
    )


def test_config_and_discovery_endpoints_report_the_online_left_hand(tmp_path: Path) -> None:
    app = make_app(tmp_path / "hands.json")

    with TestClient(app) as client:
        config = client.get("/api/config")
        discovery = client.post("/api/discovery/refresh")

    assert config.status_code == 200
    assert config.json()["left"]["host"] == "192.0.2.11"
    assert discovery.status_code == 200
    assert discovery.json()["hands"]["left"]["connection"] == "online"
    assert discovery.json()["hands"]["right"]["connection"] == "offline"


def test_websocket_requires_arming_and_disarms_when_session_closes(tmp_path: Path) -> None:
    app = make_app(tmp_path / "hands.json")

    with TestClient(app) as client:
        client.post("/api/discovery/refresh")
        with client.websocket_connect("/api/ws") as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "snapshot"
            assert snapshot["hands"]["left"]["tactile"] == {
                "profile": "disabled",
                "state": "off",
                "target_hz": 20,
                "sample_hz": 0.0,
                "updated_at": None,
                "error": None,
            }

            websocket.send_json(
                {
                    "type": "execute_pose",
                    "side": "left",
                    "command_id": "before-arm",
                    "angles": [900] * 6,
                    "speeds": [100] * 6,
                    "forces": [500] * 6,
                }
            )
            assert websocket.receive_json()["code"] == "not_armed"

            websocket.send_json({"type": "set_armed", "side": "left", "armed": True})
            armed = websocket.receive_json()
            assert armed == {"type": "armed_state", "side": "left", "armed": True}

            websocket.send_json(
                {
                    "type": "execute_pose",
                    "side": "left",
                    "command_id": "pose-1",
                    "angles": [900] * 6,
                    "speeds": [100] * 6,
                    "forces": [500] * 6,
                }
            )
            result = websocket.receive_json()
            assert result["type"] == "command_result"
            assert result["command_id"] == "pose-1"
            assert result["accepted"] is True
            assert result["actual_angles"] == [900] * 6

        assert app.state.manager.snapshots()["left"].armed is False


def test_unified_read_only_mode_rejects_device_arm(tmp_path: Path) -> None:
    app = make_app(tmp_path / "hands.json", allow_control=False)

    with TestClient(app) as client:
        client.post("/api/discovery/refresh")
        with client.websocket_connect("/api/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "set_armed", "side": "left", "armed": True})

            assert websocket.receive_json() == {
                "type": "error",
                "code": "vision_control_required",
                "message": "Use Vision Control to operate the hand",
            }


def test_duplicate_enabled_endpoints_are_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path / "hands.json")

    with TestClient(app) as client:
        response = client.put(
            "/api/config",
            json={
                "left": {"enabled": True, "host": "192.0.2.10", "port": 6000},
                "right": {"enabled": True, "host": "192.0.2.10", "port": 6000},
            },
        )

    assert response.status_code == 422


def test_tactile_calibration_endpoint_round_trips_for_configured_device(tmp_path: Path) -> None:
    app = make_app(tmp_path / "hands.json")
    with TestClient(app) as client:
        client.put("/api/config", json={"left": {"enabled": True, "host": "192.0.2.11", "port": 6000, "tactile_profile": "piezoresistive_v1"}, "right": {"enabled": False, "host": "192.0.2.10", "port": 6000}})
        assert client.get("/api/tactile-calibration/left").json() is None
        payload = {
            "side": "left",
            "host": "192.0.2.11",
            "port": 6000,
            "profile": "piezoresistive_v1",
            "regions": {},
            "updated_at": "2026-07-15T00:00:00Z",
        }
        saved = client.put("/api/tactile-calibration/left", json=payload)
        loaded = client.get("/api/tactile-calibration/left")
    assert saved.status_code == 200
    assert loaded.json() == {**payload, "version": 1, "model": "RH56DFTP", "drafts": {}}


def test_tactile_frame_payload_preserves_region_shape_and_metrics() -> None:
    frame = TactileFrame(
        side="left",
        profile="piezoresistive_v1",
        sequence=7,
        captured_at=123.5,
        regions=(
            TactileRegion(
                id="palm",
                rows=1,
                columns=2,
                values=(10, 20),
                metrics={"peak": 20},
            ),
        ),
    )

    assert _tactile_payload(frame) == {
        "type": "tactile_frame",
        "side": "left",
        "profile": "piezoresistive_v1",
        "sequence": 7,
        "captured_at": 123.5,
        "regions": [
            {
                "id": "palm",
                "rows": 1,
                "columns": 2,
                "values": (10, 20),
                "metrics": {"peak": 20},
            }
        ],
    }
