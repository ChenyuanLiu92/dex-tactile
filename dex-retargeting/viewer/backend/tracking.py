from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from mediapipe.python.solutions import hands as mp_hands

from dex_retargeting.constants import OPERATOR2MANO_RIGHT

from .state import TrackingStatus


@dataclass(frozen=True)
class DetectedHand:
    handedness: str
    confidence: float
    landmarks_2d: list[list[float]]


@dataclass(frozen=True)
class HandDetection:
    status: TrackingStatus
    handedness: str | None = None
    confidence: float | None = None
    landmarks_2d: list[list[float]] | None = None
    landmarks_3d: np.ndarray | None = None
    detected_hands: tuple[DetectedHand, ...] = ()


def estimate_hand_frame(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=float).reshape(21, 3)
    palm_points = points[[0, 5, 9]]
    x_vector = palm_points[0] - palm_points[2]
    centered = palm_points - np.mean(palm_points, axis=0, keepdims=True)
    _, _, basis = np.linalg.svd(centered)
    normal = basis[2]
    x_axis = x_vector - np.sum(x_vector * normal) * normal
    x_axis /= np.linalg.norm(x_axis)
    z_axis = np.cross(x_axis, normal)
    z_axis /= np.linalg.norm(z_axis)
    if np.sum(z_axis * (centered[1] - centered[2])) < 0:
        normal *= -1
        z_axis *= -1
    return np.stack([x_axis, normal, z_axis], axis=1)


class RightHandTracker:
    def __init__(self, hands=None, detection_width: int = 640):
        self.detection_width = detection_width
        self._hands = hands or mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )

    def process(self, frame: np.ndarray) -> HandDetection:
        height, width = frame.shape[:2]
        target_height = max(1, round(height * self.detection_width / width))
        resized = cv2.resize(frame, (self.detection_width, target_height))
        results: Any = self._hands.process(
            cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        )
        if not results.multi_hand_landmarks:
            return HandDetection(TrackingStatus.SEARCHING)

        detected_hands: list[DetectedHand] = []
        right_candidates: list[tuple[int, DetectedHand]] = []
        for index, image_landmark_list in enumerate(results.multi_hand_landmarks):
            handedness = results.multi_handedness[index].classification[0]
            points_2d = [[float(point.x), float(point.y)] for point in image_landmark_list.landmark]
            detected = DetectedHand(handedness.label, float(handedness.score), points_2d)
            detected_hands.append(detected)
            if detected.handedness == "Right":
                right_candidates.append((index, detected))

        if not right_candidates:
            primary = max(detected_hands, key=lambda hand: hand.confidence)
            return HandDetection(
                TrackingStatus.WRONG_HAND,
                handedness=primary.handedness,
                confidence=primary.confidence,
                landmarks_2d=primary.landmarks_2d,
                detected_hands=tuple(detected_hands),
            )

        right_index, primary = max(right_candidates, key=lambda candidate: candidate[1].confidence)
        world_landmarks = results.multi_hand_world_landmarks[right_index].landmark
        points_3d = np.array(
            [[point.x, point.y, point.z] for point in world_landmarks], dtype=float
        )
        points_3d -= points_3d[0:1]
        wrist_frame = estimate_hand_frame(points_3d)
        mano_points = points_3d @ wrist_frame @ OPERATOR2MANO_RIGHT
        return HandDetection(
            TrackingStatus.TRACKING,
            handedness=primary.handedness,
            confidence=primary.confidence,
            landmarks_2d=primary.landmarks_2d,
            landmarks_3d=mano_points,
            detected_hands=tuple(detected_hands),
        )

    def close(self) -> None:
        self._hands.close()
