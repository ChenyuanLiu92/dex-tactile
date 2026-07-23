"""Local web control surface for standalone hand teleoperation."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import webbrowser
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TeleopSnapshot:
    """Values published to the live web dashboard."""

    tracking_enabled: bool
    motion_data_ready: bool
    loop_hz: float
    elapsed_seconds: float
    left_enabled: bool
    right_enabled: bool
    left_state: tuple[float, ...]
    right_state: tuple[float, ...]
    left_target: tuple[float, ...]
    right_target: tuple[float, ...]
    speed_mode: str = "adaptive_v2"
    motion_filter_enabled: bool = False
    left_speed: tuple[float, ...] = ()
    right_speed: tuple[float, ...] = ()
    modules: dict[str, dict[str, Any]] = field(default_factory=dict)
    tactile: dict[str, Any] = field(default_factory=dict)


class _WebLogHandler(logging.Handler):
    def __init__(self, web_ui: "HandTeleoperationWebUI") -> None:
        super().__init__()
        self._web_ui = web_ui

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._web_ui.add_message(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)


class _WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler, web_ui: "HandTeleoperationWebUI") -> None:
        self.web_ui = web_ui
        super().__init__(server_address, handler)


class _TactileCaptureSession:
    """Pace tactile snapshots and stream them to a JSON Lines file."""

    FORMAT_NAME = "inspire-tactile-jsonl"
    FORMAT_VERSION = 1

    def __init__(
        self,
        *,
        path: Path,
        sides: tuple[str, ...],
        frequency_hz: float,
        duration_seconds: float,
    ) -> None:
        self.path = path
        self.sides = sides
        self.frequency_hz = frequency_hz
        self.duration_seconds = duration_seconds
        self._lock = threading.Lock()
        self._records: queue.Queue[dict[str, Any]] = queue.Queue(
            maxsize=max(64, int(frequency_hz * 4))
        )
        self._started_monotonic = time.monotonic()
        self._started_at = datetime.now().astimezone()
        self._deadline = self._started_monotonic + duration_seconds
        self._next_sample_at = self._started_monotonic
        self._last_revisions: tuple[int, ...] | None = None
        self._enqueued_count = 0
        self._sample_count = 0
        self._dropped_count = 0
        self._state = "recording"
        self._error = ""
        self._stop_reason = ""
        self._file = path.open("x", encoding="utf-8", buffering=1)
        self._thread = threading.Thread(
            target=self._write_loop,
            name="tactile-jsonl-writer",
            daemon=True,
        )
        self._thread.start()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._state in {"recording", "stopping"}

    def enqueue(self, tactile: dict[str, Any]) -> None:
        now = time.monotonic()
        hands = tactile.get("hands", {}) if isinstance(tactile, dict) else {}
        with self._lock:
            if self._state != "recording" or now >= self._deadline:
                return
            selected = [hands.get(side, {}) for side in self.sides]
            if any(not hand.get("regions") for hand in selected):
                return
            revisions = tuple(int(hand.get("revision", 0)) for hand in selected)
            if revisions == self._last_revisions or now < self._next_sample_at:
                return
            sequence = self._enqueued_count
            self._enqueued_count += 1
            self._last_revisions = revisions
            self._next_sample_at = now + 1.0 / self.frequency_hz
            record = {
                "type": "sample",
                "sequence": sequence,
                "captured_at": datetime.now().astimezone().isoformat(
                    timespec="milliseconds"
                ),
                "elapsed_seconds": round(now - self._started_monotonic, 6),
                "hands": {
                    side: {
                        "revision": revisions[index],
                        "regions": selected[index]["regions"],
                        **(
                            {
                                "forces": selected[index]["forces"],
                                "force_age_seconds": selected[index].get(
                                    "force_age_seconds"
                                ),
                            }
                            if selected[index].get("forces")
                            else {}
                        ),
                    }
                    for index, side in enumerate(self.sides)
                },
            }
        try:
            self._records.put_nowait(record)
        except queue.Full:
            with self._lock:
                self._dropped_count += 1

    def stop(self, reason: str = "") -> None:
        with self._lock:
            if self._state != "recording":
                return
            self._state = "stopping"
            self._stop_reason = reason

    def join(self, timeout: float = 2.0) -> None:
        self._thread.join(timeout)

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            state = self._state
            elapsed = max(0.0, now - self._started_monotonic)
            if state not in {"recording", "stopping"}:
                elapsed = min(elapsed, self.duration_seconds)
            return {
                "state": state,
                "format": self.FORMAT_NAME,
                "format_version": self.FORMAT_VERSION,
                "path": str(self.path),
                "sides": list(self.sides),
                "frequency_hz": self.frequency_hz,
                "duration_seconds": self.duration_seconds,
                "elapsed_seconds": min(elapsed, self.duration_seconds),
                "remaining_seconds": max(0.0, self.duration_seconds - elapsed),
                "sample_count": self._sample_count,
                "dropped_count": self._dropped_count,
                "error": self._error,
                "stop_reason": self._stop_reason,
            }

    def _write_loop(self) -> None:
        final_state = "completed"
        try:
            metadata = {
                "type": "metadata",
                "format": self.FORMAT_NAME,
                "version": self.FORMAT_VERSION,
                "started_at": self._started_at.isoformat(timespec="milliseconds"),
                "frequency_hz": self.frequency_hz,
                "duration_seconds": self.duration_seconds,
                "sides": list(self.sides),
                "value_range": [0, 4095],
            }
            self._file.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            while True:
                now = time.monotonic()
                with self._lock:
                    stopping = self._state == "stopping"
                expired = now >= self._deadline
                if (stopping or expired) and self._records.empty():
                    final_state = "stopped" if stopping else "completed"
                    break
                try:
                    record = self._records.get(
                        timeout=max(0.01, min(0.2, self._deadline - now))
                    )
                except queue.Empty:
                    continue
                self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
                with self._lock:
                    self._sample_count += 1
            with self._lock:
                summary = {
                    "type": "summary",
                    "ended_at": datetime.now().astimezone().isoformat(
                        timespec="milliseconds"
                    ),
                    "state": final_state,
                    "sample_count": self._sample_count,
                    "dropped_count": self._dropped_count,
                    "stop_reason": self._stop_reason,
                }
            self._file.write(json.dumps(summary, ensure_ascii=False) + "\n")
        except Exception as error:
            final_state = "error"
            with self._lock:
                self._error = str(error)
        finally:
            try:
                self._file.flush()
                self._file.close()
            except Exception as error:
                final_state = "error"
                with self._lock:
                    if not self._error:
                        self._error = str(error)
            with self._lock:
                self._state = final_state


class _RequestHandler(BaseHTTPRequestHandler):
    server: _WebServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/api/state":
            self._json(HTTPStatus.OK, self.server.web_ui.state_payload())
            return
        asset = self.server.web_ui.asset(self.path)
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content, content_type = asset
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            payload = self._read_json()
            if self.path == "/api/setup":
                config = self.server.web_ui.submit_setup(payload)
                self._json(HTTPStatus.ACCEPTED, {"ok": True, "config": config})
            elif self.path == "/api/action":
                action = self.server.web_ui.submit_action(payload.get("action"))
                self._json(HTTPStatus.ACCEPTED, {"ok": True, "action": action})
            elif self.path == "/api/tactile":
                sides = self.server.web_ui.submit_tactile_selection(
                    payload.get("sides")
                )
                self._json(HTTPStatus.ACCEPTED, {"ok": True, "sides": sides})
            elif self.path == "/api/tactile/capture":
                capture = self.server.web_ui.submit_tactile_capture(payload)
                self._json(HTTPStatus.ACCEPTED, {"ok": True, "capture": capture})
            elif self.path == "/api/calibration/ack":
                calibration = self.server.web_ui.acknowledge_calibration()
                self._json(HTTPStatus.OK, {"ok": True, "calibration": calibration})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (OSError, TypeError, ValueError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(error)})

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length <= 0 or length > 32_768:
            raise ValueError("Request body must contain 1..32768 bytes")
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Request body is not valid JSON") from error
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        return payload

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, _format: str, *args: Any) -> None:
        """Keep high-frequency polling out of the application log."""


class HandTeleoperationWebUI:
    """Serve configuration, telemetry, and controls from a local web page."""

    _ASSETS = {
        "/": ("index.html", "text/html; charset=utf-8"),
        "/index.html": ("index.html", "text/html; charset=utf-8"),
        "/app.css": ("app.css", "text/css; charset=utf-8"),
        "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    }
    _ACTIONS = {
        "run",
        "pause",
        "speed_mode",
        "motion_filter",
        "calibrate_force",
        "disconnect",
        "quit",
    }

    def __init__(self, args) -> None:
        self.host = args.web_host
        self.port = args.web_port
        self.language = args.language
        self._assets_dir = Path(__file__).with_name("web")
        self._condition = threading.Condition()
        self._phase = "setup"
        self._detail = ""
        self._setup_config = self._config_from_args(args)
        self._pending_setup: dict[str, Any] | None = None
        self._actions: deque[str] = deque()
        self._messages: deque[dict[str, str]] = deque(maxlen=300)
        self._snapshot: TeleopSnapshot | None = None
        self._tactile_selection: tuple[str, ...] = ()
        self._pending_tactile_selection: tuple[str, ...] | None = None
        self._tactile_capture: _TactileCaptureSession | None = None
        self._calibration: dict[str, str] = {"state": "idle", "detail": ""}
        self._server: _WebServer | None = None
        self._thread: threading.Thread | None = None
        self._log_handler = _WebLogHandler(self)

    @staticmethod
    def _config_from_args(args) -> dict[str, Any]:
        speed_mode = "adaptive_v2" if args.speed_mode == "adaptive" else args.speed_mode
        return {
            "left_enabled": bool(args.left_hand_host),
            "left_host": args.left_hand_host or "192.168.11.211",
            "left_device_id": args.left_device_id,
            "right_enabled": bool(args.right_hand_host),
            "right_host": args.right_hand_host or "192.168.11.210",
            "right_device_id": args.right_device_id,
            "modbus_port": args.modbus_port,
            "modbus_timeout": args.modbus_timeout,
            "target_speed": args.target_speed,
            "speed_mode": speed_mode,
            "frequency": args.frequency,
            "hand_frequency": args.hand_frequency,
            "tactile_frequency": args.tactile_frequency,
            "start": args.start,
            "open_on_exit": args.open_on_exit,
            "hide_hand_markers": args.hide_hand_markers,
        }

    @property
    def url(self) -> str:
        display_host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return f"http://{display_host}:{self.port}"

    def start(self, open_browser: bool = True) -> None:
        self._server = _WebServer((self.host, self.port), _RequestHandler, self)
        self.port = self._server.server_port
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="hand-teleoperation-web",
            daemon=True,
        )
        self._thread.start()
        logging.getLogger().addHandler(self._log_handler)
        if open_browser:
            threading.Thread(target=webbrowser.open, args=(self.url,), daemon=True).start()

    def stop(self) -> None:
        logging.getLogger().removeHandler(self._log_handler)
        self._stop_tactile_capture("Control service stopped")
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def asset(self, path: str) -> tuple[bytes, str] | None:
        descriptor = self._ASSETS.get(path.split("?", 1)[0])
        if descriptor is None:
            return None
        filename, content_type = descriptor
        return (self._assets_dir.joinpath(filename).read_bytes(), content_type)

    @staticmethod
    def validate_setup(payload: dict[str, Any]) -> dict[str, Any]:
        required = {
            "left_enabled", "left_host", "left_device_id", "right_enabled",
            "right_host", "right_device_id", "modbus_port", "modbus_timeout",
            "target_speed", "speed_mode", "frequency", "hand_frequency",
            "tactile_frequency",
            "start", "open_on_exit", "hide_hand_markers", "safety_confirmed",
        }
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Missing setup field: {sorted(missing)[0]}")

        def boolean(name: str) -> bool:
            value = payload[name]
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a boolean")
            return value

        def integer(name: str, minimum: int, maximum: int) -> int:
            value = payload[name]
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
            return value

        def number(name: str) -> float:
            value = payload[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{name} must be a positive number")
            return float(value)

        left_enabled = boolean("left_enabled")
        right_enabled = boolean("right_enabled")
        if not left_enabled and not right_enabled:
            raise ValueError("At least one hand must be enabled")
        if not boolean("safety_confirmed"):
            raise ValueError("Confirm that the hand workspace is clear before connecting")

        def host(name: str, enabled: bool) -> str:
            value = payload[name]
            if not isinstance(value, str):
                raise TypeError(f"{name} must be text")
            value = value.strip()
            if enabled and not value:
                raise ValueError(f"{name} cannot be empty when the hand is enabled")
            if len(value) > 253 or any(character.isspace() for character in value):
                raise ValueError(f"{name} is not a valid host name or address")
            return value

        speed_mode = payload["speed_mode"]
        if speed_mode == "adaptive":
            speed_mode = "adaptive_v2"
        if speed_mode not in ("adaptive_v2", "adaptive_v1", "fixed"):
            raise ValueError(
                "speed_mode must be adaptive_v2, adaptive_v1, adaptive, or fixed"
            )
        left_host = host("left_host", left_enabled)
        right_host = host("right_host", right_enabled)
        if (
            left_enabled
            and right_enabled
            and left_host.casefold() == right_host.casefold()
        ):
            raise ValueError("Left and right hands must use different host addresses")
        tactile_frequency = number("tactile_frequency")
        if tactile_frequency > 60:
            raise ValueError("tactile_frequency must be in the range 1..60")
        return {
            "left_enabled": left_enabled,
            "left_host": left_host,
            "left_device_id": integer("left_device_id", 1, 254),
            "right_enabled": right_enabled,
            "right_host": right_host,
            "right_device_id": integer("right_device_id", 1, 254),
            "modbus_port": integer("modbus_port", 1, 65535),
            "modbus_timeout": number("modbus_timeout"),
            "target_speed": integer("target_speed", 0, 1000),
            "speed_mode": speed_mode,
            "frequency": number("frequency"),
            "hand_frequency": number("hand_frequency"),
            "tactile_frequency": tactile_frequency,
            "start": boolean("start"),
            "open_on_exit": boolean("open_on_exit"),
            "hide_hand_markers": boolean("hide_hand_markers"),
        }

    def submit_setup(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = self.validate_setup(payload)
        with self._condition:
            if self._phase != "setup":
                raise ValueError("Setup has already been submitted")
            self._setup_config = config
            self._pending_setup = config
            self._phase = "connecting"
            self._condition.notify_all()
        return config

    def wait_for_setup(self) -> dict[str, Any] | None:
        with self._condition:
            while self._pending_setup is None and "quit" not in self._actions:
                self._condition.wait(timeout=0.5)
            if "quit" in self._actions:
                return None
            return dict(self._pending_setup or {})

    def submit_action(self, action: Any) -> str:
        if action not in self._ACTIONS:
            raise ValueError(f"Unknown action: {action!r}")
        with self._condition:
            if self._phase == "setup" and action != "quit":
                raise ValueError("Connect the hands before sending controls")
            if action in {
                "run",
                "pause",
                "speed_mode",
                "motion_filter",
                "calibrate_force",
            } and self._phase != "live":
                raise ValueError("Hand controls are available only while connected")
            if action == "disconnect" and self._phase not in {
                "connecting", "live", "error"
            }:
                raise ValueError("There is no active device session to disconnect")
            if action == "calibrate_force":
                if self._calibration["state"] in {"queued", "running"}:
                    raise ValueError("Force-sensor calibration is already running")
                if self._calibration["state"] in {"completed", "failed"}:
                    raise ValueError(
                        "Acknowledge the previous force-sensor calibration result"
                    )
                self._calibration = {"state": "queued", "detail": ""}
            self._actions.append(action)
            self._condition.notify_all()
        return action

    def poll_action(self) -> str | None:
        with self._condition:
            return self._actions.popleft() if self._actions else None

    def set_calibration_state(self, state: str, detail: str = "") -> None:
        """Publish the asynchronous force-calibration lifecycle to the Web UI."""

        if state not in {"idle", "queued", "running", "completed", "failed"}:
            raise ValueError(f"Unknown calibration state: {state!r}")
        with self._condition:
            self._calibration = {"state": state, "detail": str(detail)}

    def acknowledge_calibration(self) -> dict[str, str]:
        """Clear a terminal calibration result after explicit user confirmation."""

        with self._condition:
            if self._calibration["state"] in {"queued", "running"}:
                raise ValueError("Force-sensor calibration is still running")
            self._calibration = {"state": "idle", "detail": ""}
            return dict(self._calibration)

    def submit_tactile_selection(self, sides: Any) -> list[str]:
        """Select enabled hands for paced tactile sampling."""

        if not isinstance(sides, list) or any(
            side not in {"left", "right"} for side in sides
        ):
            raise ValueError("sides must be a list containing left and/or right")
        if len(sides) != len(set(sides)):
            raise ValueError("sides must not contain duplicates")
        normalized = tuple(side for side in ("left", "right") if side in sides)
        with self._condition:
            if self._phase != "live":
                raise ValueError("Tactile sampling is available only while connected")
            available = tuple(
                side
                for side in ("left", "right")
                if self._setup_config[f"{side}_enabled"]
            )
            if any(side not in available for side in normalized):
                raise ValueError("Cannot sample tactile data from a disabled hand")
            if len(available) == 1 and normalized not in {(), available}:
                raise ValueError("A single-hand session must display its enabled hand")
            if (
                self._tactile_capture is not None
                and self._tactile_capture.active
                and normalized != self._tactile_capture.sides
            ):
                raise ValueError("Stop tactile capture before changing the selected hands")
            self._tactile_selection = normalized
            self._pending_tactile_selection = normalized
            self._condition.notify_all()
        return list(normalized)

    def poll_tactile_selection(self) -> tuple[str, ...] | None:
        with self._condition:
            selection = self._pending_tactile_selection
            self._pending_tactile_selection = None
            return selection

    def submit_tactile_capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        if action == "stop":
            capture = self._tactile_capture
            if capture is None or not capture.active:
                raise ValueError("There is no active tactile capture")
            capture.stop("Stopped by user")
            self.add_message("info", "Tactile capture stop requested.")
            return capture.status()
        if action != "start":
            raise ValueError("Tactile capture action must be start or stop")

        sides = payload.get("sides")
        if not isinstance(sides, list) or not sides or any(
            side not in {"left", "right"} for side in sides
        ):
            raise ValueError("Capture sides must contain left and/or right")
        normalized = tuple(side for side in ("left", "right") if side in sides)
        if len(normalized) != len(sides):
            raise ValueError("Capture sides must be unique")

        frequency = payload.get("frequency_hz")
        duration = payload.get("duration_seconds")
        if isinstance(frequency, bool) or not isinstance(frequency, (int, float)):
            raise TypeError("Capture frequency must be a number")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise TypeError("Capture duration must be a number")
        frequency = float(frequency)
        duration = float(duration)
        if not 0 < frequency <= 60:
            raise ValueError("Capture frequency must be in the range 0..60 Hz")
        if not 0 < duration <= 86_400:
            raise ValueError("Capture duration must be in the range 0..86400 seconds")

        output_path = payload.get("output_path")
        if not isinstance(output_path, str) or not output_path.strip():
            raise ValueError("Capture output path cannot be empty")
        if "\x00" in output_path or len(output_path) > 4096:
            raise ValueError("Capture output path is invalid")

        with self._condition:
            if self._phase != "live":
                raise ValueError("Tactile capture is available only while connected")
            if self._tactile_capture is not None and self._tactile_capture.active:
                raise ValueError("A tactile capture is already running")
            available = tuple(
                side
                for side in ("left", "right")
                if self._setup_config[f"{side}_enabled"]
            )
            if any(side not in available for side in normalized):
                raise ValueError("Cannot capture tactile data from a disabled hand")
            polling_frequency = float(self._setup_config["tactile_frequency"])
            publication_frequency = float(self._setup_config["frequency"])
            maximum_frequency = min(polling_frequency, publication_frequency)
            if frequency > maximum_frequency:
                raise ValueError(
                    "Capture frequency cannot exceed the available tactile data rate "
                    f"({maximum_frequency:g} Hz)"
                )
            path = self._capture_output_path(output_path)
            capture = _TactileCaptureSession(
                path=path,
                sides=normalized,
                frequency_hz=frequency,
                duration_seconds=duration,
            )
            self._tactile_capture = capture
            self._tactile_selection = normalized
            self._pending_tactile_selection = normalized
            self._condition.notify_all()
        self.add_message("info", f"Tactile capture started: {path}")
        return capture.status()

    @staticmethod
    def _capture_output_path(value: str) -> Path:
        requested = Path(value.strip()).expanduser().resolve()
        is_directory = value.rstrip().endswith(("/", "\\")) or (
            requested.exists() and requested.is_dir()
        ) or not requested.suffix
        if is_directory:
            requested.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
            return requested / f"tactile-{stamp}.jsonl"
        if requested.suffix.lower() != ".jsonl":
            raise ValueError("Tactile captures must use the .jsonl extension")
        requested.parent.mkdir(parents=True, exist_ok=True)
        return requested

    def _stop_tactile_capture(self, reason: str) -> None:
        capture = self._tactile_capture
        if capture is None or not capture.active:
            return
        capture.stop(reason)
        capture.join()

    def set_phase(self, phase: str, detail: str = "") -> None:
        if phase != "live":
            self._stop_tactile_capture("Device session ended")
        with self._condition:
            self._phase = phase
            self._detail = detail

    def return_to_setup(self, detail: str = "") -> None:
        """End the current device session while keeping the Web server alive."""

        self._stop_tactile_capture("Device session disconnected")
        with self._condition:
            self._phase = "setup"
            self._detail = detail
            self._pending_setup = None
            self._snapshot = None
            self._tactile_selection = ()
            self._pending_tactile_selection = None
            self._calibration = {"state": "idle", "detail": ""}
            self._actions = deque(
                action for action in self._actions if action == "quit"
            )
            self._condition.notify_all()

    def publish(self, snapshot: TeleopSnapshot) -> None:
        capture = self._tactile_capture
        if capture is not None and capture.active:
            capture.enqueue(snapshot.tactile)
        with self._condition:
            self._snapshot = snapshot

    def add_message(self, level: str, message: str) -> None:
        normalized = " ".join(str(message).split())
        if not normalized:
            return
        item = {
            "level": level.lower(),
            "message": normalized,
            "time": datetime.now().astimezone().strftime("%H:%M:%S"),
        }
        with self._condition:
            previous = self._messages[-1] if self._messages else None
            if previous is None or (
                previous["level"] != item["level"]
                or previous["message"] != item["message"]
            ):
                self._messages.append(item)

    def state_payload(self) -> dict[str, Any]:
        with self._condition:
            return {
                "phase": self._phase,
                "detail": self._detail,
                "language": self.language,
                "config": dict(self._setup_config),
                "snapshot": asdict(self._snapshot) if self._snapshot is not None else None,
                "tactile_selection": list(self._tactile_selection),
                "tactile_capture": (
                    {"state": "idle"}
                    if self._tactile_capture is None
                    else self._tactile_capture.status()
                ),
                "calibration": dict(self._calibration),
                "messages": list(self._messages),
            }
