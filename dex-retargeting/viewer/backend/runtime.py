from __future__ import annotations

import threading
import time
from pathlib import Path

from .camera import CameraWorker, LatestFrameStore
from .control.controller import ControlState, TransitionError, VisionHandController
from .retargeting import InspireVisionRetargeter
from .state import TrackingSnapshot, TrackingStatus
from .tracking import HandDetection, RightHandTracker


CALIBRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "retargeting-calibration.json"
)


class ViewerRuntime:
    def __init__(
        self,
        retargeter=None,
        tracker=None,
        camera=None,
        controller=None,
        start_workers: bool = True,
    ):
        self.frame_store = LatestFrameStore()
        self.retargeter = retargeter or InspireVisionRetargeter(
            calibration_path=CALIBRATION_PATH
        )
        self.tracker = tracker or RightHandTracker()
        self.camera = camera or CameraWorker(
            self.frame_store, on_error=self._camera_error
        )
        self.controller = controller or VisionHandController()
        self.start_workers = start_workers
        self._snapshot = TrackingSnapshot()
        self._snapshot_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._tracking_thread: threading.Thread | None = None
        self._has_tracked = False
        self._last_tracking_at = 0.0
        self._tracking_fps = 0.0

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

    def calibration_status(self) -> dict[str, object]:
        return self.retargeter.get_calibration_status()

    def start_open_calibration(self) -> dict[str, object]:
        if self.controller.snapshot().state is not ControlState.DISARMED:
            raise TransitionError("Open calibration requires DISARMED control")
        if self.snapshot().status is not TrackingStatus.TRACKING:
            raise TransitionError("Open calibration requires fresh right-hand tracking")
        return self.retargeter.start_open_calibration()

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
            joints, actuators = self.retargeter.retarget(detection.landmarks_3d)
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
