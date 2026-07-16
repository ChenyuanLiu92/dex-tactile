# macOS RealSense RGB Bridge Design

## Objective

Feed the D435 RGB stream to the vision Viewer reliably on macOS without using
AVFoundation camera indexes and without running the Viewer or robot controller
as root.

## Constraints

- macOS 12+ requires elevated privileges for direct librealsense USB access.
- The phone Continuity Camera can reorder AVFoundation indexes.
- The robot control process must remain unprivileged.
- A missing bridge, unplugged camera, malformed frame, or stale stream must
  produce an explicit camera error and no Modbus motion.
- The first implementation needs RGB only. Depth is outside this scope.

## Architecture

### Privileged capture helper

A small C++ executable links against Homebrew `librealsense2`. It selects a
RealSense device, enables `RS2_STREAM_COLOR` at 1280x720 and 30 FPS, JPEG-encodes
each BGR frame, and publishes it through a Unix domain socket under `/tmp`.

The helper owns no robot configuration and imports no Viewer or Modbus code. It
runs only for the lifetime of the launch script and removes its socket on exit.
The user enters a macOS password once when launching it with `sudo`.

### Frame protocol

Each message uses a fixed network-byte-order header followed by JPEG bytes:

- magic and protocol version
- monotonically increasing sequence number
- capture timestamp in nanoseconds
- JPEG payload length

The payload has a strict maximum size. Invalid magic, unsupported versions,
oversized payloads, truncated reads, and stale frames close the connection.

### Unprivileged Viewer client

A Python camera worker connects to the Unix socket, decodes JPEG into BGR,
applies the existing rotation and mirror transform, and publishes
`FramePacket`s through `LatestFrameStore`. It reconnects after transient bridge
disconnects but reports `CAMERA_ERROR` when no fresh frame arrives within the
configured timeout.

The existing AVFoundation worker remains available as an explicit fallback for
non-RealSense webcams. RealSense bridge mode is the default for this project.

## Startup And Shutdown

`scripts/run_web.sh` loads `.env`, builds the helper when its source is newer,
starts it with `sudo`, waits for the socket to become ready, then starts the
ordinary `uv run` Viewer process. Shell traps stop both processes and remove the
socket on Ctrl+C or failure.

An environment switch allows starting only the Viewer when a bridge is already
running. Camera source, socket path, rotation, resolution, FPS, and optional
RealSense serial are configurable without storing a real serial in tracked
files.

## Safety And Errors

- Only the RGB helper receives elevated privileges.
- The helper accepts no commands over the socket.
- Socket permissions allow only the invoking user to connect.
- Camera loss updates the Viewer to `CAMERA_ERROR`; it never fabricates tracking.
- Existing controller tracking-loss behavior remains authoritative and the
  launch script does not ARM the hand.
- The health endpoint reports camera source and bridge state for diagnosis.

## Verification

- Python unit tests cover protocol parsing, fragmented reads, invalid headers,
  stale connections, reconnect behavior, and health metadata.
- A native helper smoke test verifies compilation and `--help` without opening
  hardware.
- Manual hardware verification checks that the frame is D435 RGB, a right hand
  reaches `TRACKING`, unplugging the camera reports `CAMERA_ERROR`, and control
  remains `DISARMED` throughout.

## Out Of Scope

- Depth streaming, RGB-depth alignment, point clouds, and recording.
- Passwordless sudo or a persistent LaunchDaemon.
- Supporting multiple simultaneous D435 devices beyond optional serial
  selection.
