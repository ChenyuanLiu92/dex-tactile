# Inspire Teleoperation API 文档

本文档描述当前项目的 Python API、模块生命周期、数据约束、Web HTTP API，
以及从纯灵巧手 Teleop 扩展到机械臂 Teleop 的推荐接入方式。

目录：

1. API 分层与稳定性
2. 总体数据流
3. 核心数据模型
4. 扩展协议
5. `TeleopRuntime`
6. `QuestSource`
7. `HandTeleopModule`
8. 高级手部控制 API
9. `Dexhand` Modbus TCP API
10. Web Python 与 HTTP API
11. 机械臂模块接入模板
12. 异常与安全语义
13. 测试替身与依赖注入

## 1. API 分层与稳定性

项目 API 分为三层：

| 层级 | 模块 | 用途 | 建议稳定性 |
|---|---|---|---|
| 公共模块 API | `inspire_teleoperation.api`、`runtime` | 新增输入源、机械臂或其他执行模块 | 推荐外部集成依赖 |
| 设备适配 API | `quest_source`、`hand_module` | 使用或替换 Quest、灵巧手适配器 | 推荐应用层依赖 |
| 高级/底层 API | `hand_controller`、`dexhand` | 自定义控制循环或直接访问 Modbus | 需要理解线程与硬件协议 |

包根目录公开以下名称：

```python
from inspire_teleoperation import (
    HandTracking,
    ModuleStatus,
    RigidTransform,
    TeleopFrame,
    TeleopModule,
    TeleopRuntime,
    TeleopSource,
)
```

`HandTeleopModule`、`QuestSource` 和 `Dexhand` 需要从各自模块导入：

```python
from inspire_teleoperation.hand_module import HandTeleopModule
from inspire_teleoperation.quest_source import QuestSource
from inspire_teleoperation.dexhand import Dexhand
```

## 2. 总体数据流

```text
TeleopSource.read()
        |
        v
   TeleopFrame
        |
        v
 TeleopRuntime.dispatch()
        |
        +----------------------+----------------------+
        v                      v                      v
 HandTeleopModule      ArmTeleopModule       RecorderModule
 独立控制线程/Modbus      IK/限速/机械臂 SDK        记录或回放
```

一个运行时包含一个输入源和零个或多个输出模块。输入源负责生成统一帧；运行时
按注册顺序同步调用各模块的 `update()`；模块自行管理设备连接、独立高频控制线程、
安全限制和遥测。

## 3. 核心数据模型

核心类型位于 `inspire_teleoperation.api`。数据对象使用冻结的 dataclass；NumPy
数组在构造时会复制并设置为只读，避免一个模块意外修改另一个模块看到的数据。

### 3.1 `RigidTransform`

```python
RigidTransform(matrix: NDArray[np.float64])
```

表示一个 4×4 齐次刚体变换。

约束：

- 输入必须可转换为有限的 `float64` 数组；
- 形状必须是 `(4, 4)`；
- 最后一行必须近似为 `[0, 0, 0, 1]`；
- 左上角 3×3 旋转矩阵必须正交且为右手系，行列式近似为 `1`；
- 构造后 `matrix` 是独立、只读的数组副本。

示例：

```python
import numpy as np
from inspire_teleoperation import RigidTransform

pose = np.eye(4)
pose[:3, 3] = [0.35, -0.10, 0.42]
transform = RigidTransform(pose)

translation = transform.matrix[:3, 3]
rotation = transform.matrix[:3, :3]
```

坐标系注意事项：`RigidTransform` 只验证数学形式，不改变坐标系。`QuestSource`
透传 TeleVuer 给出的矩阵。将腕部位姿用于机械臂前，必须确认矩阵的源/目标坐标系、
长度单位、左右手约定，并完成 XR 到机器人基座的外参标定。

### 3.2 `HandTracking`

```python
HandTracking(
    landmarks: NDArray[np.float64],
    wrist: RigidTransform | None = None,
)
```

表示一只手的追踪数据。

| 字段 | 类型 | 说明 |
|---|---|---|
| `landmarks` | `(25, 3)` 只读 `float64` 数组 | Quest/OpenXR 25 个手部关键点 |
| `wrist` | `RigidTransform | None` | 可选腕部位姿 |

`landmarks` 必须为有限数值。关键点坐标系和单位由输入源定义，数据模型不做缩放
或轴变换。

### 3.3 `TeleopFrame`

```python
TeleopFrame(
    sequence: int,
    timestamp: float,
    motion_data_ready: bool,
    left_hand: HandTracking | None = None,
    right_hand: HandTracking | None = None,
    head: RigidTransform | None = None,
    extras: Mapping[str, Any] = {},
)
```

统一的单帧追踪数据。

| 字段 | 约束与含义 |
|---|---|
| `sequence` | 非负整数。输入源每产生一帧应递增 |
| `timestamp` | 有限浮点数；内置输入源使用 `time.monotonic()` |
| `motion_data_ready` | 必须是 `bool`；表示输入源认为本帧运动数据可用 |
| `left_hand` | 左手关键点和腕部位姿；可能缺失 |
| `right_hand` | 右手关键点和腕部位姿；可能缺失 |
| `head` | 可选头部位姿 |
| `extras` | 输入源特有的非关键数据；构造时浅复制为只读映射 |

`motion_data_ready=True` 不保证某个具体模块所需的字段一定存在。模块必须继续检查
例如 `frame.right_hand is not None` 和 `frame.right_hand.wrist is not None`。

创建追踪丢失/无效帧：

```python
lost_frame = TeleopFrame.empty(sequence=123)
```

该方法使用当前单调时钟，设置 `motion_data_ready=False`，其他追踪字段为空。它适合
回放、看门狗或输入校验失败时通知模块进入保持状态。

### 3.4 `ModuleStatus`

```python
ModuleStatus(
    name: str,
    ready: bool,
    detail: str = "",
    telemetry: Mapping[str, Any] = {},
)
```

模块的通用健康状态。

- `name`：与模块的 `name` 属性一致；
- `ready`：模块是否已完成初始化且可工作；
- `detail`：面向日志或 UI 的简短说明；
- `telemetry`：模块自定义的只读约定数据。调用方不应修改其中的共享对象。

## 4. 扩展协议

协议使用 Python `Protocol`，无需显式继承；只要对象实现相同接口即可注册。

### 4.1 `TeleopSource`

```python
class TeleopSource(Protocol):
    def start(self) -> None: ...
    def read(self) -> TeleopFrame: ...
    def close(self) -> None: ...
```

方法契约：

| 方法 | 契约 |
|---|---|
| `start()` | 建立输入连接并准备读取；应允许重复调用而不重复初始化 |
| `read()` | 返回一个 `TeleopFrame`；可以阻塞到数据可用，但应满足应用频率要求 |
| `close()` | 释放资源；应尽量幂等，并能处理未完全启动的状态 |

输入源不应直接控制机器人。数据解码或校验失败时可以抛出 `TypeError`/`ValueError`；
应用也可以选择生成 `TeleopFrame.empty()` 表示短暂追踪丢失。

### 4.2 `TeleopModule`

```python
class TeleopModule(Protocol):
    @property
    def name(self) -> str: ...
    def start(self) -> None: ...
    def update(self, frame: TeleopFrame, *, enabled: bool) -> None: ...
    def status(self) -> ModuleStatus: ...
    def close(self) -> None: ...
```

方法契约：

| 成员 | 契约 |
|---|---|
| `name` | 运行时内唯一、稳定的模块名，如 `"hands"`、`"arms"` |
| `start()` | 连接设备、建立控制线程；失败时抛出异常 |
| `update()` | 接收每一帧以及全局使能状态 |
| `status()` | 返回当前健康状态和遥测，避免长时间阻塞 |
| `close()` | 停止命令、终止线程并关闭连接；应尽量幂等 |

`enabled=False` 时仍会收到帧。模块必须定义安全行为，例如保持当前位置、停止发送新
目标或触发受控停止。不要把 `enabled=False` 等同于硬件急停；急停应由独立、可靠的
硬件或控制链路实现。

## 5. `TeleopRuntime`

```python
TeleopRuntime(source: TeleopSource, modules: Iterable[TeleopModule])
```

构造时会固化模块顺序，并检查模块名唯一性。重复名称抛出 `ValueError`。

### 5.1 方法

#### `start() -> None`

先启动输入源，再按注册顺序启动模块。重复调用安全。如果某个模块启动失败，运行时
按逆序关闭已经开始启动的模块，然后关闭输入源，并重新抛出原始启动异常。

#### `set_enabled(enabled: bool) -> None`

设置后续 `update()` 调用收到的全局使能值。构造后的默认值为 `False`。

#### `step() -> TeleopFrame`

等价于读取一帧再分发：

```python
frame = runtime.source.read()
runtime.dispatch(frame)
```

运行时未启动时抛出 `RuntimeError`。输入源返回非 `TeleopFrame` 对象时抛出
`TypeError`。模块异常不会被运行时吞掉，调用应用应停止或进入安全状态。

#### `dispatch(frame: TeleopFrame) -> TeleopFrame`

绕过输入源，将已有帧按注册顺序发送给所有模块。用于数据回放、测试和显式发送
追踪丢失帧。返回原始 `frame`。

#### `status() -> dict[str, ModuleStatus]`

按模块名返回状态：

```python
statuses = runtime.status()
if not statuses["hands"].ready:
    print(statuses["hands"].detail)
```

#### `module(name: str) -> TeleopModule`

按名称获得模块。不存在时抛出 `KeyError`。需要调用某个模块的扩展方法时可使用该
方法，但业务代码最好持有具体模块变量以保留静态类型。

#### `close() -> None`

按注册顺序的逆序关闭模块，最后关闭输入源。即使一个组件关闭失败，也会继续尝试
关闭其他组件；结束后以第一个异常为 cause 抛出 `RuntimeError`。

### 5.2 基本组合示例

```python
from inspire_teleoperation import TeleopRuntime
from inspire_teleoperation.hand_module import HandTeleopModule
from inspire_teleoperation.quest_source import QuestSource

source = QuestSource()
hands = HandTeleopModule(
    left_host=None,
    right_host="192.168.11.210",
    target_speed=200,
)
runtime = TeleopRuntime(source, [hands])

try:
    runtime.start()
    runtime.set_enabled(True)
    while True:
        runtime.step()
finally:
    runtime.set_enabled(False)
    runtime.close()
```

真实应用需要在循环中加入频率控制、退出条件、异常日志和独立急停。

## 6. `QuestSource`

```python
QuestSource(
    *,
    binocular: bool = False,
    image_shape: tuple[int, int, int] = (480, 640, 3),
    display_mode: str = "pass-through",
    show_hand_markers: bool = True,
    wrapper_factory: Callable[..., Any] | None = None,
)
```

TeleVuer 到 `TeleopFrame` 的适配器。

| 参数 | 说明 |
|---|---|
| `binocular` | 是否按双目图像配置 Quest viewer |
| `image_shape` | TeleVuer 所需的 `(高度, 宽度, 通道)` 占位形状 |
| `display_mode` | `immersive`、`ego` 或 `pass-through` |
| `show_hand_markers` | 是否显示手部关节/骨架标记；旧版限制见下文 |
| `wrapper_factory` | 测试或自定义 TeleVuer 包装器的依赖注入工厂；工厂必须支持签名反射 |

### 6.1 启动和 TeleVuer 版本兼容

`start()` 延迟导入并构造 `televuer.TeleVuerWrapper`，固定请求启用手部追踪并关闭
ZMQ 和 WebRTC 图像流。项目当前锁定 TeleVuer 4.0.0，但适配器也允许注入其他
版本或自定义 wrapper。

TeleVuer 不同版本的构造参数不同。适配器使用 `inspect.signature()` 检查 factory：

- factory 声明 `**kwargs` 时，传递全部内部选项；
- factory 使用显式参数时，只传递其签名中存在的选项；
- 被过滤的可选参数会写入 INFO 日志，而不是导致构造失败；
- 自定义 factory 如果无法被 `inspect.signature()` 反射，`start()` 会传播相应的
  `TypeError` 或 `ValueError`。

完整内部选项为：

```python
{
    "use_hand_tracking": True,
    "binocular": binocular,
    "img_shape": image_shape,
    "display_mode": display_mode,
    "zmq": False,
    "webrtc": False,
    "arm_reference_mode": "head_yaw",
    "show_hand_markers": show_hand_markers,
}
```

其中锁定的 TeleVuer 4.0.0 不声明 `arm_reference_mode` 和 `show_hand_markers`，因此
这两个构造参数会被过滤。适配器会为该旧版安装运行时兼容处理：

- 接受扁平的 400 元素手事件，或可展平为 25×16 矩阵的手事件；
- 分别更新左右手腕矩阵、25 个关键点位置、方向以及 pinch/squeeze 状态；
- 在 `pass-through` 模式中应用 `show_hand_markers`。

旧版 `immersive` 和 `ego` 渲染函数仍由 TeleVuer 自己控制 marker，本兼容层不保证
`show_hand_markers` 在这两种模式生效。运行时兼容会修改进程内 TeleVuer 类方法，
因此同一 Python 进程中的其他 TeleVuer 使用者也会看到兼容实现；当前应用按一个
`QuestSource` 实例设计。

### 6.2 帧映射和 readiness

`read()` 对 TeleVuer 数据做如下映射：

| TeleVuer 属性 | `TeleopFrame` 字段 |
|---|---|
| `motion_data_ready`（如果存在） | `motion_data_ready` |
| `left_hand_pos` | `left_hand.landmarks` |
| `right_hand_pos` | `right_hand.landmarks` |
| `left_wrist_pose` | `left_hand.wrist` |
| `right_wrist_pose` | `right_hand.wrist` |
| `head_pose` | `head` |

readiness 按以下优先级确定：

1. `TeleData.motion_data_ready` 存在且不为 `None` 时，对其取 `bool()`；
2. 旧版没有该字段时，依次检查 `left_hand_pos` 和 `right_hand_pos`；
3. 至少一只手必须是完整、有限且包含绝对值大于 `1e-9` 数据的 `(25, 3)` 数组；
4. 两只手都缺失、格式错误或全零时，readiness 为 `False`。

只有 readiness 为 `True` 时才装配运动字段。缺少某只手时，该手字段为 `None`；
形状、有限值或刚体矩阵校验失败会抛出 `ValueError`。显式 readiness 的行为优先，
因此提供该字段的 wrapper 与此前 API 语义相同。

### 6.3 Legacy readiness 的限制

非零关键点推断只能过滤 TeleVuer 4.0.0 启动时的全零占位数据，不能证明数据是新鲜
的。如果 XR 停止发送事件而共享内存仍保留上一帧，readiness 可能继续为 `True`。
同时，“任意一只手非零”不代表特定启用侧一定有效；消费模块仍须验证自己需要的手。

因此机械臂模块不得仅依赖 legacy readiness 作为安全看门狗。应额外维护事件序号或
本机最后接收时间，并在超时后保持/停止机械臂。`TeleopFrame.timestamp` 表示
`QuestSource.read()` 的本机读取时间，不是底层 XR 事件产生时间。

## 7. `HandTeleopModule`

```python
HandTeleopModule(
    *,
    left_host: str | None,
    right_host: str | None,
    open_on_exit: bool = False,
    controller_factory: Callable[..., Any] | None = None,
    **controller_options: Any,
)
```

将统一帧适配到现有 `HandController`。模块名固定为 `"hands"`。至少配置一个手部
地址，否则构造时抛出 `ValueError`。

常用 `controller_options`：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `port` | `6000` | 双手 Modbus TCP 端口 |
| `left_device_id` | `1` | 左手设备 ID，范围 1～254 |
| `right_device_id` | `1` | 右手设备 ID，范围 1～254 |
| `timeout` | `3.0` | Modbus 请求超时，秒 |
| `target_speed` | `300` | 固定速度及初始化速度，范围 0～1000 |
| `speed_mode` | `adaptive_v2` | `adaptive_v2`、`adaptive_v1`、`adaptive` 或 `fixed` |
| `motion_filter_enabled` | `False` | 是否初始启用关节目标运动微滤波 |
| `fps` | `100.0` | 手部控制线程目标频率 |
| `tactile_frequency` | `10.0` | 完整触觉帧目标频率，范围 1～60 Hz |
| `client_factory` | `Dexhand` | 自定义/模拟底层手客户端工厂 |

`open_on_exit=True` 会在控制线程安全停止后向所有已启用手发送 `[1000] * 6`，然后
关闭连接。它不应替代安全停机流程。

### 7.1 帧接受规则

模块仅在以下条件全部满足时发布新的共享帧序号：

- `enabled=True`；
- `frame.motion_data_ready=True`；
- 每一只已启用的手在帧中都有 `HandTracking`。

条件不满足时不产生新目标，`HandController` 保留最后目标。左右手数据在同一把锁
内复制，防止控制线程读取到跨帧组合。

### 7.2 扩展方法

```python
mode = hands.toggle_speed_mode()
filter_enabled = hands.toggle_motion_filter()
calibrated = hands.calibrate_force_sensors()
```

循环顺序为 `adaptive_v2 -> adaptive_v1 -> fixed -> adaptive_v2`，返回切换后的模式。
`toggle_motion_filter()` 独立切换关节目标运动微滤波并返回新状态，不改变速度模式。
`calibrate_force_sensors()` 向所有已连接手并行下发力传感器校准命令。每只手至少等待
0.5 秒，并以 50 Hz 检查最近 0.5 秒的实际力：六路绝对值均不超过 5 g、各通道窗口
极差均不超过 2 g 时完成；即等待时间取固定 0.5 秒与轮询稳定所需时间的较大者。全部
手通过后返回手部名称元组，3 秒内未稳定则抛出 `TimeoutError` 包装后的
`RuntimeError`。调用前应移除手部外力和接触物。模块未启动时抛出 `RuntimeError`。

### 7.3 状态遥测

`status().telemetry` 包含：

| 键 | 类型 | 说明 |
|---|---|---|
| `left_enabled` / `right_enabled` | `bool` | 对应手是否配置 |
| `motion_data_ready` | `bool` | 最近一帧是否被手模块完整接受 |
| `left_state` / `right_state` | 6 元组 | 实际角度归一化值，约为 0～1 |
| `left_target` / `right_target` | 6 元组 | 当前归一化目标 |
| `speed_mode` | `str` | 当前速度模式 |
| `motion_filter_enabled` | `bool` | 运动微滤波是否启用 |
| `left_speed` / `right_speed` | 6 元组 | 当前设备速度寄存器值 |

## 8. 高级手部控制 API

通常应使用 `HandTeleopModule`。只有需要复用既有共享内存、替换数据发布进程或精确
控制手部线程时，才直接使用 `HandController`。

### 8.1 `HandController`

```python
HandController(
    left_hand_array,
    right_hand_array,
    dual_hand_data_lock=None,
    dual_hand_state_array=None,
    dual_hand_action_array=None,
    *,
    left_host=None,
    right_host=None,
    port=6000,
    left_device_id=1,
    right_device_id=1,
    timeout=3.0,
    target_speed=300,
    speed_mode="adaptive_v2",
    motion_filter_enabled=False,
    fps=100.0,
    tactile_frequency=10.0,
    xr_motion_data_ready_in=None,
    xr_motion_data_sequence_in=None,
    client_factory=None,
)
```

输入手数组必须能保存 75 个浮点值，即展平后的 `(25, 3)` 关键点。构造过程会：

1. 验证频率、速度模式和主机配置；
2. 延迟加载手部重定向/URDF 栈；
3. 为每只启用的手创建、连接 `Dexhand`；
4. 写入初始化目标速度并读取初始实际角度；
5. 启动名为 `hand-modbus-control` 的守护线程。

主要公共成员：

| 成员 | 说明 |
|---|---|
| `speed_mode` | 线程安全读取当前速度模式 |
| `set_speed_mode(mode)` | 请求切换到指定模式 |
| `toggle_speed_mode()` | 循环切换模式并返回新模式 |
| `motion_filter_enabled` | 线程安全读取运动微滤波状态 |
| `set_motion_filter_enabled(enabled)` | 请求启用或停用运动微滤波 |
| `toggle_motion_filter()` | 独立切换运动微滤波并返回新状态 |
| `calibrate_force_sensors()` | 并行校准所有已连接手，并等待至少 0.5 秒且力值稳定 |
| `raise_if_failed()` | 控制线程失败时抛出 `RuntimeError`，原异常为 cause |
| `stop(timeout=None, open_hand=False)` | 停止线程、可选张手、关闭连接 |
| `left_hand_state_array` 等 | 用于 UI/进程间读取状态、目标速度的共享数组 |

如果提供 `xr_motion_data_sequence_in`，控制线程只消费序号变化的新帧；否则可使用
`xr_motion_data_ready_in` 的一次性布尔标志；两者都未提供时，每轮都读取关键点。

仅连接一只手时，控制线程直接执行该手的 Modbus 操作。连接双手时，控制器复用两个
长期 I/O 工作线程，并行执行左右手各自的“写速度、写角度、读实际角度”周期；单手
内部顺序不变，两个周期都完成后才发布组合状态。这样可将双手网络往返时间由近似相加
降为取较慢一侧，但这不是硬件时钟级同步，两台设备的实际执行时刻仍可能有少量偏差。

运动微滤波在重定向和归一化之后、速度规划与 Modbus 下发之前执行一阶指数平滑：新目标
权重为 `0.65`，上一滤波目标权重为 `0.35`。首次启用后的第一帧直接采用当前目标，随后
才开始平滑，因此不会因空滤波状态产生跳变。该开关默认关闭，与速度模式相互独立；用于
削弱手部识别产生的高频小幅抖动，但会引入约一帧以内的轻微响应滞后。

### 8.2 关节顺序和归一化

所有六维手部数组顺序固定为：

```text
finger4, finger3, finger2, finger1, finger0_bend, finger0_rotate
```

控制器内部目标为 0～1，含义是 `0=闭合`、`1=张开`。发送到角度寄存器时乘以
1000 并取整。

### 8.3 `AdaptiveSpeedPlannerV2`

推荐的自适应速度规划器：

```python
planner = AdaptiveSpeedPlannerV2(config=None)
planner.reset(target=None, initial_speed=None, now=None)
speeds = planner.compute(target, actual, now=None)
```

`target` 和 `actual` 都必须是六个有限数值，输入会裁剪到 0～1，输出是六个
0～1000 整数。使用目标运动速率和跟随误差的较大者，并进行死区、跨关节混合和
按时间常数平滑，因此不依赖固定调用频率。时间戳倒退或超过 stale 阈值时会抑制
一次运动率尖峰。

`AdaptiveSpeedConfig` 默认值：

| 字段 | 默认值 | 含义 |
|---|---:|---|
| `min_speed` | 80 | 最小寄存器速度 |
| `max_speed` | 1000 | 最大寄存器速度 |
| `full_error` | 0.25 | 达到满需求的跟随误差 |
| `full_target_rate` | 5.0 | 达到满需求的归一化目标速率 |
| `error_deadband` | 0.005 | 跟随误差死区 |
| `target_rate_deadband` | 0.05 | 目标速率死区 |
| `global_blend` | 0.15 | 单关节需求与全局最大需求混合比例 |
| `smoothing_tau_s` | 0.08 | 速度平滑时间常数 |
| `stale_reset_s` | 0.20 | 判定数据中断的时间 |
| `write_threshold` | 5 | 速度变化达到该值才重写寄存器 |

`AdaptiveSpeedPlanner` / `AdaptiveSpeedPlannerV1` 是兼容保留的 1.0 实现，使用
逐调用平滑而非基于时间的运动率，不建议用于新的不同频率控制链路。

1.0 构造签名为：

```python
AdaptiveSpeedPlanner(
    minimum_speed=80,
    maximum_speed=1000,
    full_scale_error=0.25,
    motion_gain=3.0,
    smoothing=0.35,
    initial_speed=300,
)
```

调用 `calculate(target, actual)` 返回六维整数 NumPy 数组；`reset(initial_speed)`
清除上一目标并重置平滑速度。`AdaptiveSpeedPlannerV1` 是同一类的别名。

### 8.4 `HandRetargeting`

```python
from pathlib import Path
from inspire_teleoperation.hand_retargeting import HandRetargeting

# 签名：HandRetargeting(config_path: Path | None = None)
retargeting = HandRetargeting()
```

该类从 YAML 和本地 URDF 资源建立左右手 `dex-retargeting` 实例。默认配置为
`assets/hand_model/retargeting.yml`。自定义配置必须包含顶层 `left` 和 `right`
段，否则抛出 `ValueError`。

构造后提供以下属性：

| 属性 | 说明 |
|---|---|
| `left_retargeting` / `right_retargeting` | dex-retargeting 运行实例 |
| `left_indices` / `right_indices` | 从 25 点输入构造优化器 reference 所需的索引 |
| `left_dex_retargeting_to_hardware` | 左手 retargeting 输出到硬件六关节顺序的索引 |
| `right_dex_retargeting_to_hardware` | 右手 retargeting 输出到硬件六关节顺序的索引 |

典型计算方式与 `HandController` 一致：

```python
indices = retargeting.right_indices
reference = landmarks[indices[1, :]] - landmarks[indices[0, :]]
radians = retargeting.right_retargeting.retarget(reference)
hardware_radians = radians[
    retargeting.right_dex_retargeting_to_hardware
]
```

该接口依赖具体 URDF 关节名和 dex-retargeting 配置格式，属于高级设备 API。机械臂
模块不应依赖它。

## 9. `Dexhand` Modbus TCP API

`Dexhand` 是同步、带锁的底层六自由度与触觉客户端。构造函数不连接设备。

```python
Dexhand(
    host: str = "192.168.11.210",
    port: int = 6000,
    device_id: int = 1,
    timeout: float = 3.0,
    *,
    client: ModbusClient | None = None,
)
```

验证规则：主机非空、端口 1～65535、设备 ID 1～254、超时大于 0。`client` 用于
注入兼容 PyModbus 最小协议的模拟客户端。

模块提供的协议和常量（其中 `ModbusClient`、`RegisterSpec` 主要用于类型标注和
扩展实现）：

| 名称 | 值/作用 |
|---|---|
| `DEFAULT_HOST` | `192.168.11.210` |
| `DEFAULT_PORT` | `6000` |
| `DEFAULT_DEVICE_ID` | `1` |
| `DEFAULT_TIMEOUT_SECONDS` | `3.0` |
| `DOF_NAMES` | 固定六关节名称和顺序 |
| `MAX_MODBUS_READ_REGISTERS` | `125` |
| `MAX_MODBUS_WRITE_REGISTERS` | `123` |
| `IP_ADDRESS_START_ADDRESS` / `IP_ADDRESS_BYTE_COUNT` | IP 配置字节区，1700 / 4 |
| `REGISTER_SPECS` | 具名连续寄存器块到 `RegisterSpec` 的映射 |
| `ModbusClient` | 可注入客户端所需的结构化协议 |
| `RegisterSpec` | `address/minimum/maximum/writable/signed/allow_no_change` 定义 |
| `TACTILE_START_ADDRESS` / `TACTILE_END_ADDRESS` | 完整触觉区的起始/末尾独占字节地址，3000 / 5124 |
| `TACTILE_REGION_SPECS` | 17 个区域的地址、行列形状和存储顺序 |
| `TACTILE_READ_BATCHES` | 完整帧的 11 个 Modbus 读取批次 |
| `TactileRegionSpec` / `TactileArray` | 触觉区域元数据与二维 `uint16` 数组类型 |

### 9.1 连接和上下文管理

```python
hand = Dexhand(host="192.168.11.210")
hand.connect()
try:
    print(hand.read_actual_angles())
finally:
    hand.close()

# 等价的上下文方式
with Dexhand(host="192.168.11.210") as hand:
    hand.write_target_angles([1000] * 6)
```

- `is_connected`：连接是否可用；
- `connect()`：幂等连接，失败抛出 `ConnectionError`；
- `close()`：关闭客户端，可重复调用。

### 9.2 原始寄存器 API

```python
read_registers(address: int, count: int) -> NDArray[np.uint16]
write_registers(address: int, values: Sequence[int]) -> None
```

- 地址必须是非负整数；
- 单次读取数量为 1～125；
- 单次写入数量为 1～123；
- 原始写入值必须为整数且位于 0～65535；
- 未连接时抛出 `ConnectionError`；
- Modbus 错误响应、缺少数据或长度不符时抛出 `RuntimeError`。

### 9.3 六自由度寄存器块

所有方法使用前述固定六关节顺序。

| 数据 | 起始地址 | 读方法 | 写方法 | 范围/类型 |
|---|---:|---|---|---|
| 上电默认速度 | 1032 | `read_default_speeds` | `write_default_speeds` | `uint16`，0～1000 |
| 上电默认力阈值 | 1044 | `read_default_force_limits` | `write_default_force_limits` | `uint16`，0～3000 |
| 目标位置 | 1474 | `read_target_positions` | `write_target_positions` | `int16`，0～2000 或 `-1` 保持 |
| 目标角度 | 1486 | `read_target_angles` | `write_target_angles` | `int16`，0～1000 或 `-1` 保持 |
| 目标力阈值 | 1498 | `read_target_force_limits` | `write_target_force_limits` | `uint16`，0～3000 |
| 目标速度 | 1522 | `read_target_speeds` | `write_target_speeds` | `uint16`，0～1000 |
| 实际位置 | 1534 | `read_actual_positions` | 无 | `uint16`，定义范围 0～2000 |
| 实际角度 | 1546 | `read_actual_angles` | 无 | `uint16`，定义范围 0～1000 |
| 实际力 | 1582 | `read_actual_forces` | 无 | 有符号 `int16`，定义范围 -4000～4000 |
| 电流 | 1594 | `read_currents` | 无 | `uint16`，定义范围 0～2000 |

每个写方法严格要求六个整数。`-1` 会编码为 `0xFFFF`，只允许用于目标位置和目标
角度。

### 9.4 IP 地址配置

RH56DFTP 使用字节地址 1700～1703 保存 IPv4 的四段。客户端将四个字节按设备的
低位字节在前约定打包为两个 Modbus word，提供以下同步 API：

```python
read_ip_address() -> str
write_ip_address(address: str, *, save: bool = True) -> None
```

示例：

```python
with Dexhand(host="192.168.11.210") as hand:
    print(hand.read_ip_address())               # 192.168.11.210
    hand.write_ip_address("192.168.11.211")    # 默认同时保存到 Flash
```

`address` 必须是合法的 IPv4 字符串。`save=True` 时，写入 IP 后会调用
`save_parameters()`；传入 `save=False` 可暂不保存。按照设备手册，新 IP 需要重新
上电才会生效。写入方法不会修改当前实例的 `host` 或重建连接；设备重新上电后，
应使用新 IP 创建新的 `Dexhand` 实例。修改前应确保控制机与新地址仍处于可达网络，
并记录原地址，以免设备重新上电后失联。

### 9.5 触觉读取

RH56DFTP 压阻式触觉阵列通过以下两个同步 API 读取：

```python
read_tactile_region(name: str) -> NDArray[np.uint16]
read_tactile() -> dict[str, NDArray[np.uint16]]
```

`read_tactile_region()` 只读取指定区域；`read_tactile()` 读取地址 3000～5123 的
完整触觉帧并返回全部 17 个区域。每个返回数组都是二维的，使用 `[row, column]`
索引，触点协议值范围为 0～4095。手指数据按文档的逐行顺序排列；掌心在设备中的
逐列、行倒序数据会自动转换为正常的空间行列顺序。完整帧分为 11 个 Modbus 请求，
每批单独持有客户端锁，因此并行控制线程可在批次之间继续下发目标或读取状态。

```python
with Dexhand(host="192.168.11.210") as hand:
    index_pad = hand.read_tactile_region("index_pad")  # shape: (10, 8)
    tactile = hand.read_tactile()
    palm = tactile["palm"]                              # shape: (8, 14)
```

可用区域名和形状：

| 区域名 | 形状 | 区域名 | 形状 |
|---|---:|---|---:|
| `little_tip` | 3×3 | `little_nail` | 12×8 |
| `little_pad` | 10×8 | `ring_tip` | 3×3 |
| `ring_nail` | 12×8 | `ring_pad` | 10×8 |
| `middle_tip` | 3×3 | `middle_nail` | 12×8 |
| `middle_pad` | 10×8 | `index_tip` | 3×3 |
| `index_nail` | 12×8 | `index_pad` | 10×8 |
| `thumb_tip` | 3×3 | `thumb_nail` | 12×8 |
| `thumb_middle` | 3×3 | `thumb_pad` | 12×8 |
| `palm` | 8×14 | | |

文档中的触觉地址是字节偏移，而 Modbus FC03 的 `count` 是 16 位寄存器数量；每个
PyModbus 返回 word 对应一个触点，不应只取低 8 位。客户端把相邻的小区域合并成
11 个读取批次，每批不超过 Modbus 的 125 寄存器上限；完整帧的所有批次由同一个
`Dexhand` 锁串行化。区域元数据和批次可分别通过 `TACTILE_REGION_SPECS`、
`TACTILE_READ_BATCHES` 查询。这里的“完整帧”是 11 次连续读取组成的逻辑帧；文档
未定义硬件锁存机制，因此不同批次的采样时刻可能略有差异。

### 9.6 状态和维护命令

```python
read_error_codes() -> NDArray[np.uint8]
read_status_codes() -> NDArray[np.uint8]
read_temperatures() -> NDArray[np.uint8]
clear_errors() -> None
save_parameters() -> None
restore_factory_defaults() -> None
calibrate_force_sensors() -> None
```

状态/温度块起始地址分别为 1606、1612、1618；六个字节按每个 16 位寄存器低字节
在前的方式解包。维护命令写入地址分别为：清错 1004、保存参数 1005、恢复出厂
1006、力传感器校准 1009，写入值均为 `1`。

维护命令会直接写设备寄存器，尤其恢复出厂参数、保存 Flash 和力传感器校准可能
改变持久状态或设备行为，只应在设备文档规定的安全条件下调用。

### 9.7 等待动作稳定

```python
wait_for_motion_complete(
    *,
    poll_interval: float = 0.02,
    stable_samples: int = 5,
    timeout: float | None = 30.0,
    output: TextIO | None = None,
) -> NDArray[np.uint16]
```

当实际角度连续 `stable_samples` 次完全相同时返回最后读数。`timeout=None` 表示无限
等待；超时抛出 `TimeoutError`。传入 `output` 时会打印尚未稳定的当前读数。

注意：相邻采样完全相等只代表寄存器读数稳定，不等价于达到某个目标，也不构成
功能安全判定。

### 9.8 线程安全

同一个 `Dexhand` 实例的连接和每次 Modbus 调用由 `RLock` 串行化。多个实例之间
没有共享锁。不要让两个客户端同时控制同一个设备，除非设备协议明确支持。

## 10. Web Python 与 HTTP API

Web 控制台默认监听 `127.0.0.1:8080`。除静态资源外提供以下 JSON API。当前未
实现认证和 TLS；将监听地址改为 `0.0.0.0` 前，应通过防火墙、反向代理或可信网络
限制访问。

### 10.1 Python API

```python
from inspire_teleoperation.web_ui import (
    HandTeleoperationWebUI,
    TeleopSnapshot,
)
```

`TeleopSnapshot` 是传给 Web UI 的冻结数据对象，构造参数为：

```python
TeleopSnapshot(
    tracking_enabled: bool,
    motion_data_ready: bool,
    loop_hz: float,
    elapsed_seconds: float,
    left_enabled: bool,
    right_enabled: bool,
    left_state: tuple[float, ...],
    right_state: tuple[float, ...],
    left_target: tuple[float, ...],
    right_target: tuple[float, ...],
    speed_mode: str = "adaptive_v2",
    motion_filter_enabled: bool = False,
    left_speed: tuple[float, ...] = (),
    right_speed: tuple[float, ...] = (),
    modules: dict[str, dict[str, Any]] = {},
    tactile: dict[str, Any] = {},
)
```

`HandTeleoperationWebUI(args)` 从 argparse 风格的 `args` 对象读取 Web 地址、语言和
手部初始配置。主要方法：

| 方法/属性 | 说明 |
|---|---|
| `url` | 当前 Web 地址；监听全地址时返回可本机访问的 `127.0.0.1` 地址 |
| `start(open_browser=True)` | 启动后台 HTTP 线程，可选打开浏览器 |
| `stop()` | 关闭服务器、移除日志 handler 并等待线程结束 |
| `validate_setup(payload)` | 校验并归一化 setup 字典，不修改 UI 状态 |
| `submit_setup(payload)` | 在 `setup` 阶段提交配置并切换到 `connecting` |
| `wait_for_setup()` | 阻塞等待 setup；先收到 quit 时返回 `None` |
| `submit_action(action)` | 校验动作并放入线程安全队列 |
| `poll_action()` | 非阻塞取出最早动作；队列为空返回 `None` |
| `set_calibration_state(state, detail="")` | 发布力校准的排队、运行或终态 |
| `acknowledge_calibration()` | 用户确认终态后将校准状态恢复为 `idle` |
| `submit_tactile_selection(sides)` | 选择要低频采集触觉数据的已接入手部 |
| `poll_tactile_selection()` | 非阻塞取出最新触觉采集选择；无变更返回 `None` |
| `submit_tactile_capture(payload)` | 开始或停止后台 JSONL 触觉文件采集 |
| `set_phase(phase, detail="")` | 更新阶段和说明 |
| `return_to_setup(detail="")` | 清理当前快照和 setup 提交，保留配置并返回接入界面 |
| `publish(snapshot)` | 原子替换当前 Web 快照 |
| `add_message(level, message)` | 追加规范化、相邻去重的日志消息 |
| `state_payload()` | 返回可 JSON 序列化的当前完整状态 |

Web UI 使用 `threading.Condition` 保护 setup、动作、状态和消息。`asset()` 只读取
内置白名单静态资源，不把任意 URL 路径映射到文件系统。

### 10.2 `GET /api/state`

返回：

```json
{
  "phase": "live",
  "detail": "",
  "language": "auto",
  "config": {},
  "snapshot": {
    "tracking_enabled": true,
    "motion_data_ready": true,
    "loop_hz": 60.0,
    "elapsed_seconds": 12.5,
    "left_enabled": false,
    "right_enabled": true,
    "left_state": [0, 0, 0, 0, 0, 0],
    "right_state": [0.8, 0.8, 0.8, 0.8, 0.7, 0.5],
    "left_target": [0, 0, 0, 0, 0, 0],
    "right_target": [0.8, 0.8, 0.8, 0.8, 0.7, 0.5],
    "speed_mode": "adaptive_v2",
    "motion_filter_enabled": true,
    "left_speed": [0, 0, 0, 0, 0, 0],
    "right_speed": [200, 200, 200, 200, 180, 160],
    "modules": {
      "hands": {"ready": true, "detail": ""}
    },
    "tactile": {
      "sample_hz": 9.8,
      "target_hz": 10.0,
      "selection": ["right"],
      "hands": {
        "right": {
          "revision": 4,
          "age_seconds": 0.18,
          "forces": [0, 1, -1, 0, 3, 0],
          "force_age_seconds": 0.04,
          "force_error": "",
          "error": "",
          "regions": {
            "little_tip": [[0, 14, 28], [0, 18, 31], [0, 9, 22]]
          }
        }
      }
    }
  },
  "tactile_selection": ["right"],
  "tactile_capture": {
    "state": "recording",
    "format": "inspire-tactile-jsonl",
    "format_version": 1,
    "path": "/workspace/tactile_captures/tactile-20260722-120000-000000.jsonl",
    "sides": ["right"],
    "frequency_hz": 10.0,
    "duration_seconds": 30.0,
    "elapsed_seconds": 8.2,
    "remaining_seconds": 21.8,
    "sample_count": 82,
    "dropped_count": 0,
    "error": ""
  },
  "calibration": {
    "state": "running",
    "detail": ""
  },
  "messages": []
}
```

`phase` 当前使用 `setup`、`connecting`、`live`、`disconnecting`、`error`、
`stopping`、`stopped`。
`snapshot` 在首次发布前为 `null`。触觉页未打开时 `tactile.selection` 和
`tactile_selection` 为空，控制器不会额外读取触觉寄存器。`regions` 中每个区域为
二维整数矩阵，数值范围为 0～4095；`revision` 只在该手完成一帧读取后递增。
`forces` 是按小指、无名指、中指、食指、拇指、旋转顺序排列的六路有符号原始实际力，
触觉页打开时以最高约 10 Hz 读取；`force_age_seconds` 表示最近一次成功力读取的年龄，
`force_error` 单独报告力读取错误，不会丢弃已经成功取得的触觉帧。
`target_hz` 是当前配置的目标帧率，`sample_hz` 是实际完成帧率的平滑测量值。
`tactile_capture.state` 使用 `idle`、`recording`、`stopping`、`completed`、
`stopped` 或 `error`。`calibration.state` 使用 `idle`、`queued`、`running`、
`completed` 或 `failed`；终态会一直保留到用户确认。`messages` 最多保留 300 条
去重后的日志。

### 10.3 `POST /api/setup`

请求头必须为 `Content-Type: application/json`，请求体大小 1～32768 字节。

完整请求字段：

```json
{
  "left_enabled": false,
  "left_host": "192.168.11.211",
  "left_device_id": 1,
  "right_enabled": true,
  "right_host": "192.168.11.210",
  "right_device_id": 1,
  "modbus_port": 6000,
  "modbus_timeout": 3.0,
  "target_speed": 200,
  "speed_mode": "adaptive_v2",
  "frequency": 60.0,
  "hand_frequency": 100.0,
  "tactile_frequency": 10.0,
  "start": false,
  "open_on_exit": false,
  "hide_hand_markers": false,
  "safety_confirmed": true
}
```

约束：至少启用一只手；启用手的主机不能为空或包含空白；同时启用左右手时，两者
不能使用相同主机地址（比较时忽略主机名大小写）；端口 1～65535；设备 ID 1～254；
超时和 Quest/手部频率为正数；`tactile_frequency` 范围为 1～60 Hz；目标速度
0～1000；`speed_mode` 支持
`adaptive_v2`、`adaptive_v1`、`adaptive` 和 `fixed`，其中 `adaptive` 会归一化为
`adaptive_v2`；必须显式确认 `safety_confirmed=true`。

成功返回 HTTP 202：

```json
{"ok": true, "config": {}}
```

设置只允许在 `setup` 阶段提交。设备断开后服务会重新进入 `setup`，保留上次配置，
可修改后再次提交，无需重启 Python 进程。验证失败返回 HTTP 400 和 `error` 字符串。
浏览器还会把设备启用状态、地址、设备 ID、通信/触觉频率、速度策略及会话选项保存到
本机 `localStorage`，刷新页面或重启服务后会优先恢复。安全确认不会缓存，每次连接前
仍需人工重新勾选。触觉文件采集的频率、时间和输出路径也会单独保存在本机浏览器中。

### 10.4 `POST /api/action`

```json
{"action": "run"}
```

允许的动作：

| 动作 | 含义 |
|---|---|
| `run` | 将全局 Teleop 使能设为真 |
| `pause` | 停止跟踪并停止发布新手部目标，保留最后目标 |
| `speed_mode` | 循环切换手部速度模式 |
| `motion_filter` | 独立切换关节目标运动微滤波 |
| `calibrate_force` | 停止跟踪并校准所有已连接手的力传感器 |
| `disconnect` | 关闭当前设备与 Quest 会话，返回 `setup`，Web 服务保持运行 |
| `quit` | 关闭当前设备会话和 Web 服务，退出程序 |

成功返回 HTTP 202：

```json
{"ok": true, "action": "pause"}
```

在 `setup` 阶段仅允许 `quit`。`motion_filter` 与 `calibrate_force` 仅在 `live`
阶段可用；力校准执行前应确保
所有手部不受外力，控制台会弹出确认提示并自动停止跟踪。后台会等待至少 0.5 秒且
力值轮询稳定后记录完成；3 秒未稳定则记录校准失败。未知动作返回 HTTP 400。

校准弹窗贯穿安全确认、校准中和最终结果三个阶段。校准期间不能取消；达到
`completed` 或 `failed` 后仍保持打开，用户点击“确定”时浏览器调用：

```http
POST /api/calibration/ack
Content-Type: application/json

{}
```

成功后校准状态恢复为 `idle`，弹窗关闭。校准仍为 `queued` 或 `running` 时确认请求
返回 HTTP 400。

### 10.5 `POST /api/tactile`

在已连接会话中选择触觉页要采集的手部：

```json
{"sides": ["left", "right"]}
```

成功返回 HTTP 202：

```json
{"ok": true, "sides": ["left", "right"]}
```

只配置一只手时只能提交该手或空数组；配置双手时可提交左手、右手或双手。空数组会
停止触觉采样，Web 控制台在离开触觉页时自动提交。完整触觉帧目标频率由连接配置的
`tactile_frequency` 决定，范围为 1～60 Hz；每帧包含 11 个触觉读取批次，并以最高
约 10 Hz 附带一次六路实际力读取。各批次独立
加锁，让控制指令有机会穿插执行。若设备响应较慢，实际帧率会自然低于目标值，不会
积压过期读取任务。选择双手时，控制器会为左右手分别使用长期工作线程和各自的
Modbus 客户端并行读取；单手内部的 11 个批次仍按协议顺序读取。两只手的完成时间戳
与修订号相互独立，因此这是低延迟并发采集，不是硬件时钟同步采样。断开设备后可在
Web 中修改该值并重新连接，无需重启服务。
选择未接入的手、重复项或在非 `live` 阶段调用会返回 HTTP 400。

### 10.6 `POST /api/tactile/capture`

开始把当前所选手部的触觉数据流式写入 JSON Lines 文件：

```json
{
  "action": "start",
  "sides": ["left", "right"],
  "frequency_hz": 10.0,
  "duration_seconds": 30.0,
  "output_path": "tactile_captures"
}
```

`frequency_hz` 必须为正数且不超过 60 Hz，同时不能高于当前触觉轮询率和 Web
快照发布率中的较小值，避免把重复帧当作更高频数据写出。`duration_seconds` 必须
大于 0 且不超过 86400 秒。`output_path` 可指向目录或以 `.jsonl` 结尾的文件；目录会自动
创建，并在其中生成带时间戳且不覆盖已有文件的文件名。相对路径以启动控制服务时的
工作目录为基准。采集期间不能切换所选手部；离开触觉页不会中断正在运行的采集。

手动停止：

```json
{"action": "stop"}
```

两种操作均返回 HTTP 202，并在 `capture` 字段返回与 `/api/state` 相同的采集状态。
设备断开或控制服务停止时，进行中的采集会停止并关闭文件。

JSONL 第一行是元数据，中间每行是一帧，正常结束或手动停止时最后一行是摘要：

```json
{"type":"metadata","format":"inspire-tactile-jsonl","version":1,"started_at":"2026-07-22T12:00:00.000+08:00","frequency_hz":10.0,"duration_seconds":30.0,"sides":["right"],"value_range":[0,4095]}
{"type":"sample","sequence":0,"captured_at":"2026-07-22T12:00:00.101+08:00","elapsed_seconds":0.101,"hands":{"right":{"revision":12,"regions":{"palm":[[0,12,24]]},"forces":[0,1,-1,0,3,0],"force_age_seconds":0.04}}}
{"type":"summary","ended_at":"2026-07-22T12:00:30.001+08:00","state":"completed","sample_count":300,"dropped_count":0,"stop_reason":""}
```

逐行格式无需在内存中保留完整采集结果，程序异常中断时也能保留此前已经写出的完整
行；使用 Python 时可对文件逐行调用 `json.loads()`。`forces` 和
`force_age_seconds` 是可选字段：设备尚未返回有效力数据时省略，旧版读取程序可以继续
只处理 `revision` 与 `regions`。

## 11. 机械臂模块接入模板

以下模板展示 API 边界，不代表完整的安全机械臂控制器。具体实现应把标定、逆运动学、
关节/笛卡尔限位、速度和加速度限制、碰撞检测、看门狗及急停接入模块内部。

```python
from __future__ import annotations

import time
from typing import Any

import numpy as np

from inspire_teleoperation import ModuleStatus, TeleopFrame


class ArmTeleopModule:
    name = "arms"

    def __init__(
        self,
        controller: Any,
        robot_from_xr: np.ndarray,
        *,
        stale_timeout_s: float = 0.15,
    ) -> None:
        self.controller = controller
        self.robot_from_xr = np.asarray(robot_from_xr, dtype=np.float64)
        self.stale_timeout_s = stale_timeout_s
        self._ready = False
        self._detail = "not started"
        self._last_valid_frame_at: float | None = None

    def start(self) -> None:
        self.controller.connect()
        self.controller.enter_position_control()
        self._ready = True
        self._detail = ""

    def update(self, frame: TeleopFrame, *, enabled: bool) -> None:
        now = time.monotonic()
        hand = frame.right_hand
        pose_available = hand is not None and hand.wrist is not None

        if not enabled or not frame.motion_data_ready or not pose_available:
            self.controller.hold_position()
            self._detail = "disabled or tracking unavailable"
            return

        if now - frame.timestamp > self.stale_timeout_s:
            self.controller.hold_position()
            self._detail = "stale tracking frame"
            return

        xr_wrist = hand.wrist.matrix
        robot_wrist = self.robot_from_xr @ xr_wrist

        # 必须在这些步骤中执行工作空间裁剪、姿态限制、速度/加速度限制、
        # IK 可解性检查和碰撞检查，再允许发送到真实控制器。
        safe_target = self.validate_and_limit(robot_wrist)
        self.controller.command_cartesian_pose(safe_target)
        self._last_valid_frame_at = now
        self._detail = ""

    def validate_and_limit(self, target: np.ndarray) -> np.ndarray:
        # 项目集成时替换为机器人相关的完整安全限制。
        if not np.isfinite(target).all():
            raise ValueError("arm target contains non-finite values")
        return target

    def status(self) -> ModuleStatus:
        return ModuleStatus(
            name=self.name,
            ready=self._ready,
            detail=self._detail,
            telemetry={"last_valid_frame_at": self._last_valid_frame_at},
        )

    def close(self) -> None:
        try:
            if self._ready:
                self.controller.hold_position()
                self.controller.leave_position_control()
        finally:
            self.controller.close()
            self._ready = False
            self._detail = "closed"
```

上述陈旧帧判断要求输入源和机械臂模块位于同一 `time.monotonic()` 时钟域。网络输入
或离线回放应先转换时间基准，或另行记录本机接收时间，不能直接比较远端单调时钟。

注册方式：

```python
source = QuestSource()
hands = HandTeleopModule(
    left_host=None,
    right_host="192.168.11.210",
)
arms = ArmTeleopModule(arm_controller, robot_from_xr=calibration_matrix)

runtime = TeleopRuntime(source, [hands, arms])
```

推荐让机械臂模块拥有独立的固定频率控制线程：`update()` 只原子地发布最新安全目标，
控制线程按机器人要求的频率读取目标并执行。这样 Quest 采样频率、Web 主循环频率和
机械臂伺服频率互不绑定。线程间目标应包含时间戳和序号，以便看门狗检测陈旧数据。

## 12. 异常与安全语义

| 异常 | 常见来源 | 建议处理 |
|---|---|---|
| `TypeError` | 非数值数组、错误布尔类型、错误帧类型 | 丢弃该帧并记录输入问题 |
| `ValueError` | 形状、范围、矩阵或配置不合法 | 配置阶段阻止启动；运行期丢弃帧 |
| `ConnectionError` | Modbus/机器人连接失败或尚未连接 | 禁止使能，关闭已启动模块 |
| `TimeoutError` | 等待手部动作稳定超时 | 进入保持/故障状态，不继续盲目下发 |
| `RuntimeError` | 设备错误响应、异步控制线程失败、关闭失败 | 停止运行时并保留原异常链 |

建议应用遵循以下顺序：

1. 默认 `enabled=False` 启动所有设备；
2. 验证连接、标定、状态和工作空间后再允许使能；
3. 短暂追踪丢失时向模块发送 `TeleopFrame.empty()`；
4. 模块内部用看门狗处理主循环卡死或不再收到帧的情况；
5. 任一输出模块发生未预期异常时，停止整个组合并执行逆序关闭；
6. 使用独立硬件急停，不依赖 Python、Web UI 或网络作为唯一安全手段。

## 13. 测试替身与依赖注入

无需连接硬件即可测试模块组合：

- `QuestSource(wrapper_factory=...)` 注入模拟 TeleVuer 包装器；
- `HandTeleopModule(controller_factory=...)` 注入模拟手控制器；
- `HandController(client_factory=...)` 注入模拟 `Dexhand`；
- `Dexhand(client=...)` 注入最小 `ModbusClient` 协议实现；
- 使用 `runtime.dispatch(frame)` 回放确定性的输入帧。

最小模拟模块：

```python
class RecordingModule:
    name = "recorder"

    def __init__(self):
        self.frames = []

    def start(self):
        pass

    def update(self, frame, *, enabled):
        self.frames.append((frame, enabled))

    def status(self):
        return ModuleStatus(self.name, ready=True)

    def close(self):
        pass
```

这类测试应覆盖启动失败回滚、暂停、追踪丢失、陈旧帧、异常关闭、坐标标定、限位和
看门狗，而不仅是正常运动路径。
