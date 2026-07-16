import json

import h5py
import numpy as np

from hand_data_collection.writer import HDF5EpisodeWriter


JOINTS = [f"joint_{index}" for index in range(12)]
LAYOUT = [
    {"id": f"region_{index}", "rows": 1, "columns": length, "offset": offset, "length": length}
    for index, (offset, length) in enumerate(
        zip(range(0, 1062, 63), [63] * 16 + [54], strict=True)
    )
]


def test_writer_finalizes_atomic_hdf5(tmp_path):
    path = tmp_path / "episode.h5"
    writer = HDF5EpisodeWriter(
        path,
        metadata={"task": "pinch"},
        joint_names=JOINTS,
        tactile_layout=LAYOUT,
    )
    writer.append_frame(
        {
            "frames/time/elapsed": 0.0,
            "frames/tracking/valid": True,
            "frames/tracking/landmarks_3d": np.zeros((21, 3)),
            "frames/retargeting/joints": np.arange(12),
        }
    )
    writer.append_robot({"robot/time/elapsed": 0.0, "robot/actual": [1, 2, 3, 4, 5, 6]})
    writer.append_tactile({"tactile/time/elapsed": 0.0, "tactile/values": np.arange(1062)})
    writer.event(0.0, "started", "test")
    result = writer.close(complete=True, summary={"frame_count": 1})

    assert result == path
    assert path.exists()
    assert not path.with_suffix(".partial.h5").exists()
    with h5py.File(path, "r") as file:
        assert bool(file.attrs["complete"]) is True
        assert file["frames/tracking/landmarks_3d"].shape == (1, 21, 3)
        assert file["robot/actual"][0].tolist() == [1, 2, 3, 4, 5, 6]
        assert file["tactile/values"].shape == (1, 1062)
        assert json.loads(file.attrs["summary_json"])["frame_count"] == 1


def test_writer_keeps_partial_file_on_failure(tmp_path):
    path = tmp_path / "failed.h5"
    writer = HDF5EpisodeWriter(
        path,
        metadata={"task": "test"},
        joint_names=JOINTS,
        tactile_layout=LAYOUT,
    )
    result = writer.close(complete=False)

    assert result.name == "failed.partial.h5"
    assert result.exists()
    assert not path.exists()
    with h5py.File(result, "r") as file:
        assert bool(file.attrs["complete"]) is False
