# macOS RealSense RGB Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream D435 RGB frames into the unprivileged vision Viewer through a narrowly privileged native helper.

**Architecture:** A C++ librealsense/turbojpeg helper publishes versioned JPEG frames over a user-owned Unix socket. A Python `RealSenseBridgeWorker` validates and decodes that protocol into the existing `LatestFrameStore`; the launch script builds and starts only the helper with `sudo`, then runs the unified Viewer normally.

**Tech Stack:** C++17, librealsense2 2.58+, libturbojpeg, Unix domain sockets, Python 3.11, OpenCV, pytest, Bash.

## Global Constraints

- macOS 12+ direct librealsense USB access requires elevated privileges.
- Only the RGB helper may run as root; Viewer and Modbus control remain unprivileged.
- RGB only at 1280x720 and 30 FPS; depth and point clouds are excluded.
- Camera failure must become `CAMERA_ERROR` and must never ARM the hand.
- Tracked configuration must not contain the physical camera serial number.

---

### Task 1: Versioned Frame Protocol And Python Bridge Client

**Files:**
- Create: `dex-retargeting/viewer/backend/realsense_bridge.py`
- Create: `dex-retargeting/viewer/backend/tests/test_realsense_bridge.py`

**Interfaces:**
- Produces: `HEADER_STRUCT`, `MAX_JPEG_BYTES`, `BridgeFrame`, `read_bridge_frame(stream)`, and `RealSenseBridgeWorker(store, socket_path, rotation, on_error)`.
- Consumes: `LatestFrameStore` and the same rotation/mirror behavior as `CameraWorker`.

- [ ] **Step 1: Write failing protocol tests** for a fragmented valid header/payload, invalid magic, unsupported version, oversized payload, truncated payload, and JPEG decode failure.
- [ ] **Step 2: Run** `uv run pytest -q dex-retargeting/viewer/backend/tests/test_realsense_bridge.py` and verify failures are caused by the missing module.
- [ ] **Step 3: Implement protocol parsing** with a network-order header `!4sB3xQQI`, magic `DRGB`, version `1`, and an 8 MiB payload ceiling.
- [ ] **Step 4: Add failing worker tests** using a temporary Unix socket server to prove frame publication, rotation/mirroring, reconnect after disconnect, and a clear error when no server becomes available.
- [ ] **Step 5: Implement `RealSenseBridgeWorker`** with bounded connect/read timeouts, exact reads, JPEG decode, FPS smoothing, retry, and idempotent start/stop.
- [ ] **Step 6: Run** the bridge tests and existing camera tests; expect all passing.

### Task 2: Native D435 RGB Helper

**Files:**
- Create: `dex-retargeting/viewer/native/realsense_rgb_bridge.cpp`
- Create: `dex-retargeting/viewer/native/build_realsense_bridge.sh`
- Create: `dex-retargeting/viewer/native/tests/test_bridge_cli.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes CLI: `--socket PATH --width N --height N --fps N [--serial SERIAL] [--jpeg-quality N]`.
- Produces Task 1 protocol messages on the Unix socket and exits nonzero with a concrete stderr diagnostic on configuration, camera, socket, or encoding failure.

- [ ] **Step 1: Write a failing CLI smoke test** that expects `--help`, rejects an invalid JPEG quality, and verifies no socket is left after argument failure.
- [ ] **Step 2: Run the smoke test** and verify it fails because the helper/build script does not exist.
- [ ] **Step 3: Implement the helper** using librealsense `pipeline/config`, explicit `RS2_STREAM_COLOR` BGR8, turbojpeg compression, `SIGINT`/`SIGTERM` cleanup, `SO_NOSIGPIPE`, `chmod 0600`, and full-write handling.
- [ ] **Step 4: Implement the build script** using Homebrew prefixes explicitly instead of the broken `realsense2.pc` library directory; build to ignored `dex-retargeting/viewer/native/build/`.
- [ ] **Step 5: Run the CLI smoke test** and expect pass without opening camera hardware.

### Task 3: Runtime Selection, Health Metadata, And Launch Lifecycle

**Files:**
- Modify: `dex-retargeting/viewer/backend/runtime.py`
- Modify: `dex-retargeting/viewer/backend/app.py`
- Modify: `dex-retargeting/viewer/backend/tests/test_app.py`
- Modify: `dex-retargeting/viewer/backend/tests/test_camera.py`
- Create: `scripts/run_realsense_bridge.sh`
- Modify: `scripts/run_web.sh`
- Modify: `.env.example`

**Interfaces:**
- Environment: `D435_CAMERA_SOURCE=realsense|avfoundation`, `D435_BRIDGE_SOCKET`, `D435_CAMERA_ROTATION`, `D435_WIDTH`, `D435_HEIGHT`, `D435_FPS`, optional `D435_SERIAL`, and `D435_BRIDGE_EXTERNAL=1`.
- Health response adds `camera_source`, `camera_socket`, and `camera_alive`; AVFoundation retains `camera_index`.

- [ ] **Step 1: Add failing runtime/health tests** proving bridge is default, AVFoundation remains explicit fallback, and health reports source/socket/alive without requiring a real camera.
- [ ] **Step 2: Run focused tests** and confirm expected failures.
- [ ] **Step 3: Implement camera factory selection** in `ViewerRuntime` and source-agnostic health metadata.
- [ ] **Step 4: Write a shell lifecycle test** with fake `sudo`, helper, and Viewer executables, proving the helper starts first and is terminated when Viewer exits.
- [ ] **Step 5: Implement `run_realsense_bridge.sh` and update `run_web.sh`** to build, prompt once through `sudo`, wait for socket readiness, run Viewer unprivileged, and clean up with traps. `D435_BRIDGE_EXTERNAL=1` skips helper startup.
- [ ] **Step 6: Run Python and shell tests** and expect all pass.

### Task 4: Documentation And Hardware Verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Documents `brew install librealsense jpeg-turbo`, normal startup, external bridge mode, camera errors, and AVFoundation fallback without real IPs or serial numbers.

- [ ] **Step 1: Update setup and troubleshooting documentation** with exact commands and macOS privilege rationale.
- [ ] **Step 2: Run** `uv run ruff check dex-retargeting/viewer/backend`, focused pytest, Bash syntax checks, native CLI smoke test, and `git diff --check`.
- [ ] **Step 3: Start the bridge/Viewer with hardware**, confirm health reports `realsense`, capture one RGB frame, and inspect it visually.
- [ ] **Step 4: Hold a right hand in view** and verify WebSocket transitions to `TRACKING` while control remains `DISARMED`.
- [ ] **Step 5: Stop the server cleanly** only if hardware verification fails; otherwise leave Viewer running on `http://127.0.0.1:8787/` for the user.
