from __future__ import annotations

import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "dex-retargeting",
    ROOT / "inspire_visualizer" / "backend" / "src",
):
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)

from inspire_visualizer_api.app import app as default_device_app  # noqa: E402
from viewer.backend.app import app as default_vision_app  # noqa: E402


def create_unified_app(
    *,
    device_app: FastAPI | None = None,
    vision_app: FastAPI | None = None,
) -> FastAPI:
    active_device_app = device_app or default_device_app
    active_vision_app = vision_app or default_vision_app
    if device_app is None:
        active_device_app.state.allow_control = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(
                active_vision_app.router.lifespan_context(active_vision_app)
            )
            await stack.enter_async_context(
                active_device_app.router.lifespan_context(active_device_app)
            )
            yield

    app = FastAPI(title="Inspire Dexterous Hand Workbench", lifespan=lifespan)
    app.state.device_app = active_device_app
    app.state.vision_app = active_vision_app
    app.mount("/vision", active_vision_app, name="vision")
    app.mount("/", active_device_app, name="device")
    return app


app = create_unified_app()
