# Tasks: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills`
**Input**: Design documents from `/specs/002-hi-agent-skills/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All paths relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the existing Python framework to support plan artifacts and the `skills/.curated/` namespace.

> **⚠️ NOTE**: Framework migrated to Python (click + ruamel.yaml + pytest). All bash/yq/bats tasks below are now Python equivalents. See `src/hi/` and `tests/`.

- [X] T001 ✅ Add `plans/` directory creation to `hi init` (`src/hi/commands/init.py`)
- [X] T002 [P] ✅ Markdown front matter parsing — handled in Python via ruamel.yaml; `common.py` has `sha256_file()`, `load_tracking()`, `save_tracking()`
- [X] T003 [P] ✅ SHA-256 checksum via `hashlib` in `src/hi/common.py` (`sha256_file()`)
- [X] T004 [P] ✅ Create `skills/.curated/` directory skeleton with 6 subdirectories: `hi-discovery/`, `hi-ingest/`, `hi-extract/`, `hi-formalize/`, `hi-verify/`, `hi-status/`

**Checkpoint**: ✅ Python helpers available; `hi init` creates `plans/` subdir; framework skill dirs exist.

---

## Phase 2: Foundational (`hi ingest` CLI)

**Purpose**: Build the deterministic CLI that all ingest-related SKILL.md files will invoke.

> **Status**: ✅ Fully implemented in `src/hi/commands/ingest.py`.

- [X] T005 ✅ `hi ingest` click group with `plan`/`implement`/`verify` subcommand routing (`src/hi/commands/ingest.py`)
- [X] T006 ✅ `hi ingest plan [--force]`: write `plans/ingest-plan.md` with YAML front matter template; re-run guard
- [X] T007 ✅ `hi ingest implement <file> [--force]`: copy to `sources/`, compute SHA-256, append `sources[]` entry in `tracking.yaml`, append `source_added` event
- [X] T008 ✅ Optional text extraction: detect `pdftotext` (PDF) and `pandoc` (Word/Excel); emit warning if tool absent; set `text_extracted` flag
- [X] T009 ✅ `hi ingest verify`: re-checksum all registered sources, report `✓ OK` or `✗ CHANGED`; exit 1 if any mismatch
- [ ] T010 [P] Create `tests/unit/test_ingest.py`: test `plan` creates `plans/ingest-plan.md` with YAML front matter; test `implement` registers source in `tracking.yaml` with correct checksum; test `verify` exits 0 for unchanged file; test `verify` detects modified file; test `implement` errors when file not found

**Checkpoint**: `hi ingest plan/implement/verify` fully functional and tested. Ready for SKILL.md authoring.

---

## Phase 3: User Story 1 — Guided Discovery (Priority: P1) 🎯 MVP

**Goal**: An agent skill that generates a structured source research plan and converts it to ingest tasks — no files registered yet.

**Independent Test**: `hi-discovery plan` on an empty topic produces `topics/<name>/plans/discovery-plan.md` with YAML front matter listing suggested sources. `hi-discovery implement` on that plan produces `topics/<name>/plans/ingest-plan.md`.

- [ ] T011 [US1] Create `skills/.curated/hi-discovery/SKILL.md` with YAML front matter: `name: hi-discovery`, `description: "Discover clinical sources for a topic. Modes: plan | implement"`, `compatibility`, `metadata.author`, `metadata.source`; include `## User Input` section with `$ARGUMENTS` and directive to parse first arg as mode
- [ ] T012 [US1] Write `plan` mode narrative in `skills/.curated/hi-discovery/SKILL.md`: (1) check if `topics/<name>/plans/discovery-plan.md` exists → warn and stop unless `--force`; (2) call `hi status <name>` and display output; (3) reason about the topic domain from `tracking.yaml` title/description; (4) produce `topics/<name>/plans/discovery-plan.md` with YAML front matter (`sources[]: {name, type, rationale, search_terms[], url_or_path?}`) and prose explaining each source; (5) append `discovery_planned` event to `tracking.yaml`
- [ ] T013 [US1] Write `implement` mode narrative in `skills/.curated/hi-discovery/SKILL.md`: (1) fail if no `topics/<name>/plans/discovery-plan.md` with clear error; (2) read YAML front matter from discovery plan; (3) for each source in `sources[]`, add an entry to `topics/<name>/plans/ingest-plan.md` YAML front matter; (4) write `topics/<name>/plans/ingest-plan.md`; (5) append `discovery_implemented` event to `tracking.yaml`; (6) print summary of sources added
- [ ] T014 [P] [US1] Create `tests/unit/test_discovery.py`: test that a fixture discovery-plan.md is parsed and produces ingest-plan.md with matching source entries

**Checkpoint**: US1 fully functional — discovery → ingest task list pipeline works end-to-end.

---

## Phase 4: User Story 2 — Raw Artifact Ingest with Change Detection (Priority: P1)

**Goal**: An agent skill that wraps `hi ingest` for human-guided registration and change detection.

**Independent Test**: Ingest a fixture file, modify it, run `hi ingest verify` via skill — changed file is flagged with original vs. current checksum.

- [ ] T015 [US2] Create `skills/.curated/hi-ingest/SKILL.md` with YAML front matter: `name: hi-ingest`, `description: "Ingest and track raw source artifacts. Modes: plan | implement | verify"`, `compatibility`, `metadata`; `$ARGUMENTS` block
- [ ] T016 [US2] Write `plan` mode narrative in `skills/.curated/hi-ingest/SKILL.md`: invoke `hi ingest plan`, display the generated `topics/<name>/plans/ingest-plan.md` content, instruct user to review YAML front matter (paths/URLs are editable), explain what `implement` will do next
- [ ] T017 [US2] Write `implement` mode narrative in `skills/.curated/hi-ingest/SKILL.md`: invoke `hi ingest implement <file>` for each source, report per-source results (✓ registered / ✗ failed), surface any `text_extracted: false` warnings with remediation hint (`brew install poppler` / `brew install pandoc`)
- [ ] T018 [US2] Write `verify` mode narrative in `skills/.curated/hi-ingest/SKILL.md`: invoke `hi ingest verify`, format results as a human-readable table (source name, status, checksum delta if changed), recommend `hi ingest implement --force` for changed files
- [ ] T019 [P] [US2] Add change-detection integration test to `tests/unit/test_ingest.py`: write fixture file → ingest → overwrite fixture → `hi ingest verify` must detect mismatch

**Checkpoint**: US2 complete — raw source files can be registered and change detection works.

---

## Phase 5: User Story 3 — Structured Extraction with Human Review (Priority: P2)

**Goal**: Agent skill that plans and executes structured (L2) derivation from sources with human review gate.

**Independent Test**: `hi-extract plan` on a topic with source artifacts produces `topics/<name>/plans/extract-plan.md`; `hi-extract implement` without the plan fails with clear error.

- [ ] T020 [US3] Create `skills/.curated/hi-extract/SKILL.md` with YAML front matter: `name: hi-extract`, `description: "Extract structured artifacts from sources. Modes: plan | implement | verify"`, `compatibility`, `metadata`; `$ARGUMENTS` block
- [ ] T021 [US3] Write `plan` mode narrative in `skills/.curated/hi-extract/SKILL.md`: (1) re-run guard for `topics/<name>/plans/extract-plan.md`; (2) call `hi list` or `hi status <topic>` to enumerate source artifacts; (3) analyze content and propose candidate structured artifact names + one-sentence descriptions; (4) write `topics/<name>/plans/extract-plan.md` with YAML front matter (`artifacts[]: {name, description, source_files[]}`) and prose; (5) append `extract_planned` event
- [ ] T022 [US3] Write `implement` mode narrative in `skills/.curated/hi-extract/SKILL.md`: (1) fail immediately with clear error if no `topics/<name>/plans/extract-plan.md`; (2) read `artifacts[]` from plan front matter; (3) for each artifact call `hi promote derive <topic> <name>`; (4) run `hi validate <topic> <name>` after each promote; (5) if validation fails surface the specific missing fields and skip the tracking event for that artifact; (6) append `structured_derived` event for each success
- [ ] T023 [US3] Write `verify` mode narrative in `skills/.curated/hi-extract/SKILL.md`: read `tracking.yaml` events to find last `structured_derived` batch; call `hi validate <topic> <artifact>` for each; format results as pass/fail table with field-level detail on failures
- [ ] T024 [P] [US3] Create `tests/unit/test_extract_skill.py`: test `plan` mode creates `extract-plan.md` (fixture topic with sources dir); test that checking for missing plan blocks implement

**Checkpoint**: US3 complete — structured derivation is gated behind human-reviewed plan.

---

## Phase 6: User Story 4 — Formalization with Human Review (Priority: P2)

**Goal**: Agent skill that plans and executes computable (L3) convergence from multiple structured artifacts, with FHIR completeness verification.

**Independent Test**: `hi-formalize plan` on a topic with ≥2 structured artifacts produces `topics/<name>/plans/formalize-plan.md` before any computable files are created.

- [ ] T025 [US4] Create `skills/.curated/hi-formalize/SKILL.md` with YAML front matter: `name: hi-formalize`, `description: "Formalize computable artifacts from structured sources. Modes: plan | implement | verify"`, `compatibility`, `metadata`; `$ARGUMENTS` block
- [ ] T026 [US4] Write `plan` mode narrative in `skills/.curated/hi-formalize/SKILL.md`: (1) re-run guard for `topics/<name>/plans/formalize-plan.md`; (2) enumerate validated structured artifacts via `hi status <topic>`; (3) reason about convergence — which structured artifacts should combine, what computable sections result; (4) write `topics/<name>/plans/formalize-plan.md` with YAML front matter (`sources_structured[], target_name, sections[]: {name, description, source_files[]}`) + draft outline prose; (5) append `formalize_planned` event
- [ ] T027 [US4] Write `implement` mode narrative in `skills/.curated/hi-formalize/SKILL.md`: (1) fail if no `topics/<name>/plans/formalize-plan.md`; (2) read `sources_structured[]` and `target_name` from plan front matter; (3) call `hi promote combine <topic> <sources...> <target>`; (4) run `hi validate <topic> <target>`; (5) append `computable_converged` event on success
- [ ] T028 [US4] Write `verify` mode narrative in `skills/.curated/hi-formalize/SKILL.md`: call `hi validate <topic> <artifact>`; additionally check FHIR-compatible completeness: `measures[]` entries have `numerator` and `denominator`; `value_sets[]` entries have `codes[]` array; report any sub-field gaps
- [ ] T029 [P] [US4] Create `tests/unit/test_formalize_skill.py`: test `plan` creates `formalize-plan.md` with required YAML fields; test `implement` fails with exit code when no plan exists

**Checkpoint**: US4 complete — computable artifacts produced and FHIR-completeness verified.

---

## Phase 7: User Story 5 — Housekeeping: Progress, Next Steps, Change Detection (Priority: P3)

**Goal**: CLI extensions for `hi status` plus SKILL.md wrappers that give teams actionable summaries. Plus standalone `hi-verify` skill.

**Independent Test**: `hi status diabetes-screening` on the example topic returns accurate artifact counts and lifecycle stage.

> **Note**: `hi status <topic>` basic output exists. Subcommands `progress`, `next-steps`, `check-changes` need to be added to `src/hi/commands/status.py`.

- [ ] T030 [US5] Extend `hi status` with `--progress` mode in `src/hi/commands/status.py`: output lifecycle stage (Discovery / Ingest / Extract / Formalize), source/structured/computable artifact counts, validation status summary, last event timestamp, completeness percentage
- [ ] T031 [US5] Extend `hi status` with `next-steps` subcommand in `src/hi/commands/status.py`: analyze `tracking.yaml` state machine (no sources → suggest ingest; sources but no structured → suggest extract; etc.); emit single most important next action with exact `hi` CLI command
- [ ] T032 [US5] Extend `hi status` with `check-changes` subcommand: re-checksum all sources entries from tracking.yaml; report changed/missing sources; for each changed source list the structured artifacts derived from it as potentially stale
- [ ] T033 [US5] Create `skills/.curated/hi-status/SKILL.md` with YAML front matter: `name: hi-status`, `description: "Topic lifecycle housekeeping. Modes: progress | next-steps | check-changes"`; write narrative for each mode that invokes the corresponding `hi status` CLI command and presents results with contextual guidance
- [ ] T034 [P] [US5] Create `skills/.curated/hi-verify/SKILL.md`: standalone non-modal skill; reads `$ARGUMENTS` as `<topic> <artifact-name>`; invokes `hi validate <topic> <artifact>` and presents field-level errors (blocking) and warnings (advisory); explicitly non-destructive
- [ ] T035 [P] [US5] Create `tests/unit/test_status_extended.py`: test `progress` outputs source/structured/computable counts for `diabetes-screening` fixture; test `next-steps` emits a runnable `hi` command; test `check-changes` detects modified fixture file

**Checkpoint**: US5 complete — teams have actionable progress summaries and change alerts.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T036 [P] Verify `hi list` correctly enumerates `topics/`; confirm `.curated/` skill dirs are excluded from topic listings
- [ ] T037 [P] Create `docs/GETTING_STARTED.md`: `uv tool install hi`, `hi init`, first topic walkthrough through all lifecycle stages referencing framework skills
- [ ] T038 [P] Create `docs/WORKFLOW.md`: sources→structured→computable lifecycle diagram, plan→implement→verify pattern, many-to-many artifact relationships (one source → multiple structured; multiple structured → one computable)
- [ ] T039 [P] Create `docs/COMMANDS.md`: full reference for all `hi` CLI commands including `hi ingest` and `hi status` subcommands
- [ ] T040 Run full integration test using `diabetes-screening` fixture: `hi init` → `hi-discovery plan` → `hi-discovery implement` → `hi ingest implement` (source registered, tracking.yaml sources[]) → `hi-extract plan` → `hi-extract implement` → `hi validate` → confirm all pass

**Checkpoint**: All user stories integrated, documented, and validated end-to-end.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: ✅ Complete
- **Phase 2 (Foundational)**: ✅ CLI complete; T010 (ingest tests) still needed
- **Phase 3 (US1)**: Can start — Phase 1 done; SKILL.md needs no bash dependency
- **Phase 4 (US2)**: Can start — Phase 2 CLI done; SKILL.md wraps `hi ingest`
- **Phase 5 (US3)**: Can start — `hi promote derive` exists in Python
- **Phase 6 (US4)**: After Phase 5 — needs structured artifacts to exist (logical dependency)
- **Phase 7 (US5)**: After Phase 2 — `check-changes` extends `hi ingest verify` logic
- **Phase 8 (Polish)**: After all user story phases

### Parallel Opportunities

```
# Phases 3-5 SKILL.md can be written in parallel (different files)
T011-T013 (hi-discovery SKILL.md)
T015-T018 (hi-ingest SKILL.md)
T020-T023 (hi-extract SKILL.md)

# Tests can be written alongside SKILL.md files
T010 (test_ingest.py)      — alongside Phase 2 completion
T014 (test_discovery.py)   — alongside T011-T013
T024 (test_extract_skill.py)— alongside T020-T023

# Phase 8: all docs tasks parallel
T037, T038, T039
```

---

## Implementation Strategy

### Next Up (Priority Order)

1. **T010**: `tests/unit/test_ingest.py` — close the test coverage gap on hi ingest
2. **Phase 3 (T011-T013)**: `hi-discovery` SKILL.md — MVP entry point
3. **Phase 4 (T015-T018)**: `hi-ingest` SKILL.md — wires discovery output to CLI
4. **Phase 5 (T020-T023)**: `hi-extract` SKILL.md — L2 derivation with human review
5. **Phase 6 (T025-T028)**: `hi-formalize` SKILL.md — L3 convergence
6. **Phase 7 (T030-T035)**: `hi status` extensions + `hi-status`/`hi-verify` SKILL.md
7. **Phase 8**: Docs + end-to-end integration test

### Incremental Delivery

- MVP: US1 + US2 → clinical teams can discover and register sources
- Add US3: structured extraction with human review gate
- Add US4: computable formalization with FHIR completeness check
- Add US5: progress summaries and housekeeping
- Final: docs, polish, end-to-end integration test

---

## Notes

- **Python stack**: `click` for CLI, `ruamel.yaml` for YAML round-trip, `pytest` for tests; install via `uv tool install hi`; dev via `uv sync && uv run hi`
- **SKILL.md mode dispatch**: First positional `$ARGUMENTS` word; narrative conditionals in body ("If the mode is `plan`...")
- **Re-run guard**: Every `plan`/`implement` mode warns+stops if output exists; `--force` overrides
- **No LLM in CLI**: `hi ingest` is pure Python — all reasoning stays in SKILL.md
- **`skills/.curated/`**: Excluded from `hi list` topic output (dot-prefix convention)
- **Optional tools**: `pdftotext`, `pandoc` — degrade gracefully, never hard-fail
- **Terminology**: sources (raw/L1), structured (L2), computable (L3); dirs: `sources/`, `topics/<name>/structured/`, `topics/<name>/computable/`
- **Plan artifacts**: live at `topics/<name>/plans/<skill>-plan.md` with YAML front matter + Markdown prose body
- Commit after each phase checkpoint

**Branch**: `002-hi-agent-skills`
**Input**: Design documents from `/specs/002-hi-agent-skills/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All paths relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the existing framework to support plan artifacts, markdown parsing, and the `skills/.curated/` namespace.

- [X] T001 ✅ Add `plans/` directory creation to `bin/hi-init` (add `mkdir -p "$topic_dir/plans"` alongside existing l1/l2/l3)
- [X] T002 [P] Add `hi_markdown_get_frontmatter_block()`, `hi_markdown_get_field()`, `hi_markdown_get_content()` helper functions to `bin/common.sh` (portable bash 3.2+ using `sed -n '1,/^---$/p'` pattern from research.md)
- [X] T003 [P] Add `hi_sha256()` portable checksum function to `bin/common.sh` (detect `sha256sum` vs `shasum -a 256` via `command -v` at runtime; no `declare -A`)
- [X] T004 [P] Create `skills/.curated/` directory skeleton with 6 subdirectories: `hi-discovery/`, `hi-ingest/`, `hi-extract/`, `hi-formalize/`, `hi-verify/`, `hi-status/`

**Checkpoint**: common.sh helpers available; `hi init` creates plans/ subdir; framework skill dirs exist.

---

## Phase 2: Foundational (`bin/hi-ingest` CLI)

**Purpose**: Build the deterministic CLI that all ingest-related SKILL.md files will invoke. This blocks US2 and partially US1 (ingest plan output).

**⚠️ CRITICAL**: SKILL.md files for hi-ingest (US2) and hi-status check-changes (US5) depend on this CLI being complete.

- [ ] T005 Create `bin/hi-ingest` dispatcher: argument parsing, `plan`/`implement`/`verify` subcommand routing, usage/help text, exit codes matching existing `bin/hi-*` conventions
- [ ] T006 Implement `hi ingest plan <skill> [--force]` in `bin/hi-ingest`: read `topics/<topic>/plans/discovery-plan.md` front matter (if exists) for source hints, write `topics/<topic>/plans/ingest-plan.md` with YAML front matter (`sources[]: {name, path_or_url, type}`) + Markdown prose; re-run guard: warn and exit 0 if plan exists and `--force` not set
- [ ] T007 Implement `hi ingest implement <skill> [--force]` in `bin/hi-ingest`: read `plans/ingest-plan.md` YAML front matter via `hi_markdown_get_frontmatter_block` + `yq`, copy each source file to `topics/<topic>/l1/`, compute SHA-256 via `hi_sha256()`, append `sources[]` entry (name, path, type, checksum, ingested_at, text_extracted) to `topics/<topic>/tracking.yaml`, append `l1_added` event; fail with exit 2 if no ingest-plan.md
- [ ] T008 Implement optional text extraction in `bin/hi-ingest implement`: detect `pdftotext` (PDF) and `pandoc` (Word/Excel) via `command -v`; extract text to `<name>.txt` alongside l1 artifact if tool available and set `text_extracted: true`; if tool absent emit `[WARN] text extraction skipped: pdftotext not found` and set `text_extracted: false`; exit 0 in both cases
- [ ] T009 Implement `hi ingest verify <skill>` in `bin/hi-ingest`: read all `sources[]` from `tracking.yaml` via `yq`, re-checksum each file with `hi_sha256()`, print `✓ <name>  OK` or `✗ <name>  CHANGED (was <old> now <new>)` per source, exit 1 if any mismatch
- [ ] T010 [P] Create `tests/hi-ingest.bats`: test `plan` creates `plans/ingest-plan.md` with YAML front matter; test `implement` registers source in `tracking.yaml` with correct checksum; test `verify` exits 0 for unchanged file; test `verify` exits 1 and reports checksum for modified file; test `implement` exits 2 when no ingest-plan.md

**Checkpoint**: `bin/hi-ingest plan/implement/verify` fully functional and tested. Ready for SKILL.md authoring.

---

## Phase 3: User Story 1 — Guided Discovery (Priority: P1) 🎯 MVP

**Goal**: An agent skill that generates a structured source research plan and converts it to ingest tasks — no files registered yet.

**Independent Test**: `hi-discovery plan` on an empty skill produces `plans/discovery-plan.md` with YAML front matter listing suggested sources. `hi-discovery implement` on that plan produces `plans/ingest-plan.md`.

- [ ] T011 [US1] Create `skills/.curated/hi-discovery/SKILL.md` with YAML front matter: `name: hi-discovery`, `description: "Discover clinical sources for a skill. Modes: plan | implement"`, `compatibility`, `metadata.author`, `metadata.source`; include `## User Input` section with `$ARGUMENTS` and directive to parse first arg as mode
- [ ] T012 [US1] Write `plan` mode narrative in `skills/.curated/hi-discovery/SKILL.md`: (1) check if `topics/<name>/plans/discovery-plan.md` exists → warn and stop unless `--force`; (2) call `hi status progress <name>` and display output; (3) reason about the skill domain from `tracking.yaml` title/description; (4) produce `plans/discovery-plan.md` with YAML front matter (`sources[]: {name, type, rationale, search_terms[], url_or_path?}`) and prose explaining each source; (5) append `discovery_planned` event to `tracking.yaml`
- [ ] T013 [US1] Write `implement` mode narrative in `skills/.curated/hi-discovery/SKILL.md`: (1) fail if no `plans/discovery-plan.md` with clear error; (2) call `hi_markdown_get_frontmatter_block` equivalent (instruct agent to read YAML front matter); (3) for each source in `sources[]`, add an entry to `plans/ingest-plan.md` YAML front matter; (4) write `plans/ingest-plan.md`; (5) append `discovery_implemented` event to `tracking.yaml`; (6) print summary of sources added
- [ ] T014 [P] [US1] Create `tests/hi-discovery.bats`: test that a fixture discovery-plan.md is parsed and produces ingest-plan.md with matching source entries (use `bats` helper to write fixture, invoke skill in a subshell or check file output)

**Checkpoint**: US1 fully functional — discovery → ingest task list pipeline works end-to-end.

---

## Phase 4: User Story 2 — Raw Artifact Ingest with Change Detection (Priority: P1)

**Goal**: An agent skill that wraps `bin/hi-ingest` for human-guided registration and change detection.

**Independent Test**: Ingest a fixture file, modify it, run `hi-ingest verify` via skill — changed file is flagged with original vs. current checksum.

- [ ] T015 [US2] Create `skills/.curated/hi-ingest/SKILL.md` with YAML front matter: `name: hi-ingest`, `description: "Ingest and track raw source artifacts. Modes: plan | implement | verify"`, `compatibility`, `metadata`; `$ARGUMENTS` block
- [ ] T016 [US2] Write `plan` mode narrative in `skills/.curated/hi-ingest/SKILL.md`: invoke `hi ingest plan <skill>`, display the generated `plans/ingest-plan.md` content, instruct user to review YAML front matter (paths/URLs are editable), explain what `implement` will do next
- [ ] T017 [US2] Write `implement` mode narrative in `skills/.curated/hi-ingest/SKILL.md`: invoke `hi ingest implement <skill>`, report per-source results (✓ registered / ✗ failed), surface any `text_extracted: false` warnings with remediation hint (`brew install poppler` / `brew install pandoc`)
- [ ] T018 [US2] Write `verify` mode narrative in `skills/.curated/hi-ingest/SKILL.md`: invoke `hi ingest verify <skill>`, format results as a human-readable table (source name, status, checksum delta if changed), recommend `hi ingest implement --force <skill>` for changed files
- [ ] T019 [P] [US2] Add change-detection integration test to `tests/hi-ingest.bats`: write fixture file → ingest → overwrite fixture → `hi ingest verify` must exit 1 with checksum mismatch output

**Checkpoint**: US2 complete — raw source files can be registered and change detection works.

---

## Phase 5: User Story 3 — Structured L2 Extraction with Human Review (Priority: P2)

**Goal**: Agent skill that plans and executes L2 derivation from L1 artifacts with human review gate.

**Independent Test**: `hi-extract plan` on a skill with L1 artifacts produces `plans/extract-plan.md`; `hi-extract implement` without the plan fails with clear error.

- [ ] T020 [US3] Create `skills/.curated/hi-extract/SKILL.md` with YAML front matter: `name: hi-extract`, `description: "Extract structured L2 artifacts from L1 sources. Modes: plan | implement | verify"`, `compatibility`, `metadata`; `$ARGUMENTS` block
- [ ] T021 [US3] Write `plan` mode narrative in `skills/.curated/hi-extract/SKILL.md`: (1) re-run guard for `plans/extract-plan.md`; (2) call `hi list <skill>` or `hi status progress <skill>` to enumerate L1 artifacts; (3) analyze content and propose candidate L2 artifact names + one-sentence descriptions; (4) write `plans/extract-plan.md` with YAML front matter (`artifacts[]: {name, description, source_l1s[]}`) and prose; (5) append `extract_planned` event
- [ ] T022 [US3] Write `implement` mode narrative in `skills/.curated/hi-extract/SKILL.md`: (1) fail immediately with clear error if no `plans/extract-plan.md`; (2) read `artifacts[]` from plan front matter; (3) for each artifact call `hi promote derive <skill> <name>`; (4) run `hi validate <skill> <name>` after each promote; (5) if validation fails surface the specific missing fields and skip the tracking event for that artifact; (6) append `extract_implemented` event for each success
- [ ] T023 [US3] Write `verify` mode narrative in `skills/.curated/hi-extract/SKILL.md`: read `tracking.yaml` events to find last `extract_implemented` batch; call `hi validate <skill> <artifact>` for each; format results as pass/fail table with field-level detail on failures
- [ ] T024 [P] [US3] Create `tests/hi-extract.bats`: test `plan` mode creates `extract-plan.md` (fixture skill with l1 dir); test that checking for missing plan blocks implement (fixture without extract-plan.md)

**Checkpoint**: US3 complete — L2 derivation is gated behind human-reviewed plan.

---

## Phase 6: User Story 4 — L3 Formalization with Human Review (Priority: P2)

**Goal**: Agent skill that plans and executes L3 convergence from multiple L2 artifacts, with FHIR completeness verification.

**Independent Test**: `hi-formalize plan` on a skill with ≥2 L2 artifacts produces `plans/formalize-plan.md` before any L3 files are created.

- [ ] T025 [US4] Create `skills/.curated/hi-formalize/SKILL.md` with YAML front matter: `name: hi-formalize`, `description: "Formalize L3 computable artifacts from L2 structures. Modes: plan | implement | verify"`, `compatibility`, `metadata`; `$ARGUMENTS` block
- [ ] T026 [US4] Write `plan` mode narrative in `skills/.curated/hi-formalize/SKILL.md`: (1) re-run guard for `plans/formalize-plan.md`; (2) enumerate validated L2 artifacts via `hi status progress <skill>`; (3) reason about convergence — which L2s should combine, what L3 sections result; (4) write `plans/formalize-plan.md` with YAML front matter (`sources_l2[], target_l3_name, sections[]: {name, description, source_l2s[]}`) + draft outline prose; (5) append `formalize_planned` event
- [ ] T027 [US4] Write `implement` mode narrative in `skills/.curated/hi-formalize/SKILL.md`: (1) fail if no `plans/formalize-plan.md`; (2) read `sources_l2[]` and `target_l3_name` from plan front matter; (3) call `hi promote combine <skill> <sources...> <target>`; (4) run `hi validate <skill> <target>`; (5) append `formalize_implemented` event on success
- [ ] T028 [US4] Write `verify` mode narrative in `skills/.curated/hi-formalize/SKILL.md`: call `hi validate <skill> <l3-artifact>`; additionally check FHIR-compatible completeness: `measures[]` entries have `numerator` and `denominator`; `value_sets[]` entries have `codes[]` array; report any sub-field gaps
- [ ] T029 [P] [US4] Create `tests/hi-formalize.bats`: test `plan` creates `formalize-plan.md` with required YAML fields; test `implement` fails with exit code when no plan exists

**Checkpoint**: US4 complete — L3 computable artifacts produced and FHIR-completeness verified.

---

## Phase 7: User Story 5 — Housekeeping: Progress, Next Steps, Change Detection (Priority: P3)

**Goal**: CLI extensions for `bin/hi-status` plus SKILL.md wrappers that give teams actionable summaries. Plus standalone `hi-verify` skill.

**Independent Test**: `hi status progress diabetes-screening` on the example skill returns accurate artifact counts and lifecycle stage.

- [ ] T030 [US5] Extend `bin/hi-status` with `progress <skill>` subcommand: read `tracking.yaml` via `yq`, output lifecycle stage (Discovery / Ingest / Extract / Formalize), L1/L2/L3 artifact counts, validation status summary, last event timestamp, completeness percentage
- [ ] T031 [US5] Extend `bin/hi-status` with `next-steps <skill>` subcommand: analyze `tracking.yaml` state machine (no plan → suggest discovery plan; plan but no ingest → suggest ingest; l1 but no l2 → suggest extract; etc.); emit single most important next action with exact `hi` CLI command
- [ ] T032 [US5] Extend `bin/hi-status` with `check-changes <skill>` subcommand: internally call `hi ingest verify <skill>` logic, report changed/missing sources; for each changed L1 file list the L2 artifacts derived from it (via `tracking.yaml` events `source` fields) as potentially stale
- [ ] T033 [US5] Create `skills/.curated/hi-status/SKILL.md` with YAML front matter: `name: hi-status`, `description: "Skill lifecycle housekeeping. Modes: progress | next-steps | check-changes"`; write narrative for each mode that invokes the corresponding `hi status <mode> <skill>` CLI command and presents results with contextual guidance
- [ ] T034 [P] [US5] Create `skills/.curated/hi-verify/SKILL.md`: standalone non-modal skill (no mode argument); reads `$ARGUMENTS` as `<skill> <artifact-name>`; invokes `hi validate <skill> <artifact>` and presents field-level errors (blocking) and warnings (advisory); explicitly non-destructive — never modifies any file
- [ ] T035 [P] [US5] Create `tests/hi-status.bats`: test `progress` outputs L1/L2/L3 counts for `diabetes-screening` fixture; test `next-steps` emits a runnable `hi` command; test `check-changes` detects modified fixture file

**Checkpoint**: US5 complete — teams have actionable progress summaries and change alerts.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T036 [P] Verify `bin/hi-list` correctly enumerates `topics/` (already uses `hi_topics_root()`); add `--verbose` flag showing per-topic artifact counts and last-event timestamps
- [ ] T037 [P] Create `docs/GETTING_STARTED.md`: installation, `hi init`, first skill walkthrough through all lifecycle stages referencing framework skills
- [ ] T038 [P] Create `docs/WORKFLOW.md`: L1→L2→L3 lifecycle diagram, plan→implement→verify pattern, many-to-many artifact relationships (one L1 → multiple L2; multiple L2 → one L3)
- [ ] T039 [P] Create `docs/COMMANDS.md`: full reference for all `hi` CLI commands including new `hi ingest` and `hi status progress/next-steps/check-changes` subcommands
- [ ] T040 Run full integration test using `diabetes-screening` fixture: `hi init` (plans/ created) → `hi-discovery plan` (discovery-plan.md) → `hi-discovery implement` (ingest-plan.md) → `hi ingest implement` (l1 registered, tracking.yaml sources[]) → `hi-extract plan` → `hi-extract implement` → `hi validate` → confirm all pass

**Checkpoint**: All user stories integrated, documented, and validated end-to-end.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T002, T003, T004 can run in parallel
- **Phase 2 (Foundational)**: Depends on Phase 1; T005–T010 sequential (T006 needs T005, T007 needs T006, T008 needs T007)
- **Phase 3 (US1)**: Depends on Phase 1 only (discovery SKILL.md needs common.sh helpers); can start after T001–T004
- **Phase 4 (US2)**: Depends on Phase 2 (bin/hi-ingest CLI must exist)
- **Phase 5 (US3)**: Depends on Phase 1 (`hi promote derive` is existing)
- **Phase 6 (US4)**: Depends on Phase 5 (needs L2 artifacts)
- **Phase 7 (US5)**: Depends on Phase 2 (check-changes needs bin/hi-ingest verify)
- **Phase 8 (Polish)**: Depends on all user story phases being complete

### User Story Dependencies

- **US1 (P1)**: After Phase 1 — no dependency on US2–US5
- **US2 (P1)**: After Phase 2 — no dependency on US1 (independent)
- **US3 (P2)**: After Phase 1 — no dependency on US1/US2 for the SKILL.md; uses existing `hi promote derive`
- **US4 (P2)**: After US3 — needs L2 artifacts to exist (logical dependency)
- **US5 (P3)**: After Phase 2 — no dependency on US1–US4 for CLI; SKILL.md wraps existing commands

### Within Each Phase

- SKILL.md front matter and mode narratives can be written in one pass (all in one file)
- Tests can be written in parallel with SKILL.md (T014 alongside T011–T013)
- `bin/hi-ingest` subcommands must be sequential: dispatcher → plan → implement → text extraction → verify

### Parallel Opportunities

```bash
# Phase 1: all four setup tasks in parallel
Task: T001 Add plans/ to hi-init
Task: T002 Add markdown helpers to common.sh
Task: T003 Add hi_sha256 to common.sh
Task: T004 Create skills/.curated/ dirs

# Phase 2: test file can be started while implementing
Task: T005–T009 sequential implementation
Task: T010 tests can be written alongside T007

# User stories: US1 and US2 can proceed in parallel after their prereqs
Task: T011–T013 (hi-discovery SKILL.md)
Task: T015–T018 (hi-ingest SKILL.md — after Phase 2)

# Phase 8: all docs tasks parallel
Task: T037 GETTING_STARTED.md
Task: T038 WORKFLOW.md
Task: T039 COMMANDS.md
Task: T036 Update hi-list
```

---

## Implementation Strategy

### MVP (User Stories 1 + 2 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (bin/hi-ingest CLI)
3. Complete Phase 3 (US1 — hi-discovery SKILL.md)
4. Complete Phase 4 (US2 — hi-ingest SKILL.md)
5. **STOP and VALIDATE**: full discovery → ingest cycle on `diabetes-screening`
6. Confirm: `plans/` directory created, discovery-plan.md written, sources registered in tracking.yaml, change detection works

### Incremental Delivery

- MVP: US1 + US2 → clinical teams can discover and register sources
- Add US3: L2 extraction with human review gate
- Add US4: L3 formalization with FHIR completeness check
- Add US5: Progress summaries and housekeeping
- Final: docs, polish, end-to-end integration test

---

## Notes

- **bash 3.2+ portability**: No `mapfile`, no `${var^}`, no `declare -A`, no `${//}` — see research.md and CLAUDE.md for full rules
- **`sed` separator**: Use `-e 's/a/b/'` not semicolon syntax (GNU-only)
- **SKILL.md mode dispatch**: First positional `$ARGUMENTS` word; narrative conditionals in body ("If the mode is `plan`...")
- **Re-run guard**: Every `plan`/`implement` mode warns+stops if output exists; `--force` overrides
- **No LLM in CLI**: `bin/hi-ingest` is pure bash — all reasoning stays in SKILL.md
- **`skills/.curated/`**: Excluded from `hi list` output (underscore prefix convention)
- **Optional tools**: `pdftotext`, `pandoc` — degrade gracefully, never hard-fail
- Commit after each phase checkpoint
