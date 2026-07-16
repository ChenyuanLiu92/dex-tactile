# RH56DFTP Home Pose Design

## Objective

Add a compact, approximate fist pose for placing the RH56DFTP back in its case,
and expose it through the workspace-level `../scripts/go_home.sh` command.

## Pose

The official pressure-tactile manual confirms that the built-in gesture library
contains a fist but does not identify its gesture number or six-channel values.
The implementation therefore uses an explicit, reviewable target rather than an
unknown firmware gesture:

```text
[120, 120, 120, 120, 180, 480]
```

The channel order is little finger, ring finger, middle finger, index finger,
thumb bend, and thumb rotation. The manual defines `1000` as open and `0` as
flexed for the finger angle channels, so this target forms a compact but not
fully saturated fist.

The thumb-rotation value was calibrated from the first supervised hardware run:
the mechanism settled at `479` while the original approximate `350` target could
not be reached. The target is therefore rounded to the attainable value `480`.

## Controller Behavior

`HOMING` is a distinct controller state. Home is accepted only from connected
`DISARMED`; it reads the current six-channel position, resets the adaptive motion
profile, and starts from that measured position. The existing 30 Hz profile,
position limits, speed limits, force limits, and single controller-owned Modbus
writer remain unchanged.

Home does not require camera or tracking data. It completes when all measured
channels are within the existing eight-count deadband, then holds the measured
position and returns to `DISARMED`. E-STOP can interrupt `HOMING`. A Modbus error
or a 20-second timeout stops periodic home writes and enters `FAULT`. Shutdown
holds current position when either `ARMED` or `HOMING`.

Control telemetry reports Modbus output while `HOMING`, because motion commands
are being written. The fixed home target is visible in the normal target fields.

## API and Script

`POST /api/control/home` uses the same `X-RH56-Control: operator-confirmed`
header as other protected motion transitions. It accepts no command body and
returns the controller snapshot immediately after entering `HOMING`.

`../scripts/go_home.sh` resolves the workspace and uv project roots, invokes the Home endpoint, and
polls `/api/health` until the controller reaches `DISARMED`. It defaults to
`http://127.0.0.1:8787` and supports `RH56_VIEWER_URL` for another address. It
fails with a nonzero exit code when the Viewer is unavailable, the transition is
rejected, the controller enters `FAULT`/`ESTOPPED`/`DISCONNECTED`, or the client
wait exceeds 25 seconds. It clears the inherited `VIRTUAL_ENV` before invoking
the project's uv environment and prints progress once per second. It never opens
a separate Modbus connection.

## Safety

The operator must start the Viewer first, verify the connected hand and clear its
workspace, then run the script. Home is a software position move and hold, not a
certified safety stop or torque-off. Physical power removal must remain available.

## Verification

Controller tests cover measured-position seeding, target progression, completion,
timeout, E-STOP interruption, and invalid transitions. API tests cover the
protected route. A script test uses a local fake HTTP server, so automated tests
never move the real hand. Hardware verification remains read-only unless the
operator explicitly runs `../scripts/go_home.sh`.
