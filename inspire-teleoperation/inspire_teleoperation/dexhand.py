"""六自由度灵巧手的 Modbus TCP 通信 API。

提供原始寄存器读写、六自由度速度/位置/角度/力/状态寄存器，以及压阻式
触觉阵列的便捷读取接口；不包含运动学、关节坐标或角度转换。
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import AddressValueError, IPv4Address
import sys
from threading import RLock
import time
from types import TracebackType
from typing import Protocol, Sequence, TextIO

import numpy as np
from numpy.typing import NDArray
from pymodbus.client import ModbusTcpClient


DEFAULT_HOST = "192.168.11.210"
DEFAULT_PORT = 6000
DEFAULT_DEVICE_ID = 1
DEFAULT_TIMEOUT_SECONDS = 3.0
DOF_COUNT = 6
MAX_MODBUS_READ_REGISTERS = 125
MAX_MODBUS_WRITE_REGISTERS = 123
TACTILE_START_ADDRESS = 3000
TACTILE_END_ADDRESS = 5124
IP_ADDRESS_START_ADDRESS = 1700
IP_ADDRESS_BYTE_COUNT = 4

DOF_NAMES = (
    "finger4",
    "finger3",
    "finger2",
    "finger1",
    "finger0_bend",
    "finger0_rotate",
)

JointArray = NDArray[np.signedinteger | np.unsignedinteger]
TactileArray = NDArray[np.uint16]


class ModbusClient(Protocol):
    """本客户端所需的 PyModbus 客户端最小接口。"""

    connected: bool

    def connect(self) -> bool: ...

    def close(self) -> None: ...

    def read_holding_registers(
        self, address: int, *, count: int, device_id: int
    ) -> object: ...

    def write_registers(
        self, address: int, values: list[int], *, device_id: int
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class RegisterSpec:
    """连续六自由度寄存器块的原始范围定义。"""

    address: int
    minimum: int
    maximum: int
    writable: bool = False
    signed: bool = False
    allow_no_change: bool = False


@dataclass(frozen=True, slots=True)
class TactileRegionSpec:
    """一个触觉区域的字节地址、空间形状和设备存储顺序。"""

    address: int
    rows: int
    columns: int
    palm_column_major: bool = False

    @property
    def byte_count(self) -> int:
        """该区域在设备字节地址空间内占用的字节数。"""

        return self.rows * self.columns * 2

    @property
    def register_count(self) -> int:
        """该区域通过 Modbus 读取的 16 位触点/寄存器数量。"""

        return self.rows * self.columns


REGISTER_SPECS: dict[str, RegisterSpec] = {
    "default_speeds": RegisterSpec(1032, 0, 1000, writable=True),
    "default_force_limits": RegisterSpec(1044, 0, 3000, writable=True),
    "target_positions": RegisterSpec(
        1474, 0, 2000, writable=True, allow_no_change=True
    ),
    "target_angles": RegisterSpec(1486, 0, 1000, writable=True, allow_no_change=True),
    "target_force_limits": RegisterSpec(1498, 0, 3000, writable=True),
    "target_speeds": RegisterSpec(1522, 0, 1000, writable=True),
    "actual_positions": RegisterSpec(1534, 0, 2000),
    "actual_angles": RegisterSpec(1546, 0, 1000),
    "actual_forces": RegisterSpec(1582, -4000, 4000, signed=True),
    "currents": RegisterSpec(1594, 0, 2000),
}


TACTILE_REGION_SPECS: dict[str, TactileRegionSpec] = {
    "little_tip": TactileRegionSpec(3000, 3, 3),
    "little_nail": TactileRegionSpec(3018, 12, 8),
    "little_pad": TactileRegionSpec(3210, 10, 8),
    "ring_tip": TactileRegionSpec(3370, 3, 3),
    "ring_nail": TactileRegionSpec(3388, 12, 8),
    "ring_pad": TactileRegionSpec(3580, 10, 8),
    "middle_tip": TactileRegionSpec(3740, 3, 3),
    "middle_nail": TactileRegionSpec(3758, 12, 8),
    "middle_pad": TactileRegionSpec(3950, 10, 8),
    "index_tip": TactileRegionSpec(4110, 3, 3),
    "index_nail": TactileRegionSpec(4128, 12, 8),
    "index_pad": TactileRegionSpec(4320, 10, 8),
    "thumb_tip": TactileRegionSpec(4480, 3, 3),
    "thumb_nail": TactileRegionSpec(4498, 12, 8),
    "thumb_middle": TactileRegionSpec(4690, 3, 3),
    "thumb_pad": TactileRegionSpec(4708, 12, 8),
    "palm": TactileRegionSpec(4900, 8, 14, palm_column_major=True),
}


# 相邻小区域可在一个 FC03 请求内读取；每批不超过 Modbus 的 125 寄存器上限。
TACTILE_READ_BATCHES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (3000, ("little_tip", "little_nail")),
    (3210, ("little_pad",)),
    (3370, ("ring_tip", "ring_nail")),
    (3580, ("ring_pad",)),
    (3740, ("middle_tip", "middle_nail")),
    (3950, ("middle_pad",)),
    (4110, ("index_tip", "index_nail")),
    (4320, ("index_pad",)),
    (4480, ("thumb_tip", "thumb_nail")),
    (4690, ("thumb_middle", "thumb_pad")),
    (4900, ("palm",)),
)


class Dexhand:
    """灵巧手的 Modbus TCP 客户端。

    构造函数不会连接设备。除原始寄存器 API 外，六自由度便捷方法只做寄存器
    地址选择、范围校验与 16 位有符号值/``-1`` 保持不动标记的协议转换；触觉
    方法负责分批读取和二维空间布局转换。
    """

    tactile_batch_count = len(TACTILE_READ_BATCHES)

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        device_id: int = DEFAULT_DEVICE_ID,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        *,
        client: ModbusClient | None = None,
    ) -> None:
        if not host:
            raise ValueError("host 不能为空")
        if not 1 <= port <= 65535:
            raise ValueError("port 必须在 1～65535 范围内")
        if not 1 <= device_id <= 254:
            raise ValueError("device_id 必须在 1～254 范围内")
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")

        self.host = host
        self.port = port
        self.device_id = device_id
        self.timeout = timeout
        self._client: ModbusClient = client or ModbusTcpClient(
            host=host, port=port, timeout=timeout
        )
        self._connected = client is not None
        self._lock = RLock()

    @property
    def is_connected(self) -> bool:
        """当前客户端是否可用于通信。"""

        client_connected = getattr(self._client, "connected", None)
        return self._connected if client_connected is None else self._connected and bool(
            client_connected
        )

    def connect(self) -> None:
        """建立到灵巧手的 Modbus TCP 连接。"""

        with self._lock:
            if self.is_connected:
                return
            if not self._client.connect():
                self._client.close()
                raise ConnectionError(
                    f"无法连接 Modbus TCP 设备：{self.host}:{self.port}"
                )
            self._connected = True

    def close(self) -> None:
        """关闭连接；重复调用安全。"""

        with self._lock:
            self._client.close()
            self._connected = False

    def __enter__(self) -> Dexhand:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def read_registers(self, address: int, count: int) -> NDArray[np.uint16]:
        """读取 1～125 个连续保持寄存器，返回未解释的 ``uint16`` word。"""

        self._validate_address(address)
        if not 1 <= count <= MAX_MODBUS_READ_REGISTERS:
            raise ValueError("count 必须在 1～125 范围内")
        self._require_connected()

        with self._lock:
            response = self._client.read_holding_registers(
                address, count=count, device_id=self.device_id
            )
        self._ensure_success(response, f"读寄存器 {address}")
        registers = getattr(response, "registers", None)
        if not isinstance(registers, Sequence) or isinstance(registers, (str, bytes)):
            raise RuntimeError(f"读寄存器 {address}失败：响应中没有寄存器数据")
        if len(registers) != count:
            raise RuntimeError(
                f"读寄存器 {address}失败：期望 {count} 个寄存器，实际收到 {len(registers)} 个"
            )
        return self._as_word_array(registers, name="响应寄存器").astype(
            np.uint16, copy=False
        )

    def write_registers(self, address: int, values: Sequence[int]) -> None:
        """写入 1～123 个连续保持寄存器，不解释地址或数据含义。"""

        self._validate_address(address)
        if not 1 <= len(values) <= MAX_MODBUS_WRITE_REGISTERS:
            raise ValueError("values 长度必须在 1～123 范围内")
        words = self._as_word_array(values, name="values")
        self._require_connected()

        with self._lock:
            response = self._client.write_registers(
                address, [int(value) for value in words], device_id=self.device_id
            )
        self._ensure_success(response, f"写寄存器 {address}")

    def read_default_speeds(self) -> NDArray[np.uint16]:
        """读取六自由度上电默认速度（0～1000）。"""

        return self._read_joint_block("default_speeds")

    def write_default_speeds(self, values: Sequence[int]) -> None:
        """写入六自由度上电默认速度（每项 0～1000）。"""

        self._write_joint_block("default_speeds", values)

    def read_default_force_limits(self) -> NDArray[np.uint16]:
        """读取六自由度上电默认力阈值。"""

        return self._read_joint_block("default_force_limits")

    def write_default_force_limits(self, values: Sequence[int]) -> None:
        """写入六自由度上电默认力阈值（每项 0～3000）。"""

        self._write_joint_block("default_force_limits", values)

    def read_target_positions(self) -> NDArray[np.int16]:
        """读取六自由度目标位置。"""

        return self._read_joint_block("target_positions")

    def write_target_positions(self, values: Sequence[int]) -> None:
        """写入六自由度目标位置（0～2000；``-1`` 表示保持不动）。"""

        self._write_joint_block("target_positions", values)

    def read_target_angles(self) -> NDArray[np.int16]:
        """读取六自由度目标角度标度值。"""

        return self._read_joint_block("target_angles")

    def write_target_angles(self, values: Sequence[int]) -> None:
        """写入六自由度目标角度标度值（0～1000；``-1`` 表示保持不动）。"""

        self._write_joint_block("target_angles", values)

    def read_target_force_limits(self) -> NDArray[np.uint16]:
        """读取六自由度目标力阈值。"""

        return self._read_joint_block("target_force_limits")

    def write_target_force_limits(self, values: Sequence[int]) -> None:
        """写入六自由度目标力阈值（每项 0～3000）。"""

        self._write_joint_block("target_force_limits", values)

    def read_target_speeds(self) -> NDArray[np.uint16]:
        """读取六自由度目标速度。"""

        return self._read_joint_block("target_speeds")

    def write_target_speeds(self, values: Sequence[int]) -> None:
        """写入六自由度目标速度（每项 0～1000）。"""

        self._write_joint_block("target_speeds", values)

    def read_actual_positions(self) -> NDArray[np.uint16]:
        """读取六自由度实际位置。"""

        return self._read_joint_block("actual_positions")

    def read_actual_angles(self) -> NDArray[np.uint16]:
        """读取六自由度实际角度标度值。"""

        return self._read_joint_block("actual_angles")

    def wait_for_motion_complete(
        self,
        *,
        poll_interval: float = 0.02,
        stable_samples: int = 5,
        timeout: float | None = 30.0,
        output: TextIO | None = None,
    ) -> NDArray[np.uint16]:
        """等待实际角度连续稳定后返回最后一次六自由度读数。"""

        if poll_interval <= 0:
            raise ValueError("poll_interval 必须大于 0")
        if stable_samples < 2:
            raise ValueError("stable_samples 必须至少为 2")
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout 必须大于 0 或为 None")

        stream = sys.stdout if output is None else output
        deadline = None if timeout is None else time.monotonic() + timeout
        previous: NDArray[np.uint16] | None = None
        stable_count = 0
        while True:
            angles = self.read_actual_angles()
            if previous is not None and np.array_equal(angles, previous):
                stable_count += 1
            else:
                stable_count = 1
            if stable_count >= stable_samples:
                return angles
            previous = angles
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("等待动作完成超时，实际角度仍在变化")
            if output is not None:
                print("当前关节角度：" + " ".join(map(str, angles)), file=stream)
            time.sleep(poll_interval)

    def read_actual_forces(self) -> NDArray[np.int16]:
        """读取六自由度实际作用力（有符号 16 位值）。"""

        return self._read_joint_block("actual_forces")

    def read_currents(self) -> NDArray[np.uint16]:
        """读取六自由度电流。"""

        return self._read_joint_block("currents")

    def read_error_codes(self) -> NDArray[np.uint8]:
        """读取六自由度错误码。"""

        return self._read_byte_block(1606, DOF_COUNT)

    def read_status_codes(self) -> NDArray[np.uint8]:
        """读取六自由度状态码。"""

        return self._read_byte_block(1612, DOF_COUNT)

    def read_temperatures(self) -> NDArray[np.uint8]:
        """读取六自由度温度。"""

        return self._read_byte_block(1618, DOF_COUNT)

    def read_ip_address(self) -> str:
        """读取设备配置的 IPv4 地址。"""

        parts = self._read_byte_block(IP_ADDRESS_START_ADDRESS, IP_ADDRESS_BYTE_COUNT)
        return str(IPv4Address(bytes(parts)))

    def write_ip_address(self, address: str, *, save: bool = True) -> None:
        """写入设备 IPv4 地址；保存后仍需重新上电才会生效。

        ``save=True`` 会在写入地址后调用 :meth:`save_parameters` 将参数保存到
        Flash。修改不会重建当前客户端连接，也不会改变 :attr:`host`；设备重新
        上电后，应使用新地址创建新的 :class:`Dexhand` 实例。
        """

        if not isinstance(address, str):
            raise TypeError("address 必须是 IPv4 地址字符串")
        try:
            packed = IPv4Address(address).packed
        except AddressValueError as error:
            raise ValueError(f"无效的 IPv4 地址：{address!r}") from error

        # 设备文档使用连续字节地址；PyModbus word 按设备约定以低位字节在前打包。
        words = [
            packed[0] | (packed[1] << 8),
            packed[2] | (packed[3] << 8),
        ]
        with self._lock:
            self.write_registers(IP_ADDRESS_START_ADDRESS, words)
            if save:
                self.save_parameters()

    def read_tactile_region(self, name: str) -> TactileArray:
        """读取一个具名触觉区域，返回按实际行列排列的二维 ``uint16`` 数组。

        区域名称见 :data:`TACTILE_REGION_SPECS`。手指区域按文档给出的逐行顺序
        排列；掌心数据会从设备的逐列、行倒序存储转换为常规的 ``[row, column]``
        排列。触点的协议定义范围为 0～4095。
        """

        if not isinstance(name, str):
            raise TypeError("name 必须是字符串")
        try:
            spec = TACTILE_REGION_SPECS[name]
        except KeyError as error:
            available = ", ".join(TACTILE_REGION_SPECS)
            raise ValueError(f"未知触觉区域 {name!r}；可用区域：{available}") from error

        # 文档地址按字节递增，但 FC03 count 和 PyModbus 响应均按 16 位 word 计数。
        values = self.read_registers(spec.address, spec.register_count)
        return self._reshape_tactile_region(values, spec)

    def read_tactile(self) -> dict[str, TactileArray]:
        """读取完整压阻式触觉帧，返回 17 个具名二维区域。

        设备的触觉区是 3000～5123 的连续字节地址，共 1062 个 16 位触点。一次
        Modbus 读取不能覆盖完整数据，因此内部会合并相邻区域分批读取。每个批次
        单独持有客户端锁，使控制线程可以在批次之间及时下发指令。
        """

        regions: dict[str, TactileArray] = {}
        for batch_index, (address, names) in enumerate(TACTILE_READ_BATCHES):
            count = sum(
                TACTILE_REGION_SPECS[name].register_count for name in names
            )
            values = self.read_registers(address, count)
            offset = 0
            for name in names:
                spec = TACTILE_REGION_SPECS[name]
                end = offset + spec.register_count
                regions[name] = self._reshape_tactile_region(
                    values[offset:end], spec
                )
                offset = end
            if batch_index + 1 < len(TACTILE_READ_BATCHES):
                time.sleep(0)
        return regions

    def clear_errors(self) -> None:
        """清除设备允许清除的错误。"""

        self.write_registers(1004, [1])

    def save_parameters(self) -> None:
        """将可保存参数写入设备 Flash。"""

        self.write_registers(1005, [1])

    def restore_factory_defaults(self) -> None:
        """请求恢复设备出厂参数。"""

        self.write_registers(1006, [1])

    def calibrate_force_sensors(self) -> None:
        """启动六自由度力传感器校准。"""

        self.write_registers(1009, [1])

    def _read_joint_block(self, name: str) -> JointArray:
        spec = REGISTER_SPECS[name]
        raw = self.read_registers(spec.address, DOF_COUNT)
        if spec.signed:
            return raw.view(np.int16).copy()
        if spec.allow_no_change:
            decoded = raw.astype(np.int32)
            decoded[raw == 0xFFFF] = -1
            return decoded.astype(np.int16)
        return raw

    def _write_joint_block(self, name: str, values: Sequence[int]) -> None:
        spec = REGISTER_SPECS[name]
        if not spec.writable:
            raise ValueError(f"寄存器组 {name} 不可写")
        array = self._as_integer_array(values, name="values")
        if array.size != DOF_COUNT:
            raise ValueError(f"values 必须包含 {DOF_COUNT} 个元素，顺序为 {DOF_NAMES}")
        in_range = (array >= spec.minimum) & (array <= spec.maximum)
        if spec.allow_no_change:
            in_range |= array == -1
        if not np.all(in_range):
            allowed = f"{spec.minimum}～{spec.maximum}"
            if spec.allow_no_change:
                allowed += " 或 -1"
            raise ValueError(f"values 的每个元素必须为 {allowed}")
        self.write_registers(spec.address, [int(value) & 0xFFFF for value in array])

    def _read_byte_block(self, address: int, count: int) -> NDArray[np.uint8]:
        words = self.read_registers(address, (count + 1) // 2)
        result = np.empty(count, dtype=np.uint8)
        result[0::2] = words[: (count + 1) // 2] & 0xFF
        result[1::2] = (words[: count // 2] >> 8) & 0xFF
        return result

    @staticmethod
    def _reshape_tactile_region(
        values: TactileArray, spec: TactileRegionSpec
    ) -> TactileArray:
        if values.size != spec.register_count:
            raise RuntimeError(
                "触觉区域数据长度错误："
                f"期望 {spec.register_count} 个值，实际 {values.size} 个"
            )
        if spec.palm_column_major:
            return values.reshape(spec.columns, spec.rows)[:, ::-1].T.copy()
        return values.reshape(spec.rows, spec.columns).copy()

    def _require_connected(self) -> None:
        if not self.is_connected:
            raise ConnectionError("Modbus TCP 客户端尚未连接，请先调用 connect()")

    @staticmethod
    def _validate_address(address: int) -> None:
        if not isinstance(address, int) or isinstance(address, bool) or address < 0:
            raise ValueError("address 必须是非负整数")

    @staticmethod
    def _as_word_array(values: Sequence[int], *, name: str) -> NDArray[np.int64]:
        array = Dexhand._as_integer_array(values, name=name)
        if np.any((array < 0) | (array > 0xFFFF)):
            raise ValueError(f"{name} 的元素必须在 0～65535 范围内")
        return array

    @staticmethod
    def _as_integer_array(values: Sequence[int], *, name: str) -> NDArray[np.int64]:
        array = np.asarray(values)
        if array.ndim != 1:
            raise ValueError(f"{name} 必须是一维整数序列")
        if not np.issubdtype(array.dtype, np.integer):
            raise TypeError(f"{name} 的元素必须全部为整数")
        return array.astype(np.int64, copy=False)

    @staticmethod
    def _ensure_success(response: object, operation: str) -> None:
        is_error = getattr(response, "isError", None)
        if response is None or not callable(is_error) or is_error():
            raise RuntimeError(f"{operation}失败：{response}")


__all__ = [
    "DEFAULT_DEVICE_ID",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_TIMEOUT_SECONDS",
    "DOF_NAMES",
    "Dexhand",
    "IP_ADDRESS_BYTE_COUNT",
    "IP_ADDRESS_START_ADDRESS",
    "MAX_MODBUS_READ_REGISTERS",
    "MAX_MODBUS_WRITE_REGISTERS",
    "REGISTER_SPECS",
    "TACTILE_END_ADDRESS",
    "TACTILE_READ_BATCHES",
    "TACTILE_REGION_SPECS",
    "TACTILE_START_ADDRESS",
    "TactileArray",
    "TactileRegionSpec",
]
