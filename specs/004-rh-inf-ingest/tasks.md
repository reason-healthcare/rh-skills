---
description: "Tasks for 004-rh-inf-ingest — rh-inf-ingest source acquisition and preparation skill"
---

# Tasks: `rh-inf-ingest` — Source Acquisition and Preparation

**Input**: Design documents from `/specs/004-rh-inf-ingest/`  
**Branch**: `004-rh-inf-ingest`  
**Prerequisites**: `plan.md` ✅ | `spec.md` ✅ | `research.md` ✅ | `data-model.md` ✅ | `contracts/` ✅ | `quickstart.md` ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2
- All paths are relative to repository root

---

## Phase 1: Setup (Shared Test/Command Scaffolding)

**Purpose**: Establish topic-aware ingest fixtures and helper structure before behavior changes.

- [X] T001 Create topic/discovery-plan test fixtures for ingest in `tests/unit/test_ingest.py`
- [X] T002 [P] Add discovery-plan and topic-status helper functions in `src/hi/commands/ingest.py`

---

## Phase 2: Foundational (Blocking CLI Enhancements)

**Purpose**: Add the shared topic-aware command behavior that both user stories depend on.

- [X] T003 Extend `rh-skills ingest plan` in `src/hi/commands/ingest.py` to support topic-based pre-flight summaries while preserving existing template-generation fallback
- [X] T004 Extend `rh-skills ingest verify` in `src/hi/commands/ingest.py` to support topic-based readiness reports and `concepts.yaml` validation without writing files
- [X] T005 [P] Add unit coverage for topic-aware `plan` and `verify` behavior in `tests/unit/test_ingest.py`

**Checkpoint**: Topic-aware read-only plan and verify flows are available for the skill to call.

---

## Phase 3: User Story 1 — Ingest from Discovery Plan (Priority: P1) 🎯 MVP

**Goal**: A user with a completed `discovery-plan.yaml` can review ingest readiness, download/register sources, and see status outputs that match the curated skill docs.

**Independent Test**: With a fixture topic containing `process/plans/discovery-plan.yaml`, `rh-skills ingest plan <topic>` reports open/auth/manual counts and tool availability, `rh-skills ingest implement --url ... --topic <topic>` records topic-aware source metadata, and `rh-skills ingest verify <topic>` reports checksum/readiness status without writes.

- [X] T006 [US1] Add optional `--topic` handling to `rh-skills ingest implement` and persist topic-aware source metadata in `src/hi/commands/ingest.py`
- [X] T007 [P] [US1] Add unit coverage for topic-aware `implement --url` behavior in `tests/unit/test_ingest_url.py`
- [X] T008 [US1] Update `skills/.curated/rh-inf-ingest/SKILL.md` to use the transient pre-flight plan flow, current CLI flags, injection boundary, and topic-aware verify guidance
- [X] T009 [P] [US1] Update `skills/.curated/rh-inf-ingest/reference.md` with the finalized path conventions, verify expectations, and topic-aware command examples
- [X] T010 [P] [US1] Update `skills/.curated/rh-inf-ingest/examples/output.md` and `skills/.curated/rh-inf-ingest/examples/plan.yaml` to match the implemented discovery-plan ingest flow
- [X] T011 [P] [US1] Update `specs/004-rh-inf-ingest/quickstart.md` and `DEVELOPER.md` to match the implemented topic-aware ingest workflow

**Checkpoint**: Discovery-plan-driven ingest is documented, test-covered, and consistent across CLI, skill, and examples.

---

## Phase 4: User Story 2 — Manual Source Entry (Priority: P2)

**Goal**: A user without a discovery plan, or with a mix of discovery and manual sources, can still see untracked files and verify readiness gaps clearly.

**Independent Test**: With manually placed files in `sources/` and no discovery plan, `rh-skills ingest plan <topic>` surfaces untracked manual files, and `rh-skills ingest verify <topic>` reports normalized/classified/annotated gaps without mutating tracking state.

- [X] T012 [US2] Add manual-source discovery and untracked-file reporting to topic-aware `plan`/`verify` flows in `src/hi/commands/ingest.py`
- [X] T013 [P] [US2] Add unit coverage for manual-source-only and mixed-source topic flows in `tests/unit/test_ingest.py`
- [X] T014 [US2] Update `skills/.curated/rh-inf-ingest/SKILL.md` and `skills/.curated/rh-inf-ingest/examples/output.md` with manual classification confirmation and mixed-entry guidance

**Checkpoint**: Manual-only and mixed ingest entry points are visible and documented.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Finish the feature with validation and task bookkeeping.

- [X] T015 Mark completed ingest tasks in `specs/004-rh-inf-ingest/tasks.md` as work lands
- [X] T016 Run targeted ingest tests in `tests/unit/test_ingest.py`, `tests/unit/test_ingest_url.py`, `tests/unit/test_ingest_normalize.py`, `tests/unit/test_ingest_classify.py`, and `tests/unit/test_ingest_annotate.py`
- [X] T017 Run the full test suite with `uv run pytest`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 and can proceed after the shared topic-aware flows exist
- **Phase 5 (Polish)**: Depends on the desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational — establishes the discovery-plan-driven MVP
- **US2 (P2)**: Starts after Foundational — builds on the same topic-aware helpers but remains independently testable

### Parallel Opportunities

- T002 can run in parallel with T001 once the target helper scope is clear
- T005 can run in parallel with late-stage implementation of T003/T004 once command signatures are stable
- T007, T009, T010, and T011 can run in parallel after T006/T008 set the command and skill direction
- T013 can run in parallel with T014 once T012 defines the manual-source behavior

---

## Parallel Example: User Story 1

```bash
# After T006 and T008 define the topic-aware command/docs surface:
Task: "Add unit coverage for topic-aware implement --url behavior in tests/unit/test_ingest_url.py"
Task: "Update skills/.curated/rh-inf-ingest/reference.md with finalized command examples"
Task: "Update skills/.curated/rh-inf-ingest/examples/output.md and examples/plan.yaml"
Task: "Update specs/004-rh-inf-ingest/quickstart.md and DEVELOPER.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2 to establish topic-aware read-only plan/verify flows
2. Complete Phase 3 to align CLI, skill docs, and examples for discovery-plan ingest
3. Validate the discovery-plan-driven workflow end to end

### Incremental Delivery

1. Build topic-aware plan/verify helpers
2. Add discovery-plan ingest metadata + documentation alignment
3. Add manual-source visibility and mixed-entry guidance
4. Finish with targeted and full validation

---

## Notes

- The task list reflects the current codebase: `normalize`, `classify`, and `annotate` already exist, so the remaining work centers on topic-aware orchestration, readiness reporting, and doc/example consistency
- `rh-inf-ingest` keeps a transient pre-flight summary rather than a durable ingest plan artifact; `discovery-plan.yaml` remains the canonical queued input
