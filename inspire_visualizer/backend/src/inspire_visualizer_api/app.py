import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from inspire_visualizer_api.config import ConfigStore, HandsConfig
from inspire_visualizer_api.device.manager import (
    DeviceManager,
    DeviceUnavailable,
    NotArmed,
    TactileFrame,
)
from inspire_visualizer_api.protocol import (
    ExecutePoseMessage,
    SetArmedMessage,
    client_message_adapter,
)
from inspire_visualizer_api.tactile_calibration import TactileCalibrationDocument, TactileCalibrationStore

VISUALIZER_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = VISUALIZER_ROOT / "config" / "hands.json"
DEFAULT_TACTILE_CALIBRATION_PATH = VISUALIZER_ROOT / "config" / "tactile_calibration.json"
WEB_DIST_PATH = VISUALIZER_ROOT / "web" / "dist"


@dataclass
class _ConnectionState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending_tactile: dict[str, dict[str, Any]] = field(default_factory=dict)


class ConnectionHub:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, _ConnectionState] = {}

    def add(self, websocket: WebSocket) -> None:
        self._connections[websocket] = _ConnectionState()

    def remove(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def send(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        state = self._connections.get(websocket)
        if state is None:
            return
        if message.get("type") == "tactile_frame" and state.lock.locked():
            state.pending_tactile[str(message["side"])] = message
            return
        async with state.lock:
            await websocket.send_json(jsonable_encoder(message))
            while state.pending_tactile:
                _, pending = state.pending_tactile.popitem()
                await websocket.send_json(jsonable_encoder(pending))

    async def broadcast(self, message: dict[str, Any]) -> None:
        for websocket in tuple(self._connections):
            try:
                await self.send(websocket, message)
            except Exception:
                self.remove(websocket)


def _snapshot_payload(manager: DeviceManager) -> dict[str, Any]:
    hands = {
        side: {
            "side": snapshot.side,
            "connection": snapshot.connection,
            "actual_angles": snapshot.actual_angles,
            "armed": snapshot.armed,
            "updated_at": snapshot.updated_at,
            "error": snapshot.error,
            "tactile": {
                "profile": snapshot.tactile.profile,
                "state": snapshot.tactile.state,
                "target_hz": snapshot.tactile.target_hz,
                "sample_hz": snapshot.tactile.sample_hz,
                "updated_at": snapshot.tactile.updated_at,
                "error": snapshot.tactile.error,
            },
        }
        for side, snapshot in manager.snapshots().items()
    }
    return {"type": "snapshot", "hands": hands}


def _tactile_payload(frame: TactileFrame) -> dict[str, Any]:
    return {
        "type": "tactile_frame",
        "side": frame.side,
        "profile": frame.profile,
        "sequence": frame.sequence,
        "captured_at": frame.captured_at,
        "regions": [
            {
                "id": region.id,
                "rows": region.rows,
                "columns": region.columns,
                "values": region.values,
                "metrics": region.metrics,
            }
            for region in frame.regions
        ],
    }


async def _device_loop(app: FastAPI) -> None:
    last_discovery = 0.0
    while True:
        manager: DeviceManager = app.state.manager
        snapshots = manager.snapshots()
        now = monotonic()
        tasks: list[asyncio.Future[Any] | asyncio.Task[Any] | Any] = []
        for side, snapshot in snapshots.items():
            if snapshot.connection == "online":
                tasks.append(asyncio.to_thread(manager.poll, side))
            elif now - last_discovery >= 2.0:
                tasks.append(asyncio.to_thread(manager.discover_side, side))
        if now - last_discovery >= 2.0:
            last_discovery = now
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await app.state.hub.broadcast(_snapshot_payload(manager))
        await asyncio.sleep(0.2)


async def _tactile_loop(app: FastAPI) -> None:
    next_sample = {"left": 0.0, "right": 0.0}
    while True:
        manager: DeviceManager = app.state.manager
        snapshots = manager.snapshots()
        now = monotonic()
        scheduled: list[tuple[str, asyncio.Task[Any]]] = []
        for side, snapshot in snapshots.items():
            if (
                snapshot.connection == "online"
                and snapshot.tactile.profile != "disabled"
                and now >= next_sample[side]
            ):
                next_sample[side] = now + 1 / snapshot.tactile.target_hz
                scheduled.append(
                    (side, asyncio.create_task(asyncio.to_thread(manager.poll_tactile, side)))
                )
        if not scheduled:
            await asyncio.sleep(0.005)
            continue
        results = await asyncio.gather(
            *(task for _, task in scheduled),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, TactileFrame):
                await app.state.hub.broadcast(_tactile_payload(result))


def create_app(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    tactile_calibration_path: Path = DEFAULT_TACTILE_CALIBRATION_PATH,
    manager_factory: Callable[[HandsConfig], DeviceManager] = DeviceManager,
    start_background: bool = True,
    allow_control: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = ConfigStore(config_path)
        app.state.store = store
        app.state.tactile_calibration_store = TactileCalibrationStore(tactile_calibration_path)
        app.state.manager = manager_factory(store.load())
        app.state.hub = ConnectionHub()
        background_tasks = (
            (
                asyncio.create_task(_device_loop(app), name="inspire-device-loop"),
                asyncio.create_task(_tactile_loop(app), name="inspire-tactile-loop"),
            )
            if start_background
            else ()
        )
        try:
            yield
        finally:
            for background_task in background_tasks:
                background_task.cancel()
            for background_task in background_tasks:
                with suppress(asyncio.CancelledError):
                    await background_task
            await asyncio.to_thread(app.state.manager.close)

    app = FastAPI(title="Inspire Hand Visualizer", version="0.1.0", lifespan=lifespan)
    app.state.allow_control = allow_control

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        snapshots = app.state.manager.snapshots()
        return {
            "status": "ok",
            "online_hands": sum(
                snapshot.connection == "online" for snapshot in snapshots.values()
            ),
        }

    @app.get("/api/config", response_model=HandsConfig)
    async def get_config() -> HandsConfig:
        return app.state.store.load()

    @app.put("/api/config", response_model=HandsConfig)
    async def put_config(config: HandsConfig) -> HandsConfig:
        app.state.store.save(config)
        await asyncio.to_thread(app.state.manager.reconfigure, config)
        await app.state.hub.broadcast(_snapshot_payload(app.state.manager))
        return config

    @app.get("/api/tactile-calibration/{side}", response_model=TactileCalibrationDocument | None)
    async def get_tactile_calibration(side: str) -> TactileCalibrationDocument | None:
        if side not in ("left", "right"):
            return None
        endpoint = app.state.store.load().left if side == "left" else app.state.store.load().right
        return app.state.tactile_calibration_store.load(side, str(endpoint.host), endpoint.port, endpoint.tactile_profile)

    @app.put("/api/tactile-calibration/{side}", response_model=TactileCalibrationDocument)
    async def put_tactile_calibration(side: str, document: TactileCalibrationDocument) -> TactileCalibrationDocument:
        if side not in ("left", "right") or document.side != side:
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail="calibration side does not match route")
        endpoint = app.state.store.load().left if side == "left" else app.state.store.load().right
        if (document.host, document.port, document.profile) != (str(endpoint.host), endpoint.port, endpoint.tactile_profile):
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="calibration endpoint does not match current device config")
        app.state.tactile_calibration_store.save(document)
        return document

    @app.post("/api/discovery/refresh")
    async def refresh_discovery() -> dict[str, Any]:
        await asyncio.to_thread(app.state.manager.discover)
        payload = _snapshot_payload(app.state.manager)
        await app.state.hub.broadcast(payload)
        return {"hands": payload["hands"]}

    @app.websocket("/api/ws")
    async def device_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = str(uuid4())
        app.state.hub.add(websocket)
        await app.state.hub.send(websocket, _snapshot_payload(app.state.manager))
        try:
            while True:
                raw_message = await websocket.receive_json()
                try:
                    message = client_message_adapter.validate_python(raw_message)
                    if isinstance(message, SetArmedMessage):
                        if not app.state.allow_control:
                            await app.state.hub.send(
                                websocket,
                                {
                                    "type": "error",
                                    "code": "vision_control_required",
                                    "message": "Use Vision Control to operate the hand",
                                },
                            )
                            continue
                        await asyncio.to_thread(
                            app.state.manager.set_armed,
                            message.side,
                            session_id,
                            message.armed,
                        )
                        await app.state.hub.send(
                            websocket,
                            {
                                "type": "armed_state",
                                "side": message.side,
                                "armed": message.armed,
                            },
                        )
                    elif isinstance(message, ExecutePoseMessage):
                        if not app.state.allow_control:
                            await app.state.hub.send(
                                websocket,
                                {
                                    "type": "error",
                                    "code": "vision_control_required",
                                    "message": "Use Vision Control to operate the hand",
                                },
                            )
                            continue
                        actual_angles = await asyncio.to_thread(
                            app.state.manager.execute_pose,
                            message.side,
                            session_id,
                            angles=message.angles,
                            speeds=message.speeds,
                            forces=message.forces,
                        )
                        await app.state.hub.send(
                            websocket,
                            {
                                "type": "command_result",
                                "command_id": message.command_id,
                                "side": message.side,
                                "accepted": True,
                                "actual_angles": actual_angles,
                            },
                        )
                except ValidationError as error:
                    await app.state.hub.send(
                        websocket,
                        {"type": "error", "code": "invalid_message", "message": str(error)},
                    )
                except NotArmed as error:
                    await app.state.hub.send(
                        websocket,
                        {"type": "error", "code": "not_armed", "message": str(error)},
                    )
                except DeviceUnavailable as error:
                    await app.state.hub.send(
                        websocket,
                        {"type": "error", "code": "device_unavailable", "message": str(error)},
                    )
        except WebSocketDisconnect:
            pass
        finally:
            await asyncio.to_thread(app.state.manager.disarm_session, session_id)
            app.state.hub.remove(websocket)

    if WEB_DIST_PATH.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST_PATH, html=True), name="web")

    return app


app = create_app()
