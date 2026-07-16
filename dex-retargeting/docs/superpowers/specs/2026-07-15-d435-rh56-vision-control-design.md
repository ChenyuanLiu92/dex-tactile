# D435 RH56DFTP Vision Control Design

## Objective

Extend the standalone D435 vision viewer from dry-run preview to guarded RH56DFTP
position control. The controller accepts only the existing right-hand vision
pipeline, starts from the robot's measured position, and uses the same aggressive
motion profile as the current Open-Teach configuration.

## Scope

The first release controls one RH56DFTP at `192.0.2.10:6000` over Modbus TCP.
It writes six position, speed, and force channels. It does not control a robot arm,
tactile feedback loop, Quest input, arbitrary Modbus registers, or multiple hands.

## Architecture

The implementation lives under `viewer/backend/control/` and remains independent
from the sibling Open-Teach repository:

- `driver.py` owns the pymodbus connection and the four approved register blocks:
  `ANGLE_SET=1486`, `FORCE_SET=1498`, `SPEED_SET=1522`, and `ANGLE_ACT=1546`.
- `motion.py` converts raw six-channel vision targets into bounded commands using
  the approved deadband, hysteresis, error bands, step limits, and speeds.
- `controller.py` owns connection and safety state, runs the 30 Hz write loop, and
  is the only component allowed to call the driver write methods.
- `runtime.py` supplies immutable tracking snapshots to the controller. HTTP
  handlers request state transitions but never write registers directly.

The driver uses pymodbus 2.5.3, matching the official hand example and the current
Open-Teach driver. Its dependency is installed through the uv `viewer` extra.

## Control State Machine

States are `DISCONNECTED`, `DISARMED`, `ARMING`, `ARMED`, `HOLDING`, `ESTOPPED`,
and `FAULT`.

- Startup attempts a connection and enters `DISARMED` after a valid six-channel
  `ANGLE_ACT` read. Startup and reconnect never write a motion command.
- ARM is accepted only from `DISARMED`, with a connected driver and a fresh
  `TRACKING` snapshot. ARM reads `ANGLE_ACT` again and initializes the commanded
  position from that measurement before entering `ARMED`.
- While `ARMED`, only fresh `TRACKING` snapshots can produce commands. The loop
  runs at 30 Hz and advances independently per channel.
- DISARM reads actual position, writes it back as the hold target, then enters
  `DISARMED` and stops periodic writes.
- Tracking loss, wrong hand, camera error, stale telemetry, or controller shutdown
  invokes the same hold-current-position operation and automatically disarms.
- E-STOP reads actual position, writes it once as the hold target, stops periodic
  writes, and enters the latched `ESTOPPED` state. If the read fails, periodic
  writes still stop and the state remains latched with the error recorded.
- RESET is accepted only from `ESTOPPED`. It performs a connection/read health
  check and returns to `DISARMED`; it never arms automatically.
- Any Modbus read/write failure while armed stops periodic writes and enters
  `FAULT`. Recovery requires an explicit reconnect/reset action and a new ARM.

Holding means commanding the measured actuator positions. The RH56DFTP interface
does not expose a hardware torque-off operation, so the UI must not describe this
software action as a certified safety stop.

## Motion Profile

All target, actual, and command positions are validated and clipped to `0..1000`.
Per-channel absolute error selects a motion band with hysteresis:

- deadband: `8`
- error thresholds: `[40, 180]`
- maximum steps per 30 Hz cycle: `[20, 60, 120]`
- speed register values: `[100, 260, 450]`
- hysteresis: `10`
- force values: `[220, 120, 120, 120, 220, 220]`

Inside the deadband, the previous commanded position is retained. Outside it, the
command advances toward the vision target by no more than the active band's step.
ARM always seeds this algorithm from the latest measured `ANGLE_ACT`, preventing a
command jump to the currently observed hand pose.

## Freshness and Failure Rules

A vision target is fresh when its status is `TRACKING` and its publish timestamp is
no more than 150 ms old. A single stale/non-tracking control cycle triggers hold
and automatic disarm; control does not wait for MediaPipe's later `LOST` state.
Targets must contain exactly six finite channel values.

The controller records connection state, actual positions, raw targets, commanded
positions, speed values, last write timestamp, and the latest error. These values
are included in WebSocket telemetry but do not alter the existing tracking payload.

## API

The guarded command endpoints are:

- `POST /api/control/arm`
- `POST /api/control/disarm`
- `POST /api/control/estop`
- `POST /api/control/reset`
- `POST /api/control/reconnect`

Every endpoint returns the complete control state. Invalid transitions return HTTP
409. Connection or device failures return a non-success status and preserve the
latched controller state. There is no endpoint for arbitrary targets, speed values,
force values, or register addresses.

`GET /api/health` and `/api/ws` include the live control state. The previous
`dry_run` and `modbus_output` fields are replaced by accurate state values once the
controller is present.

## Workbench Interaction

The top safety strip always displays the current control state and connection.
ARM opens a confirmation modal showing device address, measured positions, current
vision targets, and the fact that software hold is not a hardware emergency stop.
Confirmation is disabled unless the device is connected and right-hand tracking is
fresh.

While armed, the normal DISARM action remains available. E-STOP is a dedicated red
button that does not require a confirmation dialog. `ESTOPPED` presents only RESET;
`FAULT` presents reconnect. The telemetry rail displays actual position, sent
position, current speed band, and last successful write age without resizing the
workbench.

## Testing and Verification

Unit tests use a fake Modbus client and fake clock to cover register addresses,
validation, current-position ARM seeding, all motion bands, hysteresis, target
clipping, invalid transitions, stale tracking auto-disarm, hold-on-disarm, latched
E-STOP, and write failure to `FAULT`.

FastAPI tests cover all guarded transitions and ensure no arbitrary write route is
exposed. Frontend tests cover the modal, disabled ARM conditions, E-STOP, RESET,
FAULT, and bilingual-independent English control labels.

Hardware verification proceeds in this order: connectivity/read-only check,
DISARMED observation, ARM with the human pose matched to actual position, one
finger at low displacement, six-channel bounded motion, tracking-loss hold,
DISARM, E-STOP latch, and RESET. The physical test area must remain clear and the
operator must retain access to power removal because software hold is not a
certified emergency stop.
