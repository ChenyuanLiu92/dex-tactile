# D435 RH56DFTP Vision Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add guarded 30 Hz RH56DFTP Modbus control to the D435 right-hand vision viewer with current-position ARM seeding, automatic hold/disarm, and latched E-STOP.

**Architecture:** A focused control package separates Modbus register access, adaptive motion shaping, and the safety state machine. `ViewerRuntime` publishes vision snapshots to the controller; FastAPI exposes only guarded state transitions, while React renders ARM confirmation, DISARM, E-STOP, RESET, and live control telemetry.

**Tech Stack:** Python 3.11, pymodbus 2.5.3, NumPy, FastAPI, React 19, TypeScript, Vitest, Playwright, uv

## Global Constraints

- Device: RH56DFTP at `192.0.2.10:6000`.
- Control frequency: 30 Hz.
- Position range: `0..1000`; reject malformed or non-finite six-channel inputs.
- Motion profile: deadband `8`, thresholds `[40, 180]`, steps `[20, 60, 120]`, speeds `[100, 260, 450]`, hysteresis `10`.
- Force: `[220, 120, 120, 120, 220, 220]`.
- Startup and reconnect never write motion registers.
- ARM seeds from a fresh `ANGLE_ACT` read; no direct jump to the vision target.
- Any stale/non-tracking target while armed holds measured position and disarms.
- E-STOP is latched and can only leave through explicit RESET.
- No arbitrary register, target, speed, or force API.

---

### Task 1: Modbus Driver and Adaptive Motion

**Files:**
- Create: `viewer/backend/control/__init__.py`
- Create: `viewer/backend/control/driver.py`
- Create: `viewer/backend/control/motion.py`
- Test: `viewer/backend/tests/test_control_driver.py`
- Test: `viewer/backend/tests/test_control_motion.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `RH56Driver.connect()`, `read_positions()`, `write_motion(positions, speeds)`, `hold_current()` and `AdaptiveMotion.command(targets, current) -> MotionCommand`.

- [ ] Write fake-client tests proving register addresses `1486/1498/1522/1546`, validation, connection cleanup, and no writes during connect/read.
- [ ] Run `uv run pytest -q viewer/backend/tests/test_control_driver.py` and require failure because the control package is absent.
- [ ] Add `pymodbus==2.5.3` to the uv `viewer` extra and implement the minimal driver.
- [ ] Write motion tests for all three bands, deadband, hysteresis, clipping, and independent channel steps; observe failure.
- [ ] Implement immutable `MotionCommand` and the approved adaptive profile, then require both focused modules to pass.

### Task 2: Guarded Controller State Machine

**Files:**
- Create: `viewer/backend/control/controller.py`
- Test: `viewer/backend/tests/test_control_controller.py`
- Modify: `viewer/backend/state.py`
- Modify: `viewer/backend/runtime.py`

**Interfaces:**
- Consumes: `RH56Driver`, `AdaptiveMotion`, and `TrackingSnapshot`.
- Produces: `ControlState`, `ControlSnapshot.to_payload()`, and `VisionHandController` methods `start`, `stop`, `arm`, `disarm`, `estop`, `reset`, `reconnect`, and `update_tracking`.

- [ ] Write fake-clock/fake-driver tests for read-only startup, measured-position ARM seeding, 30 Hz command shaping, invalid transition rejection, 150 ms freshness, loss hold/disarm, E-STOP latch, RESET, and write failure to FAULT.
- [ ] Run the focused tests and verify they fail because `controller.py` is absent.
- [ ] Implement the locked state machine and controller worker with periodic writes owned only by the controller.
- [ ] Attach controller lifecycle to `ViewerRuntime`; pass every new tracking snapshot through `update_tracking` without blocking MediaPipe.
- [ ] Run controller and existing runtime tests and require a clean pass.

### Task 3: Guarded FastAPI Control Surface

**Files:**
- Modify: `viewer/backend/app.py`
- Modify: `viewer/backend/tests/test_app.py`

**Interfaces:**
- Consumes: `VisionHandController` transition methods.
- Produces: `POST /api/control/{arm,disarm,estop,reset,reconnect}`, extended health, and WebSocket payload field `control`.

- [ ] Extend the fake runtime and write failing tests for every transition, HTTP 409 on invalid transitions, control telemetry, and absence of a general write route.
- [ ] Implement thin endpoints that return controller snapshots and translate transition errors without accepting register or target bodies.
- [ ] Update health and WebSocket payloads with accurate `modbus_output` and control state.
- [ ] Run all backend API tests and require a clean pass.

### Task 4: Workbench Safety Controls

**Files:**
- Modify: `viewer/web/src/api.ts`
- Modify: `viewer/web/src/App.tsx`
- Modify: `viewer/web/src/styles.css`
- Create: `viewer/web/src/control/ControlPanel.tsx`
- Create: `viewer/web/src/control/ControlPanel.test.tsx`
- Modify: `viewer/web/src/App.test.tsx`

**Interfaces:**
- Consumes: WebSocket `control` telemetry and guarded POST endpoints.
- Produces: connection/state indicator, ARM confirmation modal, DISARM, immediate E-STOP, RESET/RECONNECT, and actual/command/speed telemetry.

- [ ] Write failing component tests for disabled ARM without fresh tracking, confirmation contents, transition calls, unconditional E-STOP visibility while armed, and ESTOPPED/FAULT recovery actions.
- [ ] Implement typed API calls and the control panel with stable dimensions and keyboard-visible modal controls.
- [ ] Replace permanent dry-run copy with truthful state while retaining a visible software-hold warning.
- [ ] Run Vitest and production build and require a clean pass.

### Task 5: Safety and Hardware Verification

**Files:**
- Modify: `README.md`
- Modify: `viewer/web/e2e/viewer.spec.ts`

**Interfaces:**
- Consumes: completed controller, API, and UI.
- Produces: documented launch/safety workflow and hardware evidence.

- [ ] Document DISARMED startup, ARM confirmation, automatic hold/disarm, E-STOP latch, RESET, and physical power-removal warning.
- [ ] Run Python tests, Ruff, Vitest, TypeScript build, npm audit, and Playwright at 1440x900 and 1920x1080.
- [ ] Restart Viewer and verify read-only startup against `192.0.2.10:6000`, confirming no motion writes before ARM.
- [ ] Do not issue ARM or movement during automated verification; leave the live server `DISARMED` for supervised manual testing.
