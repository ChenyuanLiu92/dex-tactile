import struct
import socket
import threading
import time
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from viewer.backend.camera import LatestFrameStore
from viewer.backend.realsense_bridge import (
    HEADER_STRUCT,
    MAX_JPEG_BYTES,
    BridgeProtocolError,
    RealSenseBridgeWorker,
    decode_bridge_jpeg,
    read_bridge_frame,
)


class FragmentedStream:
    def __init__(self, data: bytes, fragment_size: int = 3):
        self.data = data
        self.fragment_size = fragment_size

    def recv(self, size: int) -> bytes:
        if not self.data:
            return b""
        count = min(size, self.fragment_size, len(self.data))
        chunk, self.data = self.data[:count], self.data[count:]
        return chunk


def bridge_message(
    payload: bytes,
    *,
    magic: bytes = b"DRGB",
    version: int = 1,
    sequence: int = 7,
    captured_ns: int = 1_234_000_000,
    declared_size: int | None = None,
) -> bytes:
    size = len(payload) if declared_size is None else declared_size
    return HEADER_STRUCT.pack(magic, version, sequence, captured_ns, size) + payload


def test_read_bridge_frame_accepts_fragmented_header_and_payload():
    stream = FragmentedStream(bridge_message(b"jpeg-data"), fragment_size=2)

    frame = read_bridge_frame(stream)

    assert frame.sequence == 7
    assert frame.captured_at == pytest.approx(1.234)
    assert frame.jpeg == b"jpeg-data"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (bridge_message(b"x", magic=b"NOPE"), "magic"),
        (bridge_message(b"x", version=2), "version"),
        (
            bridge_message(b"", declared_size=MAX_JPEG_BYTES + 1),
            "payload size",
        ),
    ],
)
def test_read_bridge_frame_rejects_invalid_header(message: bytes, expected: str):
    with pytest.raises(BridgeProtocolError, match=expected):
        read_bridge_frame(FragmentedStream(message))


def test_read_bridge_frame_rejects_truncated_payload():
    message = bridge_message(b"short", declared_size=10)

    with pytest.raises(BridgeProtocolError, match="closed"):
        read_bridge_frame(FragmentedStream(message))


def test_read_bridge_frame_rejects_truncated_header():
    message = struct.pack("!4sB", b"DRGB", 1)

    with pytest.raises(BridgeProtocolError, match="closed"):
        read_bridge_frame(FragmentedStream(message))


def test_decode_bridge_jpeg_rejects_invalid_payload():
    with pytest.raises(BridgeProtocolError, match="JPEG"):
        decode_bridge_jpeg(b"not-a-jpeg")


def encode_frame(frame: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
    assert ok
    return encoded.tobytes()


def serve_connections(path: Path, messages: list[bytes]) -> threading.Thread:
    ready = threading.Event()

    def run():
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        server.listen(1)
        server.settimeout(2.0)
        ready.set()
        try:
            for message in messages:
                connection, _ = server.accept()
                with connection:
                    connection.sendall(message)
        finally:
            server.close()
            path.unlink(missing_ok=True)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(1.0)
    return thread


@pytest.fixture
def socket_path():
    directory = Path(tempfile.mkdtemp(prefix="dex-rgb-", dir="/tmp"))
    path = directory / "rgb.sock"
    yield path
    path.unlink(missing_ok=True)
    directory.rmdir()


def test_bridge_worker_publishes_oriented_frame(socket_path: Path):
    frame = np.full((40, 60, 3), 20, dtype=np.uint8)
    frame[:, 30:, :] = 200
    server = serve_connections(
        socket_path,
        [bridge_message(encode_frame(frame), sequence=1, captured_ns=time.time_ns())],
    )
    store = LatestFrameStore()
    worker = RealSenseBridgeWorker(store, socket_path=socket_path, rotation=90)

    worker.start()
    packet = store.wait_for_new(0, timeout=2.0)
    worker.stop()
    server.join(timeout=2.0)

    assert packet is not None
    assert packet.frame.shape == (60, 40, 3)
    assert float(packet.frame[:25].mean()) == pytest.approx(20, abs=3)
    assert float(packet.frame[35:].mean()) == pytest.approx(200, abs=3)
    assert not worker.is_alive


def test_bridge_worker_reconnects_after_server_closes_connection(socket_path: Path):
    first = np.full((3, 3, 3), 25, dtype=np.uint8)
    second = np.full((3, 3, 3), 175, dtype=np.uint8)
    server = serve_connections(
        socket_path,
        [
            bridge_message(encode_frame(first), sequence=1, captured_ns=time.time_ns()),
            bridge_message(encode_frame(second), sequence=2, captured_ns=time.time_ns()),
        ],
    )
    store = LatestFrameStore()
    worker = RealSenseBridgeWorker(
        store,
        socket_path=socket_path,
        retry_interval=0.01,
    )

    worker.start()
    first_packet = store.wait_for_new(0, timeout=2.0)
    second_packet = store.wait_for_new(
        0 if first_packet is None else first_packet.sequence,
        timeout=2.0,
    )
    worker.stop()
    server.join(timeout=2.0)

    assert first_packet is not None
    assert second_packet is not None
    assert float(second_packet.frame.mean()) == pytest.approx(175, abs=3)


def test_bridge_worker_reports_missing_socket(socket_path: Path):
    errors: list[str] = []
    worker = RealSenseBridgeWorker(
        LatestFrameStore(),
        socket_path=socket_path,
        retry_interval=0.01,
        error_after=0.03,
        on_error=errors.append,
    )

    worker.start()
    deadline = time.monotonic() + 1.0
    while not errors and time.monotonic() < deadline:
        time.sleep(0.01)
    worker.stop()

    assert errors
    assert "bridge" in errors[0].lower()
