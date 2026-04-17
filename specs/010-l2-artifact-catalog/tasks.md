# Tasks: L2 Artifact Catalog Expansion

**Input**: Design documents from `/specs/010-l2-artifact-catalog/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include test tasks — this feature changes CLI behavior, contracts,
generated outputs, and path resolution across promote, validate, and render commands.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project initialization needed — this feature modifies an existing CLI tool. Setup ensures the baseline is green.

- [X] T001 Run full test suite to confirm baseline (493 passing, 11 skipped) via `pytest`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Directory restructure and artifact profile expansion that MUST be complete before render or formalize work can begin.

**⚠️ CRITICAL**: User Stories 1, 3, 4, 5 depend on this phase.

- [X] T002 [P] Add 4 new artifact profiles to `EXTRACT_ARTIFACT_PROFILES` in `src/rh_skills/commands/promote.py` — add `clinical-frame` (keywords: picot, pico, clinical question, scope, framing; section: frames), `decision-table` (keywords: decision table, condition, action, rule, if-then; section: decision_table), `assessment` (keywords: assessment, screening, questionnaire, instrument, phq, gad, score; section: assessment), `policy` (keywords: policy, prior auth, authorization, coverage, documentation requirement, payer; section: policy) with key questions per data-model.md
- [X] T003 [P] Update `_formalize_required_sections()` in `src/rh_skills/commands/promote.py` — add `decision-table` and `policy` → `actions`, `assessment` → `assessments`; `clinical-frame` gets no mapping (scoping only)
- [X] T004 Update derive path in `src/rh_skills/commands/promote.py` line ~1042 — change `l2_file = td / "structured" / f"{artifact_name}.yaml"` to `l2_file = td / "structured" / artifact_name / f"{artifact_name}.yaml"`; update tracking entry file path at line ~1066 to `f"topics/{topic}/structured/{artifact_name}/{artifact_name}.yaml"`
- [X] T005 Update artifact path resolution in `src/rh_skills/commands/validate.py` line ~366 — change `artifact_file = td / artifact_subdir / f"{artifact}.yaml"` to `artifact_file = td / artifact_subdir / artifact / f"{artifact}.yaml"`
- [X] T006 [P] Update `src/rh_skills/schemas/tracking-schema.yaml` — change structured file path comment from `topics/<name>/structured/<name>.yaml` to `topics/<name>/structured/<name>/<name>.yaml`
- [X] T007 Run full test suite after path changes — expect failures in `tests/unit/test_promote.py` and `tests/unit/test_validate.py` due to changed paths; capture which tests fail

**Checkpoint**: All path resolution uses subdirectory structure. Profile expansion ready. Tests will be fixed in Phase 3.

---

## Phase 3: User Story 1 — Extract Agent Proposes New Artifact Types (Priority: P1) 🎯 MVP

**Goal**: Planner keyword-matches source content to the expanded 12-type catalog and proposes correct artifact types.

**Independent Test**: Create normalized sources with type-specific keywords; verify `rh-skills promote plan` proposes the correct `artifact_type` for each.

### Tests for User Story 1 ⚠️

- [X] T008 [P] [US1] Add unit tests in `tests/unit/test_promote.py` — test `_infer_artifact_profile()` returns correct profile for each of the 4 new types given keyword-containing text; test that existing 8 types still match (no regression)
- [X] T009 [P] [US1] Fix any existing `test_promote.py` tests broken by path restructure (T004) — update expected paths from `structured/<name>.yaml` to `structured/<name>/<name>.yaml` in derive-related test assertions

### Implementation for User Story 1

- [X] T010 [US1] Update Hybrid Artifact Catalog table in `skills/.curated/rh-inf-extract/reference.md` (lines ~94-104) — add 4 new rows for `clinical-frame`, `decision-table`, `assessment`, `policy` with descriptions per data-model.md
- [X] T011 [P] [US1] Document type-specific L2 section shapes in `skills/.curated/rh-inf-extract/reference.md` (after line ~141) — add YAML examples for each new type's sections per data-model.md (clinical-frame frames, decision-table conditions/actions/rules, assessment instrument/items/scoring, policy applicability/criteria/actions)
- [X] T012 [P] [US1] Update plan step 4 catalog list in `skills/.curated/rh-inf-extract/SKILL.md` (lines ~142-151) — add all 4 new artifact types to the enumerated list

**Checkpoint**: Planner proposes all 12 types. Extract reference documents all section shapes. Tests green.

---

## Phase 4: User Story 2 — Derive Writes to Subdirectory Structure (Priority: P1)

**Goal**: `rh-skills promote derive` writes L2 artifacts to `structured/<name>/<name>.yaml` and all downstream commands resolve at the new path.

**Independent Test**: Run derive and verify file at new path, tracking.yaml `file` field, validate finds it.

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Fix/update derive-related tests in `tests/unit/test_promote.py` — update all assertions checking `structured/<name>.yaml` paths to `structured/<name>/<name>.yaml`; verify tracking entry `file` field uses new format
- [X] T014 [P] [US2] Fix/update path-related tests in `tests/unit/test_validate.py` — update artifact resolution assertions to `structured/<name>/<name>.yaml`

### Implementation for User Story 2

- [X] T015 [US2] Update eval fixture `eval/scenarios/rh-inf-extract/conflicting-guidelines.yaml` line ~115 — change `structured/diabetes-ccm-standards.yaml` to `structured/diabetes-ccm-standards/diabetes-ccm-standards.yaml`
- [X] T016 [US2] Update eval fixture `eval/scenarios/rh-inf-formalize/converge-l2.yaml` — change all `structured/<name>.yaml` paths (lines ~28, ~30, ~72, ~112) to `structured/<name>/<name>.yaml` format
- [X] T017 [US2] Scan for any remaining flat-path references across the codebase: `grep -rn 'structured/[^/]*\.yaml' src/ skills/ eval/ tests/ --include='*.py' --include='*.yaml' --include='*.md'` — fix any remaining hits

**Checkpoint**: All derive/validate/combine commands use subdirectory paths. Full test suite green. No flat-path references remain.

---

## Phase 5: User Story 6 — Type-Specific L2 Section Shapes (Priority: P2)

**Goal**: Each new artifact type has documented and enforceable section shapes.

**Independent Test**: Section shape validation is enforced at render time (T019). Documentation completed in US1 (T011).

**Note**: This story is sequenced before US3 (Render) because render depends on knowing the expected section shapes.

### Implementation for User Story 6

- [X] T018 [US6] Define `REQUIRED_SECTIONS` mapping in `src/rh_skills/commands/render.py` — map `clinical-frame` → `["frames"]`, `decision-table` → `["conditions", "actions", "rules"]`, `assessment` → `["instrument", "items", "scoring"]`, `policy` → `["applicability", "criteria", "actions"]`; implement `_validate_sections(yaml_data, artifact_type)` that checks `sections` dict for required keys and raises `click.UsageError` listing missing sections

**Checkpoint**: Section shape contract defined and enforceable.

---

## Phase 6: User Story 3 — Render Generates SME-Reviewable Views (Priority: P2)

**Goal**: `rh-skills render <topic> <artifact>` generates type-specific human-readable views into `views/` subdirectory.

**Independent Test**: Derive a decision-table artifact, run render, verify `views/` contains mermaid + markdown + completeness report.

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] Create `tests/unit/test_render.py` — test render command with missing artifact (exit 1 error), test generic summary renderer for existing type (produces `summary.md`), test clinical-frame renderer (produces `picots-summary.md`), test assessment renderer (produces `questionnaire.md` and `scoring-summary.md`), test policy renderer (produces `criteria-flowchart.mmd` and `requirements-checklist.md`), test decision-table renderer (produces `rules-table.md`, `decision-tree.mmd`, `completeness-report.md`), test re-render overwrites existing views (idempotent), test missing required sections error

### Implementation for User Story 3

- [X] T020 [US3] Create `src/rh_skills/commands/render.py` — implement click command group with `render` command accepting `topic` and `artifact` arguments; load artifact YAML from `topics/<topic>/structured/<artifact>/<artifact>.yaml`; read `artifact_type`; call `_validate_sections()`; dispatch to type renderer or generic fallback; create `views/` dir; print summary of files written
- [X] T021 [US3] Implement generic summary renderer `_render_generic_summary()` in `src/rh_skills/commands/render.py` — extract metadata (id, title, domain, description, artifact_type, clinical_question) and format `sections` dict as markdown with heading per key; write to `views/summary.md`
- [X] T022 [P] [US3] Implement `_render_clinical_frame()` in `src/rh_skills/commands/render.py` — read `sections.frames[]` and generate markdown table with columns: ID, Population, Intervention, Comparison, Outcomes, Timing, Setting; write to `views/picots-summary.md`
- [X] T023 [P] [US3] Implement `_render_assessment()` in `src/rh_skills/commands/render.py` — render `sections.items[]` as numbered questionnaire with options in `views/questionnaire.md`; render `sections.scoring.ranges[]` as markdown table in `views/scoring-summary.md`
- [X] T024 [P] [US3] Implement `_render_policy()` in `src/rh_skills/commands/render.py` — generate mermaid flowchart from `sections.criteria[]` showing requirement_type branching into approve/deny/pend in `views/criteria-flowchart.mmd`; generate checklist from criteria in `views/requirements-checklist.md`
- [X] T025 [US3] Register render command in `src/rh_skills/cli.py` — add `from rh_skills.commands import render` and `main.add_command(render.render)`
- [X] T026 [US3] Run full test suite including new `test_render.py` — verify all render tests pass and no regressions

**Checkpoint**: `rh-skills render` works for all types. Generic fallback covers existing 8 types. Tests green.

---

## Phase 7: User Story 4 — Decision Table Verifiability (Priority: P2)

**Goal**: Decision-table completeness report calculates Shiffman completeness, identifies missing rules, flags contradictions.

**Independent Test**: Create decision-table YAML with known missing rule; verify completeness report identifies it.

### Tests for User Story 4 ⚠️

- [X] T027 [P] [US4] Add decision-table completeness tests in `tests/unit/test_render.py` — test complete table (3 binary conditions, 8 rules → "8/8 complete"); test incomplete table (missing 1 rule → lists missing combination); test contradiction (2 rules same conditions, different actions → flags conflict); test wildcard dash (rule with dash in binary condition covers 2 combos); test large table warning (>10 condition modulus product warns about combinatorial explosion)

### Implementation for User Story 4

- [X] T028 [US4] Implement `_render_decision_table()` in `src/rh_skills/commands/render.py` — generate markdown rules table from `sections.rules[]` mapping condition values to actions in `views/rules-table.md`; generate mermaid decision tree from conditions/rules in `views/decision-tree.mmd`
- [X] T029 [US4] Implement `_check_completeness()` in `src/rh_skills/commands/render.py` — calculate product of condition moduli (total_space); for each rule, compute coverage (product of moduli for dashed conditions); sum all coverages; compare to total_space; list missing combinations if incomplete; expand dashes and check for contradictory rules (same combo → different actions); warn if total_space > 1024 (>10 binary conditions equivalent); write report to `views/completeness-report.md`
- [X] T030 [US4] Run completeness-specific tests — verify all 5 test cases pass

**Checkpoint**: Decision-table completeness reports are correct for complete, incomplete, contradictory, and wildcard cases.

---

## Phase 8: User Story 5 — Formalize Maps New Types to L3 Sections (Priority: P3)

**Goal**: `_formalize_required_sections()` correctly maps new types to L3 sections.

**Independent Test**: Unit test with mock artifacts of each new type verifies correct section mappings.

### Tests for User Story 5 ⚠️

- [X] T031 [P] [US5] Add formalize section mapping tests in `tests/unit/test_promote.py` — test `_formalize_required_sections()` with `decision-table` artifacts returns `actions`; `assessment` → `assessments`; `policy` → `actions`; `clinical-frame` → no additional sections beyond `pathways` default; mixed types → union of required sections

### Implementation for User Story 5

Implementation was completed in T003 (Foundational phase). This phase adds test coverage only.

**Checkpoint**: Formalize correctly routes all 12 types. Tests green.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, documentation cleanup, and commit.

- [X] T032 [P] Scan for any remaining references to the old 8-type-only catalog across `skills/.curated/`, `docs/`, and `eval/` — update any stale references
- [X] T033 Run full test suite (`pytest`) — confirm all tests pass with no regressions from baseline
- [X] T034 Run quickstart.md validation — walk through the derive→render workflow manually with a test topic to confirm end-to-end flow
- [X] T035 Create git commit with all changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — confirms green baseline
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (profiles + path changes)
- **US2 (Phase 4)**: Depends on Phase 2 (path changes); parallelizable with US1
- **US6 (Phase 5)**: Depends on Phase 2; parallelizable with US1/US2
- **US3 (Phase 6)**: Depends on US6 (section shapes) and Phase 2 (paths)
- **US4 (Phase 7)**: Depends on US3 (render infrastructure)
- **US5 (Phase 8)**: Depends on Phase 2 only (T003); parallelizable with all others
- **Polish (Phase 9)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)** + **US2 (P1)** + **US5 (P3)** + **US6 (P2)**: All independent after Foundational — can run in parallel
- **US3 (P2)**: Depends on US6 (section shape definitions for validation)
- **US4 (P2)**: Depends on US3 (render infrastructure must exist)

### Within Each User Story

- Tests before/alongside implementation
- Validate tests fail before implementing (where applicable)
- Run targeted tests after each task group

### Parallel Opportunities

- T002, T003, T006 can run in parallel (different functions/files)
- T008, T009 can run in parallel (different test areas)
- T010, T011, T012 can run in parallel (different doc files)
- T013, T014 can run in parallel (different test files)
- T019 can run while T018 completes (test file vs source file)
- T022, T023, T024 can run in parallel (independent renderer functions)
- T027, T031 can run in parallel (different test files/functions)

---

## Parallel Example: Foundational Phase

```bash
# These can all run in parallel (different locations in promote.py and different files):
Task T002: "Add 4 new artifact profiles to EXTRACT_ARTIFACT_PROFILES in promote.py"
Task T003: "Update _formalize_required_sections() in promote.py"
Task T006: "Update tracking-schema.yaml path comments"
```

## Parallel Example: User Story 3 Renderers

```bash
# Independent renderer functions — all can run in parallel:
Task T022: "_render_clinical_frame() in render.py"
Task T023: "_render_assessment() in render.py"
Task T024: "_render_policy() in render.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (baseline green)
2. Complete Phase 2: Foundational (profiles + paths)
3. Complete Phase 3: US1 (planner proposes new types)
4. Complete Phase 4: US2 (derive/validate/fixtures use new paths)
5. **STOP and VALIDATE**: Planner works, derive writes to subdirectory, validate finds artifacts
6. This is a shippable increment — new types work in extract→derive→validate flow

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. Add US1 + US2 → Extract and derive work with 12 types (MVP!)
3. Add US6 + US3 → Render command generates views for all types
4. Add US4 → Decision-table completeness verification
5. Add US5 → Formalize mappings complete the lifecycle
6. Each increment adds value without breaking previous work

---

## Notes

- [P] tasks = different files or non-overlapping code, no dependencies
- [Story] label maps task to specific user story for traceability
- Total: 35 tasks across 9 phases
- Baseline test count: 493 passing, 11 skipped — must not regress
- render.py is a new file — no merge conflicts expected
- promote.py has the most edits (profiles, formalize, derive path, tracking path)
- Commit after each phase checkpoint for safe rollback points
