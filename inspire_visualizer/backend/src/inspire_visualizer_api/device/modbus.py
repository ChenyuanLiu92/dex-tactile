from collections.abc import Callable, Sequence
from typing import Any

from pymodbus.client.sync import ModbusTcpClient

from inspire_visualizer_api.device.tactile import (
    CAPACITIVE_FINGERS,
    TactileProfile,
    TactileRegion,
    decode_capacitive_sensor,
    decode_piezoresistive_bytes,
)

ANGLE_SET = 1486
FORCE_SET = 1498
SPEED_SET = 1522
ANGLE_ACT = 1546
TOUCH_START = 3000
TOUCH_END = 5124
TOUCH_CHUNK = 120


class ModbusDeviceError(RuntimeError):
    """Raised when the hand returns an invalid Modbus response."""


def _default_client_factory(host: str, port: int) -> ModbusTcpClient:
    return ModbusTcpClient(host, port=port, timeout=0.5)


class InspireModbusClient:
    def __init__(
        self,
        host: str,
        port: int,
        client_factory: Callable[[str, int], Any] = _default_client_factory,
    ) -> None:
        self.host = host
        self.port = port
        self._client_factory = client_factory
        self._client: Any | None = None

    def connect(self) -> bool:
        self.close()
        client = self._client_factory(self.host, self.port)
        if client.connect() is not True:
            client.close()
            raise ModbusDeviceError(f"unable to connect to {self.host}:{self.port}")
        self._client = client
        try:
            self.read_angles()
        except Exception:
            self.close()
            raise
        return True

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def read_angles(self) -> tuple[int, ...]:
        client = self._require_client()
        response = client.read_holding_registers(ANGLE_ACT, 6)
        if response.isError() or len(getattr(response, "registers", ())) != 6:
            raise ModbusDeviceError("invalid ANGLE_ACT response")
        values = tuple(int(value) for value in response.registers)
        if any(value < 0 or value > 1000 for value in values):
            raise ModbusDeviceError("ANGLE_ACT values must be in the range 0..1000")
        return values

    def read_tactile(self, profile: TactileProfile) -> tuple[TactileRegion, ...]:
        if profile == "disabled":
            return ()
        if profile == "piezoresistive_v1":
            data = self._read_byte_registers(TOUCH_START, TOUCH_END - TOUCH_START)
            try:
                return decode_piezoresistive_bytes(data)
            except ValueError as error:
                raise ModbusDeviceError(str(error)) from error
        if profile == "capacitive_v1":
            regions: list[TactileRegion] = []
            for index, region_id in enumerate(CAPACITIVE_FINGERS):
                data = self._read_byte_registers(TOUCH_START + index * 58, 58)
                try:
                    regions.append(decode_capacitive_sensor(region_id, data))
                except ValueError as error:
                    raise ModbusDeviceError(str(error)) from error
            return tuple(regions)
        raise ValueError(f"unsupported tactile profile: {profile}")

    def execute_pose(
        self,
        *,
        angles: Sequence[int],
        speeds: Sequence[int],
        forces: Sequence[int],
    ) -> None:
        angle_values = self._validated_group("angles", angles, 1000)
        speed_values = self._validated_group("speeds", speeds, 1000)
        force_values = self._validated_group("forces", forces, 3000)
        client = self._require_client()

        for address, values in (
            (SPEED_SET, speed_values),
            (FORCE_SET, force_values),
            (ANGLE_SET, angle_values),
        ):
            response = client.write_registers(address, values)
            if response.isError():
                raise ModbusDeviceError(f"write failed at register {address}")

    def _require_client(self) -> Any:
        if self._client is None:
            raise ModbusDeviceError("device is not connected")
        return self._client

    def _read_byte_registers(self, address: int, count: int) -> bytes:
        client = self._require_client()
        output = bytearray()
        for chunk_address in range(address, address + count, TOUCH_CHUNK):
            chunk_count = min(TOUCH_CHUNK, address + count - chunk_address)
            response = client.read_holding_registers(chunk_address, chunk_count)
            registers = getattr(response, "registers", ())
            if response.isError() or len(registers) != chunk_count:
                raise ModbusDeviceError(f"invalid tactile response at register {chunk_address}")
            output.extend(int(value) & 0xFF for value in registers)
        return bytes(output)

    @staticmethod
    def _validated_group(name: str, values: Sequence[int], maximum: int) -> list[int]:
        if len(values) != 6 or any(value < 0 or value > maximum for value in values):
            raise ValueError(f"{name} must contain six values in the range 0..{maximum}")
        return [int(value) for value in values]
