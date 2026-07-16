from dataclasses import dataclass
import asyncio

from fastapi.testclient import TestClient

from viewer.backend.app import create_app
from viewer.backend.control.controller import (
    ControlSnapshot,
    ControlState,
    Preset,
    TransitionError,
)
from viewer.backend.state import TrackingSnapshot, TrackingStatus


@dataclass
class Packet:
    sequence: int = 1
    jpeg: bytes = b"jpeg-data"


class FrameStore:
    def latest(self):
        return Packet()

    def wait_for_new(self, _sequence, timeout=1.0):
        return Packet()


class FakeRuntime:
    def __init__(self):
        self.frame_store = FrameStore()
        self.controller = FakeController()
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def snapshot(self):
        return TrackingSnapshot(
            status=TrackingStatus.TRACKING,
            sequence=4,
            handedness="Right",
            confidence=0.95,
            landmarks_2d=[[0.1, 0.2]] * 21,
            landmarks_3d=[[0.0, 0.0, 0.0]] * 21,
            joints={"index_proximal_joint": 0.2},
            actuators=[1, 2, 3, 4, 5, 6],
            contact={
                "state": "LOCKED",
                "finger": "index",
                "human_distance_mm": 20.0,
                "projected_distance_mm": 5.0,
            },
        )

    def calibration_status(self):
        return {
            "state": "UNCALIBRATED",
            "samples": 0,
            "required_samples": 30,
            "neutral_flexion_deg": [0.0] * 4,
        }

    def start_open_calibration(self):
        return {
            "state": "COLLECTING",
            "samples": 0,
            "required_samples": 30,
            "neutral_flexion_deg": [0.0] * 4,
        }


class FakeController:
    def __init__(self):
        self.value = ControlSnapshot(
            state=ControlState.DISARMED,
            connected=True,
            actual=[900] * 6,
            commanded=[900] * 6,
        )

    def snapshot(self):
        return self.value

    def _set(self, state, preset=None):
        if (
            state is ControlState.ARMED
            and self.value.state is not ControlState.DISARMED
        ):
            raise TransitionError("invalid transition")
        target = None
        if preset is Preset.HOME:
            target = [120, 120, 120, 120, 180, 480]
        elif preset is Preset.OPEN:
            target = [1000] * 6
        self.value = ControlSnapshot(
            state=state,
            connected=True,
            preset=preset,
            targets=target,
        )
        return self.value

    def arm(self):
        return self._set(ControlState.ARMED)

    def home(self):
        return self._set(ControlState.POSITIONING, Preset.HOME)

    def open(self):
        return self._set(ControlState.POSITIONING, Preset.OPEN)

    def disarm(self):
        return self._set(ControlState.DISARMED)

    def estop(self):
        return self._set(ControlState.ESTOPPED)

    def reset(self):
        return self._set(ControlState.DISARMED)

    def reconnect(self):
        return self._set(ControlState.DISARMED)


def test_health_and_runtime_lifespan():
    runtime = FakeRuntime()
    with TestClient(create_app(runtime=runtime)) as client:
        response = client.get("/api/health")
        assert response.json() == {
            "status": "ok",
            "camera_index": 0,
            "modbus_output": False,
            "control_state": "DISARMED",
            "connected": True,
        }
        assert runtime.started
    assert runtime.stopped


def test_websocket_sends_tracking_snapshot():
    with TestClient(create_app(runtime=FakeRuntime())) as client:
        with client.websocket_connect("/api/ws") as websocket:
            payload = websocket.receive_json()
    assert payload["status"] == "TRACKING"
    assert payload["handedness"] == "Right"
    assert payload["actuators"] == [1, 2, 3, 4, 5, 6]
    assert payload["contact"]["finger"] == "index"
    assert payload["modbus_output"] is False
    assert payload["control"]["state"] == "DISARMED"


def test_guarded_control_transitions_have_no_command_body():
    runtime = FakeRuntime()
    with TestClient(create_app(runtime=runtime)) as client:
        headers = {"X-RH56-Control": "operator-confirmed"}
        rejected = client.post("/api/control/arm")
        armed = client.post("/api/control/arm", headers=headers)
        conflict = client.post("/api/control/arm", headers=headers)
        stopped = client.post("/api/control/estop", headers=headers)
        reset = client.post("/api/control/reset", headers=headers)
        routes = {route.path for route in client.app.routes}

    assert rejected.status_code == 403
    assert armed.json()["state"] == "ARMED"
    assert conflict.status_code == 409
    assert stopped.json()["state"] == "ESTOPPED"
    assert reset.json()["state"] == "DISARMED"
    assert "/api/control/write" not in routes
    assert "/api/control/target" not in routes
    assert "/api/control/preset" not in routes


def test_preset_routes_require_control_header_and_use_fixed_targets():
    with TestClient(create_app(runtime=FakeRuntime())) as client:
        rejected = client.post("/api/control/home")
        home = client.post(
            "/api/control/home",
            headers={"X-RH56-Control": "operator-confirmed"},
        )
    with TestClient(create_app(runtime=FakeRuntime())) as client:
        opened = client.post(
            "/api/control/open",
            headers={"X-RH56-Control": "operator-confirmed"},
        )

    assert rejected.status_code == 403
    assert home.status_code == 200
    assert home.json()["state"] == "POSITIONING"
    assert home.json()["preset"] == "HOME"
    assert home.json()["targets"] == [120, 120, 120, 120, 180, 480]
    assert home.json()["modbus_output"] is True
    assert opened.status_code == 200
    assert opened.json()["preset"] == "OPEN"
    assert opened.json()["targets"] == [1000] * 6


def test_open_calibration_route_is_guarded_and_starts_collection():
    with TestClient(create_app(runtime=FakeRuntime())) as client:
        rejected = client.post("/api/retargeting/calibration/open")
        started = client.post(
            "/api/retargeting/calibration/open",
            headers={"X-RH56-Control": "operator-confirmed"},
        )
        status = client.get("/api/retargeting/calibration")

    assert rejected.status_code == 403
    assert started.status_code == 200
    assert started.json()["state"] == "COLLECTING"
    assert status.json()["state"] == "UNCALIBRATED"


def test_mjpeg_frame_uses_multipart_boundary():
    app = create_app(runtime=FakeRuntime())
    route = next(route for route in app.routes if route.path == "/api/video.mjpg")
    response = route.endpoint()
    first_chunk = asyncio.run(response.body_iterator.__anext__())
    assert response.media_type == "multipart/x-mixed-replace; boundary=frame"
    assert first_chunk == (b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg-data\r\n")


def test_inspire_urdf_is_served():
    with TestClient(create_app(runtime=FakeRuntime())) as client:
        response = client.get("/assets/inspire_hand_right.urdf")
    assert response.status_code == 200
    assert "<robot" in response.text


def test_built_frontend_and_web_assets_are_served():
    with TestClient(create_app(runtime=FakeRuntime())) as client:
        index = client.get("/")
        asset_path = index.text.split('src="')[1].split('"')[0]
        asset = client.get(asset_path)
    assert "D435 Vision Workbench" in index.text
    assert asset.headers["content-type"].startswith("text/javascript")
