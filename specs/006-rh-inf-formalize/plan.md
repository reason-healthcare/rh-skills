# Implementation Plan: `rh-inf-formalize` Skill

**Branch**: `006-rh-inf-formalize` | **Date**: 2026-04-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-rh-inf-formalize/spec.md`

## Summary

`rh-inf-formalize` is the reviewer-gated L2→L3 convergence stage of the RH
lifecycle. It plans one primary pathway-oriented computable artifact package per
topic, using only approved and currently valid structured inputs from extract.
The implementation should reuse `rh-skills promote formalize-plan`,
`rh-skills promote combine`, and `rh-skills validate` as the deterministic
substrate, while extending planning and validation contracts so formalize can
enforce plan approval, input eligibility, required section completeness, and
read-only verification.

## Technical Context

**Language/Version**: Python 3.13+ (existing `rh-skills` CLI stack)  
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, existing
`promote`/`validate` command stack, curated skill contract framework in
`tests/skills/`  
**Storage**: File system (`topics/<topic>/process/plans/`,
`topics/<topic>/structured/`, `topics/<topic>/computable/`, `tracking.yaml`)  
**Testing**: `pytest`, `click.testing.CliRunner`, curated skill audit/security
tests under `tests/skills/`  
**Target Platform**: macOS/Linux CLI environment  
**Project Type**: CLI extension + curated SKILL.md  
**Performance Goals**: Plan generation should remain interactive for a typical
topic with 1–8 eligible structured artifacts; per-artifact combine/validate
loops should complete in seconds in stub/test mode and scale linearly with the
number of required sections  
**Constraints**: Implement mode must not write any L3 file before plan approval;
only approved and still-valid L2 inputs may be formalized; verify must be
read-only; section completeness checks must distinguish blocking errors from
advisory warnings  
**Scale/Scope**: One topic at a time; formalize v1 produces one primary
pathway-oriented computable artifact package per approved plan, with supporting
sections such as actions, value sets, measures, assessments, or libraries when
required

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Deterministic writes via `rh-skills` CLI | ✅ Pass | Durable plan writes belong to `rh-skills promote formalize-plan`; durable L3 writes belong to `rh-skills promote combine`, and verification remains on `rh-skills validate` |
| Reviewable lifecycle artifacts | ✅ Pass | 006 uses `formalize-plan.md` with an explicit approval gate before combine |
| Spec-linked validation | ✅ Pass | 006 requires validation coverage for plan approval, eligible L2 inputs, L3 section completeness, and read-only verify behavior |
| Safety and evidence integrity | ✅ Pass | Formalize consumes only approved, valid L2 inputs and must preserve review-visible unresolved modeling choices |
| Minimal surface area | ✅ Pass | 006 should extend existing promote/validate primitives rather than creating a separate L3 persistence layer |

No blocking gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/006-rh-inf-formalize/
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
├── promote.py                      # combine primitive and future formalize plan helper surface
└── validate.py                     # L3 validation surface to extend for plan-aware section completeness

tests/
├── unit/
│   ├── test_promote.py
│   └── test_validate.py
└── skills/
    ├── test_skill_audit.py
    └── test_skill_security.py

skills/.curated/rh-inf-formalize/
├── SKILL.md
├── reference.md
└── examples/
    ├── plan.md
    └── output.md
```

**Structure Decision**: Single-project Python CLI with a curated skill wrapper.
006 should extend `promote.py` and `validate.py` for deterministic plan/combine
and plan-aware L3 verification behavior, while adding a curated
`rh-inf-formalize` skill surface for review-packet reasoning and orchestration.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Plan-aware L3 section completeness checks | Formalize quality depends on more than base schema presence; section semantics must match the approved plan | Schema-only validation would miss empty pathways, value sets without codes, and measures without numerator/denominator |
| One primary output plus alternate review candidates | Reviewers need to compare candidate computable packages without implementing multiple outputs in one run | Requiring exactly one plan candidate would weaken review quality; implementing multiple outputs in v1 would complicate approval and verification flows |
