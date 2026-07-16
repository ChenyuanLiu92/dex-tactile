from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from .schema import (
    CONNECTION_STATES,
    CONTACT_FINGERS,
    CONTACT_STATES,
    CONTROL_STATES,
    HANDEDNESS,
    TRACKING_STATES,
)
from .sources import HandDataSource, LatestFrame, select_source
from .writer import HDF5EpisodeWriter


@dataclass(frozen=True)
class CollectionOptions:
    task: str
    operator: str
    output: Path
    duration: float | None = None
    source: str = "auto"
    viewer_url: str = "http://127.0.0.1:8787"
    startup_timeout: float = 30.0
    frequency: float = 30.0


def _episode_path(output: Path, task: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", task).strip("-").lower() or "episode"
    return output / f"{timestamp}_{slug}_{uuid.uuid4().hex[:8]}.h5"


def _right_hand(device: dict[str, Any] | None) -> dict[str, Any] | None:
    if not device:
        return None
    hand = device.get("hands", {}).get("right")
    return hand if isinstance(hand, dict) else None


def _tactile_layout(payload: dict[str, Any]) -> list[dict[str, Any]]:
    layout: list[dict[str, Any]] = []
    offset = 0
    for region in payload.get("regions", []):
        rows = int(region["rows"])
        columns = int(region["columns"])
        length = rows * columns
        layout.append(
            {
                "id": str(region["id"]),
                "rows": rows,
                "columns": columns,
                "offset": offset,
                "length": length,
            }
        )
        offset += length
    if len(layout) != 17 or offset != 1062:
        raise RuntimeError(f"Expected 17 tactile regions and 1062 taxels, got {len(layout)} and {offset}")
    return layout


async def _wait_ready(
    source: HandDataSource, timeout: float
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last_report = 0.0
    while time.monotonic() < deadline:
        frame = source.latest_frame().payload
        hand = _right_hand(source.latest_device())
        tactile = source.latest_tactile()
        tracking_ready = bool(
            frame
            and frame.get("status") == "TRACKING"
            and frame.get("landmarks_3d") is not None
            and frame.get("joints")
        )
        robot_ready = bool(
            hand
            and hand.get("connection") == "online"
            and hand.get("actual_angles") is not None
        )
        tactile_ready = bool(tactile and tactile.get("profile") == "piezoresistive_v1")
        if tracking_ready and robot_ready and tactile_ready:
            assert frame is not None
            assert hand is not None
            assert tactile is not None
            return frame, hand, tactile
        now = time.monotonic()
        if now - last_report >= 1.0:
            print(
                "Waiting for data: "
                f"tracking={'ok' if tracking_ready else 'waiting'} "
                f"robot={'ok' if robot_ready else 'waiting'} "
                f"tactile={'ok' if tactile_ready else 'waiting'}"
            )
            last_report = now
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Hand data sources were not ready within {timeout:g} seconds")


def _array(value: Any, shape: tuple[int, ...], dtype, fill) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=dtype)
    except (TypeError, ValueError):
        result = np.empty((0,), dtype=dtype)
    if result.shape != shape:
        return np.full(shape, fill, dtype=dtype)
    return result


def _state_code(mapping: dict[str, int], value: Any, default: int = 0) -> int:
    return mapping.get(value, default) if isinstance(value, str) else default


def _frame_row(
    latest: LatestFrame,
    *,
    elapsed: float,
    wall: float,
    start_monotonic: float,
    joint_names: list[str],
) -> dict[str, Any]:
    payload = latest.payload or {}
    fresh = latest.connected and time.monotonic() - latest.received_at <= 0.25
    status = str(payload.get("status", "DISCONNECTED")) if fresh else "DISCONNECTED"
    valid = status == "TRACKING"
    raw_control = payload.get("control")
    raw_contact = payload.get("contact")
    raw_joints = payload.get("joints")
    control: dict[str, Any] = raw_control if isinstance(raw_control, dict) else {}
    contact: dict[str, Any] = raw_contact if isinstance(raw_contact, dict) else {}
    joints: dict[str, Any] = raw_joints if valid and isinstance(raw_joints, dict) else {}
    return {
        "frames/time/elapsed": elapsed,
        "frames/time/wall": wall,
        "frames/time/source_received": latest.received_at - start_monotonic if fresh else np.nan,
        "frames/time/source_captured": payload.get("captured_at", np.nan),
        "frames/time/source_published": payload.get("published_at", np.nan),
        "frames/source_sequence": payload.get("sequence", -1),
        "frames/source_connected": fresh,
        "frames/tracking/status": TRACKING_STATES.get(status, TRACKING_STATES["DISCONNECTED"]),
        "frames/tracking/valid": valid,
        "frames/tracking/handedness": HANDEDNESS.get(
            payload.get("handedness") if isinstance(payload.get("handedness"), str) else None,
            -1,
        ),
        "frames/tracking/confidence": payload.get("confidence", np.nan),
        "frames/tracking/landmarks_2d": _array(
            payload.get("landmarks_2d") if valid else None, (21, 2), np.float32, np.nan
        ),
        "frames/tracking/landmarks_3d": _array(
            payload.get("landmarks_3d") if valid else None, (21, 3), np.float32, np.nan
        ),
        "frames/retargeting/joints": np.asarray(
            [joints.get(name, np.nan) for name in joint_names], dtype=np.float32
        ),
        "frames/retargeting/actuator_targets": _array(
            payload.get("actuators") if valid else None, (6,), np.int16, -1
        ),
        "frames/contact/state": _state_code(CONTACT_STATES, contact.get("state")),
        "frames/contact/finger": CONTACT_FINGERS.get(
            contact.get("finger") if isinstance(contact.get("finger"), str) else None,
            -1,
        ),
        "frames/contact/human_distance_mm": contact.get("human_distance_mm", np.nan),
        "frames/contact/projected_distance_mm": contact.get("projected_distance_mm", np.nan),
        "frames/control/state": _state_code(CONTROL_STATES, control.get("state")),
        "frames/control/connected": bool(control.get("connected", False)),
        "frames/control/actual": _array(control.get("actual"), (6,), np.int16, -1),
        "frames/control/targets": _array(control.get("targets"), (6,), np.int16, -1),
        "frames/control/commanded": _array(control.get("commanded"), (6,), np.int16, -1),
        "frames/control/speeds": _array(control.get("speeds"), (6,), np.int16, -1),
        "frames/control/modbus_output": bool(control.get("modbus_output", False)),
        "frames/control/tracking_hold": bool(control.get("tracking_hold", False)),
    }


def _robot_row(hand: dict[str, Any], elapsed: float, wall: float) -> dict[str, Any]:
    return {
        "robot/time/elapsed": elapsed,
        "robot/time/wall": wall,
        "robot/time/source_updated": hand.get("updated_at", np.nan),
        "robot/connection": _state_code(CONNECTION_STATES, hand.get("connection")),
        "robot/armed": bool(hand.get("armed", False)),
        "robot/actual": _array(hand.get("actual_angles"), (6,), np.int16, -1),
    }


def _tactile_row(payload: dict[str, Any], start_wall: float) -> dict[str, Any]:
    values = [value for region in payload.get("regions", []) for value in region.get("values", [])]
    if len(values) != 1062:
        raise ValueError(f"Expected 1062 tactile values, got {len(values)}")
    received = float(payload.get("received_at", time.time()))
    return {
        "tactile/time/elapsed": max(0.0, received - start_wall),
        "tactile/time/wall": received,
        "tactile/time/source_captured": payload.get("captured_at", np.nan),
        "tactile/source_sequence": payload.get("sequence", -1),
        "tactile/values": np.asarray(values, dtype=np.uint16),
    }


async def collect_episode(options: CollectionOptions) -> Path:
    source = select_source(options.source, options.viewer_url)
    print(f"Data source: {source.mode}")
    await source.start()
    writer: HDF5EpisodeWriter | None = None
    completed = False
    try:
        initial_frame, _, initial_tactile = await _wait_ready(source, options.startup_timeout)
        joint_names = list(initial_frame["joints"].keys())
        if len(joint_names) != 12:
            raise RuntimeError(f"Expected 12 retargeting joints, got {len(joint_names)}")
        layout = _tactile_layout(initial_tactile)
        path = _episode_path(options.output, options.task)
        writer = HDF5EpisodeWriter(
            path,
            metadata={
                "task": options.task,
                "operator": options.operator,
                "source_mode": source.mode,
                "viewer_url": options.viewer_url if source.mode == "viewer" else None,
                "frame_frequency_hz": options.frequency,
                "contains_rgb": False,
                "contains_depth": False,
                "contains_arm": False,
            },
            joint_names=joint_names,
            tactile_layout=layout,
        )
        start_monotonic = time.monotonic()
        start_wall = time.time()
        writer.event(0.0, "recording_started", source.mode)
        print(f"Recording started: {writer.partial_path}")
        print("Press Ctrl+C to finish and finalize the episode.")
        period = 1.0 / options.frequency
        next_tick = start_monotonic
        last_robot_update = None
        last_tracking_status = None
        frame_count = robot_count = tactile_count = invalid_count = 0
        reason = "duration_reached" if options.duration is not None else "operator_stop"
        try:
            while True:
                now = time.monotonic()
                elapsed = now - start_monotonic
                if options.duration is not None and elapsed >= options.duration:
                    break
                latest = source.latest_frame()
                row = _frame_row(
                    latest,
                    elapsed=elapsed,
                    wall=time.time(),
                    start_monotonic=start_monotonic,
                    joint_names=joint_names,
                )
                writer.append_frame(row)
                frame_count += 1
                if not row["frames/tracking/valid"]:
                    invalid_count += 1
                status = int(row["frames/tracking/status"])
                if status != last_tracking_status:
                    writer.event(elapsed, "tracking_state", str(status))
                    last_tracking_status = status

                hand = _right_hand(source.latest_device())
                if hand and hand.get("updated_at") != last_robot_update:
                    writer.append_robot(_robot_row(hand, elapsed, time.time()))
                    last_robot_update = hand.get("updated_at")
                    robot_count += 1

                for tactile in source.drain_tactile():
                    try:
                        writer.append_tactile(_tactile_row(tactile, start_wall))
                        tactile_count += 1
                    except ValueError as error:
                        writer.event(elapsed, "invalid_tactile_frame", str(error))

                next_tick += period
                await asyncio.sleep(max(0.0, next_tick - time.monotonic()))
        except asyncio.CancelledError:
            reason = "operator_interrupt"
        duration = time.monotonic() - start_monotonic
        summary = {
            "duration_seconds": duration,
            "frame_count": frame_count,
            "robot_count": robot_count,
            "tactile_count": tactile_count,
            "tracking_invalid_count": invalid_count,
            "tracking_invalid_ratio": invalid_count / frame_count if frame_count else 1.0,
            "end_reason": reason,
        }
        writer.event(duration, "recording_finished", reason)
        output = writer.close(complete=True, summary=summary)
        completed = True
        print(
            f"Saved {output}: {duration:.1f}s, frames={frame_count}, "
            f"robot={robot_count}, tactile={tactile_count}, "
            f"tracking_invalid={summary['tracking_invalid_ratio']:.1%}"
        )
        return output
    finally:
        if writer is not None and not completed:
            partial = writer.close(complete=False, summary={"end_reason": "error"})
            print(f"Recording did not complete; recoverable partial file: {partial}")
        await source.stop()
