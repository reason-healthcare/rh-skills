---
description: "Tasks for 006-rh-inf-formalize — reviewer-gated L2→L3 formalization workflow"
---

# Tasks: `rh-inf-formalize` — Reviewer-Gated L2→L3 Formalization

**Input**: Design documents from `/specs/006-rh-inf-formalize/`  
**Branch**: `006-rh-inf-formalize`  
**Prerequisites**: `plan.md` ✅ | `spec.md` ✅ | `research.md` ✅ | `data-model.md` ✅ | `contracts/` ✅ | `quickstart.md` ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2, US3
- All paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the 006 skill surface and shared formalize test fixtures.

- [X] T001 Create curated formalize skill directory skeleton in `skills/.curated/rh-inf-formalize/` with `examples/` companion paths
- [X] T002 [P] Add shared formalize topic, review-packet, and computable-artifact fixtures in `tests/unit/test_promote.py` and `tests/unit/test_validate.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared plan/approval/validation helpers that every formalize mode depends on.

- [X] T003 Add formalize plan parsing, implementation-target selection, and approved-L2 eligibility helpers in `src/rh_skills/commands/promote.py`
- [X] T004 [P] Add formalize plan loading and L3 section-completeness helper functions in `src/rh_skills/commands/validate.py`
- [X] T005 [P] Add foundational unit coverage for formalize helper boundaries in `tests/unit/test_promote.py` and `tests/unit/test_validate.py`

**Checkpoint**: Formalize plan parsing, approved-target resolution, and plan-aware L3 validation primitives are available.

---

## Phase 3: User Story 1 — Plan Computable Artifact Scope (Priority: P1) 🎯 MVP

**Goal**: A clinical informaticist can generate `formalize-plan.md` as a reviewer-facing packet from approved, valid L2 artifacts before any L3 file is written.

**Independent Test**: Running `rh-inf-formalize plan <topic>` on a topic with approved structured inputs writes `topics/<topic>/process/plans/formalize-plan.md` with valid frontmatter, ordered review sections, one implementation target, alternate candidates marked review-only when present, required computable sections, and no L3 file creation; running it on a topic with no eligible structured artifacts exits without writing a plan.

### Tests for User Story 1

- [X] T006 [P] [US1] Add unit tests for formalize review-packet generation, alternate-candidate review-only rendering, `--force` overwrite behavior, and no-eligible-input guardrails in `tests/unit/test_promote.py`
- [X] T007 [P] [US1] Add curated skill audit coverage for the canonical `formalize-plan.md` contract in `tests/skills/test_skill_audit.py`

### Implementation for User Story 1

- [X] T008 [US1] Implement formalize review-packet generation and `formalize_planned` tracking updates in `src/rh_skills/commands/promote.py` for `topics/<topic>/process/plans/formalize-plan.md`
- [X] T009 [US1] Create `skills/.curated/rh-inf-formalize/SKILL.md` plan mode with approved-input screening, prompt-injection boundary guidance, and reviewer-packet workflow
- [X] T010 [P] [US1] Create `skills/.curated/rh-inf-formalize/reference.md` with the review-packet schema, computable package contract, and required-section completeness guidance
- [X] T011 [P] [US1] Create `skills/.curated/rh-inf-formalize/examples/plan.md` and `skills/.curated/rh-inf-formalize/examples/output.md` for the plan and approval flow

**Checkpoint**: Formalize plan mode is independently usable and produces a reviewer-ready packet without creating computable artifacts.

---

## Phase 4: User Story 2 — Implement Approved Computable Artifact (Priority: P1)

**Goal**: After reviewer approval, only the single approved implementation target is combined into an L3 artifact and immediately validated.

**Independent Test**: `rh-inf-formalize implement <topic>` fails cleanly when `formalize-plan.md` is missing, pending, rejected, or points at invalid structured inputs; when approved, it combines only the target artifact into `topics/<topic>/computable/` and runs `rh-skills validate <topic> <artifact>` immediately afterward.

### Tests for User Story 2

- [X] T012 [P] [US2] Add unit tests for approved-target selection, invalid-input blocking, and combine argument mapping in `tests/unit/test_promote.py`
- [X] T013 [P] [US2] Add focused formalize implement contract coverage in `tests/skills/test_skill_audit.py`

### Implementation for User Story 2

- [X] T014 [US2] Implement approved-target resolution and approved+valid L2 input enforcement in `src/rh_skills/commands/promote.py`
- [X] T015 [US2] Implement `rh-inf-formalize` implement mode in `skills/.curated/rh-inf-formalize/SKILL.md` to call `rh-skills promote combine` and `rh-skills validate`
- [X] T016 [P] [US2] Update `docs/COMMANDS.md` and `DEVELOPER.md` to document the formalize implement workflow and approval gate semantics

**Checkpoint**: Approved formalize plans can create exactly one computable artifact through the canonical CLI path.

---

## Phase 5: User Story 3 — Verify Computable Artifact Completeness (Priority: P2)

**Goal**: A reviewer can run verify and see whether the approved computable artifact exists, matches the plan, and satisfies minimum completeness for required section types.

**Independent Test**: `rh-inf-formalize verify <topic>` reports pass/fail per approved artifact, flags missing or mismatched `converged_from` inputs, flags missing required sections, flags incomplete section content, and makes no file or tracking writes.

### Tests for User Story 3

- [X] T017 [P] [US3] Add unit tests for plan-aware L3 verification, review-only alternate handling, `converged_from` alignment, and required-section completeness rules in `tests/unit/test_validate.py`
- [X] T018 [P] [US3] Add curated skill security coverage for read-only formalize verify behavior in `tests/skills/test_skill_security.py`

### Implementation for User Story 3

- [X] T019 [US3] Extend `src/rh_skills/commands/validate.py` with formalize-specific verification checks for approved-target alignment and section completeness
- [X] T020 [US3] Implement `rh-inf-formalize` verify mode in `skills/.curated/rh-inf-formalize/SKILL.md` with per-artifact pass/fail reporting and no-write behavior

**Checkpoint**: Verify mode independently confirms 006-specific artifact completeness guarantees.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final alignment, validation, and documentation consistency across the feature.

- [X] T021 [P] Validate SC-001 scanability and update `specs/006-rh-inf-formalize/quickstart.md` and `skills/.curated/rh-inf-formalize/reference.md` to match final command behavior and reporting details
- [X] T022 Run targeted formalize tests in `tests/unit/test_promote.py`, `tests/unit/test_validate.py`, and `tests/skills/`
- [X] T023 Run the full test suite with `uv run pytest`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 and benefits from the stabilized `formalize-plan.md` contract from US1
- **Phase 5 (US3)**: Depends on Phase 2 and should follow the finalized approved-target and L3 output behavior from US2
- **Phase 6 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Establishes the durable formalize review packet and is the MVP
- **US2 (P1)**: Depends on the approved plan contract from US1
- **US3 (P2)**: Depends on the approved-target semantics and computable output shape from US2

### Parallel Opportunities

- T002 can run in parallel with T001
- T004 and T005 can proceed in parallel once the helper boundaries in T003 are defined
- Within US1, T006 and T007 can run in parallel; T010 and T011 can run in parallel after T009 sets the skill direction
- Within US2, T012 and T013 can run in parallel; T016 can proceed once T015 settles the user-facing workflow
- Within US3, T017 and T018 can run in parallel before or alongside T019/T020

---

## Parallel Example: User Story 1

```bash
# After the review-packet schema is clear:
Task: "Add unit tests for formalize review-packet generation in tests/unit/test_promote.py"
Task: "Add curated skill audit coverage for rh-inf-formalize in tests/skills/test_skill_audit.py"

# After SKILL.md direction is set:
Task: "Create skills/.curated/rh-inf-formalize/reference.md"
Task: "Create skills/.curated/rh-inf-formalize/examples/plan.md and examples/output.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational work
2. Complete User Story 1 to produce the durable formalize review packet
3. Validate that plan mode writes the correct approval artifact and stops before any L3 writes

### Incremental Delivery

1. Ship plan-mode formalize review-packet generation
2. Add approval-gated implement over `rh-skills promote combine`
3. Add plan-aware L3 verify semantics
4. Finish with docs, skill tests, and full-suite validation

---

## Notes

- 006 should reuse `rh-skills promote combine` as the only deterministic L3 write surface rather than introducing a second computable writer
- `formalize-plan.md` is the core review artifact for this feature; approval and eligibility semantics should be treated as first-class constraints throughout implementation
