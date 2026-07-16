# Inspire Aggressive Motion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Inspire RH56DFTP hand retargeting at 30 Hz with aggressive per-channel step and speed bands while retaining existing safety behavior.

**Architecture:** Keep adaptive error-band logic in `InspireRetargeter`, but provide the aggressive profile through Hydra configuration. Make `InspireHandOperator` control frequency configurable and derive its approximately 5 Hz diagnostic interval from that frequency.

**Tech Stack:** Python 3.11, NumPy, Hydra, pymodbus 2.5.3, pytest, uv

## Global Constraints

- Control frequency is 30 Hz.
- Error thresholds remain `[40, 180]` with deadband 8 and hysteresis 10.
- Maximum steps are `[20, 60, 120]`; speeds are `[100, 260, 450]`.
- Force remains `[220, 120, 120, 120, 220, 220]`.
- Automated verification must remain dry-run and must not connect to the physical hand.

---

### Task 1: Configurable Operator Frequency

**Files:**
- Modify: `openteach/components/operators/inspire.py`
- Modify: `tests/test_inspire_operator.py`

**Interfaces:**
- Consumes: `FrequencyTimer(frequency_rate)` and existing `InspireHandOperator` constructor arguments.
- Produces: `InspireHandOperator(..., control_frequency=30)` and `_log_every == 6` at 30 Hz.

- [ ] **Step 1: Write the failing test**

Add a constructor test that replaces `ZMQKeypointSubscriber` and `FrequencyTimer`, constructs the operator with `control_frequency=30`, and asserts the timer receives 30 and `_log_every` is 6.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project .. pytest -q tests/test_inspire_operator.py`

Expected: FAIL because `control_frequency` is not accepted and logging is fixed at four frames.

- [ ] **Step 3: Write minimal implementation**

Update the constructor to accept `control_frequency=20`, validate it as a positive integer, initialize `FrequencyTimer(control_frequency)`, and set `_log_every = max(1, round(control_frequency / 5))`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project .. pytest -q tests/test_inspire_operator.py`

Expected: all operator tests pass.

### Task 2: Aggressive Hydra Profile

**Files:**
- Modify: `configs/robot/inspire_hand.yaml`
- Modify: `tests/test_inspire_retargeting.py`
- Modify: `docs/inspire_hand.md`

**Interfaces:**
- Consumes: existing `adaptive_motion` mapping accepted by `InspireRetargeter`.
- Produces: Hydra operator configuration with `control_frequency: 30`, `max_steps: [20, 60, 120]`, and `speeds: [100, 260, 450]`.

- [ ] **Step 1: Write the failing profile test**

Add an aggressive-profile test that creates `InspireRetargeter` with the approved values and checks errors 9, 50, and 300 produce steps 20, 60, and 120 with speeds 100, 260, and 450.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project .. pytest -q tests/test_inspire_retargeting.py`

Expected: FAIL until the test fixture and expected profile are updated together.

- [ ] **Step 3: Update configuration and documentation**

Set `control_frequency: 30`, `max_steps: [20, 60, 120]`, and `speeds: [100, 260, 450]`. Update the documented error-band table and 30 Hz control rate without changing force, thresholds, deadband, or hysteresis.

- [ ] **Step 4: Run focused tests**

Run: `uv run --project .. pytest -q tests/test_inspire_retargeting.py tests/test_inspire_operator.py`

Expected: all focused tests pass.

### Task 3: Full Dry-Run Verification

**Files:**
- Verify: `configs/robot/inspire_hand.yaml`
- Verify: `openteach/components/operators/inspire.py`
- Verify: `openteach/robot/inspire/retargeting.py`

**Interfaces:**
- Consumes: approved aggressive Hydra profile.
- Produces: evidence that configuration, tests, and synthetic commands are valid without Modbus access.

- [ ] **Step 1: Run full tests and compile checks**

Run: `uv run --project .. pytest -q tests`

Run: `uv run --project .. python -m compileall -q openteach/robot/inspire openteach/components/operators/inspire.py tests`

Expected: both commands exit zero.

- [ ] **Step 2: Verify Hydra composition**

Run: `uv run --project .. python teleop.py --cfg job robot=inspire_hand`

Expected: output contains `control_frequency: 30`, approved steps and speeds, and `dry_run: true`.

- [ ] **Step 3: Run synthetic dry-run**

Construct a dry-run `InspireHand` and adapt channel errors 9, 50, and 300 in both directions.

Expected positions: `[509, 550, 620, 491, 450, 380]`; expected speeds: `[100, 260, 450, 100, 260, 450]` from a current position of 500.
