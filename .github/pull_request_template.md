<!--
Read CONTRIBUTING.md (English) or CONTRIBUTING.zh-CN.md (中文) before submitting.
Keep every section. Use "Not applicable" or "Not run" with a reason when needed.
Do not include real IPs, serials, usernames, absolute paths, or participant data.
-->

## Summary / 变更摘要

<!-- What behavior or outcome changes? Keep this to 2-5 concrete bullets. -->

-

## Scope / 改动范围

<!-- Name the affected subsystem and important files. State what is intentionally out of scope. -->

Affected subsystem:

Out of scope:

## Safety and hardware impact / 安全与硬件影响

Hardware validation level (select one):

- [ ] Not hardware tested / 未进行真机测试
- [ ] Dry-run verified; Modbus output disabled / 已完成 dry-run，未启用 Modbus 输出
- [ ] Hardware verified with physical power removal available / 已完成真机测试并保持物理断电可触达

Hand model (no serial/IP):

Control path (`D435`, `Open-Teach`, `pose script`, `none`):

Failure mode and worst credible motion:

Tracking-loss, disconnect, and E-STOP behavior:

Safe rollback or release procedure:

## Validation / 验证

<!-- Paste exact commands and concise outcomes. Never write only "tests pass". -->

```text
Command:
Result:
```

Not-run checks and reason:

## Dry-run or physical evidence / Dry-run 或真机证据

<!-- For retargeting/control: include tested gestures, starting pose, limits, and anomalies. -->

Starting pose:

Tested gestures/actions:

Relevant maximum speed/step:

Observed overshoot, vibration, unexpected contact, or motion:

## Visual evidence / 视觉证据

<!-- Required for UI, URDF visualization, tactile mapping, and calibration interaction changes. -->

Before:

After:

## Compatibility and data / 兼容性与数据

- [ ] No public API, configuration, protocol, or HDF5 schema change
- [ ] Migration/backward compatibility is documented below
- [ ] Tactile changes preserve or explicitly version the 17-region, 1,062-taxel contract

Compatibility notes:

## Privacy and repository hygiene / 隐私与仓库清洁

- [ ] No `.env`, `hands.json`, Profile, calibration, dataset, log, or generated build artifact
- [ ] No real IP, serial, participant identity, username, or absolute local path
- [ ] Manufacturer originals under `inspire_doc/` were not modified
- [ ] Third-party licenses and `THIRD_PARTY.md` are updated when applicable
- [ ] `git diff --check` passes

## Rollback / 回滚

<!-- State exactly how to disable or revert the change and return hardware to a known-safe state. -->


## Reviewer focus / Reviewer 重点

<!-- Point reviewers to the riskiest assumption, control boundary, or compatibility decision. -->


## Author checklist / 作者检查

- [ ] The PR has one coherent purpose and unrelated changes were removed
- [ ] Tests cover new behavior or the absence of tests is justified
- [ ] User-facing behavior and configuration changes are documented
- [ ] English and Chinese UI/docs remain aligned when applicable
- [ ] The PR title follows `<type>: <imperative summary>`
