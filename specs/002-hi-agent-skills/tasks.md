# Tasks: HI Framework — CLI & Repository Layout (002)

**Branch**: `002-hi-agent-skills`
**Input**: Design documents from `/specs/002-hi-agent-skills/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Scope**: This task list covers the framework CLI and repository layout only. SKILL.md authoring for each skill is tracked in the respective skill specs (003–008).

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- All paths relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend the Python framework to support plan artifacts and the `skills/.curated/` namespace.

- [X] T001 ✅ Add `plans/` directory creation to `hi init` (`src/hi/commands/init.py`)
- [X] T002 [P] ✅ Markdown front matter parsing via ruamel.yaml; `common.py` has `sha256_file()`, `load_tracking()`, `save_tracking()`
- [X] T003 [P] ✅ SHA-256 checksum via `hashlib` in `src/hi/common.py` (`sha256_file()`)
- [X] T004 [P] ✅ Create `skills/.curated/` directory skeleton with 6 subdirectories: `hi-discovery/`, `hi-ingest/`, `hi-extract/`, `hi-formalize/`, `hi-verify/`, `hi-status/`

**Checkpoint**: ✅ Python helpers available; `hi init` creates `process/` subdir scaffold; framework skill dirs exist.

---

## Phase 2: Foundational (`hi ingest` CLI)

**Purpose**: Build the deterministic CLI that all ingest-related SKILL.md files will invoke.

> **Status**: ✅ CLI fully implemented in `src/hi/commands/ingest.py`.

- [X] T005 ✅ `hi ingest` click group with `plan`/`implement`/`verify` subcommand routing
- [X] T006 ✅ `hi ingest plan [--force]`: write `plans/ingest-plan.md` with YAML front matter template; re-run guard
- [X] T007 ✅ `hi ingest implement <file> [--force]`: copy to `sources/`, compute SHA-256, append `sources[]` entry in `tracking.yaml`, append `source_added` event
- [X] T008 ✅ Optional text extraction: detect `pdftotext` (PDF) and `pandoc` (Word/Excel); emit warning if tool absent; set `text_extracted` flag
- [X] T009 ✅ `hi ingest verify`: re-checksum all registered sources, report `✓ OK` or `✗ CHANGED`; exit 1 if any mismatch
- [X] T010 [P] ✅ Create `tests/unit/test_ingest.py`: 13 tests covering plan/implement/verify subcommands, checksum, force flag, missing-file error

**Checkpoint**: `hi ingest plan/implement/verify` fully functional and tested.

---

## Phase 3: `hi status` CLI Extensions

**Purpose**: Extend `hi status` with the subcommands that `hi-status` skill (008) will wrap.

> **Note**: Basic `hi status <topic>` exists. These subcommands add lifecycle analysis and drift detection.

- [X] T030 ✅ Extend `hi status` with `progress` subcommand in `src/hi/commands/status.py`
- [X] T031 ✅ Extend `hi status` with `next-steps` subcommand
- [X] T032 ✅ Extend `hi status` with `check-changes` subcommand
- [X] T035 [P] ✅ Create `tests/unit/test_status_extended.py`: 14 tests for all new status subcommands

**Checkpoint**: `hi status --progress`, `hi status next-steps`, `hi status check-changes` functional and tested. Ready for hi-status SKILL.md (spec 008).

---

## Phase 4: Polish & Documentation

- [X] T036 [P] ✅ Verify `hi list` correctly enumerates `topics/`; `.curated/` excluded from topic listings (test added to `test_status.py`)
- [X] T037 [P] ✅ Create `docs/GETTING_STARTED.md`
- [X] T038 [P] ✅ Create `docs/WORKFLOW.md`
- [X] T039 [P] ✅ Create `docs/COMMANDS.md`
- [ ] T040 Run integration test using `diabetes-screening` fixture: `hi init` → `hi ingest implement` (source registered in tracking.yaml) → `hi promote derive` → `hi validate` → confirm all pass

---

## Phase 5: Skill Template, Tests & Documentation (added 2026-04-04)

**Purpose**: Establish the canonical SKILL.md template, automated skill quality gates, and audience-split documentation.

- [X] T041 ✅ Create `skills/_template/SKILL.md` — canonical three-level progressive disclosure template for all HI skills
- [X] T042 ✅ Create `skills/_template/reference.md` — Level 3 companion: plan/output schemas, clinical standards (FHIR, SNOMED, LOINC, ICD-10), GRADE, glossary
- [X] T043 ✅ Create `skills/_template/examples/plan.md` and `examples/output.md` — worked diabetes-screening examples
- [X] T044 ✅ Create `docs/SKILL_AUTHORING.md` — step-by-step guide with design principles and completion checklist
- [X] T045 ✅ Create `tests/skills/conftest.py` — shared fixtures: `curated_skill_dirs()`, `parse_frontmatter()`, `curated_skill` parametrized fixture
- [X] T046 ✅ Create `tests/skills/test_skill_schema.py` — 16 always-run template tests + 13 parametrized curated skill schema tests (FR-023, FR-024)
- [X] T047 ✅ Create `tests/skills/test_skill_security.py` — 5 security checks per skill (FR-025): COMMAND_EXECUTION, PROMPT_INJECTION, CREDENTIAL_HANDLING, PHI_EXPOSURE, TRACKING_WRITE; 11 unit tests for check functions
- [X] T048 ✅ Create `tests/skills/test_skill_audit.py` — companion file tests + FR-016–FR-022 contract tests + library health checks (FR-026)
- [X] T049 ✅ Rewrite `README.md` for end-user audience (NFR-006): install, LLM config, quickstart, command reference, schemas
- [X] T050 ✅ Create `DEVELOPER.md` for contributor audience (NFR-006): dev setup, test suite, repo layout, skill authoring, security/contract tables, spec structure

**Checkpoint**: Framework fully documented and integration-tested.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)**: ✅ Complete
- **Phase 2 (Foundational)**: ✅ CLI complete; T010 (ingest tests) still needed
- **Phase 3 (hi status CLI)**: Can start now — extends existing `status.py`
- **Phase 4 (Polish)**: After Phase 3

### Parallel Opportunities

- T010, T035, T036 can run in parallel (different test files)
- T037, T038, T039 can run in parallel (different doc files)
- T030, T031, T032 should be sequential (same status.py file)

---

## Notes

- **Guiding principle**: All deterministic work in `hi` CLI commands; all reasoning in SKILL.md prompts.
- **Optional tools**: `pdftotext`, `pandoc` — degrade gracefully, never hard-fail
- **Terminology**: sources (raw/L1), structured (L2), computable (L3); dirs: `sources/`, `topics/<name>/structured/`, `topics/<name>/computable/`
- **Plan artifacts**: live at `topics/<name>/process/plans/<skill>-plan.md` with YAML front matter + Markdown prose body
- Commit after each phase checkpoint
- **Skill SKILL.md tasks**: tracked in respective skill specs (003–008), not here
