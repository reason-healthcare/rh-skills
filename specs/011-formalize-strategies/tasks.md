# Tasks: L2→L3 Formalization Strategies

**Input**: Design documents from `/specs/011-formalize-strategies/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — this feature changes CLI commands, output formats, validation rules, tracking events, and skill contracts.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the FHIR validation/normalization module and CLI scaffolding

- [X] T001 Create `src/rh_skills/fhir/__init__.py` with module docstring describing hybrid LLM + validation architecture
- [X] T002 [P] Implement FHIR resource normalization in `src/rh_skills/fhir/normalize.py` — functions for: kebab-case id generation, canonical URL pattern (`http://example.org/fhir/<ResourceType>/<id>`), ISO date formatting, version string default (`1.0.0`), status default (`draft`), resourceType validation against allowed set
- [X] T003 [P] Implement FHIR structural validation in `src/rh_skills/fhir/validate.py` — per-resource-type required-field checks (e.g., PlanDefinition must have `type`, Measure must have `group[].population[]`, Questionnaire must have `item[].linkId`); return list of validation errors; detect `TODO:MCP-UNREACHABLE` placeholders as errors
- [X] T004 [P] Implement FHIR package builder in `src/rh_skills/fhir/packaging.py` — functions to: generate `package.json` (name, version, fhirVersions, dependencies, type), generate `ImplementationGuide` resource JSON, collect files from `computable/` directory
- [X] T005 [P] Write tests for normalization in `tests/test_fhir_normalize.py` — id generation, URL patterns, date formatting, resourceType validation
- [X] T006 [P] Write tests for structural validation in `tests/test_fhir_validate.py` — required field checks per resource type, MCP-UNREACHABLE detection, valid resource passes
- [X] T007 [P] Write tests for packaging in `tests/test_fhir_packaging.py` — package.json generation, IG resource structure, file collection

**Checkpoint**: FHIR module ready — normalization, validation, and packaging utilities tested

---

## Phase 2: Foundational (CLI Commands)

**Purpose**: Implement the two new CLI commands that serve as the deterministic write boundary

**⚠️ CRITICAL**: No user story work can begin until these commands exist

- [X] T008 Implement `rh-skills formalize <topic> <artifact>` command in **`src/rh_skills/commands/formalize.py`** (new file) — follows existing `promote combine` LLM pattern: load L2 artifact, build type-specific system prompt referencing strategy from reference.md, invoke LLM, parse FHIR JSON response, run normalization, write individual `<ResourceType>-<id>.json` and `.cql` files to `topics/<topic>/computable/`, update tracking with `files` list + `checksums` dict + `converged_from` + `strategy`, append `computable_converged` event. Support `--dry-run` and `--force` flags. Handle partial failure (keep written files, report failures, exit code 1). Handle MCP-UNREACHABLE (placeholder codes, warn, continue). Register command in `src/rh_skills/commands/__init__.py`. Per contract: `specs/011-formalize-strategies/contracts/formalize-command.md`
- [X] T009 Implement `rh-skills package <topic>` command in `src/rh_skills/commands/package.py` — collect all FHIR JSON + CQL from `topics/<topic>/computable/`, call `fhir/packaging.py` to generate `package.json` and `ImplementationGuide`, copy all files to `topics/<topic>/package/`, append `package_created` event. Support `--dry-run` and `--output-dir`. Register command in `src/rh_skills/commands/__init__.py`. Per contract: `specs/011-formalize-strategies/contracts/package-command.md`
- [X] T010 Add deprecation warning to existing `promote combine` command in `src/rh_skills/commands/promote.py` — emit `DeprecationWarning` pointing to `rh-skills formalize` + `rh-skills package`; command still functions
- [X] T011 Update tracking schema for new `computable` entry shape in `src/rh_skills/commands/promote.py` — change from single `file`/`checksum` to `files` (list) and `checksums` (dict) per data-model.md Entity 4; ensure backward compatibility with existing single-file entries
- [X] T011b Write eval scenario for unknown/custom artifact_type fallback in `eval/scenarios/rh-inf-formalize/unknown-type-fallback.yaml` — provide an artifact with an unrecognized `artifact_type`, verify `rh-skills formalize` falls back to generic strategy with warning message, confirm tracking records `strategy: generic` (covers FR-009 edge case)
- [X] T012 [P] Write CLI integration tests for `rh-skills formalize` in `tests/test_formalize_command.py` — precondition checks (topic exists, artifact approved, plan approved), dry-run output, FHIR JSON file writing, tracking event appended, partial failure behavior, unknown artifact_type fallback
- [X] T013 [P] Write CLI integration tests for `rh-skills package` in `tests/test_package_command.py` — precondition checks, package.json structure, IG resource, file collection, tracking event

**Checkpoint**: Both CLI commands functional + tested. `promote combine` deprecated with warning.

---

## Phase 3: User Story 1 — Type-specific formalize plan generation (Priority: P1) 🎯 MVP

**Goal**: Plan mode reads each L2 artifact type, selects the correct strategy, and proposes L3 FHIR targets with type-appropriate structure

**Independent Test**: Run `rh-inf-formalize plan <topic>` on a topic with a `decision-table` artifact. Confirm the plan proposes PlanDefinition (eca-rule) with condition/action sections, not generic pathway.

### Implementation for User Story 1

- [X] T014 [US1] Update strategy-to-target mapping in `src/rh_skills/commands/promote.py` `_formalize_required_sections()` — replace current generic section mapping with the 7-type L3 target mapping from `docs/FORMALIZE_STRATEGIES.md`: evidence-summary→Evidence/EvidenceVariable/Citation, decision-table→PlanDefinition(eca-rule)/Library, care-pathway→PlanDefinition(clinical-protocol)/ActivityDefinition, terminology→ValueSet/ConceptMap, measure→Measure/Library, assessment→Questionnaire, policy→PlanDefinition(eca-rule)/Questionnaire(DTR)
- [X] T015 [US1] Update `_build_formalize_artifacts()` in `src/rh_skills/commands/promote.py` — populate `artifact_type` from actual L2 type (not fixed `pathway-package`), add `strategy` and `l3_targets` fields per data-model.md Entity 6
- [X] T016 [US1] Update `_render_formalize_plan()` in `src/rh_skills/commands/promote.py` — render strategy name, L3 target resource types, and type-specific required sections in the plan markdown
- [X] T017 [US1] Update formalize SKILL.md plan mode section in `skills/.curated/rh-inf-formalize/SKILL.md` — replace generic pathway-package instructions with type-specific strategy selection instructions; reference the 7-strategy table; instruct agent to read `artifact_type` from each L2 input and match to strategy
- [X] T018 [US1] Update formalize reference.md plan schema in `skills/.curated/rh-inf-formalize/reference.md` — update `artifacts[].artifact_type` from fixed `pathway-package` to actual L2 type; add `artifacts[].strategy` and `artifacts[].l3_targets` fields; update L3 target schema from YAML sections to FHIR resource types

### Tests for User Story 1 ⚠️

- [X] T019 [P] [US1] Write eval scenario for plan with `evidence-summary` input in `eval/scenarios/rh-inf-formalize/evidence-summary.yaml` — provide approved L2 evidence-summary, expect plan proposes Evidence + EvidenceVariable + Citation targets
- [X] T020 [P] [US1] Write eval scenario for plan with `decision-table` input in `eval/scenarios/rh-inf-formalize/decision-table.yaml` — provide approved L2 decision-table, expect plan proposes PlanDefinition (eca-rule) + Library targets
- [X] T021 [P] [US1] Write eval scenario for plan with `care-pathway` input in `eval/scenarios/rh-inf-formalize/care-pathway.yaml` — provide approved L2 care-pathway, expect plan proposes PlanDefinition (clinical-protocol) + ActivityDefinition targets
- [X] T022 [P] [US1] Write eval scenario for plan with `terminology` input in `eval/scenarios/rh-inf-formalize/terminology.yaml` — provide approved L2 terminology, expect plan proposes ValueSet + ConceptMap targets
- [X] T023 [P] [US1] Write eval scenario for plan with `measure` input in `eval/scenarios/rh-inf-formalize/measure.yaml` — provide approved L2 measure, expect plan proposes Measure + Library targets
- [X] T024 [P] [US1] Write eval scenario for plan with `assessment` input in `eval/scenarios/rh-inf-formalize/assessment.yaml` — provide approved L2 assessment, expect plan proposes Questionnaire target
- [X] T025 [P] [US1] Write eval scenario for plan with `policy` input in `eval/scenarios/rh-inf-formalize/policy.yaml` — provide approved L2 policy, expect plan proposes PlanDefinition (eca-rule) + Questionnaire (DTR) targets

**Checkpoint**: Plan mode produces type-specific strategies for all 7 L2 types. Each eval scenario validates the correct L3 target selection.

---

## Phase 4: User Story 2 — Type-specific implement execution (Priority: P1)

**Goal**: Implement mode applies correct conversion rules per L2 type, producing FHIR JSON + CQL via LLM with post-generation normalization/validation

**Independent Test**: Approve a plan for a `measure` artifact, run implement, confirm output contains `Measure-<id>.json` with `group[].population[]` and `Library-<id>.json` with CQL expressions.

### Implementation for User Story 2

- [ ] T026 [US2] Update formalize SKILL.md implement mode in `skills/.curated/rh-inf-formalize/SKILL.md` — replace generic combine instructions with: (1) read L2 artifact_type, (2) consult reference.md for type-specific conversion rules, (3) generate FHIR JSON per strategy, (4) call `rh-skills formalize <topic> <artifact>` for each artifact. Reference `docs/FORMALIZE_STRATEGIES.md` for detailed business rules.
- [ ] T027 [US2] Update formalize reference.md implement section in `skills/.curated/rh-inf-formalize/reference.md` — add per-type conversion rule summaries: L2 input shape → FHIR resource structure mapping, MCP tool usage per type (which searches/lookups needed), CQL generation guidance (when compilable vs stub), required FHIR fields per resource type. Source from `docs/FORMALIZE_STRATEGIES.md` sections §1–§7.
- [ ] T028 [US2] Build type-specific LLM system prompts in `src/rh_skills/commands/formalize.py` `formalize` command — for each `artifact_type`, construct a system prompt that includes: the specific FHIR resource type(s) to produce, required fields and structure, section mapping rules, CQL conventions. Use reference.md as the prompt source.
- [ ] T029 [US2] Implement FHIR JSON response parsing in `rh-skills formalize` command — parse LLM response as JSON array of FHIR resources, handle cases where LLM returns markdown-fenced JSON, split into individual resource files by resourceType
- [ ] T030 [US2] Wire normalization + validation into `rh-skills formalize` command — after LLM response parsed: run `fhir/normalize.py` on each resource dict, run `fhir/validate.py` for structural checks, warn on validation errors but still write (verify catches them later)

### Tests for User Story 2 ⚠️

- [ ] T031 [P] [US2] Extend eval scenarios (T019–T025) with implement phase — each scenario should include full plan→approve→implement cycle; expected outputs check for correct FHIR resourceType, required fields present, `computable_converged` event in tracking
- [ ] T032 [P] [US2] Update existing `eval/scenarios/rh-inf-formalize/converge-l2.yaml` for new output format — change expected outputs from `.yaml` to `.json` FHIR resources; update tracking checks for `files` (list) and `checksums` (dict)

**Checkpoint**: Implement produces FHIR JSON + CQL for all 7 L2 types. Each scenario validates structural correctness.

---

## Phase 5: User Story 3 — Type-specific verify validation (Priority: P2)

**Goal**: Verify mode checks type-appropriate completeness rules per strategy, not just generic section presence

**Independent Test**: Run verify on a Measure missing a denominator. Confirm it reports "Measure group missing denominator population" not generic "section incomplete."

### Implementation for User Story 3

- [ ] T033 [US3] Update formalize SKILL.md verify mode in `skills/.curated/rh-inf-formalize/SKILL.md` — replace generic section-presence checks with type-specific verification instructions: what to check per FHIR resource type, how to use MCP `codesystem_verify_code` for terminology validation, how to detect `TODO:MCP-UNREACHABLE` placeholders
- [ ] T034 [US3] Update formalize reference.md verify section in `skills/.curated/rh-inf-formalize/reference.md` — add per-type verification rules: PlanDefinition must have `action[]` with `condition[]` for eca-rule; Measure must have `group[].population[]` with numerator/denominator; Questionnaire must have `item[].linkId`; ValueSet must have `compose.include[]`; Evidence must have `certainty[]`; Library must have companion `.cql` file
- [ ] T035 [US3] Update `validate.py` L3 formalize validation in `src/rh_skills/commands/validate.py` — add type-specific completeness checks using `fhir/validate.py` module; check `converged_from` matches tracking entry; verify all expected resource files exist on disk; detect and report `TODO:MCP-UNREACHABLE` placeholders; exit non-zero on structural errors

### Tests for User Story 3 ⚠️

- [ ] T036 [P] [US3] Extend eval scenarios (T019–T025) with verify phase — each scenario should include plan→approve→implement→verify cycle; expected verify output confirms type-specific checks pass
- [ ] T037 [P] [US3] Add negative verify test cases to existing `tests/test_fhir_validate.py` (extends T006) — Measure missing denominator, Questionnaire missing linkId, PlanDefinition missing action, ValueSet empty compose, Evidence missing certainty, resource with MCP-UNREACHABLE placeholders

**Checkpoint**: Verify catches type-specific structural errors that generic checks would miss. All 7 types have verification rules.

---

## Phase 6: User Story 4 — Multi-type convergence (Priority: P2)

**Goal**: Formalize handles topics with multiple L2 types, applying each type's strategy independently and producing a coherent FHIR package

**Independent Test**: Run formalize plan on a topic with 3+ L2 types. Confirm per-type strategy selection and conflict detection for overlapping FHIR resource types.

### Implementation for User Story 4

- [ ] T038 [US4] Update formalize SKILL.md convergence instructions in `skills/.curated/rh-inf-formalize/SKILL.md` — add convergence section: (1) run plan for each L2 artifact with its type-specific strategy, (2) detect overlapping FHIR resource types across artifacts, (3) flag overlaps for reviewer resolution, (4) after approval, run `rh-skills formalize` per artifact sequentially, (5) run `rh-skills package` to bundle all computable resources
- [ ] T039 [US4] Update formalize reference.md convergence section in `skills/.curated/rh-inf-formalize/reference.md` — add merge precedence rules for common overlaps (e.g., two PlanDefinitions from decision-table + care-pathway: compose vs separate resources); add cross-reference binding rules (e.g., decision-table PlanDefinition references terminology ValueSet via canonical URL)
- [ ] T040 [US4] Implement overlap detection in `src/rh_skills/commands/formalize.py` or `promote.py` `_build_formalize_artifacts()` — when building plan for multiple artifacts, detect if two artifacts would produce the same FHIR resource type; add warning in plan markdown; require reviewer to document resolution

### Tests for User Story 4 ⚠️

- [ ] T041 [P] [US4] Write eval scenario for multi-type convergence in `eval/scenarios/rh-inf-formalize/multi-type-convergence.yaml` — provide 3+ L2 artifacts of different types (e.g., decision-table + terminology + measure), test full plan→approve→implement→verify→package cycle; verify each artifact uses correct strategy; verify package contains all resources; verify cross-references (ValueSet URLs in PlanDefinition conditions)
- [ ] T042 [P] [US4] Write eval scenario for resource type overlap in `eval/scenarios/rh-inf-formalize/convergence-overlap.yaml` — provide decision-table + care-pathway (both produce PlanDefinition), verify plan flags overlap for reviewer resolution

**Checkpoint**: Convergence produces coherent multi-type FHIR packages. Overlaps detected and surfaced.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, deprecation, and final validation

- [ ] T043 [P] Update `docs/FORMALIZE_STRATEGIES.md` open questions section — resolve or document decisions for open items (CQL `context Patient` explicit, minimum validate checks, inline vs project-level shared libraries)
- [ ] T044 [P] Add `rh-skills formalize` and `rh-skills package` to CLI help/documentation in relevant docs
- [ ] T045 Run `rh-skills validate` suite to ensure existing topics still work with updated tracking schema (backward compatibility for single-file `computable` entries)
- [ ] T046 Run all eval scenarios end-to-end to validate full pipeline
- [ ] T047 Run quickstart.md validation per `specs/011-formalize-strategies/quickstart.md`
- [ ] T048 Update or create worked examples under `skills/.curated/rh-inf-formalize/` demonstrating the new `rh-skills formalize` + `rh-skills package` workflow with FHIR JSON output — required by constitution Delivery Constraint ("curated skills MUST include worked examples")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS all user stories
- **US1 Plan (Phase 3)**: Depends on Foundational (Phase 2) — MVP starts here
- **US2 Implement (Phase 4)**: Depends on Foundational (Phase 2) — can parallel with US1 but eval scenarios extend US1's
- **US3 Verify (Phase 5)**: Depends on Foundational (Phase 2) — can parallel with US1/US2
- **US4 Convergence (Phase 6)**: Depends on US1 + US2 (needs both plan + implement type-specific)
- **Polish (Phase 7)**: Depends on all user stories

### User Story Dependencies

- **US1 (Plan)**: Independent after Foundational — no dependencies on other stories
- **US2 (Implement)**: Independent after Foundational — eval scenarios extend US1's but implementation is independent
- **US3 (Verify)**: Independent after Foundational — validation rules don't depend on plan/implement code
- **US4 (Convergence)**: Depends on US1 + US2 — convergence needs type-specific plan + implement

### Within Each User Story

- SKILL.md/reference.md updates before CLI code changes (skill contract defines behavior)
- CLI implementation before eval scenarios (scenarios test the implementation)
- Eval scenarios validate the story end-to-end

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 can all run in parallel (different files)
- **Phase 1**: T005, T006, T007 can all run in parallel (different test files)
- **Phase 2**: T012, T013 can run in parallel (different test files)
- **Phase 3**: T019–T025 can all run in parallel (independent eval scenario files)
- **Phase 5**: T036, T037 can run in parallel
- **Phase 6**: T041, T042 can run in parallel
- **Phase 7**: T043, T044 can run in parallel

---

## Parallel Example: Phase 1 Setup

```
# Launch all FHIR module implementations in parallel:
Task T002: "Implement normalization in src/rh_skills/fhir/normalize.py"
Task T003: "Implement validation in src/rh_skills/fhir/validate.py"
Task T004: "Implement packaging in src/rh_skills/fhir/packaging.py"

# Then launch all tests in parallel:
Task T005: "Test normalization in tests/test_fhir_normalize.py"
Task T006: "Test validation in tests/test_fhir_validate.py"
Task T007: "Test packaging in tests/test_fhir_packaging.py"
```

## Parallel Example: Phase 3 Eval Scenarios

```
# Launch all 7 type-specific eval scenarios in parallel:
Task T019: "evidence-summary eval scenario"
Task T020: "decision-table eval scenario"
Task T021: "care-pathway eval scenario"
Task T022: "terminology eval scenario"
Task T023: "measure eval scenario"
Task T024: "assessment eval scenario"
Task T025: "policy eval scenario"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3 = Plan Mode)

1. Complete Phase 1: Setup (FHIR module)
2. Complete Phase 2: Foundational (CLI commands)
3. Complete Phase 3: US1 — Type-specific plan generation
4. **STOP and VALIDATE**: Run eval scenarios for all 7 plan modes
5. This delivers type-aware formalize plans without changing implement/verify

### Incremental Delivery

1. Setup + Foundational → CLI commands functional
2. Add US1 (Plan) → Type-specific plan generation → Validate (MVP!)
3. Add US2 (Implement) → Type-specific FHIR JSON generation → Validate
4. Add US3 (Verify) → Type-specific verification → Validate
5. Add US4 (Convergence) → Multi-type packages → Validate
6. Polish → Documentation + backward compatibility → Final validation

---

## Requirement Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 (type-specific strategy selection) | T014, T015 |
| FR-002 (strategy defines L3 targets) | T014, T018, T027 |
| FR-003 (plan proposes strategy targets) | T015, T016, T017 |
| FR-004 (implement applies conversion rules) | T008, T026, T027, T028 |
| FR-005 (verify checks type-specific rules) | T033, T034, T035 |
| FR-006 (convergence merge precedence) | T038, T039, T040 |
| FR-007 (SKILL.md + reference.md document all 7) | T017, T018, T026, T027, T033, T034, T038, T039 |
| FR-008 (eval scenarios for all 7 types + convergence) | T019–T025, T041, T042 |
| FR-009 (unknown type fallback) | T008, T014, T011b |
| FR-010 (FHIR JSON output + computable_converged) | T008, T029, T030 |
| FR-011 (package command + package_created) | T009 |
| FR-012 (compilable CQL) | T027, T028 |
| SC-001 (all 7 types documented) | (pre-satisfied by FORMALIZE_STRATEGIES.md) |

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
