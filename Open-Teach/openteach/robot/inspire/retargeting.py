from dataclasses import dataclass

import numpy as np

from openteach.constants import OCULUS_JOINTS


@dataclass(frozen=True)
class InspireMotionCommand:
    positions: np.ndarray
    speeds: np.ndarray
    targets: np.ndarray
    errors: np.ndarray


def finger_bend(points):
    points = np.asarray(points, dtype=float)
    bends = []
    for index in range(1, len(points) - 1):
        first = points[index] - points[index - 1]
        second = points[index + 1] - points[index]
        denominator = np.linalg.norm(first) * np.linalg.norm(second)
        if denominator <= 1e-9:
            continue
        cosine = np.clip(np.dot(first, second) / denominator, -1.0, 1.0)
        bends.append(np.arccos(cosine) / np.pi)
    return float(np.mean(bends)) if bends else 0.0


class InspireRetargeter:
    CHANNEL_FINGERS = ('pinky', 'ring', 'middle', 'index')

    def __init__(
        self,
        open_bend=0.08,
        closed_bend=0.55,
        thumb_open_bend=0.05,
        thumb_closed_bend=0.45,
        thumb_rotation_open=1.25,
        thumb_rotation_closed=0.35,
        max_step=35,
        adaptive_motion=None,
    ):
        self.open_bend = open_bend
        self.closed_bend = closed_bend
        self.thumb_open_bend = thumb_open_bend
        self.thumb_closed_bend = thumb_closed_bend
        self.thumb_rotation_open = thumb_rotation_open
        self.thumb_rotation_closed = thumb_rotation_closed
        self.max_step = int(max_step)
        adaptive_motion = adaptive_motion or {}
        self.adaptive_enabled = bool(adaptive_motion.get('enabled', False))
        self.deadband = int(adaptive_motion.get('deadband', 8))
        self.error_thresholds = np.asarray(
            adaptive_motion.get('error_thresholds', [40, 180]), dtype=int
        )
        self.adaptive_max_steps = np.asarray(
            adaptive_motion.get('max_steps', [6, 18, 40]), dtype=int
        )
        self.adaptive_speeds = np.asarray(
            adaptive_motion.get('speeds', [30, 80, 160]), dtype=int
        )
        self.hysteresis = int(adaptive_motion.get('hysteresis', 10))
        if len(self.error_thresholds) != 2:
            raise ValueError('adaptive_motion.error_thresholds must contain two values')
        if len(self.adaptive_max_steps) != 3 or len(self.adaptive_speeds) != 3:
            raise ValueError('adaptive_motion max_steps and speeds must contain three values')
        self._motion_bands = np.full(6, -1, dtype=int)

    @staticmethod
    def _to_counts(value, closed, opened):
        span = closed - opened
        if abs(span) <= 1e-9:
            return 1000
        ratio = np.clip((value - opened) / span, 0.0, 1.0)
        return int(round(1000 * (1.0 - ratio)))

    def _thumb_rotation(self, keypoints):
        index_knuckle = keypoints[OCULUS_JOINTS['index'][0]]
        pinky_knuckle = keypoints[OCULUS_JOINTS['pinky'][0]]
        palm_width = np.linalg.norm(index_knuckle - pinky_knuckle)
        if palm_width <= 1e-9:
            return 1000
        thumb_tip = keypoints[OCULUS_JOINTS['thumb'][-1]]
        ratio = np.linalg.norm(thumb_tip - pinky_knuckle) / palm_width
        return self._to_counts(ratio, self.thumb_rotation_closed, self.thumb_rotation_open)

    def _raw_targets(self, keypoints):
        keypoints = np.asarray(keypoints, dtype=float).reshape(24, 3)
        targets = [
            self._to_counts(
                finger_bend(keypoints[OCULUS_JOINTS[finger]]),
                self.closed_bend,
                self.open_bend,
            )
            for finger in self.CHANNEL_FINGERS
        ]
        thumb_bend = finger_bend(keypoints[OCULUS_JOINTS['thumb']])
        targets.extend([
            self._to_counts(thumb_bend, self.thumb_closed_bend, self.thumb_open_bend),
            self._thumb_rotation(keypoints),
        ])
        return np.asarray(targets, dtype=int)

    def adapt_targets(self, targets, current):
        targets = np.clip(np.asarray(targets, dtype=int).reshape(6), 0, 1000)
        current = np.clip(np.asarray(current, dtype=int).reshape(6), 0, 1000)
        signed_errors = targets - current
        errors = np.abs(signed_errors)

        for channel, error in enumerate(errors):
            band = self._motion_bands[channel]
            if band < 0:
                band = int(np.searchsorted(self.error_thresholds, error, side='left'))
            while band < 2 and error > self.error_thresholds[band] + self.hysteresis:
                band += 1
            while band > 0 and error <= self.error_thresholds[band - 1] - self.hysteresis:
                band -= 1
            self._motion_bands[channel] = band

        steps = self.adaptive_max_steps[self._motion_bands]
        positions = current + np.clip(targets - current, -steps, steps)
        positions[errors <= self.deadband] = current[errors <= self.deadband]
        return InspireMotionCommand(
            positions=np.clip(positions, 0, 1000).astype(int),
            speeds=self.adaptive_speeds[self._motion_bands].copy(),
            targets=targets.copy(),
            errors=signed_errors.copy(),
        )

    def retarget_command(self, keypoints, current):
        targets = self._raw_targets(keypoints)
        if self.adaptive_enabled:
            return self.adapt_targets(targets, current)
        positions = self.retarget(keypoints, previous=current)
        return InspireMotionCommand(
            positions=positions,
            speeds=np.full(6, self.adaptive_speeds[0], dtype=int),
            targets=targets.copy(),
            errors=(targets - np.asarray(current, dtype=int).reshape(6)),
        )

    def retarget(self, keypoints, previous=None):
        targets = self._raw_targets(keypoints)
        if previous is None:
            return targets
        previous = np.asarray(previous, dtype=int).reshape(6)
        return previous + np.clip(targets - previous, -self.max_step, self.max_step)


def build_inspire_retargeter(config=None):
    settings = dict(config or {})
    backend = settings.pop('backend', 'heuristic')
    if backend == 'heuristic':
        return InspireRetargeter(**settings)
    if backend == 'dex':
        from .dex_retargeting import DexInspireRetargeter

        return DexInspireRetargeter(**settings)
    raise ValueError(f'Unsupported Inspire retargeting backend: {backend}')
