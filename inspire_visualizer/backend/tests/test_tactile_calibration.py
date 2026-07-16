from pathlib import Path

from inspire_visualizer_api.tactile_calibration import TactileCalibrationDocument, TactileCalibrationStore


def test_calibration_store_round_trips_by_device_endpoint(tmp_path: Path) -> None:
    store = TactileCalibrationStore(tmp_path / "tactile_calibration.json")
    document = TactileCalibrationDocument(side="left", host="192.0.2.11", port=6000, updated_at="2026-07-15T00:00:00Z")
    store.save(document)

    assert store.load("left", "192.0.2.11", 6000, "piezoresistive_v1") == document
    assert store.load("right", "192.0.2.11", 6000, "piezoresistive_v1") is None


def test_calibration_document_accepts_drafts_and_sensor_shape() -> None:
    document = TactileCalibrationDocument.model_validate({
        "side": "left", "host": "192.0.2.11", "port": 6000, "updated_at": "2026-07-15T00:00:00Z",
        "drafts": {"index_tip": {"region_id": "index_tip", "status": "incomplete", "samples": [], "applied": False, "sensor_rows": 12, "sensor_columns": 8}},
    })
    assert document.drafts["index_tip"].sensor_rows == 12
