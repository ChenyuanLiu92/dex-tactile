import json

import pytest

from viewer.backend.operator_profiles import OperatorProfileStore, ProfileError


def five_pose_calibration():
    metrics = {
        "finger_flexions": [0.0] * 4,
        "thumb_flexion": 0.0,
        "thumb_opposition": 0.0,
        "pinch_ratio": 1.0,
        "palm_width": 0.08,
    }
    return {
        "mode": "five_pose",
        "poses": {pose: dict(metrics) for pose in ("open", "relaxed", "fist", "thumb_opposition", "ok")},
        "contact_enter_ratio": 0.3,
        "contact_release_ratio": 0.45,
    }


def test_store_exposes_default_profile_without_writing(tmp_path):
    path = tmp_path / "operator-profiles.json"
    store = OperatorProfileStore(path)

    payload = store.list_payload()

    assert payload["active_profile_id"] == "default"
    assert payload["profiles"] == [
        {
            "id": "default",
            "name": "Default",
            "calibration_state": "DEFAULT",
            "active": True,
            "updated_at": None,
        }
    ]
    assert not path.exists()


def test_profile_lifecycle_persists_and_reloads(tmp_path):
    path = tmp_path / "operator-profiles.json"
    store = OperatorProfileStore(path)
    created = store.create("Operator 01")
    store.activate(created["id"])
    store.rename(created["id"], "Operator A")
    store.set_calibration(created["id"], five_pose_calibration())

    restored = OperatorProfileStore(path)
    payload = restored.list_payload()

    assert payload["active_profile_id"] == created["id"]
    profile = next(item for item in payload["profiles"] if item["id"] == created["id"])
    assert profile["name"] == "Operator A"
    assert profile["calibration_state"] == "CALIBRATED"
    assert restored.active_document()["calibration"]["mode"] == "five_pose"


def test_delete_active_profile_returns_to_default(tmp_path):
    store = OperatorProfileStore(tmp_path / "operator-profiles.json")
    profile = store.create("Temporary")
    store.activate(profile["id"])

    store.delete(profile["id"])

    assert store.list_payload()["active_profile_id"] == "default"


def test_legacy_open_calibration_migrates_without_deleting_source(tmp_path):
    legacy = tmp_path / "retargeting-calibration.json"
    legacy.write_text(
        json.dumps(
            {
                "version": 1,
                "neutral_flexions": [0.1, 0.2, 0.3, 0.4],
                "neutral_thumb_offsets": [0.15, 0.25],
                "neutral_thumb_flexion": 0.12,
            }
        ),
        encoding="utf-8",
    )

    store = OperatorProfileStore(
        tmp_path / "operator-profiles.json", legacy_path=legacy
    )

    active = store.active_document()
    assert active["name"] == "Legacy calibration"
    assert active["calibration"]["mode"] == "legacy_open"
    assert legacy.exists()


def test_export_import_regenerates_identity_and_validates_values(tmp_path):
    source = OperatorProfileStore(tmp_path / "source.json")
    profile = source.create("Portable")
    source.set_calibration(
        profile["id"],
        five_pose_calibration(),
    )

    exported = source.export_document(profile["id"])
    target = OperatorProfileStore(tmp_path / "target.json")
    imported = target.import_document(exported)

    assert imported["id"] != profile["id"]
    assert imported["name"] == "Portable"
    assert target.document(imported["id"])["calibration"]["mode"] == "five_pose"

    with pytest.raises(ProfileError):
        target.import_document({"version": 99, "name": "Bad", "calibration": {}})


def test_rejects_incomplete_five_pose_calibration(tmp_path):
    store = OperatorProfileStore(tmp_path / "profiles.json")
    profile = store.create("Incomplete")

    with pytest.raises(ProfileError, match="incomplete"):
        store.set_calibration(profile["id"], {"mode": "five_pose", "poses": {}})


@pytest.mark.parametrize(
    "mutate",
    [
        lambda calibration: calibration["poses"]["open"].__setitem__(
            "finger_flexions", ["bad", 0.0, 0.0, 0.0]
        ),
        lambda calibration: calibration["poses"]["open"].__setitem__(
            "thumb_flexion", True
        ),
        lambda calibration: calibration["poses"]["open"].__setitem__(
            "palm_width", 0.0
        ),
        lambda calibration: calibration.__setitem__("contact_enter_ratio", -0.1),
    ],
)
def test_rejects_non_numeric_or_non_positive_calibration_values(mutate, tmp_path):
    store = OperatorProfileStore(tmp_path / "profiles.json")
    profile = store.create("Invalid")
    calibration = five_pose_calibration()
    mutate(calibration)

    with pytest.raises(ProfileError):
        store.set_calibration(profile["id"], calibration)


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        json.dumps({"version": 99, "active_profile_id": "default", "profiles": []}),
        json.dumps({"version": 2, "active_profile_id": "missing", "profiles": []}),
    ],
)
def test_corrupt_profile_store_fails_without_silently_resetting(payload, tmp_path):
    path = tmp_path / "operator-profiles.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ProfileError, match="operator profile store"):
        OperatorProfileStore(path)

    assert path.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_profile_names_are_bounded(name, tmp_path):
    store = OperatorProfileStore(tmp_path / "operator-profiles.json")
    with pytest.raises(ProfileError):
        store.create(name)
