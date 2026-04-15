---
description: "Tasks for 009-skill-build-system — RH skills build system"
---

# Tasks: `RH Skills Build System`

**Input**: Design documents from `/specs/009-skill-build-system/`  
**Branch**: `009-skill-build-system`  
**Prerequisites**: `plan.md` ✅ | `spec.md` ✅ | `research.md` ✅ | `data-model.md` ✅ | `contracts/` ✅ | `quickstart.md` ✅

**Tests**: This feature explicitly requires fixture-driven build validation and CI installability checks, so test tasks are included for each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (`US1`, `US2`, `US3`)
- Every task includes an exact file path or concrete path group

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the file surfaces and contributor documentation entry points for the build system.

- [X] T001 Create the build-system file skeleton in `scripts/build-skills.sh`, `skills/_profiles/`, `tests/build/`, and `.github/workflows/`
- [X] T002 [P] Add generated-output ignore coverage for `dist/` in `/Users/bkaney/projects/reason-skills-2/.gitignore`
- [X] T003 [P] Create contributor-facing build documentation stub in `/Users/bkaney/projects/reason-skills-2/docs/SKILL_DISTRIBUTION.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared build/profile/test infrastructure that every story depends on.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [X] T004 Implement shared argument parsing, platform selection, and summary scaffolding in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T005 [P] Create reusable subprocess/build fixtures in `/Users/bkaney/projects/reason-skills-2/tests/build/conftest.py`
- [X] T006 [P] Create bundled platform profile baselines in `/Users/bkaney/projects/reason-skills-2/skills/_profiles/copilot.yaml`, `/Users/bkaney/projects/reason-skills-2/skills/_profiles/claude.yaml`, and `/Users/bkaney/projects/reason-skills-2/skills/_profiles/gemini.yaml`
- [X] T007 [P] Add the optional aggregate-output profile in `/Users/bkaney/projects/reason-skills-2/skills/_profiles/agents-md.yaml`
- [X] T008 Add foundational pytest coverage for zero buildable skills, placeholder detection, missing profiles, conflicting outputs, and unknown fields in `/Users/bkaney/projects/reason-skills-2/tests/build/test_build_skills.py`

**Checkpoint**: The build entrypoint, bundled profiles, and shared validation fixture surface are ready for user-story work.

---

## Phase 3: User Story 1 - Build skill bundles for supported platforms (Priority: P1) 🎯 MVP

**Goal**: Contributors can generate deterministic platform-specific bundles from the canonical curated skill library for one platform or all bundled platforms.

**Independent Test**: Run the build workflow for one supported platform and for `--all`, then confirm generated bundles appear under `dist/` with deterministic content and a contributor-facing summary.

### Tests for User Story 1

- [X] T009 [P] [US1] Add single-platform and all-platform build scenarios in `/Users/bkaney/projects/reason-skills-2/tests/build/test_build_skills.py`
- [X] T010 [P] [US1] Add expected build fixture inputs and output assertions under `/Users/bkaney/projects/reason-skills-2/tests/build/fixtures/`

### Implementation for User Story 1

- [X] T011 [US1] Implement single-platform and `--all` bundle generation in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T012 [US1] Implement profile-driven frontmatter, preamble, suffix, and omitted-section transforms in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T013 [US1] Implement deterministic writes to `/Users/bkaney/projects/reason-skills-2/dist/` and per-skill/per-platform summary output in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T014 [US1] Document local build workflows and generated output expectations in `/Users/bkaney/projects/reason-skills-2/docs/SKILL_DISTRIBUTION.md`

**Checkpoint**: User Story 1 is independently functional when contributors can build deterministic bundles locally for one or all bundled platforms.

---

## Phase 4: User Story 2 - Add or adjust a platform profile declaratively (Priority: P2)

**Goal**: Maintainers can onboard or refine platform support through profile files rather than editing core build logic.

**Independent Test**: Add a new test profile and confirm the build workflow can consume it without core script changes while still failing clearly on invalid profile definitions.

### Tests for User Story 2

- [X] T015 [P] [US2] Add declarative profile onboarding tests in `/Users/bkaney/projects/reason-skills-2/tests/build/test_build_skills.py`
- [X] T016 [P] [US2] Add invalid-profile fixtures for missing supporting files and output conflicts in `/Users/bkaney/projects/reason-skills-2/tests/build/fixtures/`

### Implementation for User Story 2

- [X] T017 [US2] Implement generic profile loading and transform dispatch in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T018 [US2] Implement profile validation for required fields, supporting-file existence, and conflicting destinations in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T019 [US2] Document platform profile authoring and extension rules in `/Users/bkaney/projects/reason-skills-2/docs/SKILL_DISTRIBUTION.md`

**Checkpoint**: User Story 2 is independently functional when a maintainer can add a new profile and build it without rewriting core build orchestration.

---

## Phase 5: User Story 3 - Validate or preview build output before distribution (Priority: P2)

**Goal**: Contributors can preview build results non-destructively, validate generated bundles locally, and rely on CI installability checks before distribution.

**Independent Test**: Run `--dry-run` and `--validate` locally, then verify repository CI performs validation plus installability smoke checks and reports platform-specific failures clearly.

### Tests for User Story 3

- [X] T020 [P] [US3] Add dry-run and validation-mode scenarios in `/Users/bkaney/projects/reason-skills-2/tests/build/test_build_skills.py`
- [X] T021 [P] [US3] Add CI/installability fixture assertions for bundled targets in `/Users/bkaney/projects/reason-skills-2/tests/build/test_build_skills.py`

### Implementation for User Story 3

- [X] T022 [US3] Implement `--dry-run` and `--validate` behavior in `/Users/bkaney/projects/reason-skills-2/scripts/build-skills.sh`
- [X] T023 [US3] Create CI build, validation, and installability smoke workflow in `/Users/bkaney/projects/reason-skills-2/.github/workflows/skill-build.yml`
- [X] T024 [US3] Add contributor guidance for CI failures and local reproduction steps in `/Users/bkaney/projects/reason-skills-2/docs/SKILL_DISTRIBUTION.md`

**Checkpoint**: User Story 3 is independently functional when contributors can preview, validate, and rely on CI installability checks before shipping bundles.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation alignment, and end-to-end validation across all stories.

- [X] T025 [P] Align `/Users/bkaney/projects/reason-skills-2/DEVELOPER.md` and `/Users/bkaney/projects/reason-skills-2/README.md` with the new build/distribution workflow
- [X] T026 [P] Validate `/Users/bkaney/projects/reason-skills-2/specs/009-skill-build-system/quickstart.md` against the implemented build, validate, and CI flows
- [X] T027 Run targeted build-system tests in `/Users/bkaney/projects/reason-skills-2/tests/build/test_build_skills.py` and existing skill suites affected by generated outputs
- [X] T028 Run the full repository test suite and workflow validation commands from `/Users/bkaney/projects/reason-skills-2`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all story work
- **Phase 3 (US1)**: Depends on Phase 2 and delivers the MVP build capability
- **Phase 4 (US2)**: Depends on Phase 2 and builds on the generic profile surface introduced for US1
- **Phase 5 (US3)**: Depends on Phase 2 and should follow the core build surface from US1 so validation runs against real generated bundles
- **Phase 6 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational and is the MVP
- **US2 (P2)**: Depends on the shared profile/build infrastructure from Foundational and should integrate cleanly with US1 output generation
- **US3 (P2)**: Depends on the same build surface as US1 and the profile contracts established in US2 for validation/installability checks

### Within Each User Story

- Story-specific tests should be written before or alongside the corresponding implementation
- Fixture/data setup precedes script or workflow changes that rely on those fixtures
- Build generation precedes validation/installability integration
- Each story should remain independently runnable using its stated test criteria

### Parallel Opportunities

- T002 and T003 can run in parallel during Setup
- T005, T006, and T007 can run in parallel once T004 defines the entrypoint surface
- Within US1, T009 and T010 can run in parallel; T014 can proceed after T011–T013 settle the local workflow
- Within US2, T015 and T016 can run in parallel; T019 can proceed after T017–T018 define the profile contract
- Within US3, T020 and T021 can run in parallel; T024 can proceed after T022–T023 define the validation/CI behavior
- T025 and T026 can run in parallel during Polish

---

## Parallel Example: User Story 1

```bash
# Launch story tests/fixtures together:
Task: "Add single-platform and all-platform build scenarios in tests/build/test_build_skills.py"
Task: "Add expected build fixture inputs and output assertions under tests/build/fixtures/"

# After the build contract is stable:
Task: "Document local build workflows and generated output expectations in docs/SKILL_DISTRIBUTION.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Confirm one-platform and all-platform builds are deterministic and usable locally
5. Demo/distribute the MVP build surface before extending it

### Incremental Delivery

1. Ship the deterministic multi-platform build workflow first (US1)
2. Add declarative platform onboarding and profile validation (US2)
3. Add preview, validation, and CI installability checks (US3)
4. Finish with documentation alignment and full-suite validation

### Parallel Team Strategy

With multiple contributors:

1. One contributor completes Setup + Foundational
2. After Foundational:
   - Contributor A: US1 build generation
   - Contributor B: US2 profile onboarding/validation
   - Contributor C: US3 validation + CI smoke workflow
3. Rejoin in Polish for documentation and end-to-end validation

---

## Notes

- `[P]` tasks target different files or separable fixture/workflow surfaces
- Story labels map every story-phase task back to a specific user story for traceability
- 009 explicitly excludes transcript-ranking and model-evaluation infrastructure
- Generated output must remain separate from canonical curated skills at every phase
