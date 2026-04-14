---
description: "Tasks for 005-rh-inf-extract — reviewer-gated L2 extraction workflow"
---

# Tasks: `rh-inf-extract` — Reviewer-Gated L2 Extraction

**Input**: Design documents from `/specs/005-rh-inf-extract/`  
**Branch**: `005-rh-inf-extract`  
**Prerequisites**: `plan.md` ✅ | `spec.md` ✅ | `research.md` ✅ | `data-model.md` ✅ | `contracts/` ✅ | `quickstart.md` ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2, US3
- All paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the 005 skill surface and common extract test fixtures.

- [X] T001 Create curated extract skill directory skeleton in `skills/.curated/rh-inf-extract/` with `examples/` companion paths
- [X] T002 [P] Add shared extract topic/review-packet test fixtures in `tests/unit/test_promote.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared schema and validation helpers that all extract modes depend on.

- [ ] T003 Add extract plan parsing and approval-gate helper functions in `src/hi/commands/promote.py`
- [X] T004 [P] Extend L2 artifact validation helpers in `src/hi/commands/validate.py` for traceability/conflict checks required by 005
- [X] T005 [P] Add foundational validation coverage for extract helpers in `tests/unit/test_validate.py`

**Checkpoint**: Extract plan parsing, approval-state checks, and 005 validation primitives are available.

---

## Phase 3: User Story 1 — Generate the Extract Review Packet (Priority: P1) 🎯 MVP

**Goal**: A clinical informaticist can generate `extract-plan.md` as a reviewer-facing packet from normalized sources and `concepts.yaml`, before any L2 files are written.

**Independent Test**: Running `rh-inf-extract plan <topic>` on a topic with normalized inputs writes `topics/<topic>/process/plans/extract-plan.md` with valid frontmatter, ordered review sections, proposed artifacts, source coverage, and unresolved conflicts; running it on a topic with no normalized sources exits without writing a plan.

### Tests for User Story 1

- [ ] T006 [P] [US1] Add unit tests for extract review-packet generation and no-input guardrails in `tests/unit/test_promote.py`
- [X] T007 [P] [US1] Add curated skill audit coverage for `rh-inf-extract` plan artifact contract in `tests/skills/test_skill_audit.py`

### Implementation for User Story 1

- [ ] T008 [US1] Implement review-packet plan generation in `src/hi/commands/promote.py` for `topics/<topic>/process/plans/extract-plan.md`
- [X] T009 [US1] Create `skills/.curated/rh-inf-extract/SKILL.md` plan mode with the injection boundary, hybrid catalog guidance, and reviewer-packet workflow
- [X] T010 [P] [US1] Create `skills/.curated/rh-inf-extract/reference.md` with artifact catalog, traceability rules, and conflict-handling guidance
- [X] T011 [P] [US1] Create `skills/.curated/rh-inf-extract/examples/plan.md` and `skills/.curated/rh-inf-extract/examples/output.md` for the review-packet flow

**Checkpoint**: Extract plan mode is independently usable and produces a reviewer-ready packet.

---

## Phase 4: User Story 2 — Implement Only Approved Artifacts (Priority: P1)

**Goal**: After reviewer approval, only approved artifacts are derived, and each derived artifact is immediately validated.

**Independent Test**: `rh-inf-extract implement <topic>` fails cleanly when `extract-plan.md` is missing or unapproved, derives only `reviewer_decision: approved` artifacts via `rh-skills promote derive`, and runs `rh-skills validate <topic> <artifact>` after each artifact.

### Tests for User Story 2

- [ ] T012 [P] [US2] Add unit tests for approval-gated derive behavior and approved-artifact selection in `tests/unit/test_promote.py`
- [X] T013 [P] [US2] Add unit tests for extract validation invocation/reporting in `tests/unit/test_validate.py`

### Implementation for User Story 2

- [X] T014 [US2] Extend `src/hi/commands/promote.py` derive flow to emit the richer 005 L2 schema with multi-source provenance, clinical question, sections, and conflict placeholders
- [X] T015 [US2] Implement approval-gated extract implement orchestration in `skills/.curated/rh-inf-extract/SKILL.md`
- [X] T016 [P] [US2] Update `specs/005-rh-inf-extract/quickstart.md` and `DEVELOPER.md` to document approval-gated derive/validate orchestration

**Checkpoint**: Approved artifacts can be derived and validated without touching rejected or pending entries.

---

## Phase 5: User Story 3 — Verify Traceability and Conflict Handling (Priority: P2)

**Goal**: A reviewer can run verify and see whether derived L2 artifacts satisfy both schema and extract-specific evidence/conflict requirements.

**Independent Test**: `rh-inf-extract verify <topic>` reports pass/fail per artifact, flags missing traceability sections, flags missing conflict records when the approved plan required them, and makes no file or tracking writes.

### Tests for User Story 3

- [X] T017 [P] [US3] Add unit tests for extract-specific verify reporting in `tests/unit/test_validate.py`
- [X] T018 [P] [US3] Add curated skill security/audit coverage for read-only verify mode in `tests/skills/test_skill_security.py`

### Implementation for User Story 3

- [X] T019 [US3] Extend `src/hi/commands/validate.py` with extract-specific artifact verification checks tied to approved plan expectations
- [X] T020 [US3] Implement verify mode in `skills/.curated/rh-inf-extract/SKILL.md` with per-artifact pass/fail reporting and no-write behavior

**Checkpoint**: Verify mode independently confirms 005-specific artifact quality guarantees.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final alignment, task bookkeeping, and validation.

- [X] T021 Mark completed work items in `specs/005-rh-inf-extract/tasks.md` as implementation lands
- [X] T022 Run targeted extract tests in `tests/unit/test_promote.py`, `tests/unit/test_validate.py`, and `tests/skills/`
- [X] T023 Run the full test suite with `uv run pytest`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 and benefits from US1 plan artifact shape being finalized
- **Phase 5 (US3)**: Depends on Phase 2 and should follow the stabilized 005 artifact schema from US2
- **Phase 6 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Establishes the durable review packet and is the MVP
- **US2 (P1)**: Depends on the approved plan contract from US1
- **US3 (P2)**: Depends on the richer L2 schema and approval semantics from US2

### Parallel Opportunities

- T002 can run in parallel with T001
- T004 and T005 can proceed in parallel once helper boundaries in T003 are clear
- Within US1, T006/T007 can run in parallel and T010/T011 can run in parallel after T009 sets the skill direction
- Within US2, T012 and T013 can run in parallel; T016 can proceed once command behavior is settled
- Within US3, T017 and T018 can run in parallel before/alongside T019/T020

---

## Parallel Example: User Story 1

```bash
# After the review-packet contract is clear:
Task: "Add unit tests for extract review-packet generation in tests/unit/test_promote.py"
Task: "Add curated skill audit coverage for rh-inf-extract in tests/skills/test_skill_audit.py"

# After SKILL.md direction is set:
Task: "Create skills/.curated/rh-inf-extract/reference.md"
Task: "Create skills/.curated/rh-inf-extract/examples/plan.md and examples/output.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational work
2. Complete User Story 1 to produce the durable review packet
3. Validate that plan mode writes the correct approval artifact and stops before any L2 writes

### Incremental Delivery

1. Ship plan-mode review packet generation
2. Add approval-gated implement over `rh-skills promote derive`
3. Add extract-specific verify semantics
4. Finish with docs, skill tests, and full-suite validation

---

## Notes

- 005 should extend existing deterministic CLI primitives instead of creating a second L2 write path
- The review packet is the core artifact for this feature; approval semantics should be treated as first-class, not as a thin wrapper around `promote derive`
