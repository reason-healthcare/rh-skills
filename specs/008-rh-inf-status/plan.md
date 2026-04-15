# Implementation Plan: `rh-inf-status` Skill

**Branch**: `008-rh-inf-status` | **Date**: 2026-04-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-rh-inf-status/spec.md`

## Summary

`rh-inf-status` should become the read-only status companion for the RH
workflow, backed by the canonical `rh-skills status` CLI surface. The feature
should unify single-topic status, portfolio status, and drift reporting around
one deterministic status model, and replace model-specific A/B/C next-step
choices with CLI-produced bullet lists of recommended actions.

## Technical Context

**Language/Version**: Python 3.13+ (existing `rh-skills` CLI stack)  
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, existing
`src/rh_skills/commands/status.py`, curated skill contract framework in `tests/skills/`  
**Storage**: File system reads only (`tracking.yaml`, `topics/<topic>/...`,
`sources/`)  
**Testing**: `pytest`, status unit tests in `tests/unit/`, curated skill
audit/schema/security tests in `tests/skills/`  
**Target Platform**: macOS/Linux CLI environment  
**Project Type**: CLI command extension + curated SKILL.md alignment  
**Performance Goals**: Status and next-step reporting should remain interactive
for 1-topic and portfolio use, with typical output ready in under 1 minute of
user inspection  
**Constraints**: 008 must remain strictly read-only; all next-step
recommendations must come from deterministic CLI logic; the canonical status
surface must be reused instead of duplicating status reasoning in `SKILL.md`;
next steps must be rendered as bullet items rather than lettered choices  
**Scale/Scope**: One repository portfolio at a time; multiple topics per
portfolio; topic-level drift reporting for registered sources and downstream
staleness hints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Deterministic writes via `rh-skills` CLI | ✅ Pass | 008 is intentionally read-only; status and recommendation logic stays inside `rh-skills status` rather than the skill prompt |
| Reviewable lifecycle artifacts | ✅ Pass | 008 is a status-only/read-only feature, so no plan artifact is required for runtime use; rerun safety remains mandatory |
| Spec-linked validation | ✅ Pass | 008 requires test coverage for changed status CLI contracts, deterministic next-step output, and the removal of lettered choice UX |
| Safety and evidence integrity | ✅ Pass | Status/drift output must remain read-only and distinguish state summaries from drift findings without inventing unsupported conclusions |
| Minimal surface area | ✅ Pass | The feature extends the existing `rh-skills status` command and aligned `rh-inf-status` skill instead of adding a parallel status command |

No blocking gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/008-rh-inf-status/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
src/rh_skills/commands/
└── status.py

skills/.curated/rh-inf-status/
├── SKILL.md
├── reference.md
└── examples/
    ├── plan.md
    └── output.md

docs/
├── COMMANDS.md
├── WORKFLOW.md
└── SKILL_AUTHORING.md

tests/unit/
├── test_status.py
└── test_status_extended.py

tests/skills/
├── test_skill_audit.py
├── test_skill_schema.py
└── test_skill_security.py
```

**Structure Decision**: 008 should land primarily in the existing status CLI
command, the curated `rh-inf-status` skill files, and their associated docs and
tests. No new persistence surface or separate orchestration command is needed.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Portfolio + topic next-step unification | Status must feel identical whether users inspect one topic or the full portfolio | Leaving topic and portfolio UX divergent would preserve the current inconsistency the feature is meant to remove |
