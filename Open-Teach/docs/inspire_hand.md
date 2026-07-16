# Inspire RH56DFTP setup

This adapter routes the Quest right-hand keypoint stream through the same
URDF-constrained optimizer used by the D435 dex-retargeting viewer. The six
RH56DFTP actuator channels remain in this order:

`little, ring, middle, index, thumb bend, thumb rotation`

## Network

- Computer/Open-Teach host on the Quest network: `OPENTEACH_HOST`
- Inspire right hand: `RH56_HOST:RH56_PORT`
- Quest and computer must be reachable on the same network.
- In the Open-Teach Quest app, enter the current value of `OPENTEACH_HOST`.

Set these values in the root `.env` file. The committed configuration contains only
RFC 5737 documentation addresses and reads the real values from the environment.

## Install with UV

From the Dex Tactile repository root:

```bash
uv sync --all-groups
```

## Safe dry run

The checked-in configuration has `dry_run: true`. It receives Quest data and prints six target values but never connects to or writes to the hand.

```bash
./scripts/run_openteach.sh
```

Use the Open-Teach pause/continue gesture in the Quest app. Commands are only generated while the app publishes `Continue`.

The checked-in `retargeting.backend: dex` path performs:

1. Quest 24-point skeleton to MediaPipe 21-point topology conversion.
2. Wrist-relative MANO frame alignment shared with the D435 pipeline.
3. RH56 URDF optimization with segment, thumb-frame and pinch-contact constraints.
4. Open-Teach adaptive step and speed limiting before any Modbus command.

Set `retargeting.backend: heuristic` only when comparing against the legacy
finger-bend ratio mapper.

## Enable the physical hand

First stop the web visualizer backend so that two processes do not write to the same Modbus device. Verify the hand is open and unobstructed, then run:

```bash
./scripts/run_openteach.sh --live \
  robot.operators.0.robot.log_commands=true
```

Keep an emergency stop or power disconnect within reach. The default force limits are
`[220, 120, 120, 120, 220, 220]` in Inspire channel order. These values account for
the higher measured force needed to move the pinky and thumb channels.

## Retargeting calibration

The dex backend shares `dex-retargeting/viewer/config/retargeting-calibration.json`
with the D435 viewer. The legacy bend and thumb bounds remain in the YAML only for
the optional `heuristic` backend.

Adaptive motion runs at 30 Hz and independently selects a command step and motor speed
for each channel from the current position error:

| Absolute error | Maximum step/frame | Speed |
| --- | ---: | ---: |
| `0..8` | hold | current low-speed band |
| `9..40` | `20` | `100` |
| `41..180` | `60` | `260` |
| `181..1000` | `120` | `450` |

A 10-count hysteresis around the 40 and 180 thresholds prevents rapid speed switching.
Tune `adaptive_motion.max_steps` first if the physical hand leads or lags the operator;
tune `adaptive_motion.speeds` only after confirming the step response. The legacy
`max_step` remains available when adaptive motion is disabled.

This is an aggressive profile. Keep the hand unobstructed during initial physical
testing and reduce `max_steps` before increasing force if any channel overshoots.
