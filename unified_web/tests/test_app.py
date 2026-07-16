from contextlib import asynccontextmanager

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
