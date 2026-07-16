# RH56DFTP Preset Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Home-specific motion with guarded fixed-preset positioning and provide one `go_pose.sh {home|open}` operator command.

**Architecture:** `VisionHandController` owns an immutable `Preset` table and one `POSITIONING` execution path; explicit body-free Home/Open API routes are thin wrappers. One workspace shell script validates its preset argument and calls the matching route without exposing arbitrary actuator targets.

**Tech Stack:** Python 3.11, NumPy, FastAPI, pytest, Bash, React 19, TypeScript, uv

## Global Constraints

- Presets are `HOME=[120,120,120,120,180,480]` and `OPEN=[1000,1000,1000,1000,1000,1000]`.
- Positioning starts only from connected `DISARMED` and uses measured-position seeding.
- Existing 30 Hz motion shaping, force limits, 20-second server timeout, E-STOP, and fault behavior remain unchanged.
- HTTP and CLI surfaces do not accept arbitrary six-channel targets.
- Automated tests never call a real motion endpoint.

---

### Task 1: Generic Preset Controller

**Files:**
- Modify: `viewer/backend/control/controller.py`
- Modify: `viewer/backend/control/__init__.py`
- Test: `viewer/backend/tests/test_control_controller.py`

**Interfaces:**
- Produces: `Preset`, `PRESET_POSES`, `ControlState.POSITIONING`, `move_to_preset()`, `home()`, and `open()`.

- [ ] Replace Home-only test expectations with failing generic-state tests and add the fully open target test.
- [ ] Run the focused controller tests and verify failures reference missing `Preset`, `POSITIONING`, or `open()` behavior.
- [ ] Implement the immutable preset table and one positioning tick path.
- [ ] Re-run controller tests and require a clean pass.

### Task 2: Explicit Preset APIs and Telemetry

**Files:**
- Modify: `viewer/backend/app.py`
- Modify: `viewer/backend/tests/test_app.py`
- Modify: `viewer/web/src/api.ts`

**Interfaces:**
- Produces: protected `POST /api/control/home`, protected `POST /api/control/open`, and `POSITIONING`/`preset` telemetry.

- [ ] Add failing API tests for both fixed routes and no arbitrary route.
- [ ] Implement the Open route and generic output-state reporting.
- [ ] Update frontend snapshot types from `HOMING` to `POSITIONING` and add nullable `preset`.
- [ ] Run API tests and the frontend type/build checks.

### Task 3: One Parameterized Operator Script

**Files:**
- Delete: `../scripts/go_home.sh`
- Create: `../scripts/go_pose.sh`
- Rename: `../scripts/tests/test_go_home.py` to `../scripts/tests/test_go_pose.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `go_pose.sh home` and `go_pose.sh open`.

- [ ] Rewrite fake-server tests to cover both arguments, usage rejection, authentication, progress, success, transition rejection, and faults; verify they fail against the old script.
- [ ] Implement exact argument validation and route mapping in the single executable script.
- [ ] Remove the old script and update operator documentation.
- [ ] Run script tests and Shell syntax checks.

### Task 4: Non-Hardware Regression and Restart

**Files:**
- No additional production files.

**Interfaces:**
- Produces: test/build evidence and a live read-only `DISARMED` Viewer.

- [ ] Run Ruff and all Python tests including upstream, Viewer, and root script tests.
- [ ] Run Vitest and the production frontend build.
- [ ] Restart the Viewer only if an old process occupies port 8787.
- [ ] Read `/api/health` and confirm connected `DISARMED` with `modbus_output=false`; do not POST Home or Open.
