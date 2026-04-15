# Implementation Plan: `rh-inf-verify` Skill

**Branch**: `007-rh-inf-verify` | **Date**: 2026-04-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-rh-inf-verify/spec.md`

## Summary

`rh-inf-verify` becomes a standalone, topic-level verification orchestrator for
the RH lifecycle. It should remain read-only, determine which lifecycle stages
are applicable to a topic, invoke the stage-specific verify workflows via
subagents, and render one consolidated verification report that preserves
blocking failures, advisory warnings, applicability decisions, and next actions
without adding a parallel validation or persistence path.

## Technical Context

**Language/Version**: Python 3.13+ (existing `rh-skills` CLI stack)  
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, existing
`status`/`validate` command stack, curated skill contract framework in
`tests/skills/`  
**Storage**: File system only for reads (`topics/<topic>/process/plans/`,
`topics/<topic>/structured/`, `topics/<topic>/computable/`, `tracking.yaml`);
007 itself performs no writes  
**Testing**: `pytest`, curated skill audit/security/schema tests in
`tests/skills/`, plus targeted unit coverage only if helper logic is added to
the Python CLI  
**Target Platform**: macOS/Linux CLI environment  
**Project Type**: CLI extension + curated SKILL.md orchestrator  
**Performance Goals**: Unified verification should summarize a typical topic's
applicable stages in under 2 minutes and keep stage fan-out interactive for the
expected 1-topic-at-a-time review workflow  
**Constraints**: 007 must remain strictly non-destructive; stage-specific
blocking failures must remain attributable; later stages that are not yet ready
must still be reported explicitly; applicable stages with missing or stale
expected artifacts must normalize to `fail`; `invocation-error` is reserved for
verify workflows that cannot run; implementation should reuse existing verify
flows rather than duplicating validation rules  
**Scale/Scope**: One topic at a time; consolidated verification across the RH
lifecycle stages that are applicable and available for that topic

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Deterministic writes via `rh-skills` CLI | ✅ Pass | 007 is intentionally read-only and introduces no new durable write path; existing stage verify flows retain their canonical CLI boundaries |
| Reviewable lifecycle artifacts | ✅ Pass | 007 is a standalone read-only verification/reporting feature, so no new plan artifact is required; outputs must still be rerunnable and non-destructive |
| Spec-linked validation | ✅ Pass | 007 requires validation coverage for consolidated stage statuses, applicability logic, invocation-error handling, and read-only behavior |
| Safety and evidence integrity | ✅ Pass | 007 must preserve stage-level blocking errors versus warnings and avoid flattening provenance-rich stage results into generic summaries |
| Minimal surface area | ✅ Pass | 007 should orchestrate existing stage-specific verify workflows via subagents instead of creating a second validation engine |

No blocking gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/007-rh-inf-verify/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
skills/.curated/rh-inf-verify/
├── SKILL.md
├── reference.md
└── examples/
    ├── plan.md
    └── output.md

tests/skills/
├── test_skill_audit.py
├── test_skill_schema.py
└── test_skill_security.py

docs/
├── COMMANDS.md
├── WORKFLOW.md
└── SKILL_AUTHORING.md

src/rh_skills/commands/
├── status.py            # existing topic-stage summary surface used to infer applicability
└── validate.py          # existing canonical validation surface invoked by stage-specific verify flows
```

**Structure Decision**: 007 should primarily be a curated skill implementation
with documentation and skill-test updates. The design should reuse existing
topic-state and validation CLI surfaces to infer applicability and invoke
stage-specific verify behavior, avoiding a new Python validation subsystem unless
minimal helper logic proves necessary during implementation.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Stage applicability matrix | Unified verify must distinguish pass/fail from not-applicable and invocation-error for partial lifecycle topics | Treating all missing later-stage artifacts as failures would make mid-lifecycle topics look incorrectly broken |
| Parallel stage subagent fan-out | Reviewers need one consolidated report without serially re-running every stage verify workflow by hand | A single monolithic validation path would duplicate stage-specific logic and drift from the lifecycle skills |
