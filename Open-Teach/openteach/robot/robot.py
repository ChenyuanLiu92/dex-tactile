from abc import ABC, abstractmethod
from typing import Any

class RobotWrapper(ABC):
    @property
    @abstractmethod
    def name(self) -> Any:
        pass

    @property
    @abstractmethod
    def recorder_functions(self) -> Any:
        pass

    @property
    @abstractmethod
    def data_frequency(self) -> Any:
        pass

    @abstractmethod
    def get_joint_state(self) -> Any:
        pass

    @abstractmethod
    def get_joint_position(self) -> Any:
        pass

    # @abstractmethod
    def get_cartesian_position(self):
        pass

    # @abstractmethod
    def get_joint_velocity(self):
        pass

    # @abstractmethod
    def get_joint_torque(self):
        pass

    @abstractmethod
    def home(self) -> None:
        pass

    @abstractmethod
    def move(self, input_angles: Any) -> None:
        pass

    @abstractmethod
    def move_coords(self, input_coords: Any) -> None:
        pass

    # @abstractmethod
    # def reset(self):
    #     pass

    # @abstractmethod
    # def arm_control(self):
    #     pass

    # @abstractmethod
    # def set_gripper_state(self):
    #     pass
