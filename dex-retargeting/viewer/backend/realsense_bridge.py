from __future__ import annotations

import struct
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from .camera import LatestFrameStore, orient_frame


BRIDGE_MAGIC = b"DRGB"
BRIDGE_VERSION = 1
HEADER_STRUCT = struct.Struct("!4sB3xQQI")
MAX_JPEG_BYTES = 8 * 1024 * 1024


class ReadableStream(Protocol):
    def recv(self, size: int, /) -> bytes: ...


class BridgeProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeFrame:
    sequence: int
    captured_at: float
    jpeg: bytes


def _read_exact(stream: ReadableStream, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise BridgeProtocolError("Bridge connection closed during frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_bridge_frame(stream: ReadableStream) -> BridgeFrame:
    header = _read_exact(stream, HEADER_STRUCT.size)
    magic, version, sequence, captured_ns, payload_size = HEADER_STRUCT.unpack(header)
    if magic != BRIDGE_MAGIC:
        raise BridgeProtocolError("Invalid bridge frame magic")
    if version != BRIDGE_VERSION:
        raise BridgeProtocolError(f"Unsupported bridge protocol version {version}")
    if payload_size == 0 or payload_size > MAX_JPEG_BYTES:
        raise BridgeProtocolError(f"Invalid bridge payload size {payload_size}")
    payload = _read_exact(stream, payload_size)
    return BridgeFrame(sequence, captured_ns / 1_000_000_000, payload)


def decode_bridge_jpeg(payload: bytes) -> np.ndarray:
    frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise BridgeProtocolError("Bridge payload is not a valid JPEG frame")
    return frame


class RealSenseBridgeWorker:
    source = "realsense"

    def __init__(
        self,
        store: LatestFrameStore,
        socket_path: str | Path,
        rotation: int = 0,
        retry_interval: float = 0.1,
        connect_timeout: float = 0.25,
        frame_timeout: float = 1.0,
        error_after: float = 1.0,
        on_error=None,
    ):
        if rotation not in {0, 90, 180, 270}:
            raise ValueError("rotation must be one of 0, 90, 180, or 270 degrees")
        self.store = store
        self.socket_path = str(socket_path)
        self.rotation = rotation
        self.retry_interval = retry_interval
        self.connect_timeout = connect_timeout
        self.frame_timeout = frame_timeout
        self.error_after = error_after
        self.on_error = on_error
        self.connected = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_alive:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="realsense-rgb-bridge",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.frame_timeout + 1.0)
        self.connected = False

    def _capture_loop(self) -> None:
        failure_started_at: float | None = None
        error_reported = False
        last_capture = 0.0
        smoothed_fps = 0.0
        while not self._stop_event.is_set():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(self.connect_timeout)
                    connection.connect(self.socket_path)
                    connection.settimeout(self.frame_timeout)
                    self.connected = True
                    while not self._stop_event.is_set():
                        bridge_frame = read_bridge_frame(connection)
                        frame = orient_frame(
                            decode_bridge_jpeg(bridge_frame.jpeg), self.rotation
                        )
                        ok, encoded = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82]
                        )
                        if not ok:
                            raise BridgeProtocolError(
                                "Could not encode oriented bridge JPEG frame"
                            )
                        now = time.time()
                        instantaneous = (
                            0.0 if last_capture == 0 else 1.0 / (now - last_capture)
                        )
                        smoothed_fps = (
                            instantaneous
                            if smoothed_fps == 0
                            else 0.9 * smoothed_fps + 0.1 * instantaneous
                        )
                        last_capture = now
                        self.store.put(
                            frame,
                            encoded.tobytes(),
                            bridge_frame.captured_at,
                            smoothed_fps,
                        )
                        failure_started_at = None
                        error_reported = False
            except (OSError, BridgeProtocolError) as error:
                self.connected = False
                now = time.monotonic()
                if failure_started_at is None:
                    failure_started_at = now
                if (
                    not error_reported
                    and now - failure_started_at >= self.error_after
                ):
                    self._report_error(f"RealSense RGB bridge unavailable: {error}")
                    error_reported = True
                self._stop_event.wait(self.retry_interval)

    def _report_error(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)
