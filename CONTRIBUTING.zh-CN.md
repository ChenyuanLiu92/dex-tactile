# 参与 Dex Tactile 开发

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING.zh-CN.md)

感谢参与 Dex Tactile。本项目会控制真实硬件，因此一个改动只有在行为、验证范围、安全影响和
回滚路径都能被另一位开发者清楚理解时，才算完成。本指南定义所有 Pull Request 的最低标准。

## 开始之前

1. 先搜索已有 issue 和 PR，避免重复工作。
2. 改动控制行为、数据 schema、公共 API 或仓库架构时，先创建 issue 或 Draft PR。
3. 一个 PR 只解决一个目标；不要混入无关清理、依赖升级或其他功能。
4. 连接真机或采集数据前，先阅读下方安全与隐私规则。

环境和硬件配置见 [README.zh-CN.md](README.zh-CN.md)。

## 不可违反的规则

- 禁止提交 `.env`、`hands.json`、操作者 Profile、触觉标定、数据集、日志、真实 IP、设备序列号、
  受试者身份或本机绝对路径。
- 不直接修改 `inspire_doc/` 中的厂家原始资料；衍生代码和结论放到其他目录。
- 同一只手上禁止同时运行多个 Modbus 真机写入者。
- dry-run 目标、左右手、限幅和物理空间未确认前，真机控制必须保持 `DISARMED`。
- 只做了仿真、mock 或 dry-run 时，不得声称已经完成真机验证。
- 修改第三方代码、资产或上游版本时保留许可证，并更新 [THIRD_PARTY.md](THIRD_PARTY.md)。
- 禁止强推 `main`、重写共享历史，或绕过 Review 合并会影响硬件的改动。

## 开发环境

```bash
git clone https://github.com/ChenyuanLiu92/dex-tactile.git
cd dex-tactile

uv sync --all-groups
npm ci --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web
```

从模板复制本地配置，真实端点只能写入被忽略的文件：

```bash
cp .env.example .env
cp inspire_visualizer/config/hands.example.json inspire_visualizer/config/hands.json
```

## 分支

从最新 `main` 创建短生命周期分支：

```bash
git switch main
git pull --ff-only
git switch -c <type>/<short-kebab-description>
```

分支前缀：

| 前缀 | 用途 |
| --- | --- |
| `feat/` | 用户可见的新能力 |
| `fix/` | 缺陷或安全修复 |
| `docs/` | 仅文档改动 |
| `test/` | 测试或测试基础设施 |
| `refactor/` | 不改变行为的重构 |
| `perf/` | 有测量依据的性能优化 |
| `chore/` | 工具、维护或依赖工作 |

示例：`feat/operator-profiles`、`fix/thumb-opposition-rate`、`docs/dataset-schema`。

不要在长期分支中混合多位开发者的无关改动。请求最终 Review 前同步 `main`，并在本地解决冲突。

## Commit

使用聚焦、祈使语气的 Conventional Commit 风格标题：

```text
feat: add operator calibration profiles
fix: hold position during tracking recovery
docs: document HDF5 event semantics
test: cover Modbus ownership conflicts
```

- 标题尽量不超过 72 个字符。
- 当安全或算法原因不明显时，在正文解释为什么修改。
- 不提交 `WIP`、缓存、调试采集、编辑器元数据或无关格式化。
- 测试和文档应与其描述的行为在同一个 PR 中更新。

## 工程要求

### Python

- 依赖只通过根目录 `pyproject.toml` 和 `uv.lock` 管理。
- 遵循现有类型和所有权边界，不建立平行的设备/控制抽象。
- 结构化协议和数据使用结构化 API 解析，不做脆弱的字符串拼接。
- 每个缺陷修复都增加回归测试；硬件命令增加边界测试。

### React 与 TypeScript

- 统一前端只位于 `inspire_visualizer/web`，不要再创建独立 Viewer。
- 新增用户可见文本必须同时覆盖中英文，工程标识保持英文。
- 先验证 PC 工作台，再确认紧凑视口没有溢出或重叠。
- 复用现有图标库、设计 token 和交互模式。

### Retargeting 与控制

- 映射以 RH56 URDF 和既定六通道顺序为依据。
- 保留目标限幅、滤波、速度限制、视觉丢失保持、ARM/DISARM、E-STOP 和 Modbus 互斥所有权；
  如需改动，PR 必须明确重新设计并测试这些安全机制。
- Retargeting 改动需要提供张开、握拳、四指逐指弯曲、拇指弯曲/对掌、四种捏合和 tripod pinch
  的确定性诊断证据。
- 新的真机控制或定位过程开始前必须读取灵巧手实测位置。

### 触觉与数据

- 除非有明确硬件版本变更，必须保留 17 个区域和 1,062 个 taxel。
- raw counts 与标定力必须区分；没有力标定时不得标注为 N 或 Pa。
- HDF5 schema 改动属于兼容性改动，必须说明迁移和 partial 文件行为。
- 即使仓库是私有的，也禁止提交受试者采集数据。

## 验证矩阵

运行所有与改动范围匹配的检查，并在 PR 中记录完整命令和结果。

| 改动 | 最低证据 |
| --- | --- |
| 仅文档 | `git diff --check`、链接/资产检查、隐私扫描 |
| Python/后端 | Ruff、Pyright、根 pytest、受影响模块测试 |
| React/UI | Vitest、TypeScript、生产构建；工作流/布局需 Playwright |
| Retargeting | 单元测试、确定性手势诊断和 dry-run 手势矩阵 |
| Modbus/控制 | 单元测试、dry-run、故障/保持行为、明确硬件风险 |
| 触觉 | 完整 1,062-taxel 帧、mapping 测试和相关截图 |
| RealSense/相机 | 相机测试、适用时桥接测试、`/vision/api/health` 结果 |
| HDF5/数据 | schema、异常中断/partial 文件测试和样例文件检查 |

后端标准检查：

```bash
uv run ruff check hand_data_collection inspire_visualizer/backend/src unified_web \
  dex-retargeting/viewer/backend \
  dex-retargeting/src/dex_retargeting/inspire_retargeting.py \
  Open-Teach/openteach/robot/inspire \
  Open-Teach/openteach/components/operators/inspire.py
uv run pyright
uv run pytest -q
uv run pytest -q dex-retargeting/tests dex-retargeting/viewer/backend/tests Open-Teach/tests
```

前端标准检查：

```bash
npm test --prefix inspire_visualizer/web -- --run
npm run typecheck --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web
```

浏览器工作流先启动统一后端，再执行：

```bash
./scripts/run_web.sh
npm run e2e --prefix inspire_visualizer/web
```

RealSense 原生生命周期检查：

```bash
bash scripts/tests/test_run_web_realsense.sh
bash dex-retargeting/viewer/native/tests/test_bridge_cli.sh
```

某项检查因平台限制无法执行时，明确标为 `Not run`，解释原因并说明残余风险。禁止静默省略
与改动有关的检查。

## 真机验证级别

PR 中必须准确选择一个级别：

- **Not hardware tested**：只做软件检查，不能得出真机结论。
- **Dry-run verified**：检查真实输入和输出目标，但关闭 Modbus 输出。
- **Hardware verified**：在指定型号真机上测试，并保持物理断电可触达。

真机验证只记录型号和控制路径，不记录 IP 或序列号，并说明：

- 起始姿态和测试手势/动作
- 与改动相关的最大速度或步长
- 观察到的视觉丢失、断连和 E-STOP 行为
- 是否出现异常运动、超调、振动或机械接触
- 如何回到已知安全的释放或张开姿态

出现异常运动必须立即停止。软件恢复不能替代物理断电。

## Pull Request

### 创建前

1. 重新阅读 diff，删除无关文件。
2. 运行 `git diff --check` 和对应验证矩阵。
3. 运行 `git status --ignored`，确认本地配置和数据仍处于 ignored 状态。
4. 检查文字、截图、fixture 和日志中的隐私信息。
5. 契约发生变化时，同步更新 README、schema 文档、`.env.example` 和测试。

### PR 标题

与 commit 使用相同格式：

```text
<type>: <imperative summary>
```

例如：`fix: preserve thumb target lead` 或 `docs: define contribution workflow`。

### PR 描述

填写仓库 PR 模板中所有适用部分，特别是：

- 描述用户或系统行为，而不只是列出修改文件。
- 明确说明硬件和安全影响。
- 粘贴实际测试命令和简洁结果。
- 视觉改动附截图；映射/控制改动附 dry-run 证据。
- 说明兼容性、迁移和回滚。
- 缺少的证据标记为 `Not run`，不要删除对应章节。

需要早期设计或硬件反馈时可先开 Draft PR。完成自查和对应本地检查后再标记 Ready for review。

## Review 与合并规则

满足以下条件后才能合并：

- 改动范围一致，PR 模板填写完整。
- 对应自动化检查通过，未运行项有合理说明。
- Review 讨论全部解决。
- 公共行为、配置或数据契约变更已更新文档。
- 隐私和生成文件检查通过。
- 硬件相关改动有明确安全 Review 和 dry-run 证据；真机测试或合并前应由第二位 Reviewer 检查。

Review 优先检查正确性、物理安全、回归、协议/数据兼容性、缺失测试、隐私和回滚；不要让纯风格
意见掩盖行为风险。

单一目的 PR 默认使用 **Squash merge**。只有当多个 commit 的历史确实有价值时才保留 merge
commit。合并后删除功能分支。禁止合并 Draft PR 或强制绕过失败检查。

## 报告缺陷

提供最小复现、预期/实际行为、平台、灵巧手型号、控制状态和脱敏日志。删除 IP、序列号、用户名、
本机绝对路径和受试者数据。发生危险动作时先断电，再记录最后已知控制器状态和命令路径。
