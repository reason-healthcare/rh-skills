# Tasks: Healthcare Informatics Skills Framework

**Input**: Design documents from `/specs/001-hi-skills-framework/`  
**Branch**: `001-hi-skills-framework`  
**Generated**: 2026-04-03

**Format**: `[ID] [P?] [Story?] Description with file path`  
- **[P]**: Parallelizable — no dependency on incomplete sibling tasks  
- **[US#]**: User story this task belongs to  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository scaffold and shared shell utilities that every subsequent command depends on.

- [X] T001 Create full directory structure: `bin/`, `skills/`, `schemas/`, `templates/l1/`, `templates/l2/`, `templates/l3/`, `tests/unit/`, `tests/integration/`
- [X] T002 Create `bin/hi` dispatcher: parse first argument as subcommand, route to `bin/hi-{command}`, handle `--help` and `--version` global flags, print usage on unknown subcommand
- [X] T003 [P] Create `bin/common.sh`: shared utility functions used by all subcommands — `hi_log_info`, `hi_log_warn`, `hi_log_error`, `hi_timestamp` (ISO-8601), `hi_require_skill` (validate skill dir exists), `hi_kebab_validate` (check name is kebab-case), `hi_yq_get` (safe yq field read returning empty string instead of null)
- [X] T004 [P] Create `.env.example` with all LLM provider environment variables: `LLM_PROVIDER`, `OLLAMA_ENDPOINT`, `OLLAMA_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `OPENAI_API_KEY`, `OPENAI_ENDPOINT`, `OPENAI_MODEL`
- [X] T005 [P] Configure `bats-core` testing: add `package.json` with `bats`, `bats-mock` as dev dependencies; create `tests/test_helper.bash` with shared setup helpers (skill fixture creation, `SKILLS_DIR` pointing to `$BATS_TMPDIR/skills`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schemas, templates, and `hi-validate` that ALL user story commands depend on. Must be complete before any US phase begins.

- [X] T006 Create `schemas/l2-schema.yaml`: define required fields (`id`, `name`, `title`, `version`, `status`, `description`, `domain`, `derived_from`) and optional fields (`notes`, `references`, `tags`, `subject_area`) with field-level type annotations and enum values
- [X] T007 Create `schemas/l3-schema.yaml`: define required fields (`artifact_schema_version`, `metadata.id`, `metadata.name`, `metadata.title`, `metadata.version`, `metadata.status`, `metadata.domain`, `metadata.created_date`, `metadata.description`, `converged_from`) and optional sections (`pathways`, `actions`, `libraries`, `measures`, `assessments`, `value_sets`, `code_systems`) with full field specs and FHIR mapping comments
- [X] T008 [P] Create `schemas/tracking-schema.yaml`: define required fields (`schema_version`, `skill.name`, `skill.created_at`, `artifacts.l1`, `artifacts.l2`, `artifacts.l3`, `events`) with event type enum (`created`, `l1_added`, `l2_derived`, `l3_converged`, `validated`, `test_run`)
- [X] T009 [P] Create `templates/l1/discovery.md`: stub template for raw L1 discovery artifacts with heading prompts for notes, references, and key concepts
- [X] T010 [P] Create `templates/l2/artifact.yaml`: pre-filled template with all required and optional field keys from L2 schema; required fields have `# REQUIRED` comments; optional fields have `# OPTIONAL` comments and are set to empty strings
- [X] T011 [P] Create `templates/l3/artifact.yaml`: pre-filled template with `artifact_schema_version: "1.0"` and all required `metadata` fields; optional section skeletons (`pathways`, `actions`, `libraries`, `measures`, `assessments`, `value_sets`, `code_systems`) as commented-out YAML blocks with inline FHIR mapping notes
- [X] T012 [P] Create `templates/tracking.yaml`: initial tracking artifact template with `schema_version: "1.0"`, empty `artifacts` block (`l1: []`, `l2: []`, `l3: []`), empty `events: []`, and placeholder `skill` block
- [X] T013 [P] Create `templates/SKILL.md`: anthropic skills-developer SKILL.md template with YAML frontmatter (`name`, `description`, `compatibility`, `metadata`) and Markdown body sections (`## User Input`, `## Instructions`) following the pattern from `.agents/skills/*/SKILL.md`
- [X] T014 Implement `bin/hi-validate`: source `bin/common.sh`; accept `<skill-name> <artifact-path>` args; detect artifact level from path prefix (`l1/`, `l2/`, `l3/`); for L2: load required/optional field lists from `schemas/l2-schema.yaml` and validate using yq field reads; for L3: validate `metadata` required fields and `converged_from`; emit `[PASS]`/`[WARN]`/`[FAIL]` lines to stdout; support `--json` flag outputting `{"status","errors":[],"warnings":[],"promotable":bool}`; exit 0 on pass/warnings, exit 1 on error
- [X] T015 Create `tests/unit/hi-validate.bats`: test L2 validation passes with all required fields; test L2 validation blocks with missing required field; test L2 validation warns on missing optional field; test L3 validation passes with required metadata; test L3 validation blocks with missing `metadata.id`; test `--json` output is valid JSON; verify exit codes 0 and 1

---

## Phase 3: US1 — Scaffold a New Skill (`hi init`)

**Story goal**: A developer runs `hi init <skill-name>` and gets a fully scaffolded skill directory with L1 stubs, SKILL.md, and an initial tracking artifact.

**Independent test**: `hi init diabetes-screening` produces the expected directory tree, SKILL.md, and a tracking.yaml with a `created` event — verifiable without running any other command.

- [X] T016 [US1] Implement `bin/hi-init`: validate `<skill-name>` is provided and kebab-case (exit 2 on invalid); check `skills/{name}` does not exist (exit 1 if it does); create directory tree (`l1/`, `l2/`, `l3/`, `fixtures/results/`); copy `templates/SKILL.md` → `skills/{name}/SKILL.md` with name substituted; copy `templates/l1/discovery.md` → `skills/{name}/l1/discovery.md`; copy `templates/tracking.yaml` → `skills/{name}/tracking.yaml`; populate tracking.yaml `skill` block with name, title, description, author (`$USER`), `created_at` timestamp; append `created` event to `events[]`; print `✓` confirmation lines to stdout
- [X] T017 [US1] Create `tests/unit/hi-init.bats`: test success creates all required dirs and files; test `tracking.yaml` contains correct `skill.name` and a `created` event; test duplicate skill name exits 1 with error message; test invalid skill name (not kebab-case) exits 2; test `--description` flag writes to tracking.yaml; test `--author` flag overrides `$USER`; test `hi list` shows new skill after init (cross-command integration assertion within unit test)
- [X] T018 [US1] Create skeleton `tests/integration/skill-lifecycle.bats`: scaffold full lifecycle test file; implement first step — `hi init` — asserting directory structure, SKILL.md content, and tracking.yaml initial state; stub remaining steps as `@test "TODO: promote L1→L2" { skip "requires T022" }`

---

## Phase 4: US2 — Progress Artifacts Through Levels (`hi promote`)

**Story goal**: A developer promotes individual artifacts through L1→L2 (derive, many-to-one or many-to-many) and L2→L3 (combine, many-to-one), with tracking events recorded at each step and lenient validation (warnings allowed, required fields enforced).

**Independent test**: Init a skill, add an L1 file, run `hi promote derive`, then run `hi promote combine` — verify L2/L3 files exist, have correct `derived_from`/`converged_from` fields, and tracking.yaml has two events logged.

- [X] T019 [US2] Implement derive mode in `bin/hi-promote` (`--to l2`): validate skill exists; validate `<l1-artifact-name>.md` exists in `skills/{name}/l1/`; parse `--count N` (default 1); for each of N: copy `templates/l2/artifact.yaml` → `skills/{name}/l2/{name}-{i}.yaml` with `derived_from` pre-populated; call `bin/hi-validate {skill} l2/{artifact}` and capture warnings; append `l2_derived` event to tracking.yaml with `source_artifacts`, `target_artifacts`, `validation_status`, and any warnings; print `✓` and `! [WARN]` lines per artifact
- [X] T020 [US2] Implement combine mode in `bin/hi-promote` (`--combine ... --output`): validate skill exists; validate each named L2 artifact exists in `skills/{name}/l2/`; run `hi-validate` on each source L2, block if any have required field errors; copy `templates/l3/artifact.yaml` → `skills/{name}/l3/{output}.yaml` with `converged_from` list pre-populated; run `hi-validate {skill} l3/{output}`; append `l3_converged` event to tracking.yaml with source/target lists and validation status; print `✓` confirmation and any warnings
- [X] T021 [P] [US2] Create `tests/unit/hi-promote.bats`: derive mode — success with count 1; derive mode — success with count 2 creates 2 files; derive mode — source L1 not found exits 1; derive mode — missing required L2 field exits 2; derive mode — missing optional field warns but exits 0; combine mode — success creates L3 with correct `converged_from`; combine mode — L2 source not found exits 1; combine mode — L2 has required field error blocks with exit 2; combine mode — L3 schema validation fails exits 3
- [X] T022 [US2] Extend `tests/integration/skill-lifecycle.bats`: add derive step (L1→L2 with count 2); add combine step (L2→L3); assert tracking.yaml has `l2_derived` and `l3_converged` events; remove `skip` stubs for these steps

---

## Phase 5: US3 — Locally Test a Skill (`hi test`)

**Story goal**: A developer runs `hi test <skill-name>` and the CLI submits the skill's SKILL.md prompt + each fixture's input to the configured LLM, compares output against expected, and produces a structured test result artifact.

**Independent test**: With `LLM_PROVIDER=ollama` and a running Ollama instance (or curl stubbed in unit tests), `hi test diabetes-screening` produces a JSON result artifact with pass/fail/errored outcomes and updates tracking.yaml.

- [X] T023 [US3] Create `bin/llm-lib.sh`: implement `invoke_llm <prompt>` dispatcher routing to provider-specific functions; implement `invoke_anthropic`, `invoke_openai_compatible`, `invoke_ollama` using curl (prompt escaped via `jq -Rs .`); implement `parse_llm_response` dispatcher per provider using jq; implement five comparison functions: `compare_exact`, `compare_normalized` (collapse whitespace), `compare_case_insensitive`, `compare_contains`, `compare_keywords`; implement `run_fixture_test <prompt> <input> <expected> <mode>` returning exit 0/1/2 for pass/fail/errored
- [X] T024 [US3] Implement `bin/hi-test`: source `bin/common.sh` and `bin/llm-lib.sh`; validate skill exists and has L3 artifacts (warn and offer structural validation if not); check `skills/{name}/fixtures/` for fixture dirs (exit 2 if none); parse `--fixture` and `--provider` flags; for each fixture: read `input.yaml` and `expected.yaml` with yq; load comparison mode from `expected.yaml`; call `run_fixture_test`; accumulate results; write JSON test result artifact to `skills/{name}/fixtures/results/{timestamp}-{runid}.json`; update `test_results` summary in tracking.yaml; print human-readable pass/fail/errored summary with `✓`/`✗`/`⚠` per fixture; exit 0 if all pass, exit 1 if any failed/errored, exit 2 if no fixtures, exit 3 if provider unreachable
- [X] T025 [P] [US3] Create `tests/unit/hi-test.bats`: stub `curl` with `bats-mock` to return provider-specific fixture responses; test all five comparison modes pass correctly; test `compare_normalized` accepts whitespace differences; test failed comparison exits 1; test curl error is captured as ERRORED (exit 2 from `run_fixture_test`); test no-fixtures exits 2 with guidance message; test `--fixture` flag runs only named fixture; test result JSON artifact is created and contains correct structure; test tracking.yaml `test_results` block is updated after run

---

## Phase 6: US4 — Track and Inspect Workflow State (`hi status`, `hi list`)

**Story goal**: A developer runs `hi status <skill-name>` or `hi list` and sees current artifact inventory, event history, and test results from tracking artifacts — without navigating the file system.

**Independent test**: After `hi init` (US1), `hi status diabetes-screening` renders the correct tracking state; after `hi list`, the skill appears in the summary table. Both are verifiable with tracking.yaml from Phase 2 foundational data alone.

- [X] T026 [US4] Implement `bin/hi-status`: source `bin/common.sh`; validate skill exists (exit 1) and tracking.yaml is present and parseable (exit 2 with repair guidance if not); read skill metadata, artifact inventory counts, and event list using yq; read `test_results` block; print human-readable report: skill name/title/author/date, L1/L2/L3 artifact counts with names, latest test run summary, full timestamped event history with derivation/convergence relationships; support `--json` flag outputting the full tracking.yaml content as JSON via yq
- [X] T027 [P] [US4] Implement `bin/hi-list`: enumerate `skills/*/` directories; for each, read `tracking.yaml` with yq (skip with warning if unreadable); collect name, L1/L2/L3 counts, last test run date and pass/fail indicator; support `--level` filter (only show skills with at least one artifact at that level); print aligned summary table; support `--json` flag outputting array of skill summaries; exit 0 always (even empty repo), exit 1 if `skills/` directory does not exist
- [X] T028 [P] [US4] Create `tests/unit/hi-status.bats`: test renders correct skill name and creation date from tracking.yaml; test shows correct L1/L2/L3 artifact counts; test shows event history entries in order; test shows test result summary when present; test exits 1 when skill does not exist; test exits 2 when tracking.yaml is missing with repair guidance message; test `--json` output is valid JSON
- [X] T029 [P] [US4] Create `tests/unit/hi-list.bats`: test empty `skills/` dir prints header with 0 skills; test single initialized skill appears in table; test multiple skills render correct artifact counts; test `--level l3` filters to only skills with L3 artifacts; test exits 1 when `skills/` does not exist; test `--json` output is a valid JSON array

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end integration, example skill, documentation, and final CLI hardening.

- [X] T030 [P] Complete `tests/integration/skill-lifecycle.bats`: implement full L1→L2→L3→test lifecycle for a `test-screening` example skill using real commands (no stubs except LLM curl); assert tracking.yaml contains all four event types in order; assert `hi status` renders correct final state; assert `hi list` shows skill with correct counts
- [X] T031 [P] Create example skill `skills/diabetes-screening/`: populate `l1/ada-guidelines-excerpt.md` with representative clinical guideline text; write `SKILL.md` following anthropic pattern with clinical prompt; include two example fixtures (`fixtures/basic-case/` and `fixtures/high-risk-case/`) with `input.yaml` and `expected.yaml` using `keywords` comparison mode; run `hi init` scaffold and then manually layer in content
- [X] T032 [P] Write `README.md`: installation section (`brew install yq jq`, PATH setup, Ollama quickstart); five-step authoring workflow matching `quickstart.md`; CLI reference table for all six commands; LLM provider configuration table; contributing guidelines
- [X] T033 Validate `--help` output for all six commands (`hi`, `hi init`, `hi promote`, `hi validate`, `hi test`, `hi status`, `hi list`): each must print synopsis, argument descriptions, flag descriptions, and exit code table; add `usage()` function to each bin script and wire to `--help`/`-h` flags and called with no args

---

## Dependencies

```
Phase 1 (Setup)
  └── Phase 2 (Foundational: schemas + templates + hi-validate)
        ├── Phase 3: US1 — hi init
        │     └── Phase 4: US2 — hi promote
        │           └── Phase 5: US3 — hi test
        ├── Phase 6: US4 — hi status + hi list  ← parallel with US1–US3
        └── Phase 7: Polish  ← after all US phases
```

**Key constraints**:
- T014 (`hi-validate`) must complete before T016, T019, T020 (all promote/init call validate)
- T016 (`hi-init`) must complete before T019/T020 (promote requires an initialized skill)
- T023 (`llm-lib.sh`) must complete before T024 (`hi-test` sources it)
- T026/T027 may be developed in parallel with T016–T025 (they only read tracking.yaml, not write it)

---

## Parallel Execution Per Story

### US1 (after Phase 2 complete)
```
T016 hi-init implementation  ──┐
                                ├──► T017 unit tests  ──► T018 integration skeleton
                               (sequential within story)
```

### US2 (after US1 complete)
```
T019 derive mode  ──┐
                    ├──► T021 unit tests (parallel)  ──► T022 integration extension
T020 combine mode ──┘
```

### US3 (after US2 complete)
```
T023 llm-lib.sh  ──► T024 hi-test  ──► T025 unit tests
```

### US4 (after Phase 2, parallel with US1–US3)
```
T026 hi-status  ──┐
                   ├──► T028 status tests (parallel)
T027 hi-list    ──┤
                   └──► T029 list tests (parallel)
```

### Phase 7 (after all US phases)
```
T030 integration tests  ──┐
T031 example skill      ──┤  (all parallel)
T032 README             ──┤
T033 --help validation  ──┘
```

---

## Implementation Strategy

**MVP scope (US1 only — deliver first)**:
Phases 1 + 2 + Phase 3 (T001–T018) → a working `hi init` command that scaffolds a skill with correct structure and tracking artifact. Independently demonstrable without any other command.

**Increment 2 (US1 + US2)**:
Add Phase 4 (T019–T022) → full L1→L2→L3 promotion pipeline. Independently demonstrable with `hi validate` confirming schema compliance.

**Increment 3 (US1 + US2 + US3)**:
Add Phase 5 (T023–T025) → LLM-based fixture testing. Demonstrable end-to-end workflow from discovery to validated computable artifact to tested skill.

**Full delivery (all stories)**:
Add Phase 6 (T026–T029) + Phase 7 (T030–T033) → complete framework with status/list visibility, example skill, and documentation.

---

## Task Summary

| Phase | Story | Tasks | Parallelizable |
|-------|-------|-------|---------------|
| 1 — Setup | — | T001–T005 (5) | T003, T004, T005 |
| 2 — Foundational | — | T006–T015 (10) | T008–T013, T015 |
| 3 — hi init | US1 | T016–T018 (3) | — |
| 4 — hi promote | US2 | T019–T022 (4) | T021 |
| 5 — hi test | US3 | T023–T025 (3) | T025 |
| 6 — hi status/list | US4 | T026–T029 (4) | T027, T028, T029 |
| 7 — Polish | — | T030–T033 (4) | T030, T031, T032, T033 |
| **Total** | | **33 tasks** | **18 parallelizable** |
