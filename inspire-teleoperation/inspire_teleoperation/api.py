"""Stable, hardware-agnostic contracts for teleoperation integrations.

The API intentionally separates tracking input from robot output.  A source
produces :class:`TeleopFrame` objects and any number of modules consume them.
An arm integration can therefore be added without changing the hand module or
the application loop.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from numbers import Integral
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]


def _finite_array(
    value: Any,
    *,
    name: str,
    shape: tuple[int, ...],
) -> FloatArray:
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains NaN or infinity")
    array = array.copy()
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True)
class RigidTransform:
    """A validated homogeneous transform for an XR tracked body."""

    matrix: FloatArray

    def __post_init__(self) -> None:
        matrix = _finite_array(self.matrix, name="transform", shape=(4, 4))
        if not np.allclose(matrix[3], (0.0, 0.0, 0.0, 1.0), atol=1e-6):
            raise ValueError("transform must use a homogeneous [0, 0, 0, 1] last row")
        rotation = matrix[:3, :3]
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-4) or not np.isclose(
            np.linalg.det(rotation), 1.0, atol=1e-4
        ):
            raise ValueError("transform rotation must be orthonormal and right-handed")
        object.__setattr__(self, "matrix", matrix)


@dataclass(frozen=True, slots=True)
class HandTracking:
    """One tracked hand in the OpenXR/Quest 25-landmark layout."""

    landmarks: FloatArray
    wrist: RigidTransform | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "landmarks",
            _finite_array(self.landmarks, name="hand landmarks", shape=(25, 3)),
        )


@dataclass(frozen=True, slots=True)
class TeleopFrame:
    """A single immutable tracking sample shared by all robot modules.

    ``extras`` is reserved for source-specific, non-critical data.  New robot
    modules should prefer explicit fields for values that form part of their
    public contract.
    """

    sequence: int
    timestamp: float
    motion_data_ready: bool
    left_hand: HandTracking | None = None
    right_hand: HandTracking | None = None
    head: RigidTransform | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, Integral)
            or self.sequence < 0
        ):
            raise ValueError("sequence must be a non-negative integer")
        if not math.isfinite(self.timestamp):
            raise ValueError("timestamp must be finite")
        if not isinstance(self.motion_data_ready, bool):
            raise TypeError("motion_data_ready must be a boolean")
        object.__setattr__(self, "sequence", int(self.sequence))
        object.__setattr__(self, "extras", MappingProxyType(dict(self.extras)))

    @classmethod
    def empty(cls, sequence: int = 0) -> "TeleopFrame":
        return cls(
            sequence=sequence,
            timestamp=time.monotonic(),
            motion_data_ready=False,
        )


@dataclass(frozen=True, slots=True)
class ModuleStatus:
    """Generic health information exposed by every output module."""

    name: str
    ready: bool
    detail: str = ""
    telemetry: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class TeleopSource(Protocol):
    """Tracking provider such as Quest, mocap, or a replay file."""

    def start(self) -> None: ...

    def read(self) -> TeleopFrame: ...

    def close(self) -> None: ...


@runtime_checkable
class TeleopModule(Protocol):
    """Independent robot subsystem consuming the common tracking frame."""

    @property
    def name(self) -> str: ...

    def start(self) -> None: ...

    def update(self, frame: TeleopFrame, *, enabled: bool) -> None: ...

    def status(self) -> ModuleStatus: ...

    def close(self) -> None: ...
