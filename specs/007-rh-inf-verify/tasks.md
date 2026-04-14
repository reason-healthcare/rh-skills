---
description: "Tasks for 007-rh-inf-verify — unified topic-level verification orchestrator"
---

# Tasks: `rh-inf-verify` — Unified Topic-Level Verification

**Input**: Design documents from `/specs/007-rh-inf-verify/`  
**Branch**: `007-rh-inf-verify`  
**Prerequisites**: `plan.md` ✅ | `spec.md` ✅ | `research.md` ✅ | `data-model.md` ✅ | `contracts/` ✅ | `quickstart.md` ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2, US3
- All paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the 007 skill surface and shared verification-report fixtures.

- [X] T001 Create curated verify skill directory skeleton in `skills/.curated/rh-inf-verify/` with `examples/` companion paths
- [X] T002 [P] Add shared topic-level verification report-shape coverage in `tests/skills/` and companion examples for multi-stage topic scenarios

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared applicability and reporting contract that all unified verification stories depend on.

- [X] T003 Add the unified verify report contract and stage-orchestration guidance to `skills/.curated/rh-inf-verify/reference.md`
- [X] T004 [P] Add foundational skill schema/audit expectations for `rh-inf-verify` in `tests/skills/test_skill_audit.py` and `tests/skills/test_skill_schema.py`
- [X] T005 [P] Add foundational security coverage for read-only unified verification in `tests/skills/test_skill_security.py`

**Checkpoint**: The 007 skill contract, companion-file expectations, and read-only security boundaries are in place.

---

## Phase 3: User Story 1 — Run a Unified Topic Verification Report (Priority: P1) 🎯 MVP

**Goal**: A reviewer can run `rh-inf-verify verify <topic>` and receive one consolidated report across the lifecycle stages that apply to that topic.

**Independent Test**: Run `rh-inf-verify verify <topic>` on a multi-stage topic fixture and confirm that the output includes a per-stage verification result for each applicable lifecycle skill, plus an overall topic status, without modifying any files.

### Tests for User Story 1

- [X] T006 [P] [US1] Add skill audit tests for canonical unified verification sections and stage-result reporting in `tests/skills/test_skill_audit.py`
- [X] T007 [P] [US1] Add fixture-backed verification transcript tests for multi-stage topic reporting in `tests/skills/test_skill_schema.py`

### Implementation for User Story 1

- [X] T008 [US1] Implement `skills/.curated/rh-inf-verify/SKILL.md` as a standalone topic-level orchestrator that launches applicable stage-specific verify workflows via subagents
- [X] T009 [P] [US1] Create `skills/.curated/rh-inf-verify/examples/plan.md` and `skills/.curated/rh-inf-verify/examples/output.md` for consolidated verification runs
- [X] T010 [P] [US1] Update `docs/WORKFLOW.md` and `docs/COMMANDS.md` to describe `rh-inf-verify` as unified topic verification rather than per-artifact validation

**Checkpoint**: Unified verification is independently usable as a single reviewer-facing entry point for applicable lifecycle stages.

---

## Phase 4: User Story 2 — Preserve Stage-Specific Failures and Warnings (Priority: P1)

**Goal**: The consolidated report preserves stage attribution, distinguishes blocking failures from advisory warnings, and surfaces invocation problems separately.

**Independent Test**: Run `rh-inf-verify verify <topic>` on fixtures where one stage fails, one stage warns, one applicable stage has missing or stale expected artifacts, or one stage verify cannot be invoked, and confirm the report attributes each outcome to the correct stage with distinct statuses.

### Tests for User Story 2

- [X] T011 [P] [US2] Add stage-status normalization, stale-artifact failure, and attribution coverage in `tests/skills/test_skill_audit.py`
- [X] T012 [P] [US2] Add security/audit tests that invocation problems remain distinct from domain failures in `tests/skills/test_skill_security.py`

### Implementation for User Story 2

- [X] T013 [US2] Extend `skills/.curated/rh-inf-verify/SKILL.md` with normalized stage statuses (`pass`, `fail`, `warning-only`, `not-applicable`, `invocation-error`) and attribution rules
- [X] T014 [P] [US2] Update `skills/.curated/rh-inf-verify/reference.md` and `specs/007-rh-inf-verify/quickstart.md` with blocking-vs-advisory examples, stale-artifact failure rules, and next-action expectations

**Checkpoint**: The unified report preserves stage-level diagnostics instead of flattening them into a generic topic verdict.

---

## Phase 5: User Story 3 — Handle Partial Lifecycle Topics Safely (Priority: P2)

**Goal**: `rh-inf-verify` explicitly marks stages as applicable, not-yet-ready, or not-applicable for mid-lifecycle topics while remaining read-only.

**Independent Test**: Run `rh-inf-verify verify <topic>` on a partially completed topic and confirm that eligible stages are verified, later stages are marked explicitly through applicability plus non-pass status, and repeated runs remain non-destructive.

### Tests for User Story 3

- [X] T015 [P] [US3] Add partial-lifecycle applicability, explicit not-yet-ready reporting, and rerun-safety coverage in `tests/skills/test_skill_audit.py` and `tests/skills/test_skill_security.py`
- [X] T016 [P] [US3] Add transcript examples for not-applicable and not-yet-ready stages in `skills/.curated/rh-inf-verify/examples/output.md`

### Implementation for User Story 3

- [X] T017 [US3] Implement applicability decision rules in `skills/.curated/rh-inf-verify/SKILL.md` using existing topic-state and artifact-read surfaces
- [X] T018 [P] [US3] Update `docs/SKILL_AUTHORING.md` and `docs/WORKFLOW.md` to document unified verify behavior for partial lifecycle topics

**Checkpoint**: 007 handles mid-lifecycle topics safely and predictably without implying that unavailable stages have passed or failed silently.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final alignment, validation, and documentation consistency across the feature.

- [X] T019 [P] Validate `specs/007-rh-inf-verify/quickstart.md` against the final consolidated report shape, first-failing-stage visibility, and companion examples
- [X] T020 Run targeted 007 skill tests in `tests/skills/test_skill_audit.py`, `tests/skills/test_skill_schema.py`, and `tests/skills/test_skill_security.py`
- [X] T021 Run the full test suite with `uv run pytest`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 and benefits from the stabilized unified-report shape from US1
- **Phase 5 (US3)**: Depends on Phase 2 and should follow the established stage-result model from US1 and US2
- **Phase 6 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Establishes the unified topic-level verification report and is the MVP
- **US2 (P1)**: Depends on the consolidated report structure from US1
- **US3 (P2)**: Depends on the stage applicability and result semantics established in US1/US2

### Parallel Opportunities

- T002 can run in parallel with T001
- T004 and T005 can run in parallel once T003 establishes the companion-file contract
- Within US1, T006 and T007 can run in parallel; T009 and T010 can run in parallel after T008 sets the core skill direction
- Within US2, T011 and T012 can run in parallel; T014 can proceed once T013 settles normalized statuses
- Within US3, T015 and T016 can run in parallel before or alongside T017/T018

---

## Parallel Example: User Story 1

```bash
# After the unified report contract is clear:
Task: "Add skill audit tests for unified verification sections in tests/skills/test_skill_audit.py"
Task: "Add multi-stage verification transcript tests in tests/skills/test_skill_schema.py"

# After SKILL.md direction is set:
Task: "Create skills/.curated/rh-inf-verify/examples/plan.md and examples/output.md"
Task: "Update docs/WORKFLOW.md and docs/COMMANDS.md for unified verify"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational work
2. Complete User Story 1 to produce the unified topic-level verification report
3. Validate that unified verification runs only applicable stage verifies and remains read-only

### Incremental Delivery

1. Ship unified topic-level verification orchestration
2. Add explicit failure/warning attribution and invocation-error handling
3. Add partial-lifecycle applicability behavior
4. Finish with docs/examples alignment and full-suite validation

---

## Notes

- 007 should reuse the existing stage-specific verify workflows instead of creating a parallel validation engine
- The main product value is a trustworthy consolidated report, so stage attribution, applicability, and non-destructive behavior should be treated as first-class requirements
