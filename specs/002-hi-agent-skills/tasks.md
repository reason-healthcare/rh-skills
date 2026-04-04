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
- [ ] T010 [P] Create `tests/unit/test_ingest.py`: test `plan` creates `plans/ingest-plan.md` with YAML front matter; test `implement` registers source in `tracking.yaml` with correct checksum; test `verify` exits 0 for unchanged file; test `verify` detects modified file; test `implement` errors when file not found

**Checkpoint**: `hi ingest plan/implement/verify` fully functional and tested.

---

## Phase 3: `hi status` CLI Extensions

**Purpose**: Extend `hi status` with the subcommands that `hi-status` skill (008) will wrap.

> **Note**: Basic `hi status <topic>` exists. These subcommands add lifecycle analysis and drift detection.

- [ ] T030 Extend `hi status` with `--progress` mode in `src/hi/commands/status.py`: output lifecycle stage, source/structured/computable artifact counts, validation status summary, last event timestamp, completeness percentage
- [ ] T031 Extend `hi status` with `next-steps` subcommand: analyze `tracking.yaml` state machine (no sources → suggest ingest; sources but no structured → suggest extract; etc.); emit single most important next action with exact `hi` CLI command
- [ ] T032 Extend `hi status` with `check-changes` subcommand: re-checksum all sources from tracking.yaml; report changed/missing sources; for each changed source list the structured artifacts derived from it as potentially stale
- [ ] T035 [P] Create `tests/unit/test_status_extended.py`: test `progress` outputs source/structured/computable counts; test `next-steps` emits a runnable `hi` command; test `check-changes` detects modified fixture file

**Checkpoint**: `hi status --progress`, `hi status next-steps`, `hi status check-changes` functional and tested. Ready for hi-status SKILL.md (spec 008).

---

## Phase 4: Polish & Documentation

- [ ] T036 [P] Verify `hi list` correctly enumerates `topics/`; confirm `.curated/` skill dirs are excluded from topic listings
- [ ] T037 [P] Create `docs/GETTING_STARTED.md`: `uv tool install hi`, `hi init`, first topic walkthrough referencing framework skills
- [ ] T038 [P] Create `docs/WORKFLOW.md`: sources→structured→computable lifecycle diagram, plan→implement→verify pattern, many-to-many artifact relationships
- [ ] T039 [P] Create `docs/COMMANDS.md`: full reference for all `hi` CLI commands including all subcommands
- [ ] T040 Run integration test using `diabetes-screening` fixture: `hi init` → `hi ingest implement` (source registered in tracking.yaml) → `hi promote derive` → `hi validate` → confirm all pass

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
