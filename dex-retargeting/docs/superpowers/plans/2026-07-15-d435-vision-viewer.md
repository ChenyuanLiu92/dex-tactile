# D435 Vision Retargeting Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone FastAPI and React/Three.js Dry-run Viewer for D435 RGB right-hand tracking and Inspire retargeting.

**Architecture:** A latest-frame OpenCV capture worker and a MediaPipe/retargeting worker share thread-safe frame and telemetry stores. FastAPI streams MJPEG and WebSocket telemetry; a Vite React client overlays landmarks, animates the Inspire URDF by joint name, and displays 12 joint and six estimated channel values.

**Tech Stack:** Python 3.11, uv, OpenCV, MediaPipe, dex-retargeting, FastAPI, React, TypeScript, Vite, Three.js, urdf-loader, Vitest, Playwright

## Global Constraints

- Use AVFoundation camera index 0, requested 1280 by 720 at 30 FPS.
- Accept only the right hand and clear targets in every non-tracking state.
- Override Inspire vector retargeting `low_pass_alpha` to 0.5.
- Output estimated channels in `[pinky, ring, middle, index, thumb bend, thumb rotation]` order.
- Do not import `pymodbus`; do not include a physical hand IP or port 6000.
- Keep `DRY RUN` and `NO MODBUS OUTPUT` permanently visible.

---

### Task 1: Viewer Models and Six-Channel Mapping

**Files:**
- Create: `viewer/__init__.py`
- Create: `viewer/backend/__init__.py`
- Create: `viewer/backend/state.py`
- Create: `viewer/backend/retargeting.py`
- Create: `viewer/backend/tests/test_retargeting.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `TrackingStatus`, `TrackingSnapshot.to_payload()`, and `InspireRetargeter.retarget(landmarks_3d) -> (dict[str, float], list[int])`.

- [ ] Write tests for open/closed joint-limit normalization, exact actuator order, clipping, and null targets outside `TRACKING`.
- [ ] Run `uv run pytest -q viewer/backend/tests/test_retargeting.py` and observe failure because modules do not exist.
- [ ] Implement immutable snapshot models and name-based 12-to-six mapping.
- [ ] Add a `viewer` optional dependency extra with FastAPI and Uvicorn through uv.
- [ ] Re-run the focused tests and require a clean pass.

### Task 2: Camera and Right-Hand Tracking Pipeline

**Files:**
- Create: `viewer/backend/camera.py`
- Create: `viewer/backend/tracking.py`
- Create: `viewer/backend/runtime.py`
- Create: `viewer/backend/tests/test_tracking.py`
- Create: `viewer/backend/tests/test_camera.py`

**Interfaces:**
- Consumes: `TrackingSnapshot` and `InspireRetargeter` from Task 1.
- Produces: `CameraWorker`, `RightHandTracker.process(frame)`, and `ViewerRuntime` lifecycle/snapshot methods.

- [ ] Write failing tests using fake capture and fake MediaPipe results for mirrored frames, right-hand acceptance, left-hand rejection, LOST transition, latest-frame replacement, and clean shutdown.
- [ ] Implement AVFoundation capture with one latest-frame slot and no frame queue.
- [ ] Implement the MediaPipe landmark conversion using the existing MANO orientation convention.
- [ ] Implement runtime capture/tracking workers and FPS/latency metrics.
- [ ] Run both focused test modules and require a clean pass.

### Task 3: FastAPI, MJPEG, WebSocket, and Assets

**Files:**
- Create: `viewer/backend/app.py`
- Create: `viewer/backend/tests/test_app.py`
- Create: `viewer/run.py`

**Interfaces:**
- Consumes: `ViewerRuntime` from Task 2.
- Produces: `create_app()`, `/api/health`, `/api/video.mjpg`, `/api/ws`, and `/assets`.

- [ ] Write failing API tests with an injected fake runtime for health payload, WebSocket schema, MJPEG boundary/content type, and right-hand URDF access.
- [ ] Implement lifespan-controlled runtime startup and shutdown.
- [ ] Implement MJPEG and WebSocket routes without actuator-write routes.
- [ ] Mount the Inspire hand asset directory and built frontend when present.
- [ ] Run API tests and require a clean pass.

### Task 4: React Tracking Workbench

**Files:**
- Create: `viewer/web/package.json`
- Create: `viewer/web/index.html`
- Create: `viewer/web/tsconfig.json`
- Create: `viewer/web/vite.config.ts`
- Create: `viewer/web/src/main.tsx`
- Create: `viewer/web/src/App.tsx`
- Create: `viewer/web/src/api.ts`
- Create: `viewer/web/src/styles.css`
- Create: `viewer/web/src/camera/CameraPanel.tsx`
- Create: `viewer/web/src/scene/RobotScene.tsx`
- Create: `viewer/web/src/telemetry/TelemetryPanel.tsx`
- Create: `viewer/web/src/App.test.tsx`

**Interfaces:**
- Consumes: MJPEG at `/api/video.mjpg`, WebSocket snapshots at `/api/ws`, and URDF assets at `/assets`.
- Produces: the desktop tracking workbench and `viewer/web/dist`.

- [ ] Scaffold Vite/React TypeScript and install React, Three.js, urdf-loader, lucide-react, Vitest, Testing Library, and Playwright packages.
- [ ] Write a failing component test for permanent Dry-run labels, tracking state, 12 joint rows, and six actuator rows.
- [ ] Implement reconnecting WebSocket state, landmark canvas overlay, Three.js URDF animation, telemetry, and error states.
- [ ] Implement the dark industrial PC layout with stable panel dimensions and restrained transitions.
- [ ] Run `npm test` and `npm run build`.

### Task 5: Integration and Hardware Verification

**Files:**
- Modify: `README.md`
- Create: `viewer/web/e2e/viewer.spec.ts`
- Create: `viewer/web/playwright.config.ts`

**Interfaces:**
- Consumes: completed backend and frontend.
- Produces: documented launch command and verification evidence.

- [ ] Add uv/npm launch instructions, camera permission prerequisites, and explicit Dry-run scope.
- [ ] Run all Python tests, Ruff, frontend tests, and production build.
- [ ] Start the backend on a free localhost port and run Playwright at 1440 by 900 and 1920 by 1080, including a nonblank WebGL pixel check.
- [ ] Run a 30-second D435 camera-index-0 smoke test and report measured capture FPS/read failures.
- [ ] Scan `viewer/` for `pymodbus`, the physical-hand IP, and port 6000; require no matches.
