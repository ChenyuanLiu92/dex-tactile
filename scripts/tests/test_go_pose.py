from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = WORKSPACE_ROOT / "scripts" / "go_pose.sh"
OLD_SCRIPT = WORKSPACE_ROOT / "scripts" / "go_home.sh"
TARGETS = {
    "home": [120, 120, 120, 120, 180, 480],
    "open": [1000] * 6,
}


@contextmanager
def fake_viewer(
    preset,
    states,
    reject=False,
    preflight_state="DISARMED",
    post_delay=0.0,
):
    requests = []
    health_states = iter(states)
    current_state = "POSITIONING"
    posted = False

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            nonlocal posted
            posted = True
            requests.append((self.path, self.headers.get("X-RH56-Control")))
            if post_delay:
                time.sleep(post_delay)
            if reject:
                self._json(409, {"detail": "Expected DISARMED"})
                return
            self._json(
                200,
                {
                    "state": "POSITIONING",
                    "preset": preset.upper(),
                    "targets": TARGETS[preset],
                },
            )

        def do_GET(self):
            nonlocal current_state
            if not posted:
                self._json(
                    200,
                    {
                        "control_state": preflight_state,
                        "connected": True,
                    },
                )
                return
            current_state = next(health_states, current_state)
            self._json(
                200,
                {"control_state": current_state, "connected": True},
            )

        def _json(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def run_script(url, *arguments):
    environment = os.environ | {
        "RH56_VIEWER_URL": url,
        "VIRTUAL_ENV": str(WORKSPACE_ROOT / ".venv"),
    }
    return subprocess.run(
        [str(SCRIPT), *arguments],
        cwd=WORKSPACE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("preset", ["home", "open"])
def test_go_pose_uses_fixed_route_and_waits_for_disarmed(preset):
    with fake_viewer(preset, ["POSITIONING"] * 6 + ["DISARMED"]) as (
        url,
        requests,
    ):
        result = run_script(url, preset)

    assert result.returncode == 0
    assert requests == [(f"/api/control/{preset}", "operator-confirmed")]
    assert f"{preset.upper()} positioning started: {TARGETS[preset]}" in result.stdout
    assert f"{preset.upper()} in progress" in result.stdout
    assert f"{preset.upper()} pose reached; controller is DISARMED." in result.stdout
    assert "does not match the project environment" not in result.stderr


@pytest.mark.parametrize("arguments", [(), ("close",), ("home", "open")])
def test_go_pose_rejects_missing_unknown_or_extra_arguments(arguments):
    result = run_script("http://127.0.0.1:1", *arguments)

    assert result.returncode == 2
    assert "Usage: ./scripts/go_pose.sh {home|open}" in result.stderr


def test_go_pose_reports_rejected_transition():
    with fake_viewer("open", [], reject=True) as (url, _requests):
        result = run_script(url, "open")

    assert result.returncode != 0
    assert "OPEN request rejected" in result.stderr


def test_go_pose_reports_terminal_fault_and_replaces_old_script():
    with fake_viewer("home", ["FAULT"]) as (url, _requests):
        result = run_script(url, "home")

    assert result.returncode != 0
    assert "controller entered FAULT" in result.stderr
    assert not OLD_SCRIPT.exists()


def test_go_pose_preflight_rejects_non_disarmed_viewer_without_posting():
    with fake_viewer("home", [], preflight_state="FAULT") as (url, requests):
        result = run_script(url, "home")

    assert result.returncode != 0
    assert requests == []
    assert "Viewer must be connected and DISARMED" in result.stderr


def test_go_pose_reports_ambiguous_post_timeout_without_traceback():
    with fake_viewer("home", [], post_delay=3.0) as (url, requests):
        result = run_script(url, "home")

    assert result.returncode != 0
    assert requests == [("/api/control/home", "operator-confirmed")]
    assert "request timed out before Viewer confirmed" in result.stderr
    assert "Do not retry" in result.stderr
    assert "Traceback" not in result.stderr
