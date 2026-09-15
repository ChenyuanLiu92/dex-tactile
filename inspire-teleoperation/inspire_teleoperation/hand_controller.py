"""Retarget and control one or two six-DOF hands over Modbus TCP."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import math
import threading
import time
from dataclasses import dataclass
from multiprocessing import Array, Lock, Value
from typing import TYPE_CHECKING, Callable, Sequence

import numpy as np

if TYPE_CHECKING:
    from .dexhand import Dexhand
    from .hand_retargeting import HandRetargeting

try:
    import logging_mp
except ModuleNotFoundError:
    import logging as logging_mp


logger_mp = logging_mp.getLogger(__name__)
JOINT_COUNT = 6
SPEED_MODES = ("adaptive_v2", "adaptive_v1", "fixed")
MOTION_FILTER_ALPHA = 0.65
TACTILE_SAMPLE_HZ = 10.0
MAX_TACTILE_SAMPLE_HZ = 60.0
TACTILE_FORCE_SAMPLE_HZ = 10.0
FORCE_CALIBRATION_MIN_WAIT_S = 0.5
FORCE_CALIBRATION_STABLE_WINDOW_S = 0.5
FORCE_CALIBRATION_POLL_INTERVAL_S = 0.02
FORCE_CALIBRATION_TIMEOUT_S = 3.0
FORCE_CALIBRATION_ZERO_LIMIT_G = 5
FORCE_CALIBRATION_SPAN_LIMIT_G = 2


def _normalize_speed_mode(mode: str) -> str:
    """Map the original public adaptive name to the 2.0 implementation."""

    normalized = "adaptive_v2" if mode == "adaptive" else mode
    if normalized not in SPEED_MODES:
        raise ValueError(
            "speed_mode must be 'adaptive_v2', 'adaptive_v1', 'adaptive', or 'fixed'"
        )
    return normalized


class AdaptiveSpeedPlanner:
    """Adaptive speed 1.0, retained for comparison and compatibility."""

    def __init__(
        self,
        minimum_speed: int = 80,
        maximum_speed: int = 1000,
        full_scale_error: float = 0.25,
        motion_gain: float = 3.0,
        smoothing: float = 0.35,
        initial_speed: int = 300,
    ) -> None:
        if not 0 <= minimum_speed <= maximum_speed <= 1000:
            raise ValueError("adaptive speeds must satisfy 0 <= minimum <= maximum <= 1000")
        if full_scale_error <= 0:
            raise ValueError("full_scale_error must be positive")
        if motion_gain < 0:
            raise ValueError("motion_gain must be non-negative")
        if not 0 < smoothing <= 1:
            raise ValueError("smoothing must be in the range (0, 1]")
        self.minimum_speed = minimum_speed
        self.maximum_speed = maximum_speed
        self.full_scale_error = full_scale_error
        self.motion_gain = motion_gain
        self.smoothing = smoothing
        self._speeds = np.full(JOINT_COUNT, initial_speed, dtype=np.float64)
        self._previous_target: np.ndarray | None = None

    def reset(self, initial_speed: int) -> None:
        """Start a new adaptive session without a stale target-motion spike."""

        self._speeds.fill(np.clip(initial_speed, self.minimum_speed, self.maximum_speed))
        self._previous_target = None

    def calculate(self, target: np.ndarray, actual: np.ndarray) -> np.ndarray:
        """Return one 0..1000 speed for every normalized target joint."""

        target = np.asarray(target, dtype=np.float64)
        actual = np.asarray(actual, dtype=np.float64)
        if target.shape != (JOINT_COUNT,) or actual.shape != (JOINT_COUNT,):
            raise ValueError(f"target and actual must each contain {JOINT_COUNT} values")

        following_error = np.abs(target - actual)
        target_motion = (
            np.zeros(JOINT_COUNT, dtype=np.float64)
            if self._previous_target is None
            else np.abs(target - self._previous_target)
        )
        demand = np.maximum(following_error, target_motion * self.motion_gain)
        ratio = np.clip(demand / self.full_scale_error, 0.0, 1.0)
        desired = self.minimum_speed + ratio * (self.maximum_speed - self.minimum_speed)
        self._speeds += self.smoothing * (desired - self._speeds)
        self._previous_target = target.copy()
        return np.rint(self._speeds).astype(int)


AdaptiveSpeedPlannerV1 = AdaptiveSpeedPlanner


@dataclass(frozen=True)
class AdaptiveSpeedConfig:
    """Tuning parameters for the frequency-independent 2.0 planner."""

    min_speed: int = 80
    max_speed: int = 1000
    full_error: float = 0.25
    full_target_rate: float = 5.0
    error_deadband: float = 0.005
    target_rate_deadband: float = 0.05
    global_blend: float = 0.15
    smoothing_tau_s: float = 0.08
    stale_reset_s: float = 0.20
    write_threshold: int = 5

    def __post_init__(self) -> None:
        if not 0 <= self.min_speed <= self.max_speed <= 1000:
            raise ValueError("speeds must satisfy 0 <= min_speed <= max_speed <= 1000")
        if self.error_deadband < 0 or self.full_error <= self.error_deadband:
            raise ValueError("full_error must be greater than the non-negative error_deadband")
        if (
            self.target_rate_deadband < 0
            or self.full_target_rate <= self.target_rate_deadband
        ):
            raise ValueError(
                "full_target_rate must be greater than the non-negative "
                "target_rate_deadband"
            )
        if not 0.0 <= self.global_blend <= 1.0:
            raise ValueError("global_blend must be in the range 0..1")
        if self.smoothing_tau_s <= 0:
            raise ValueError("smoothing_tau_s must be positive")
        if self.stale_reset_s <= 0:
            raise ValueError("stale_reset_s must be positive")
        if (
            isinstance(self.write_threshold, bool)
            or not isinstance(self.write_threshold, int)
            or self.write_threshold < 0
        ):
            raise ValueError("write_threshold must be a non-negative integer")


class AdaptiveSpeedPlannerV2:
    """Frequency-independent, deadbanded adaptive joint speed planner."""

    JOINT_COUNT = JOINT_COUNT

    def __init__(self, config: AdaptiveSpeedConfig | None = None) -> None:
        self.config = config or AdaptiveSpeedConfig()
        self._filtered_speed = np.full(
            self.JOINT_COUNT, self.config.min_speed, dtype=np.float64
        )
        self._previous_target: np.ndarray | None = None
        self._last_timestamp: float | None = None
        self._suppress_motion_once = False
        self._warned_time_regression = False

    @staticmethod
    def _joint_vector(values: Sequence[float], name: str) -> np.ndarray:
        try:
            vector = np.asarray(values, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{name} must contain six numeric values") from error
        if vector.shape != (JOINT_COUNT,):
            raise ValueError(f"{name} must contain {JOINT_COUNT} values")
        if not np.isfinite(vector).all():
            raise ValueError(f"{name} must contain only finite values")
        return np.clip(vector, 0.0, 1.0)

    @staticmethod
    def _timestamp(now: float | None) -> float:
        timestamp = time.monotonic() if now is None else float(now)
        if not math.isfinite(timestamp):
            raise ValueError("now must be finite")
        return timestamp

    def reset(
        self,
        target: Sequence[float] | None = None,
        initial_speed: int | Sequence[int] | None = None,
        now: float | None = None,
    ) -> None:
        """Reset target history, timestamp, and the speed smoothing state."""

        self._previous_target = (
            None if target is None else self._joint_vector(target, "target")
        )
        if initial_speed is None:
            speeds = np.full(self.JOINT_COUNT, self.config.min_speed, dtype=np.float64)
        elif np.isscalar(initial_speed):
            speed = float(initial_speed)
            if not math.isfinite(speed):
                raise ValueError("initial_speed must be finite")
            speeds = np.full(self.JOINT_COUNT, speed, dtype=np.float64)
        else:
            try:
                speeds = np.asarray(initial_speed, dtype=np.float64)
            except (TypeError, ValueError) as error:
                raise ValueError("initial_speed must contain six numeric values") from error
            if speeds.shape != (self.JOINT_COUNT,) or not np.isfinite(speeds).all():
                raise ValueError("initial_speed must contain six finite values")
        self._filtered_speed = np.clip(
            speeds, self.config.min_speed, self.config.max_speed
        )
        self._last_timestamp = self._timestamp(now)
        self._suppress_motion_once = True
        self._warned_time_regression = False

    def compute(
        self,
        target: Sequence[float],
        actual: Sequence[float],
        now: float | None = None,
    ) -> list[int]:
        """Compute six smooth 0..1000 speed-register values for one frame."""

        target_vector = self._joint_vector(target, "target")
        actual_vector = self._joint_vector(actual, "actual")
        timestamp = self._timestamp(now)
        dt = (
            None
            if self._last_timestamp is None
            else timestamp - self._last_timestamp
        )
        discontinuity = (
            self._previous_target is None
            or dt is None
            or dt <= 0.0
            or dt > self.config.stale_reset_s
            or self._suppress_motion_once
        )
        if dt is not None and dt <= 0.0 and not self._warned_time_regression:
            logger_mp.warning(
                "Adaptive speed 2.0 timestamp did not advance; resetting motion rate."
            )
            self._warned_time_regression = True
        elif dt is not None and dt > self.config.stale_reset_s:
            logger_mp.warning(
                "Adaptive speed 2.0 resumed after %.3f seconds; resetting motion rate.",
                dt,
            )
            self._warned_time_regression = False
        elif not discontinuity:
            self._warned_time_regression = False

        if discontinuity:
            motion_rate = np.zeros(self.JOINT_COUNT, dtype=np.float64)
            dt_filter = min(self.config.smoothing_tau_s, 0.10)
        else:
            motion_rate = np.abs(target_vector - self._previous_target) / dt
            dt_filter = float(np.clip(dt, 1e-3, 0.10))

        following_error = np.abs(target_vector - actual_vector)
        error_demand = np.clip(
            np.maximum(following_error - self.config.error_deadband, 0.0)
            / (self.config.full_error - self.config.error_deadband),
            0.0,
            1.0,
        )
        motion_demand = np.clip(
            np.maximum(motion_rate - self.config.target_rate_deadband, 0.0)
            / (self.config.full_target_rate - self.config.target_rate_deadband),
            0.0,
            1.0,
        )
        local_demand = np.maximum(error_demand, motion_demand)
        global_demand = float(np.max(local_demand))
        combined = (
            (1.0 - self.config.global_blend) * local_demand
            + self.config.global_blend * global_demand
        )
        shaped = combined * combined * (3.0 - 2.0 * combined)
        desired = self.config.min_speed + shaped * (
            self.config.max_speed - self.config.min_speed
        )
        alpha = 1.0 - math.exp(-dt_filter / self.config.smoothing_tau_s)
        self._filtered_speed += alpha * (desired - self._filtered_speed)
        output = np.rint(
            np.clip(
                self._filtered_speed,
                self.config.min_speed,
                self.config.max_speed,
            )
        ).astype(int)
        self._previous_target = target_vector.copy()
        self._last_timestamp = timestamp
        self._suppress_motion_once = False
        return output.tolist()


class HandController:
    """Retarget Quest landmarks and command enabled hands over Modbus TCP.

    The DexHand API uses the same six-joint order as the existing retargeting
    configuration: finger4, finger3, finger2, finger1, finger0_bend, and
    finger0_rotate.  Its target-angle range is 0 (closed) through 1000
    (open), matching the normalized target values generated below.
    """

    def __init__(
        self,
        left_hand_array: Array,
        right_hand_array: Array,
        dual_hand_data_lock: Lock | None = None,
        dual_hand_state_array: Array | None = None,
        dual_hand_action_array: Array | None = None,
        *,
        left_host: str | None = None,
        right_host: str | None = None,
        port: int = 6000,
        left_device_id: int = 1,
        right_device_id: int = 1,
        timeout: float = 3.0,
        target_speed: int = 300,
        speed_mode: str = "adaptive_v2",
        motion_filter_enabled: bool = False,
        fps: float = 100.0,
        tactile_frequency: float = TACTILE_SAMPLE_HZ,
        xr_motion_data_ready_in: Value | None = None,
        xr_motion_data_sequence_in: Value | None = None,
        client_factory: Callable[..., "Dexhand"] | None = None,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        if not 1 <= tactile_frequency <= MAX_TACTILE_SAMPLE_HZ:
            raise ValueError("tactile_frequency must be between 1 and 60 Hz")
        if not 0 <= target_speed <= 1000:
            raise ValueError("target_speed must be between 0 and 1000")
        speed_mode = _normalize_speed_mode(speed_mode)

        hosts = {side: host for side, host in (("left", left_host), ("right", right_host)) if host}
        if not hosts:
            raise ValueError("At least one of left_host and right_host must be configured")
        if (
            left_host
            and right_host
            and left_host.strip().casefold() == right_host.strip().casefold()
        ):
            raise ValueError("left_host and right_host must use different addresses")

        if client_factory is None:
            # Keep the protocol client local to this extracted package.
            try:
                from .dexhand import Dexhand as DexhandClient
            except ModuleNotFoundError as error:
                raise ModuleNotFoundError(
                    "The local dexhand Modbus API and its pymodbus dependency "
                    "are required."
                ) from error
            client_factory = DexhandClient

        self.fps = fps
        self._fixed_speed = target_speed
        self._speed_mode = speed_mode
        self._speed_mode_lock = threading.Lock()
        self._motion_filter_enabled = bool(motion_filter_enabled)
        self._motion_filter_lock = threading.Lock()
        self._request_timeout = timeout
        self._dual_hand_data_lock = dual_hand_data_lock
        self._left_hand_array = left_hand_array
        self._right_hand_array = right_hand_array
        self._dual_hand_state_array = dual_hand_state_array
        self._dual_hand_action_array = dual_hand_action_array
        self._xr_motion_data_ready = xr_motion_data_ready_in
        self._xr_motion_data_sequence = xr_motion_data_sequence_in
        self._last_motion_data_sequence = (
            xr_motion_data_sequence_in.value
            if xr_motion_data_sequence_in is not None
            else None
        )
        self._stop_event = threading.Event()
        self._control_error: BaseException | None = None
        self._tactile_lock = threading.Lock()
        self._tactile_condition = threading.Condition(self._tactile_lock)
        self._tactile_selection: tuple[str, ...] = ()
        self._tactile_frames: dict[
            str,
            tuple[
                float,
                dict[str, list[list[int]]],
                float | None,
                list[int],
                str,
            ],
        ] = {}
        self._tactile_revisions: dict[str, int] = {}
        self._tactile_rates: dict[str, float] = {}
        self._tactile_errors: dict[str, str] = {}
        # Retargeting brings in the URDF/kinematics stack.  Load it only when
        # an actual hand controller is constructed so the public API, speed
        # planners, arm-only applications, and --help stay lightweight.
        from .hand_retargeting import HandRetargeting

        self._hand_retargeting = HandRetargeting()

        self.left_hand_state_array = Array("d", JOINT_COUNT, lock=True)
        self.right_hand_state_array = Array("d", JOINT_COUNT, lock=True)
        self.left_hand_speed_array = Array("i", JOINT_COUNT, lock=True)
        self.right_hand_speed_array = Array("i", JOINT_COUNT, lock=True)
        device_ids = {"left": left_device_id, "right": right_device_id}
        self._hands: dict[str, Dexhand] = {
            side: client_factory(
                host=host,
                port=port,
                device_id=device_ids[side],
                timeout=timeout,
            )
            for side, host in hosts.items()
        }
        # Each hand gets an independent tactile worker and Modbus client. The
        # batches still release their per-client lock so control traffic for
        # the same hand can run between tactile requests.
        self._tactile_target_hz = float(tactile_frequency)

        try:
            for hand in self._hands.values():
                hand.connect()
                hand.write_target_speeds([target_speed] * JOINT_COUNT)
            initial_state = self._update_hand_states()
        except BaseException:
            self._close_hands()
            raise

        self._initial_state = {
            "left": initial_state[:JOINT_COUNT],
            "right": initial_state[JOINT_COUNT:],
        }

        self._control_thread = threading.Thread(
            target=self._control_loop,
            name="hand-modbus-control",
            daemon=True,
        )
        self._control_thread.start()
        self._tactile_threads = {
            side: threading.Thread(
                target=self._tactile_loop,
                args=(side,),
                name=f"hand-modbus-tactile-{side}",
                daemon=True,
            )
            for side in self._hands
        }
        for thread in self._tactile_threads.values():
            thread.start()
        logger_mp.info(
            "Hand Modbus connected in %s-speed mode: %s.",
            speed_mode,
            ", ".join(
                f"{side}={hosts[side]}:{port} (id={device_ids[side]})"
                for side in self._hands
            ),
        )

    def _read_landmarks(self) -> dict[str, np.ndarray]:
        if self._dual_hand_data_lock is not None:
            self._dual_hand_data_lock.acquire()
        try:
            landmarks = {}
            arrays = {
                "left": self._left_hand_array,
                "right": self._right_hand_array,
            }
            for side in self._hands:
                with arrays[side].get_lock():
                    landmarks[side] = (
                        np.array(arrays[side][:]).reshape(25, 3).copy()
                    )
            return landmarks
        finally:
            if self._dual_hand_data_lock is not None:
                self._dual_hand_data_lock.release()

    def _consume_motion_data_ready(self) -> bool:
        """Atomically consume one newly published Quest landmark frame."""

        if self._xr_motion_data_sequence is not None:
            with self._xr_motion_data_sequence.get_lock():
                sequence = self._xr_motion_data_sequence.value
            if sequence == self._last_motion_data_sequence:
                return False
            self._last_motion_data_sequence = sequence
            return True
        if self._xr_motion_data_ready is None:
            return True
        with self._xr_motion_data_ready.get_lock():
            ready = bool(self._xr_motion_data_ready.value)
            self._xr_motion_data_ready.value = False
            return ready

    @staticmethod
    def _normalize_targets(targets: np.ndarray) -> np.ndarray:
        """Convert retargeting radians to the device's 0-closed/1-open scale."""

        limits = ((0.0, 1.7),) * 4 + ((0.0, 0.5), (-0.1, 1.3))
        normalized = np.empty(JOINT_COUNT, dtype=np.float64)
        for index, (minimum, maximum) in enumerate(limits):
            normalized[index] = np.clip(
                (maximum - targets[index]) / (maximum - minimum), 0.0, 1.0
            )
        return normalized

    def _read_hand_state(self, side: str) -> np.ndarray:
        state = np.asarray(
            self._hands[side].read_actual_angles(), dtype=np.float64
        )
        if state.shape != (JOINT_COUNT,):
            raise RuntimeError(
                f"Dexhand {side} actual angles must contain "
                f"{JOINT_COUNT} values, got {state.shape}"
            )
        return state / 1000.0

    def _publish_hand_states(self, states: dict[str, np.ndarray]) -> np.ndarray:
        complete_states = {
            side: states.get(side, np.zeros(JOINT_COUNT, dtype=np.float64))
            for side in ("left", "right")
        }
        with self.left_hand_state_array.get_lock():
            self.left_hand_state_array[:] = complete_states["left"]
        with self.right_hand_state_array.get_lock():
            self.right_hand_state_array[:] = complete_states["right"]
        return np.concatenate((complete_states["left"], complete_states["right"]))

    def _update_hand_states(self) -> np.ndarray:
        return self._publish_hand_states(
            {side: self._read_hand_state(side) for side in self._hands}
        )

    def _run_hand_cycle(
        self,
        side: str,
        command: list[int] | None,
        speeds: list[int] | None,
    ) -> np.ndarray:
        """Run one hand's ordered Modbus operations in one I/O worker."""

        hand = self._hands[side]
        if speeds is not None:
            hand.write_target_speeds(speeds)
        if command is not None:
            hand.write_target_angles(command)
        return self._read_hand_state(side)

    def _run_hand_cycles(
        self,
        executor: ThreadPoolExecutor | None,
        commands: dict[str, list[int]],
        speed_writes: dict[str, list[int]],
    ) -> np.ndarray:
        """Run left/right Modbus cycles concurrently while preserving per-hand order."""

        if executor is None:
            states = {
                side: self._run_hand_cycle(
                    side, commands.get(side), speed_writes.get(side)
                )
                for side in self._hands
            }
        else:
            futures = {
                side: executor.submit(
                    self._run_hand_cycle,
                    side,
                    commands.get(side),
                    speed_writes.get(side),
                )
                for side in self._hands
            }
            states = {side: future.result() for side, future in futures.items()}
        return self._publish_hand_states(states)

    def _publish_observation(self, state: np.ndarray, action: np.ndarray) -> None:
        if self._dual_hand_state_array is None or self._dual_hand_action_array is None:
            return
        if self._dual_hand_data_lock is None:
            self._dual_hand_state_array[:] = state
            self._dual_hand_action_array[:] = action
            return
        with self._dual_hand_data_lock:
            self._dual_hand_state_array[:] = state
            self._dual_hand_action_array[:] = action

    @property
    def speed_mode(self) -> str:
        with self._speed_mode_lock:
            return self._speed_mode

    def set_speed_mode(self, mode: str) -> None:
        """Request a thread-safe live switch between supported speed modes."""

        normalized = _normalize_speed_mode(mode)
        with self._speed_mode_lock:
            self._speed_mode = normalized

    def toggle_speed_mode(self) -> str:
        with self._speed_mode_lock:
            index = SPEED_MODES.index(self._speed_mode)
            self._speed_mode = SPEED_MODES[(index + 1) % len(SPEED_MODES)]
            return self._speed_mode

    @property
    def motion_filter_enabled(self) -> bool:
        with self._motion_filter_lock:
            return self._motion_filter_enabled

    def set_motion_filter_enabled(self, enabled: bool) -> None:
        """Request a thread-safe live motion-filter state change."""

        with self._motion_filter_lock:
            self._motion_filter_enabled = bool(enabled)

    def toggle_motion_filter(self) -> bool:
        with self._motion_filter_lock:
            self._motion_filter_enabled = not self._motion_filter_enabled
            return self._motion_filter_enabled

    @staticmethod
    def _smooth_motion_target(
        target: np.ndarray, previous: np.ndarray | None
    ) -> np.ndarray:
        """Apply a low-lag EMA to one normalized six-joint target."""

        if previous is None:
            return target.copy()
        return (
            MOTION_FILTER_ALPHA * target
            + (1.0 - MOTION_FILTER_ALPHA) * previous
        )

    def calibrate_force_sensors(self) -> tuple[str, ...]:
        """Calibrate all hands and wait for a stable unloaded force window."""

        calibrated: list[str] = []
        failures: list[tuple[str, Exception]] = []
        with ThreadPoolExecutor(
            max_workers=len(self._hands),
            thread_name_prefix="hand-force-calibration",
        ) as executor:
            futures = {
                side: executor.submit(self._calibrate_hand_force_sensors, side)
                for side in self._hands
            }
            for side, future in futures.items():
                try:
                    future.result()
                except Exception as error:
                    failures.append((side, error))
                else:
                    calibrated.append(side)
        if failures:
            detail = "; ".join(f"{side}: {error}" for side, error in failures)
            raise RuntimeError(
                f"Force-sensor calibration failed ({detail})"
            ) from failures[0][1]
        return tuple(calibrated)

    def _calibrate_hand_force_sensors(self, side: str) -> None:
        """Trigger one hand, then require both minimum wait and stable polling."""

        hand = self._hands[side]
        started_at = time.monotonic()
        hand.calibrate_force_sensors()
        samples: list[tuple[float, np.ndarray]] = []
        last_forces = np.zeros(JOINT_COUNT, dtype=np.int16)
        while True:
            sample_started = time.monotonic()
            try:
                forces = np.asarray(hand.read_actual_forces(), dtype=np.int16)
            except Exception as error:
                raise RuntimeError(f"could not poll actual forces: {error}") from error
            if forces.shape != (JOINT_COUNT,):
                raise RuntimeError(
                    f"actual forces must contain {JOINT_COUNT} values, "
                    f"got {forces.shape}"
                )

            elapsed = time.monotonic() - started_at
            last_forces = forces.copy()
            samples.append((elapsed, last_forces))
            window_start = elapsed - FORCE_CALIBRATION_STABLE_WINDOW_S
            samples = [sample for sample in samples if sample[0] >= window_start]
            covers_stable_window = bool(samples) and samples[0][0] <= (
                window_start + 1.5 * FORCE_CALIBRATION_POLL_INTERVAL_S
            )
            if (
                elapsed >= FORCE_CALIBRATION_MIN_WAIT_S
                and covers_stable_window
            ):
                values = np.stack([sample[1] for sample in samples])
                stable = (
                    np.max(np.abs(values)) <= FORCE_CALIBRATION_ZERO_LIMIT_G
                    and np.max(np.ptp(values, axis=0))
                    <= FORCE_CALIBRATION_SPAN_LIMIT_G
                )
                if stable:
                    return
            if elapsed >= FORCE_CALIBRATION_TIMEOUT_S:
                raise TimeoutError(
                    "force values did not stabilize within "
                    f"{FORCE_CALIBRATION_TIMEOUT_S:.1f}s; "
                    f"last={last_forces.astype(int).tolist()}"
                )

            remaining = FORCE_CALIBRATION_POLL_INTERVAL_S - (
                time.monotonic() - sample_started
            )
            if remaining > 0:
                time.sleep(remaining)

    def set_tactile_sides(self, sides: Sequence[str]) -> None:
        """Enable command-rate-aware tactile sampling for connected hands."""

        normalized = tuple(side for side in ("left", "right") if side in sides)
        if len(normalized) != len(tuple(sides)):
            raise ValueError("tactile sides must be unique connected hand names")
        unavailable = [side for side in normalized if side not in self._hands]
        if unavailable:
            raise ValueError(f"tactile hand is not connected: {unavailable[0]}")
        with self._tactile_condition:
            self._tactile_selection = normalized
            self._tactile_frames = {
                side: frame
                for side, frame in self._tactile_frames.items()
                if side in normalized
            }
            self._tactile_revisions = {
                side: revision
                for side, revision in self._tactile_revisions.items()
                if side in normalized
            }
            self._tactile_rates = {
                side: rate
                for side, rate in self._tactile_rates.items()
                if side in normalized
            }
            self._tactile_errors = {
                side: error
                for side, error in self._tactile_errors.items()
                if side in normalized
            }
            self._tactile_condition.notify_all()

    def tactile_snapshot(self) -> dict[str, object]:
        """Return the last completed tactile frames without performing I/O."""

        now = time.monotonic()
        with self._tactile_lock:
            selection = self._tactile_selection
            measured_rates = [
                self._tactile_rates[side]
                for side in selection
                if self._tactile_rates.get(side, 0.0) > 0
            ]
            hands: dict[str, object] = {}
            for side in selection:
                frame = self._tactile_frames.get(side)
                hands[side] = {
                    "regions": {} if frame is None else frame[1],
                    "age_seconds": None if frame is None else max(0.0, now - frame[0]),
                    "forces": [] if frame is None else frame[3],
                    "force_age_seconds": (
                        None
                        if frame is None or frame[2] is None
                        else max(0.0, now - frame[2])
                    ),
                    "force_error": "" if frame is None else frame[4],
                    "revision": self._tactile_revisions.get(side, 0),
                    "error": self._tactile_errors.get(side, ""),
                }
        return {
            "sample_hz": min(measured_rates, default=self._tactile_target_hz),
            "target_hz": self._tactile_target_hz,
            "selection": list(selection),
            "hands": hands,
        }

    def _tactile_loop(self, side: str) -> None:
        """Read one hand independently so dual-hand sampling runs in parallel."""

        sample_period = 1.0 / self._tactile_target_hz
        force_period = 1.0 / TACTILE_FORCE_SAMPLE_HZ
        next_force_at = 0.0
        force_captured_at: float | None = None
        forces: list[int] = []
        force_error = ""
        while not self._stop_event.is_set():
            with self._tactile_condition:
                self._tactile_condition.wait_for(
                    lambda: self._stop_event.is_set()
                    or side in self._tactile_selection,
                    timeout=0.5,
                )
                if self._stop_event.is_set():
                    break
                if side not in self._tactile_selection:
                    continue

            started_at = time.monotonic()
            try:
                tactile = self._hands[side].read_tactile()
                regions = {
                    name: np.asarray(values, dtype=np.uint16).astype(
                        int, copy=False
                    ).tolist()
                    for name, values in tactile.items()
                }
                force_reader = getattr(self._hands[side], "read_actual_forces", None)
                if force_reader is not None and started_at >= next_force_at:
                    next_force_at = started_at + force_period
                    try:
                        force_values = np.asarray(force_reader(), dtype=np.int16)
                        if force_values.shape != (JOINT_COUNT,):
                            raise RuntimeError(
                                "actual forces must contain "
                                f"{JOINT_COUNT} values, got {force_values.shape}"
                            )
                    except Exception as error:
                        force_error = str(error)
                    else:
                        forces = force_values.astype(int, copy=False).tolist()
                        force_captured_at = time.monotonic()
                        force_error = ""
            except Exception as error:
                message = str(error)
                with self._tactile_condition:
                    if side not in self._tactile_selection:
                        continue
                    previous = self._tactile_errors.get(side)
                    self._tactile_errors[side] = message
                if previous != message:
                    logger_mp.warning(
                        "Could not read %s-hand tactile data: %s", side, error
                    )
            else:
                with self._tactile_condition:
                    if side in self._tactile_selection:
                        captured_at = time.monotonic()
                        previous_frame = self._tactile_frames.get(side)
                        if previous_frame is not None:
                            interval = captured_at - previous_frame[0]
                            if interval > 0:
                                measured_rate = 1.0 / interval
                                previous_rate = self._tactile_rates.get(side, 0.0)
                                self._tactile_rates[side] = (
                                    measured_rate
                                    if previous_rate <= 0
                                    else 0.75 * previous_rate + 0.25 * measured_rate
                                )
                        self._tactile_frames[side] = (
                            captured_at,
                            regions,
                            force_captured_at,
                            forces,
                            force_error,
                        )
                        self._tactile_revisions[side] = (
                            self._tactile_revisions.get(side, 0) + 1
                        )
                        self._tactile_errors.pop(side, None)

            deadline = started_at + sample_period
            with self._tactile_condition:
                while (
                    not self._stop_event.is_set()
                    and side in self._tactile_selection
                ):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._tactile_condition.wait(remaining)

    def _publish_speeds(self, side: str, speeds: np.ndarray) -> None:
        shared = self.left_hand_speed_array if side == "left" else self.right_hand_speed_array
        with shared.get_lock():
            shared[:] = speeds.tolist()

    def _control_loop(self) -> None:
        targets = {side: self._initial_state[side].copy() for side in ("left", "right")}
        states = {side: self._initial_state[side].copy() for side in ("left", "right")}
        filtered_targets: dict[str, np.ndarray] = {}
        planners_v1 = {
            side: AdaptiveSpeedPlanner(initial_speed=self._fixed_speed)
            for side in self._hands
        }
        speed_config = AdaptiveSpeedConfig()
        planners_v2 = {
            side: AdaptiveSpeedPlannerV2(speed_config) for side in self._hands
        }
        last_written_speeds: dict[str, np.ndarray | None] = {
            side: np.full(JOINT_COUNT, self._fixed_speed, dtype=int)
            for side in self._hands
        }
        active_mode = self.speed_mode
        active_motion_filter = self.motion_filter_enabled
        fixed_speeds = np.full(JOINT_COUNT, self._fixed_speed, dtype=int)
        for side in self._hands:
            self._publish_speeds(side, fixed_speeds)
        executor = (
            ThreadPoolExecutor(
                max_workers=len(self._hands),
                thread_name_prefix="hand-modbus-io",
            )
            if len(self._hands) > 1
            else None
        )
        try:
            while not self._stop_event.is_set():
                started_at = time.monotonic()
                requested_mode = self.speed_mode
                requested_motion_filter = self.motion_filter_enabled
                if requested_motion_filter != active_motion_filter:
                    active_motion_filter = requested_motion_filter
                    filtered_targets.clear()
                    logger_mp.info(
                        "Hand motion micro-filter %s.",
                        "enabled" if active_motion_filter else "disabled",
                    )
                speed_writes: dict[str, list[int]] = {}
                if requested_mode != active_mode:
                    active_mode = requested_mode
                    last_written_speeds = {side: None for side in self._hands}
                    now = time.monotonic()
                    for planner in planners_v1.values():
                        planner.reset(self._fixed_speed)
                    for side, planner in planners_v2.items():
                        planner.reset(
                            target=targets[side],
                            initial_speed=self._fixed_speed,
                            now=now,
                        )
                    if active_mode == "fixed":
                        speed_writes = {
                            side: fixed_speeds.tolist() for side in self._hands
                        }
                    logger_mp.info("Hand speed mode changed to %s.", active_mode)
                fresh_sides: set[str] = set()
                if self._consume_motion_data_ready():
                    landmarks_by_side = self._read_landmarks()
                    for side in self._hands:
                        try:
                            landmarks = landmarks_by_side[side]
                            indices = getattr(self._hand_retargeting, f"{side}_indices")
                            retargeting = getattr(
                                self._hand_retargeting, f"{side}_retargeting"
                            )
                            joint_order = getattr(
                                self._hand_retargeting,
                                f"{side}_dex_retargeting_to_hardware",
                            )
                            reference = (
                                landmarks[indices[1, :]] - landmarks[indices[0, :]]
                            )
                            radians = retargeting.retarget(reference)[joint_order]
                            target = self._normalize_targets(radians)
                            if not np.isfinite(target).all():
                                raise ValueError("retargeting produced non-finite targets")
                            if active_motion_filter:
                                target = self._smooth_motion_target(
                                    target, filtered_targets.get(side)
                                )
                                filtered_targets[side] = target.copy()
                            targets[side] = target
                            fresh_sides.add(side)
                        except (TypeError, ValueError) as error:
                            logger_mp.warning(
                                "Ignoring invalid %s-hand target: %s", side, error
                            )

                commands: dict[str, list[int]] = {}
                for side in self._hands:
                    if side not in fresh_sides:
                        continue
                    try:
                        if active_mode == "adaptive_v2":
                            speeds = np.asarray(
                                planners_v2[side].compute(targets[side], states[side]),
                                dtype=int,
                            )
                        elif active_mode == "adaptive_v1":
                            speeds = planners_v1[side].calculate(
                                targets[side], states[side]
                            )
                        else:
                            speeds = fixed_speeds
                    except (TypeError, ValueError) as error:
                        logger_mp.warning(
                            "Ignoring invalid %s-hand adaptive input: %s", side, error
                        )
                        continue
                    speeds = np.clip(speeds, 0, 1000).astype(int)
                    previous_speeds = last_written_speeds[side]
                    if (
                        previous_speeds is None
                        or np.max(np.abs(speeds - previous_speeds))
                        >= speed_config.write_threshold
                    ):
                        speed_writes[side] = speeds.tolist()
                    commands[side] = (
                        np.rint(targets[side] * 1000).astype(int).tolist()
                    )

                state = self._run_hand_cycles(executor, commands, speed_writes)
                for side, speeds in speed_writes.items():
                    published_speeds = np.asarray(speeds, dtype=int)
                    last_written_speeds[side] = published_speeds.copy()
                    self._publish_speeds(side, published_speeds)
                states["left"] = state[:JOINT_COUNT]
                states["right"] = state[JOINT_COUNT:]
                self._publish_observation(
                    state, np.concatenate((targets["left"], targets["right"]))
                )
                wait_time = max(0.0, 1.0 / self.fps - (time.monotonic() - started_at))
                self._stop_event.wait(wait_time)
        except BaseException as error:
            self._control_error = error
            self._stop_event.set()
            logger_mp.exception("Hand Modbus control loop stopped due to an error.")
        finally:
            if executor is not None:
                executor.shutdown(wait=True)

    def raise_if_failed(self) -> None:
        """Surface an asynchronous control failure in the teleop main thread."""

        if self._control_error is not None:
            raise RuntimeError("Hand Modbus control loop failed") from self._control_error

    def stop(self, timeout: float | None = None, open_hand: bool = False) -> None:
        """Stop control, optionally open enabled hands, then close sockets."""

        self._stop_event.set()
        with self._tactile_condition:
            self._tactile_condition.notify_all()
        wait_timeout = self._request_timeout + 1.0 if timeout is None else timeout
        threads = [
            thread
            for thread in [
                getattr(self, "_control_thread", None),
                *getattr(self, "_tactile_threads", {}).values(),
            ]
            if thread is not None
        ]
        deadline = time.monotonic() + wait_timeout
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        alive = [thread for thread in threads if thread.is_alive()]
        if alive:
            # Closing the sockets interrupts pending Modbus requests. Do not
            # send an optional open command while either worker may still use
            # the same clients.
            logger_mp.warning(
                "Hand Modbus worker did not stop in time; closing its "
                "connections without sending an open command."
            )
            self._close_hands()
            for thread in alive:
                thread.join(1.0)
                if thread.is_alive():
                    logger_mp.error(
                        "Hand Modbus worker %s is still running after socket close.",
                        thread.name,
                    )
            return
        try:
            if open_hand:
                for hand in self._hands.values():
                    hand.write_target_angles([1000] * JOINT_COUNT)
        finally:
            self._close_hands()

    def _close_hands(self) -> None:
        for hand in self._hands.values():
            try:
                hand.close()
            except Exception:
                logger_mp.exception("Failed to close a Dexhand connection.")
