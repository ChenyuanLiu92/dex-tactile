# Viewer Bilingual UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every user-visible Viewer string switch consistently between English and Simplified Chinese while preserving engineering identifiers.

**Architecture:** Add a dependency-free typed i18n context with complete locale dictionaries and presentation helpers. Replace component-local copy and locale conditionals with translation keys, keeping protocol and domain values unchanged.

**Tech Stack:** React 19, TypeScript, Vitest, Playwright, Vite.

## Global Constraints

- Supported locales are `en` and `zh-CN`; English is the first-run default.
- Persist the locale in local storage and switch without resetting application or 3D state.
- Keep `J1`-`J6`, `WORLD`, `BASE / MOUNT`, `Modbus TCP`, `RH56DFTP`, `PIEZO`, `CAP`, IP addresses, ports, units, model/profile identifiers, and diagnostic protocol values untranslated.
- Translate visible copy, errors, tooltips, placeholders, accessibility labels, region names, and calibration instructions.

---

### Task 1: Typed Internationalization Core

**Files:**
- Create: `inspire_visualizer/web/src/i18n/I18nProvider.tsx`
- Create: `inspire_visualizer/web/src/i18n/messages.ts`
- Test: `inspire_visualizer/web/tests/i18n.test.tsx`

**Interfaces:**
- Produces: `Locale = 'en' | 'zh-CN'`, `MessageKey`, `I18nProvider`, and `useI18n(): { locale, setLocale, toggleLocale, t }`.
- `t(key, values?)` interpolates `{name}` placeholders without rendering HTML.

- [ ] Write tests proving dictionary key parity, interpolation, first-run English, persisted Chinese restoration, and immediate switching.
- [ ] Run `npm test -- --run tests/i18n.test.tsx` and verify the missing module fails.
- [ ] Implement complete typed dictionaries and the provider using local-storage key `inspire-language`.
- [ ] Run the focused test and verify it passes.

### Task 2: Application Shell and Viewer Tools

**Files:**
- Modify: `inspire_visualizer/web/src/main.tsx`
- Modify: `inspire_visualizer/web/src/App.tsx`
- Modify: `inspire_visualizer/web/src/hand-viewer/HandScene.tsx`
- Modify: `inspire_visualizer/web/src/hand-viewer/CoordinateFrame.tsx`
- Modify: `inspire_visualizer/web/src/device-control/ResizableInspector.tsx`
- Test: `inspire_visualizer/web/tests/appI18n.test.tsx`

**Interfaces:**
- Consumes: `useI18n()` from Task 1.
- Produces: localized shell, workspace modes, connection state, empty/error states, Viewer tools, frame menu, legend, and inspector controls.

- [ ] Add a test that switches to Chinese and asserts representative shell and Viewer copy while `WORLD` and `BASE / MOUNT` remain unchanged.
- [ ] Run the focused test and verify it fails on untranslated text.
- [ ] Replace inline locale state and visible strings with typed translation calls; keep camera and workspace state local to existing components.
- [ ] Run the focused test and verify it passes.

### Task 3: Motion, Tactile, Configuration, and Calibration Surfaces

**Files:**
- Modify: `inspire_visualizer/web/src/device-control/ControlPanel.tsx`
- Modify: `inspire_visualizer/web/src/device-control/ConfigDialog.tsx`
- Modify: `inspire_visualizer/web/src/tactile/TactilePanel.tsx`
- Modify: `inspire_visualizer/web/src/tactile/CalibrationDialog.tsx`
- Modify: `inspire_visualizer/web/src/app/types.ts`
- Test: `inspire_visualizer/web/tests/componentI18n.test.tsx`

**Interfaces:**
- Consumes: `useI18n()` and translation keys from Task 1.
- Produces: localized motion controls, endpoint form, tactile telemetry, region names, calibration points, statuses, errors, and accessibility text.

- [ ] Add component tests for English and Chinese labels, status mapping, tactile region naming, configuration errors, and engineering-identifier preservation.
- [ ] Run the focused tests and verify untranslated labels fail.
- [ ] Replace component literals with translations and add presentation helpers for side, channel, region, status, and calibration-point labels.
- [ ] Run the focused tests and verify they pass.

### Task 4: Coverage Guard and Browser Verification

**Files:**
- Modify: `inspire_visualizer/web/e2e/visualizer.spec.ts`
- Modify: `inspire_visualizer/web/src/styles.css`

**Interfaces:**
- Consumes: the complete bilingual UI from Tasks 1-3.
- Produces: regression coverage for language switching and layout safety.

- [ ] Add a Playwright flow that selects Chinese and verifies shell, motion panel, tactile panel, Viewer menu, configuration dialog, and calibration modal strings.
- [ ] Ensure Chinese labels wrap or size correctly in existing buttons without changing the industrial visual direction.
- [ ] Run `npm test -- --run`, `npm run typecheck`, `npm run build`, and `npm run e2e`.
- [ ] Search TSX sources for remaining user-visible English literals; classify preserved engineering identifiers and translate every other match.

## Self-Review

- All design-spec surfaces map to Tasks 2-4.
- Translation-key parity and runtime persistence are covered in Task 1.
- Preserved engineering identifiers are asserted in Tasks 2-3.
- The plan contains no placeholders and introduces no third-party dependency.
