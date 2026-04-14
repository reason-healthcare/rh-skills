# Contract: Unified Topic Verification Report

**Phase 1 Design Artifact** | **Branch**: `007-rh-inf-verify`

---

## Invocation

`rh-inf-verify verify <topic>`

## Required Report Sections

The consolidated output should appear in this order:

1. `Topic Summary`
2. `Stage Results`
3. `Overall Readiness`
4. `Recommended Next Action`

## Stage Result Shape

Each stage entry in the report must include:
- stage name
- underlying skill name
- applicability decision
- normalized status (`pass`, `fail`, `warning-only`, `not-applicable`,
  or `invocation-error`)
- short summary
- blocking findings (if any)
- advisory findings (if any)
- next action

## Normalization Rules

- Stage-specific blocking failures map to `fail`.
- Stage-specific warning-only outcomes map to `warning-only`.
- A stage that cannot be run successfully maps to `invocation-error`.
- A stage that is otherwise applicable but has missing or stale expected
  artifacts maps to `fail`.
- A stage omitted because the topic has not advanced far enough must be rendered
  with applicability `not-yet-ready` or `not-applicable`, not silently skipped.
- Stages with applicability `not-yet-ready` normalize to status
  `not-applicable` in the consolidated report.

## Read-Only Rules

- The unified report is terminal output only.
- `rh-inf-verify` must not create a durable verification file.
- The skill must not write to `tracking.yaml` directly or indirectly.
