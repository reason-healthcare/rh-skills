---
description: "Tasks for 008-rh-inf-status — deterministic status UX"
---

# Tasks: `rh-inf-status` — Deterministic Status UX

**Input**: Design documents from `/specs/008-rh-inf-status/`  
**Branch**: `008-rh-inf-status`  
**Prerequisites**: `plan.md` ✅ | `spec.md` ✅ | `research.md` ✅ | `data-model.md` ✅ | `contracts/` ✅ | `quickstart.md` ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2, US3
- All paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the 008 task surface and fixtures for the deterministic status UX.

- [X] T001 Review and update shared status fixtures/helpers in `tests/unit/test_status.py` and `tests/unit/test_status_extended.py` for deterministic next-step output coverage
- [X] T002 [P] Review `skills/.curated/rh-inf-status/`, `docs/COMMANDS.md`, and `docs/WORKFLOW.md` for all surfaces that currently mention status next-step UX

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Put the canonical next-step presentation contract in place before story work begins.

- [X] T003 Add the bullet-list next-step contract to `specs/008-rh-inf-status/contracts/status-output-contract.md` and align examples in `specs/008-rh-inf-status/quickstart.md`
- [X] T004 [P] Add foundational CLI validation coverage for deterministic next-step rendering in `tests/unit/test_status_extended.py`
- [X] T005 [P] Add foundational skill contract coverage for read-only status guidance in `tests/skills/test_skill_audit.py`, `tests/skills/test_skill_schema.py`, and `tests/skills/test_skill_security.py`

**Checkpoint**: The deterministic status contract and validation expectations are defined.

---

## Phase 3: User Story 1 — See current topic status with deterministic next steps (Priority: P1) 🎯 MVP

**Goal**: A user can run `rh-inf-status <topic>` and receive the canonical topic status plus deterministic bullet next steps.

**Independent Test**: Run `rh-inf-status <topic>` for topics at multiple lifecycle stages and confirm the output uses the canonical status surface, includes a `Next steps` section every time, and renders guidance as bullet items instead of lettered choices.

### Tests for User Story 1

- [X] T006 [P] [US1] Add topic-status CLI tests for bullet next steps and explicit no-action messaging in `tests/unit/test_status.py` and `tests/unit/test_status_extended.py`
- [X] T007 [P] [US1] Add skill-level status UX tests for deterministic topic guidance in `tests/skills/test_skill_audit.py` and `tests/skills/test_skill_schema.py`

### Implementation for User Story 1

- [X] T008 [US1] Update topic-level next-step rendering in `src/hi/commands/status.py` to emit deterministic bullet items instead of A/B/C-style choices
- [X] T009 [US1] Update `skills/.curated/rh-inf-status/SKILL.md` to describe `rh-skills status` as the canonical topic status engine and require bullet-list next steps
- [X] T010 [P] [US1] Update `skills/.curated/rh-inf-status/reference.md` and `skills/.curated/rh-inf-status/examples/output.md` to match the new topic-status contract

**Checkpoint**: Topic status is independently usable with deterministic next-step bullets.

---

## Phase 4: User Story 2 — Review portfolio status with consistent UX (Priority: P1)

**Goal**: A user can run `rh-inf-status` with no topic and receive portfolio status using the same status vocabulary and bullet-list next steps as topic status.

**Independent Test**: Run `rh-inf-status` with multiple topics present and confirm the portfolio summary uses the canonical status surface and the same bullet-list next-step style as the single-topic view.

### Tests for User Story 2

- [X] T011 [P] [US2] Add portfolio-status CLI tests for consistent next-step bullets in `tests/unit/test_status.py` and `tests/unit/test_status_extended.py`
- [X] T012 [P] [US2] Add skill/example contract tests for portfolio status consistency in `tests/skills/test_skill_audit.py` and `tests/skills/test_skill_schema.py`

### Implementation for User Story 2

- [X] T013 [US2] Update portfolio status output in `src/hi/commands/status.py` so portfolio recommendations follow the same deterministic bullet-list contract as topic status
- [X] T014 [P] [US2] Update `skills/.curated/rh-inf-status/examples/output.md`, `docs/COMMANDS.md`, and `docs/WORKFLOW.md` for the portfolio-status UX

**Checkpoint**: Topic and portfolio status now share one consistent status-and-guidance contract.

---

## Phase 5: User Story 3 — Detect drift and still guide the next action (Priority: P2)

**Goal**: Drift checks report changed or missing inputs, downstream stale risk, and deterministic bullet next steps for remediation.

**Independent Test**: Run `rh-skills status check-changes <topic>` for topics with changed or missing sources and confirm drift findings, stale downstream artifacts, and deterministic remediation bullets are all visible in one read-only report.

### Tests for User Story 3

- [X] T015 [P] [US3] Add drift-report CLI tests for bullet remediation guidance and downstream stale visibility in `tests/unit/test_status_extended.py`
- [X] T016 [P] [US3] Add skill/security coverage for read-only drift guidance in `tests/skills/test_skill_audit.py` and `tests/skills/test_skill_security.py`

### Implementation for User Story 3

- [X] T017 [US3] Update drift-report output in `src/hi/commands/status.py` to include deterministic bullet next steps and explicit downstream stale-risk messaging
- [X] T018 [P] [US3] Update `skills/.curated/rh-inf-status/SKILL.md`, `skills/.curated/rh-inf-status/reference.md`, and `skills/.curated/rh-inf-status/examples/output.md` for the drift-report contract
- [X] T019 [P] [US3] Align `specs/008-rh-inf-status/contracts/status-drift-contract.md` and `specs/008-rh-inf-status/quickstart.md` with the implemented drift guidance behavior

**Checkpoint**: Drift reporting is actionable and consistent with the rest of the status UX.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation consistency across the feature.

- [X] T020 [P] Validate `specs/008-rh-inf-status/quickstart.md` against the final topic, portfolio, and drift output shapes
- [X] T021 Run targeted status CLI and skill tests in `tests/unit/test_status.py`, `tests/unit/test_status_extended.py`, `tests/skills/test_skill_audit.py`, `tests/skills/test_skill_schema.py`, and `tests/skills/test_skill_security.py`
- [X] T022 Run the full test suite with `uv run pytest`
- [X] T023 Add explicit FR-010 coverage for missing tracking, unknown topics, and empty portfolios in `tests/unit/test_status.py` and `tests/unit/test_status_extended.py`
- [X] T024 Update `src/hi/commands/status.py` and `specs/008-rh-inf-status/spec.md` so failure paths include clear recovery guidance and artifact metadata stays in sync
- [X] T025 Align `specs/008-rh-inf-status/data-model.md` with the implemented portfolio contract so next steps remain per-topic except for empty-state recovery guidance
- [X] T026 Clarify in `specs/008-rh-inf-status/spec.md` and `specs/008-rh-inf-status/contracts/status-drift-contract.md` that partial drift reports for unexpected runtime I/O failures are out of scope for 008

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 and benefits from the topic-status contract established in US1
- **Phase 5 (US3)**: Depends on Phase 2 and should follow the same next-step contract used by US1 and US2
- **Phase 6 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Establishes the canonical deterministic topic-status UX and is the MVP
- **US2 (P1)**: Depends on the same next-step contract as US1, but should remain independently testable as portfolio status
- **US3 (P2)**: Depends on the shared status-and-guidance contract from US1/US2, then extends it to drift reporting

### Parallel Opportunities

- T001 and T002 can run in parallel
- T004 and T005 can run in parallel once T003 settles the output contract
- Within US1, T006 and T007 can run in parallel; T010 can run in parallel once T009 defines the skill wording
- Within US2, T011 and T012 can run in parallel; T014 can proceed once T013 settles the portfolio output shape
- Within US3, T015 and T016 can run in parallel; T018 and T019 can proceed once T017 settles the drift output shape

---

## Parallel Example: User Story 1

```bash
# After the deterministic next-step contract is defined:
Task: "Add topic-status CLI tests for bullet next steps in tests/unit/test_status.py and tests/unit/test_status_extended.py"
Task: "Add skill-level status UX tests in tests/skills/test_skill_audit.py and tests/skills/test_skill_schema.py"

# After SKILL.md direction is updated:
Task: "Update skills/.curated/rh-inf-status/reference.md and examples/output.md"
Task: "Update docs/COMMANDS.md and docs/WORKFLOW.md if topic-status wording changes"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational work
2. Complete User Story 1 so `rh-inf-status <topic>` consistently shows bullet next steps
3. Validate that the status output remains read-only and deterministic

### Incremental Delivery

1. Ship deterministic topic status first
2. Extend the same UX contract to portfolio status
3. Extend the same UX contract to drift reporting
4. Finish with quickstart/docs alignment and full validation

---

## Notes

- 008 should extend the existing `rh-skills status` logic rather than creating a parallel status engine
- The key product change is deterministic, CLI-backed next-step guidance rendered as bullet items across every status surface
