from dataclasses import dataclass

import numpy as np

from viewer.backend.runtime import ViewerRuntime
from viewer.backend.state import TrackingStatus
from viewer.backend.tracking import RightHandTracker, estimate_hand_frame


@dataclass
class Landmark:
    x: float
    y: float
    z: float


class LandmarkList:
    def __init__(self, points):
        self.landmark = [Landmark(*point) for point in points]


class Classification:
    def __init__(self, label, score=0.9):
        self.label = label
        self.score = score


class Handedness:
    def __init__(self, label):
        self.classification = [Classification(label)]


class Results:
    def __init__(self, label=None):
        points = np.zeros((21, 3), dtype=float)
        points[:, 0] = np.linspace(0.0, 0.2, 21)
        points[5] = [0.04, 0.04, 0.0]
        points[9] = [0.0, 0.09, 0.01]
        self.multi_hand_landmarks = None if label is None else [LandmarkList(points)]
        self.multi_hand_world_landmarks = (
            None if label is None else [LandmarkList(points)]
        )
        self.multi_handedness = None if label is None else [Handedness(label)]


class MultiResults:
    def __init__(self, labels):
        point_sets = []
        for offset, _label in enumerate(labels):
            points = np.zeros((21, 3), dtype=float)
            points[:, 0] = np.linspace(0.0, 0.2, 21) + offset * 0.3
            points[5] = [0.04 + offset * 0.3, 0.04, 0.0]
            points[9] = [offset * 0.3, 0.09, 0.01]
            point_sets.append(LandmarkList(points))
        self.multi_hand_landmarks = point_sets
        self.multi_hand_world_landmarks = point_sets
        self.multi_handedness = [Handedness(label) for label in labels]


class FakeHands:
    def __init__(self, results):
        self.results = iter(results)

    def process(self, _rgb):
        return next(self.results)

    def close(self):
        pass


class FakeRetargeter:
    def __init__(self):
        self.reset_count = 0

    def retarget(self, _landmarks):
        return {"index_proximal_joint": 0.25}, [1, 2, 3, 4, 5, 6]

    def get_contact_status(self):
        return {
            "state": "LOCKED",
            "finger": "index",
            "human_distance_mm": 20.0,
            "projected_distance_mm": 5.0,
        }

    def reset_tracking_context(self):
        self.reset_count += 1


class FakeController:
    def __init__(self):
        self.tracking = []

    def update_tracking(self, snapshot):
        self.tracking.append(snapshot)


def test_tracker_accepts_right_and_rejects_left_on_mirrored_input():
    tracker = RightHandTracker(hands=FakeHands([Results("Right"), Results("Left")]))
    frame = np.zeros((360, 640, 3), dtype=np.uint8)

    right = tracker.process(frame)
    left = tracker.process(frame)

    assert right.status is TrackingStatus.TRACKING
    assert right.handedness == "Right"
    assert len(right.landmarks_2d) == 21
    assert left.status is TrackingStatus.WRONG_HAND
    assert left.landmarks_3d is None
    assert len(left.landmarks_2d) == 21
    assert left.detected_hands[0].handedness == "Left"


def test_tracker_reports_both_hands_and_prioritizes_right_for_retargeting():
    tracker = RightHandTracker(hands=FakeHands([MultiResults(["Left", "Right"])]))
    detection = tracker.process(np.zeros((360, 640, 3), dtype=np.uint8))

    assert detection.status is TrackingStatus.TRACKING
    assert detection.handedness == "Right"
    assert [hand.handedness for hand in detection.detected_hands] == ["Left", "Right"]


def test_tracker_reports_searching_without_a_hand():
    tracker = RightHandTracker(hands=FakeHands([Results()]))
    detection = tracker.process(np.zeros((360, 640, 3), dtype=np.uint8))
    assert detection.status is TrackingStatus.SEARCHING


def test_hand_frame_is_orthonormal():
    points = np.zeros((21, 3), dtype=float)
    points[5] = [0.04, 0.04, 0.0]
    points[9] = [0.0, 0.09, 0.01]
    frame = estimate_hand_frame(points)
    np.testing.assert_allclose(frame.T @ frame, np.eye(3), atol=1e-6)


def test_runtime_changes_missing_hand_to_lost_after_tracking():
    controller = FakeController()
    retargeter = FakeRetargeter()
    runtime = ViewerRuntime(
        retargeter=retargeter, controller=controller, start_workers=False
    )
    tracked = runtime.apply_detection(
        sequence=1,
        captured_at=10.0,
        capture_fps=30.0,
        detection=RightHandTracker(hands=FakeHands([Results("Right")])).process(
            np.zeros((360, 640, 3), dtype=np.uint8)
        ),
        now=10.02,
    )
    lost = runtime.apply_detection(
        sequence=2,
        captured_at=10.1,
        capture_fps=30.0,
        detection=RightHandTracker(hands=FakeHands([Results()])).process(
            np.zeros((360, 640, 3), dtype=np.uint8)
        ),
        now=10.12,
    )

    assert tracked.status is TrackingStatus.TRACKING
    assert tracked.actuators == [1, 2, 3, 4, 5, 6]
    assert tracked.contact["finger"] == "index"
    assert lost.status is TrackingStatus.LOST
    assert lost.to_payload()["joints"] is None
    assert retargeter.reset_count == 1
    assert controller.tracking == [tracked, lost]
