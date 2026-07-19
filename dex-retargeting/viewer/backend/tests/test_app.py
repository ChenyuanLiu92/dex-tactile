from dataclasses import dataclass
import asyncio

from fastapi.testclient import TestClient

from viewer.backend.app import create_app
import viewer.backend.app as app_module
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
        self.camera = FakeCamera()
        self.started = False
        self.stopped = False
        self.active_profile_id = "default"
        self.profiles = [
            {
                "id": "default",
                "name": "Default",
                "calibration_state": "DEFAULT",
                "active": True,
                "updated_at": None,
            }
        ]
        self.profile_calibration = None

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

    def list_operator_profiles(self):
        return {"active_profile_id": self.active_profile_id, "profiles": self.profiles}

    def operator_profile_status(self):
        return next(item for item in self.profiles if item["id"] == self.active_profile_id)

    def profile_calibration_status(self):
        return self.profile_calibration

    def create_operator_profile(self, name):
        profile = {
            "id": "profile-1",
            "name": name,
            "calibration_state": "UNCALIBRATED",
            "active": False,
            "updated_at": "now",
        }
        self.profiles.append(profile)
        return profile

    def rename_operator_profile(self, profile_id, name):
        profile = next(item for item in self.profiles if item["id"] == profile_id)
        profile["name"] = name
        return profile

    def delete_operator_profile(self, profile_id):
        self.profiles = [item for item in self.profiles if item["id"] != profile_id]
        return self.list_operator_profiles()

    def activate_operator_profile(self, profile_id):
        self.active_profile_id = profile_id
        for item in self.profiles:
            item["active"] = item["id"] == profile_id
        return self.operator_profile_status()

    def export_operator_profile(self, profile_id):
        profile = next(item for item in self.profiles if item["id"] == profile_id)
        return {"version": 1, "name": profile["name"], "calibration": {"mode": "five_pose"}}

    def import_operator_profile(self, payload):
        return self.create_operator_profile(payload["name"])

    def start_profile_calibration(self, profile_id):
        self.activate_operator_profile(profile_id)
        self.profile_calibration = {
            "state": "COLLECTING",
            "profile_id": profile_id,
            "pose": "open",
            "pose_index": 0,
            "total_poses": 5,
            "accepted_samples": 0,
            "required_samples": 30,
            "stability": None,
            "error": None,
            "failed_pose": None,
        }
        return self.profile_calibration

    def retry_profile_calibration(self, profile_id):
        return self.profile_calibration

    def cancel_profile_calibration(self, profile_id):
        self.profile_calibration = {**self.profile_calibration, "state": "CANCELED"}
        return self.profile_calibration


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


class FakeCamera:
    source = "realsense"
    socket_path = "/tmp/test-rgb.sock"
    rotation = 90
    is_alive = True
    connected = True


def test_health_and_runtime_lifespan():
    runtime = FakeRuntime()
    with TestClient(create_app(runtime=runtime)) as client:
        response = client.get("/api/health")
        assert response.json() == {
            "status": "ok",
            "camera_source": "realsense",
            "camera_socket": "/tmp/test-rgb.sock",
            "camera_alive": True,
            "camera_connected": True,
            "camera_rotation": 90,
            "modbus_output": False,
            "control_state": "DISARMED",
            "connected": True,
        }
        assert runtime.started
    assert runtime.stopped


def test_default_runtime_is_created_only_when_lifespan_starts(monkeypatch):
    runtime = FakeRuntime()
    created = []

    def build_runtime():
        created.append(runtime)
        return runtime

    monkeypatch.setattr(app_module, "ViewerRuntime", build_runtime)
    app = create_app()

    assert created == []
    with TestClient(app):
        assert created == [runtime]
        assert app.state.runtime is runtime
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
    assert payload["operator_profile"]["id"] == "default"
    assert payload["retargeting_calibration"] is None


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


def test_motion_commands_are_rejected_when_manual_control_owns_hand():
    app = create_app(runtime=FakeRuntime())
    app.state.allow_control = False
    headers = {"X-RH56-Control": "operator-confirmed"}

    with TestClient(app) as client:
        arm = client.post("/api/control/arm", headers=headers)
        home = client.post("/api/control/home", headers=headers)
        stopped = client.post("/api/control/estop", headers=headers)

    assert arm.status_code == 409
    assert home.status_code == 409
    assert stopped.status_code == 200


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


def test_deprecated_open_hand_calibration_routes_are_removed():
    paths = {getattr(route, "path", None) for route in create_app(runtime=FakeRuntime()).routes}

    assert "/api/retargeting/calibration" not in paths
    assert "/api/retargeting/calibration/open" not in paths


def test_operator_profile_routes_are_guarded_and_start_five_pose_calibration():
    runtime = FakeRuntime()
    headers = {"X-RH56-Control": "operator-confirmed"}
    with TestClient(create_app(runtime=runtime)) as client:
        assert client.get("/api/retargeting/profiles").json()["active_profile_id"] == "default"
        rejected = client.post("/api/retargeting/profiles", json={"name": "Operator A"})
        created = client.post(
            "/api/retargeting/profiles", headers=headers, json={"name": "Operator A"}
        )
        profile_id = created.json()["id"]
        activated = client.put(
            f"/api/retargeting/profiles/{profile_id}/activate", headers=headers
        )
        started = client.post(
            f"/api/retargeting/profiles/{profile_id}/calibration/start", headers=headers
        )

    assert rejected.status_code == 403
    assert created.status_code == 200
    assert activated.json()["id"] == profile_id
    assert started.json()["pose"] == "open"
    assert started.json()["total_poses"] == 5


def test_profile_import_export_and_mutation_routes():
    runtime = FakeRuntime()
    headers = {"X-RH56-Control": "operator-confirmed"}
    with TestClient(create_app(runtime=runtime)) as client:
        created = client.post(
            "/api/retargeting/profiles", headers=headers, json={"name": "Portable"}
        ).json()
        renamed = client.patch(
            f"/api/retargeting/profiles/{created['id']}",
            headers=headers,
            json={"name": "Portable A"},
        )
        exported = client.get(f"/api/retargeting/profiles/{created['id']}/export")
        imported = client.post(
            "/api/retargeting/profiles/import",
            headers=headers,
            json={"version": 1, "name": "Imported", "calibration": {"mode": "five_pose"}},
        )
        deleted = client.delete(
            f"/api/retargeting/profiles/{created['id']}", headers=headers
        )

    assert renamed.json()["name"] == "Portable A"
    assert exported.json()["version"] == 1
    assert imported.json()["name"] == "Imported"
    assert deleted.status_code == 200


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


def test_vision_service_does_not_serve_the_deprecated_standalone_frontend():
    app = create_app(runtime=FakeRuntime())
    assert not any(getattr(route, "path", None) == "/{path:path}" for route in app.routes)

    with TestClient(app) as client:
        assert client.get("/").status_code == 404
