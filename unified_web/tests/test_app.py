from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from unified_web.app import create_unified_app


def child(name: str, events: list[str]) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        events.append(f"{name}:start")
        yield
        events.append(f"{name}:stop")

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"service": name}

    return app


class FakeController:
    def __init__(self, state: str = "DISARMED") -> None:
        self.state = state
        self.disarm_count = 0

    def snapshot(self):
        return SimpleNamespace(state=SimpleNamespace(value=self.state))

    def disarm(self):
        self.disarm_count += 1
        self.state = "DISARMED"
        return self.snapshot()


class FakeManager:
    def __init__(self) -> None:
        self.disarm_all_count = 0

    def disarm_all(self) -> None:
        self.disarm_all_count += 1


def control_children(events: list[str], vision_state: str = "DISARMED"):
    device = child("device", events)
    vision = child("vision", events)
    controller = FakeController(vision_state)
    manager = FakeManager()
    device.state.manager = manager
    vision.state.runtime = SimpleNamespace(controller=controller)
    return device, vision, controller, manager


def test_unified_app_mounts_both_services_and_runs_their_lifespans():
    events: list[str] = []
    app = create_unified_app(
        device_app=child("device", events),
        vision_app=child("vision", events),
    )

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"service": "device"}
        assert client.get("/vision/api/health").json() == {"service": "vision"}
        assert events == ["vision:start", "device:start"]

    assert events == ["vision:start", "device:start", "device:stop", "vision:stop"]


def test_switching_to_manual_disarms_vision_before_enabling_manual_control():
    events: list[str] = []
    device, vision, controller, _manager = control_children(events, "ARMED")
    app = create_unified_app(device_app=device, vision_app=vision)

    with TestClient(app) as client:
        response = client.put(
            "/api/control-owner",
            headers={"X-RH56-Control": "operator-confirmed"},
            json={"owner": "manual"},
        )

    assert response.status_code == 200
    assert response.json()["owner"] == "manual"
    assert controller.disarm_count == 1
    assert vision.state.allow_control is False
    assert device.state.allow_control is True


def test_switching_to_vision_disables_manual_and_releases_all_sessions():
    events: list[str] = []
    device, vision, _controller, manager = control_children(events)
    app = create_unified_app(device_app=device, vision_app=vision)
    headers = {"X-RH56-Control": "operator-confirmed"}

    with TestClient(app) as client:
        assert client.put("/api/control-owner", headers=headers, json={"owner": "manual"}).status_code == 200
        response = client.put("/api/control-owner", headers=headers, json={"owner": "vision"})

    assert response.status_code == 200
    assert response.json()["owner"] == "vision"
    assert manager.disarm_all_count == 1
    assert device.state.allow_control is False
    assert vision.state.allow_control is True


def test_owner_switch_requires_confirmation_and_rejects_unsafe_vision_state():
    events: list[str] = []
    device, vision, _controller, _manager = control_children(events, "POSITIONING")
    app = create_unified_app(device_app=device, vision_app=vision)

    with TestClient(app) as client:
        missing_header = client.put("/api/control-owner", json={"owner": "manual"})
        conflict = client.put(
            "/api/control-owner",
            headers={"X-RH56-Control": "operator-confirmed"},
            json={"owner": "manual"},
        )

    assert missing_header.status_code == 403
    assert conflict.status_code == 409
    assert device.state.allow_control is False
