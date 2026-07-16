import numpy as np
import pytest

from viewer.backend.control.controller import (
    ControlState,
    TransitionError,
    VisionHandController,
)
from viewer.backend.state import TrackingSnapshot, TrackingStatus


class FakeDriver:
    host = "192.0.2.10"
    port = 6000

    def __init__(self):
        self.connected = False
        self.positions = np.array([900, 800, 700, 600, 500, 400])
        self.writes = []
        self.holds = 0
        self.fail_write = False

    def connect(self):
        self.connected = True

    def close(self):
        self.connected = False

    def read_positions(self):
        return self.positions.copy()

    def write_motion(self, positions, speeds):
        if self.fail_write:
            raise RuntimeError("write failed")
        self.writes.append((list(positions), list(speeds)))
        self.positions = np.asarray(positions, dtype=int)

    def hold_current(self):
        self.holds += 1
        self.write_motion(self.positions, [100] * 6)
        return self.positions.copy()


def tracked(now=100.0, targets=None):
    return TrackingSnapshot(
        status=TrackingStatus.TRACKING,
        published_at=now,
        actuators=targets or [0] * 6,
    )


def make_controller():
    driver = FakeDriver()
    controller = VisionHandController(driver=driver, start_worker=False)
    return controller, driver


def test_start_connects_and_reads_without_writing():
    controller, driver = make_controller()
    controller.start()

    snapshot = controller.snapshot()

    assert snapshot.state is ControlState.DISARMED
    assert snapshot.actual == [900, 800, 700, 600, 500, 400]
    assert driver.writes == []


def test_arm_seeds_from_measured_position_then_slews_on_tick():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())

    armed = controller.arm(now=100.05)
    controller.tick(now=100.06)

    assert armed.state is ControlState.ARMED
    assert armed.commanded == [900, 800, 700, 600, 500, 400]
    assert driver.writes[-1][0] == [780, 680, 580, 480, 380, 160]
    assert driver.writes[-1][1] == [450, 450, 450, 450, 450, 900]


def test_stale_tracking_holds_once_during_recovery_grace():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked(now=100.0))
    controller.arm(now=100.05)

    controller.tick(now=100.2)
    controller.tick(now=100.4)

    snapshot = controller.snapshot()
    assert snapshot.state is ControlState.ARMED
    assert snapshot.tracking_hold is True
    assert snapshot.tracking_loss_ms == pytest.approx(200)
    assert driver.holds == 1


def test_tracking_recovers_within_grace_without_rearming():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())
    controller.arm(now=100.01)
    controller.update_tracking(TrackingSnapshot(status=TrackingStatus.LOST))

    controller.tick(now=100.02)
    controller.update_tracking(tracked(now=100.20, targets=[700] * 6))
    controller.tick(now=100.21)

    snapshot = controller.snapshot()
    assert snapshot.state is ControlState.ARMED
    assert snapshot.tracking_hold is False
    assert snapshot.tracking_loss_ms is None
    assert driver.holds == 1
    resumed = driver.writes[-1][0]
    measured = [900, 800, 700, 600, 500, 400]
    assert resumed != measured
    for index, (current, command) in enumerate(zip(measured, resumed)):
        assert min(current, 700) <= command <= max(current, 700)
        assert abs(command - current) <= (240 if index == 5 else 120)


def test_sustained_tracking_loss_remains_armed_and_holds_once():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())
    controller.arm(now=100.01)
    controller.update_tracking(TrackingSnapshot(status=TrackingStatus.LOST))

    controller.tick(now=100.02)
    controller.tick(now=130.02)

    snapshot = controller.snapshot()
    assert snapshot.state is ControlState.ARMED
    assert snapshot.tracking_hold is True
    assert snapshot.tracking_loss_ms == pytest.approx(30_000)
    assert driver.holds == 1


@pytest.mark.parametrize(
    "status", [TrackingStatus.WRONG_HAND, TrackingStatus.CAMERA_ERROR]
)
def test_nontracking_status_holds_without_ending_arm_session(status):
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())
    controller.arm(now=100.01)
    controller.update_tracking(TrackingSnapshot(status=status))

    controller.tick(now=100.02)

    assert controller.snapshot().state is ControlState.ARMED
    assert controller.snapshot().tracking_hold is True
    assert driver.holds == 1


def test_malformed_tracking_targets_hold_and_disarm_immediately():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())
    controller.arm(now=100.01)
    controller.update_tracking(
        TrackingSnapshot(
            status=TrackingStatus.TRACKING,
            published_at=100.02,
            actuators=[100, 200],
        )
    )

    controller.tick(now=100.03)

    assert controller.snapshot().state is ControlState.DISARMED
    assert driver.holds == 1


def test_estop_is_latched_until_reset():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())
    controller.arm(now=100.01)

    controller.estop()

    assert controller.snapshot().state is ControlState.ESTOPPED
    assert driver.holds == 1
    with pytest.raises(TransitionError):
        controller.arm(now=100.02)
    reset = controller.reset()
    assert reset.state is ControlState.DISARMED
    assert driver.writes == [([900, 800, 700, 600, 500, 400], [100] * 6)]


def test_write_failure_enters_fault_without_continuing():
    controller, driver = make_controller()
    controller.start()
    controller.update_tracking(tracked())
    controller.arm(now=100.01)
    driver.fail_write = True

    controller.tick(now=100.02)

    snapshot = controller.snapshot()
    assert snapshot.state is ControlState.FAULT
    assert "write failed" in snapshot.error


def test_invalid_transitions_are_rejected():
    controller, _driver = make_controller()
    with pytest.raises(TransitionError):
        controller.arm(now=100)
    controller.start()
    with pytest.raises(TransitionError):
        controller.reset()


def test_home_seeds_positioning_from_measured_position():
    controller, driver = make_controller()
    controller.start()

    positioning = controller.home(now=100.0)

    assert positioning.state.value == "POSITIONING"
    assert positioning.preset.value == "HOME"
    assert positioning.targets == [120, 120, 120, 120, 180, 480]
    assert positioning.commanded == [900, 800, 700, 600, 500, 400]
    assert driver.writes == []

    controller.tick(now=100.01)

    assert driver.writes[-1][0] == [820, 720, 620, 520, 420, 440]
    assert driver.writes[-1][1] == [300, 300, 300, 300, 300, 180]
    assert controller.snapshot().state.value == "POSITIONING"


def test_open_uses_fully_open_target_and_slower_preset_motion_profile():
    controller, driver = make_controller()
    controller.start()

    positioning = controller.open(now=100.0)
    controller.tick(now=100.01)

    assert positioning.state.value == "POSITIONING"
    assert positioning.preset.value == "OPEN"
    assert positioning.targets == [1000] * 6
    assert driver.writes[-1][0] == [940, 880, 780, 680, 580, 480]
    assert driver.writes[-1][1] == [180, 300, 300, 300, 300, 300]


def test_open_completes_with_physical_readback_near_full_scale():
    controller, driver = make_controller()
    controller.start()
    controller.open(now=100.0)
    driver.positions = np.array([992, 991, 998, 992, 992, 987])

    completed = controller.tick(now=100.5)

    assert completed.state is ControlState.DISARMED
    assert driver.holds == 1


def test_home_completes_with_hold_after_all_channels_reach_deadband():
    controller, driver = make_controller()
    controller.start()
    controller.home(now=100.0)
    driver.positions = np.array([124, 115, 120, 120, 180, 480])

    completed = controller.tick(now=100.5)

    assert completed.state is ControlState.DISARMED
    assert completed.preset is None
    assert completed.targets == [120, 120, 120, 120, 180, 480]
    assert driver.holds == 1


def test_home_rejects_non_disarmed_state_and_estop_interrupts_motion():
    controller, driver = make_controller()
    controller.start()
    controller.home(now=100.0)

    with pytest.raises(TransitionError):
        controller.home(now=100.1)

    stopped = controller.estop()

    assert stopped.state is ControlState.ESTOPPED
    assert driver.holds == 1


def test_home_timeout_holds_and_enters_fault():
    controller, driver = make_controller()
    controller.start()
    controller.home(now=100.0)

    timed_out = controller.tick(now=120.01)

    assert timed_out.state is ControlState.FAULT
    assert timed_out.error == "HOME positioning timed out after 20 seconds"
    assert driver.holds == 1


def test_stop_holds_an_active_home_before_disconnect():
    controller, driver = make_controller()
    controller.start()
    controller.home(now=100.0)

    controller.stop()

    assert driver.holds == 1
    assert controller.snapshot().state is ControlState.DISCONNECTED
