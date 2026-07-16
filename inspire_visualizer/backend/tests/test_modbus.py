from collections.abc import Sequence
from struct import pack

import pytest

from inspire_visualizer_api.device.modbus import InspireModbusClient, ModbusDeviceError


class FakeResponse:
    def __init__(self, registers: Sequence[int] = (), error: bool = False) -> None:
        self.registers = list(registers)
        self._error = error

    def isError(self) -> bool:  # noqa: N802 - pymodbus compatibility
        return self._error


class FakeClient:
    def __init__(self, angles: Sequence[int] = (1000,) * 6) -> None:
        self.angles = angles
        self.writes: list[tuple[int, list[int]]] = []
        self.connected = False

    def connect(self) -> bool:
        self.connected = True
        return True

    def close(self) -> None:
        self.connected = False

    def read_holding_registers(self, address: int, count: int) -> FakeResponse:
        assert (address, count) == (1546, 6)
        return FakeResponse(self.angles)

    def write_registers(self, address: int, values: Sequence[int]) -> FakeResponse:
        self.writes.append((address, list(values)))
        return FakeResponse()


class TactileFakeClient(FakeClient):
    def __init__(self, memory: dict[int, int]) -> None:
        super().__init__()
        self.memory = memory
        self.reads: list[tuple[int, int]] = []

    def read_holding_registers(self, address: int, count: int) -> FakeResponse:
        self.reads.append((address, count))
        if (address, count) == (1546, 6):
            return FakeResponse(self.angles)
        return FakeResponse([self.memory[index] for index in range(address, address + count)])


def test_connect_requires_a_valid_six_channel_angle_read() -> None:
    raw_client = FakeClient((1000, 900, 800, 700, 600, 500))
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)

    assert client.connect() is True
    assert client.read_angles() == (1000, 900, 800, 700, 600, 500)


def test_execute_pose_writes_speed_force_then_angle_groups() -> None:
    raw_client = FakeClient()
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)
    client.connect()

    client.execute_pose(
        angles=[900, 800, 700, 600, 500, 400],
        speeds=[100] * 6,
        forces=[500] * 6,
    )

    assert raw_client.writes == [
        (1522, [100] * 6),
        (1498, [500] * 6),
        (1486, [900, 800, 700, 600, 500, 400]),
    ]


def test_execute_pose_rejects_out_of_range_values_before_writing() -> None:
    raw_client = FakeClient()
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)

    with pytest.raises(ValueError):
        client.execute_pose(angles=[1001] * 6, speeds=[100] * 6, forces=[500] * 6)

    assert raw_client.writes == []


def test_read_error_is_reported_as_device_error() -> None:
    raw_client = FakeClient((1000,) * 5)
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)

    with pytest.raises(ModbusDeviceError):
        client.connect()


def test_piezoresistive_tactile_read_decodes_all_1062_taxels_and_regions() -> None:
    values = list(range(1062))
    byte_stream = [byte for value in values for byte in (value & 0xFF, value >> 8)]
    raw_client = TactileFakeClient(
        {address: value for address, value in enumerate(byte_stream, start=3000)}
    )
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)
    client.connect()

    regions = client.read_tactile("piezoresistive_v1")

    assert sum(len(region.values) for region in regions) == 1062
    assert [(region.id, region.rows, region.columns) for region in regions] == [
        ("little_tip_end", 3, 3),
        ("little_tip", 12, 8),
        ("little_pad", 10, 8),
        ("ring_tip_end", 3, 3),
        ("ring_tip", 12, 8),
        ("ring_pad", 10, 8),
        ("middle_tip_end", 3, 3),
        ("middle_tip", 12, 8),
        ("middle_pad", 10, 8),
        ("index_tip_end", 3, 3),
        ("index_tip", 12, 8),
        ("index_pad", 10, 8),
        ("thumb_tip_end", 3, 3),
        ("thumb_tip", 12, 8),
        ("thumb_middle", 3, 3),
        ("thumb_pad", 12, 8),
        ("palm", 8, 14),
    ]
    assert regions[0].values == tuple(range(9))
    assert regions[-1].values[:14] == tuple(957 + column * 8 for column in range(14))
    assert regions[-1].values[-14:] == tuple(950 + column * 8 for column in range(14))
    tactile_reads = [read for read in raw_client.reads if read[0] >= 3000]
    assert tactile_reads[0] == (3000, 120)
    assert tactile_reads[-1] == (5040, 84)
    assert len(tactile_reads) == 18


def test_capacitive_tactile_read_decodes_finger_channels_and_force_metrics() -> None:
    sensor = pack("<8I f i f i h i H H", *range(1, 9), 2.5, -3, 1.25, 4, 90, -5, 0x1234, 0)
    memory: dict[int, int] = {}
    for base in (3000, 3058, 3116, 3174, 3232):
        memory.update({base + index: value for index, value in enumerate(sensor)})
    raw_client = TactileFakeClient(memory)
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)
    client.connect()

    regions = client.read_tactile("capacitive_v1")

    assert [region.id for region in regions] == ["little_tip", "ring_tip", "middle_tip", "index_tip", "thumb_tip"]
    assert regions[0].values == tuple(range(1, 9))
    assert regions[0].metrics == {
        "normal_force": 2.5,
        "normal_delta": -3,
        "tangential_force": 1.25,
        "tangential_delta": 4,
        "tangential_direction": 90,
        "proximity_delta": -5,
        "checksum": 0x1234,
    }


def test_incomplete_tactile_chunk_is_rejected() -> None:
    class ShortClient(TactileFakeClient):
        def read_holding_registers(self, address: int, count: int) -> FakeResponse:
            response = super().read_holding_registers(address, count)
            if address == 3120:
                response.registers.pop()
            return response

    raw_client = ShortClient({address: 0 for address in range(3000, 5124)})
    client = InspireModbusClient("192.0.2.10", 6000, client_factory=lambda *_: raw_client)
    client.connect()

    with pytest.raises(ModbusDeviceError, match="tactile"):
        client.read_tactile("piezoresistive_v1")
