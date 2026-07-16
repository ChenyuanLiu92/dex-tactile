from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
    _OPEN_CALIBRATION_FRAMES = 30

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
        base_retargeting = RetargetingConfig.load_from_file(config_path).build()
        base_optimizer = base_retargeting.optimizer

        self._robot = base_optimizer.robot
        self._adaptor = base_optimizer.adaptor
        self._target_indices = base_optimizer.idx_pin2target.copy()
        self._joint_limits_array = self._robot.joint_limits
        self.joint_names = tuple(self._robot.dof_joint_names)
        self.joint_limits = {
            name: (float(bounds[0]), float(bounds[1]))
            for name, bounds in zip(self.joint_names, self._joint_limits_array)
        }

        if tuple(base_optimizer.target_joint_names) != ACTUATOR_JOINTS:
            raise ValueError("Inspire actuator joint order no longer matches the RH56 protocol")
        if self._adaptor is None:
            raise ValueError("Inspire URDF mimic constraints were not loaded")

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
        self._calibration_lock = threading.Lock()
        self._calibration_collecting = False
        self._calibration_samples: list[np.ndarray] = []
        self._calibration_joint_samples: list[np.ndarray] = []
        self._calibration_thumb_samples: list[float] = []
        self._neutral_flexions = np.zeros(4, dtype=float)
        self._neutral_thumb_flexion = 0.0
        self._neutral_thumb_offsets = np.zeros(2, dtype=float)
        self._neutral_calibrated = False
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
    ):
        if target_distances is None:
            distance_scale = self._robot_middle_length / max(
                targets.human_middle_length, 1e-6
            )
            target_distances = targets.human_distances * distance_scale
        else:
            target_distances = np.asarray(target_distances, dtype=float)
        previous = self._last_independent.copy()
        with self._calibration_lock:
            neutral_flexions = self._neutral_flexions.copy()
            neutral_thumb_flexion = self._neutral_thumb_flexion
        relative_flexions = np.maximum(
            targets.finger_flexions - neutral_flexions, 0.0
        )
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
                - targets.human_distances
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

    def retarget(self, landmarks_3d: np.ndarray) -> tuple[dict[str, float], list[int]]:
        landmarks = np.asarray(landmarks_3d, dtype=float).reshape(21, 3)
        targets = build_constraint_targets(self._filter_landmarks(landmarks))
        with self._calibration_lock:
            contact_flexion_intents = np.maximum(
                targets.finger_flexions - self._neutral_flexions, 0.0
            )[::-1]
        contact_index = self._contact_latch.update(
            targets.human_distances, contact_flexion_intents
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
            self._objective(targets, activations, projected_distances)
        )
        try:
            independent = np.asarray(
                self._optimizer.optimize(self._last_independent), dtype=float
            )
        except RuntimeError:
            independent = self._last_independent.copy()
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
        self._collect_open_calibration(
            targets.finger_flexions, targets.thumb_flexion, independent
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
        target_index = self._contact_latch.target_index
        return {
            "state": "LOCKED" if target_index is not None else "NONE",
            "finger": None if target_index is None else CONTACT_FINGERS[target_index],
            "human_distance_mm": None
            if self._contact_human_distance is None
            else round(self._contact_human_distance * 1000.0, 1),
            "projected_distance_mm": self._PROJECTED_CONTACT_DISTANCE * 1000.0,
        }

    def start_open_calibration(self) -> dict[str, object]:
        with self._calibration_lock:
            self._calibration_collecting = True
            self._calibration_samples.clear()
            self._calibration_joint_samples.clear()
            self._calibration_thumb_samples.clear()
        return self.get_calibration_status()

    def _collect_open_calibration(
        self,
        finger_flexions: np.ndarray,
        thumb_flexion: float,
        independent: np.ndarray,
    ) -> None:
        with self._calibration_lock:
            if not self._calibration_collecting:
                return
            self._calibration_samples.append(
                np.asarray(finger_flexions, dtype=float).copy()
            )
            self._calibration_joint_samples.append(
                np.asarray(independent, dtype=float).copy()
            )
            self._calibration_thumb_samples.append(float(thumb_flexion))
            if len(self._calibration_samples) < self._OPEN_CALIBRATION_FRAMES:
                return
            self._neutral_flexions = np.median(
                np.stack(self._calibration_samples), axis=0
            )
            self._neutral_thumb_offsets = np.median(
                np.stack(self._calibration_joint_samples), axis=0
            )[4:6]
            self._neutral_thumb_flexion = float(
                np.median(self._calibration_thumb_samples)
            )
            self._neutral_calibrated = True
            self._calibration_collecting = False
            self._calibration_samples.clear()
            self._calibration_joint_samples.clear()
            self._calibration_thumb_samples.clear()
            self._save_calibration_locked()

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

    def _save_calibration_locked(self) -> None:
        path = self._calibration_path
        if path is None:
            return
        payload = {
            "version": 1,
            "neutral_flexions": self._neutral_flexions.tolist(),
            "neutral_thumb_offsets": self._neutral_thumb_offsets.tolist(),
            "neutral_thumb_flexion": self._neutral_thumb_flexion,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(path)
        except OSError:
            return

    def get_calibration_status(self) -> dict[str, object]:
        with self._calibration_lock:
            if self._calibration_collecting:
                state = "COLLECTING"
                samples = len(self._calibration_samples)
            elif self._neutral_calibrated:
                state = "CALIBRATED"
                samples = self._OPEN_CALIBRATION_FRAMES
            else:
                state = "UNCALIBRATED"
                samples = 0
            return {
                "state": state,
                "samples": samples,
                "required_samples": self._OPEN_CALIBRATION_FRAMES,
                "neutral_flexion_deg": [
                    round(float(np.degrees(value)), 1)
                    for value in self._neutral_flexions
                ],
                "neutral_thumb_offset_counts": [
                    int(
                        round(
                            1000.0
                            * self._neutral_thumb_offsets[index]
                            / max(
                                self._joint_limits_array[
                                    self._target_indices[index + 4], 1
                                ]
                                - self._joint_limits_array[
                                    self._target_indices[index + 4], 0
                                ],
                                1e-8,
                            )
                        )
                    )
                    for index in range(2)
                ],
                "neutral_thumb_flexion_deg": round(
                    float(np.degrees(self._neutral_thumb_flexion)), 1
                ),
            }

    def reset_tracking_context(self) -> None:
        """Clear observation history without moving the retained robot pose."""
        self._filtered_landmarks = None
        self._previous_activations = None
        self._contact_latch.reset()
        self._contact_human_distance = None
        with self._calibration_lock:
            if self._calibration_collecting:
                self._calibration_samples.clear()
                self._calibration_joint_samples.clear()
                self._calibration_thumb_samples.clear()
