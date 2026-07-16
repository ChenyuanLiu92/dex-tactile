import numpy as np

import openteach.components.operators.inspire as inspire_operator
from openteach.components.operators.inspire import InspireHandOperator
from openteach.robot.inspire.retargeting import InspireMotionCommand


class Subscriber:
    def __init__(self, value):
        self.value = value

    def recv_keypoints(self):
        return self.value


class Robot:
    def __init__(self, log_commands=False):
        self.log_commands = log_commands
        self.moves = []

    def get_joint_position(self):
        return np.full(6, 500, dtype=int)

    def move(self, positions, speed=None):
        self.moves.append((positions.copy(), speed.copy()))


class Retargeter:
    def retarget_command(self, keypoints, current):
        return InspireMotionCommand(
            positions=np.full(6, 518, dtype=int),
            speeds=np.full(6, 80, dtype=int),
            targets=np.full(6, 550, dtype=int),
            errors=np.full(6, 50, dtype=int),
        )


class Timer:
    def __init__(self, frequency):
        self.frequency = frequency


def make_operator(pause_state=1, keypoints=None, log_commands=False):
    operator = InspireHandOperator.__new__(InspireHandOperator)
    operator._transformed_hand_keypoint_subscriber = Subscriber(
        np.zeros((24, 3)) if keypoints is None else keypoints
    )
    operator._pause_subscriber = Subscriber([pause_state])
    operator._robot = Robot(log_commands=log_commands)
    operator._retargeter = Retargeter()
    operator._log_every = 4
    operator._loop_count = 0
    return operator


def test_operator_passes_adaptive_positions_and_speeds_to_robot():
    operator = make_operator()

    operator._apply_retargeted_angles()

    positions, speeds = operator.robot.moves[0]
    assert positions.tolist() == [518] * 6
    assert speeds.tolist() == [80] * 6


def test_operator_does_not_write_while_paused_or_tracking_frame_is_invalid():
    paused = make_operator(pause_state=0)
    missing_pause = make_operator(pause_state=None)
    invalid = make_operator(keypoints=np.zeros((2, 3)))

    paused._apply_retargeted_angles()
    missing_pause._apply_retargeted_angles()
    invalid._apply_retargeted_angles()

    assert paused.robot.moves == []
    assert missing_pause.robot.moves == []
    assert invalid.robot.moves == []


def test_operator_logs_motion_diagnostics_at_throttled_interval(capsys):
    operator = make_operator(log_commands=True)
    operator._log_every = 1

    operator._apply_retargeted_angles()

    output = capsys.readouterr().out
    assert 'current=[500, 500, 500, 500, 500, 500]' in output
    assert 'target=[550, 550, 550, 550, 550, 550]' in output
    assert 'command=[518, 518, 518, 518, 518, 518]' in output
    assert 'error=[50, 50, 50, 50, 50, 50]' in output
    assert 'speed=[80, 80, 80, 80, 80, 80]' in output


def test_operator_uses_configured_frequency_and_five_hz_logging(monkeypatch):
    monkeypatch.setattr(inspire_operator, 'ZMQKeypointSubscriber', lambda *_: Subscriber(None))
    monkeypatch.setattr(inspire_operator, 'FrequencyTimer', Timer)
    monkeypatch.setattr(InspireHandOperator, 'notify_component_start', lambda *_: None)

    operator = InspireHandOperator(
        host='127.0.0.1',
        transformed_keypoints_port=8089,
        teleop_reset_port=8102,
        robot=Robot(),
        control_frequency=30,
    )

    assert operator.timer.frequency == 30
    assert operator._log_every == 6
