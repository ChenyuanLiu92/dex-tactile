import numpy as np

import openteach.components.operators.inspire as inspire_operator
from openteach.components.operators.inspire import InspireHandOperator
from openteach.robot.inspire.dex_retargeting import DexInspireRetargeter
from openteach.robot.inspire.retargeting import build_inspire_retargeter


class FakeDexSolver:
    def __init__(self, targets):
        self.targets = targets
        self.received = None

    def retarget(self, landmarks):
        self.received = np.asarray(landmarks)
        return {}, self.targets

    def get_contact_status(self):
        return {'state': 'NONE'}


def quest_pose():
    points = np.zeros((24, 3), dtype=float)
    points[0] = [0.0, 0.0, 0.0]
    points[[2, 3, 4, 5, 19]] = [
        [0.03, -0.01, 0.0], [0.05, -0.02, 0.0], [0.07, -0.03, 0.0],
        [0.08, -0.04, 0.0], [0.09, -0.05, 0.0],
    ]
    for indices, x in (((6, 7, 8, 20), 0.022), ((9, 10, 11, 21), 0.0), ((12, 13, 14, 22), -0.022), ((16, 17, 18, 23), -0.044)):
        points[list(indices)] = [[x, -0.025, 0.0], [x, -0.055, 0.0], [x, -0.085, 0.0], [x, -0.115, 0.0]]
    points[15] = [-0.055, -0.01, 0.0]
    return points


def test_dex_backend_converts_quest_points_and_preserves_motion_limits():
    solver = FakeDexSolver([100, 200, 300, 400, 500, 600])
    retargeter = DexInspireRetargeter(
        solver=solver,
        adaptive_motion={
            'enabled': True,
            'deadband': 8,
            'error_thresholds': [40, 180],
            'max_steps': [20, 60, 120],
            'speeds': [100, 260, 450],
            'hysteresis': 10,
        },
    )

    command = retargeter.retarget_command(quest_pose(), np.full(6, 500))

    assert solver.received.shape == (21, 3)
    assert np.all(np.isfinite(solver.received))
    assert command.targets.tolist() == [100, 200, 300, 400, 500, 600]
    assert command.positions.tolist() == [380, 380, 380, 440, 500, 560]
    assert command.speeds.tolist() == [450, 450, 450, 260, 100, 260]


def test_factory_selects_dex_backend_without_changing_operator_contract():
    solver = FakeDexSolver([500] * 6)
    retargeter = build_inspire_retargeter({'backend': 'dex', 'solver': solver})

    assert isinstance(retargeter, DexInspireRetargeter)
    assert retargeter.get_contact_status() == {'state': 'NONE'}


def test_open_teach_operator_routes_quest_frame_through_real_dex_solver(monkeypatch):
    payloads = {
        'transformed_hand_coords': quest_pose().reshape(-1),
        'transformed_hand_frame': np.zeros(12),
        'pause': np.array([1]),
    }

    class Subscriber:
        def __init__(self, value):
            self.value = value

        def recv_keypoints(self):
            return self.value

        def stop(self):
            pass

    class Timer:
        def __init__(self, frequency):
            self.frequency = frequency

    class DryRunRobot:
        log_commands = False

        def __init__(self):
            self.current = np.full(6, 700)
            self.command = None
            self.speed = None

        def get_joint_position(self):
            return self.current.copy()

        def move(self, command, speed=None):
            self.command = np.asarray(command)
            self.speed = np.asarray(speed)

    monkeypatch.setattr(
        inspire_operator,
        'ZMQKeypointSubscriber',
        lambda _host, _port, topic: Subscriber(payloads[topic]),
    )
    monkeypatch.setattr(inspire_operator, 'FrequencyTimer', Timer)
    monkeypatch.setattr(InspireHandOperator, 'notify_component_start', lambda *_: None)
    robot = DryRunRobot()
    operator = InspireHandOperator(
        host='127.0.0.1',
        transformed_keypoints_port=8089,
        teleop_reset_port=8102,
        robot=robot,
        control_frequency=30,
        retargeting={
            'backend': 'dex',
            'adaptive_motion': {
                'enabled': True,
                'deadband': 8,
                'error_thresholds': [40, 180],
                'max_steps': [20, 60, 120],
                'speeds': [100, 260, 450],
                'hysteresis': 10,
            },
        },
    )

    operator._apply_retargeted_angles()

    assert robot.command.shape == (6,)
    assert robot.speed.shape == (6,)
    assert np.all((robot.command >= 0) & (robot.command <= 1000))
    assert np.max(np.abs(robot.command - robot.current)) <= 120
    assert set(robot.speed).issubset({100, 260, 450})
