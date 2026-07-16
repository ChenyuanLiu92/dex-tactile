# Motion and Tactile Surface Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a combined motion-and-tactile workspace and project all RH56DFTP tactile heat-map regions onto their real URDF link meshes.

**Architecture:** A shared workspace-mode module controls target-pose and tactile visibility. A pure Three.js projection module converts each tactile sampling rectangle into indexed link-local geometry once after model load; live frames continue updating textures only.

**Tech Stack:** React 19, TypeScript, React Three Fiber, Three.js, URDF Loader, Vitest, Testing Library, Playwright.

## Global Constraints

- Keep the official 17-region, 1062-taxel protocol unchanged.
- Offset projected vertices exactly `0.15 mm` along the outward triangle normal.
- Project only against visual meshes owned by the target URDF link.
- Keep the interface in English and preserve the existing dark industrial style.
- Do not add runtime dependencies.
- This workspace is not a Git repository, so commit steps are intentionally omitted.

---

### Task 1: Shared Workspace Mode

**Files:**
- Create: `inspire_visualizer/web/src/app/workspaceMode.ts`
- Create: `inspire_visualizer/web/tests/workspaceMode.test.ts`
- Modify: `inspire_visualizer/web/src/App.tsx`
- Modify: `inspire_visualizer/web/src/hand-viewer/HandScene.tsx`
- Modify: `inspire_visualizer/web/src/hand-viewer/HandRobot.tsx`

**Interfaces:**
- Produces: `WorkspaceMode = 'motion' | 'tactile' | 'combined'`
- Produces: `showsTargetPose(mode): boolean`
- Produces: `showsTactile(mode): boolean`

- [ ] Write tests asserting motion shows only a target, tactile shows only heat, and combined shows both.
- [ ] Run `npm test -- workspaceMode.test.ts` and verify failure because the module does not exist.
- [ ] Add the type and predicates, then replace component-local mode unions and string checks.
- [ ] Add a `Motion + Tactile` segmented-control button. Combined mode uses `ControlPanel`, renders the target ghost and tactile overlay, dims the live mesh, and shows the heat legend.
- [ ] Extend `App.test.tsx` to select the combined button and verify the motion inspector remains visible.
- [ ] Run `npm test -- workspaceMode.test.ts App.test.tsx` and verify all tests pass.

### Task 2: Link-Local Surface Projection

**Files:**
- Create: `inspire_visualizer/web/src/tactile/surfaceProjection.ts`
- Create: `inspire_visualizer/web/tests/surfaceProjection.test.ts`
- Modify: `inspire_visualizer/web/src/tactile/layout.ts`
- Modify: `inspire_visualizer/web/tests/tactileLayout.test.ts`

**Interfaces:**
- Extends `TactilePatchLayout` with `projectionDirection: [number, number, number]` and `projectionDistance: number`.
- Produces: `projectPatchToSurface(link, patch, rows, columns, surfaceOffset?): { geometry: BufferGeometry; projectedVertices: number }`.
- Produces: `projectedCellGeometry(geometry, row, column, columns): BufferGeometry`.

- [ ] Add a BoxGeometry test with a sampling plane at `z=2` and rays in `-z`; assert all generated vertices lie at `z=1.00015`, UV row zero lies at `v=1`, and the expected vertex count is generated.
- [ ] Add tests that nested child-link meshes are excluded and a complete miss retains finite fallback geometry.
- [ ] Run `npm test -- surfaceProjection.test.ts` and verify failure because the projection module does not exist.
- [ ] Implement owned-mesh collection, local-to-world ray conversion, double-sided nearest-hit raycasting, local normal conversion, outward-normal correction, indexed grid construction, UVs, and miss fallback.
- [ ] Replace approximate distal endpoints with values derived from the shipped STL bounds and add side-aware inward projection directions for fingertip, thumb, pad, and palm surfaces.
- [ ] Extend layout tests to assert every patch has a non-zero normalized projection direction, positive projection distance, and the unchanged 1062-taxel total.
- [ ] Run `npm test -- surfaceProjection.test.ts tactileLayout.test.ts` and verify all tests pass.

### Task 3: Projected Tactile Rendering

**Files:**
- Modify: `inspire_visualizer/web/src/tactile/TactileOverlay.tsx`
- Modify: `inspire_visualizer/web/e2e/visualizer.spec.ts`

**Interfaces:**
- Consumes: `projectPatchToSurface` and `projectedCellGeometry` from Task 2.
- Preserves: existing `TactileSelection`, texture updates, heat styles, baseline, threshold, and scale behavior.

- [ ] Update `TactilePatch` to receive its URDF link, memoize projected geometry, render the texture on that geometry, and dispose generated geometries and textures.
- [ ] Replace the flat selected-taxel plane with geometry copied from the selected projected cell.
- [ ] Keep UV pointer selection unchanged so the official row and column mapping is preserved.
- [ ] Extend Playwright setup to select `Motion + Tactile`, assert `data-workspace-mode="combined"`, verify the motion inspector and heat legend, and capture a desktop screenshot.
- [ ] Run `npm run typecheck`, `npm test`, and `npm run build`; require zero errors.
- [ ] Run `npm run e2e`; inspect the projected overlay screenshot for floating patches, over-coverage, blank canvas, and UI overlap.

### Task 4: Final Verification

**Files:**
- Modify only files required by defects found during verification.

- [ ] Compare the projected left-hand screenshot with the official sensor-location diagram: fingertip, tip-end, proximal pad, thumb middle, thumb pad, and palm must occupy the correct physical surfaces.
- [ ] Confirm the combined mode shows white live pose, amber target pose when different, and tactile heat simultaneously.
- [ ] Re-run `npm test`, `npm run typecheck`, `npm run build`, and `npm run e2e` after any correction.
- [ ] Report exact verification commands and any remaining limitation caused by the URDF mesh or missing sensor CAD.
