"""Quest hand-keypoint conversion for RH56 retargeting.

Open-Teach publishes the Oculus/Quest skeleton as 24 wrist-relative points.
The Inspire optimizer consumes the MediaPipe 21-point topology in a MANO-aligned
local hand frame. This module is deliberately transport-independent so both
projects use one tested conversion.
"""

from __future__ import annotations

import numpy as np

from dex_retargeting.constants import OPERATOR2MANO_RIGHT


QUEST_FINGER_CHAINS = {
    "index": (6, 7, 8, 20),
    "middle": (9, 10, 11, 21),
    "ring": (12, 13, 14, 22),
    "pinky": (16, 17, 18, 23),
}
QUEST_THUMB_CHAIN = (2, 3, 4, 5, 19)


def _resample_chain(points: np.ndarray, count: int) -> np.ndarray:
    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(distances)))
    total = float(cumulative[-1])
    if total <= 1e-9:
        return np.repeat(points[:1], count, axis=0)
    samples = np.linspace(0.0, total, count)
    return np.stack(
        [np.interp(samples, cumulative, points[:, axis]) for axis in range(3)],
        axis=1,
    )


def quest_to_mediapipe(quest_keypoints: np.ndarray) -> np.ndarray:
    """Convert Quest's 24-point hand skeleton to MediaPipe's 21-point order."""
    quest = np.asarray(quest_keypoints, dtype=float).reshape(24, 3)
    if not np.all(np.isfinite(quest)):
        raise ValueError("Quest keypoints must be finite")

    result = np.zeros((21, 3), dtype=float)
    result[0] = quest[0]
    result[1:5] = _resample_chain(quest[list(QUEST_THUMB_CHAIN)], 4)
    for destination, name in zip((5, 9, 13, 17), ("index", "middle", "ring", "pinky")):
        result[destination : destination + 4] = quest[list(QUEST_FINGER_CHAINS[name])]
    return result


def estimate_hand_frame(points: np.ndarray) -> np.ndarray:
    """Estimate the same wrist frame used by the D435/MediaPipe pipeline."""
    landmarks = np.asarray(points, dtype=float).reshape(21, 3)
    palm_points = landmarks[[0, 5, 9]]
    x_vector = palm_points[0] - palm_points[2]
    centered = palm_points - np.mean(palm_points, axis=0, keepdims=True)
    _, _, basis = np.linalg.svd(centered)
    normal = basis[2]
    x_axis = x_vector - np.sum(x_vector * normal) * normal
    x_norm = float(np.linalg.norm(x_axis))
    if x_norm <= 1e-9:
        raise ValueError("Quest palm points are degenerate")
    x_axis /= x_norm
    z_axis = np.cross(x_axis, normal)
    z_axis /= np.linalg.norm(z_axis)
    if np.sum(z_axis * (centered[1] - centered[2])) < 0:
        normal *= -1
        z_axis *= -1
    return np.stack([x_axis, normal, z_axis], axis=1)


def quest_to_mano(quest_keypoints: np.ndarray) -> np.ndarray:
    """Convert Quest points to the MANO-aligned input expected by the solver."""
    landmarks = quest_to_mediapipe(quest_keypoints)
    landmarks -= landmarks[0:1]
    return landmarks @ estimate_hand_frame(landmarks) @ OPERATOR2MANO_RIGHT
