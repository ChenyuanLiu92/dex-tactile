from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from .camera import CameraWorker, LatestFrameStore
from .control.controller import ControlState, TransitionError, VisionHandController
from .operator_profiles import OperatorProfileStore
from .realsense_bridge import RealSenseBridgeWorker
from .retargeting import InspireVisionRetargeter
from .state import TrackingSnapshot, TrackingStatus
from .tracking import HandDetection, RightHandTracker


CALIBRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "retargeting-calibration.json"
)
PROFILE_STORE_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "operator-profiles.json"
)


class ViewerRuntime:
    def __init__(
        self,
        retargeter=None,
        tracker=None,
        camera=None,
        controller=None,
        profile_store=None,
        start_workers: bool = True,
    ):
        self.frame_store = LatestFrameStore()
        self.profile_store = profile_store or OperatorProfileStore(
            PROFILE_STORE_PATH, legacy_path=CALIBRATION_PATH
        )
        self.retargeter = retargeter or InspireVisionRetargeter()
        set_profile = getattr(self.retargeter, "set_operator_profile", None)
        if set_profile is not None:
            set_profile(self.profile_store.active_document())
        self.tracker = tracker or RightHandTracker()
        self.camera = camera or self._create_camera()
        self.controller = controller or VisionHandController()
        self.start_workers = start_workers
        self._snapshot = TrackingSnapshot()
        self._snapshot_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._tracking_thread: threading.Thread | None = None
        self._has_tracked = False
        self._last_tracking_at = 0.0
        self._tracking_fps = 0.0
        self._saved_profile_calibration: tuple[str, int] | None = None

    def _create_camera(self):
        source = os.environ.get("D435_CAMERA_SOURCE", "avfoundation").lower()
        rotation = int(os.environ.get("D435_CAMERA_ROTATION", "0"))
        if source == "realsense":
            return RealSenseBridgeWorker(
                self.frame_store,
                socket_path=os.environ.get(
                    "D435_BRIDGE_SOCKET", "/tmp/dex-realsense-rgb.sock"
                ),
                rotation=rotation,
                on_error=self._camera_error,
            )
        if source == "avfoundation":
            return CameraWorker(
                self.frame_store,
                camera_index=int(os.environ.get("D435_CAMERA_INDEX", "0")),
                width=int(os.environ.get("D435_WIDTH", "1280")),
                height=int(os.environ.get("D435_HEIGHT", "720")),
                fps=int(os.environ.get("D435_FPS", "30")),
                rotation=rotation,
                on_error=self._camera_error,
            )
        raise ValueError(
            "D435_CAMERA_SOURCE must be 'realsense' or 'avfoundation'"
        )

    def start(self) -> None:
        if not self.start_workers or self._tracking_thread is not None:
            return
        self._stop_event.clear()
        self.controller.start()
        self.camera.start()
        self._tracking_thread = threading.Thread(
            target=self._tracking_loop, name="hand-tracking", daemon=True
        )
        self._tracking_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.camera.stop()
        if self._tracking_thread is not None:
            self._tracking_thread.join(timeout=2.0)
            self._tracking_thread = None
        self.controller.stop()
        self.tracker.close()

    def snapshot(self) -> TrackingSnapshot:
        with self._snapshot_lock:
            return self._snapshot

    def list_operator_profiles(self) -> dict[str, object]:
        return self.profile_store.list_payload()

    def operator_profile_status(self) -> dict[str, object]:
        getter = getattr(self.retargeter, "get_operator_profile", None)
        if getter is not None:
            return getter()
        active = self.profile_store.list_payload()["active_profile_id"]
        return self.profile_store.document(active)

    def profile_calibration_status(self) -> dict[str, object] | None:
        getter = getattr(self.retargeter, "get_profile_calibration_status", None)
        return None if getter is None else getter()

    def create_operator_profile(self, name: str) -> dict[str, object]:
        self._require_disarmed()
        profile = self.profile_store.create(name)
        return self._profile_summary(profile["id"])

    def rename_operator_profile(self, profile_id: str, name: str) -> dict[str, object]:
        self._require_disarmed()
        self.profile_store.rename(profile_id, name)
        if self.profile_store.list_payload()["active_profile_id"] == profile_id:
            self.retargeter.set_operator_profile(self.profile_store.document(profile_id))
        return self._profile_summary(profile_id)

    def delete_operator_profile(self, profile_id: str) -> dict[str, object]:
        self._require_disarmed()
        self._require_calibration_profile_unchanged(profile_id, deleting=True)
        self.profile_store.delete(profile_id)
        self.retargeter.set_operator_profile(self.profile_store.active_document())
        return self.profile_store.list_payload()

    def activate_operator_profile(self, profile_id: str) -> dict[str, object]:
        self._require_disarmed()
        self._require_calibration_profile_unchanged(profile_id)
        profile = self.profile_store.activate(profile_id)
        self.retargeter.set_operator_profile(profile)
        return self._profile_summary(profile_id)

    def export_operator_profile(self, profile_id: str) -> dict[str, object]:
        return self.profile_store.export_document(profile_id)

    def import_operator_profile(self, payload: object) -> dict[str, object]:
        self._require_disarmed()
        profile = self.profile_store.import_document(payload)
        return self._profile_summary(profile["id"])

    def start_profile_calibration(self, profile_id: str) -> dict[str, object]:
        self._require_disarmed()
        if self.snapshot().status is not TrackingStatus.TRACKING:
            raise TransitionError("Profile calibration requires fresh right-hand tracking")
        self.activate_operator_profile(profile_id)
        self._saved_profile_calibration = None
        return self.retargeter.start_profile_calibration(profile_id)

    def retry_profile_calibration(self, profile_id: str) -> dict[str, object]:
        self._require_session(profile_id)
        self._saved_profile_calibration = None
        return self.retargeter.retry_profile_calibration()

    def cancel_profile_calibration(self, profile_id: str) -> dict[str, object]:
        self._require_session(profile_id)
        return self.retargeter.cancel_profile_calibration()

    def _profile_summary(self, profile_id: str) -> dict[str, object]:
        return next(
            item
            for item in self.profile_store.list_payload()["profiles"]
            if item["id"] == profile_id
        )

    def _require_disarmed(self) -> None:
        if self.controller.snapshot().state is not ControlState.DISARMED:
            raise TransitionError("Operator profile changes require DISARMED control")

    def _require_session(self, profile_id: str) -> None:
        self._require_disarmed()
        status = self.profile_calibration_status()
        if status is None or status.get("profile_id") != profile_id:
            raise TransitionError("No calibration session exists for this profile")

    def _require_calibration_profile_unchanged(
        self, profile_id: str, *, deleting: bool = False
    ) -> None:
        status = self.profile_calibration_status()
        if status is None or status.get("state") == "CANCELED":
            return
        active_profile_id = str(status.get("profile_id", ""))
        conflicts = active_profile_id == profile_id if deleting else active_profile_id != profile_id
        if conflicts:
            raise TransitionError(
                "Operator calibration is active; finish or cancel it before changing profiles"
            )

    def apply_detection(
        self,
        sequence: int,
        captured_at: float,
        capture_fps: float,
        detection: HandDetection,
        now: float | None = None,
    ) -> TrackingSnapshot:
        published_at = time.time() if now is None else now
        if self._last_tracking_at:
            instantaneous = 1.0 / max(published_at - self._last_tracking_at, 1e-6)
            self._tracking_fps = (
                instantaneous
                if self._tracking_fps == 0
                else 0.9 * self._tracking_fps + 0.1 * instantaneous
            )
        self._last_tracking_at = published_at

        status = detection.status
        joints = None
        actuators = None
        contact = None
        landmarks_3d = None
        if status is TrackingStatus.TRACKING and detection.landmarks_3d is not None:
            joints, actuators = self.retargeter.retarget(
                detection.landmarks_3d, confidence=detection.confidence
            )
            self._persist_completed_profile_calibration()
            get_contact_status = getattr(self.retargeter, "get_contact_status", None)
            if get_contact_status is not None:
                contact = get_contact_status()
            landmarks_3d = detection.landmarks_3d.tolist()
            self._has_tracked = True
        else:
            reset_tracking_context = getattr(
                self.retargeter, "reset_tracking_context", None
            )
            if reset_tracking_context is not None:
                reset_tracking_context()
            if status is TrackingStatus.SEARCHING and self._has_tracked:
                status = TrackingStatus.LOST

        snapshot = TrackingSnapshot(
            status=status,
            sequence=sequence,
            captured_at=captured_at,
            published_at=published_at,
            capture_fps=capture_fps,
            tracking_fps=self._tracking_fps,
            latency_ms=max(0.0, (published_at - captured_at) * 1000),
            handedness=detection.handedness,
            confidence=detection.confidence,
            landmarks_2d=detection.landmarks_2d,
            landmarks_3d=landmarks_3d,
            detected_hands=[
                {
                    "handedness": hand.handedness,
                    "confidence": hand.confidence,
                    "landmarks_2d": hand.landmarks_2d,
                }
                for hand in detection.detected_hands
            ],
            joints=joints,
            actuators=actuators,
            contact=contact,
        )
        with self._snapshot_lock:
            self._snapshot = snapshot
        self.controller.update_tracking(snapshot)
        return snapshot

    def _persist_completed_profile_calibration(self) -> None:
        status = self.profile_calibration_status()
        if status is None or status.get("state") != "COMPLETE":
            return
        profile_id = str(status["profile_id"])
        key = (profile_id, id(getattr(self.retargeter, "_profile_session", None)))
        if self._saved_profile_calibration == key:
            return
        calibration = self.retargeter.completed_profile_calibration()
        if calibration is None:
            return
        self.profile_store.set_calibration(profile_id, calibration)
        self.profile_store.activate(profile_id)
        self.retargeter.set_operator_profile(self.profile_store.document(profile_id))
        self._saved_profile_calibration = key

    def _tracking_loop(self) -> None:
        sequence = 0
        while not self._stop_event.is_set():
            packet = self.frame_store.wait_for_new(sequence, timeout=0.25)
            if packet is None:
                continue
            sequence = packet.sequence
            try:
                detection = self.tracker.process(packet.frame)
                self.apply_detection(
                    packet.sequence,
                    packet.captured_at,
                    packet.capture_fps,
                    detection,
                )
            except Exception as error:
                self._set_error(TrackingStatus.LOST, f"Tracking failed: {error}")

    def _camera_error(self, message: str) -> None:
        self._set_error(TrackingStatus.CAMERA_ERROR, message)

    def _set_error(self, status: TrackingStatus, message: str) -> None:
        snapshot = TrackingSnapshot(status=status, error=message)
        with self._snapshot_lock:
            self._snapshot = snapshot
        self.controller.update_tracking(snapshot)
