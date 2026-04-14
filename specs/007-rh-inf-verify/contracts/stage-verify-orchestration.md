# Contract: Stage Verify Orchestration

**Phase 1 Design Artifact** | **Branch**: `007-rh-inf-verify`

---

## Goal

Define how `rh-inf-verify` delegates to stage-specific verify workflows.

## Inputs

- topic slug
- lifecycle-stage applicability decision
- stage-specific verify command shape

## Orchestration Rules

- 007 should launch one subagent per applicable lifecycle stage verify workflow.
- Applicable stage verifies may run in parallel when they do not depend on each
  other's output.
- The unified orchestrator must collect each stage's outcome before rendering the
  final report.

## Stage Mapping

Expected stage verify delegation:

- discovery → `rh-inf-discovery verify <topic>` when that workflow is available
- ingest → `rh-inf-ingest verify <topic>`
- extract → `rh-inf-extract verify <topic>`
- formalize → `rh-inf-formalize verify <topic>`

## Failure Handling

- If a stage verify returns blocking failures, preserve them as stage-specific
  blocking findings.
- If a stage verify returns warnings only, preserve them as advisory findings.
- If a stage verify cannot be invoked or cannot complete, classify that stage as
  `invocation-error`.

## Safety Rules

- Delegated stage verifies must remain read-only.
- 007 must not compensate for or override a failing stage by silently calling
  lower-level validation commands in its place.
