from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .schema import (
    ACTUATOR_NAMES,
    CONNECTION_STATES,
    CONTACT_FINGERS,
    CONTACT_STATES,
    CONTROL_STATES,
    HANDEDNESS,
    ROBOT_FIELDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    TACTILE_FIELDS,
    TRACKING_STATES,
    Field,
    enum_json,
    frame_fields,
)


class _StreamWriter:
    def __init__(self, file: h5py.File, fields: Sequence[Field], batch_size: int = 32):
        self.file = file
        self.fields = tuple(fields)
        self.batch_size = batch_size
        self.buffers: dict[str, list[Any]] = {field.path: [] for field in self.fields}
        self.datasets: dict[str, h5py.Dataset] = {}
        for field in self.fields:
            parent, _, name = field.path.rpartition("/")
            group = file.require_group(parent)
            chunks = (max(1, min(batch_size, 64)), *field.shape)
            self.datasets[field.path] = group.create_dataset(
                name,
                shape=(0, *field.shape),
                maxshape=(None, *field.shape),
                chunks=chunks,
                dtype=field.dtype,
                compression="gzip",
                compression_opts=4,
                shuffle=True,
            )

    @property
    def buffered(self) -> int:
        first = self.fields[0].path
        return len(self.buffers[first])

    def append(self, row: Mapping[str, Any]) -> None:
        for field in self.fields:
            value = row.get(field.path, field.fill)
            if field.shape:
                array = np.asarray(value, dtype=field.dtype)
                if array.shape != field.shape:
                    array = np.full(field.shape, field.fill, dtype=field.dtype)
                value = array
            self.buffers[field.path].append(value)
        if self.buffered >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        count = self.buffered
        if count == 0:
            return
        for field in self.fields:
            dataset = self.datasets[field.path]
            start = len(dataset)
            dataset.resize(start + count, axis=0)
            dataset[start:] = np.asarray(self.buffers[field.path], dtype=field.dtype)
            self.buffers[field.path].clear()


class HDF5EpisodeWriter:
    """Append-only, crash-identifiable HDF5 writer for one hand episode."""

    def __init__(
        self,
        final_path: Path,
        *,
        metadata: Mapping[str, Any],
        joint_names: Sequence[str],
        tactile_layout: Sequence[Mapping[str, Any]],
        flush_interval: float = 1.0,
    ):
        self.final_path = Path(final_path)
        self.partial_path = self.final_path.with_suffix(".partial.h5")
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        if self.final_path.exists() or self.partial_path.exists():
            raise FileExistsError(self.final_path)
        self.file = h5py.File(self.partial_path, "w", libver="latest")
        self.file.attrs.update(
            {
                "schema": SCHEMA_NAME,
                "schema_version": SCHEMA_VERSION,
                "complete": False,
                "side": "right",
                "robot_model": "RH56DFTP",
                "created_at": time.time(),
                "metadata_json": json.dumps(dict(metadata), ensure_ascii=True),
            }
        )
        frames = self.file.require_group("frames")
        frames.attrs["joint_names_json"] = json.dumps(list(joint_names))
        frames.attrs["actuator_names_json"] = json.dumps(ACTUATOR_NAMES)
        frames.attrs["tracking_states_json"] = enum_json(TRACKING_STATES)
        frames.attrs["control_states_json"] = enum_json(CONTROL_STATES)
        frames.attrs["contact_states_json"] = enum_json(CONTACT_STATES)
        frames.attrs["contact_fingers_json"] = enum_json(CONTACT_FINGERS)
        frames.attrs["handedness_json"] = enum_json(HANDEDNESS)
        self.file.require_group("robot").attrs["connection_states_json"] = enum_json(
            CONNECTION_STATES
        )
        self.file.require_group("tactile").attrs["layout_json"] = json.dumps(
            list(tactile_layout)
        )
        self.frames = _StreamWriter(self.file, frame_fields(len(joint_names)))
        self.robot = _StreamWriter(self.file, ROBOT_FIELDS)
        self.tactile = _StreamWriter(self.file, TACTILE_FIELDS, batch_size=16)
        event_type = h5py.string_dtype(encoding="utf-8")
        events = self.file.require_group("events")
        self._event_time = events.create_dataset("elapsed", (0,), maxshape=(None,), dtype=np.float64)
        self._event_kind = events.create_dataset("kind", (0,), maxshape=(None,), dtype=event_type)
        self._event_detail = events.create_dataset("detail", (0,), maxshape=(None,), dtype=event_type)
        self.flush_interval = flush_interval
        self._last_flush = time.monotonic()
        self._closed = False

    def append_frame(self, row: Mapping[str, Any]) -> None:
        self.frames.append(row)
        self._periodic_flush()

    def append_robot(self, row: Mapping[str, Any]) -> None:
        self.robot.append(row)
        self._periodic_flush()

    def append_tactile(self, row: Mapping[str, Any]) -> None:
        self.tactile.append(row)
        self._periodic_flush()

    def event(self, elapsed: float, kind: str, detail: str = "") -> None:
        index = len(self._event_time)
        for dataset in (self._event_time, self._event_kind, self._event_detail):
            dataset.resize(index + 1, axis=0)
        self._event_time[index] = elapsed
        self._event_kind[index] = kind
        self._event_detail[index] = detail

    def flush(self) -> None:
        self.frames.flush()
        self.robot.flush()
        self.tactile.flush()
        self.file.flush()
        self._last_flush = time.monotonic()

    def close(self, *, complete: bool, summary: Mapping[str, Any] | None = None) -> Path:
        if self._closed:
            return self.final_path if complete else self.partial_path
        self.flush()
        self.file.attrs["complete"] = complete
        self.file.attrs["closed_at"] = time.time()
        if summary is not None:
            self.file.attrs["summary_json"] = json.dumps(dict(summary), ensure_ascii=True)
        self.file.flush()
        self.file.close()
        self._closed = True
        if complete:
            os.replace(self.partial_path, self.final_path)
            return self.final_path
        return self.partial_path

    def _periodic_flush(self) -> None:
        if time.monotonic() - self._last_flush >= self.flush_interval:
            self.flush()
