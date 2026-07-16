import numpy as np
import pytest

from viewer.backend.control.driver import (
    ANGLE_ACT,
    ANGLE_SET,
    FORCE_SET,
    SPEED_SET,
    RH56Driver,
)


class Response:
    def __init__(self, registers=(), error=False):
        self.registers = list(registers)
        self._error = error

    def isError(self):
        return self._error


class FakeClient:
    def __init__(self, positions=(900, 800, 700, 600, 500, 400)):
        self.positions = positions
        self.connected = False
        self.closed = False
        self.reads = []
        self.writes = []

    def connect(self):
        self.connected = True
        return True

    def close(self):
        self.closed = True

    def read_holding_registers(self, address, count):
        self.reads.append((address, count))
        return Response(self.positions)

    def write_registers(self, address, values):
        self.writes.append((address, list(values)))
        return Response()


def test_connect_and_read_are_write_free():
    client = FakeClient()
    driver = RH56Driver(client_factory=lambda *_args: client)

    driver.connect()
    positions = driver.read_positions()

    assert positions.tolist() == [900, 800, 700, 600, 500, 400]
    assert client.reads == [(ANGLE_ACT, 6)]
    assert client.writes == []


def test_driver_reads_local_endpoint_from_environment(monkeypatch):
    monkeypatch.setenv("RH56_HOST", "198.51.100.25")
    monkeypatch.setenv("RH56_PORT", "6502")

    driver = RH56Driver(client_factory=lambda *_args: FakeClient())

    assert driver.host == "198.51.100.25"
    assert driver.port == 6502


def test_write_motion_uses_approved_registers_and_force():
    client = FakeClient()
    driver = RH56Driver(client_factory=lambda *_args: client)
    driver.connect()

    driver.write_motion([800] * 6, [100, 260, 450, 100, 260, 450])

    assert client.writes == [
        (SPEED_SET, [100, 260, 450, 100, 260, 450]),
        (FORCE_SET, [220, 120, 120, 120, 220, 220]),
        (ANGLE_SET, [800] * 6),
    ]


def test_hold_reads_actual_then_writes_same_position():
    client = FakeClient(positions=(501, 502, 503, 504, 505, 506))
    driver = RH56Driver(client_factory=lambda *_args: client)
    driver.connect()

    held = driver.hold_current()

    assert held.tolist() == [501, 502, 503, 504, 505, 506]
    assert client.writes[-1] == (ANGLE_SET, held.tolist())


@pytest.mark.parametrize("values", [[1, 2], [-1] * 6, [1001] * 6, [np.nan] * 6])
def test_driver_rejects_invalid_six_channel_values(values):
    driver = RH56Driver(client_factory=lambda *_args: FakeClient())
    driver.connect()
    with pytest.raises(ValueError):
        driver.write_motion(values, [100] * 6)
