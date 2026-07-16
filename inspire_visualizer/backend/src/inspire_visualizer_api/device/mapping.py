from collections.abc import Sequence
from typing import Literal

HandSide = Literal["left", "right"]

CHANNELS = (
    "little",
    "ring",
    "middle",
    "index",
    "thumb_bend",
    "thumb_rotate",
)

_JOINTS: dict[HandSide, tuple[tuple[str, float, float], ...]] = {
    "left": (
        ("left_little_1_joint", 0.0, 1.6),
        ("left_ring_1_joint", 0.0, 1.6),
        ("left_middle_1_joint", 0.0, 1.6),
        ("left_index_1_joint", 0.0, 1.6),
        ("left_thumb_1_joint", 0.0, -0.95),
        ("left_thumb_swing_joint", 0.0, 1.7),
    ),
    "right": (
        ("right_little_1_joint", 0.0, 1.6),
        ("right_ring_1_joint", 0.0, 1.6),
        ("right_middle_1_joint", 0.0, 1.6),
        ("right_index_1_joint", 0.0, 1.6),
        ("right_thumb_2_joint", 0.0, 0.75),
        ("right_thumb_1_joint", 0.0, 1.7),
    ),
}


def device_to_joint_values(side: HandSide, values: Sequence[int]) -> dict[str, float]:
    if len(values) != 6 or any(value < 0 or value > 1000 for value in values):
        raise ValueError("angles must contain six values in the range 0..1000")

    result: dict[str, float] = {}
    for value, (joint, opened, closed) in zip(values, _JOINTS[side], strict=True):
        openness = value / 1000
        result[joint] = closed + openness * (opened - closed)
    return result
