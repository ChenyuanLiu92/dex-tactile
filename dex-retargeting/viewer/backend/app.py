from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .runtime import ViewerRuntime
from .control.controller import TransitionError
from .operator_profiles import ProfileError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HAND_ASSET_ROOT = REPOSITORY_ROOT / "assets" / "robots" / "hands" / "inspire_hand"


class ProfileNameRequest(BaseModel):
    name: str


def create_app(runtime: ViewerRuntime | None = None) -> FastAPI:
    active_runtime = runtime

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal active_runtime
        if active_runtime is None:
            active_runtime = ViewerRuntime()
        _app.state.runtime = active_runtime
        active_runtime.start()
        try:
            yield
        finally:
            active_runtime.stop()

    app = FastAPI(title="D435 Vision Retargeting Viewer", lifespan=lifespan)
    app.state.runtime = active_runtime
    app.state.allow_control = True
    app.state.control_gate = RLock()

    def current_runtime() -> ViewerRuntime:
        if active_runtime is None:
            raise RuntimeError("Viewer runtime is not started")
        return active_runtime

    @app.get("/api/health")
    def health():
        runtime = current_runtime()
        control = runtime.controller.snapshot()
        camera = getattr(runtime, "camera", None)
        payload = {
            "status": "ok",
            "camera_source": getattr(camera, "source", "unknown"),
            "camera_alive": bool(getattr(camera, "is_alive", False)),
            "camera_connected": bool(getattr(camera, "connected", False)),
            "camera_rotation": getattr(camera, "rotation", 0),
            "modbus_output": control.state.value in {"ARMED", "POSITIONING"},
            "control_state": control.state.value,
            "connected": control.connected,
        }
        if camera is not None and hasattr(camera, "socket_path"):
            payload["camera_socket"] = camera.socket_path
        if camera is not None and hasattr(camera, "camera_index"):
            payload["camera_index"] = camera.camera_index
        return payload

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

    def controlled_transition(action):
        with app.state.control_gate:
            if not app.state.allow_control:
                raise HTTPException(
                    status_code=409,
                    detail="Digital Twin manual control owns the hand",
                )
            return transition(action)

    def profile_action(action):
        with app.state.control_gate:
            try:
                return action()
            except TransitionError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except ProfileError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/control/arm")
    def arm(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return controlled_transition(current_runtime().controller.arm)

    @app.post("/api/control/disarm")
    def disarm(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(current_runtime().controller.disarm)

    @app.post("/api/control/home")
    def home(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return controlled_transition(current_runtime().controller.home)

    @app.post("/api/control/open")
    def open_pose(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return controlled_transition(current_runtime().controller.open)

    @app.post("/api/control/estop")
    def estop(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(current_runtime().controller.estop)

    @app.post("/api/control/reset")
    def reset(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(current_runtime().controller.reset)

    @app.post("/api/control/reconnect")
    def reconnect(x_rh56_control: str | None = Header(default=None)):
        verify_control_header(x_rh56_control)
        return transition(current_runtime().controller.reconnect)

    @app.get("/api/retargeting/profiles")
    def list_profiles():
        return current_runtime().list_operator_profiles()

    @app.post("/api/retargeting/profiles")
    def create_profile(
        request: ProfileNameRequest,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().create_operator_profile(request.name))

    @app.patch("/api/retargeting/profiles/{profile_id}")
    def rename_profile(
        profile_id: str,
        request: ProfileNameRequest,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(
            lambda: current_runtime().rename_operator_profile(profile_id, request.name)
        )

    @app.delete("/api/retargeting/profiles/{profile_id}")
    def delete_profile(
        profile_id: str,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().delete_operator_profile(profile_id))

    @app.put("/api/retargeting/profiles/{profile_id}/activate")
    def activate_profile(
        profile_id: str,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().activate_operator_profile(profile_id))

    @app.get("/api/retargeting/profiles/{profile_id}/export")
    def export_profile(profile_id: str):
        return profile_action(lambda: current_runtime().export_operator_profile(profile_id))

    @app.post("/api/retargeting/profiles/import")
    def import_profile(
        payload: dict,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().import_operator_profile(payload))

    @app.post("/api/retargeting/profiles/{profile_id}/calibration/start")
    def start_profile_calibration(
        profile_id: str,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().start_profile_calibration(profile_id))

    @app.post("/api/retargeting/profiles/{profile_id}/calibration/retry")
    def retry_profile_calibration(
        profile_id: str,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().retry_profile_calibration(profile_id))

    @app.post("/api/retargeting/profiles/{profile_id}/calibration/cancel")
    def cancel_profile_calibration(
        profile_id: str,
        x_rh56_control: str | None = Header(default=None),
    ):
        verify_control_header(x_rh56_control)
        return profile_action(lambda: current_runtime().cancel_profile_calibration(profile_id))

    @app.get("/api/video.mjpg")
    def video_stream():
        def frames():
            runtime = current_runtime()
            sequence = 0
            while True:
                packet = runtime.frame_store.wait_for_new(sequence, timeout=1.0)
                if packet is None:
                    packet = runtime.frame_store.latest()
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
                runtime = current_runtime()
                payload = runtime.snapshot().to_payload()
                control = runtime.controller.snapshot().to_payload()
                payload["control"] = control
                payload["operator_profile"] = runtime.operator_profile_status()
                payload["retargeting_calibration"] = (
                    runtime.profile_calibration_status()
                )
                payload["dry_run"] = False
                payload["modbus_output"] = control["modbus_output"]
                await websocket.send_json(payload)
                await asyncio.sleep(1 / 30)
        except (WebSocketDisconnect, RuntimeError):
            return

    app.mount("/assets", StaticFiles(directory=HAND_ASSET_ROOT), name="hand-assets")

    return app


app = create_app()
