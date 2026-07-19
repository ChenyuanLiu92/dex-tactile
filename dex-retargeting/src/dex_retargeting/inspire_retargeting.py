from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import nlopt
import numpy as np

from dex_retargeting.constants import (
    HandType,
    RetargetingType,
    RobotName,
    get_default_config_path,
)
from dex_retargeting.retargeting_config import RetargetingConfig


ACTUATOR_JOINTS = (
    "pinky_proximal_joint",
    "ring_proximal_joint",
    "middle_proximal_joint",
    "index_proximal_joint",
    "thumb_proximal_pitch_joint",
    "thumb_proximal_yaw_joint",
)

# Segment constraints follow the MediaPipe landmark topology. The Inspire hand has
# one independently driven joint per finger, with the remaining joints represented
# by URDF mimic constraints.
SEGMENT_CONSTRAINTS = (
    (1, 2, "thumb_proximal_base", "thumb_proximal", 1.0),
    (2, 3, "thumb_proximal", "thumb_intermediate", 1.0),
    (3, 4, "thumb_intermediate", "thumb_tip", 0.9),
    (5, 7, "index_proximal", "index_intermediate", 1.0),
    (7, 8, "index_intermediate", "index_tip", 0.9),
    (9, 11, "middle_proximal", "middle_intermediate", 1.0),
    (11, 12, "middle_intermediate", "middle_tip", 0.9),
    (13, 15, "ring_proximal", "ring_intermediate", 1.0),
    (15, 16, "ring_intermediate", "ring_tip", 0.9),
    (17, 19, "pinky_proximal", "pinky_intermediate", 1.0),
    (19, 20, "pinky_intermediate", "pinky_tip", 0.9),
)

# The order matches the first four RH56 drive channels and ACTUATOR_JOINTS.
FINGER_FLEXION_CHAINS = (
    (17, 18, 19, 20),
    (13, 14, 15, 16),
    (9, 10, 11, 12),
    (5, 6, 7, 8),
)

THUMB_DISTANCE_CONSTRAINTS = (
    (4, 8, "thumb_tip", "index_tip", 2000.0),
    (4, 12, "thumb_tip", "middle_tip", 1500.0),
    (4, 16, "thumb_tip", "ring_tip", 1000.0),
    (4, 20, "thumb_tip", "pinky_tip", 800.0),
)

CONTACT_FINGERS = ("index", "middle", "ring", "pinky")
MCP_FLEXION_DEADBAND = 0.12
PROFILE_CALIBRATION_POSES = (
    "open",
    "relaxed",
    "fist",
    "thumb_opposition",
    "ok",
)


def _normalized_joint(value: float, limits: tuple[float, float]) -> float:
    lower, upper = limits
    if upper <= lower:
        return 0.0
    return float(np.clip((value - lower) / (upper - lower), 0.0, 1.0))


def _count_from_flexion(value: float) -> int:
    return int(round(1000 * (1.0 - float(np.clip(value, 0.0, 1.0)))))


def map_joints_to_actuators(
    joints: Mapping[str, float], limits: Mapping[str, tuple[float, float]]
) -> list[int]:
    """Map the six independent URDF joints directly to RH56 drive channels."""
    return [
        _count_from_flexion(_normalized_joint(joints[name], limits[name]))
        for name in ACTUATOR_JOINTS
    ]


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < 1e-8:
        return np.zeros(3, dtype=float)
    return vector / norm


def _bend_angle(first: np.ndarray, pivot: np.ndarray, last: np.ndarray) -> float:
    incoming = _unit(first - pivot)
    outgoing = _unit(last - pivot)
    if not np.any(incoming) or not np.any(outgoing):
        return 0.0
    straight_angle = float(
        np.arccos(np.clip(np.dot(incoming, outgoing), -1.0, 1.0))
    )
    return float(np.pi - straight_angle)


def _palm_normal(landmarks: np.ndarray) -> np.ndarray:
    across_palm = landmarks[5] - landmarks[17]
    palm_center = np.mean(landmarks[[5, 9, 13, 17]], axis=0)
    along_palm = palm_center - landmarks[0]
    return _unit(np.cross(across_palm, along_palm))


def _mcp_flexion(
    landmarks: np.ndarray, mcp: int, pip: int, palm_normal: np.ndarray
) -> float:
    proximal_direction = _unit(landmarks[pip] - landmarks[mcp])
    if not np.any(proximal_direction) or not np.any(palm_normal):
        return 0.0
    out_of_plane = float(
        np.arcsin(
            np.clip(abs(np.dot(proximal_direction, palm_normal)), 0.0, 1.0)
        )
    )
    return max(0.0, out_of_plane - MCP_FLEXION_DEADBAND)


def smooth_contact_activations(
    current: np.ndarray,
    previous: np.ndarray | None,
    alpha: float = 0.3,
) -> np.ndarray:
    """Apply SomeHand's contact-activation EMA without delaying first contact."""
    values = np.asarray(current, dtype=float)
    if previous is None:
        return values.copy()
    return alpha * values + (1.0 - alpha) * np.asarray(previous, dtype=float)


class ContactLatch:
    """DexPilot-style exclusive contact latch for the four thumb-finger pairs."""

    def __init__(
        self,
        enter_distance: float = 0.035,
        release_distance: float = 0.05,
        switch_intent_margin: float = np.deg2rad(20.0),
    ):
        if enter_distance >= release_distance:
            raise ValueError("contact enter distance must be below release distance")
        self.enter_distance = enter_distance
        self.release_distance = release_distance
        self.switch_intent_margin = switch_intent_margin
        self.target_index: int | None = None

    def update(
        self, distances: np.ndarray, flexion_intents: np.ndarray | None = None
    ) -> int | None:
        values = np.asarray(distances, dtype=float).reshape(len(CONTACT_FINGERS))
        if self.target_index is not None:
            if flexion_intents is not None:
                intents = np.asarray(flexion_intents, dtype=float).reshape(
                    len(CONTACT_FINGERS)
                )
                current_intent = intents[self.target_index]
                switch_candidates = np.flatnonzero(
                    (values < self.enter_distance)
                    & (intents > current_intent + self.switch_intent_margin)
                )
                if switch_candidates.size:
                    self.target_index = int(
                        switch_candidates[
                            np.argmax(intents[switch_candidates])
                        ]
                    )
                    return self.target_index
            if values[self.target_index] <= self.release_distance:
                return self.target_index
            self.target_index = None
            return None

        nearest = int(np.argmin(values))
        if values[nearest] < self.enter_distance:
            self.target_index = nearest
        return self.target_index

    def reset(self) -> None:
        self.target_index = None


@dataclass(frozen=True)
class ConstraintTargets:
    directions: np.ndarray
    finger_flexions: np.ndarray
    thumb_flexion: float
    frame_primary: np.ndarray
    frame_secondary: np.ndarray
    human_distances: np.ndarray
    human_middle_length: float


def build_constraint_targets(landmarks_3d: np.ndarray) -> ConstraintTargets:
    landmarks = np.asarray(landmarks_3d, dtype=float).reshape(21, 3)
    directions = np.stack(
        [_unit(landmarks[b] - landmarks[a]) for a, b, *_ in SEGMENT_CONSTRAINTS]
    )
    palm_normal = _palm_normal(landmarks)
    finger_flexions = np.asarray(
        [
            _mcp_flexion(landmarks, mcp, pip, palm_normal)
            + _bend_angle(landmarks[mcp], landmarks[pip], landmarks[dip])
            + _bend_angle(landmarks[pip], landmarks[dip], landmarks[tip])
            for mcp, pip, dip, tip in FINGER_FLEXION_CHAINS
        ],
        dtype=float,
    )
    thumb_flexion = _bend_angle(
        landmarks[1], landmarks[2], landmarks[3]
    ) + _bend_angle(landmarks[2], landmarks[3], landmarks[4])
    distances = np.asarray(
        [np.linalg.norm(landmarks[b] - landmarks[a]) for a, b, *_ in THUMB_DISTANCE_CONSTRAINTS],
        dtype=float,
    )
    middle_length = float(
        np.linalg.norm(landmarks[10] - landmarks[9])
        + np.linalg.norm(landmarks[11] - landmarks[10])
        + np.linalg.norm(landmarks[12] - landmarks[11])
    )
    frame_primary, frame_secondary = _orthonormal_axes(
        landmarks[2] - landmarks[1], landmarks[5] - landmarks[1]
    )
    return ConstraintTargets(
        directions,
        finger_flexions,
        thumb_flexion,
        frame_primary,
        frame_secondary,
        distances,
        middle_length,
    )


def _palm_width(landmarks: np.ndarray) -> float:
    return max(float(np.linalg.norm(landmarks[5] - landmarks[17])), 1e-6)


def _thumb_opposition_angle(landmarks: np.ndarray) -> float:
    across = _unit(landmarks[5] - landmarks[17])
    along = _unit(landmarks[9] - landmarks[0])
    normal = _unit(np.cross(across, along))
    thumb = _unit(landmarks[4] - landmarks[1])
    return float(np.arctan2(np.dot(thumb, normal), np.dot(thumb, across)))


def _pose_metrics(landmarks: np.ndarray) -> dict[str, Any]:
    targets = build_constraint_targets(landmarks)
    width = _palm_width(landmarks)
    return {
        "finger_flexions": targets.finger_flexions.tolist(),
        "thumb_flexion": float(targets.thumb_flexion),
        "thumb_opposition": _thumb_opposition_angle(landmarks),
        "pinch_ratio": float(targets.human_distances[0] / width),
        "palm_width": width,
    }


def _median_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    rows = np.asarray(
        [
            [*item["finger_flexions"], item["thumb_flexion"], item["thumb_opposition"], item["pinch_ratio"], item["palm_width"]]
            for item in samples
        ],
        dtype=float,
    )
    center = np.median(rows, axis=0)
    mad = np.median(np.abs(rows - center), axis=0)
    tolerance = np.maximum(3.0 * mad, 1e-6)
    retained = rows[np.all(np.abs(rows - center) <= tolerance, axis=1)]
    if retained.size == 0:
        retained = rows
    robust = np.median(retained, axis=0)
    return {
        "finger_flexions": robust[:4].tolist(),
        "thumb_flexion": float(robust[4]),
        "thumb_opposition": float(robust[5]),
        "pinch_ratio": float(robust[6]),
        "palm_width": float(robust[7]),
    }


def _piecewise_profile(
    value: float, open_value: float, relaxed_value: float, closed_value: float
) -> float:
    if closed_value <= open_value + 1e-6:
        return 0.0
    middle = float(np.clip(relaxed_value, open_value + 1e-6, closed_value - 1e-6))
    if value <= middle:
        return float(
            0.2 * np.clip((value - open_value) / (middle - open_value), 0.0, 1.0)
        )
    return float(
        0.2
        + 0.8
        * np.clip((value - middle) / (closed_value - middle), 0.0, 1.0)
    )


class ProfileCalibrationSession:
    poses = PROFILE_CALIBRATION_POSES

    def __init__(
        self,
        profile_id: str,
        *,
        required_samples: int = 30,
        window_size: int = 15,
        confidence_threshold: float = 0.7,
        stability_threshold: float = 0.02,
    ):
        self.profile_id = profile_id
        self.required_samples = required_samples
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.stability_threshold = stability_threshold
        self.pose_index = 0
        self.state = "COLLECTING"
        self.error: str | None = None
        self.failed_pose: str | None = None
        self._window: deque[np.ndarray] = deque(maxlen=window_size)
        self._samples: list[dict[str, Any]] = []
        self._captured: dict[str, dict[str, Any]] = {}
        self._completed: dict[str, Any] | None = None

    @property
    def current_pose(self) -> str | None:
        if self.pose_index >= len(self.poses):
            return None
        return self.poses[self.pose_index]

    def observe(self, landmarks: np.ndarray, confidence: float | None = None) -> None:
        if self.state != "COLLECTING" or self.current_pose is None:
            return
        score = 1.0 if confidence is None else float(confidence)
        if score < self.confidence_threshold:
            self._window.clear()
            return
        points = np.asarray(landmarks, dtype=float).reshape(21, 3)
        normalized = (points - points[0]) / _palm_width(points)
        self._window.append(normalized)
        if len(self._window) < self.window_size:
            return
        stack = np.stack(tuple(self._window))
        stability = float(np.sqrt(np.mean((stack - stack.mean(axis=0)) ** 2)))
        if stability > self.stability_threshold:
            return
        self._samples.append(_pose_metrics(points))
        if len(self._samples) < self.required_samples:
            return
        self._captured[self.current_pose] = _median_metrics(self._samples)
        self.pose_index += 1
        self._samples = []
        self._window.clear()
        if self.pose_index == len(self.poses):
            self._finish()

    def retry(self) -> None:
        if self.state == "COMPLETE" or self.state == "CANCELED":
            return
        if self.state == "FAILED" and self.failed_pose in self.poses:
            self.pose_index = self.poses.index(self.failed_pose)
            for pose in self.poses[self.pose_index :]:
                self._captured.pop(pose, None)
        self.state = "COLLECTING"
        self.error = None
        self.failed_pose = None
        self._samples = []
        self._window.clear()

    def cancel(self) -> None:
        self.state = "CANCELED"
        self._samples = []
        self._window.clear()

    def status(self) -> dict[str, Any]:
        stability = None
        if len(self._window) == self.window_size:
            stack = np.stack(tuple(self._window))
            stability = float(
                np.sqrt(np.mean((stack - stack.mean(axis=0)) ** 2))
            )
        return {
            "state": self.state,
            "profile_id": self.profile_id,
            "pose": self.current_pose,
            "pose_index": self.pose_index,
            "total_poses": len(self.poses),
            "accepted_samples": len(self._samples),
            "required_samples": self.required_samples,
            "stability": stability,
            "error": self.error,
            "failed_pose": self.failed_pose,
        }

    def completed_calibration(self) -> dict[str, Any] | None:
        return None if self._completed is None else json.loads(json.dumps(self._completed))

    def _finish(self) -> None:
        open_pose = self._captured["open"]
        relaxed = self._captured["relaxed"]
        fist = self._captured["fist"]
        opposed = self._captured["thumb_opposition"]
        ok = self._captured["ok"]
        open_flex = np.asarray(open_pose["finger_flexions"])
        relaxed_flex = np.asarray(relaxed["finger_flexions"])
        fist_flex = np.asarray(fist["finger_flexions"])
        if np.any(fist_flex - open_flex < np.deg2rad(45.0)):
            self._fail("fist", "Fist range is below 45 degrees for one or more fingers")
            return
        if np.any(relaxed_flex < open_flex) or np.any(relaxed_flex > fist_flex):
            self._fail("relaxed", "Relaxed pose must lie between open and fist")
            return
        opposition_delta = abs(
            float(opposed["thumb_opposition"]) - float(open_pose["thumb_opposition"])
        )
        if opposition_delta < np.deg2rad(15.0):
            self._fail("thumb_opposition", "Thumb opposition range is below 15 degrees")
            return
        if float(ok["pinch_ratio"]) >= float(open_pose["pinch_ratio"]):
            self._fail("ok", "OK pinch is not closer than the open-hand distance")
            return
        enter = max(float(ok["pinch_ratio"]) * 1.25, float(ok["pinch_ratio"]) + 0.02)
        self._completed = {
            "mode": "five_pose",
            "poses": self._captured,
            "contact_enter_ratio": enter,
            "contact_release_ratio": enter + 0.15,
        }
        self.state = "COMPLETE"

    def _fail(self, pose: str, message: str) -> None:
        self.state = "FAILED"
        self.failed_pose = pose
        self.error = message
        self.pose_index = self.poses.index(pose)


def _orthonormal_axes(
    primary_vector: np.ndarray, secondary_vector: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    primary = _unit(primary_vector)
    secondary = _unit(secondary_vector - np.dot(secondary_vector, primary) * primary)
    return primary, secondary


class InspireVisionRetargeter:
    """Six-DoF Inspire solver using segment, contact, and thumb-frame constraints."""

    _LANDMARK_ALPHA = 0.65
    _OUTPUT_ALPHA = 0.92
    _OUTPUT_MAX_COUNT_STEP = 220
    _ACTIVATION_ALPHA = 0.3
    _NORM_DELTA = 1e-3
    _CONTACT_WEIGHT = 2000.0
    _PROJECTED_CONTACT_DISTANCE = 0.005
    _FINGER_FLEXION_WEIGHT = 12.0
    _FINGER_FLEXION_DEADBAND = 0.05
    _FINGER_FLEXION_GAIN = 1.15
    _FINGER_MIMIC_TOTAL = 1.0 + 1.06399
    _THUMB_FLEXION_WEIGHT = 60.0
    _THUMB_FLEXION_GAIN = 1.2
    _THUMB_MIMIC_TOTAL = 1.0 + 1.334 + 0.667
    _SECONDARY_CONTACT_FLEXION = 0.55
    def __init__(
        self,
        repository_root: Path | None = None,
        calibration_path: Path | None = None,
    ):
        root = repository_root or Path(__file__).resolve().parents[2]
        RetargetingConfig.set_default_urdf_dir(str(root / "assets" / "robots" / "hands"))
        config_path = get_default_config_path(
            RobotName.inspire, RetargetingType.vector, HandType.right
        )
        if config_path is None:
            raise FileNotFoundError("Inspire right-hand retargeting config was not found")
        base_retargeting = RetargetingConfig.load_from_file(config_path).build()
        base_optimizer = base_retargeting.optimizer

        self._robot = base_optimizer.robot
        adaptor = base_optimizer.adaptor
        if adaptor is None:
            raise ValueError("Inspire URDF mimic constraints were not loaded")
        self._adaptor = adaptor
        self._target_indices = base_optimizer.idx_pin2target.copy()
        self._joint_limits_array = self._robot.joint_limits
        self.joint_names = tuple(self._robot.dof_joint_names)
        self.joint_limits = {
            name: (float(bounds[0]), float(bounds[1]))
            for name, bounds in zip(self.joint_names, self._joint_limits_array)
        }

        if tuple(base_optimizer.target_joint_names) != ACTUATOR_JOINTS:
            raise ValueError("Inspire actuator joint order no longer matches the RH56 protocol")
        link_names = {
            name
            for constraint in (*SEGMENT_CONSTRAINTS, *THUMB_DISTANCE_CONSTRAINTS)
            for name in constraint[2:4]
        }
        self._link_names = tuple(sorted(link_names))
        self._link_indices = {
            name: self._robot.get_link_index(name) for name in self._link_names
        }

        target_limits = self._joint_limits_array[self._target_indices]
        self._last_independent = target_limits.mean(axis=1).astype(float)
        self._last_full: np.ndarray | None = None
        self._filtered_landmarks: np.ndarray | None = None
        self._previous_activations: np.ndarray | None = None
        self._contact_latch = ContactLatch()
        self._contact_human_distance: float | None = None
        self._calibration_lock = threading.RLock()
        self._neutral_flexions = np.zeros(4, dtype=float)
        self._neutral_thumb_flexion = 0.0
        self._neutral_thumb_offsets = np.zeros(2, dtype=float)
        self._neutral_calibrated = False
        self._operator_profile: dict[str, Any] = {
            "id": "default",
            "name": "Default",
            "calibration": None,
        }
        self._profile_calibration: dict[str, Any] | None = None
        self._profile_session: ProfileCalibrationSession | None = None
        self._calibration_path = calibration_path
        self._load_calibration()
        self._frame_local_primary, self._frame_local_secondary = (
            self._compute_thumb_frame_axes(self._last_independent)
        )
        self._robot_middle_length = self._compute_robot_middle_length(
            self._last_independent
        )

        self._optimizer = nlopt.opt(nlopt.LD_SLSQP, len(ACTUATOR_JOINTS))
        self._optimizer.set_lower_bounds(target_limits[:, 0])
        self._optimizer.set_upper_bounds(target_limits[:, 1])
        self._optimizer.set_ftol_abs(1e-6)
        self._optimizer.set_maxeval(60)

    def set_operator_profile(self, profile: Mapping[str, Any]) -> None:
        with self._calibration_lock:
            calibration = profile.get("calibration")
            self._operator_profile = {
                "id": str(profile.get("id", "default")),
                "name": str(profile.get("name", "Default")),
                "calibration": calibration,
            }
            self._profile_calibration = (
                dict(calibration)
                if isinstance(calibration, Mapping)
                and calibration.get("mode") == "five_pose"
                else None
            )
            if isinstance(calibration, Mapping) and calibration.get("mode") == "legacy_open":
                self._neutral_flexions = np.asarray(
                    calibration.get("neutral_flexions", [0.0] * 4), dtype=float
                ).reshape(4)
                self._neutral_thumb_offsets = np.asarray(
                    calibration.get("neutral_thumb_offsets", [0.0] * 2), dtype=float
                ).reshape(2)
                self._neutral_thumb_flexion = float(
                    calibration.get("neutral_thumb_flexion", 0.0)
                )
                self._neutral_calibrated = True
            elif self._profile_calibration is None:
                self._neutral_flexions = np.zeros(4, dtype=float)
                self._neutral_thumb_offsets = np.zeros(2, dtype=float)
                self._neutral_thumb_flexion = 0.0
                self._neutral_calibrated = False
            else:
                self._neutral_flexions = np.zeros(4, dtype=float)
                self._neutral_thumb_offsets = np.zeros(2, dtype=float)
                self._neutral_thumb_flexion = 0.0
                self._neutral_calibrated = False
            self._filtered_landmarks = None
            self._previous_activations = None
            self._contact_latch = ContactLatch()

    def get_operator_profile(self) -> dict[str, Any]:
        with self._calibration_lock:
            calibration = self._operator_profile.get("calibration")
            return {
                "id": self._operator_profile["id"],
                "name": self._operator_profile["name"],
                "calibration_state": (
                    "DEFAULT"
                    if self._operator_profile["id"] == "default"
                    else "CALIBRATED" if calibration else "UNCALIBRATED"
                ),
            }

    def start_profile_calibration(self, profile_id: str) -> dict[str, Any]:
        with self._calibration_lock:
            self._profile_session = ProfileCalibrationSession(profile_id)
            return self._profile_session.status()

    def retry_profile_calibration(self) -> dict[str, Any]:
        with self._calibration_lock:
            if self._profile_session is None:
                raise ValueError("No profile calibration is active")
            self._profile_session.retry()
            return self._profile_session.status()

    def cancel_profile_calibration(self) -> dict[str, Any]:
        with self._calibration_lock:
            if self._profile_session is None:
                raise ValueError("No profile calibration is active")
            self._profile_session.cancel()
            return self._profile_session.status()

    def get_profile_calibration_status(self) -> dict[str, Any] | None:
        with self._calibration_lock:
            return None if self._profile_session is None else self._profile_session.status()

    def completed_profile_calibration(self) -> dict[str, Any] | None:
        with self._calibration_lock:
            if self._profile_session is None:
                return None
            return self._profile_session.completed_calibration()

    def _full_qpos(self, independent: np.ndarray) -> np.ndarray:
        qpos = np.zeros(self._robot.dof, dtype=float)
        qpos[self._target_indices] = independent
        return self._adaptor.forward_qpos(qpos)

    def _link_state(
        self, independent: np.ndarray
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, np.ndarray],
        dict[str, np.ndarray],
        dict[str, np.ndarray],
    ]:
        qpos = self._full_qpos(independent)
        self._robot.compute_forward_kinematics(qpos)
        positions: dict[str, np.ndarray] = {}
        jacobians: dict[str, np.ndarray] = {}
        rotations: dict[str, np.ndarray] = {}
        angular_jacobians: dict[str, np.ndarray] = {}
        for name, link_index in self._link_indices.items():
            pose = self._robot.get_link_pose(link_index)
            positions[name] = pose[:3, 3]
            rotation = pose[:3, :3]
            rotations[name] = rotation
            local_jacobian = self._robot.compute_single_link_local_jacobian(
                qpos, link_index
            )
            jacobians[name] = self._adaptor.backward_jacobian(
                rotation @ local_jacobian[:3]
            )
            angular_jacobians[name] = self._adaptor.backward_jacobian(
                rotation @ local_jacobian[3:]
            )
        return positions, jacobians, rotations, angular_jacobians

    def _compute_thumb_frame_axes(
        self, independent: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        positions, _, rotations, _ = self._link_state(independent)
        origin = positions["thumb_proximal_base"]
        primary, secondary = _orthonormal_axes(
            positions["thumb_proximal"] - origin,
            positions["index_proximal"] - origin,
        )
        inverse_rotation = rotations["thumb_proximal_base"].T
        return inverse_rotation @ primary, inverse_rotation @ secondary

    def _compute_robot_middle_length(self, independent: np.ndarray) -> float:
        positions, _, _, _ = self._link_state(independent)
        return float(
            np.linalg.norm(positions["middle_intermediate"] - positions["middle_proximal"])
            + np.linalg.norm(positions["middle_tip"] - positions["middle_intermediate"])
        )

    def _filter_landmarks(self, landmarks: np.ndarray) -> np.ndarray:
        if self._filtered_landmarks is None:
            self._filtered_landmarks = landmarks.copy()
        else:
            alpha = self._LANDMARK_ALPHA
            self._filtered_landmarks = (
                alpha * landmarks + (1.0 - alpha) * self._filtered_landmarks
            )
        return self._filtered_landmarks.copy()

    def _objective(
        self,
        targets: ConstraintTargets,
        activations: np.ndarray,
        target_distances: np.ndarray | None = None,
        proximity_distances: np.ndarray | None = None,
    ):
        if target_distances is None:
            distance_scale = self._robot_middle_length / max(
                targets.human_middle_length, 1e-6
            )
            target_distances = targets.human_distances * distance_scale
        else:
            target_distances = np.asarray(target_distances, dtype=float)
        if proximity_distances is None:
            proximity_distances = targets.human_distances
        previous = self._last_independent.copy()
        with self._calibration_lock:
            neutral_flexions = self._neutral_flexions.copy()
            neutral_thumb_flexion = self._neutral_thumb_flexion
        relative_flexions = np.maximum(
            targets.finger_flexions - neutral_flexions, 0.0
        )
        profile = self._profile_calibration
        if profile is not None:
            poses = profile["poses"]
            normalized_fingers = np.asarray(
                [
                    _piecewise_profile(
                        targets.finger_flexions[index],
                        poses["open"]["finger_flexions"][index],
                        poses["relaxed"]["finger_flexions"][index],
                        poses["fist"]["finger_flexions"][index],
                    )
                    for index in range(4)
                ]
            )
            finger_limits = self._joint_limits_array[self._target_indices[:4]]
            finger_targets = finger_limits[:, 0] + normalized_fingers * (
                finger_limits[:, 1] - finger_limits[:, 0]
            )
        else:
            finger_targets = np.clip(
                (
                    np.maximum(
                        relative_flexions - self._FINGER_FLEXION_DEADBAND,
                        0.0,
                    )
                    * self._FINGER_FLEXION_GAIN
                    / self._FINGER_MIMIC_TOTAL
                ),
                self._joint_limits_array[self._target_indices[:4], 0],
                self._joint_limits_array[self._target_indices[:4], 1],
            )
        thumb_pitch_limits = self._joint_limits_array[self._target_indices[4]]
        if profile is not None:
            poses = profile["poses"]
            thumb_normalized = _piecewise_profile(
                targets.thumb_flexion,
                poses["open"]["thumb_flexion"],
                poses["relaxed"]["thumb_flexion"],
                poses["fist"]["thumb_flexion"],
            )
            thumb_pitch_target = float(
                thumb_pitch_limits[0]
                + thumb_normalized * (thumb_pitch_limits[1] - thumb_pitch_limits[0])
            )
        else:
            thumb_pitch_target = float(
                np.clip(
                    max(targets.thumb_flexion - neutral_thumb_flexion, 0.0)
                    * self._THUMB_FLEXION_GAIN
                    / self._THUMB_MIMIC_TOTAL,
                    thumb_pitch_limits[0],
                    thumb_pitch_limits[1],
                )
            )
        proximity_strength = np.clip(
            (
                self._contact_latch.release_distance
                - proximity_distances
            )
            / (
                self._contact_latch.release_distance
                - self._contact_latch.enter_distance
            ),
            0.0,
            1.0,
        )
        # Distance projection remains exclusive, but a second nearby fingertip
        # still needs a closure prior for common tripod pinches.
        proximity_floor = (
            proximity_strength[::-1] * self._SECONDARY_CONTACT_FLEXION
        )
        finger_targets = np.maximum(finger_targets, proximity_floor)

        def objective(independent: np.ndarray, gradient: np.ndarray) -> float:
            positions, jacobians, rotations, angular_jacobians = self._link_state(
                independent
            )
            loss = 0.0
            grad = np.zeros_like(independent)

            finger_delta = independent[:4] - finger_targets
            # A latched pinch owns its target finger; the contact projection must
            # be free to close farther than the observed human joint angle.
            contact_by_actuator = activations[::-1]
            flexion_weights = self._FINGER_FLEXION_WEIGHT * (
                1.0 - contact_by_actuator
            )
            loss += float(np.dot(flexion_weights, finger_delta * finger_delta))
            grad[:4] += 2.0 * flexion_weights * finger_delta

            thumb_pitch_weight = self._THUMB_FLEXION_WEIGHT * (
                1.0 - float(np.max(activations))
            )
            thumb_pitch_delta = independent[4] - thumb_pitch_target
            loss += thumb_pitch_weight * thumb_pitch_delta * thumb_pitch_delta
            grad[4] += 2.0 * thumb_pitch_weight * thumb_pitch_delta

            for index, (_, _, origin, task, weight) in enumerate(SEGMENT_CONSTRAINTS):
                vector = positions[task] - positions[origin]
                norm = float(np.linalg.norm(vector))
                target = targets.directions[index]
                if norm < 1e-8 or not np.any(target):
                    continue
                robot_direction = vector / norm
                cosine = float(np.clip(np.dot(robot_direction, target), -1.0, 1.0))
                loss += weight * (1.0 - cosine)
                direction_grad = -(target - cosine * robot_direction) / norm
                grad += weight * direction_grad @ (
                    jacobians[task] - jacobians[origin]
                )

            thumb_rotation = rotations["thumb_proximal_base"]
            thumb_angular_jacobian = angular_jacobians["thumb_proximal_base"]
            for local_axis, target_axis, weight in (
                (self._frame_local_primary, targets.frame_primary, 2.0),
                (self._frame_local_secondary, targets.frame_secondary, 1.8),
            ):
                axis = thumb_rotation @ local_axis
                cosine = float(np.clip(np.dot(axis, target_axis), -1.0, 1.0))
                loss += weight * (1.0 - cosine)
                axis_jacobian = np.cross(thumb_angular_jacobian.T, axis).T
                grad += -weight * target_axis @ axis_jacobian

            for index, (_, _, first, second, _) in enumerate(
                THUMB_DISTANCE_CONSTRAINTS
            ):
                if activations[index] < 1e-4:
                    continue
                vector = positions[second] - positions[first]
                distance = float(np.linalg.norm(vector))
                difference = distance - target_distances[index]
                if distance < 1e-8 or difference <= 0.0:
                    continue
                effective_weight = self._CONTACT_WEIGHT * activations[index]
                loss += effective_weight * difference * difference
                grad += (
                    2.0
                    * effective_weight
                    * difference
                    * (vector / distance)
                    @ (jacobians[second] - jacobians[first])
                )

            delta = independent - previous
            loss += self._NORM_DELTA * float(np.dot(delta, delta))
            grad += 2.0 * self._NORM_DELTA * delta
            if gradient.size:
                gradient[:] = grad
            return float(loss)

        return objective

    def retarget(
        self, landmarks_3d: np.ndarray, confidence: float | None = None
    ) -> tuple[dict[str, float], list[int]]:
        with self._calibration_lock:
            return self._retarget(landmarks_3d, confidence)

    def _retarget(
        self, landmarks_3d: np.ndarray, confidence: float | None = None
    ) -> tuple[dict[str, float], list[int]]:
        landmarks = np.asarray(landmarks_3d, dtype=float).reshape(21, 3)
        if self._profile_session is not None:
            self._profile_session.observe(landmarks, confidence)
        targets = build_constraint_targets(self._filter_landmarks(landmarks))
        with self._calibration_lock:
            contact_flexion_intents = np.maximum(
                targets.finger_flexions - self._neutral_flexions, 0.0
            )[::-1]
        contact_distances = targets.human_distances
        if self._profile_calibration is not None:
            width = _palm_width(landmarks)
            contact_distances = targets.human_distances / width
            self._contact_latch.enter_distance = float(
                self._profile_calibration["contact_enter_ratio"]
            )
            self._contact_latch.release_distance = float(
                self._profile_calibration["contact_release_ratio"]
            )
        contact_index = self._contact_latch.update(
            contact_distances, contact_flexion_intents
        )
        raw_activations = np.zeros(len(THUMB_DISTANCE_CONSTRAINTS), dtype=float)
        if contact_index is None:
            activations = raw_activations
            self._contact_human_distance = None
        else:
            raw_activations[contact_index] = 1.0
            activations = smooth_contact_activations(
                raw_activations,
                self._previous_activations,
                self._ACTIVATION_ALPHA,
            )
            self._contact_human_distance = float(
                targets.human_distances[contact_index]
            )
        self._previous_activations = activations.copy()
        projected_distances = np.full(
            len(THUMB_DISTANCE_CONSTRAINTS),
            self._PROJECTED_CONTACT_DISTANCE,
            dtype=float,
        )
        self._optimizer.set_min_objective(
            self._objective(
                targets,
                activations,
                projected_distances,
                proximity_distances=contact_distances,
            )
        )
        try:
            independent = np.asarray(
                self._optimizer.optimize(self._last_independent), dtype=float
            )
        except RuntimeError:
            independent = self._last_independent.copy()
        if self._profile_calibration is not None:
            poses = self._profile_calibration["poses"]
            open_angle = float(poses["open"]["thumb_opposition"])
            opposed_angle = float(poses["thumb_opposition"]["thumb_opposition"])
            denominator = opposed_angle - open_angle
            progress = 0.0
            if abs(denominator) > 1e-6:
                progress = float(
                    np.clip(
                        (_thumb_opposition_angle(landmarks) - open_angle) / denominator,
                        0.0,
                        1.0,
                    )
                )
            yaw_limits = self._joint_limits_array[self._target_indices[5]]
            independent[5] = yaw_limits[0] + progress * (
                yaw_limits[1] - yaw_limits[0]
            )
        if self._last_full is not None:
            previous_independent = self._last_full[self._target_indices]
            independent = previous_independent + self._OUTPUT_ALPHA * (
                independent - previous_independent
            )
            target_limits = self._joint_limits_array[self._target_indices]
            maximum_joint_step = (
                self._OUTPUT_MAX_COUNT_STEP
                / 1000.0
                * (target_limits[:, 1] - target_limits[:, 0])
            )
            independent = previous_independent + np.clip(
                independent - previous_independent,
                -maximum_joint_step,
                maximum_joint_step,
            )
        with self._calibration_lock:
            neutral_thumb_offsets = self._neutral_thumb_offsets.copy()
            neutral_calibrated = self._neutral_calibrated
        if neutral_calibrated:
            target_limits = self._joint_limits_array[self._target_indices]
            independent[5] = np.clip(
                independent[5] - neutral_thumb_offsets[1],
                target_limits[5, 0],
                target_limits[5, 1],
            )
        self._last_independent = independent.copy()

        full_qpos = self._full_qpos(independent)
        self._last_full = full_qpos.copy()
        joints = {
            name: float(full_qpos[index])
            for index, name in enumerate(self.joint_names)
        }
        return joints, map_joints_to_actuators(joints, self.joint_limits)

    def get_contact_status(self) -> dict[str, str | float | None]:
        with self._calibration_lock:
            target_index = self._contact_latch.target_index
            return {
                "state": "LOCKED" if target_index is not None else "NONE",
                "finger": None if target_index is None else CONTACT_FINGERS[target_index],
                "human_distance_mm": None
                if self._contact_human_distance is None
                else round(self._contact_human_distance * 1000.0, 1),
                "projected_distance_mm": self._PROJECTED_CONTACT_DISTANCE * 1000.0,
            }

    def _load_calibration(self) -> None:
        path = self._calibration_path
        if path is None or not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            flexions = np.asarray(payload["neutral_flexions"], dtype=float).reshape(4)
            thumb = np.asarray(payload["neutral_thumb_offsets"], dtype=float).reshape(2)
            thumb_flexion = float(payload.get("neutral_thumb_flexion", 0.0))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return
        if (
            not np.all(np.isfinite(flexions))
            or not np.all(np.isfinite(thumb))
            or not np.isfinite(thumb_flexion)
        ):
            return
        self._neutral_flexions = np.maximum(flexions, 0.0)
        self._neutral_thumb_offsets = np.maximum(thumb, 0.0)
        self._neutral_thumb_flexion = max(thumb_flexion, 0.0)
        self._neutral_calibrated = True

    def reset_tracking_context(self) -> None:
        """Clear observation history without moving the retained robot pose."""
        with self._calibration_lock:
            self._filtered_landmarks = None
            self._previous_activations = None
            self._contact_latch.reset()
            self._contact_human_distance = None
