# D435 Vision Retargeting Viewer Design

## Goal

Build a standalone local web viewer inside `dex-retargeting` that uses one Intel
RealSense D435 RGB stream to track a right human hand, retarget it to the Inspire
right-hand URDF, and display 21 landmarks, 12 robot joints, and six estimated
RH56DFTP actuator channels. The first release is visualization-only and must not
contain a Modbus output path.

## Scope

The viewer includes:

- D435 RGB video from AVFoundation camera index 0.
- MediaPipe right-hand tracking with 21 landmarks.
- Inspire right-hand vector retargeting.
- A live Three.js rendering of the existing Inspire right-hand URDF and GLB meshes.
- Twelve retargeted URDF joint values.
- Six estimated RH56DFTP actuator values in physical Modbus channel order.
- Tracking status, handedness confidence, processing FPS, and capture-to-publish latency.

Depth, tactile sensing, Quest input, physical-hand feedback, calibration, recording,
and Modbus output are outside this release.

## Directory Structure

```text
viewer/
├── backend/
│   ├── __init__.py
│   ├── app.py
│   ├── camera.py
│   ├── tracking.py
│   ├── retargeting.py
│   ├── state.py
│   └── tests/
└── web/
    ├── src/
    │   ├── camera/
    │   ├── scene/
    │   ├── telemetry/
    │   └── App.tsx
    ├── package.json
    └── vite.config.ts
```

The Python backend remains in the top-level `viewer` package so all viewer code is
isolated from the core optimizer. The frontend is an independent Vite application.

## Backend Architecture

`camera.py` owns one OpenCV AVFoundation capture thread configured for camera index
0 at 1280 by 720 and a requested 30 FPS. It stores only the latest frame; unprocessed
frames are replaced rather than queued.

`tracking.py` horizontally mirrors each frame and runs the existing MediaPipe legacy
Hands detector on a 640 by 360 copy. It accepts only the right hand and returns
normalized 2D landmarks, MANO-oriented 3D landmarks, handedness confidence, and the
tracking state.

`retargeting.py` builds the Inspire right-hand vector retargeter from the repository
configuration and overrides `low_pass_alpha` to 0.5. It converts valid 3D landmarks
to a 12-joint pose and computes six estimated actuator counts.

`state.py` provides a thread-safe immutable latest snapshot shared by the camera,
tracking, MJPEG, and WebSocket paths. Each tracking snapshot includes a monotonic
sequence number and timestamps used to compute latency.

`app.py` owns process lifecycle and exposes:

- `GET /api/health`
- `GET /api/video.mjpg`
- `WS /api/ws`
- `GET /assets/...` for the right-hand URDF and visual meshes
- the built frontend in production mode

## Tracking States

- `STARTING`: camera startup is in progress.
- `SEARCHING`: no hand is detected.
- `WRONG_HAND`: a left hand is detected.
- `TRACKING`: a valid right hand is producing landmarks and targets.
- `LOST`: a previously tracked right hand is no longer present.
- `CAMERA_ERROR`: the D435 stream cannot be opened or read.

Only `TRACKING` snapshots contain robot joint and actuator targets. All other states
publish null targets immediately; stale targets are never held on screen.

## Twelve-to-Six Mapping

All robot joints are addressed by name. Each joint is normalized using its URDF lower
and upper limit and clipped to 0 through 1. A normalized flexion of zero maps to count
1000 and one maps to count 0.

The actuator output order is:

```text
[pinky, ring, middle, index, thumb bend, thumb rotation]
```

Finger channels use the mean normalized flexion of their proximal and intermediate
joints. Thumb bend uses the mean normalized flexion of
`thumb_proximal_pitch_joint`, `thumb_intermediate_joint`, and
`thumb_distal_joint`. Thumb rotation uses `thumb_proximal_yaw_joint`.

These values are labeled `ESTIMATED / DRY RUN`; they are not treated as calibrated
physical commands.

## Web Application

The frontend uses React, TypeScript, Three.js, `urdf-loader`, and GLTFLoader. It
displays the MJPEG stream below a canvas overlay driven by normalized WebSocket
landmarks. The Three.js scene loads the repository's right-hand URDF and GLB meshes,
then applies joint values by name.

The desktop workbench has three persistent columns: a large RGB tracking view, the
Inspire 3D model, and telemetry containing tracking metrics, 12 joints, and six
estimated channels. It uses a charcoal background, cold-white model, amber tracking
accents, red error states, restrained status animations, and no tactile panel.

`DRY RUN` and `NO MODBUS OUTPUT` remain visible in both the header and footer.

## Safety Constraints

- Viewer code must not import `pymodbus`.
- Viewer code must not contain the physical hand IP or TCP port 6000.
- The backend exposes no actuator-write route.
- Non-tracking states clear all target data.
- Camera shutdown releases the AVFoundation device cleanly.

## Verification

Backend tests cover actuator mapping, right-hand enforcement, tracking-loss clearing,
snapshot serialization, health, MJPEG, WebSocket schema, and static URDF assets.

Frontend tests cover connection states, the 21-landmark overlay, 12 joint values, six
estimated channels, and error states. Playwright checks 1440 by 900 and 1920 by 1080
layouts, verifies the 3D canvas is nonblank, and checks for overlap.

An actual D435 smoke test opens camera index 0 and runs for at least 30 seconds. A
repository scan verifies that `viewer/` contains no `pymodbus`, physical hand IP, or
port 6000 references.
