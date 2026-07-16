# Inspire RH56DFTP Aggressive Motion Design

## Goal

Reduce the perceived lag between Quest hand tracking and the physical RH56DFTP
while retaining the existing per-channel adaptive controller and safety behavior.

## Control Profile

- Control frequency: 30 Hz
- Error thresholds: `[40, 180]`
- Maximum steps per frame: `[20, 60, 120]`
- Motor speeds: `[100, 260, 450]`
- Deadband: 8 counts
- Threshold hysteresis: 10 counts
- Per-channel force: `[220, 120, 120, 120, 220, 220]`

At the high band, the command can advance by up to 3600 counts per second. The
controller continues to decelerate independently per channel as each actuator
approaches its target.

## Integration

`InspireHandOperator` will accept a configurable control frequency and default to
30 Hz in the Inspire robot configuration. Diagnostic logging remains near 5 Hz by
deriving its interval from the control frequency instead of using a fixed frame
count.

The retargeter retains the existing error-band and hysteresis implementation; only
the configured step and speed values change. The Modbus driver continues to cache
unchanged speed and force writes.

## Safety

- Keep all actuator targets within `0..1000`.
- Send no motion command while paused or when tracking data is missing or invalid.
- Do not increase force limits.
- Keep physical-hand operation opt-in through `dry_run=false`.
- Do not automatically home the hand on startup or tracking loss.

## Verification

- Unit-test the aggressive step and speed values for all three error bands.
- Verify the operator timer runs at 30 Hz and logs every sixth enabled frame.
- Run the full Inspire test suite.
- Run a synthetic dry-run showing independent low, medium, and high channel output.
- Do not drive the physical hand during automated verification.
