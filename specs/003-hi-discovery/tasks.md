---
description: "Tasks for 003-hi-discovery — hi-discovery interactive research assistant skill"
---

# Tasks: `hi-discovery` — Healthcare Informatics Discovery Skill

**Input**: Design documents from `/specs/003-hi-discovery/`
**Branch**: `003-hi-discovery`
**Spec**: User Stories: US1 (P1) — Research from scratch, US2 (P1) — Iterative expansion, US3 (P2) — Verify coverage

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label — US1, US2, US3
- All paths are relative to repository root

---

## Phase 1: Setup (Dependencies)

**Purpose**: Add new dependencies required by `hi search` and URL download.

- [ ] T001 Add `httpx>=0.27` to `[project.dependencies]` in `pyproject.toml` and run `uv sync` to install
- [ ] T002 [P] Add `pytest-httpx>=0.30` to `[project.optional-dependencies.dev]` in `pyproject.toml` for HTTP mocking in tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core API helpers and CLI scaffolding that all user story commands depend on.

- [ ] T003 Create `src/hi/commands/search.py` with a `search` click group (no subcommands yet); register it in `src/hi/cli.py` with `main.add_command(search.search)`
- [ ] T004 Implement `_entrez_search_fetch(query, db, max_results, api_key)` helper function in `src/hi/commands/search.py` — performs NCBI esearch (`retmode=json`) then efetch (`rettype=xml`) two-step, parses PubMed XML via `xml.etree.ElementTree`, respects rate limit (0.34s sleep without key; 0.11s with `NCBI_API_KEY`); returns list of dicts with keys: `id`, `title`, `url`, `year`, `journal`, `open_access`, `pmcid`, `abstract_snippet`
- [ ] T005 [P] Implement `_clinicaltrials_search(query, max_results, status_filter)` helper function in `src/hi/commands/search.py` — calls ClinicalTrials.gov REST API v2 (`GET https://clinicaltrials.gov/api/v2/studies`), parses JSON, returns list of dicts with keys: `id`, `title`, `url`, `year`, `journal`, `open_access`, `pmcid`, `abstract_snippet` (journal and pmcid are null; open_access always true)

---

## Phase 3: User Story 1 — Research a Clinical Topic from Scratch (P1)

**Story goal**: A clinical informaticist runs `hi-discovery` on a new topic, receives domain advice, searches PubMed/PMC/ClinicalTrials, approves sources that are downloaded inline, and saves a living discovery plan to disk.

**Independent test criteria**:
1. `hi search pubmed --query "sepsis management" --json` returns valid JSON with ≥1 result (mocked)
2. `hi search pmc --query "sepsis management" --json` returns results with `open_access: true`
3. `hi search clinicaltrials --query "sepsis" --json` returns NCT ID results
4. `hi ingest implement --url <mocked-pdf-url> --name test-source` downloads file, computes SHA-256, registers in tracking.yaml
5. `hi ingest implement --url <login-redirect-url> --name test` exits 3 with advisory
6. `hi init diabetes-ccm` creates `RESEARCH.md` at root and `topics/diabetes-ccm/process/research.md`
7. SKILL.md passes `tests/skills/` parametrized suite

- [ ] T006 [US1] Implement `hi search pubmed` subcommand in `src/hi/commands/search.py` — wires `_entrez_search_fetch(db="pubmed")`; options: `--query` (required), `--max 20`, `--filter TEXT`, `--api-key TEXT` (env: `NCBI_API_KEY`); human-readable stdout format per contracts/hi-search.md; exit 0 (success), 1 (network error), 2 (zero results)
- [ ] T007 [P] [US1] Implement `hi search pmc` subcommand in `src/hi/commands/search.py` — reuses `_entrez_search_fetch(db="pmc")`; sets `open_access: true` on all results; same options and exit codes as `hi search pubmed`
- [ ] T008 [US1] Implement `hi search clinicaltrials` subcommand in `src/hi/commands/search.py` — wires `_clinicaltrials_search()`; options: `--query` (required), `--max 20`, `--status "COMPLETED,RECRUITING"`; human-readable stdout; exit 0/1/2
- [ ] T009 [US1] Add `--json` flag to all three `hi search` subcommands in `src/hi/commands/search.py`; emit structured JSON to stdout per the `hi search` Result schema in `specs/003-hi-discovery/data-model.md` Entity 3; `--json` and human-readable are mutually exclusive output paths
- [ ] T010 [P] [US1] Write `tests/unit/test_search_pubmed.py` — use `pytest-httpx` to mock NCBI esearch + efetch HTTP calls; test: successful result list, `open_access: true` when pmcid present, zero-results exits 2, network error exits 1, `--json` output matches Entity 3 schema, rate-limit sleep called
- [ ] T011 [P] [US1] Write `tests/unit/test_search_clinicaltrials.py` — use `pytest-httpx` to mock ClinicalTrials.gov v2 API; test: result list parsed correctly, `open_access: true` always set, zero results exits 2, `--json` output matches schema
- [ ] T012 [US1] Extend `hi ingest implement` in `src/hi/commands/ingest.py` to accept `--url TEXT` and `--name TEXT` flags (mutually exclusive with positional FILE arg); implement: GET url via httpx (follow redirects up to 20), detect MIME from Content-Type header using MIME_TO_EXT map from `specs/003-hi-discovery/research.md` Decision 5, write to `sources/<name>.<ext>`, compute SHA-256, append `source_ingested` event to `tracking.yaml`, print `✓ Downloaded: sources/<name>.<ext>`
- [ ] T013 [US1] Add auth-redirect detection to `hi ingest implement --url` in `src/hi/commands/ingest.py` — after redirect chain resolves, check if final URL contains `login`, `signin`, `auth`, or `access-denied`; if true: print access advisory (source URL, final redirect URL, manual retrieval instructions) and exit 3 without writing any file
- [ ] T014 [P] [US1] Write `tests/unit/test_ingest_url.py` — use `pytest-httpx` to mock HTTP responses; test: successful PDF download (SHA-256 computed, file written, tracking.yaml event appended), MIME detection (pdf → `.pdf`, html → `.html`), auth-redirect exit 3 (no file written), already-exists exit 2 (no overwrite), network error exit 1
- [ ] T015 [US1] Extend `hi init` in `src/hi/commands/init.py` to create `RESEARCH.md` at repo root if not already present using the canonical format from `specs/003-hi-discovery/data-model.md` Entity 4; then append one Active Topics row `| <topic> | initialized | 0 | <date> | <date> | |`; if `RESEARCH.md` already exists, append row only (idempotent: skip if topic row already present)
- [ ] T016 [US1] Extend `hi init` in `src/hi/commands/init.py` to create `topics/<name>/process/notes.md` with the canonical stub format (`# Research Notes — <topic>` header; `## Open Questions`, `## Decisions`, `## Source Conflicts`, `## Notes` sections with placeholder comments) per `specs/003-hi-discovery/data-model.md` Entity 5; skip creation if file already exists
- [ ] T017 [P] [US1] Write `tests/unit/test_init_research.py` — test: first `hi init` creates both `RESEARCH.md` and `process/notes.md`, second `hi init` on different topic appends row to existing `RESEARCH.md` without corrupting existing rows, duplicate init is idempotent, process/notes.md contains all four section headers (Open Questions, Decisions, Source Conflicts, Notes)
- [ ] T018 [US1] Write `skills/.curated/hi-discovery/SKILL.md` — frontmatter (name, description, modes: session/verify, context_files: reference.md + examples/plan.yaml + examples/output.md, lifecycle_stage: l1-discovery, reads_from/writes_via_cli per spec FR-021); Overview section; session mode step-by-step instructions (steps 1–12 from `specs/003-hi-discovery/research.md` Decision 7): check topic initialized → domain advice → search pubmed → search clinicaltrials → search pmc → curate sources → present to user → print authenticated source advisories → present expansion suggestions → prompt user → save (writes `discovery-plan.yaml` + `discovery-readout.md`; creates `notes.md` stub; no downloads — hi-ingest handles acquisition); include FR-015 warning (existing plan detection), `--dry-run` behavior (no writes)
- [ ] T019 [US1] Add session save instructions to `skills/.curated/hi-discovery/SKILL.md` — agent writes `process/plans/discovery-plan.yaml` (pure YAML, per data-model.md Entity 2) and `process/plans/discovery-readout.md` (generated narrative with Domain Advice and Research Expansion Suggestions, per data-model.md Entity 2b); creates `process/notes.md` stub (create-unless-exists); updates RESEARCH.md Active Topics row (source count + date)

---

## Phase 4: User Story 2 — Iterative Research Expansion (P1)

**Story goal**: After the initial pass, the user asks the agent to expand into adjacent areas (economics, SDOH, comorbidities). The agent adds new sources to the living plan, respects the 25-source cap, and prompts for save checkpoints.

**Independent test criteria**:
1. SKILL.md session mode includes Expansion Suggestions section with ≥3 prompts after initial pass
2. SKILL.md instructs agent to warn when 25-source cap is reached and move surplus to expansion candidates
3. SKILL.md instructs agent to search additional DBs when plan has <5 sources
4. US government source checks (CMS, USPSTF, SDOH) appear in session instructions
5. Worked `examples/plan.yaml` contains a complete discovery-plan.yaml with all required YAML fields

- [ ] T020 [US2] Extend `skills/.curated/hi-discovery/SKILL.md` with Research Expansion Suggestions instructions (FR-025, FR-025a) — after each search pass, agent produces 3–7 numbered prompts covering: adjacent comorbidities, healthcare economics angle (cost/burden), health equity or disparate-population angle, implementation science gap (adoption barriers), data/registry evidence gap; suggestions must state the adjacent topic, why it is relevant, and the first `hi search` command to run; suggestions MUST NOT be auto-added to `sources[]`
- [ ] T021 [US2] Extend `skills/.curated/hi-discovery/SKILL.md` with US government source coverage instructions (FR-023) — for any topic with US clinical care or population health angle, agent MUST check: CMS eCQM Library/CMIT for existing quality measures, QPP/MIPS if clinician performance angle exists, USPSTF for preventive service grades, Gravity Project SDOH taxonomy, AHRQ evidence-based practice reports, CDC surveillance/MMWR if epidemiological evidence needed; add findings to `sources[]`
- [ ] T022 [US2] Extend `skills/.curated/hi-discovery/SKILL.md` with health-economics source requirement instructions (FR-026) — when topic involves a chronic condition, preventive intervention, or CMS quality program, agent MUST include ≥1 `health-economics` source in `sources[]`; minimum: a cost-of-care/disease-burden source (HCUP, MEPS, GBD) and where intervention involved, a cost-effectiveness reference (CEA Registry, NICE HTA); failing to include prompts warning in verify mode
- [ ] T023 [US2] Extend `skills/.curated/hi-discovery/SKILL.md` with living document + interactive assistant instructions (FR-027) — after each research pass the agent presents the scripted A/B/C prompt verbatim: "A) Explore an expansion area — tell me the number  B) Add, remove, or modify sources  C) Save the plan and move on to hi-ingest"; agent emits the status block and stops — no post-block text, no pre-answering unchosen options; mid-session save writes checkpoint (subsequent saves use `--force` implicitly); plan grows as conversation evolves
- [ ] T024 [US2] Extend `skills/.curated/hi-discovery/SKILL.md` with source count bound instructions (FR-004a) — if plan reaches 25 sources: warn user, move additional candidates to Research Expansion Suggestions section rather than `sources[]`; if plan has fewer than 5 sources after all searches: agent MUST search additional databases (society URLs, government sources, AHRQ) before presenting for approval; never present a plan with <5 sources as complete
- [ ] T025 [US2] Write `skills/.curated/hi-discovery/examples/plan.yaml` — complete worked example `discovery-plan.yaml` for topic `diabetes-ccm`; pure YAML (no frontmatter delimiters); must include: `topic`, `version`, `created`, `last_updated`, `status: approved`, `domain_advice`, `expansion_suggestions` (≥3), `sources[]` (≥5 entries with all required fields including `access`, `evidence_level`, `rationale`, `open_access`, `auth_note` where applicable); also write `skills/.curated/hi-discovery/examples/readout.md` — corresponding generated narrative with Domain Advice and Research Expansion Suggestions sections; sourced from `specs/003-hi-discovery/quickstart.md` for consistency
- [ ] T026 [P] [US2] Write `skills/.curated/hi-discovery/examples/output.md` — worked example of a full session dialogue: agent domain advice → search output → source curation → access advisory for authenticated source → expansion suggestions → user selects areas → mid-session save → verify prompt; demonstrates all key flows from US1 and US2 acceptance scenarios

---

## Phase 5: User Story 3 — Verify Discovery Coverage (P2)

**Story goal**: Before proceeding to ingest, the informaticist validates that the saved discovery plan is structurally complete and covers required evidence categories.

**Independent test criteria**:
1. `hi validate --plan topics/test/process/plans/discovery-plan.yaml` exits 0 on a complete plan
2. `hi validate --plan` exits 1 with `✗ No terminology source` when none present
3. `hi validate --plan` exits 1 when a source entry is missing `rationale` or `evidence_level`
4. `hi validate --plan` exits 0 with `⚠ No health-economics source` warning (warning only)
5. SKILL.md verify mode calls `hi validate --plan` and displays per-check output; makes no file writes

- [ ] T027 [US3] Add verify mode instructions to `skills/.curated/hi-discovery/SKILL.md` — agent calls `hi validate --plan topics/<name>/process/plans/discovery-plan.yaml`, displays per-check ✓/✗ output, interprets exit code (0 = all pass, 1 = failures present); verify mode MUST NOT write any files or append to tracking.yaml (FR-018); if plan not found, agent prints clear error and exits
- [ ] T028 [US3] Extend `hi validate` in `src/hi/commands/validate.py` to accept `--plan <path>` flag (alternative to positional TOPIC/LEVEL/ARTIFACT args); when `--plan` is given: (a) parse pure YAML from path (no frontmatter extraction — file is plain YAML), exit 1 on parse error; (b) check `sources[]` count 5–25, exit 1 if outside range; (c) check ≥1 entry with `type: terminology`, exit 1 if none; (d) check every entry has non-empty `rationale`, exit 1 naming missing source; (e) check every entry has valid `evidence_level` from allowed set, exit 1 naming invalid; (f) check every `type` is from allowed set (unknown → warning only); (g) if no `health-economics` type → emit `⚠ No health-economics source found` (warning; exit 0); print `✓`/`✗` per check; exit 0 only if all mandatory checks pass
- [ ] T029 [P] [US3] Write `tests/unit/test_validate_plan.py` — test each FR-019 check: valid plan exits 0 with all `✓`, missing terminology source exits 1 with `✗`, source missing `rationale` exits 1 naming the source, invalid `evidence_level` exits 1, no health-economics source exits 0 with `⚠` warning, malformed YAML exits 1 at parse, source count <5 exits 1, source count >25 exits 1

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration validation, documentation, and final test suite confirmation.

- [ ] T030 Run `uv run pytest tests/unit/ -v` and fix any regressions or import errors introduced by new `search.py`, updated `ingest.py`, and updated `init.py`; confirm all new test files pass
- [ ] T031 [P] Run `uv run pytest tests/skills/ -v` to confirm `hi-discovery` SKILL.md is picked up by the parametrized skills suite and all checks pass (FR-022 / NFR-003)
- [ ] T032 [P] Update `DEVELOPER.md` with `hi search` command group documentation: subcommands, `NCBI_API_KEY` env var, `--json` flag usage, rate limit notes
- [ ] T033 Commit all Phase 3–6 implementation files; run `uv run pytest` (full suite) to confirm green before merging `003-hi-discovery`

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
implement T006  # hi search pubmed

# Terminal 2:
implement T007  # hi search pmc (same helper, different db)
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
implement T015  # hi init RESEARCH.md

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
T001–T019 (Phases 1–3) — gives a working CLI (`hi search` + `hi ingest --url` + `hi init` research tracking) and a functional SKILL.md that can run a basic discovery session from start to save.

**Increment 2 (US2 — Expansion)**: T020–T026 — enriches the SKILL.md with expansion suggestions, US government source coverage, health-economics requirement, and worked examples.

**Increment 3 (US3 — Verify)**: T027–T029 — adds `hi validate --plan` and verify mode.

**Polish**: T030–T033 — full suite validation, docs, final commit.
