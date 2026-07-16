import asyncio
from collections import deque

import h5py
import numpy as np

from hand_data_collection.collector import CollectionOptions, collect_episode
from hand_data_collection.sources import LatestFrame


def tactile_frame(sequence=1):
    lengths = [9, 96, 80, 9, 96, 80, 9, 96, 80, 9, 96, 80, 9, 96, 9, 96, 112]
    regions = []
    for index, length in enumerate(lengths):
        regions.append(
            {"id": f"region_{index}", "rows": 1, "columns": length, "values": [sequence] * length}
        )
    return {
        "type": "tactile_frame",
        "side": "right",
        "profile": "piezoresistive_v1",
        "sequence": sequence,
        "captured_at": 10.0,
        "received_at": 10.0,
        "regions": regions,
    }


def tracking_frame(status="TRACKING"):
    valid = status == "TRACKING"
    return {
        "status": status,
        "sequence": 4,
        "captured_at": 10.0,
        "published_at": 10.01,
        "handedness": "Right",
        "confidence": 0.95,
        "landmarks_2d": [[0.1, 0.2]] * 21 if valid else None,
        "landmarks_3d": [[0.0, 0.0, 0.0]] * 21 if valid else None,
        "joints": {f"joint_{index}": 0.1 for index in range(12)} if valid else None,
        "actuators": [900] * 6 if valid else None,
        "contact": {"state": "NONE", "finger": None, "projected_distance_mm": 5.0},
        "control": {
            "state": "DISARMED",
            "connected": True,
            "actual": [900] * 6,
            "targets": [900] * 6,
            "commanded": [900] * 6,
            "speeds": None,
            "modbus_output": False,
            "tracking_hold": False,
        },
    }


class FakeSource:
    mode = "viewer"

    def __init__(self):
        self.frame = tracking_frame()
        self.tactile = tactile_frame()
        self.queue = deque([self.tactile])
        self.frame_reads = 0

    async def start(self):
        return None

    async def stop(self):
        return None

    def latest_frame(self):
        self.frame_reads += 1
        return LatestFrame(self.frame, asyncio.get_running_loop().time(), True)

    def latest_device(self):
        return {
            "hands": {
                "right": {
                    "connection": "online",
                    "actual_angles": [800] * 6,
                    "armed": False,
                    "updated_at": 10.0,
                }
            }
        }

    def latest_tactile(self):
        return self.tactile

    def drain_tactile(self):
        result = list(self.queue)
        self.queue.clear()
        return result


def test_collect_episode_writes_three_native_streams(monkeypatch, tmp_path):
    source = FakeSource()
    monkeypatch.setattr("hand_data_collection.collector.select_source", lambda *_: source)
    output = asyncio.run(
        collect_episode(
            CollectionOptions(
                task="pinch",
                operator="tester",
                output=tmp_path,
                duration=0.08,
                frequency=30,
            )
        )
    )

    with h5py.File(output, "r") as file:
        assert len(file["frames/time/elapsed"]) >= 2
        assert len(file["robot/time/elapsed"]) == 1
        assert len(file["tactile/time/elapsed"]) == 1
        assert np.all(file["frames/tracking/valid"][:])
        assert not np.any(file["frames/control/modbus_output"][:])


def test_short_tracking_loss_keeps_timeline_and_writes_invalid_mask(monkeypatch, tmp_path):
    source = FakeSource()
    original_latest = source.latest_frame

    def latest_with_loss():
        latest = original_latest()
        if source.frame_reads in {3, 4}:
            return LatestFrame(tracking_frame("LOST"), latest.received_at, True)
        return latest

    source.latest_frame = latest_with_loss
    monkeypatch.setattr("hand_data_collection.collector.select_source", lambda *_: source)
    output = asyncio.run(
        collect_episode(
            CollectionOptions(
                task="tracking loss",
                operator="tester",
                output=tmp_path,
                duration=0.15,
                frequency=30,
            )
        )
    )

    with h5py.File(output, "r") as file:
        valid = file["frames/tracking/valid"][:]
        assert len(valid) >= 4
        assert np.any(~valid)
        assert np.any(valid)
        missing = file["frames/tracking/landmarks_3d"][:][~valid]
        assert np.all(np.isnan(missing))
