from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np


SCHEMA_NAME = "dex-tactile-hand"
SCHEMA_VERSION = "1.0"
ACTUATOR_NAMES = (
    "little_flexion",
    "ring_flexion",
    "middle_flexion",
    "index_flexion",
    "thumb_flexion",
    "thumb_opposition",
)
TRACKING_STATES = {
    "STARTING": 0,
    "SEARCHING": 1,
    "WRONG_HAND": 2,
    "TRACKING": 3,
    "LOST": 4,
    "CAMERA_ERROR": 5,
    "DISCONNECTED": 6,
}
CONTROL_STATES = {
    "DISCONNECTED": 0,
    "DISARMED": 1,
    "ARMING": 2,
    "ARMED": 3,
    "POSITIONING": 4,
    "HOLDING": 5,
    "ESTOPPED": 6,
    "FAULT": 7,
}
CONTACT_STATES = {"NONE": 0, "LOCKED": 1}
CONTACT_FINGERS: dict[str | None, int] = {
    None: -1,
    "index": 0,
    "middle": 1,
    "ring": 2,
    "pinky": 3,
}
HANDEDNESS: dict[str | None, int] = {None: -1, "Left": 0, "Right": 1}
CONNECTION_STATES = {"offline": 0, "connecting": 1, "online": 2}


@dataclass(frozen=True)
class Field:
    path: str
    shape: tuple[int, ...]
    dtype: Any
    fill: Any


def frame_fields(joint_count: int) -> tuple[Field, ...]:
    return (
        Field("frames/time/elapsed", (), np.float64, np.nan),
        Field("frames/time/wall", (), np.float64, np.nan),
        Field("frames/time/source_received", (), np.float64, np.nan),
        Field("frames/time/source_captured", (), np.float64, np.nan),
        Field("frames/time/source_published", (), np.float64, np.nan),
        Field("frames/source_sequence", (), np.int64, -1),
        Field("frames/source_connected", (), np.bool_, False),
        Field("frames/tracking/status", (), np.uint8, TRACKING_STATES["DISCONNECTED"]),
        Field("frames/tracking/valid", (), np.bool_, False),
        Field("frames/tracking/handedness", (), np.int8, -1),
        Field("frames/tracking/confidence", (), np.float32, np.nan),
        Field("frames/tracking/landmarks_2d", (21, 2), np.float32, np.nan),
        Field("frames/tracking/landmarks_3d", (21, 3), np.float32, np.nan),
        Field("frames/retargeting/joints", (joint_count,), np.float32, np.nan),
        Field("frames/retargeting/actuator_targets", (6,), np.int16, -1),
        Field("frames/contact/state", (), np.uint8, CONTACT_STATES["NONE"]),
        Field("frames/contact/finger", (), np.int8, -1),
        Field("frames/contact/human_distance_mm", (), np.float32, np.nan),
        Field("frames/contact/projected_distance_mm", (), np.float32, np.nan),
        Field("frames/control/state", (), np.uint8, CONTROL_STATES["DISCONNECTED"]),
        Field("frames/control/connected", (), np.bool_, False),
        Field("frames/control/actual", (6,), np.int16, -1),
        Field("frames/control/targets", (6,), np.int16, -1),
        Field("frames/control/commanded", (6,), np.int16, -1),
        Field("frames/control/speeds", (6,), np.int16, -1),
        Field("frames/control/modbus_output", (), np.bool_, False),
        Field("frames/control/tracking_hold", (), np.bool_, False),
    )


ROBOT_FIELDS = (
    Field("robot/time/elapsed", (), np.float64, np.nan),
    Field("robot/time/wall", (), np.float64, np.nan),
    Field("robot/time/source_updated", (), np.float64, np.nan),
    Field("robot/connection", (), np.uint8, CONNECTION_STATES["offline"]),
    Field("robot/armed", (), np.bool_, False),
    Field("robot/actual", (6,), np.int16, -1),
)

TACTILE_FIELDS = (
    Field("tactile/time/elapsed", (), np.float64, np.nan),
    Field("tactile/time/wall", (), np.float64, np.nan),
    Field("tactile/time/source_captured", (), np.float64, np.nan),
    Field("tactile/source_sequence", (), np.int64, -1),
    Field("tactile/values", (1062,), np.uint16, 0),
)


def enum_json(values: dict[Any, int]) -> str:
    return json.dumps({"null" if key is None else str(key): value for key, value in values.items()})
