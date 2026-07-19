# Inspire Hand 可视化与控制

该目录提供 Web 可视化与控制功能。后端负责 Modbus TCP 设备发现、姿态与触觉采样和安全下发；前端使用官方 URDF/STL 显示实际/目标姿态，并通过二维手形图谱显示触觉热力图和山峰图。

## 目录

```text
inspire_visualizer/
├── backend/
│   ├── src/inspire_visualizer_api/   # FastAPI、WebSocket、Modbus 与设备状态
│   └── tests/                        # Python 单元与接口测试
├── config/
│   └── hands.example.json           # 左右手端点示例
└── web/
    ├── public/models/                # 官方 URDF/STL 的运行副本和来源清单
    ├── src/                          # React、Three.js 与控制界面
    ├── tests/                        # 前端单元/组件测试
    └── e2e/                          # 真实浏览器 3D 验收
```

Python 依赖统一由根目录的 UV 项目管理；npm 只管理 `web/` 内的前端依赖。

## 统一工作台运行（推荐）

在仓库根目录构建前端并启动单一 Web 服务：

```bash
cd inspire_visualizer/web
npm install
npm run build
cd ../..
./scripts/run_web.sh
```

浏览器只需访问 <http://127.0.0.1:8787/>。顶部可在 `VISION CONTROL` 和
`DIGITAL TWIN / TACTILE` 之间切换。设备/触觉 API 位于 `/api`，D435 视觉与
真机控制 API 位于 `/vision/api`；两者由同一个 Uvicorn 进程托管。

统一模式中，Digital Twin 的姿态面板为只读，所有运动写入必须从 Vision
Control 的 ARM/E-STOP 流程执行，避免两套控制会话同时写入 RH56。

## 独立开发运行

在项目根目录同步 Python 环境并启动后端：

```bash
uv sync
uv run uvicorn inspire_visualizer_api.app:app \
  --app-dir inspire_visualizer/backend/src \
  --host 127.0.0.1 --port 8000 --reload
```

另开终端启动前端：

```bash
cd inspire_visualizer/web
npm install
npm run dev
```

浏览器访问 <http://127.0.0.1:5173>。Vite 会把 `/api` 和 WebSocket 转发到本机 8000 端口。

## 生产运行

```bash
cd inspire_visualizer/web
npm run build
cd ../..
uv run uvicorn inspire_visualizer_api.app:app \
  --app-dir inspire_visualizer/backend/src \
  --host 127.0.0.1 --port 8000
```

构建完成后 FastAPI 会托管 `web/dist`，访问 <http://127.0.0.1:8000>。

## 设备规则

- 提交的默认值仅使用 RFC 5737 示例地址；复制 `config/hands.example.json` 后填写真实左右手端点。
- 默认左手触觉配置为压阻式 `piezoresistive_v1`；电容式 `-C1` 型号应选择 `capacitive_v1`，普通手或未接触觉时选择 `disabled`。
- 左右手身份由配置槽位明确指定；设备协议没有可靠的只读手型字段，连接探测仅判断已配置端点是否在线。
- 只显示已连接且角度回读有效的手；左右手同时在线时并排显示，并提供控制对象切换。
- 后端每 200 ms 轮询在线设备，每 2 s 重试离线设备。状态超过 1 s 未更新会自动撤销解锁。
- 下发顺序固定为速度、力控阈值、目标角度。角度和速度范围为 `0..1000`，力控阈值为 `0..3000`。
- 每个浏览器 WebSocket 会话独立解锁；断开连接、设备掉线或状态过期都会自动撤销解锁。
- 3D 视图可切换 `All / World / Base / Actuator refs / Off` 坐标显示；`WORLD` 位于场景原点，`BASE / MOUNT` 绑定 URDF `base_link`，`L/R J1-J6` 绑定六个驱动通道对应的 URDF 关节轴心。
- 工程网格随相机距离在 `20 mm / 10 mm / 5 mm / 2.5 mm` 小格间分级切换，放大时自动显示更细密方格，主格始终为小格的五倍。
- `Tactile` 工作区按手掌结构排列 17 块、1062 个压阻式 taxel；`Heatmap / Surface` 切换二维热力图和二维画布绘制的山峰图，`Raw / Smooth` 只改变绘制方式，不修改原始采样值。
- 交互式标定为每个区域采集五个稳定触点，并将拟合后的双线性 taxel 坐标映射同时应用于热力图、山峰图和点击命中；未标定区域保持规则网格。
- 触觉目标采样率最高为 20 Hz，界面显示设备实际达到的速率。当前实机完整帧约需 56 ms，因此通常显示约 18 Hz。
- `Zero` 在浏览器内采集 1 秒数据并计算逐点中位基线，不写入设备、不替代官方力传感器校准。原始触觉值统一标记为 `raw counts`，不冒充 N 或 Pa。
- 前端只保存最近 10 秒的区域均值、峰值和活动点数量，不持久化原始帧。
- 当前手部 URDF 没有独立的机械臂末端或法兰 link，因此不虚构额外 flange frame；接入机械臂 URDF 或外参后再增加 `tool0`/法兰坐标。
- 当前标定修正的是区域内部的二维显示映射，不等同于厂家电极中心坐标、压力单位标定或触觉膜材料模型。

首次连接设备前，按厂家手册将主机有线网卡配置到设备所在网段，且不能与手的地址重复。

## 验证

```bash
uv run pytest -q
uv run ruff check inspire_visualizer/backend
uv run pyright inspire_visualizer/backend/src
cd inspire_visualizer/web
npm test -- --run
npm run typecheck
npm run build
npm run e2e
```

模型运行副本的来源、包名、数量和 URDF SHA-256 记录在 `web/public/models/manifest.json`。
