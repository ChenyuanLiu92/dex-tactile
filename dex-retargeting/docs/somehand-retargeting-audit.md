# SomeHand Retargeting Audit

Date: 2026-07-16

Reference repository: `BotRunner64/somehand`

Audited commit: `f0a6b42e151ca10a6eec3e24c24c10cd13c40314` (`somehand` 0.3.0)

## Conclusion

The D435 Viewer does use the core SomeHand optimization formulation for the
Inspire FTP hand. It is an adaptation, not a runtime integration: the Viewer uses
the existing Inspire URDF, Pinocchio, NLopt SLSQP, and RH56DFTP channel mapping,
while SomeHand uses a separate MJCF model, MuJoCo, and SciPy SLSQP.

Keeping the adapted solver is preferable for this Viewer. In the same 60-frame
synthetic transition benchmark, its P95 solve time was 2.88 ms versus 69.27 ms for
the SomeHand reference solver. Both stayed finite and produced a clear
thumb-to-index pinch response.

## Configuration parity

The following Inspire FTP settings match SomeHand exactly:

| Feature | SomeHand | Viewer adaptation |
| --- | --- | --- |
| Segment direction constraints | 11 MediaPipe pairs | Same 11 pairs |
| Terminal direction weight | 0.9 | 0.9 |
| Thumb distance constraints | 4 thumb-to-fingertip pairs | Same 4 pairs |
| Distance weights | 2000, 1500, 1000, 800 | Same |
| Contact threshold/type | 0.04, linear | Same |
| Distance scaling | Hand-scaled | Hand-scaled |
| Thumb CMC frame | Landmarks 1, 2, 5 | Same |
| Frame weights | 2.0, 1.8 | Same |
| Landmark EMA alpha | 0.65 | 0.65 |
| SLSQP iteration limit | 60 | 60 |
| Temporal regularization | 0.001 | 0.001 |
| Output alpha | 0.92 | 0.92 |

The Viewer tracker already performs the same wrist-local preprocessing and uses
the same right-hand operator-to-robot matrix. Running SomeHand preprocessing again
inside the adapted solver would be incorrect because it would normalize the frame
twice.

## Findings and fixes

Two temporal details were missing from the adaptation:

1. SomeHand applies a second EMA to contact activations with alpha 0.3. The Viewer
   now applies this filter, while preserving SomeHand's unattenuated first frame.
2. SomeHand feeds the filtered output pose back into the next solve. The Viewer
   previously retained the unfiltered optimum as its warm start while publishing a
   filtered pose. The six independent joints and the rendered 12-joint pose now
   share one filtered state.

No SomeHand, MuJoCo, or SciPy runtime dependency was added.

## Verification results

SomeHand core/config/acceptance suite with downloaded MJCF assets:

- 63 passed.
- 1 skipped because an optional recording was absent.
- 1 failed in an unrelated LinkerHand L20Pro pinky asset alignment check. The
  downloaded model's lateral range was 0.02372 m while the repository test expects
  less than 0.001 m. Inspire FTP tests passed.

Synthetic single-pose comparison:

| Metric | SomeHand | Viewer adaptation |
| --- | ---: | ---: |
| Open thumb-index gap / hand scale | 1.630 | 1.663 |
| Pinch thumb-index gap / hand scale | 0.526 | 0.620 |
| Open mean direction cosine | 0.989 | 0.923 |
| Pinch mean direction cosine | 0.899 | 0.848 |
| Fist mean direction cosine | 0.599 | 0.605 |
| 60-frame mean solve time | 9.56 ms | 1.87 ms |
| 60-frame P95 solve time | 69.27 ms | 2.88 ms |
| 60-frame maximum solve time | 125.37 ms | 3.23 ms |

The models are not geometrically identical, so raw qpos values are not directly
comparable. Task-space distances, direction alignment, finite outputs, and timing
were used instead.

D435 smoke check while the Viewer remained disarmed:

- Capture and tracking loop: approximately 30.1 FPS.
- Observed latency: approximately 13 ms.
- Tracking state: `LOST` because no hand was in view during the check.
- Control state: `DISARMED`.
- Modbus output: `false`.

## Reference environment notes

The SomeHand source checkout does not include MJCF assets. They were downloaded
from its documented Hugging Face asset repository for the audit. Its downloader
also assumes `pip` is installed when optional download dependencies are missing;
an isolated uv environment required installing those dependencies explicitly.
Neither issue affects the Viewer runtime.

## RH56DFTP contact adaptation

Subsequent URDF reachability checks showed that copying SomeHand's absolute distance
weights did not preserve the loss balance of its MJCF model. A canonical index pinch
left the URDF thumb yaw at zero and the modeled tips about 49.9 mm apart, although a
joint-space sweep proved that the RH56 geometry could close the pair.

The Viewer now retains the SomeHand direction and CMC-frame objective while adding
an exclusive DexPilot-style contact latch:

- The nearest thumb-finger pair locks below 30 mm and releases above 50 mm.
- Only the locked pair receives a distance objective, projected to 5 mm in robot
  space with a common weight of 2000.
- Contact activation retains the 0.3 EMA; output filtering and the physical
  controller's bounded motion profile are unchanged.
- Tracking loss clears contact and landmark history without discarding the retained
  robot pose.

The standard index-pinch regression reaches at most 15 mm after settling while
leaving the non-target fingers open. The 60-frame pinch/release benchmark measured
2.01 ms mean, 4.26 ms P95, and 6.90 ms maximum solve time. Ring and pinky cannot
reach the same absolute gap in this six-drive URDF, so their acceptance checks use
relative closure from each pair's open-pose baseline.
