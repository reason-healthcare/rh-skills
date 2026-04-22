---
description: "Task list for 014-rh-cql-skill implementation"
---

# Tasks: rh-cql — First-Class CQL Authoring Skill

**Input**: Design documents from `/specs/014-rh-cql-skill/`
**Branch**: `014-rh-cql-skill`
**Spec**: 5 user stories, 33 FRs, 7 success criteria

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in each description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new file scaffolding and wire the `cql` command group into the CLI — all other phases depend on this.

- [X] T001 Create skill directory structure: `skills/.curated/rh-cql/`, `skills/.curated/rh-cql/examples/author-example/`, `skills/.curated/rh-cql/examples/review-example/`, and `tests/cql/` at repository root
- [X] T002 Add `RH_CLI_PATH` to `_CONFIG_KEYS` and add `[cql] rh_cli_path` TOML section mapping in `src/rh_skills/common.py` (follows existing pattern for `[llm.ollama]` etc.)
- [X] T003 Create `src/rh_skills/commands/cql.py` with a `cql_group` click group and stub sub-commands `validate`, `translate`, and `test` (each prints "not yet implemented" and exits 0)
- [X] T004 Register `cql_group` in the CLI entry point (`src/rh_skills/cli.py` or equivalent) so `rh-skills cql --help` shows the three sub-commands

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the `rh-skills cql` CLI commands (wrapping `rh cql`), create `reference.md`, and write the shared cross-cutting sections of `SKILL.md` (style guide, rubric, high-risk patterns, CLI/MCP boundary). All user-story phases depend on the CLI commands being real. US1–US4 each extend `SKILL.md` with their mode section.

**Independent test criteria**: `rh-skills cql validate <topic> <library>` calls `rh cql validate` as a subprocess, exits non-zero on errors, and emits an actionable message when `rh` is absent. All existing 611+ tests still pass.

- [X] T005 Implement `validate` command in `src/rh_skills/commands/cql.py`: resolve `.cql` path at `topics/<topic>/computable/<library>.cql`; resolve `rh` binary from `RH_CLI_PATH` env / config / PATH (emit install hint if absent); run `subprocess.run(["rh", "cql", "validate", cql_path])`; echo stdout/stderr; exit non-zero on translator errors
- [X] T006 [P] Implement `translate` command in `src/rh_skills/commands/cql.py`: same binary resolution as T005; run `rh cql compile <cql_path> --output <computable_dir>`; echo output path on success
- [X] T007 [P] Implement `test` command in `src/rh_skills/commands/cql.py`: discover `tests/cql/<library>/case-*/` directories; for each case load `expected/expression-results.json`; for each expression key run `rh cql eval <lib.cql> --expr <name> --data input/bundle.json`; diff actual stdout vs expected value; report PASS/FAIL per case; exit non-zero if any case fails
- [X] T008 Write `tests/unit/test_cql.py` — unit tests for `validate`: rh binary present + no errors → exit 0; rh binary present + errors → exit non-zero + error summary in output; rh binary absent → exit non-zero + "install" keyword in output
- [X] T009 [P] Add `translate` and `test` unit tests to `tests/unit/test_cql.py`: translate success → ELM file created + path echoed; test all-pass → exit 0 with PASS per case; test one-fail → exit non-zero with FAIL summary
- [X] T010 [P] Write `skills/.curated/rh-cql/reference.md` with all four corpus layers (Core CQL, FHIR-facing, Packaging/Lifecycle, Tooling) — each layer must have at minimum one URL per source and a relevance note (FR-007, SC-007)
- [X] T011 Write the shared sections of `skills/.curated/rh-cql/SKILL.md`: frontmatter; User Input block; CQL style guide (library naming, versioning, retrieve patterns, terminology rules, null/interval conventions, anti-pattern catalog — FR-005); authoring rubric (10 areas — FR-003); high-risk pattern catalog (7 categories with BLOCKING/ADVISORY classification — FR-004); CLI boundary section listing `rh-skills cql validate/translate/test` and `rh-skills formalize` as the deterministic write commands (FR-006); MCP tools section (reasonhub search/lookup); human-in-the-loop rules; file read/write table

---

## Phase 3: User Story 1 — Author Mode (P1)

**Story goal**: A clinical informaticist provides L2 structured artifacts; `rh-cql` in `author` mode produces a validated `.cql` library and FHIR Library wrapper.

**Independent test criteria**: SKILL.md `## Mode: author` section is present with correct inputs/outputs; `examples/author-example/output.md` contains a `.cql` library that passes `rh-skills cql validate`; `TestRhCqlSkillContract` in test_skill_audit.py passes.

- [X] T012 [US1] Write `## Mode: author` section in `skills/.curated/rh-cql/SKILL.md`: inputs (L2 structured artifact YAML from `structured/`); step-by-step authoring workflow using the rubric and style guide from Phase 2; CQL structure template (library header, using FHIR, valueset declarations, context Patient, define blocks); post-authoring step calling `rh-skills cql validate <topic> <library>` (FR-010); delegation to `rh-skills formalize` for FHIR Library wrapper (FR-011); output contract (`.cql` file + Library JSON) (FR-009, FR-012)
- [X] T013 [P] [US1] Write `skills/.curated/rh-cql/examples/author-example/plan.md`: input scenario — lipid-management topic, L2 structured assessment artifact with define names, FHIR R4 model, two valuesets with pinned versions; task description instructing author mode
- [X] T014 [P] [US1] Write `skills/.curated/rh-cql/examples/author-example/output.md`: complete CQL library (≥15 lines) matching the plan.md scenario, with explicit `library` header, `using FHIR`, pinned valueset declarations, `context Patient`, and ≥3 `define` statements; include rubric check results confirming all 10 areas pass (FR-008)
- [X] T015 [US1] Extend `tests/skills/test_skill_audit.py` with `TestRhCqlSkillContract` class: assert `rh-cql` SKILL.md defines all four mode names (`author`, `review`, `debug`, `test-plan`) by section heading; assert `reference.md` contains URLs for all four corpus layers; assert `examples/` contains both `author-example/` and `review-example/` subdirectories with `plan.md` and `output.md` (FR-006 audit)

---

## Phase 4: User Story 5 — Integration with rh-inf-formalize (P2)

**Story goal**: `rh-inf-formalize` no longer generates CQL stubs inline; all `.cql` content originates from `rh-cql`; boundary documented in both skills.

**Independent test criteria**: `formalize.py` contains no CQL string construction; `rh-inf-formalize` SKILL.md references `rh-cql`; test asserts no `.cql` file is written by `rh-skills formalize` alone without prior CQL content.

- [X] T016 [US5] Remove inline CQL stub generation from `src/rh_skills/commands/formalize.py` (lines ~355–376 that construct `library <Name> version '1.0.0'\n...`); replace with a comment block: `# CQL content is authored by the rh-cql skill. See skills/.curated/rh-cql/SKILL.md.` (FR-030, SC-005)
- [X] T017 [P] [US5] Add CQL boundary block to `skills/.curated/rh-inf-formalize/SKILL.md` in the Implement section: explain that for `measure`, `decision-table`, and `policy` artifact types, `.cql` must be authored by `rh-cql author` mode first, then `rh-skills formalize` wraps it in FHIR Library JSON; explicitly state formalize must NOT be called for `terminology` and `assessment` artifact types re CQL (FR-031, FR-032, FR-033)
- [X] T018 [P] [US5] Add CQL boundary block to `skills/.curated/rh-cql/SKILL.md` clarifying the reverse boundary: `rh-cql` owns CQL content generation; `rh-skills formalize` owns FHIR Library JSON wrapper; `rh-cql` must not attempt to write Library JSON directly (FR-033)
- [X] T019 [US5] Write test in `tests/unit/test_formalize.py` (new file or extend existing) asserting that running `rh-skills formalize <topic> <artifact>` for a Library-type artifact with no pre-existing `.cql` file does NOT create a `.cql` file (stub removal regression test)

---

## Phase 5: User Story 2 — Review Mode (P2)

**Story goal**: A reviewer provides an existing `.cql` file; `rh-cql` in `review` mode produces a structured Markdown report with BLOCKING/ADVISORY/INFO findings covering all rubric areas.

**Independent test criteria**: SKILL.md `## Mode: review` section is present; `examples/review-example/output.md` contains a report with all three finding levels and ≥1 finding per rubric area; report structure is parseable by `rh-skills verify` as review evidence (FR-017).

- [X] T020 [US2] Write `## Mode: review` section in `skills/.curated/rh-cql/SKILL.md`: inputs (`.cql` file path); review workflow iterating all 10 rubric areas, all 7 high-risk pattern categories, and 4 packaging concerns; report format template (BLOCKING/ADVISORY/INFO with quoted CQL excerpt + recommended fix per finding); output contract (review report Markdown at `topics/<topic>/process/reviews/<library>-review.md`) (FR-013, FR-014, FR-015, FR-016, FR-017)
- [X] T021 [P] [US2] Write `skills/.curated/rh-cql/examples/review-example/plan.md`: a CQL library scenario with at least 3 planted issues — one BLOCKING (unpinned terminology), one ADVISORY (broad retrieve filtered ad hoc), one INFO (minor style deviation)
- [X] T022 [P] [US2] Write `skills/.curated/rh-cql/examples/review-example/output.md`: review report for the plan.md scenario, with section headings for each rubric area, correctly classified findings with quoted CQL excerpts and recommended fixes (FR-008, SC-002)

---

## Phase 6: User Story 3 — Debug Mode (P3)

**Story goal**: A developer provides a `.cql` file plus a translator error, failing test, or runtime description; `rh-cql` in `debug` mode identifies root cause and proposes a minimal corrective change.

**Independent test criteria**: SKILL.md `## Mode: debug` section is present with distinct input types, diagnosis report template, and error taxonomy.

- [X] T023 [US3] Write `## Mode: debug` section in `skills/.curated/rh-cql/SKILL.md`: three accepted input forms (translator error from `rh-skills cql validate`, failing fixture with actual vs expected, runtime error description); diagnosis report template (root cause → responsible `define` → minimal patch); error taxonomy separating authoring errors from environment/configuration errors; examples of common error categories (temporal precision, null propagation, terminology mismatch, retrieve scope, unit conversion) (FR-018, FR-019, FR-020)

---

## Phase 7: User Story 4 — Test-Plan Mode (P3)

**Story goal**: A developer provides a `.cql` file; `rh-cql` in `test-plan` mode enumerates all `define` statements and produces a test plan Markdown and structurally valid fixture skeletons.

**Independent test criteria**: SKILL.md `## Mode: test-plan` section is present; fixture schema in `tests/cql/README.md` matches the spec (input/expected directories, JSON format); SC-003 formula (4×N cases) is stated explicitly.

- [X] T024 [US4] Write `## Mode: test-plan` section in `skills/.curated/rh-cql/SKILL.md`: workflow enumerating all non-context `define` statements; minimum case requirement (positive, negative, null/absent, boundary — SC-003: 4×N); test family matrix (age below/at/above; timing before/on/after; terminology match/non-match/missing; value present/absent/null; single/multiple/conflicting events); fixture skeleton structure; output contract (test plan Markdown at `topics/<topic>/process/test-plans/<library>-test-plan.md` + fixture directories at `tests/cql/<library>/`) (FR-021, FR-022, FR-023, FR-024)
- [X] T025 [P] [US4] Create `tests/cql/README.md` documenting the fixture directory schema: `case-NNN-<description>/input/` (patient.json, bundle.json, parameters.json) and `case-NNN-<description>/expected/` (expression-results.json with `{ "<define>": <value> }` format) with a `notes.md` per case; include a minimal worked example fixture pair
- [X] T026 [P] [US4] Create `tests/cql/example-library/case-001-basic-positive/` with structurally valid `input/bundle.json` (minimal FHIR R4 Bundle with one Patient resource), `expected/expression-results.json` (`{ "IsAdult": true }`), and `notes.md` explaining the fixture (FR-024, SC-003)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify all tests pass, all audit contracts are satisfied, and the feature is coherent end-to-end.

- [X] T027 Run `pytest tests/skills/test_skill_audit.py` and `pytest tests/unit/test_cql.py` — fix any failures; confirm `TestRhCqlSkillContract` passes and all prior skill audit tests still pass
- [X] T028 [P] Run full test suite (`pytest`) to confirm no regressions from formalize.py changes and CLI registration — target: all existing 611+ tests pass
- [X] T029 [P] Validate that `skills/.curated/rh-cql/reference.md` URLs for all four corpus layers are reachable (spot-check with `curl -sI <url>` for each source); fix any dead links

---

## Dependencies

```
Phase 1 (T001–T004) → ALL subsequent phases
Phase 2 (T005–T011) → Phase 3, 4, 5, 6, 7
Phase 3 (T012–T015) → Phase 4 (T018 needs SKILL.md author section for boundary note)
Phase 4 (T016–T019) → Phase 8 (formalize regression test must precede final test run)
Phase 5 (T020–T022) → Phase 8
Phase 6 (T023) → Phase 8
Phase 7 (T024–T026) → Phase 8
Phase 8 (T027–T029) → END
```

**Stories are mostly independent** — US1 (P1) should be delivered first as MVP. US5 (P2) and US2 (P2) can be done in either order after US1. US3 and US4 (both P3) are additive modes that do not block each other.

---

## Parallel Execution Examples

### Within Phase 2 (foundation CLI + content)
```
T005 (validate cmd) ──────────────────────┐
T006 (translate cmd) ─────────────────────┤─→ T008/T009 tests
T007 (test cmd) ──────────────────────────┘
T010 (reference.md) ─────────────────────────→ T015 audit tests
T011 (SKILL.md shared sections) ───────────→ T012 author mode
```

### Within Phase 3 (author mode)
```
T012 (SKILL.md author section) ──→ T015 (audit tests)
T013 (author example plan.md) ───┐
T014 (author example output.md) ─┘  (parallel, same dir, independent files)
```

### Within Phase 5 (review mode)
```
T020 (SKILL.md review section) → independent
T021 (review example plan.md) ─┐
T022 (review example output.md)┘  (parallel)
```

---

## Implementation Strategy

**MVP scope (Phase 1 + Phase 2 + Phase 3)**: Delivers a working `rh-skills cql` command group (validate/translate/test wrapping `rh`) plus `rh-cql` SKILL.md with `author` mode and the complete style guide and rubric. An agent can author, validate, and produce a FHIR Library wrapper. All audit tests pass.

**Increment 2 (Phase 4 + Phase 5)**: Removes the formalize stub (integration) and adds `review` mode. Together with MVP, this satisfies all P1 and P2 user stories and all integration requirements.

**Increment 3 (Phase 6 + Phase 7)**: Adds `debug` and `test-plan` modes plus the fixture schema. Satisfies all P3 user stories. Polish phase closes the feature.

---

## Task Summary

| Phase | Story | Task count |
|-------|-------|-----------|
| Setup | — | 4 |
| Foundational | — | 7 |
| US1 Author | P1 | 4 |
| US5 Integration | P2 | 4 |
| US2 Review | P2 | 3 |
| US3 Debug | P3 | 1 |
| US4 Test-plan | P3 | 3 |
| Polish | — | 3 |
| **Total** | | **29** |

**Parallel opportunities**: 14 tasks marked `[P]`
**MVP**: Phases 1–3 (15 tasks) — delivers working CLI + author mode
