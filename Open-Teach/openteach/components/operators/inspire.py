import numpy as np

from openteach.components.operators.operator import Operator
from openteach.constants import ARM_TELEOP_CONT
from openteach.robot.inspire.retargeting import build_inspire_retargeter
from openteach.utils.network import ZMQKeypointSubscriber
from openteach.utils.timer import FrequencyTimer


class InspireHandOperator(Operator):
    def __init__(
        self,
        host,
        transformed_keypoints_port,
        teleop_reset_port,
        robot,
        retargeting=None,
        control_frequency=20,
    ):
        self.notify_component_start('Inspire RH56DFTP hand operator')
        self._transformed_hand_keypoint_subscriber = ZMQKeypointSubscriber(
            host, transformed_keypoints_port, 'transformed_hand_coords'
        )
        self._transformed_arm_keypoint_subscriber = ZMQKeypointSubscriber(
            host, transformed_keypoints_port, 'transformed_hand_frame'
        )
        self._pause_subscriber = ZMQKeypointSubscriber(host, teleop_reset_port, 'pause')
        self._robot = robot
        self._retargeter = build_inspire_retargeter(retargeting)
        control_frequency = int(control_frequency)
        if control_frequency <= 0:
            raise ValueError('control_frequency must be positive')
        self._timer = FrequencyTimer(control_frequency)
        self._log_every = max(1, round(control_frequency / 5))
        self._loop_count = 0

    @property
    def timer(self):
        return self._timer

    @property
    def robot(self):
        return self._robot

    @property
    def transformed_hand_keypoint_subscriber(self):
        return self._transformed_hand_keypoint_subscriber

    @property
    def transformed_arm_keypoint_subscriber(self):
        return self._transformed_arm_keypoint_subscriber

    def return_real(self):
        return False

    def stream(self):
        try:
            super().stream()
        finally:
            self._pause_subscriber.stop()
            self.robot.close()

    def _apply_retargeted_angles(self):
        pause_state = self._pause_subscriber.recv_keypoints()
        if pause_state is None:
            return
        try:
            pause_values = np.asarray(pause_state, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            return
        enabled = (
            len(pause_values) > 0
            and np.isfinite(pause_values[0])
            and int(pause_values[0]) == ARM_TELEOP_CONT
        )
        if not enabled:
            return
        keypoint_values = np.asarray(
            self.transformed_hand_keypoint_subscriber.recv_keypoints(), dtype=float
        )
        if keypoint_values.size != 72 or not np.all(np.isfinite(keypoint_values)):
            return
        keypoints = keypoint_values.reshape(24, 3)
        current = self.robot.get_joint_position()
        command = self._retargeter.retarget_command(keypoints, current)
        self.robot.move(command.positions, speed=command.speeds)

        self._loop_count += 1
        if self.robot.log_commands and self._loop_count % self._log_every == 0:
            print(
                'Inspire motion '
                f'current={current.tolist()} '
                f'target={command.targets.tolist()} '
                f'command={command.positions.tolist()} '
                f'error={command.errors.tolist()} '
                f'speed={command.speeds.tolist()}'
            )
