from __future__ import annotations

import json
import math
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STORE_VERSION = 2
EXPORT_VERSION = 1
DEFAULT_PROFILE_ID = "default"


class ProfileError(ValueError):
    pass


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _name(value: object) -> str:
    name = str(value).strip()
    if not name or len(name) > 40:
        raise ProfileError("Profile name must contain 1..40 characters")
    return name


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ProfileError(f"{label} must be finite")
    if positive and result <= 0.0:
        raise ProfileError(f"{label} must be positive")
    return result


def _vector(value: object, length: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ProfileError(f"{label} requires {length} values")
    return [_number(item, f"{label}[{index}]") for index, item in enumerate(value)]


def _calibration(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError("Profile calibration must be an object")
    mode = value.get("mode")
    if mode not in {"five_pose", "legacy_open"}:
        raise ProfileError("Unsupported profile calibration mode")
    if mode == "five_pose":
        poses = value.get("poses")
        required = ("open", "relaxed", "fist", "thumb_opposition", "ok")
        if not isinstance(poses, dict) or any(pose not in poses for pose in required):
            raise ProfileError("Five-pose calibration is incomplete")
        for pose in required:
            metrics = poses[pose]
            if not isinstance(metrics, dict):
                raise ProfileError(f"Calibration pose {pose} must be an object")
            _vector(
                metrics.get("finger_flexions"),
                4,
                f"Calibration pose {pose} finger flexions",
            )
            _number(metrics.get("thumb_flexion"), f"Calibration pose {pose} thumb flexion")
            _number(
                metrics.get("thumb_opposition"),
                f"Calibration pose {pose} thumb opposition",
            )
            _number(
                metrics.get("pinch_ratio"),
                f"Calibration pose {pose} pinch ratio",
                positive=True,
            )
            _number(
                metrics.get("palm_width"),
                f"Calibration pose {pose} palm width",
                positive=True,
            )
        enter = _number(
            value.get("contact_enter_ratio"),
            "Contact enter ratio",
            positive=True,
        )
        release = _number(
            value.get("contact_release_ratio"),
            "Contact release ratio",
            positive=True,
        )
        if enter >= release:
            raise ProfileError("Contact ratios must be finite and enter must be below release")
    else:
        _vector(value.get("neutral_flexions"), 4, "Legacy neutral flexions")
        _vector(value.get("neutral_thumb_offsets"), 2, "Legacy thumb offsets")
        _number(value.get("neutral_thumb_flexion"), "Legacy thumb flexion")
    return deepcopy(value)


class OperatorProfileStore:
    def __init__(self, path: Path, legacy_path: Path | None = None):
        self.path = Path(path)
        self.legacy_path = Path(legacy_path) if legacy_path is not None else None
        self._lock = threading.RLock()
        self._payload: dict[str, Any] = {
            "version": STORE_VERSION,
            "active_profile_id": DEFAULT_PROFILE_ID,
            "profiles": [],
        }
        self._load()
        if not self.path.exists():
            self._migrate_legacy()

    def list_payload(self) -> dict[str, Any]:
        with self._lock:
            active = self._payload["active_profile_id"]
            profiles = [
                {
                    "id": DEFAULT_PROFILE_ID,
                    "name": "Default",
                    "calibration_state": "DEFAULT",
                    "active": active == DEFAULT_PROFILE_ID,
                    "updated_at": None,
                }
            ]
            profiles.extend(
                {
                    "id": profile["id"],
                    "name": profile["name"],
                    "calibration_state": (
                        "CALIBRATED" if profile.get("calibration") else "UNCALIBRATED"
                    ),
                    "active": active == profile["id"],
                    "updated_at": profile["updated_at"],
                }
                for profile in self._payload["profiles"]
            )
            return {"active_profile_id": active, "profiles": deepcopy(profiles)}

    def create(self, name: str) -> dict[str, Any]:
        with self._lock:
            now = _timestamp()
            profile = {
                "id": uuid.uuid4().hex,
                "name": _name(name),
                "created_at": now,
                "updated_at": now,
                "handedness": "right",
                "calibration": None,
            }
            self._payload["profiles"].append(profile)
            self._save()
            return deepcopy(profile)

    def rename(self, profile_id: str, name: str) -> dict[str, Any]:
        with self._lock:
            profile = self._find(profile_id)
            profile["name"] = _name(name)
            profile["updated_at"] = _timestamp()
            self._save()
            return deepcopy(profile)

    def activate(self, profile_id: str) -> dict[str, Any]:
        with self._lock:
            if profile_id != DEFAULT_PROFILE_ID:
                self._find(profile_id)
            self._payload["active_profile_id"] = profile_id
            self._save()
            return self.active_document()

    def delete(self, profile_id: str) -> None:
        if profile_id == DEFAULT_PROFILE_ID:
            raise ProfileError("The default profile cannot be deleted")
        with self._lock:
            self._find(profile_id)
            self._payload["profiles"] = [
                item for item in self._payload["profiles"] if item["id"] != profile_id
            ]
            if self._payload["active_profile_id"] == profile_id:
                self._payload["active_profile_id"] = DEFAULT_PROFILE_ID
            self._save()

    def set_calibration(
        self, profile_id: str, calibration: dict[str, Any]
    ) -> dict[str, Any]:
        with self._lock:
            profile = self._find(profile_id)
            profile["calibration"] = _calibration(calibration)
            profile["updated_at"] = _timestamp()
            self._save()
            return deepcopy(profile)

    def document(self, profile_id: str) -> dict[str, Any]:
        with self._lock:
            if profile_id == DEFAULT_PROFILE_ID:
                return {
                    "id": DEFAULT_PROFILE_ID,
                    "name": "Default",
                    "handedness": "right",
                    "calibration": None,
                }
            return deepcopy(self._find(profile_id))

    def active_document(self) -> dict[str, Any]:
        with self._lock:
            return self.document(self._payload["active_profile_id"])

    def export_document(self, profile_id: str) -> dict[str, Any]:
        profile = self.document(profile_id)
        if profile_id == DEFAULT_PROFILE_ID:
            raise ProfileError("The default profile has no calibration to export")
        return {
            "version": EXPORT_VERSION,
            "name": profile["name"],
            "handedness": "right",
            "calibration": deepcopy(profile.get("calibration")),
        }

    def import_document(self, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("version") != EXPORT_VERSION:
            raise ProfileError("Unsupported operator profile export")
        if payload.get("handedness", "right") != "right":
            raise ProfileError("Only right-hand profiles are supported")
        calibration = _calibration(payload.get("calibration"))
        profile = self.create(_name(payload.get("name", "")))
        return self.set_calibration(profile["id"], calibration)

    def _find(self, profile_id: str) -> dict[str, Any]:
        for profile in self._payload["profiles"]:
            if profile["id"] == profile_id:
                return profile
        raise ProfileError(f"Unknown operator profile: {profile_id}")

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProfileError(f"Unable to read operator profile store: {error}") from error
        try:
            if not isinstance(payload, dict):
                raise ProfileError("Invalid operator profile store")
            if payload.get("version") != STORE_VERSION:
                raise ProfileError("Unsupported operator profile store")
            if not isinstance(payload.get("profiles"), list):
                raise ProfileError("Invalid operator profile store")
            profile_ids: set[str] = set()
            for profile in payload["profiles"]:
                if not isinstance(profile, dict):
                    raise ProfileError("Invalid operator profile store entry")
                profile_id = profile.get("id")
                if (
                    not isinstance(profile_id, str)
                    or not profile_id
                    or profile_id == DEFAULT_PROFILE_ID
                    or profile_id in profile_ids
                ):
                    raise ProfileError("Invalid or duplicate operator profile id")
                profile_ids.add(profile_id)
                _name(profile.get("name", ""))
                if profile.get("handedness") != "right":
                    raise ProfileError("Only right-hand profiles are supported")
                calibration = profile.get("calibration")
                if calibration is not None:
                    _calibration(calibration)
            self._payload = payload
            active = payload.get("active_profile_id", DEFAULT_PROFILE_ID)
            if active != DEFAULT_PROFILE_ID and active not in profile_ids:
                raise ProfileError("Active profile is missing from operator profile store")
        except (AttributeError, ProfileError) as error:
            raise ProfileError(f"Invalid operator profile store: {error}") from error

    def _migrate_legacy(self) -> None:
        if self.legacy_path is None or not self.legacy_path.is_file():
            return
        try:
            payload = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            calibration = _calibration(
                {
                    "mode": "legacy_open",
                    "neutral_flexions": payload["neutral_flexions"],
                    "neutral_thumb_offsets": payload["neutral_thumb_offsets"],
                    "neutral_thumb_flexion": payload.get(
                        "neutral_thumb_flexion", 0.0
                    ),
                }
            )
        except (OSError, KeyError, json.JSONDecodeError, ProfileError):
            return
        profile = self.create("Legacy calibration")
        self.set_calibration(profile["id"], calibration)
        self.activate(profile["id"])

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._payload, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.path)
