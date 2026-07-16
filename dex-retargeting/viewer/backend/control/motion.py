from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def _channels(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if len(array) != 6 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain six finite values")
    return np.rint(array).astype(int)


def _channel_scales(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if len(array) != 6 or not np.all(np.isfinite(array)) or np.any(array <= 0):
        raise ValueError(f"{name} must contain six positive finite values")
    return array


@dataclass(frozen=True)
class MotionCommand:
    positions: np.ndarray
    speeds: np.ndarray
    targets: np.ndarray
    errors: np.ndarray


class AdaptiveMotion:
    def __init__(
        self,
        steps: Sequence[int] = (20, 60, 120),
        speeds: Sequence[int] = (100, 260, 450),
        channel_step_scales: Sequence[float] = (1, 1, 1, 1, 1, 1),
        channel_speed_scales: Sequence[float] = (1, 1, 1, 1, 1, 1),
    ):
        self.deadband = 8
        self.thresholds = np.array([40, 180], dtype=int)
        self.steps = np.asarray(steps, dtype=int)
        self.speeds = np.asarray(speeds, dtype=int)
        if self.steps.shape != (3,) or np.any(self.steps <= 0):
            raise ValueError("steps must contain three positive values")
        if self.speeds.shape != (3,) or np.any(self.speeds <= 0):
            raise ValueError("speeds must contain three positive values")
        self.channel_step_scales = _channel_scales(
            channel_step_scales, "channel_step_scales"
        )
        self.channel_speed_scales = _channel_scales(
            channel_speed_scales, "channel_speed_scales"
        )
        self.hysteresis = 10
        self._bands = np.full(6, -1, dtype=int)

    def reset(self) -> None:
        self._bands.fill(-1)

    def command(
        self, targets: Sequence[float], current: Sequence[float]
    ) -> MotionCommand:
        target_values = np.clip(_channels(targets, "targets"), 0, 1000)
        current_values = np.clip(_channels(current, "current"), 0, 1000)
        signed_errors = target_values - current_values
        errors = np.abs(signed_errors)

        for channel, error in enumerate(errors):
            band = self._bands[channel]
            if band < 0:
                band = int(np.searchsorted(self.thresholds, error, side="left"))
            while band < 2 and error > self.thresholds[band] + self.hysteresis:
                band += 1
            while band > 0 and error <= self.thresholds[band - 1] - self.hysteresis:
                band -= 1
            self._bands[channel] = band

        steps = np.rint(
            self.steps[self._bands] * self.channel_step_scales
        ).astype(int)
        speeds = np.rint(
            self.speeds[self._bands] * self.channel_speed_scales
        ).astype(int)
        positions = current_values + np.clip(signed_errors, -steps, steps)
        positions[errors <= self.deadband] = current_values[errors <= self.deadband]
        return MotionCommand(
            positions=np.clip(positions, 0, 1000).astype(int),
            speeds=np.clip(speeds, 1, 1000),
            targets=target_values.copy(),
            errors=signed_errors.copy(),
        )
