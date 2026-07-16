from pathlib import Path

import numpy as np

import dex_retargeting
from dex_retargeting.inspire_retargeting import InspireVisionRetargeter
from dex_retargeting.quest import quest_to_mano

from .retargeting import InspireMotionCommand, InspireRetargeter


class DexInspireRetargeter:
    """Route Quest keypoints through the URDF-constrained RH56 optimizer."""

    def __init__(
        self,
        adaptive_motion=None,
        max_step=35,
        calibration_path=None,
        solver=None,
        **_,
    ):
        if calibration_path is None:
            repository = Path(dex_retargeting.__file__).resolve().parents[2]
            candidate = repository / 'viewer' / 'config' / 'retargeting-calibration.json'
            calibration_path = candidate if candidate.is_file() else None
        elif calibration_path:
            calibration_path = Path(calibration_path).expanduser().resolve()
        self._solver = solver or InspireVisionRetargeter(calibration_path=calibration_path)
        self._motion = InspireRetargeter(
            max_step=max_step,
            adaptive_motion=adaptive_motion,
        )

    def retarget_command(self, keypoints, current):
        mano_landmarks = quest_to_mano(keypoints)
        _, targets = self._solver.retarget(mano_landmarks)
        targets = np.asarray(targets, dtype=int)
        current = np.asarray(current, dtype=int).reshape(6)
        if self._motion.adaptive_enabled:
            return self._motion.adapt_targets(targets, current)
        positions = current + np.clip(targets - current, -self._motion.max_step, self._motion.max_step)
        return InspireMotionCommand(
            positions=np.clip(positions, 0, 1000).astype(int),
            speeds=np.full(6, self._motion.adaptive_speeds[0], dtype=int),
            targets=targets,
            errors=targets - current,
        )

    def get_contact_status(self):
        return self._solver.get_contact_status()
