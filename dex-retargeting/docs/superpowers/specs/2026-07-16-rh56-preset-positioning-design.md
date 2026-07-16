# RH56DFTP Preset Positioning Design

## Objective

Replace the Home-specific motion state and command with a reusable fixed-preset
positioning system. Operators use one workspace-level script with a preset name:

```shell
./scripts/go_pose.sh home
./scripts/go_pose.sh open
```

The system supports only reviewed presets. It does not accept arbitrary six-channel
targets from the command line or HTTP API.

## Presets

The controller owns the immutable preset table:

```text
HOME = [120, 120, 120, 120, 180, 480]
OPEN = [1000, 1000, 1000, 1000, 1000, 1000]
```

The order is little finger, ring finger, middle finger, index finger, thumb bend,
and thumb rotation. `HOME` retains the thumb-rotation value calibrated during the
first supervised hardware run. `OPEN` follows the official manual's definition of
`1000` as the fully open angle value.

## Controller Architecture

`ControlState.HOMING` is replaced by `ControlState.POSITIONING`. The controller
exposes `move_to_preset(preset, now=None)` as the single implementation and keeps
small `home()` and `open()` entry methods for the fixed HTTP routes. A `Preset`
enum prevents unvalidated names from reaching the motion layer.

Positioning is accepted only from connected `DISARMED`. It reads the six actual
positions, resets `AdaptiveMotion`, records the selected preset and start time,
and enters `POSITIONING` without writing during the transition call. The existing
30 Hz worker then advances all channels toward the immutable target with the
existing deadband, step, speed, force, and position limits.

When every measured channel is within the eight-count deadband, the controller
holds the measured position and returns to `DISARMED`. A Modbus error or a
20-second timeout holds current position and enters `FAULT`. E-STOP and shutdown
interrupt `POSITIONING` through the existing hold path. Vision tracking is not
required and cannot alter a preset target.

`ControlSnapshot` adds `preset`, containing `HOME` or `OPEN` only while a preset
move is active. `modbus_output` is true for `ARMED` and `POSITIONING`. The target
field continues to expose the selected six-channel preset.

## API

The guarded routes remain explicit and body-free:

- `POST /api/control/home`
- `POST /api/control/open`

Both require `X-RH56-Control: operator-confirmed`. They call the corresponding
fixed controller entry method and return the complete control snapshot. There is
no generic `/target`, `/write`, or request-body preset route. Invalid transitions
return HTTP 409.

Health and WebSocket telemetry report `POSITIONING` as active Modbus output. The
React control-state type accepts `POSITIONING`, and the workbench continues to
offer immediate E-STOP while a preset move is active.

## Command-Line Interface

The root `scripts/` directory contains one operator command:

```text
go_pose.sh home
go_pose.sh open
```

The existing `go_home.sh` is removed. `go_pose.sh` validates exactly one lowercase
argument, maps it to the matching fixed API route, clears inherited `VIRTUAL_ENV`,
and runs its HTTP client through the `dex-retargeting` uv project. Missing or
unsupported arguments print `Usage: ./scripts/go_pose.sh {home|open}` and exit
nonzero.

The Viewer is an optional transport. When its health endpoint is reachable,
connected, and `DISARMED`, the script uses the guarded API. When the local Viewer
port explicitly refuses the connection, the script creates a transient
`VisionHandController(start_worker=False)`, connects directly to the RH56 Modbus
endpoint, reads actual position, and runs the same bounded positioning ticks.
Timeouts or malformed responses from a present Viewer block direct fallback to
avoid two controllers writing the device concurrently.

After the guarded POST succeeds, the Viewer path validates that the response is
`POSITIONING`, prints the server-returned six-channel target, and polls health.
It prints progress once per second, succeeds only after `DISARMED`, and fails on
`FAULT`, `ESTOPPED`, `DISCONNECTED`, unexpected state, connection loss, or a
25-second client timeout. Stopping the terminal client is not an E-STOP; terminal
copy and documentation state that the workbench E-STOP or physical power removal
must be used for an unsafe move. In direct mode, `Ctrl+C` holds measured position
before closing Modbus; physical power removal remains the final safety action.

## Testing and Verification

Controller tests cover both immutable targets, measured-position seeding,
independent progression, completion, timeout, E-STOP, shutdown, and rejection
outside `DISARMED`. API tests cover authentication and both body-free routes while
confirming arbitrary write routes remain absent.

Script tests use a local fake HTTP server to cover `home`, `open`, invalid usage,
the required control header, progress output, successful completion, rejected
transitions, and terminal faults. Automated verification never calls either
motion route on the real Viewer. After restart, the live check is read-only and
must leave the connected hand in `DISARMED` with `modbus_output=false`.

## Safety

Preset positioning is software-controlled motion and hold, not a certified safety
stop or torque-off. The operator must clear the hand's workspace and retain access
to the workbench E-STOP and physical power removal before running either preset.
