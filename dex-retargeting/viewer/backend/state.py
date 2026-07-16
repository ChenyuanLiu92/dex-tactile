from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TrackingStatus(StrEnum):
    STARTING = "STARTING"
    SEARCHING = "SEARCHING"
    WRONG_HAND = "WRONG_HAND"
    TRACKING = "TRACKING"
    LOST = "LOST"
    CAMERA_ERROR = "CAMERA_ERROR"


@dataclass(frozen=True)
class TrackingSnapshot:
    status: TrackingStatus = TrackingStatus.STARTING
    sequence: int = 0
    captured_at: float = 0.0
    published_at: float = 0.0
    capture_fps: float = 0.0
    tracking_fps: float = 0.0
    latency_ms: float = 0.0
    handedness: str | None = None
    confidence: float | None = None
    landmarks_2d: list[list[float]] | None = None
    landmarks_3d: list[list[float]] | None = None
    detected_hands: list[dict[str, Any]] | None = None
    joints: dict[str, float] | None = None
    actuators: list[int] | None = None
    contact: dict[str, Any] | None = None
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        tracking = self.status is TrackingStatus.TRACKING
        return {
            "type": "tracking",
            "status": self.status.value,
            "sequence": self.sequence,
            "captured_at": self.captured_at,
            "published_at": self.published_at,
            "capture_fps": round(self.capture_fps, 1),
            "tracking_fps": round(self.tracking_fps, 1),
            "latency_ms": round(self.latency_ms, 1),
            "handedness": self.handedness,
            "confidence": None
            if self.confidence is None
            else round(self.confidence, 3),
            "landmarks_2d": self.landmarks_2d,
            "landmarks_3d": self.landmarks_3d if tracking else None,
            "detected_hands": self.detected_hands or [],
            "joints": self.joints if tracking else None,
            "actuators": self.actuators if tracking else None,
            "contact": self.contact if tracking else None,
            "error": self.error,
            "dry_run": True,
            "modbus_output": False,
        }
