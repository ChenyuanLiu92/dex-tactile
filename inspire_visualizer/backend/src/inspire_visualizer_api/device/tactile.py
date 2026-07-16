from dataclasses import dataclass
from struct import unpack
from typing import Literal

TactileProfile = Literal["disabled", "piezoresistive_v1", "capacitive_v1"]
TactileMetric = float | int


@dataclass(frozen=True)
class TactileRegion:
    id: str
    rows: int
    columns: int
    values: tuple[int, ...]
    metrics: dict[str, TactileMetric] | None = None


PIEZORESISTIVE_LAYOUT = (
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
)

CAPACITIVE_FINGERS = ("little_tip", "ring_tip", "middle_tip", "index_tip", "thumb_tip")


def decode_piezoresistive_bytes(data: bytes) -> tuple[TactileRegion, ...]:
    if len(data) != 2124:
        raise ValueError(f"piezoresistive tactile frame must contain 2124 bytes, got {len(data)}")
    values = tuple(data[index] | (data[index + 1] << 8) for index in range(0, len(data), 2))
    regions: list[TactileRegion] = []
    offset = 0
    for region_id, rows, columns in PIEZORESISTIVE_LAYOUT:
        length = rows * columns
        region_values = values[offset : offset + length]
        if region_id == "palm":
            region_values = tuple(
                region_values[column * rows + (rows - row - 1)]
                for row in range(rows)
                for column in range(columns)
            )
        regions.append(
            TactileRegion(
                id=region_id,
                rows=rows,
                columns=columns,
                values=region_values,
            )
        )
        offset += length
    return tuple(regions)


def decode_capacitive_sensor(region_id: str, data: bytes) -> TactileRegion:
    if len(data) != 58:
        raise ValueError(f"capacitive tactile sensor must contain 58 bytes, got {len(data)}")
    unpacked = unpack("<8I f i f i h i H H", data)
    return TactileRegion(
        id=region_id,
        rows=1,
        columns=8,
        values=tuple(int(value) for value in unpacked[:8]),
        metrics={
            "normal_force": float(unpacked[8]),
            "normal_delta": int(unpacked[9]),
            "tangential_force": float(unpacked[10]),
            "tangential_delta": int(unpacked[11]),
            "tangential_direction": int(unpacked[12]),
            "proximity_delta": int(unpacked[13]),
            "checksum": int(unpacked[14]),
        },
    )
