from __future__ import annotations

import os
from collections.abc import Callable, Sequence

import numpy as np
from pymodbus.client.sync import ModbusTcpClient


ANGLE_SET = 1486
FORCE_SET = 1498
SPEED_SET = 1522
ANGLE_ACT = 1546
DEFAULT_FORCE = np.array([220, 120, 120, 120, 220, 220], dtype=int)
HOLD_SPEED = np.full(6, 100, dtype=int)
DEFAULT_HOST = "192.0.2.10"
DEFAULT_PORT = 6000


def _channels(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if len(array) != 6 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain six finite values")
    if np.any(array < 0) or np.any(array > 1000):
        raise ValueError(f"{name} values must be in the range 0..1000")
    return np.rint(array).astype(int)


class RH56Driver:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float = 0.5,
        force: Sequence[int] = DEFAULT_FORCE,
        client_factory: Callable[..., object] | None = None,
    ):
        self.host = host or os.environ.get("RH56_HOST", DEFAULT_HOST)
        self.port = int(port if port is not None else os.environ.get("RH56_PORT", DEFAULT_PORT))
        self.force = _channels(force, "force")
        self._client_factory = client_factory or (
            lambda host, port: ModbusTcpClient(host, port=port, timeout=timeout)
        )
        self._client = None
        self._written_speed: np.ndarray | None = None
        self._written_force: np.ndarray | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        self.close()
        client = self._client_factory(self.host, self.port)
        if client.connect() is not True:
            client.close()
            raise ConnectionError(
                f"Unable to connect to RH56 at {self.host}:{self.port}"
            )
        self._client = client
        self._written_speed = None
        self._written_force = None

    def read_positions(self) -> np.ndarray:
        client = self._require_client()
        response = client.read_holding_registers(ANGLE_ACT, 6)
        registers = getattr(response, "registers", ())
        if response.isError() or len(registers) != 6:
            raise RuntimeError("Invalid ANGLE_ACT response from RH56")
        return _channels(registers, "actual positions")

    def write_motion(self, positions: Sequence[float], speeds: Sequence[float]) -> None:
        position_values = _channels(positions, "positions")
        speed_values = _channels(speeds, "speeds")
        if self._written_speed is None or not np.array_equal(
            speed_values, self._written_speed
        ):
            self._write(SPEED_SET, speed_values)
            self._written_speed = speed_values.copy()
        if self._written_force is None or not np.array_equal(
            self.force, self._written_force
        ):
            self._write(FORCE_SET, self.force)
            self._written_force = self.force.copy()
        self._write(ANGLE_SET, position_values)

    def hold_current(self) -> np.ndarray:
        positions = self.read_positions()
        self.write_motion(positions, HOLD_SPEED)
        return positions

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._written_speed = None
        self._written_force = None

    def _write(self, address: int, values: np.ndarray) -> None:
        response = self._require_client().write_registers(address, values.tolist())
        if response.isError():
            raise RuntimeError(f"RH56 Modbus write failed at register {address}")

    def _require_client(self):
        if self._client is None:
            raise ConnectionError("RH56 is not connected")
        return self._client
