import pickle
import threading
from pathlib import Path

import numpy as np
import pytest

from dex_retargeting.constants import OPERATOR2MANO_RIGHT
from viewer.backend.retargeting import (
    ContactLatch,
    InspireVisionRetargeter,
    ProfileCalibrationSession,
    SEGMENT_CONSTRAINTS,
    build_constraint_targets,
    map_joints_to_actuators,
    smooth_contact_activations,
)
from viewer.backend.state import TrackingSnapshot, TrackingStatus
from viewer.backend.tracking import estimate_hand_frame
from viewer.tools.retargeting_diagnostics import curl_finger


LIMITS = {
    "index_proximal_joint": (0.0, 1.0),
    "index_intermediate_joint": (0.0, 1.0),
    "middle_proximal_joint": (0.0, 1.0),
    "middle_intermediate_joint": (0.0, 1.0),
    "pinky_proximal_joint": (0.0, 1.0),
    "pinky_intermediate_joint": (0.0, 1.0),
    "ring_proximal_joint": (0.0, 1.0),
    "ring_intermediate_joint": (0.0, 1.0),
    "thumb_proximal_yaw_joint": (0.0, 1.0),
    "thumb_proximal_pitch_joint": (0.0, 1.0),
    "thumb_intermediate_joint": (0.0, 1.0),
    "thumb_distal_joint": (0.0, 1.0),
}


def _canonical_pose(pinch: str | None = None) -> np.ndarray:
    points = np.zeros((21, 3), dtype=float)
    points[[1, 2, 3, 4]] = [
        [0.030, -0.010, 0.0],
        [0.052, -0.016, 0.0],
        [0.072, -0.022, 0.0],
        [0.092, -0.028, 0.0],
    ]
    points[[5, 6, 7, 8]] = [
        [0.022, -0.022, 0.0],
        [0.022, -0.054, 0.0],
        [0.022, -0.086, 0.0],
        [0.022, -0.118, 0.0],
    ]
    points[[9, 10, 11, 12]] = [
        [0.0, -0.022, 0.0],
        [0.0, -0.060, 0.0],
        [0.0, -0.098, 0.0],
        [0.0, -0.136, 0.0],
    ]
    points[[13, 14, 15, 16]] = [
        [-0.022, -0.020, 0.0],
        [-0.022, -0.053, 0.0],
        [-0.022, -0.086, 0.0],
        [-0.022, -0.118, 0.0],
    ]
    points[[17, 18, 19, 20]] = [
        [-0.044, -0.016, 0.0],
        [-0.044, -0.043, 0.0],
        [-0.044, -0.070, 0.0],
        [-0.044, -0.097, 0.0],
    ]
    if pinch:
        points[[1, 2, 3, 4]] = [
            [0.020, -0.016, 0.0],
            [0.034, -0.032, 0.0],
            [0.042, -0.048, 0.0],
            [0.038, -0.062, 0.0],
        ]
        if pinch == "index":
            points[[7, 8]] = [[0.027, -0.072, 0.0], [0.032, -0.082, 0.0]]
        else:
            finger_start = {"middle": 9, "ring": 13, "pinky": 17}[pinch]
            base = points[finger_start].copy()
            contact = points[4] + np.array([0.010, 0.0, 0.0])
            points[finger_start + 1] = 0.65 * base + 0.35 * contact
            points[finger_start + 2] = 0.30 * base + 0.70 * contact
            points[finger_start + 3] = contact
    centered = points - points[0:1]
    return centered @ estimate_hand_frame(centered) @ OPERATOR2MANO_RIGHT


FINGER_LANDMARKS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _single_finger_curl(finger: str, bend: float = 1.15) -> np.ndarray:
    points = _canonical_pose()
    mcp, pip, dip, tip = FINGER_LANDMARKS[finger]
    origin = points[mcp].copy()
    lengths = (
        np.linalg.norm(points[pip] - points[mcp]),
        np.linalg.norm(points[dip] - points[pip]),
        np.linalg.norm(points[tip] - points[dip]),
    )
    forward = points[pip] - origin
    forward /= np.linalg.norm(forward)
    across_palm = points[5] - points[17]
    across_palm -= forward * np.dot(across_palm, forward)
    across_palm /= np.linalg.norm(across_palm)
    palm_normal = np.cross(forward, across_palm)
    palm_normal /= np.linalg.norm(palm_normal)

    def direction(angle: float) -> np.ndarray:
        return np.cos(angle) * forward + np.sin(angle) * palm_normal

    points[pip] = origin + lengths[0] * direction(0.35 * bend)
    points[dip] = points[pip] + lengths[1] * direction(0.85 * bend)
    points[tip] = points[dip] + lengths[2] * direction(1.25 * bend)
    return points


def _mcp_only_curl(finger: str, bend: float = 1.1) -> np.ndarray:
    points = _canonical_pose()
    mcp, pip, dip, tip = FINGER_LANDMARKS[finger]
    origin = points[mcp].copy()
    lengths = (
        np.linalg.norm(points[pip] - points[mcp]),
        np.linalg.norm(points[dip] - points[pip]),
        np.linalg.norm(points[tip] - points[dip]),
    )
    forward = points[pip] - origin
    forward /= np.linalg.norm(forward)
    across_palm = points[5] - points[17]
    across_palm -= forward * np.dot(across_palm, forward)
    across_palm /= np.linalg.norm(across_palm)
    palm_normal = np.cross(forward, across_palm)
    palm_normal /= np.linalg.norm(palm_normal)
    curled_direction = (
        np.cos(bend) * forward + np.sin(bend) * palm_normal
    )

    points[pip] = origin + lengths[0] * curled_direction
    points[dip] = points[pip] + lengths[1] * curled_direction
    points[tip] = points[dip] + lengths[2] * curled_direction
    return points


def _all_fingers_curl(bend: float) -> np.ndarray:
    points = _canonical_pose()
    for finger in FINGER_LANDMARKS:
        points = curl_finger(points, finger, bend=bend)
    return points


def test_maps_joint_limits_to_physical_actuator_order():
    joints = {name: 0.0 for name in LIMITS}
    joints.update(
        {
            "pinky_proximal_joint": 1.0,
            "pinky_intermediate_joint": 1.0,
            "ring_proximal_joint": 0.5,
            "ring_intermediate_joint": 0.5,
            "thumb_proximal_pitch_joint": 1.0,
            "thumb_intermediate_joint": 0.5,
            "thumb_distal_joint": 0.0,
            "thumb_proximal_yaw_joint": 0.25,
        }
    )

    assert map_joints_to_actuators(joints, LIMITS) == [0, 500, 1000, 1000, 0, 750]


def test_actuator_mapping_clips_values_outside_joint_limits():
    joints = {name: -10.0 for name in LIMITS}
    joints["thumb_proximal_yaw_joint"] = 10.0

    assert map_joints_to_actuators(joints, LIMITS) == [1000, 1000, 1000, 1000, 1000, 0]


def test_constraint_targets_are_invariant_to_hand_scale():
    landmarks = np.arange(63, dtype=float).reshape(21, 3)
    # Avoid collinear vectors so all normalized directions are meaningful.
    landmarks[:, 1] = np.sin(np.arange(21))
    landmarks[:, 2] = np.cos(np.arange(21))

    first = build_constraint_targets(landmarks)
    second = build_constraint_targets(landmarks * 2.5)

    np.testing.assert_allclose(first.directions, second.directions, atol=1e-8)
    np.testing.assert_allclose(second.human_distances, first.human_distances * 2.5)
    assert second.human_middle_length == first.human_middle_length * 2.5


def test_constraints_cover_each_finger_segment_and_thumb_frame():
    assert len(SEGMENT_CONSTRAINTS) == 11
    assert {pair[:2] for pair in SEGMENT_CONSTRAINTS} >= {
        (1, 2),
        (2, 3),
        (3, 4),
        (5, 7),
        (7, 8),
        (9, 11),
        (11, 12),
        (13, 15),
        (15, 16),
        (17, 19),
        (19, 20),
    }


@pytest.mark.parametrize("finger", ["index", "middle", "ring", "pinky"])
def test_constraint_targets_measure_isolated_finger_flexion(finger: str):
    open_targets = build_constraint_targets(_canonical_pose())
    curled_targets = build_constraint_targets(_single_finger_curl(finger))
    finger_index = ("pinky", "ring", "middle", "index").index(finger)

    assert curled_targets.finger_flexions[finger_index] > 0.75
    other_indices = {0, 1, 2, 3} - {finger_index}
    assert all(
        abs(
            curled_targets.finger_flexions[index]
            - open_targets.finger_flexions[index]
        )
        < 1e-6
        for index in other_indices
    )


@pytest.mark.parametrize(
    ("finger", "channel"),
    [("pinky", 0), ("ring", 1), ("middle", 2), ("index", 3)],
)
def test_isolated_finger_curl_only_closes_matching_actuator(
    finger: str, channel: int
):
    retargeter = InspireVisionRetargeter()
    for _ in range(8):
        retargeter.retarget(_canonical_pose())

    for _ in range(12):
        _, actuators = retargeter.retarget(_single_finger_curl(finger))

    assert actuators[channel] < 750
    assert all(
        value > 900 for index, value in enumerate(actuators[:4]) if index != channel
    )


@pytest.mark.parametrize(
    ("finger", "channel"),
    [("pinky", 0), ("ring", 1), ("middle", 2), ("index", 3)],
)
def test_mcp_only_curl_closes_matching_actuator(finger: str, channel: int):
    retargeter = InspireVisionRetargeter()
    for _ in range(8):
        retargeter.retarget(_canonical_pose())

    for _ in range(12):
        _, actuators = retargeter.retarget(_mcp_only_curl(finger))

    assert actuators[channel] < 750
    assert all(
        value > 900 for index, value in enumerate(actuators[:4]) if index != channel
    )


def test_contact_activation_filter_matches_somehand_temporal_semantics():
    previous = np.zeros(4, dtype=float)
    active = np.ones(4, dtype=float)

    first = smooth_contact_activations(active, previous)
    second = smooth_contact_activations(active, first)

    np.testing.assert_allclose(first, [0.3] * 4)
    np.testing.assert_allclose(second, [0.51] * 4)


def test_first_contact_activation_frame_is_not_attenuated():
    active = np.array([1.0, 0.75, 0.25, 0.0])

    np.testing.assert_allclose(smooth_contact_activations(active, None), active)


def test_contact_latch_uses_nearest_candidate_and_hysteresis():
    latch = ContactLatch()

    assert latch.update(np.array([0.029, 0.020, 0.080, 0.090])) == 1
    assert latch.update(np.array([0.010, 0.049, 0.080, 0.090])) == 1
    assert latch.update(np.array([0.010, 0.051, 0.080, 0.090])) is None
    assert latch.update(np.array([0.010, 0.051, 0.080, 0.090])) == 0
    assert latch.update(np.array([0.051, 0.052, 0.080, 0.090])) is None


def test_contact_latch_reset_clears_selected_finger():
    latch = ContactLatch()
    latch.update(np.array([0.020, 0.080, 0.090, 0.100]))

    latch.reset()

    assert latch.target_index is None


def test_contact_latch_does_not_chatter_between_enter_and_release_thresholds():
    latch = ContactLatch()

    states = [
        latch.update(np.array([distance, 0.080, 0.090, 0.100]))
        for distance in (0.029, 0.031, 0.028, 0.049, 0.047)
    ]

    assert states == [0, 0, 0, 0, 0]
    assert latch.update(np.array([0.051, 0.080, 0.090, 0.100])) is None
    assert latch.update(np.array([0.049, 0.080, 0.090, 0.100])) is None
    assert latch.update(np.array([0.029, 0.080, 0.090, 0.100])) == 0


def test_contact_latch_accepts_measured_middle_pinch_distance():
    latch = ContactLatch()

    assert latch.update(np.array([0.060, 0.0313, 0.080, 0.090])) == 1


def test_contact_latch_switches_to_close_finger_with_stronger_flexion_intent():
    latch = ContactLatch()
    assert latch.update(
        np.array([0.080, 0.070, 0.020, 0.025]),
        np.array([0.0, 0.0, 0.2, 0.2]),
    ) == 2

    switched = latch.update(
        np.array([0.080, 0.070, 0.018, 0.017]),
        np.array([0.0, 0.0, 0.0, 0.7]),
    )

    assert switched == 3


def test_projected_index_pinch_uses_thumb_opposition_without_closing_other_fingers():
    retargeter = InspireVisionRetargeter()
    retargeter.retarget(_canonical_pose())

    for _ in range(12):
        _, actuators = retargeter.retarget(_canonical_pose("index"))

    positions, _, _, _ = retargeter._link_state(retargeter._last_independent)
    gap = np.linalg.norm(positions["thumb_tip"] - positions["index_tip"])
    contact = retargeter.get_contact_status()

    assert gap <= 0.015
    assert actuators[:3] == [1000, 1000, 1000]
    assert actuators[5] < 350
    assert contact["state"] == "LOCKED"
    assert contact["finger"] == "index"
    assert contact["projected_distance_mm"] == 5.0


@pytest.mark.parametrize(
    ("finger", "tip_link"),
    [
        ("index", "index_tip"),
        ("middle", "middle_tip"),
        ("ring", "ring_tip"),
        ("pinky", "pinky_tip"),
    ],
)
def test_projected_contact_supports_each_finger(finger: str, tip_link: str):
    retargeter = InspireVisionRetargeter()
    retargeter.retarget(_canonical_pose())
    open_positions, _, _, _ = retargeter._link_state(retargeter._last_independent)
    open_gap = np.linalg.norm(open_positions["thumb_tip"] - open_positions[tip_link])

    for _ in range(16):
        retargeter.retarget(_canonical_pose(finger))

    positions, _, _, _ = retargeter._link_state(retargeter._last_independent)
    gap = np.linalg.norm(positions["thumb_tip"] - positions[tip_link])

    assert retargeter.get_contact_status()["finger"] == finger
    assert gap <= open_gap * 0.65


def test_tracking_context_reset_preserves_pose_but_clears_contact():
    retargeter = InspireVisionRetargeter()
    retargeter.retarget(_canonical_pose("index"))
    previous_pose = retargeter._last_independent.copy()

    retargeter.reset_tracking_context()

    np.testing.assert_allclose(retargeter._last_independent, previous_pose)
    assert retargeter.get_contact_status()["state"] == "NONE"


def test_filtered_output_is_reused_as_the_next_solver_state():
    recording_path = (
        Path(__file__).resolve().parents[3]
        / "example"
        / "profiling"
        / "human_joint_right.pkl"
    )
    with recording_path.open("rb") as recording_file:
        frames = pickle.load(recording_file)
    retargeter = InspireVisionRetargeter()

    retargeter.retarget(frames[0])
    retargeter.retarget(frames[len(frames) // 2])

    np.testing.assert_allclose(
        retargeter._last_independent,
        retargeter._last_full[retargeter._target_indices],
    )


def test_recorded_motion_has_bounded_target_step():
    recording_path = (
        Path(__file__).resolve().parents[3]
        / "example"
        / "profiling"
        / "human_joint_right.pkl"
    )
    with recording_path.open("rb") as recording_file:
        frames = pickle.load(recording_file)
    retargeter = InspireVisionRetargeter()
    outputs = [retargeter.retarget(frame)[1] for frame in frames]

    maximum_step = np.abs(np.diff(np.asarray(outputs), axis=0)).max(axis=0)

    assert np.all(maximum_step <= 220), maximum_step.tolist()


def test_thumb_frame_targets_are_orthonormal():
    landmarks = np.zeros((21, 3), dtype=float)
    landmarks[1] = [0.0, 0.0, 0.0]
    landmarks[2] = [1.0, 0.0, 0.0]
    landmarks[5] = [1.0, 2.0, 0.0]

    targets = build_constraint_targets(landmarks)

    np.testing.assert_allclose(targets.frame_primary, [1.0, 0.0, 0.0])
    np.testing.assert_allclose(targets.frame_secondary, [0.0, 1.0, 0.0])
    assert np.dot(targets.frame_primary, targets.frame_secondary) == 0.0


def test_non_tracking_snapshot_never_serializes_targets():
    snapshot = TrackingSnapshot(
        status=TrackingStatus.LOST,
        sequence=4,
        captured_at=1.0,
        published_at=1.1,
        joints={"index_proximal_joint": 0.5},
        actuators=[500] * 6,
    )

    payload = snapshot.to_payload()

    assert payload["joints"] is None
    assert payload["actuators"] is None
    assert payload["contact"] is None


def test_profile_calibration_auto_captures_five_stable_poses():
    session = ProfileCalibrationSession("profile-1", required_samples=3, window_size=2)
    opposed = _canonical_pose("index")
    opposed[4, 0] += 0.1
    poses = {
        "open": _canonical_pose(),
        "relaxed": _all_fingers_curl(0.35),
        "fist": _all_fingers_curl(1.15),
        "thumb_opposition": opposed,
        "ok": _canonical_pose("index"),
    }

    for pose in session.poses:
        for _ in range(4):
            session.observe(poses[pose], confidence=0.95)

    status = session.status()
    calibration = session.completed_calibration()
    assert status["state"] == "COMPLETE"
    assert status["pose_index"] == 5
    assert calibration["mode"] == "five_pose"
    assert set(calibration["poses"]) == set(session.poses)
    assert calibration["contact_enter_ratio"] < calibration["contact_release_ratio"]


def test_profile_calibration_rejects_low_confidence_and_unstable_frames():
    session = ProfileCalibrationSession("profile-1", required_samples=3, window_size=2)
    pose = _canonical_pose()

    for _ in range(5):
        session.observe(pose, confidence=0.5)
    assert session.status()["accepted_samples"] == 0

    session.observe(pose, confidence=0.95)
    session.observe(pose + np.linspace(0, 0.05, 63).reshape(21, 3), confidence=0.95)
    assert session.status()["accepted_samples"] == 0


def test_switching_profile_resets_temporal_context_without_moving_pose():
    retargeter = InspireVisionRetargeter()
    retargeter.retarget(_canonical_pose("index"))
    previous_pose = retargeter._last_independent.copy()

    retargeter.set_operator_profile(
        {
            "id": "operator-a",
            "name": "Operator A",
            "calibration": None,
        }
    )

    np.testing.assert_allclose(retargeter._last_independent, previous_pose)
    assert retargeter.get_contact_status()["state"] == "NONE"
    assert retargeter.get_operator_profile()["id"] == "operator-a"


def test_profile_switch_waits_for_in_flight_retarget_frame(monkeypatch):
    retargeter = InspireVisionRetargeter()
    entered = threading.Event()
    release = threading.Event()
    switched = threading.Event()
    original_filter = retargeter._filter_landmarks

    def blocking_filter(landmarks):
        entered.set()
        assert release.wait(timeout=2.0)
        return original_filter(landmarks)

    monkeypatch.setattr(retargeter, "_filter_landmarks", blocking_filter)
    retarget_thread = threading.Thread(target=retargeter.retarget, args=(_canonical_pose(),))
    switch_thread = threading.Thread(
        target=lambda: (
            retargeter.set_operator_profile(
                {"id": "operator-b", "name": "Operator B", "calibration": None}
            ),
            switched.set(),
        )
    )

    retarget_thread.start()
    assert entered.wait(timeout=2.0)
    switch_thread.start()
    try:
        assert not switched.wait(timeout=0.1)
    finally:
        release.set()
        retarget_thread.join(timeout=3.0)
        switch_thread.join(timeout=3.0)

    assert not retarget_thread.is_alive()
    assert not switch_thread.is_alive()
    assert switched.is_set()
