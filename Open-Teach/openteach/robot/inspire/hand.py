import time

import numpy as np
from pymodbus.client.sync import ModbusTcpClient

from openteach.robot.robot import RobotWrapper

ANGLE_SET = 1486
FORCE_SET = 1498
SPEED_SET = 1522
ANGLE_ACT = 1546


class InspireHand(RobotWrapper):
    def __init__(
        self,
        host,
        port=6000,
        dry_run=True,
        speed=120,
        force=500,
        timeout=0.5,
        log_commands=False,
        client_factory=None,
        **_,
    ):
        self.host = host
        self.port = int(port)
        self.dry_run = bool(dry_run)
        self.speed = self._expand_channels(speed, 'speed')
        self.force = self._expand_channels(force, 'force')
        self.log_commands = bool(log_commands)
        self._client_factory = client_factory or (
            lambda host, port: ModbusTcpClient(host, port=port, timeout=timeout)
        )
        self._client = None
        self._commanded = np.full(6, 1000, dtype=int)
        self._written_speed = None
        self._written_force = None
        self._data_frequency = 20
        if not self.dry_run:
            self._connect()
            self._commanded = self._read_angles()

    @property
    def name(self):
        return 'inspire_rh56dftp'

    @property
    def recorder_functions(self):
        return {
            'joint_states': self.get_joint_state,
            'commanded_joint_states': self.get_commanded_joint_state,
        }

    @property
    def data_frequency(self):
        return self._data_frequency

    def _connect(self):
        self._client = self._client_factory(self.host, self.port)
        if self._client.connect() is not True:
            self._client.close()
            self._client = None
            raise ConnectionError(f'Unable to connect to Inspire hand at {self.host}:{self.port}')

    def _read_angles(self):
        response = self._client.read_holding_registers(ANGLE_ACT, 6)
        values = getattr(response, 'registers', ())
        if response.isError() or len(values) != 6:
            raise RuntimeError('Invalid ANGLE_ACT response from Inspire hand')
        return np.asarray(values, dtype=int)

    @staticmethod
    def _validate(values, maximum=1000):
        values = np.asarray(values, dtype=int).reshape(-1)
        if len(values) != 6 or np.any(values < 0) or np.any(values > maximum):
            raise ValueError(f'Expected six values in the range 0..{maximum}')
        return values

    @classmethod
    def _expand_channels(cls, values, name):
        array = np.asarray(values, dtype=int).reshape(-1)
        if len(array) == 1:
            array = np.full(6, int(array[0]), dtype=int)
        if len(array) != 6 or np.any(array < 0) or np.any(array > 1000):
            raise ValueError(f'{name} must be one value or six values in the range 0..1000')
        return array

    def _write_registers(self, address, values):
        response = self._client.write_registers(address, values.tolist())
        if response.isError():
            raise RuntimeError(f'Inspire Modbus write failed at register {address}')

    def get_joint_position(self):
        if not self.dry_run:
            self._commanded = self._read_angles()
        return self._commanded.copy()

    def get_joint_state(self):
        return {'position': self.get_joint_position(), 'timestamp': time.time()}

    def get_commanded_joint_state(self):
        return {'position': self._commanded.copy(), 'timestamp': time.time()}

    def home(self):
        self.move(np.full(6, 1000, dtype=int))

    def move(self, input_angles, speed=None):
        values = self._validate(input_angles)
        speeds = self.speed if speed is None else self._expand_channels(speed, 'speed')
        if not self.dry_run:
            if self._written_speed is None or not np.array_equal(speeds, self._written_speed):
                self._write_registers(SPEED_SET, speeds)
                self._written_speed = speeds.copy()
            if self._written_force is None or not np.array_equal(self.force, self._written_force):
                self._write_registers(FORCE_SET, self.force)
                self._written_force = self.force.copy()
            self._write_registers(ANGLE_SET, values)
        self._commanded = values.copy()

    def move_coords(self, _):
        raise NotImplementedError('RH56DFTP uses six actuator position channels')

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
