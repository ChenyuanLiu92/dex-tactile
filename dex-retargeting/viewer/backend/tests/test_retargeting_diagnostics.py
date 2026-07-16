from collections import Counter

from viewer.backend.retargeting import InspireVisionRetargeter
from viewer.tools.retargeting_diagnostics import (
    canonical_open_pose,
    common_gesture_scenarios,
    curl_finger,
    curl_thumb,
    pinch_pose,
    run_offline_diagnostics,
    summarize_live_frames,
    tripod_pinch_pose,
)


def _settle(retargeter, landmarks, frames=12):
    actuators = [1000] * 6
    for _ in range(frames):
        _, actuators = retargeter.retarget(landmarks)
    return actuators


def test_common_gesture_diagnostics_pass():
    results = run_offline_diagnostics()

    assert {result.name for result in results} >= {
        "open",
        "fist",
        "hook_grasp",
        "point",
        "tabletop",
        "thumbs_up",
        "victory",
        "curl_index",
        "curl_middle",
        "curl_ring",
        "curl_pinky",
        "mcp_index",
        "mcp_middle",
        "mcp_ring",
        "mcp_pinky",
        "pinch_index",
        "pinch_middle",
        "pinch_ring",
        "pinch_pinky",
        "tripod_pinch",
    }
    assert all(result.passed for result in results), [
        result for result in results if not result.passed
    ]


def test_index_flexion_response_is_monotonic():
    retargeter = InspireVisionRetargeter()
    open_pose = canonical_open_pose()
    _settle(retargeter, open_pose, 8)

    outputs = [
        _settle(retargeter, curl_finger(open_pose, "index", bend), 6)[3]
        for bend in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25)
    ]

    assert all(first > second for first, second in zip(outputs, outputs[1:]))
    assert outputs[0] > 950
    assert outputs[-1] < 600


def test_fist_release_returns_all_channels_to_open():
    scenarios = {item.name: item for item in common_gesture_scenarios()}
    retargeter = InspireVisionRetargeter()
    _settle(retargeter, canonical_open_pose(), 8)
    _settle(retargeter, scenarios["fist"].landmarks, 15)

    released = _settle(retargeter, canonical_open_pose(), 12)

    assert all(value > 950 for value in released[:5])
    assert retargeter.get_contact_status()["state"] == "NONE"


def test_tripod_pinch_release_clears_contact_and_reopens_fingers():
    retargeter = InspireVisionRetargeter()
    _settle(retargeter, canonical_open_pose(), 8)
    pinched = _settle(retargeter, tripod_pinch_pose(), 15)

    assert pinched[2] < 750
    assert pinched[3] < 750
    assert retargeter.get_contact_status()["finger"] in {"index", "middle"}

    released = _settle(retargeter, canonical_open_pose(), 12)

    assert released[2] > 950
    assert released[3] > 950
    assert retargeter.get_contact_status()["state"] == "NONE"


def test_live_summary_reports_channel_and_flexion_ranges():
    base = {
        "status": "TRACKING",
        "tracking_fps": 30.0,
        "latency_ms": 12.0,
        "confidence": 0.95,
        "contact_finger": None,
        "modbus_output": False,
    }
    rows = [
        {
            **base,
            "actuators": [1000] * 6,
            "finger_flexion_deg": [0.0] * 4,
        },
        {
            **base,
            "actuators": [1000, 1000, 1000, 500, 1000, 1000],
            "finger_flexion_deg": [0.0, 0.0, 0.0, 90.0],
        },
    ]

    summary = summarize_live_frames(rows, Counter({"TRACKING": 2}))

    assert summary["tracked_frames"] == 2
    assert summary["actuator_ranges"]["index"]["range"] == 500
    assert summary["finger_flexion_ranges_deg"]["index"]["range"] == 90.0
    assert summary["modbus_output_seen"] is False


def test_open_hand_calibration_removes_camera_flexion_bias():
    biased_open = canonical_open_pose()
    for finger in ("index", "middle", "ring", "pinky"):
        biased_open = curl_finger(biased_open, finger, bend=0.45)
    biased_open[1:5] = pinch_pose("index")[1:5]
    retargeter = InspireVisionRetargeter()
    retargeter.start_open_calibration()

    calibrated_output = _settle(retargeter, biased_open, 35)

    calibration = retargeter.get_calibration_status()
    assert calibration["state"] == "CALIBRATED"
    assert all(value > 950 for value in calibrated_output)
    assert calibration["neutral_flexion_deg"] == [25.4, 25.4, 25.4, 25.4]
    assert calibration["neutral_thumb_offset_counts"][0] > 100

    curled_index = curl_finger(biased_open, "index", bend=1.15)
    curled_output = _settle(retargeter, curled_index, 12)

    assert curled_output[3] < 800
    assert all(value > 900 for value in curled_output[:3])

    curled_thumb = curl_thumb(biased_open, bend=1.5)
    thumb_output = _settle(retargeter, curled_thumb, 12)

    assert thumb_output[4] < 800


def test_open_hand_calibration_persists_between_retargeters(tmp_path):
    calibration_path = tmp_path / "retargeting-calibration.json"
    biased_open = canonical_open_pose()
    for finger in ("index", "middle", "ring", "pinky"):
        biased_open = curl_finger(biased_open, finger, bend=0.45)
    first = InspireVisionRetargeter(calibration_path=calibration_path)
    first.start_open_calibration()
    _settle(first, biased_open, 35)

    restored = InspireVisionRetargeter(calibration_path=calibration_path)

    assert calibration_path.is_file()
    assert restored.get_calibration_status()["state"] == "CALIBRATED"
    output = _settle(restored, biased_open, 8)
    assert all(value > 950 for value in output[:4])
