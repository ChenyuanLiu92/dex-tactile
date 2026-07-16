import time

import numpy as np

from viewer.backend.camera import CameraWorker, LatestFrameStore


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
    worker.stop()

    assert packet is not None
    assert packet.frame[:, :, 0].tolist() == [[3, 2, 1], [6, 5, 4]]
    assert capture.released
    assert not worker.is_alive
