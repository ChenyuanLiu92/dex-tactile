# Viewer Bilingual UI Design

## Goal

Provide complete English and Simplified Chinese coverage for every user-visible Viewer string while preserving engineering identifiers in their canonical English form.

## Language Model

- Supported locales: `en` and `zh-CN`.
- English remains the default for a new browser profile.
- The selected locale is stored in local storage and restored on reload.
- A single top-bar language control switches the entire interface immediately.

## Architecture

- Add a lightweight application-owned i18n module with typed translation keys, locale dictionaries, interpolation, and an `I18nProvider`/`useI18n` API.
- Components obtain visible copy through translation keys instead of inline locale conditionals.
- Domain data keeps stable machine values; presentation helpers translate statuses, hand sides, finger names, tactile regions, and calibration point names.
- Runtime and API errors are mapped to localized UI messages at the display boundary. Protocol payloads remain unchanged.

## Translation Scope

Translate all visible labels, actions, headings, statuses, empty states, errors, tooltips, placeholders, accessibility labels, legends, and calibration instructions in:

- Application header, connection status, workspace modes, hand tabs, empty states, and notifications.
- Motion control panel and collapsible inspector.
- Tactile panel, tactile region labels, history legend, and calibration entry point.
- Device endpoint configuration dialog.
- 3D Viewer tools, coordinate-frame menu, scene labels, and tactile legend.
- Tactile calibration modal, point names, progress, and validation messages.

## Preserved Engineering Identifiers

The following remain untranslated in both locales: `J1`-`J6`, `WORLD`, `BASE / MOUNT`, `Modbus TCP`, `RH56DFTP`, `PIEZO`, `CAP`, IP addresses, ports, units, model/profile identifiers, and raw protocol values when shown as diagnostic data.

## UX Requirements

- Chinese text must fit existing controls without overlap or clipped labels.
- The language control displays the destination language: `中文` in English mode and `EN` in Chinese mode.
- Switching language must not reset device state, current workspace mode, tactile baseline, calibration progress, or camera state.
- Technical identifiers may be paired with translated descriptions where useful.

## Testing

- Unit-test locale persistence, translation lookup, interpolation, and presentation helpers.
- Add a test that fails when English and Chinese dictionaries have different keys.
- Add Playwright coverage that switches to Chinese and verifies representative strings from the header, motion panel, tactile panel, Viewer tools, configuration dialog, and calibration modal.
- Run the existing frontend unit suite, TypeScript check, production build, and existing E2E suite.

## Out of Scope

- Backend/API localization.
- Translating logs, URDF names, joint names, JSON payloads, or persisted calibration data.
- Additional locales beyond English and Simplified Chinese.
