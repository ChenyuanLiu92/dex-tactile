from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import websockets

from dex_retargeting.constants import OPERATOR2MANO_RIGHT
from viewer.backend.retargeting import (
    InspireVisionRetargeter,
    build_constraint_targets,
)
from viewer.backend.tracking import estimate_hand_frame


FINGER_LANDMARKS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
FINGER_CHANNELS = {"pinky": 0, "ring": 1, "middle": 2, "index": 3}


@dataclass(frozen=True)
class GestureScenario:
    name: str
    landmarks: np.ndarray
    closed_channels: tuple[int, ...] = ()
    open_channels: tuple[int, ...] = ()
    contact_finger: str | tuple[str, ...] | None = None
    closed_threshold: int = 750


@dataclass(frozen=True)
class GestureResult:
    name: str
    actuators: list[int]
    contact_finger: str | None
    mean_solve_ms: float
    passed: bool
    failures: tuple[str, ...]


def _raw_open_pose() -> np.ndarray:
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
    return points


def _to_mano_frame(points: np.ndarray) -> np.ndarray:
    centered = points - points[0:1]
    return centered @ estimate_hand_frame(centered) @ OPERATOR2MANO_RIGHT


def canonical_open_pose() -> np.ndarray:
    return _to_mano_frame(_raw_open_pose())


def curl_finger(
    landmarks: np.ndarray,
    finger: str,
    bend: float = 1.15,
    mcp_fraction: float = 0.35,
) -> np.ndarray:
    points = np.asarray(landmarks, dtype=float).copy()
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

    points[pip] = origin + lengths[0] * direction(mcp_fraction * bend)
    points[dip] = points[pip] + lengths[1] * direction(0.85 * bend)
    points[tip] = points[dip] + lengths[2] * direction(1.25 * bend)
    return points


def mcp_only_curl(
    landmarks: np.ndarray, finger: str, bend: float = 1.1
) -> np.ndarray:
    points = np.asarray(landmarks, dtype=float).copy()
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
    direction = np.cos(bend) * forward + np.sin(bend) * palm_normal
    points[pip] = origin + lengths[0] * direction
    points[dip] = points[pip] + lengths[1] * direction
    points[tip] = points[dip] + lengths[2] * direction
    return points


def curl_thumb(landmarks: np.ndarray, bend: float = 1.0) -> np.ndarray:
    points = np.asarray(landmarks, dtype=float).copy()
    origin = points[1].copy()
    lengths = (
        np.linalg.norm(points[2] - points[1]),
        np.linalg.norm(points[3] - points[2]),
        np.linalg.norm(points[4] - points[3]),
    )
    forward = points[2] - origin
    forward /= np.linalg.norm(forward)
    across_palm = points[5] - points[17]
    across_palm -= forward * np.dot(across_palm, forward)
    across_palm /= np.linalg.norm(across_palm)
    bend_direction = np.cross(forward, across_palm)
    bend_direction /= np.linalg.norm(bend_direction)

    def direction(angle: float) -> np.ndarray:
        return np.cos(angle) * forward + np.sin(angle) * bend_direction

    points[2] = origin + lengths[0] * direction(0.2 * bend)
    points[3] = points[2] + lengths[1] * direction(0.8 * bend)
    points[4] = points[3] + lengths[2] * direction(1.3 * bend)
    return points


def pinch_pose(finger: str) -> np.ndarray:
    points = _raw_open_pose()
    points[[1, 2, 3, 4]] = [
        [0.020, -0.016, 0.0],
        [0.034, -0.032, 0.0],
        [0.042, -0.048, 0.0],
        [0.038, -0.062, 0.0],
    ]
    finger_start = FINGER_LANDMARKS[finger][0]
    if finger == "index":
        points[[7, 8]] = [[0.027, -0.072, 0.0], [0.032, -0.082, 0.0]]
    else:
        base = points[finger_start].copy()
        contact = points[4] + np.array([0.010, 0.0, 0.0])
        points[finger_start + 1] = 0.65 * base + 0.35 * contact
        points[finger_start + 2] = 0.30 * base + 0.70 * contact
        points[finger_start + 3] = contact
    return _to_mano_frame(points)


def tripod_pinch_pose() -> np.ndarray:
    points = pinch_pose("index")
    base = points[9].copy()
    contact = points[4] + np.array([0.004, 0.0, 0.0])
    points[10] = 0.65 * base + 0.35 * contact
    points[11] = 0.30 * base + 0.70 * contact
    points[12] = contact
    return points


def common_gesture_scenarios() -> tuple[GestureScenario, ...]:
    open_pose = canonical_open_pose()
    scenarios = [
        GestureScenario("open", open_pose, open_channels=(0, 1, 2, 3)),
    ]
    for finger, channel in FINGER_CHANNELS.items():
        scenarios.append(
            GestureScenario(
                f"curl_{finger}",
                curl_finger(open_pose, finger),
                closed_channels=(channel,),
                open_channels=tuple(index for index in range(4) if index != channel),
            )
        )
        scenarios.append(
            GestureScenario(
                f"mcp_{finger}",
                mcp_only_curl(open_pose, finger),
                closed_channels=(channel,),
                open_channels=tuple(index for index in range(4) if index != channel),
                closed_threshold=800,
            )
        )

    fist = open_pose
    for finger in FINGER_LANDMARKS:
        fist = curl_finger(fist, finger)
    scenarios.append(
        GestureScenario(
            "thumbs_up",
            fist.copy(),
            closed_channels=(0, 1, 2, 3),
            open_channels=(4, 5),
        )
    )
    fist[1:5] = pinch_pose("index")[1:5]
    scenarios.append(
        GestureScenario("fist", fist, closed_channels=(0, 1, 2, 3, 4))
    )

    hook = open_pose
    for finger in FINGER_LANDMARKS:
        hook = curl_finger(hook, finger, mcp_fraction=0.0)
    scenarios.append(
        GestureScenario(
            "hook_grasp", hook, closed_channels=(0, 1, 2, 3)
        )
    )

    tabletop = open_pose
    for finger in FINGER_LANDMARKS:
        tabletop = mcp_only_curl(tabletop, finger)
    scenarios.append(
        GestureScenario(
            "tabletop",
            tabletop,
            closed_channels=(0, 1, 2, 3),
            closed_threshold=800,
        )
    )

    point = open_pose
    for finger in ("middle", "ring", "pinky"):
        point = curl_finger(point, finger)
    scenarios.append(
        GestureScenario(
            "point", point, closed_channels=(0, 1, 2), open_channels=(3,)
        )
    )

    victory = open_pose
    for finger in ("ring", "pinky"):
        victory = curl_finger(victory, finger)
    scenarios.append(
        GestureScenario(
            "victory", victory, closed_channels=(0, 1), open_channels=(2, 3)
        )
    )

    for finger, channel in FINGER_CHANNELS.items():
        scenarios.append(
            GestureScenario(
                f"pinch_{finger}",
                pinch_pose(finger),
                closed_channels=(channel,),
                contact_finger=finger,
            )
        )
    scenarios.append(
        GestureScenario(
            "tripod_pinch",
            tripod_pinch_pose(),
            closed_channels=(2, 3),
            contact_finger=("index", "middle"),
        )
    )
    return tuple(scenarios)


def evaluate_scenario(scenario: GestureScenario) -> GestureResult:
    retargeter = InspireVisionRetargeter()
    for _ in range(8):
        retargeter.retarget(canonical_open_pose())
    timings = []
    actuators = [1000] * 6
    for _ in range(15):
        started = time.perf_counter()
        _, actuators = retargeter.retarget(scenario.landmarks)
        timings.append((time.perf_counter() - started) * 1000.0)

    contact_finger = retargeter.get_contact_status()["finger"]
    failures = []
    for channel in scenario.closed_channels:
        if actuators[channel] >= scenario.closed_threshold:
            failures.append(
                f"channel {channel} remained at {actuators[channel]}"
            )
    for channel in scenario.open_channels:
        if actuators[channel] <= 900:
            failures.append(f"channel {channel} leaked to {actuators[channel]}")
    expected_contacts = (
        scenario.contact_finger
        if isinstance(scenario.contact_finger, tuple)
        else (scenario.contact_finger,)
    )
    if contact_finger not in expected_contacts:
        failures.append(
            f"contact was {contact_finger!r}, expected {scenario.contact_finger!r}"
        )
    return GestureResult(
        name=scenario.name,
        actuators=actuators,
        contact_finger=contact_finger,
        mean_solve_ms=round(float(np.mean(timings)), 3),
        passed=not failures,
        failures=tuple(failures),
    )


def run_offline_diagnostics() -> tuple[GestureResult, ...]:
    return tuple(evaluate_scenario(item) for item in common_gesture_scenarios())


def summarize_live_frames(rows: list[dict], status_counts: Counter) -> dict:
    tracked = [row for row in rows if row["status"] == "TRACKING"]
    summary = {
        "frames": len(rows),
        "tracked_frames": len(tracked),
        "status_counts": dict(status_counts),
        "modbus_output_seen": any(row["modbus_output"] for row in rows),
    }
    if not tracked:
        return summary

    actuator_values = np.asarray([row["actuators"] for row in tracked], dtype=int)
    flexion_values = np.asarray(
        [row["finger_flexion_deg"] for row in tracked], dtype=float
    )
    summary.update(
        {
            "mean_tracking_fps": round(
                float(np.mean([row["tracking_fps"] for row in tracked])), 2
            ),
            "mean_latency_ms": round(
                float(np.mean([row["latency_ms"] for row in tracked])), 2
            ),
            "mean_confidence": round(
                float(np.mean([row["confidence"] for row in tracked])), 3
            ),
            "actuator_ranges": {
                name: {
                    "min": int(actuator_values[:, index].min()),
                    "max": int(actuator_values[:, index].max()),
                    "range": int(np.ptp(actuator_values[:, index])),
                }
                for index, name in enumerate(
                    ("pinky", "ring", "middle", "index", "thumb_pitch", "thumb_yaw")
                )
            },
            "finger_flexion_ranges_deg": {
                name: {
                    "min": round(float(flexion_values[:, index].min()), 1),
                    "max": round(float(flexion_values[:, index].max()), 1),
                    "range": round(float(np.ptp(flexion_values[:, index])), 1),
                }
                for index, name in enumerate(("pinky", "ring", "middle", "index"))
            },
            "contact_counts": dict(
                Counter(row["contact_finger"] or "none" for row in tracked)
            ),
        }
    )
    distance_rows = [
        row["thumb_tip_distances_mm"]
        for row in tracked
        if row.get("thumb_tip_distances_mm") is not None
    ]
    if distance_rows:
        distances = np.asarray(distance_rows, dtype=float)
        summary["thumb_tip_distance_ranges_mm"] = {
            name: {
                "min": round(float(distances[:, index].min()), 1),
                "max": round(float(distances[:, index].max()), 1),
            }
            for index, name in enumerate(("index", "middle", "ring", "pinky"))
        }
    distance_2d_rows = [
        row["thumb_tip_distances_palm_width"]
        for row in tracked
        if row.get("thumb_tip_distances_palm_width") is not None
    ]
    if distance_2d_rows:
        distances_2d = np.asarray(distance_2d_rows, dtype=float)
        summary["thumb_tip_distance_ranges_palm_width"] = {
            name: {
                "min": round(float(distances_2d[:, index].min()), 3),
                "max": round(float(distances_2d[:, index].max()), 3),
            }
            for index, name in enumerate(("index", "middle", "ring", "pinky"))
        }
    return summary


async def capture_live_diagnostics(
    url: str, seconds: float, output: Path | None = None
) -> dict:
    rows: list[dict] = []
    status_counts: Counter = Counter()
    last_sequence: int | None = None
    deadline = time.monotonic() + seconds
    async with websockets.connect(url, proxy=None) as websocket:
        while time.monotonic() < deadline:
            timeout = max(0.1, deadline - time.monotonic())
            try:
                payload = json.loads(
                    await asyncio.wait_for(websocket.recv(), timeout=timeout)
                )
            except TimeoutError:
                break
            sequence = int(payload.get("sequence") or 0)
            if sequence == last_sequence:
                continue
            last_sequence = sequence
            status = str(payload.get("status") or "UNKNOWN")
            status_counts[status] += 1
            control = payload.get("control") or {}
            row = {
                "sequence": sequence,
                "status": status,
                "captured_at": payload.get("captured_at"),
                "tracking_fps": float(payload.get("tracking_fps") or 0.0),
                "latency_ms": float(payload.get("latency_ms") or 0.0),
                "confidence": float(payload.get("confidence") or 0.0),
                "actuators": payload.get("actuators"),
                "contact_finger": (payload.get("contact") or {}).get("finger"),
                "control_state": control.get("state"),
                "modbus_output": bool(control.get("modbus_output")),
                "control_actual": control.get("actual"),
                "control_commanded": control.get("commanded"),
                "control_speeds": control.get("speeds"),
                "finger_flexion_deg": None,
                "thumb_tip_distances_mm": None,
                "thumb_tip_distances_palm_width": None,
            }
            landmarks = payload.get("landmarks_3d")
            if status == "TRACKING" and landmarks and row["actuators"]:
                targets = build_constraint_targets(np.asarray(landmarks, dtype=float))
                row["finger_flexion_deg"] = [
                    round(float(np.degrees(value)), 2)
                    for value in targets.finger_flexions
                ]
                row["thumb_tip_distances_mm"] = [
                    round(float(value * 1000.0), 2)
                    for value in targets.human_distances
                ]
                landmarks_2d = payload.get("landmarks_2d")
                if landmarks_2d:
                    points_2d = np.asarray(landmarks_2d, dtype=float)
                    palm_width = max(
                        float(np.linalg.norm(points_2d[5] - points_2d[17])),
                        1e-6,
                    )
                    row["thumb_tip_distances_palm_width"] = [
                        round(
                            float(
                                np.linalg.norm(points_2d[tip] - points_2d[4])
                                / palm_width
                            ),
                            4,
                        )
                        for tip in (8, 12, 16, 20)
                    ]
            rows.append(row)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    return summarize_live_frames(rows, status_counts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic RH56 retargeting gesture diagnostics."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--live-seconds",
        type=float,
        default=0.0,
        help="Capture read-only Viewer telemetry for this many seconds.",
    )
    parser.add_argument(
        "--url", default="ws://127.0.0.1:8787/api/ws", help="Viewer WebSocket URL."
    )
    parser.add_argument(
        "--output", type=Path, help="Optional JSONL path for live frame records."
    )
    args = parser.parse_args()
    if args.live_seconds > 0:
        summary = asyncio.run(
            capture_live_diagnostics(args.url, args.live_seconds, args.output)
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary["tracked_frames"] else 2

    results = run_offline_diagnostics()
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print("gesture             result  actuators                       contact  mean_ms")
        for result in results:
            state = "PASS" if result.passed else "FAIL"
            contact = result.contact_finger or "-"
            print(
                f"{result.name:19s} {state:6s}  {str(result.actuators):31s} "
                f"{contact:7s}  {result.mean_solve_ms:7.3f}"
            )
            for failure in result.failures:
                print(f"  {failure}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
