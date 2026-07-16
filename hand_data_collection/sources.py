from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import websockets


ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "dex-retargeting",
    ROOT / "inspire_visualizer" / "backend" / "src",
):
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)


@dataclass(frozen=True)
class LatestFrame:
    payload: dict[str, Any] | None
    received_at: float
    connected: bool


class HandDataSource(Protocol):
    mode: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def latest_frame(self) -> LatestFrame: ...

    def latest_device(self) -> dict[str, Any] | None: ...

    def latest_tactile(self) -> dict[str, Any] | None: ...

    def drain_tactile(self) -> list[dict[str, Any]]: ...


def _ws_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base.removeprefix("https://")
    elif base.startswith("http://"):
        base = "ws://" + base.removeprefix("http://")
    return base + path


def _request_json(url: str, timeout: float = 1.0) -> dict[str, Any]:
    request = build_opener(ProxyHandler({})).open(url, timeout=timeout)
    with request:
        return json.loads(request.read().decode("utf-8"))


def viewer_health(base_url: str) -> str:
    results: list[bool] = []
    for path in ("/api/health", "/vision/api/health"):
        try:
            payload = _request_json(base_url.rstrip("/") + path)
            results.append(payload.get("status") == "ok")
        except URLError as error:
            if isinstance(error.reason, ConnectionRefusedError):
                results.append(False)
                continue
            raise RuntimeError(f"Viewer health check failed: {error.reason}") from error
        except (TimeoutError, OSError) as error:
            if isinstance(error, ConnectionRefusedError):
                results.append(False)
                continue
            raise RuntimeError(f"Viewer port is present but unhealthy: {error}") from error
    if all(results):
        return "healthy"
    if not any(results):
        return "absent"
    raise RuntimeError("Viewer is partially available; both device and vision services are required")


class ViewerSource:
    mode = "viewer"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = False
        self._vision: dict[str, Any] | None = None
        self._vision_received = 0.0
        self._vision_connected = False
        self._device: dict[str, Any] | None = None
        self._tactile: dict[str, Any] | None = None
        self._tactile_queue: deque[dict[str, Any]] = deque()

    async def start(self) -> None:
        self._stopping = False
        self._tasks = [
            asyncio.create_task(self._vision_loop(), name="collection-viewer-vision"),
            asyncio.create_task(self._device_loop(), name="collection-viewer-device"),
        ]

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    def latest_frame(self) -> LatestFrame:
        return LatestFrame(self._vision, self._vision_received, self._vision_connected)

    def latest_device(self) -> dict[str, Any] | None:
        return self._device

    def latest_tactile(self) -> dict[str, Any] | None:
        return self._tactile

    def drain_tactile(self) -> list[dict[str, Any]]:
        frames = list(self._tactile_queue)
        self._tactile_queue.clear()
        return frames

    async def _vision_loop(self) -> None:
        url = _ws_url(self.base_url, "/vision/api/ws")
        while not self._stopping:
            try:
                async with websockets.connect(url, proxy=None) as websocket:
                    self._vision_connected = True
                    async for raw in websocket:
                        self._vision = json.loads(raw)
                        self._vision_received = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._vision_connected = False
                await asyncio.sleep(1.0)
            finally:
                self._vision_connected = False

    async def _device_loop(self) -> None:
        url = _ws_url(self.base_url, "/api/ws")
        while not self._stopping:
            try:
                async with websockets.connect(url, proxy=None) as websocket:
                    async for raw in websocket:
                        payload = json.loads(raw)
                        if payload.get("type") == "snapshot":
                            self._device = payload
                        elif payload.get("type") == "tactile_frame" and payload.get("side") == "right":
                            payload["received_at"] = time.time()
                            self._tactile = payload
                            self._tactile_queue.append(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1.0)


class _ReadOnlyController:
    """ViewerRuntime adapter with no device driver and no write operations."""

    def __init__(self):
        from viewer.backend.control.controller import ControlSnapshot, ControlState

        self._snapshot = ControlSnapshot(state=ControlState.DISARMED, connected=False)

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def update_tracking(self, _snapshot) -> None:
        return None

    def snapshot(self):
        return self._snapshot


class StandaloneSource:
    mode = "standalone"

    def __init__(self):
        self._runtime = None
        self._manager = None
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = False
        self._device: dict[str, Any] | None = None
        self._tactile: dict[str, Any] | None = None
        self._tactile_queue: deque[dict[str, Any]] = deque()

    async def start(self) -> None:
        from inspire_visualizer_api.config import ConfigStore
        from inspire_visualizer_api.device.manager import DeviceManager
        from viewer.backend.runtime import ViewerRuntime

        config_path = ROOT / "inspire_visualizer" / "config" / "hands.json"
        config = ConfigStore(config_path).load()
        if not config.right.enabled:
            raise RuntimeError("Right hand is disabled in inspire_visualizer/config/hands.json")
        if config.right.tactile_profile != "piezoresistive_v1":
            raise RuntimeError("Right hand tactile_profile must be piezoresistive_v1")
        self._runtime = ViewerRuntime(controller=_ReadOnlyController())
        self._manager = DeviceManager(config)
        self._runtime.start()
        self._stopping = False
        self._tasks = [
            asyncio.create_task(self._robot_loop(), name="collection-standalone-robot"),
            asyncio.create_task(self._tactile_loop(), name="collection-standalone-tactile"),
        ]

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._runtime is not None:
            await asyncio.to_thread(self._runtime.stop)
            self._runtime = None
        if self._manager is not None:
            await asyncio.to_thread(self._manager.close)
            self._manager = None

    def latest_frame(self) -> LatestFrame:
        if self._runtime is None:
            return LatestFrame(None, 0.0, False)
        payload = self._runtime.snapshot().to_payload()
        payload["control"] = self._runtime.controller.snapshot().to_payload()
        payload["dry_run"] = True
        payload["modbus_output"] = False
        return LatestFrame(payload, time.monotonic(), True)

    def latest_device(self) -> dict[str, Any] | None:
        return self._device

    def latest_tactile(self) -> dict[str, Any] | None:
        return self._tactile

    def drain_tactile(self) -> list[dict[str, Any]]:
        frames = list(self._tactile_queue)
        self._tactile_queue.clear()
        return frames

    async def _robot_loop(self) -> None:
        assert self._manager is not None
        while not self._stopping:
            snapshot = self._manager.snapshots()["right"]
            try:
                if snapshot.connection != "online":
                    await asyncio.to_thread(self._manager.discover_side, "right")
                else:
                    await asyncio.to_thread(self._manager.poll, "right")
            except Exception:
                pass
            current = self._manager.snapshots()["right"]
            self._device = {
                "type": "snapshot",
                "hands": {
                    "right": {
                        "side": "right",
                        "connection": current.connection,
                        "actual_angles": current.actual_angles,
                        "armed": False,
                        "updated_at": current.updated_at,
                        "error": current.error,
                    }
                },
            }
            await asyncio.sleep(0.2)

    async def _tactile_loop(self) -> None:
        assert self._manager is not None
        while not self._stopping:
            try:
                frame = await asyncio.to_thread(self._manager.poll_tactile, "right")
                payload = {
                    "type": "tactile_frame",
                    "side": frame.side,
                    "profile": frame.profile,
                    "sequence": frame.sequence,
                    "captured_at": frame.captured_at,
                    "received_at": time.time(),
                    "regions": [
                        {
                            "id": region.id,
                            "rows": region.rows,
                            "columns": region.columns,
                            "values": region.values,
                        }
                        for region in frame.regions
                    ],
                }
                self._tactile = payload
                self._tactile_queue.append(payload)
            except Exception:
                pass
            await asyncio.sleep(0.05)


def select_source(mode: str, viewer_url: str) -> HandDataSource:
    if mode == "viewer":
        return ViewerSource(viewer_url)
    if mode == "standalone":
        return StandaloneSource()
    if mode != "auto":
        raise ValueError(f"Unsupported source mode: {mode}")
    health = viewer_health(viewer_url)
    return ViewerSource(viewer_url) if health == "healthy" else StandaloneSource()
