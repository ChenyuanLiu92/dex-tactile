from __future__ import annotations

import argparse
import errno
import json
import sys
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from .control.controller import ControlState, Preset, VisionHandController


CONTROL_HEADER = {"X-RH56-Control": "operator-confirmed"}
TERMINAL_STATES = {"FAULT", "ESTOPPED", "DISCONNECTED"}
DIRECT_HTTP_OPENER = build_opener(ProxyHandler({}))


def request_json(
    base_url: str,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: float = 2.0,
) -> dict:
    request = Request(
        base_url + path,
        data=b"" if method == "POST" else None,
        headers=headers or {},
        method=method,
    )
    with DIRECT_HTTP_OPENER.open(request, timeout=timeout) as response:
        return json.load(response)


def probe_viewer(base_url: str) -> dict | None:
    try:
        return request_json(base_url, "/api/health", timeout=1.0)
    except URLError as error:
        reason = error.reason
        if isinstance(reason, ConnectionRefusedError) or getattr(
            reason, "errno", None
        ) == errno.ECONNREFUSED:
            return None
        raise RuntimeError(f"Viewer health check failed: {reason}") from error
    except TimeoutError as error:
        raise RuntimeError(
            "Viewer port is present but did not answer; direct mode is blocked"
        ) from error
    except (HTTPError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Viewer health check failed: {error}") from error


def select_mode(health: dict | None) -> str:
    if health is None:
        return "direct"
    if health.get("connected") is True and health.get("control_state") == "DISARMED":
        return "viewer"
    raise RuntimeError(
        "Viewer must be connected and DISARMED before preset positioning; "
        f"current state is {health.get('control_state')!r}"
    )


def run_viewer_pose(
    preset: Preset,
    base_url: str,
    emit: Callable[[str], None] = print,
    emit_error: Callable[[str], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    report_error = emit_error or (lambda message: print(message, file=sys.stderr))
    pose = preset.value.lower()
    try:
        response = request_json(
            base_url,
            f"/api/control/{pose}",
            method="POST",
            headers=CONTROL_HEADER,
        )
    except HTTPError as error:
        try:
            detail = json.load(error).get("detail", error.reason)
        except (json.JSONDecodeError, AttributeError):
            detail = error.reason
        report_error(f"{preset.value} request rejected (HTTP {error.code}): {detail}")
        return 1
    except TimeoutError:
        report_error(
            f"{preset.value} request timed out before Viewer confirmed the transition."
        )
        report_error(
            "Do not retry until Dashboard or /api/health confirms the control state."
        )
        return 1
    except URLError as error:
        report_error(f"Lost Viewer connection: {error.reason}")
        return 1

    if response.get("state") != "POSITIONING" or response.get("preset") != preset:
        report_error(
            f"{preset.value} request returned unexpected state/preset "
            f"{response.get('state')!r}/{response.get('preset')!r}."
        )
        return 1
    target = response.get("targets")
    if not isinstance(target, list) or len(target) != 6:
        report_error(
            f"{preset.value} request did not return a valid six-channel target."
        )
        return 1

    emit(f"{preset.value} positioning started: {target}")
    emit("Use Dashboard E-STOP or physical power removal for an unsafe move.")
    started_at = time.monotonic()
    next_progress_at = started_at + 1.0
    while time.monotonic() - started_at < 25.0:
        try:
            state = request_json(base_url, "/api/health").get("control_state")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            report_error(f"Lost Viewer connection while positioning: {error}")
            return 1
        if state == "DISARMED":
            emit(f"{preset.value} pose reached; controller is DISARMED.")
            return 0
        if state in TERMINAL_STATES:
            report_error(f"{preset.value} failed: controller entered {state}.")
            return 1
        if state != "POSITIONING":
            report_error(
                f"{preset.value} failed: unexpected controller state {state!r}."
            )
            return 1
        now = time.monotonic()
        if now >= next_progress_at:
            emit(f"{preset.value} in progress... {int(now - started_at)}s")
            next_progress_at += 1.0
        sleep(0.2)
    report_error(f"{preset.value} failed: Viewer did not finish within 25 seconds.")
    return 1


def run_direct_pose(
    preset: Preset,
    controller: VisionHandController | None = None,
    emit: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    active_controller = controller or VisionHandController(start_worker=False)
    emit("Viewer is not running; using DIRECT MODBUS control.")
    emit("Keep physical power removal accessible. Ctrl+C will hold current position.")
    try:
        active_controller.start()
        snapshot = active_controller.snapshot()
        if not snapshot.connected or snapshot.state is not ControlState.DISARMED:
            raise RuntimeError(snapshot.error or "Unable to connect to RH56")
        snapshot = active_controller.move_to_preset(preset)
        emit(f"{preset.value} positioning started: {snapshot.targets}")
        started_at = time.monotonic()
        next_progress_at = started_at + 1.0
        while True:
            snapshot = active_controller.tick()
            if snapshot.state is ControlState.DISARMED:
                emit(f"{preset.value} pose reached; controller is DISARMED.")
                return 0
            if snapshot.state in {ControlState.FAULT, ControlState.ESTOPPED}:
                emit(
                    f"{preset.value} failed: controller entered "
                    f"{snapshot.state.value}: {snapshot.error or 'no detail'}"
                )
                return 1
            if snapshot.state is not ControlState.POSITIONING:
                raise RuntimeError(
                    f"Unexpected direct control state {snapshot.state.value}"
                )
            now = time.monotonic()
            if now >= next_progress_at:
                emit(
                    f"{preset.value} in progress... {int(now - started_at)}s "
                    f"actual={snapshot.actual}"
                )
                next_progress_at += 1.0
            sleep(active_controller.period)
    except KeyboardInterrupt:
        if active_controller.snapshot().state is ControlState.POSITIONING:
            try:
                active_controller.estop()
            except Exception as error:
                emit(f"Failed to hold after interrupt: {error}")
        emit("Interrupted; current position was held before disconnecting.")
        return 130
    except Exception as error:
        emit(f"Direct Modbus control failed: {error}")
        return 1
    finally:
        active_controller.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="go_pose.sh")
    parser.add_argument("pose", choices=("home", "open"))
    parser.add_argument("--viewer-url", default="http://127.0.0.1:8787")
    args = parser.parse_args(argv)
    preset = Preset(args.pose.upper())
    base_url = args.viewer_url.rstrip("/")
    try:
        mode = select_mode(probe_viewer(base_url))
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    if mode == "viewer":
        return run_viewer_pose(preset, base_url)
    return run_direct_pose(preset)


if __name__ == "__main__":
    raise SystemExit(main())
