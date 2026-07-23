# Inspire Teleoperation

Modular Quest teleoperation for a six-DOF Inspire dexterous hand.  The current
distribution controls hands only, while its public frame/module API is designed
to add robot-arm teleoperation without changing the hand data path.

Data flow:

```text
QuestSource -> TeleopFrame -> TeleopRuntime -> HandTeleopModule
                                       `----> future ArmTeleopModule
```

`TeleopFrame` carries immutable left/right hand landmarks plus optional wrist
and head transforms. Each output module owns its controller, update rate,
connection lifecycle, and telemetry. Pausing still distributes frames with
`enabled=False`, allowing every module to implement its own safe hold behavior.

## Layout

- `inspire_teleoperation/api.py`: stable frame, source, module, and status contracts
- `inspire_teleoperation/runtime.py`: source/module lifecycle and frame fan-out
- `inspire_teleoperation/quest_source.py`: TeleVuer input adapter
- `inspire_teleoperation/hand_module.py`: dexterous-hand output adapter
- `inspire_teleoperation/main.py`: CLI and Web application composition
- `inspire_teleoperation/web_ui.py` and `web/`: local Web console
- `inspire_teleoperation/hand_controller.py`: retargeting and command loop
- `inspire_teleoperation/hand_retargeting.py`: local retargeting setup
- `inspire_teleoperation/dexhand.py`: copied low-level Modbus client
- `inspire_teleoperation/assets/hand_model/`: retargeting model and meshes
- `tests/`: hardware-independent unit tests

The runtime uses `televuer` and `dex-retargeting` as libraries. The Modbus
client is included directly, so no sibling DexterousHand checkout is needed.

From the repository root:

```bash
uv run python -m inspire_teleoperation --help
uv run python -m unittest discover -s tests
uv run python -m inspire_teleoperation
```

The final command can connect hardware. Confirm each host, port, device ID,
the clear workspace, and a conservative speed in the Web console first.

完整的中文接口、生命周期、Web API、Modbus API 和机械臂接入说明见
[API 文档](docs/API.zh-CN.md)。

## Adding an arm module

Implement the small `TeleopModule` contract and register it beside the hand
module. The arm receives the same timestamped frame and can use wrist/head poses
without depending on Modbus or hand retargeting internals:

```python
from inspire_teleoperation import ModuleStatus, TeleopFrame

class ArmTeleopModule:
    name = "arms"

    def start(self):
        self.controller.connect()

    def update(self, frame: TeleopFrame, *, enabled: bool):
        if not enabled or not frame.motion_data_ready:
            self.controller.hold()
            return
        if frame.right_hand and frame.right_hand.wrist:
            self.controller.command_wrist(frame.right_hand.wrist.matrix)

    def status(self):
        return ModuleStatus(self.name, ready=self.controller.is_connected)

    def close(self):
        self.controller.close()
```

Compose it with `TeleopRuntime(source, [hand_module, arm_module])`. For a real
arm integration, add workspace limits, velocity/acceleration limiting, frame
calibration, watchdog timeout, and an explicit emergency-stop path inside the
arm module rather than in the shared runtime.
