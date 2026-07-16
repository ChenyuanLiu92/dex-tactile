from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .runtime import ViewerRuntime
from .control.controller import TransitionError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HAND_ASSET_ROOT = REPOSITORY_ROOT / "assets" / "robots" / "hands" / "inspire_hand"
WEB_DIST = REPOSITORY_ROOT / "viewer" / "web" / "dist"


def create_app(runtime: ViewerRuntime | None = None) -> FastAPI:
    active_runtime = runtime or ViewerRuntime()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        active_runtime.start()
        try:
            yield
        finally:
            active_runtime.stop()

    app = FastAPI(title="D435 Vision Retargeting Viewer", lifespan=lifespan)
    app.state.runtime = active_runtime

    @app.get("/api/health")
    def health():
        control = active_runtime.controller.snapshot()
        return {
            "status": "ok",
            "camera_index": 0,
            "modbus_output": control.state.value in {"ARMED", "POSITIONING"},
            "control_state": control.state.value,
            "connected": control.connected,
        }

    def transition(action):
        try:
            return action().to_payload()
        except TransitionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    def verify_control_header(value: str | None) -> None:
        if value != "operator-confirmed":
            raise HTTPException(
                status_code=403, detail="Missing operator control header"
            )

    @app.post("/api/control/arm")
    def arm(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.arm)

    @app.post("/api/control/disarm")
    def disarm(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.disarm)

    @app.post("/api/control/home")
    def home(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.home)

    @app.post("/api/control/open")
    def open_pose(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.open)

    @app.post("/api/control/estop")
    def estop(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.estop)

    @app.post("/api/control/reset")
    def reset(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.reset)

    @app.post("/api/control/reconnect")
    def reconnect(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(active_runtime.controller.reconnect)

    @app.get("/api/retargeting/calibration")
    def calibration_status():
        return active_runtime.calibration_status()

    @app.post("/api/retargeting/calibration/open")
    def calibrate_open(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        try:
            return active_runtime.start_open_calibration()
        except TransitionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/video.mjpg")
    def video_stream():
        def frames():
            sequence = 0
            while True:
                packet = active_runtime.frame_store.wait_for_new(sequence, timeout=1.0)
                if packet is None:
                    packet = active_runtime.frame_store.latest()
                if packet is None:
                    continue
                sequence = packet.sequence
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                    + packet.jpeg
                    + b"\r\n"
                )

        return StreamingResponse(
            frames(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    @app.websocket("/api/ws")
    async def telemetry(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                payload = active_runtime.snapshot().to_payload()
                control = active_runtime.controller.snapshot().to_payload()
                payload["control"] = control
                payload["dry_run"] = False
                payload["modbus_output"] = control["modbus_output"]
                await websocket.send_json(payload)
                await asyncio.sleep(1 / 30)
        except (WebSocketDisconnect, RuntimeError):
            return

    app.mount("/assets", StaticFiles(directory=HAND_ASSET_ROOT), name="hand-assets")

    if WEB_DIST.is_dir():
        static_dir = WEB_DIST / "web-assets"
        if static_dir.is_dir():
            app.mount(
                "/web-assets", StaticFiles(directory=static_dir), name="web-assets"
            )

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            candidate = WEB_DIST / path
            if path and candidate.is_file() and WEB_DIST in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app


app = create_app()
