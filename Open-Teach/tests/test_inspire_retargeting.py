from pathlib import Path

import numpy as np
import yaml

from openteach.robot.inspire.retargeting import (
    InspireMotionCommand,
    InspireRetargeter,
    finger_bend,
)


def test_finger_bend_distinguishes_straight_and_curled_fingers():
    straight = np.array([[0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 3, 0]], dtype=float)
    curled = np.array([[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]], dtype=float)

    assert finger_bend(straight) == 0
    assert finger_bend(curled) > 0.45


def test_retargeter_outputs_inspire_channel_order_and_limits_slew_rate():
    keypoints = np.zeros((24, 3), dtype=float)
    keypoints[6], keypoints[7], keypoints[8], keypoints[20] = [1, 0, 0], [1, 1, 0], [2, 1, 0], [2, 0, 0]
    keypoints[9], keypoints[10], keypoints[11], keypoints[21] = [0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 3, 0]
    keypoints[12], keypoints[13], keypoints[14], keypoints[22] = keypoints[9], keypoints[10], keypoints[11], keypoints[21]
    keypoints[15], keypoints[16], keypoints[17], keypoints[18], keypoints[23] = [-1, 0, 0], [-1, 1, 0], [-1, 2, 0], [-1, 3, 0], [-1, 4, 0]
    keypoints[2], keypoints[3], keypoints[4], keypoints[5], keypoints[19] = [0, 0, 0], [0.5, 0, 0], [1, 0, 0], [1.5, 0, 0], [2, 0, 0]
    keypoints[19] = [2, 0, 0]

    retargeter = InspireRetargeter(open_bend=0, closed_bend=0.5, max_step=100)
    values = retargeter.retarget(keypoints, previous=np.full(6, 1000))

    assert values.tolist() == [1000, 1000, 1000, 900, 1000, 1000]


def make_adaptive_retargeter():
    return InspireRetargeter(
        adaptive_motion={
            'enabled': True,
            'deadband': 8,
            'error_thresholds': [40, 180],
            'max_steps': [6, 18, 40],
            'speeds': [30, 80, 160],
            'hysteresis': 10,
        }
    )


def test_adaptive_command_holds_channels_inside_deadband():
    retargeter = make_adaptive_retargeter()

    command = retargeter.adapt_targets(
        targets=[1008, 992, 1000, 1000, 1000, 1000],
        current=[1000] * 6,
    )

    assert isinstance(command, InspireMotionCommand)
    assert command.positions.tolist() == [1000] * 6
    assert command.speeds.tolist() == [30] * 6
    assert command.targets.tolist() == [1000, 992, 1000, 1000, 1000, 1000]
    assert command.errors.tolist() == [0, -8, 0, 0, 0, 0]


def test_adaptive_command_uses_balanced_error_bands_per_channel():
    retargeter = make_adaptive_retargeter()

    command = retargeter.adapt_targets(
        targets=[491, 450, 200, 509, 550, 800],
        current=[500] * 6,
    )

    assert command.positions.tolist() == [494, 482, 460, 506, 518, 540]
    assert command.speeds.tolist() == [30, 80, 160, 30, 80, 160]


def test_adaptive_command_applies_hysteresis_when_crossing_speed_thresholds():
    retargeter = make_adaptive_retargeter()

    first = retargeter.adapt_targets([539] * 6, [500] * 6)
    still_low = retargeter.adapt_targets([549] * 6, [500] * 6)
    medium = retargeter.adapt_targets([551] * 6, [500] * 6)
    still_medium = retargeter.adapt_targets([531] * 6, [500] * 6)
    low_again = retargeter.adapt_targets([530] * 6, [500] * 6)

    assert first.speeds.tolist() == [30] * 6
    assert still_low.speeds.tolist() == [30] * 6
    assert medium.speeds.tolist() == [80] * 6
    assert still_medium.speeds.tolist() == [80] * 6
    assert low_again.speeds.tolist() == [30] * 6


def test_inspire_config_uses_approved_aggressive_motion_profile():
    config_path = (
        Path(__file__).resolve().parents[1]
        / 'configs'
        / 'robot'
        / 'inspire_hand.yaml'
    )
    with config_path.open() as config_file:
        config = yaml.safe_load(config_file)

    operator = config['operators'][0]
    adaptive = operator['retargeting']['adaptive_motion']

    assert operator['retargeting']['backend'] == 'dex'
    assert operator['control_frequency'] == 30
    assert adaptive['error_thresholds'] == [40, 180]
    assert adaptive['max_steps'] == [20, 60, 120]
    assert adaptive['speeds'] == [100, 260, 450]
    assert adaptive['deadband'] == 8
    assert adaptive['hysteresis'] == 10


def test_aggressive_profile_applies_independent_steps_and_speeds():
    retargeter = InspireRetargeter(
        adaptive_motion={
            'enabled': True,
            'deadband': 8,
            'error_thresholds': [40, 180],
            'max_steps': [20, 60, 120],
            'speeds': [100, 260, 450],
            'hysteresis': 10,
        }
    )

    command = retargeter.adapt_targets(
        targets=[509, 550, 800, 491, 450, 200],
        current=[500] * 6,
    )

    assert command.positions.tolist() == [509, 550, 620, 491, 450, 380]
    assert command.speeds.tolist() == [100, 260, 450, 100, 260, 450]
