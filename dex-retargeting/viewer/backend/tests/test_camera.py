import time

import numpy as np

from viewer.backend.camera import CameraWorker, LatestFrameStore
from viewer.backend.realsense_bridge import RealSenseBridgeWorker
from viewer.backend.runtime import ViewerRuntime


class FakeCapture:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        try:
            return True, next(self.frames)
        except StopIteration:
            time.sleep(0.005)
            return False, None

    def set(self, *_args):
        return True

    def release(self):
        self.released = True


def test_latest_frame_store_replaces_old_frame():
    store = LatestFrameStore()
    store.put(np.zeros((2, 3, 3), dtype=np.uint8), b"first", 1.0, 10.0)
    store.put(np.ones((2, 3, 3), dtype=np.uint8), b"second", 2.0, 20.0)

    packet = store.latest()

    assert packet is not None
    assert packet.sequence == 2
    assert packet.jpeg == b"second"
    assert packet.capture_fps == 20.0


def test_camera_worker_mirrors_d435_frame_without_rotating_it():
    frame = np.array(
        [
            [[1, 0, 0], [2, 0, 0], [3, 0, 0]],
            [[4, 0, 0], [5, 0, 0], [6, 0, 0]],
        ],
        dtype=np.uint8,
    )
    capture = FakeCapture([frame])
    store = LatestFrameStore()
    worker = CameraWorker(store, capture_factory=lambda _index: capture)

    worker.start()
    packet = store.wait_for_new(0, timeout=1.0)

    assert worker.connected

    worker.stop()

    assert packet is not None
    assert packet.frame[:, :, 0].tolist() == [[3, 2, 1], [6, 5, 4]]
    assert capture.released
    assert not worker.is_alive
    assert not worker.connected


def test_camera_worker_rotates_clockwise_before_mirroring():
    frame = np.array(
        [
            [[1, 0, 0], [2, 0, 0], [3, 0, 0]],
            [[4, 0, 0], [5, 0, 0], [6, 0, 0]],
        ],
        dtype=np.uint8,
    )
    capture = FakeCapture([frame])
    store = LatestFrameStore()
    worker = CameraWorker(
        store,
        rotation=90,
        capture_factory=lambda _index: capture,
    )

    worker.start()
    packet = store.wait_for_new(0, timeout=1.0)
    worker.stop()

    assert packet is not None
    assert packet.frame[:, :, 0].tolist() == [[1, 4], [2, 5], [3, 6]]


def test_camera_worker_rejects_unknown_rotation():
    store = LatestFrameStore()

    try:
        CameraWorker(store, rotation=45)
    except ValueError as error:
        assert "rotation" in str(error)
    else:
        raise AssertionError("Expected invalid camera rotation to be rejected")


def test_runtime_uses_avfoundation_by_default(monkeypatch):
    monkeypatch.delenv("D435_CAMERA_SOURCE", raising=False)
    monkeypatch.setenv("D435_CAMERA_INDEX", "2")

    runtime = ViewerRuntime(
        retargeter=object(),
        tracker=object(),
        controller=object(),
        start_workers=False,
    )

    assert isinstance(runtime.camera, CameraWorker)
    assert runtime.camera.camera_index == 2


def test_runtime_keeps_explicit_realsense_bridge(monkeypatch):
    monkeypatch.setenv("D435_CAMERA_SOURCE", "realsense")
    monkeypatch.setenv("D435_BRIDGE_SOCKET", "/tmp/runtime-rgb.sock")

    runtime = ViewerRuntime(
        retargeter=object(),
        tracker=object(),
        controller=object(),
        start_workers=False,
    )

    assert isinstance(runtime.camera, RealSenseBridgeWorker)
    assert runtime.camera.socket_path == "/tmp/runtime-rgb.sock"


def test_runtime_rejects_unknown_camera_source(monkeypatch):
    monkeypatch.setenv("D435_CAMERA_SOURCE", "phone")

    try:
        ViewerRuntime(
            retargeter=object(),
            tracker=object(),
            controller=object(),
            start_workers=False,
        )
    except ValueError as error:
        assert "D435_CAMERA_SOURCE" in str(error)
    else:
        raise AssertionError("Expected unknown camera source to be rejected")
