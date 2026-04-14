# Contract: Status Drift Reporting

**Phase 1 Design Artifact** | **Branch**: `008-rh-inf-status`

---

## Goal

Define how status-driven drift checks report changed or missing inputs and guide
follow-up action.

## Invocation

`rh-skills status check-changes <topic>`

## Required Behavior

- Re-check registered source inputs for changed or missing state.
- Report each affected source explicitly.
- Show which downstream artifacts may now be stale, including both structured
  artifacts derived from the changed source and computable artifacts converged
  from those stale structured artifacts when that relationship is known.
- Include deterministic bullet next steps for remediation or review.

## Drift Finding Semantics

- `ok` — source is unchanged
- `changed` — source exists but no longer matches the recorded checksum
- `missing` — source cannot be found at the expected location

Unexpected runtime filesystem or checksum errors outside these states are not a
special partially rendered drift-report mode for 008; they surface as normal
CLI command failures.

## Next-Step Rules

- The first recommended step should address the drift directly.
- Follow-up steps may include re-checking status or reviewing downstream stale
  artifacts.
- Recommendations must remain read-only unless the recommended command itself is
  a user-initiated state-changing CLI action outside the current status command.
