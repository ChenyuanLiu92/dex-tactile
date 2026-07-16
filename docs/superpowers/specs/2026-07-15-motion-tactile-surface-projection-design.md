# Motion and Tactile Surface Projection Design

## Scope

Add a third `Motion + Tactile` workspace mode and replace floating rectangular tactile planes with heat-map geometry projected onto the RH56DFTP URDF visual meshes. Device discovery, Modbus decoding, region IDs, taxel ordering, calibration, and color scaling remain unchanged.

## Workspace Modes

- `Motion` displays the white live pose and the amber target pose when they differ.
- `Tactile` displays the white live pose and the tactile heat map. The robot material remains dimmed to make the heat map legible.
- `Motion + Tactile` displays the white live pose, amber target pose, and tactile heat map together. The inspector keeps the motion controls so an operator can command a pose while observing contact.
- The heat legend is visible in both modes that contain tactile data.

The mode type is shared by `App`, `HandScene`, and `HandRobot` so rendering behavior is derived from one state rather than duplicated UI conditions.

## Surface Projection

Each of the 17 tactile regions keeps its official row and column dimensions and remains attached to its existing URDF link. The layout definition changes from a render plane transform to a projection specification:

- a local rectangular sampling area,
- a side-aware local projection direction,
- a maximum ray distance,
- and a small surface offset.

For every grid vertex, the frontend casts a ray through the relevant link's visual mesh in link-local coordinates. Only meshes whose nearest URDF link ancestor is the target link participate, so child-link geometry cannot capture the ray. The nearest intersection supplies the vertex position and triangle normal. The final vertex is moved exactly `0.15 mm` along the outward normal to avoid z-fighting. UV coordinates preserve the official row-major taxel layout.

Projection runs once after a URDF model is loaded, not for every tactile frame. Joint motion remains inexpensive because the generated geometry is parented to the same link and inherits its transform.

The sampling rectangles use STL bounds and the official sensor-location diagram as anchors. In particular, distal end patches use the actual distal mesh boundary rather than the current approximate finger-length constants.

## Geometry and Rendering

Each region renders as one indexed `BufferGeometry`, keeping the projected overlay to at most 17 draw calls per hand. Grid vertices are shared inside a region. A texture continues to carry live taxel colors, so a tactile update modifies texture bytes only and does not rebuild geometry.

If a vertex ray misses the mesh, the projector retries from the opposite side. If both rays miss, it uses the nearest projected neighboring vertex where available; otherwise it falls back to the original sampling point. A region remains visible even when a small boundary portion cannot be projected.

Pointer selection uses interpolated geometry UV coordinates, preserving the existing row and column selection behavior.

## Data Correctness

The backend region order remains:

1. Little, ring, middle, and index: `3x3` tip end, `12x8` fingertip, `10x8` pad.
2. Thumb: `3x3` tip end, `12x8` fingertip, `3x3` middle, `12x8` pad.
3. Palm: `8x14`.

This matches the official pressure-resistive manual and totals 1062 taxels. Finger regions remain row-major. The existing palm column-major-to-row-major conversion remains unchanged.

## Testing

- Unit-test mode predicates so combined mode enables both target-pose and tactile rendering.
- Unit-test projection against known Three.js geometry, including surface placement, normal offset, UV retention, and miss fallback.
- Extend layout tests to verify all projection directions point from outside toward the intended link surface and all 1062 taxels remain mapped.
- Extend app tests for the third mode and its motion inspector behavior.
- Extend Playwright coverage to render the combined mode, verify heat-map pixels, and capture a desktop screenshot for visual inspection.
- Run frontend unit tests, TypeScript checks, production build, and Playwright tests before completion.

## Non-Goals

- No backend protocol or Modbus register changes.
- No tactile-force calibration model beyond the existing baseline and display scaling.
- No authored sensor CAD meshes.
- No mobile-first redesign.
