# Dex Tactile

Dex Tactile 是面向 Inspire Robots RH56DFTP 六驱动通道压阻式触觉灵巧手的科研工作台。
项目将 D435 RGB 手部追踪、URDF 约束重定向、Quest/Open-Teach 遥操作、受保护的
Modbus TCP 控制、二维触觉热力图/三维山峰图和 HDF5 手部数据采集整合在同一仓库中。

当前版本以 **右手 RH56DFTP、macOS、单台 D435、单手遥操作** 为主要验证环境。
设备工作台可以配置并显示左右手，但 D435 和 Quest 的真机控制链路目前只向右手六通道输出。

> [!CAUTION]
> 灵巧手可能夹伤手指或损坏机构。首次运行、修改映射或提高速度时必须保持控制器
> `DISARMED`，先完成 dry-run，并确保操作者能立即物理断电。界面中的 E-STOP 是软件
> 位置保持，不等同于认证急停、驱动断能或机械限位。

## 功能状态

| 模块 | 输入 | 输出 | 真机写入 |
| --- | --- | --- | --- |
| Unified Web | D435、Modbus、触觉 | RGB/关键点、URDF、关节、二维/三维触觉 | 仅显式 ARM 后 |
| D435 retargeting | 单目 RGB、MediaPipe 21 点 | 12 个 URDF 关节、6 个驱动目标 | 可 dry-run/ARM |
| Open-Teach | Quest 3 手部关键点 | 同一套 RH56 重定向与 6 通道目标 | 默认 dry-run |
| Pose scripts | 当前电机位置 | `home` 或 `open` 预设 | 是 |
| Data collection | Tracking、真机角度、1062 taxel | 单 episode HDF5 | 否 |

六个驱动通道顺序固定为：

```text
little_flexion, ring_flexion, middle_flexion, index_flexion,
thumb_flexion, thumb_opposition
```

## 仓库结构

| 目录 | 内容 |
| --- | --- |
| `unified_web/` | 将设备/触觉和视觉控制后端挂载到同一 FastAPI 服务 |
| `inspire_visualizer/` | Modbus 设备管理、数字孪生、触觉采样和 React 工作台 |
| `dex-retargeting/` | RH56 URDF、D435 tracking、SomeHand/DexPilot 风格约束和安全控制器 |
| `Open-Teach/` | Quest 关键点接收和 RH56DFTP 遥操作适配 |
| `hand_data_collection/` | 只读、多速率、可恢复的 HDF5 episode 采集器 |
| `inspire_doc/` | 厂家手册、CAD、URDF 和官方通信示例 |
| `scripts/` | 团队稳定入口；优先使用这里的脚本 |
| `docs/` | 设计记录和阶段性技术文档 |

上游项目、基准 commit 和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。Open-Teach 的两个
完整 Unity 工程体积约 1.4 GB，不进入主仓库；已构建 APK 保留在 `Open-Teach/VR/APK/`。
需要修改 APK 时，从 THIRD_PARTY 中记录的上游 commit 获取 Unity 工程。

## 硬件

### 必需

- Inspire Robots RH56DFTP 灵巧手及厂家电源、以太网连接线
- 能够接入灵巧手设备网段的 macOS 或 Linux 工作站
- 可随时触达的物理断电装置

### 视觉遥操作

- Intel RealSense D435，使用 USB 3.x 连接
- 本项目当前只读取 1280x720、30 FPS RGB，不依赖深度流
- 相机应正对手掌活动区域，避免背光、运动模糊和手指出画

### Quest 遥操作（可选）

- Meta Quest 3，已启用 Developer Mode 和 Hand Tracking
- 数据线，用于首次 ADB 安装 APK
- Quest 与工作站之间可互访的局域网/Wi-Fi

工作站可以同时使用有线网连接 RH56、使用 Wi-Fi 连接 Quest。不要把两个接口配置成
冲突网段，也不要让工作站地址与灵巧手地址重复。

## 软件环境

推荐版本：

- Python `3.11`（由 `.python-version` 固定）
- [uv](https://docs.astral.sh/uv/) `0.5+`
- Node.js `20 LTS` 或更新版本及 npm
- Git；安装 Quest APK 时还需要 Android Platform Tools (`adb`)

macOS 安装示例：

```bash
brew install uv node android-platform-tools librealsense jpeg-turbo
```

Linux 请使用 uv 官方安装方式和发行版对应的 Node.js/ADB 包。首次克隆后在仓库根目录执行：

```bash
uv sync --all-groups

npm ci --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web
```

`uv run` 会自动使用根目录 `.venv`，不要再手动 `pip install`。统一前端依赖由
`inspire_visualizer/web/package-lock.json` 管理，不要提交 `node_modules/` 或 `dist/`。

### 可选：将缓存放到外置 SSD

以下目录只影响本机，不应写入仓库：

```bash
export UV_CACHE_DIR=/path/to/ssd/cache/uv
export UV_PYTHON_INSTALL_DIR=/path/to/ssd/tools/uv/python
```

Conda 不是本项目的 Python 包管理器。若其他项目仍需 Conda，可在 `~/.condarc` 中单独设置
`pkgs_dirs` 和 `envs_dirs`。

## 本地配置与隐私

仓库只提交 RFC 5737 文档示例地址（`192.0.2.0/24`），这些地址不会连接真实设备。
真实 IP、标定结果、数据集和日志都必须留在本机。

```bash
cp .env.example .env
cp inspire_visualizer/config/hands.example.json \
  inspire_visualizer/config/hands.json
```

编辑 `.env`：

```dotenv
RH56_HOST=YOUR_HAND_IP
RH56_PORT=6000
OPENTEACH_HOST=YOUR_WORKSTATION_IP_VISIBLE_TO_QUEST
D435_CAMERA_SOURCE=avfoundation
D435_CAMERA_INDEX=0
```

然后编辑 `inspire_visualizer/config/hands.json`：

- 将实际连接的手设置为 `enabled: true`，另一只设置为 `false`。
- `host` 填对应设备 IP；左右手必须使用不同端点。
- RH56DFTP 压阻触觉使用 `piezoresistive_v1`。
- 无触觉或不采触觉时使用 `disabled`。

根目录脚本会自动加载 `.env`。以下文件已被 `.gitignore` 排除：

```text
.env
inspire_visualizer/config/hands.json
inspire_visualizer/config/tactile_calibration.json
dex-retargeting/viewer/config/retargeting-calibration.json
dex-retargeting/viewer/config/operator-profiles.json
datasets/
*.partial.h5
*.log
```

不要在 issue、PR、截图或 HDF5 的 `--task`/`--operator` 中写入真实姓名、账号、实验室 IP、
Wi-Fi 信息或受试者身份。`--operator` 默认保存为 `anonymous`，需要区分操作者时使用团队内
约定的匿名编号。

`inspire_doc/` 是原样保留的厂家参考资料，其中出现的私网地址属于厂家通信示例，不代表
本实验室配置。不要把本地地址回写到这些参考文件；厂家 ROS 示例中已有的 `build/`、
`install/` 和 `log/` 生成目录不会进入版本控制。

## 网络检查

1. 按厂家手册为 RH56 网口配置同网段的工作站静态地址。
2. 确认不会与设备地址冲突。
3. 先测试连通性，再启动控制程序：

```bash
ping YOUR_HAND_IP
nc -vz YOUR_HAND_IP 6000
```

Quest 方案至少需要工作站监听 `8087` 接收关键点；Open-Teach 还使用
`8088-8093`、`8095`、`8100-8102`、`8110-8121`、`10005`、`10010`、`15001`
等配置端口。若主机启用了防火墙，应只对可信局域网开放 `Open-Teach/configs/network.yaml`
中实际启用的端口。

## 启动统一工作台

确保两个前端已经 build，然后运行：

```bash
./scripts/run_web.sh
```

macOS 默认通过 AVFoundation 打开 D435 的 RGB UVC 端点，不需要 `sudo`，也不依赖
`librealsense` 的原始 USB 访问。启动前可在系统设置的“隐私与安全性 → 摄像头”中允许当前
终端访问摄像头。`D435_CAMERA_INDEX=0` 表示当前枚举到的第一个视频设备；接入 Continuity
Camera 或其他 webcam 后应重新确认索引。

原生 librealsense bridge 保留为显式实验选项，主要用于具备原始 USB 访问能力的环境：

```bash
./scripts/run_realsense_bridge.sh
D435_BRIDGE_EXTERNAL=1 ./scripts/run_web.sh
```

若 AVFoundation 只枚举出名称带 `Depth` 的 D435 端点，实际画面可能是红外流，不适合当前
MediaPipe RGB hand tracking；名称带 `RGB Module RGB` 且能抓取彩色帧时才使用该索引。

默认只监听本机 `127.0.0.1:8787`。浏览器访问：

```text
http://127.0.0.1:8787/
```

健康检查：

```bash
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/vision/api/health
```

需要让同一可信局域网中的另一台电脑访问时，可运行：

```bash
./scripts/run_web.sh --host 0.0.0.0 --port 8787
```

此服务当前没有身份认证，不要暴露到公网。工作台包含：

- `VISION CONTROL`：D435 RGB/关键点切换、左右手检测、URDF 姿态、12 关节和 6 通道目标。
- `DIGITAL TWIN`：已配置左右手的在线状态、实际角度、目标角度和坐标系。
- `TACTILE`：按手掌结构排列的 17 个二维触觉区域、颜色热力图和三维山峰图。
- 中英文切换；工程标识在中文模式下仍保留英文。

设备工作台通过配置槽位区分左右手，因为 RH56 协议没有可靠的只读手型字段。只会显示
连接成功且角度回读有效的设备。

### D435 dry-run 与操作者 Profile 标定

1. 保持控制状态为 `DISARMED`。
2. 将右手完整放入 RGB 画面，确认 `TRACKING`、21 点骨架和六通道目标连续更新。
3. 测试张开、握拳、单指弯曲、四种指尖捏合和 tripod pinch。
4. 保持 `DISARMED`，在 Viewer 顶部的 `Operator profile` 中创建或选择操作者。
5. 点击 Profile 管理按钮和 `Calibrate`，依次完成张开、放松、握拳、拇指对掌和 OK 捏合。
6. 每个姿态保持稳定；Viewer 会自动收集 30 个合格样本并进入下一姿态，无需手动确认。

Profile 会把每位操作者的手指弯曲范围、拇指对掌范围和捏合距离映射到 RH56 的 URDF
可达空间。切换 Profile 会清空视觉 EMA 和接触锁存状态，但不会向真机发送位置指令。
Profile 只能在 `DISARMED` 时创建、切换、导入、删除或标定；标定失败时可在当前姿态重试。
配置保存在本机 `dex-retargeting/viewer/config/operator-profiles.json`，支持在管理器中导入和
导出匿名 JSON。旧版 `retargeting-calibration.json` 首次启动时会迁移为 `Legacy calibration`，
源文件不会被删除。
确定性手势诊断：

```bash
cd dex-retargeting
uv run --project .. python -m viewer.tools.retargeting_diagnostics
uv run --project .. python -m viewer.tools.retargeting_diagnostics \
  --live-seconds 20 \
  --output viewer/debug/retargeting-session.jsonl
cd ..
```

### D435 真机遥操作

1. 清空灵巧手运动空间，并确认没有其他进程连接 Modbus。
2. 在 `DISARMED` 状态确认实际六通道位置读取正常。
3. 保持右手稳定追踪，点击 `ARM` 并核对确认框中的实际值和视觉目标。
4. 控制器先读取当前位置，再以限幅、滤波和速度限制平滑追赶视觉目标。
5. 短暂或持续 tracking 丢失会进入 `RECOVERY HOLD`；恢复右手追踪后自动继续，不需要重新 ARM。
6. 操作结束点击 `DISARM`。异常时先使用 E-STOP，必要时立即物理断电。

控制器启动始终为 `DISARMED`。只有 `ARMED` 或 `POSITIONING` 会产生 Modbus 写入。

## 固定姿态

Viewer 可开可不开；脚本会优先使用健康且 `DISARMED` 的 Viewer，否则直接连接 Modbus：

```bash
./scripts/go_pose.sh open
./scripts/go_pose.sh home
```

- `open`：`[1000, 1000, 1000, 1000, 1000, 1000]`
- `home`：`[120, 120, 120, 120, 180, 480]`

脚本先读取实际位置，再使用较低的 preset 步长和速度执行。`Ctrl+C` 会尝试保持当前位置。
如果 Viewer 端口存在但不响应，脚本会拒绝直接回退，避免两个状态不明的控制器同时写设备。

## Quest / Open-Teach 遥操作

### 1. 安装 APK

在 Quest 中启用 Developer Mode 和 Hand Tracking，USB 连接后执行：

```bash
adb devices
adb install -r Open-Teach/VR/APK/SingleArmBot.apk
```

`adb devices` 应显示一个状态为 `device` 的序列号；若显示 `unauthorized`，需要在头显中允许
USB debugging。

### 2. 配置 Quest 网络

1. 在 `.env` 中把 `OPENTEACH_HOST` 设置为 Quest 能访问到的工作站局域网地址。
2. 在 Quest 的新安装应用中选择 `Change IP`，输入同一个地址。
3. 启用 Stream。绿色边框表示应用已开始发送关键点，但不代表真机控制已启用。
4. 能看到黑色手部 mask/关键点和测试物体后，再启动电脑端 dry-run。

### 3. Dry-run

```bash
./scripts/run_openteach.sh
```

默认配置 `dry_run: true`，只接收 Quest 24 点骨架、执行 RH56 URDF 重定向并记录六通道目标，
不会连接或写入灵巧手。先逐个测试四指弯曲、拇指弯曲/对掌和捏合。

### 4. 真机控制

先完全停止统一 Viewer，确保只有一个 Modbus 写入者，然后运行：

```bash
./scripts/run_openteach.sh --live
```

Open-Teach 使用与 D435 相同的 URDF 约束重定向，并在 30 Hz 控制循环中执行自适应步长、
速度限制和输出滤波。停止时按 `Ctrl+C`；如果手仍在运动或进程失联，立即物理断电。

## 触觉

RH56DFTP 使用压阻式触觉。当前读取 17 个区域、共 1062 个 taxel，最高目标采样率 20 Hz；
完整 Modbus 帧通常略低于该值。可视化同时提供：

- 二维区域热力图：按手掌和手指空间关系排列，适合定位触碰区域。
- 三维山峰图：高度和颜色共同表达相对压力，适合观察区域内分布。
- `Zero`：采集约 1 秒中位数作为浏览器基线，不修改设备内部标定。

原始值单位是 `raw counts`，不能直接解释为 N 或 Pa。二维布局表示阵列拓扑，不是厂家电极
中心的精确 CAD 坐标；如需物理精确 mapping，应向厂家索取每个 taxel 的编号、三维中心、
法向、有效面积、所属 link 和坐标系定义。

## 手部数据采集

当前 v1 只采手部数值，不保存 RGB、深度或机械臂数据。一次命令生成一个右手 episode：

```bash
./scripts/record_hand.sh \
  --task "index-thumb-pinch" \
  --operator "operator-01" \
  --duration 60
```

不传 `--duration` 时，按 `Ctrl+C` 完成并原子落盘。默认输出到 `datasets/hand/`。

常用参数：

```text
--output PATH
--source auto|viewer|standalone
--viewer-url http://127.0.0.1:8787
--startup-timeout 30
```

- `auto`：优先复用健康的统一 Viewer，否则启动只读 standalone pipeline。
- `viewer`：要求设备和视觉两个健康检查均通过。
- `standalone`：独立读取 D435、真机角度和触觉；没有 ARM 接口，不执行 Modbus 写入。

开始录制前必须同时满足：右手 `TRACKING`、真机六通道在线、右手触觉配置为
`piezoresistive_v1` 且收到完整 1062-taxel 帧。短暂视觉丢失不会结束 episode；对应 tracking
字段写入 NaN/invalid，真机和触觉流继续记录。

### HDF5 v1 schema

| Group | 频率 | 主要内容 |
| --- | --- | --- |
| `/frames` | 30 Hz | 21 个 2D/3D 点、12 URDF 关节、6 目标、接触与控制状态 |
| `/robot` | 约 5 Hz | 六通道实测位置、连接与 armed 状态 |
| `/tactile` | 最高 20 Hz | 17 区域、1062 个 `uint16` raw counts |
| `/events` | 事件触发 | tracking 转换、无效帧、开始和停止原因 |

写入期间文件后缀为 `.partial.h5`，正常结束后原子改名为 `.h5`。异常退出保留 partial 文件并将
`complete=false`，避免误用不完整数据。

快速检查数据：

```bash
uv run python -c '
import h5py, json, sys
with h5py.File(sys.argv[1], "r") as f:
    print(dict(f.attrs))
    print("frames", len(f["frames/time/elapsed"]))
    print("robot", len(f["robot/time/elapsed"]))
    print("tactile", len(f["tactile/time/elapsed"]))
' datasets/hand/YOUR_EPISODE.h5
```

HDF5 是当前 canonical 格式，因为数据是多速率压缩数值流。字段语义可映射到 LeRobot：
`robot/actual -> observation.state`，目标/命令 -> `action`，关键点和触觉 -> 自定义 observation。
进入策略训练或 Hugging Face Hub 发布阶段时再增加 LeRobot v3 exporter。

## 开发与验证

后端检查：

```bash
uv run ruff check hand_data_collection inspire_visualizer/backend unified_web scripts/tests \
  dex-retargeting/viewer dex-retargeting/src/dex_retargeting/inspire_retargeting.py
uv run pyright
uv run pytest -q

uv run pytest -q dex-retargeting/viewer/backend/tests
uv run pytest -q Open-Teach/tests
```

前端检查：

```bash
npm test --prefix inspire_visualizer/web -- --run
npm run typecheck --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web
```

独立前端开发服务器：

```bash
npm run dev --prefix inspire_visualizer/web
```

不要在同一台灵巧手上同时运行多个真机控制后端。前端开发可以连接统一后端，但 Modbus 写入
仍应只由一个控制器拥有。

## 团队协作约定

1. 从短生命周期 feature branch 开发，通过 PR 合并。
2. 不直接修改 `inspire_doc/` 中的厂家原始文件；衍生结论写到项目文档或代码中。
3. 不提交 `.env`、`hands.json`、个人标定、数据集、日志、截图中的地址或本机绝对路径。
4. 算法改动应附自动化测试和 dry-run 手势矩阵结果。
5. Modbus、速度、力或 pose 改动应在 PR 中记录真机型号、验证步骤和安全边界，不记录设备 IP。
6. 修改第三方目录时保留原许可证，并同步更新 [THIRD_PARTY.md](THIRD_PARTY.md)。
7. 提交前运行 `git status --ignored`，确认本地配置和数据处于 ignored 状态。

建议 PR 描述包含：

```text
Summary:
Risk / hardware impact:
Tests:
Dry-run evidence:
Physical verification (if any):
Rollback:
```

## 常见问题

### Viewer 启动但没有相机画面

- 确认 D435 使用 USB 3.x，并能被系统识别。
- 使用 AVFoundation 枚举视频端点，确认 D435 名称包含 `RGB Module RGB`。
- 确认 `.env` 使用 `D435_CAMERA_SOURCE=avfoundation` 和当前正确的摄像头索引。
- 在系统设置的“隐私与安全性 → 摄像头”中允许当前终端访问摄像头。
- `D435_CAMERA_ROTATION=90/180/270` 可按顺时针方向修正物理安装角度。
- AVFoundation 数字索引可能在手机连续互通相机或其他 webcam 接入后重新排序，不要永久
  假定 `0` 一定对应 D435。
- `RS2_USB_STATUS_ACCESS` 属于 librealsense 原始 USB 接口权限，与 AVFoundation 摄像头权限
  不同；当前 macOS 策略不依赖该接口。

### `DISCONNECTED` 或 Modbus 超时

- 检查 `.env` 与 `hands.json` 是否指向同一台设备。
- 运行 `ping` 和 `nc -vz`；检查网卡静态地址、子网掩码和防火墙。
- 确认没有 Viewer、Open-Teach 或 pose script 正在占用同一设备。

### Open-Teach 有手部画面但电脑收不到关键点

- Quest 中填写的是 `OPENTEACH_HOST`，不是灵巧手 IP。
- Quest 与该工作站接口必须互通；检查 `8087` 和防火墙。
- 先运行 `./scripts/run_openteach.sh` dry-run，再判断是否为真机链路问题。

### 数据采集一直显示 `Waiting for data`

日志会分别显示 `tracking`、`robot`、`tactile`。三者必须全部为 `ok` 才开始写 episode；确认
右手在画面中、设备在线，并在 `hands.json` 中启用 `piezoresistive_v1`。

### tracking 短暂丢失

真机控制进入 `RECOVERY HOLD` 并等待恢复；数据采集继续写无效 tracking 帧。若机械动作异常，
不要等待软件恢复，直接 E-STOP 或物理断电。

## English quick start

This repository targets an Inspire RH56DFTP right hand with a D435 RGB camera and optional
Quest 3. All committed network addresses are non-routable documentation examples.

```bash
uv sync --all-groups
brew install librealsense jpeg-turbo  # macOS D435 RGB bridge
cp .env.example .env
cp inspire_visualizer/config/hands.example.json inspire_visualizer/config/hands.json
# Edit both local files with your hardware endpoints.

npm ci --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web

./scripts/run_web.sh                 # unified workbench
./scripts/run_openteach.sh           # Quest dry-run
./scripts/run_openteach.sh --live    # Quest live control; stop Viewer first
./scripts/record_hand.sh --task "pinch" --operator "operator-01" --duration 60
```

Keep physical power removal accessible, validate every mapping in dry-run, and never commit local
IP addresses, calibration files, datasets, logs, or participant identifiers.
