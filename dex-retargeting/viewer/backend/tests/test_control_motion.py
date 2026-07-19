import numpy as np
import pytest

from viewer.backend.control.motion import AdaptiveMotion, MotionCommand


def test_motion_applies_open_teach_aggressive_bands_independently():
    motion = AdaptiveMotion()
    command = motion.command(
        targets=[509, 550, 800, 491, 450, 200],
        current=[500] * 6,
    )

    assert isinstance(command, MotionCommand)
    assert command.positions.tolist() == [509, 550, 620, 491, 450, 380]
    assert command.speeds.tolist() == [100, 260, 450, 100, 260, 450]


def test_motion_holds_inside_deadband_and_clips_targets():
    command = AdaptiveMotion().command(
        targets=[1008, -5, 1000, 992, 500, 500],
        current=[1000, 0, 1000, 1000, 500, 500],
    )
    assert command.targets.tolist() == [1000, 0, 1000, 992, 500, 500]
    assert command.positions.tolist() == [1000, 0, 1000, 1000, 500, 500]


def test_motion_applies_hysteresis_between_bands():
    motion = AdaptiveMotion()
    assert motion.command([539] * 6, [500] * 6).speeds.tolist() == [100] * 6
    assert motion.command([549] * 6, [500] * 6).speeds.tolist() == [100] * 6
    assert motion.command([551] * 6, [500] * 6).speeds.tolist() == [260] * 6
    assert motion.command([531] * 6, [500] * 6).speeds.tolist() == [260] * 6
    assert motion.command([530] * 6, [500] * 6).speeds.tolist() == [100] * 6


def test_motion_supports_faster_thumb_bend_and_yaw_channels():
    motion = AdaptiveMotion(
        channel_step_scales=[1, 1, 1, 1, 1.5, 2],
        channel_speed_scales=[1, 1, 1, 1, 1.5, 2],
    )

    command = motion.command([0] * 6, [500] * 6)

    assert command.positions.tolist() == [380, 380, 380, 380, 320, 260]
    assert command.speeds.tolist() == [450, 450, 450, 450, 675, 900]


def test_motion_keeps_speed_from_feedback_error_after_waypoint_reaches_target():
    motion = AdaptiveMotion(
        channel_step_scales=[1, 1, 1, 1, 1.5, 2],
        channel_speed_scales=[1, 1, 1, 1, 1.5, 2],
    )

    command = motion.command(
        targets=[0] * 6,
        current=[0] * 6,
        feedback=[500] * 6,
    )

    assert command.positions.tolist() == [0] * 6
    assert command.speeds.tolist() == [450, 450, 450, 450, 675, 900]


@pytest.mark.parametrize("values", [[1, 2], [np.nan] * 6, [np.inf] * 6])
def test_motion_rejects_malformed_or_nonfinite_values(values):
    with pytest.raises(ValueError):
        AdaptiveMotion().command(values, [500] * 6)


@pytest.mark.parametrize("feedback", [[1, 2], [np.nan] * 6, [np.inf] * 6])
def test_motion_rejects_malformed_feedback(feedback):
    with pytest.raises(ValueError):
        AdaptiveMotion().command([500] * 6, [500] * 6, feedback=feedback)
