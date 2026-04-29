---
description: "Tasks for 003-rh-inf-discovery — rh-inf-discovery interactive research assistant skill"
---

# Tasks: `rh-inf-discovery` — Healthcare Informatics Discovery Skill

**Input**: Design documents from `/specs/003-rh-inf-discovery/`
**Branch**: `003-rh-inf-discovery`
**Spec**: User Stories: US1 (P1) — Research from scratch, US2 (P1) — Iterative expansion, US3 (P2) — Verify coverage

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2, US3
- All paths are relative to repository root

---

## Phase 1: Setup (Dependencies)

**Purpose**: Add new dependencies required by `rh-skills search` and URL download.

- [X] T001 Add `httpx>=0.27` to `[project.dependencies]` in `pyproject.toml` and run `uv sync` to install
- [X] T002 [P] Add `pytest-httpx>=0.30` to `[project.optional-dependencies.dev]` in `pyproject.toml` for HTTP mocking in tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core API helpers and CLI scaffolding that all user story commands depend on.

- [X] T003 Create `src/rh_skills/commands/search.py` with a `search` click group (no subcommands yet); register it in `src/rh_skills/cli.py` with `main.add_command(search.search)`
- [X] T004 Implement `_entrez_search_fetch(query, db, max_results, api_key)` helper function in `src/rh_skills/commands/search.py` — performs NCBI esearch (`retmode=json`) then efetch (`rettype=xml`) two-step, parses PubMed XML via `xml.etree.ElementTree`, respects rate limit (0.34s sleep without key; 0.11s with `NCBI_API_KEY`); returns list of dicts with keys: `id`, `title`, `url`, `year`, `journal`, `open_access`, `pmcid`, `abstract_snippet`
- [X] T005 [P] Implement `_clinicaltrials_search(query, max_results, status_filter)` helper function in `src/rh_skills/commands/search.py` — calls ClinicalTrials.gov REST API v2 (`GET https://clinicaltrials.gov/api/v2/studies`), parses JSON, returns list of dicts with keys: `id`, `title`, `url`, `year`, `journal`, `open_access`, `pmcid`, `abstract_snippet` (journal and pmcid are null; open_access always true)

---

## Phase 3: User Story 1 — Research a Clinical Topic from Scratch (P1)

**Story goal**: A clinical informaticist runs `rh-inf-discovery` on a new topic, receives domain advice, searches PubMed/PMC/ClinicalTrials, curates sources with access advisories, and saves a living discovery plan to disk.

**Independent test criteria**:
1. `rh-skills search pubmed --query "sepsis management" --json` returns valid JSON with ≥1 result (mocked)
2. `rh-skills search pmc --query "sepsis management" --json` returns results with `open_access: true`
3. `rh-skills search clinicaltrials --query "sepsis" --json` returns NCT ID results
4. `rh-inf-discovery plan <topic> --domain <label>` produces `topics/<topic>/process/plans/discovery-plan.yaml` with sources[], access types, and auth_notes
5. `rh-skills validate --plan topics/<topic>/process/plans/discovery-plan.yaml` exits 0 on a valid plan
6. `rh-skills init diabetes-ccm` creates `RESEARCH.md` at root and `topics/diabetes-ccm/process/notes.md`
7. SKILL.md passes `tests/skills/` parametrized suite

- [X] T006 [US1] Implement `rh-skills search pubmed` subcommand in `src/rh_skills/commands/search.py` — wires `_entrez_search_fetch(db="pubmed")`; options: `--query` (required), `--max 20`, `--filter TEXT`, `--api-key TEXT` (env: `NCBI_API_KEY`); human-readable stdout format per contracts/rh-search.md; exit 0 (success), 1 (network error), 2 (zero results)
- [X] T007 [P] [US1] Implement `rh-skills search pmc` subcommand in `src/rh_skills/commands/search.py` — reuses `_entrez_search_fetch(db="pmc")`; sets `open_access: true` on all results; same options and exit codes as `rh-skills search pubmed`
- [X] T008 [US1] Implement `rh-skills search clinicaltrials` subcommand in `src/rh_skills/commands/search.py` — wires `_clinicaltrials_search()`; options: `--query` (required), `--max 20`, `--status "COMPLETED,RECRUITING"`; human-readable stdout; exit 0/1/2
- [X] T009 [US1] Add `--json` flag to all three `rh-skills search` subcommands in `src/rh_skills/commands/search.py`; emit structured JSON to stdout per the `rh-skills search` Result schema in `specs/003-rh-inf-discovery/data-model.md` Entity 3; `--json` and human-readable are mutually exclusive output paths
- [X] T010 [P] [US1] Write `tests/unit/test_search_pubmed.py` — use `pytest-httpx` to mock NCBI esearch + efetch HTTP calls; test: successful result list, `open_access: true` when pmcid present, zero-results exits 2, network error exits 1, `--json` output matches Entity 3 schema, rate-limit sleep called
- [X] T011 [P] [US1] Write `tests/unit/test_search_clinicaltrials.py` — use `pytest-httpx` to mock ClinicalTrials.gov v2 API; test: result list parsed correctly, `open_access: true` always set, zero results exits 2, `--json` output matches schema
- [X] T012 [US1] [MOVED TO source.py] Implement URL acquisition in `rh-skills source download` (`src/rh_skills/commands/source.py`) using `--url` and `--name`; downloads via httpx, detects MIME, writes `sources/<name>.<ext>`, computes SHA-256, appends `source_added` event to `tracking.yaml`, and prints download summary.
- [X] T013 [US1] [MOVED TO source.py] Add auth-redirect detection to `rh-skills source download --url` in `src/rh_skills/commands/source.py` — after redirect chain resolves, check if final URL contains `login`, `signin`, `auth`, or `access-denied`; if true: print access advisory (source URL, final redirect URL, manual retrieval instructions) and exit 3 without writing any file
- [X] T014 [P] [US1] [MOVED TO 004-rh-inf-ingest] Write `tests/unit/test_ingest_url.py` — use `pytest-httpx` to mock HTTP responses; test: successful PDF download (SHA-256 computed, file written, tracking.yaml event appended), MIME detection (pdf → `.pdf`, html → `.html`), auth-redirect exit 3 (no file written), already-exists exit 2 (no overwrite), network error exit 1
- [X] T015 [US1] Extend `rh-skills init` in `src/rh_skills/commands/init.py` to create `RESEARCH.md` at repo root if not already present using the canonical format from `specs/003-rh-inf-discovery/data-model.md` Entity 4; then append one Active Topics row `| <topic> | initialized | 0 | <date> | <date> | |`; if `RESEARCH.md` already exists, append row only (idempotent: skip if topic row already present)
- [X] T016 [US1] Extend `rh-skills init` in `src/rh_skills/commands/init.py` to create `topics/<name>/process/notes.md` with the canonical stub format (`# Research Notes — <topic>` header; `## Open Questions`, `## Decisions`, `## Source Conflicts`, `## Notes` sections with placeholder comments) per `specs/003-rh-inf-discovery/data-model.md` Entity 5; skip creation if file already exists
- [X] T017 [P] [US1] Write `tests/unit/test_init_research.py` — test: first `rh-skills init` creates both `RESEARCH.md` and `process/notes.md`, second `rh-skills init` on different topic appends row to existing `RESEARCH.md` without corrupting existing rows, duplicate init is idempotent, process/notes.md contains all four section headers (Open Questions, Decisions, Source Conflicts, Notes)
- [X] T018 [US1] Write `skills/.curated/rh-inf-discovery/SKILL.md` — frontmatter (name, description, modes: plan/verify, context_files: reference.md + examples/plan.yaml + examples/output.md, lifecycle_stage: l1-discovery, reads_from/writes_via_cli per spec FR-021); Overview section; plan mode step-by-step instructions (steps 1–12 from `specs/003-rh-inf-discovery/research.md` Decision 7): check topic initialized → domain advice → search pubmed → search clinicaltrials → search pmc → curate sources → present to user → print authenticated source advisories → present expansion suggestions → prompt user → save (writes `topics/<topic>/process/plans/discovery-plan.yaml` + `topics/<topic>/process/plans/discovery-readout.md`; creates `notes.md` stub; downloads open-access sources after save); include FR-015 warning (existing plan detection), `--dry-run` behavior (no writes)
- [X] T019 [US1] Add plan save instructions to `skills/.curated/rh-inf-discovery/SKILL.md` — agent writes `topics/<topic>/process/plans/discovery-plan.yaml` (pure YAML, per data-model.md Entity 2) and `topics/<topic>/process/plans/discovery-readout.md` (generated narrative with Domain Advice and Research Expansion Suggestions, per data-model.md Entity 2b); creates `process/notes.md` stub (create-unless-exists); updates RESEARCH.md Active Topics row (source count + date)

---

## Phase 4: User Story 2 — Iterative Research Expansion (P1)

**Story goal**: After the initial pass, the user asks the agent to expand into adjacent areas (economics, SDOH, comorbidities). The agent adds new sources to the living plan, respects the 25-source cap, and prompts for save checkpoints.

**Independent test criteria**:
1. SKILL.md plan mode includes Expansion Suggestions section with ≥3 prompts after initial pass
2. SKILL.md instructs agent to warn when 25-source cap is reached and move surplus to expansion candidates
3. SKILL.md instructs agent to search additional DBs when plan has <5 sources
4. US government source checks (CMS, USPSTF, SDOH) appear in session instructions
5. Worked `examples/plan.yaml` contains a complete discovery-plan.yaml with all required YAML fields

- [X] T020 [US2] Extend `skills/.curated/rh-inf-discovery/SKILL.md` with Research Expansion Suggestions instructions (FR-025, FR-025a) — after each search pass, agent produces 3–7 numbered prompts covering: adjacent comorbidities, healthcare economics angle (cost/burden), health equity or disparate-population angle, implementation science gap (adoption barriers), data/registry evidence gap; suggestions must state the adjacent topic, why it is relevant, and the first `rh-skills search` command to run; suggestions MUST NOT be auto-added to `sources[]`
- [X] T021 [US2] Extend `skills/.curated/rh-inf-discovery/SKILL.md` with US government source coverage instructions (FR-023) — for any topic with US clinical care or population health angle, agent MUST check: CMS eCQM Library/CMIT for existing quality measures, QPP/MIPS if clinician performance angle exists, USPSTF for preventive service grades, Gravity Project SDOH taxonomy, AHRQ evidence-based practice reports, CDC surveillance/MMWR if epidemiological evidence needed; add findings to `sources[]`
- [X] T022 [US2] Extend `skills/.curated/rh-inf-discovery/SKILL.md` with health-economics source requirement instructions (FR-026) — when topic involves a chronic condition, preventive intervention, or CMS quality program, agent MUST include ≥1 `health-economics` source in `sources[]`; minimum: a cost-of-care/disease-burden source (HCUP, MEPS, GBD) and where intervention involved, a cost-effectiveness reference (CEA Registry, NICE HTA); failing to include prompts warning in verify mode
- [X] T023 [US2] Extend `skills/.curated/rh-inf-discovery/SKILL.md` with living document + interactive assistant instructions (FR-027) — after each research pass the agent presents the scripted A/B/C prompt verbatim: "A) Explore an expansion area — tell me the number  B) Add, remove, or modify sources  C) Save the plan and move on to rh-inf-ingest"; agent emits the status block and stops — no post-block text, no pre-answering unchosen options; mid-plan save writes a checkpoint (subsequent saves use `--force` implicitly); plan grows as conversation evolves
- [X] T024 [US2] Extend `skills/.curated/rh-inf-discovery/SKILL.md` with source count bound instructions (FR-004a) — if plan reaches 25 sources: warn user, move additional candidates to Research Expansion Suggestions section rather than `sources[]`; if plan has fewer than 5 sources after all searches: agent MUST search additional databases (society URLs, government sources, AHRQ) before presenting for approval; never present a plan with <5 sources as complete
- [X] T025 [US2] Write `skills/.curated/rh-inf-discovery/examples/plan.yaml` — complete worked example `discovery-plan.yaml` for topic `diabetes-ccm`; pure YAML (no frontmatter delimiters); must include: `topic`, `version`, `created`, `last_updated`, `status: approved`, `domain_advice`, `expansion_suggestions` (≥3), `sources[]` (≥5 entries with all required fields including `access`, `evidence_level`, `rationale`, `open_access`, `auth_note` where applicable); also write `skills/.curated/rh-inf-discovery/examples/readout.md` — corresponding generated narrative with Domain Advice and Research Expansion Suggestions sections; sourced from `specs/003-rh-inf-discovery/quickstart.md` for consistency
- [X] T026 [P] [US2] Write `skills/.curated/rh-inf-discovery/examples/output.md` — worked example of a full plan dialogue: agent domain advice → search output → source curation → access advisory for authenticated source → expansion suggestions → user selects areas → mid-plan save → verify prompt; demonstrates all key flows from US1 and US2 acceptance scenarios

---

## Phase 5: User Story 3 — Verify Discovery Coverage (P2)

**Story goal**: Before proceeding to ingest, the informaticist validates that the saved discovery plan is structurally complete and covers required evidence categories.

**Independent test criteria**:
1. `rh-skills validate --plan discovery-plan.yaml` exits 0 on a complete plan
2. `rh-skills validate --plan` exits 1 with `✗ No terminology source` when none present
3. `rh-skills validate --plan` exits 1 when a source entry is missing `rationale` or `evidence_level`
4. `rh-skills validate --plan` exits 0 with `⚠ No health-economics source` warning (warning only)
5. SKILL.md verify mode calls `rh-skills validate --plan` and displays per-check output; makes no file writes

- [X] T027 [US3] Add verify mode instructions to `skills/.curated/rh-inf-discovery/SKILL.md` — agent calls `rh-skills validate --plan topics/<topic>/process/plans/discovery-plan.yaml`, displays per-check ✓/✗ output, interprets exit code (0 = all pass, 1 = failures present); verify mode MUST NOT write any files or append to tracking.yaml (FR-018); if plan not found, agent prints clear error and exits
- [X] T028 [US3] Extend `rh-skills validate` in `src/rh_skills/commands/validate.py` to accept `--plan <path>` flag (alternative to positional TOPIC/LEVEL/ARTIFACT args); when `--plan` is given: (a) parse pure YAML from path (no frontmatter extraction — file is plain YAML), exit 1 on parse error; (b) check `sources[]` count 5–25, exit 1 if outside range; (c) check ≥1 entry with `type: terminology`, exit 1 if none; (d) check every entry has non-empty `rationale`, exit 1 naming missing source; (e) check every entry has valid `evidence_level` from allowed set, exit 1 naming invalid; (f) check every `type` is from allowed set (unknown → warning only); (g) if no `health-economics` type → emit `⚠ No health-economics source found` (warning; exit 0); print `✓`/`✗` per check; exit 0 only if all mandatory checks pass
- [X] T029 [P] [US3] Write `tests/unit/test_validate_plan.py` — test each FR-019 check: valid plan exits 0 with all `✓`, missing terminology source exits 1 with `✗`, source missing `rationale` exits 1 naming the source, invalid `evidence_level` exits 1, no health-economics source exits 0 with `⚠` warning, malformed YAML exits 1 at parse, source count <5 exits 1, source count >25 exits 1

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration validation, documentation, and final test suite confirmation.

- [X] T030 Run `uv run pytest tests/unit/ -v` and fix any regressions or import errors introduced by new `search.py`, updated `ingest.py`, and updated `init.py`; confirm all new test files pass
- [X] T031 [P] Run `uv run pytest tests/skills/ -v` to confirm `rh-inf-discovery` SKILL.md is picked up by the parametrized skills suite and all checks pass (FR-022 / NFR-003)
- [X] T032 [P] Update `DEVELOPER.md` with `rh-skills search` command group documentation: subcommands, `NCBI_API_KEY` env var, `--json` flag usage, rate limit notes
- [ ] T033 Commit all Phase 3–6 implementation files; run `uv run pytest` (full suite) to confirm green before merging `003-rh-inf-discovery`

---

## Dependency Graph

```
T001 → T004, T005, T010, T011, T014
T002 → T010, T011, T014, T017, T029
T003 → T006, T007, T008
T004 → T006, T007
T005 → T008
T006 → T009, T010
T007 → T009, T010
T008 → T009, T011
T009 → (no further deps — enables agent --json consumption)
T012 → T013, T014
T015 → T016, T017
T018 → T019, T020, T021, T022, T023, T024, T027
T019 → T025
T028 → T027, T029
T030 → T031, T033
T031 → T033
T032 → T033
```

**US1 must complete before US2 (SKILL.md base required)**
**US1 must complete before US3 (validate --plan is CLI extension of existing validate)**
**US2 and US3 can be developed in parallel once T018 is done**

---

## Parallel Execution Examples

### Within Phase 3 (US1)

```bash
# After T003, T004 done — run in parallel:
# Terminal 1:
implement T006  # rh-skills search pubmed

# Terminal 2:
implement T007  # rh-skills search pmc (same helper, different db)
```

```bash
# After T001, T002 done — run in parallel:
# Terminal 1:
implement T010  # tests for pubmed/pmc

# Terminal 2:
implement T011  # tests for clinicaltrials

# Terminal 3:
implement T014  # tests for ingest --url
```

```bash
# After T003 done — run in parallel:
# Terminal 1:
implement T015  # rh-skills init RESEARCH.md

# Terminal 2:
implement T018  # SKILL.md core (independent file)
```

### Within Phase 4 (US2)

After T018 is done, T020–T026 can all be worked in parallel (all extend SKILL.md in non-overlapping sections, or write new example files).

### Within Phase 5 (US3)

T028 (validate --plan CLI) and T027+T029 are largely independent: T027 is SKILL.md text; T028 is Python; T029 is tests for T028.

---

## Implementation Strategy

**MVP (Deliver first — US1 only)**:
T001–T019 (Phases 1–3) — gives a working CLI (`rh-skills search` + `rh-skills ingest --url` + `rh-skills init` research tracking) and a functional SKILL.md that can run a basic discovery session from start to save.

**Increment 2 (US2 — Expansion)**: T020–T026 — enriches the SKILL.md with expansion suggestions, US government source coverage, health-economics requirement, and worked examples.

**Increment 3 (US3 — Verify)**: T027–T029 — adds `rh-skills validate --plan` and verify mode.

**Polish**: T030–T033 — full suite validation, docs, final commit.
