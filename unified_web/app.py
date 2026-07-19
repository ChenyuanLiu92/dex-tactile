from __future__ import annotations

import sys
from asyncio import to_thread
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


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


ControlOwner = Literal["vision", "manual"]


class ControlOwnerRequest(BaseModel):
    owner: ControlOwner


def create_unified_app(
    *,
    device_app: FastAPI | None = None,
    vision_app: FastAPI | None = None,
) -> FastAPI:
    active_device_app = device_app or default_device_app
    active_vision_app = vision_app or default_vision_app
    control_gate = RLock()
    active_device_app.state.allow_control = False
    active_device_app.state.control_gate = control_gate
    active_vision_app.state.allow_control = True
    active_vision_app.state.control_gate = control_gate

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
    app.state.control_owner = "vision"
    app.state.control_gate = control_gate

    def owner_payload() -> dict[str, object]:
        controller = active_vision_app.state.runtime.controller
        state = controller.snapshot().state
        return {
            "owner": app.state.control_owner,
            "vision_state": getattr(state, "value", str(state)),
            "manual_control_enabled": bool(active_device_app.state.allow_control),
        }

    def switch_owner(owner: ControlOwner) -> dict[str, object]:
        with control_gate:
            if owner == app.state.control_owner:
                return owner_payload()

            controller = active_vision_app.state.runtime.controller
            if owner == "manual":
                state = controller.snapshot().state
                state_value = getattr(state, "value", str(state))
                if state_value == "ARMED":
                    controller.disarm()
                    state_value = getattr(controller.snapshot().state, "value", "")
                if state_value not in {"DISARMED", "DISCONNECTED"}:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Cannot enter manual control while Vision is {state_value}",
                    )
                active_vision_app.state.allow_control = False
                active_device_app.state.allow_control = True
            else:
                active_device_app.state.allow_control = False
                active_device_app.state.manager.disarm_all()
                active_vision_app.state.allow_control = True

            app.state.control_owner = owner
            return owner_payload()

    @app.get("/api/control-owner")
    async def get_control_owner() -> dict[str, object]:
        return owner_payload()

    @app.put("/api/control-owner")
    async def put_control_owner(
        request: ControlOwnerRequest,
        x_rh56_control: str | None = Header(default=None),
    ) -> dict[str, object]:
        if x_rh56_control != "operator-confirmed":
            raise HTTPException(status_code=403, detail="Missing operator control header")
        return await to_thread(switch_owner, request.owner)

    app.mount("/vision", active_vision_app, name="vision")
    app.mount("/", active_device_app, name="device")
    return app


app = create_unified_app()
