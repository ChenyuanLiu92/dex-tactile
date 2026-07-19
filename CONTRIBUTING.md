# Contributing to Dex Tactile

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING.zh-CN.md)

Thank you for contributing. Dex Tactile controls physical hardware, so a change is complete only
when its behavior, verification scope, safety impact, and rollback path are clear to another
developer. This guide defines the minimum standard for every pull request.

## Before you start

1. Search existing issues and pull requests before duplicating work.
2. Use an issue or draft PR for changes that alter control behavior, data schemas, public APIs, or
   repository architecture.
3. Keep one PR focused on one outcome. Separate unrelated cleanup, dependency upgrades, and feature
   work.
4. Read the safety and privacy rules below before connecting hardware or collecting data.

For setup and hardware instructions, start with [README.md](README.md).

## Non-negotiable rules

- Never commit `.env`, `hands.json`, operator Profiles, tactile calibration, datasets, logs, real IP
  addresses, device serials, participant identity, or absolute local paths.
- Do not edit manufacturer originals in `inspire_doc/`. Put derived code or conclusions elsewhere.
- Never run more than one live Modbus writer against the same hand.
- Keep live control `DISARMED` until dry-run targets, handedness, limits, and physical clearance have
  been checked.
- Do not describe hardware as verified when only simulation, mocks, or dry-run were used.
- Preserve upstream license headers. Update [THIRD_PARTY.md](THIRD_PARTY.md) when vendored code,
  assets, or upstream revisions change.
- Never force-push `main`, rewrite shared history, or bypass review for hardware-affecting changes.

## Development setup

```bash
git clone https://github.com/ChenyuanLiu92/dex-tactile.git
cd dex-tactile

uv sync --all-groups
npm ci --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web
```

Copy local configuration from the checked-in examples. Keep real endpoints in ignored files only:

```bash
cp .env.example .env
cp inspire_visualizer/config/hands.example.json inspire_visualizer/config/hands.json
```

## Branches

Create a short-lived branch from current `main`:

```bash
git switch main
git pull --ff-only
git switch -c <type>/<short-kebab-description>
```

Use one of these prefixes:

| Prefix | Use |
| --- | --- |
| `feat/` | User-visible capability |
| `fix/` | Defect or safety correction |
| `docs/` | Documentation only |
| `test/` | Tests or test infrastructure |
| `refactor/` | Behavior-preserving code change |
| `perf/` | Measured performance improvement |
| `chore/` | Tooling, maintenance, or dependency work |

Examples: `feat/operator-profiles`, `fix/thumb-opposition-rate`, `docs/dataset-schema`.

Do not mix multiple contributors' unrelated work on one long-lived branch. Refresh from `main`
before requesting final review and resolve conflicts locally.

## Commits

Use focused commits with an imperative Conventional Commit-style subject:

```text
feat: add operator calibration profiles
fix: hold position during tracking recovery
docs: document HDF5 event semantics
test: cover Modbus ownership conflicts
```

- Keep the subject under roughly 72 characters.
- Explain *why* in the body when the safety or algorithmic reason is not obvious.
- Do not commit `WIP`, generated caches, debug captures, editor metadata, or formatting churn unrelated
  to the change.
- Update tests and documentation in the same PR as the behavior they describe.

## Engineering expectations

### Python

- Manage dependencies only through root `pyproject.toml` and `uv.lock`.
- Follow existing typing and ownership boundaries; do not add parallel device/control abstractions.
- Parse structured protocols and data with structured APIs, not ad hoc string handling.
- Add regression tests for every fixed defect and boundary tests for hardware commands.

### React and TypeScript

- Keep the unified frontend under `inspire_visualizer/web`; do not create another standalone Viewer.
- Preserve English/Chinese coverage for new user-facing text while retaining engineering identifiers.
- Verify desktop layout first, then check that compact viewports do not overflow or overlap.
- Use the existing icon library, design tokens, and interaction patterns.

### Retargeting and control

- Derive mappings from the RH56 URDF and documented six-channel order.
- Preserve target clamping, filtering, speed limits, tracking recovery hold, ARM/DISARM, E-STOP, and
  exclusive Modbus ownership unless the PR explicitly redesigns and tests them.
- Include deterministic gesture evidence for isolated finger flexion, opening, fist, thumb flexion,
  thumb opposition, four pinches, and tripod pinch when retargeting changes.
- Read the measured hand position before beginning a new live-control or positioning session.

### Tactile and data

- Preserve all 17 regions and 1,062 taxels unless a documented hardware revision changes the schema.
- Keep raw counts distinct from calibrated force; do not label values as N or Pa without calibration.
- Treat HDF5 schema changes as compatibility changes. Document migration and partial-file behavior.
- Never commit recorded participant data, even when the repository is private.

## Verification matrix

Run every gate that matches the changed surface. Record the exact commands and outcomes in the PR.

| Change | Minimum evidence |
| --- | --- |
| Documentation only | `git diff --check`; links/assets checked; privacy scan |
| Python/backend | Ruff, Pyright, root pytest, affected module tests |
| React/UI | Vitest, TypeScript, production build; Playwright for workflows/layout |
| Retargeting | Unit tests plus deterministic gesture diagnostics and dry-run matrix |
| Modbus/control | Unit tests, dry-run, failure/hold behavior, explicit hardware risk statement |
| Tactile | Complete 1,062-taxel frame, mapping tests, relevant screenshot |
| RealSense/camera | Camera tests, bridge tests when applicable, `/vision/api/health` result |
| HDF5/data | Schema tests, interruption/partial-file test, sample-file inspection |

Canonical backend gates:

```bash
uv run ruff check hand_data_collection inspire_visualizer/backend/src unified_web \
  dex-retargeting/viewer/backend \
  dex-retargeting/src/dex_retargeting/inspire_retargeting.py \
  Open-Teach/openteach/robot/inspire \
  Open-Teach/openteach/components/operators/inspire.py
uv run pyright
uv run pytest -q
uv run pytest -q dex-retargeting/tests dex-retargeting/viewer/backend/tests Open-Teach/tests
```

Canonical frontend gates:

```bash
npm test --prefix inspire_visualizer/web -- --run
npm run typecheck --prefix inspire_visualizer/web
npm run build --prefix inspire_visualizer/web
```

For browser workflows, start the unified backend first, then run:

```bash
./scripts/run_web.sh
npm run e2e --prefix inspire_visualizer/web
```

Native RealSense lifecycle checks:

```bash
bash scripts/tests/test_run_web_realsense.sh
bash dex-retargeting/viewer/native/tests/test_bridge_cli.sh
```

If a command cannot run on your platform, mark it `Not run`, explain why, and state the residual
risk. Never silently omit a relevant gate.

## Hardware validation levels

Use exactly one of these labels in the PR:

- **Not hardware tested**: software checks only; no physical conclusions.
- **Dry-run verified**: live inputs and generated targets inspected, with Modbus output disabled.
- **Hardware verified**: tested on the named hand model with physical power removal available.

For hardware verification, report the model and control path, but not IP addresses or serials. State:

- Starting pose and tested gestures/actions
- Maximum configured speed/step relevant to the change
- Tracking-loss, disconnect, and E-STOP behavior observed
- Unexpected motion, overshoot, vibration, or mechanical contact
- How to return to a known-safe release or open pose

Stop immediately on unexpected motion. Software recovery is not a substitute for physical power
removal.

## Pull requests

### Before opening

1. Re-read the diff and remove unrelated files.
2. Run `git diff --check` and the relevant verification matrix.
3. Run `git status --ignored` and confirm all local configuration/data remain ignored.
4. Check changed text, screenshots, fixtures, and logs for private information.
5. Update README, schema documentation, `.env.example`, and tests when contracts change.

### PR title

Use the same format as commits:

```text
<type>: <imperative summary>
```

Examples: `fix: preserve thumb target lead` or `docs: define contribution workflow`.

### PR description

Complete every applicable section in the repository PR template. In particular:

- Explain the user-visible or system behavior, not only the files changed.
- Identify hardware and safety impact explicitly.
- Paste exact test commands and concise results.
- Attach screenshots for visual changes and dry-run evidence for mapping/control changes.
- Describe compatibility, migration, and rollback.
- Mark unavailable evidence as `Not run` instead of deleting the section.

Open a draft PR when early design or hardware feedback is useful. Mark it ready only after self-review
and relevant local gates pass.

## Review and merge policy

A PR is ready to merge only when:

- Its scope is coherent and the PR template is complete.
- Relevant automated checks pass and omitted checks are justified.
- Review conversations are resolved.
- Public behavior, configuration, or data-contract changes are documented.
- Privacy and generated-file checks pass.
- Hardware-affecting changes have an explicit safety review and dry-run evidence; a second reviewer
  should inspect them before live testing or merge.

Reviewers prioritize correctness, physical safety, regressions, protocol/data compatibility, missing
tests, privacy, and rollback clarity. Style-only feedback should not obscure behavioral risk.

Use **squash merge by default** for a single-purpose PR. Preserve multiple commits only when their
history is intentionally useful. Delete the feature branch after merge. Never merge a draft PR or
use force merge to bypass failed checks.

## Reporting defects

Provide a minimal reproduction, expected and actual behavior, platform, hand model, control state,
and sanitized logs. Remove IPs, serials, usernames, absolute paths, and participant data. For unsafe
motion, disconnect power first and report the last known controller state and command path.
