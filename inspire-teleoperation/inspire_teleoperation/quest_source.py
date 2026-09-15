"""Quest/TeleVuer adapter for the hardware-agnostic teleoperation API."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any, Callable

import numpy as np

from .api import HandTracking, RigidTransform, TeleopFrame


logger = logging.getLogger(__name__)


def _install_legacy_hand_event_compatibility(*, show_hand_markers: bool) -> None:
    """Adapt TeleVuer 4.0.0 hand events and marker visibility at runtime."""

    from televuer.televuer import TeleVuer

    # TeleVuer creates its Vuer process inside __init__, before the wrapper is
    # returned.  Store this as a class default so the forked process sees it.
    # There is one Quest source per application, therefore a class setting is
    # sufficient and preserves the public --hide-hand-markers option.
    TeleVuer._inspire_teleop_show_hand_markers = bool(show_hand_markers)

    if not getattr(TeleVuer.on_hand_move, "_inspire_teleop_compatible", False):
        async def on_hand_move(self: Any, event: Any, session: Any, fps: float = 60) -> None:
            del session, fps
            value = getattr(event, "value", None)
            if not isinstance(value, dict):
                return

            for side in ("left", "right"):
                try:
                    matrices = np.asarray(value.get(side, ()), dtype=np.float64).reshape(-1)
                except (TypeError, ValueError):
                    continue
                if matrices.size < 25 * 16 or not np.isfinite(matrices[: 25 * 16]).all():
                    continue
                matrices = matrices[: 25 * 16].reshape(25, 16)

                arm_pose = getattr(self, f"{side}_arm_pose_shared")
                positions = getattr(self, f"{side}_hand_position_shared")
                orientations = getattr(self, f"{side}_hand_orientation_shared")
                with arm_pose.get_lock():
                    arm_pose[:] = matrices[0].tolist()
                with positions.get_lock():
                    positions[:] = matrices[:, (12, 13, 14)].ravel().tolist()
                with orientations.get_lock():
                    orientations[:] = matrices[:, (0, 1, 2, 4, 5, 6, 8, 9, 10)].ravel().tolist()

                state = value.get(f"{side}State")
                if not isinstance(state, dict):
                    continue
                for name, default, converter in (
                    ("pinch", False, bool),
                    ("pinchValue", 0.0, float),
                    ("squeeze", False, bool),
                    ("squeezeValue", 0.0, float),
                ):
                    shared = getattr(self, f"{side}_hand_{name}_shared")
                    try:
                        converted = converter(state.get(name, default))
                    except (TypeError, ValueError):
                        converted = default
                    with shared.get_lock():
                        shared.value = converted

        on_hand_move._inspire_teleop_compatible = True  # type: ignore[attr-defined]
        TeleVuer.on_hand_move = on_hand_move

    if not getattr(TeleVuer.main_pass_through, "_inspire_teleop_markers_compatible", False):
        from vuer.schemas import Hands, MotionControllers

        async def main_pass_through(self: Any, session: Any) -> None:
            if self.use_hand_tracking:
                show_markers = bool(getattr(self, "_inspire_teleop_show_hand_markers", True))
                session.upsert(
                    Hands(
                        stream=True,
                        key="hands",
                        hideLeft=not show_markers,
                        hideRight=not show_markers,
                    ),
                    to="bgChildren",
                )
            else:
                session.upsert(
                    MotionControllers(stream=True, key="motionControllers", left=True, right=True),
                    to="bgChildren",
                )
            while True:
                await asyncio.sleep(1.0 / self.display_fps)

        main_pass_through._inspire_teleop_markers_compatible = True  # type: ignore[attr-defined]
        TeleVuer.main_pass_through = main_pass_through


class QuestSource:
    """Convert TeleVuer samples into validated immutable frames."""

    def __init__(
        self,
        *,
        binocular: bool = False,
        image_shape: tuple[int, int, int] = (480, 640, 3),
        display_mode: str = "pass-through",
        show_hand_markers: bool = True,
        wrapper_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._options = {
            "use_hand_tracking": True,
            "binocular": binocular,
            "img_shape": image_shape,
            "display_mode": display_mode,
            "zmq": False,
            "webrtc": False,
            "arm_reference_mode": "head_yaw",
            "show_hand_markers": show_hand_markers,
        }
        self._wrapper_factory = wrapper_factory
        self._wrapper: Any | None = None
        self._sequence = 0

    def start(self) -> None:
        if self._wrapper is not None:
            return
        factory = self._wrapper_factory
        if factory is None:
            from televuer import TeleVuerWrapper

            factory = TeleVuerWrapper
            if "show_hand_markers" not in inspect.signature(factory).parameters:
                _install_legacy_hand_event_compatibility(
                    show_hand_markers=self._options["show_hand_markers"],
                )
        # TeleVuer's constructor has changed across releases.  The currently
        # pinned 4.0.0 release does not expose the newer marker/reference-mode
        # options, while newer forks do.  Pass every option to extensible
        # factories and otherwise limit arguments to the advertised signature.
        parameters = inspect.signature(factory).parameters.values()
        accepts_extra_options = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        if accepts_extra_options:
            options = self._options
        else:
            accepted_names = {parameter.name for parameter in parameters}
            options = {
                name: value
                for name, value in self._options.items()
                if name in accepted_names
            }
            ignored = sorted(self._options.keys() - options.keys())
            if ignored:
                logger.info(
                    "TeleVuer does not support optional setting(s): %s",
                    ", ".join(ignored),
                )
        self._wrapper = factory(**options)

    @staticmethod
    def _transform(sample: Any, attribute: str) -> RigidTransform | None:
        value = getattr(sample, attribute, None)
        return None if value is None else RigidTransform(value)

    @staticmethod
    def _motion_ready(sample: Any) -> bool:
        """Support TeleData releases with and without an explicit ready flag."""

        explicit = getattr(sample, "motion_data_ready", None)
        if explicit is not None:
            return bool(explicit)

        # TeleVuer 4.0.0 omits motion_data_ready.  Before tracking starts its
        # wrapper returns zero-filled landmark arrays, so accept the legacy
        # payload only when at least one complete hand contains real values.
        for attribute in ("left_hand_pos", "right_hand_pos"):
            try:
                landmarks = np.asarray(getattr(sample, attribute), dtype=np.float64)
            except (AttributeError, TypeError, ValueError):
                continue
            if (
                landmarks.shape == (25, 3)
                and np.isfinite(landmarks).all()
                and np.any(np.abs(landmarks) > 1e-9)
            ):
                return True
        return False

    def read(self) -> TeleopFrame:
        if self._wrapper is None:
            raise RuntimeError("Quest source has not been started")
        sample = self._wrapper.get_tele_data()
        self._sequence += 1
        ready = self._motion_ready(sample)

        left = right = None
        if ready:
            left_landmarks = getattr(sample, "left_hand_pos", None)
            right_landmarks = getattr(sample, "right_hand_pos", None)
            left_wrist = self._transform(sample, "left_wrist_pose")
            right_wrist = self._transform(sample, "right_wrist_pose")
            if left_landmarks is not None:
                left = HandTracking(left_landmarks, wrist=left_wrist)
            if right_landmarks is not None:
                right = HandTracking(right_landmarks, wrist=right_wrist)

        return TeleopFrame(
            sequence=self._sequence,
            timestamp=time.monotonic(),
            motion_data_ready=ready,
            left_hand=left,
            right_hand=right,
            head=self._transform(sample, "head_pose") if ready else None,
        )

    def close(self) -> None:
        if self._wrapper is not None:
            self._wrapper.close()
            self._wrapper = None
