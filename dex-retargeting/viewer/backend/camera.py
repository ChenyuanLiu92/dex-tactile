from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import cv2
import numpy as np


@dataclass(frozen=True)
class FramePacket:
    sequence: int
    frame: np.ndarray
    jpeg: bytes
    captured_at: float
    capture_fps: float


class LatestFrameStore:
    def __init__(self):
        self._condition = threading.Condition()
        self._packet: FramePacket | None = None
        self._sequence = 0

    def put(
        self, frame: np.ndarray, jpeg: bytes, captured_at: float, capture_fps: float
    ) -> FramePacket:
        with self._condition:
            self._sequence += 1
            self._packet = FramePacket(
                self._sequence, frame, jpeg, captured_at, capture_fps
            )
            self._condition.notify_all()
            return self._packet

    def latest(self) -> FramePacket | None:
        with self._condition:
            return self._packet

    def wait_for_new(self, sequence: int, timeout: float = 1.0) -> FramePacket | None:
        with self._condition:
            self._condition.wait_for(
                lambda: self._packet is not None and self._packet.sequence > sequence,
                timeout=timeout,
            )
            if self._packet is None or self._packet.sequence <= sequence:
                return None
            return self._packet


class VideoCapture(Protocol):
    def isOpened(self) -> bool: ...

    def set(self, propId: int, value: float) -> bool: ...

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...


CaptureFactory = Callable[[int], VideoCapture]


def orient_frame(frame: np.ndarray, rotation: int) -> np.ndarray:
    if rotation == 90:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == 180:
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    elif rotation == 270:
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return cv2.flip(frame, 1)


def _open_avfoundation(index: int) -> VideoCapture:
    return cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)


class CameraWorker:
    source = "avfoundation"

    def __init__(
        self,
        store: LatestFrameStore,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        rotation: int = 0,
        capture_factory: CaptureFactory = _open_avfoundation,
        on_error: Callable[[str], None] | None = None,
    ):
        self.store = store
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        if rotation not in {0, 90, 180, 270}:
            raise ValueError("rotation must be one of 0, 90, 180, or 270 degrees")
        self.rotation = rotation
        self.capture_factory = capture_factory
        self.on_error = on_error
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def connected(self) -> bool:
        return self._connected_event.is_set()

    def start(self) -> None:
        if self.is_alive:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop, name="d435-capture", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _capture_loop(self) -> None:
        capture = self.capture_factory(self.camera_index)
        try:
            if not capture.isOpened():
                self._report_error(f"Camera index {self.camera_index} did not open")
                return
            self._connected_event.set()
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.fps)
            last_capture = 0.0
            smoothed_fps = 0.0
            consecutive_failures = 0
            while not self._stop_event.is_set():
                ok, raw_frame = capture.read()
                now = time.time()
                if not ok or raw_frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= 30:
                        self._report_error("Camera stopped returning frames")
                        return
                    time.sleep(0.005)
                    continue
                consecutive_failures = 0
                frame = self._orient(raw_frame)
                ok, encoded = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82]
                )
                if not ok:
                    continue
                instantaneous = 0.0 if last_capture == 0 else 1.0 / (now - last_capture)
                smoothed_fps = (
                    instantaneous
                    if smoothed_fps == 0
                    else 0.9 * smoothed_fps + 0.1 * instantaneous
                )
                last_capture = now
                self.store.put(frame, encoded.tobytes(), now, smoothed_fps)
        finally:
            self._connected_event.clear()
            capture.release()

    def _report_error(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)

    def _orient(self, frame: np.ndarray) -> np.ndarray:
        return orient_frame(frame, self.rotation)
