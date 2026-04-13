# Feature Specification: RH Skills — CLI & Repository Layout

**Feature Branch**: `002-rh-agent-skills`  
**Created**: 2026-04-03 | **Updated**: 2026-04-04  
**Status**: ✅ Complete (T040 integration test deferred to skill specs)

## Overview

The RH Skills provides the **deterministic infrastructure** that all HI agent skills depend on. The guiding principle: all deterministic work is handled by `rh-skills` CLI commands — only reasoning lives in agent skill prompts. This spec covers the shared infrastructure:

1. **Repository layout** — a predictable directory structure for topics, sources, and artifacts
2. **`rh-skills` CLI** — Python commands for file tracking, checksums, artifact promotion, validation, and task management
3. **`tracking.yaml`** — the single source of truth for topic lifecycle state
4. **Framework contracts** — conventions all skill specs (003–008) must follow

Each of the six HI agent skills has its own specification:

| Skill | Spec | Purpose |
|-------|------|---------|
| `rh-inf-discovery` | [003-rh-inf-discovery](../003-rh-inf-discovery/) | Guide literature search; produce ingest tasks |
| `rh-inf-ingest` | [004-rh-inf-ingest](../004-rh-inf-ingest/) | Register raw files/URLs with checksums |
| `rh-inf-extract` | [005-rh-inf-extract](../005-rh-inf-extract/) | Derive L2 structured artifacts from L1 sources |
| `rh-inf-formalize` | [006-rh-inf-formalize](../006-rh-inf-formalize/) | Converge L2 artifacts into computable L3 |
| `rh-inf-verify` | [007-rh-inf-verify](../007-rh-inf-verify/) | Validate any artifact at any point |
| `rh-inf-status` | [008-rh-inf-status](../008-rh-inf-status/) | Lifecycle summaries and drift detection |

---

## Repository Layout

```text
RESEARCH.md                  # Root portfolio log — all topics, their stages, cross-topic relationships
sources/                     # Raw source files (L1), repo-wide
plans/                       # Repo-level plan artifacts (rh-skills ingest plan, etc.)
topics/<name>/
  structured/                # Semi-structured L2 artifacts (YAML) — prominent
  computable/                # Computable L3 artifacts (YAML) — prominent
  process/
    plans/                   # Per-topic plan artifacts
      discovery-plan.yaml    # Pure YAML — rh-inf-discovery output (machine-readable source of truth)
      discovery-readout.md   # Generated narrative — do not edit directly
      ingest-plan.md         # YAML front matter + prose
      extract-plan.md        # YAML front matter + prose
      formalize-plan.md      # YAML front matter + prose
      tasks.md               # rh-skills tasks tracking
    contracts/               # YAML validation contracts
    checklists/              # Clinical review checklists
    fixtures/                # LLM test fixtures
      results/               # Test run results
    research.md              # Per-topic source tracking (ruled in/out) + open questions (NOTE: superseded by notes.md in 003+)
    notes.md                 # Open questions, decisions, source conflicts, free notes (human-maintained)
skills/.curated/             # Framework-level agent skills (excluded from rh-skills list)
  rh-inf-discovery/SKILL.md
  rh-inf-ingest/SKILL.md
  rh-inf-extract/SKILL.md
  rh-inf-formalize/SKILL.md
  rh-inf-verify/SKILL.md
  rh-inf-status/SKILL.md
tracking.yaml                # Single source of truth for lifecycle state
```

### `RESEARCH.md` — Root Portfolio Log

`RESEARCH.md` is the **human-readable cross-topic portfolio view**. It is automatically maintained by `rh-skills` at lifecycle events but is also human-editable (the Notes column and any prose below topic blocks).

```markdown
# Research Portfolio

> Managed by `rh-skills`. Add notes freely in the Notes column or below each topic block.
> Do not reorder table rows manually — use `hi research defer <topic>` to move entries.

## Active Topics

| Topic | Stage | Sources | Started | Updated | Notes |
|-------|-------|---------|---------|---------|-------|
| diabetes-screening | L1 Discovery | 12 | 2026-04-01 | 2026-04-04 | USPSTF A/B focus |

## Completed Topics

| Topic | Stage | Sources | Completed | Summary |
|-------|-------|---------|-----------|---------|

## Deferred / Abandoned Topics

| Topic | Reason | Date |
|-------|--------|------|
```

### `process/notes.md` — Per-Topic Human Annotations

`notes.md` is a **human-maintained** stub created by `rh-skills init`. It provides a structured place to record open questions, key decisions, source conflicts, and free notes for the topic. The CLI creates the stub only; all content is human-authored.

```markdown
# Research Notes — <topic>

## Open Questions
<!-- checkbox bullets -->
- [ ] 

## Decisions
<!-- key choices and why -->
- 

## Source Conflicts
<!-- contradictions between sources -->

## Notes
<!-- free-form -->
```


`structured/` and `computable/` are at the topic root for immediate visibility. Process support files are grouped under `process/`.

---

## Skill Framework Conventions

All HI agent skills follow these conventions. They are defined here as the framework contract that specs 003–008 must conform to.

### Mode Pattern

Workflow skills use three modes — `plan` → `implement` → `verify` — passed as the first positional argument:

```
rh-inf-discovery plan
rh-inf-extract implement
rh-inf-ingest verify
```

- **`plan`** — Writes `topics/<name>/process/plans/<skill>-plan.md` with YAML front matter (machine-readable) + Markdown prose (human review). No other files created or modified. **Exception**: `rh-inf-discovery` (003) uses a two-file split instead: `discovery-plan.yaml` (pure YAML, no frontmatter delimiters) as the machine-readable source of truth, and `discovery-readout.md` (generated narrative, do not edit) for human review.
- **`implement`** — Reads YAML front matter from the plan artifact and executes it by invoking `rh-skills` CLI commands. Fails immediately if no plan exists.
- **`verify`** — Non-destructive validation only. Never modifies any file.

### Re-run Guard

Every `plan` and `implement` mode MUST warn and stop if its expected output already exists. A `--force` flag MUST be supported to overwrite.

### Event Tracking

Every skill mode that modifies state MUST append a named event to `tracking.yaml`.

### Skill File Location

All skills reside at `skills/.curated/<skill-name>/SKILL.md`, following the anthropic skills-developer SKILL.md template. The `.curated/` dot-prefix excludes framework skills from `rh-skills list` output.

---

## CLI Commands

The `rh-skills` CLI handles all deterministic operations. Skills invoke these; they never perform deterministic work directly.

| Command | Description |
|---------|-------------|
| `rh-skills init <name>` | Create topic scaffold + register in tracking.yaml |
| `rh-skills list` | List topics (excludes dot-prefixed dirs) |
| `rh-skills ingest plan` | Generate `plans/ingest-plan.md` with sources to register |
| `rh-skills ingest implement <file>` | Register a source: path, type, checksum, timestamp |
| `rh-skills ingest verify` | Confirm all sources unchanged since ingest |
| `rh-skills promote derive <topic> <name>` | Create L2 structured artifact scaffold |
| `rh-skills promote combine <topic> <sources…> <target>` | Merge L2 artifacts into L3 computable artifact |
| `rh-skills validate <topic> <artifact>` | Schema-validate any named artifact |
| `rh-skills status show <topic>` | Show lifecycle state from tracking.yaml |
| `rh-skills status progress <topic>` | Pipeline bar + completeness % |
| `rh-skills status next-steps <topic>` | Recommend single next action with exact command |
| `rh-skills status check-changes <topic>` | Re-checksum sources; report drift and stale artifacts |
| `rh-skills tasks list [<topic>]` | List tasks from tasks.md |
| `rh-skills tasks add <topic> <task>` | Append a task |
| `rh-skills tasks complete <topic> <task-id>` | Mark task complete |
| `rh-skills test <topic> <skill>` | Run skill against fixtures; write results |

---

## tracking.yaml

```yaml
schema_version: "1.0"
sources: []           # Registered raw source files (L1)
topics:
  - name: string
    title: string
    description: string
    author: string
    created_at: string
    structured: []    # L2 artifact entries
    computable: []    # L3 artifact entries
    events: []        # Per-topic lifecycle events
events: []            # Repo-level events
```

See [data-model.md](data-model.md) for full schema and event name reference.

---

## User Scenarios & Testing

### User Story: Framework Initialization

A user installs `rh-skills` via `uv tool install rh-skills` and initializes a new clinical topic. `rh-skills init diabetes-screening` creates the full directory scaffold and registers the topic. `rh-skills list` confirms it is visible. The user can immediately start working with agent skills.

**Acceptance Scenarios**:
1. **Given** an empty repo, **When** `rh-skills init <name>` runs, **Then** `topics/<name>/structured/`, `computable/`, and `process/` (with all subdirs) are created and tracking.yaml is updated.
2. **Given** a topic exists, **When** `rh-skills list` runs, **Then** the topic name and title are shown.
3. **Given** a topic exists, **When** `rh-skills init <name>` runs again, **Then** it warns about existing topic and stops.

### User Story: Source Registration via CLI

A team member registers a downloaded PDF directly with the CLI. `rh-skills ingest implement guidelines.pdf` records the file path, type, SHA-256 checksum, and timestamp in tracking.yaml. Later, `rh-skills ingest verify` confirms the file is unchanged.

**Acceptance Scenarios**:
1. **Given** a source file, **When** `rh-skills ingest implement <file>` runs, **Then** path, type, checksum, and timestamp are in tracking.yaml.
2. **Given** an ingested file is modified, **When** `rh-skills ingest verify` runs, **Then** the file is flagged with original vs. current checksum.
3. **Given** a file path does not exist, **When** `rh-skills ingest implement <file>` runs, **Then** it exits non-zero with a clear error.

### User Story: Artifact Promotion

A team member runs `rh-skills promote derive diabetes-screening screening-criteria` to scaffold a new L2 structured artifact. After editing the YAML file, they run `rh-skills promote combine diabetes-screening screening-criteria risk-factors diabetes-pathway` to create the L3 computable artifact.

**Acceptance Scenarios**:
1. **Given** a topic exists, **When** `rh-skills promote derive <topic> <name>` runs, **Then** `topics/<topic>/structured/<name>.yaml` is created with a schema-valid scaffold and the topic's `structured[]` array in tracking.yaml is updated.
2. **Given** a structured artifact already exists, **When** `rh-skills promote derive <topic> <name>` runs **without** `--force`, **Then** it warns and exits non-zero without modifying the existing file.
3. **Given** structured artifacts exist, **When** `rh-skills promote combine <topic> <sources…> <target>` runs, **Then** `topics/<topic>/computable/<target>.yaml` is created and tracking.yaml `computable[]` is updated with the source artifact names listed in `converged_from`.
4. **Given** a named source artifact does not exist, **When** `rh-skills promote combine` runs, **Then** it exits non-zero with a clear error identifying the missing artifact.

### User Story: Artifact Validation

A team member runs `rh-skills validate diabetes-screening screening-criteria` to confirm the L2 artifact meets schema requirements before proceeding to formalize.

**Acceptance Scenarios**:
1. **Given** a valid L2 artifact, **When** `rh-skills validate <topic> <artifact>` runs, **Then** it exits 0 and prints a pass summary.
2. **Given** an L2 artifact with missing required fields, **When** `rh-skills validate` runs, **Then** it exits 1 and reports each missing required field with its location.
3. **Given** an L2 artifact with missing optional fields, **When** `rh-skills validate` runs, **Then** it exits 0 and emits advisory warnings only.
4. **Given** an artifact name that does not exist in either `structured/` or `computable/`, **When** `rh-skills validate` runs, **Then** it exits non-zero with a clear error.

### User Story: Skill Validation & Security

A skill author implements `rh-inf-extract` by copying `skills/_template/`, filling in the SKILL.md, and adding companion files. Before merging, the CI suite runs `tests/skills/` which automatically picks up the new skill via the parametrized `curated_skill` fixture. The author must address any schema, security, or framework contract findings before the PR is accepted.

**Acceptance Scenarios**:
1. **Given** a new skill dir with a valid SKILL.md, **When** `uv run pytest tests/skills/` runs, **Then** all schema and contract tests pass for the new skill.
2. **Given** a SKILL.md with an unfilled `<skill-name>` placeholder, **When** the test suite runs, **Then** `test_no_unfilled_placeholders` fails with a clear message identifying the placeholder.
3. **Given** a SKILL.md whose `name` field does not match its directory name, **When** the test suite runs, **Then** `test_name_matches_directory` fails.
4. **Given** a SKILL.md that reads external files without a prompt-injection boundary rule, **When** the test suite runs, **Then** `test_no_prompt_injection_without_boundary` fails with a PROMPT_INJECTION finding.
5. **Given** a SKILL.md `verify` mode that directly writes to `tracking.yaml`, **When** the test suite runs, **Then** `test_verify_mode_does_not_write_tracking_directly` fails.
6. **Given** all six curated skills are implemented and passing, **When** `uv run pytest tests/` runs, **Then** all 31 previously-skipped skill tests activate and pass.

### Edge Cases

- `rh-skills init` on an already-initialized topic — warn and stop.
- `rh-skills promote derive` for an artifact that already exists — warn and stop.
- `rh-skills validate` for a non-existent artifact — exit with clear error.
- `rh-skills ingest verify` when tracking.yaml has no sources — exit cleanly with informational message.
- `rh-skills list` when no `tracking.yaml` exists — exit 0 with informational message; do not create the file.
- `rh-skills status show` / `rh-skills status progress` for a topic not in tracking.yaml — exit non-zero with clear error identifying the unknown topic.

---

## Requirements

### Functional Requirements

**Repository Initialization**

- **FR-001**: `rh-skills init <name>` MUST create `topics/<name>/structured/`, `topics/<name>/computable/`, and `topics/<name>/process/` with the full subdirectory scaffold (`plans/`, `contracts/`, `checklists/`, `fixtures/`, `fixtures/results/`). It MUST create stub files: `process/notes.md`, `process/plans/tasks.md`.
- **FR-002**: `rh-skills init <name>` MUST register the new topic in `tracking.yaml` with `name`, `title`, `created_at`, and empty `structured`, `computable`, and `events` lists.
- **FR-003**: `rh-skills list` MUST enumerate directories under `topics/`, excluding dot-prefixed directories.

**Source Registration**

- **FR-004**: `rh-skills ingest plan` MUST generate `plans/ingest-plan.md` at the repo root as a structured Markdown file with YAML front matter listing source paths/URLs to register.
- **FR-005**: `rh-skills ingest implement <file>` MUST register the source in `tracking.yaml` with: file path (relative to repo root), detected file type, SHA-256 checksum, and ISO 8601 ingest timestamp. It MUST exit non-zero if the file does not exist.
- **FR-006**: Supported file types MUST include: PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), and online article URLs. For PDF, `pdftotext` (poppler) enables text extraction; for Word/Excel, `pandoc`. If the tool is absent, ingest MUST register metadata and checksum but emit a warning — it MUST NOT fail hard.
- **FR-007**: `rh-skills ingest verify` MUST compare current SHA-256 checksums of all registered sources against stored values and report any changed or missing files.

**Artifact Promotion**

- **FR-008**: `rh-skills promote derive <topic> <name>` MUST create `topics/<topic>/structured/<name>.yaml` with a schema-valid scaffold. It MUST fail if the artifact already exists (unless `--force`).
- **FR-009**: `rh-skills promote combine <topic> <sources…> <target>` MUST create `topics/<topic>/computable/<target>.yaml` by merging content from all named structured source artifacts. It MUST fail if any source artifact does not exist.

**Artifact Validation**

- **FR-010**: `rh-skills validate <topic> <artifact>` MUST validate the named artifact against its schema (L2 or L3 based on location) and report required-field errors (exit non-zero) and optional-field warnings (exit zero).

**Task Tracking**

- **FR-011**: `rh-skills tasks list [<topic>]` MUST read `topics/<topic>/process/plans/tasks.md` (or root `plans/tasks.md`) and display tasks with completion state.
- **FR-012**: `rh-skills tasks add <topic> <task>` MUST append a new unchecked task to `topics/<topic>/process/plans/tasks.md`.
- **FR-013**: `rh-skills tasks complete <topic> <task-id>` MUST mark the specified task complete in tasks.md.

**Skill Testing**

- **FR-014**: `rh-skills test <topic> <skill>` MUST run the named skill against fixture inputs in `topics/<topic>/process/fixtures/` and write results to `topics/<topic>/process/fixtures/results/`.

**Topic Status**

- **FR-015**: `rh-skills status show <topic>` MUST display current lifecycle state from tracking.yaml: source count, structured artifact count, computable artifact count, current stage, and last event timestamp. `rh-skills status progress <topic>` MUST display a pipeline bar, completeness percentage, and per-level artifact counts. `rh-skills status next-steps <topic>` MUST output a single recommended next action and the exact `rh-skills` or skill command to run. `rh-skills status check-changes <topic>` MUST re-checksum all registered sources and report any changed or missing files (exit 1) and any structured artifacts derived from changed sources (stale downstream). `rh-skills status check-changes` MUST be read-only — it MUST NOT modify tracking.yaml or any artifact.

**Research Tracking**

- **FR-027**: `rh-skills init <topic>` MUST create `RESEARCH.md` at the repo root if it does not already exist (initializing with the canonical header and three empty section tables: Active Topics, Completed Topics, Deferred/Abandoned). It MUST then append a new row to the Active Topics table with: topic name, initial stage (`initialized`), source count (0), started date, updated date, and an empty Notes column.
- **FR-028**: Any `rh-skills` command that transitions a topic's stage MUST update the topic's row in `RESEARCH.md` — specifically the Stage and Updated columns. When a topic reaches a terminal state (completed or abandoned), the CLI MUST move its row from Active Topics to the appropriate section. `RESEARCH.md` row moves MUST be idempotent (running twice produces no duplicate rows).
- **FR-029**: `rh-skills init <topic>` MUST also create `topics/<topic>/process/notes.md` with the canonical stub format: `## Open Questions`, `## Decisions`, `## Source Conflicts`, `## Notes` sections. The file is human-maintained — the CLI creates the stub only (create-unless-exists).
- **FR-030**: _(Removed — CLI no longer appends source rows to per-topic files. Source disposition tracking is handled via `discovery-plan.yaml` and `RESEARCH.md`. Human annotations go in `process/notes.md`.)_

**Framework Contracts for Skills**

- **FR-016**: All skill SKILL.md files MUST reside at `skills/.curated/<skill-name>/SKILL.md` and MUST follow the anthropic skills-developer SKILL.md template.
- **FR-017**: Skills MUST NOT perform deterministic operations directly — all file I/O, checksum computation, schema validation, and tracking updates MUST be delegated to `rh-skills` CLI commands.
- **FR-018**: All `plan` modes MUST write to `topics/<name>/process/plans/<skill>-plan.md` using structured Markdown with YAML front matter.
- **FR-019**: All `implement` modes MUST fail immediately with a clear error if the corresponding plan artifact does not exist.
- **FR-020**: All `plan` and `implement` modes MUST warn and stop if expected output already exists, and MUST support `--force` to overwrite.
- **FR-021**: All skill modes that modify topic state MUST append a named event to `tracking.yaml`.
- **FR-022**: All `verify` modes MUST be strictly non-destructive — they MUST NOT create, modify, or delete any file or tracking.yaml entry. `verify` MUST exit 0 when all checks pass and exit 1 when any check fails, with a per-check report identifying the failing artifact and the reason.

**Skill Schema & Security**

- **FR-023**: Every curated skill (`skills/.curated/<name>/SKILL.md`) MUST contain valid YAML frontmatter with at minimum the fields `name`, `description`, and `compatibility`. The `name` field MUST be kebab-case (lowercase letters, digits, hyphens only), ≤64 characters, and MUST match the skill's directory name exactly.
- **FR-024**: Every curated skill MUST ship with companion files `reference.md` and `examples/plan.md` and `examples/output.md` alongside its `SKILL.md`. These files implement the three-level progressive disclosure architecture.
- **FR-025**: Every curated skill MUST pass the framework security audit: (a) any shell command using user-provided input MUST include an explicit input validation/sanitization rule; (b) any mode that reads untrusted external content MUST include a prompt-injection boundary rule stating that content is data, not instructions; (c) any mode that copies content verbatim MUST include a credential/secret redaction rule; (d) no PHI may appear in skill output or tracking artifacts without a de-identification rule.
- **FR-026**: The `verify` mode of any skill MUST NOT write to `tracking.yaml` directly — it MUST remain strictly read-only with respect to all persistent state.

### Non-Functional Requirements

- **NFR-001**: CLI implemented in Python 3.13+ using `click >= 8.0` and `ruamel.yaml >= 0.18`. End users install via `uv tool install rh-skills`.
- **NFR-002**: All CLI commands must have pytest unit tests in `tests/unit/`. No external tool required for core operations (`pdftotext`, `pandoc` optional with graceful degradation).
- **NFR-003**: Exit codes: 0 = success, 1 = user error, 2 = usage error. Consistent across all commands.
- **NFR-004**: All curated skills must pass the pytest skill test suite in `tests/skills/` before merging. The suite covers schema validation (FR-023–FR-024), security audit (FR-025–FR-026), and framework contract compliance (FR-016–FR-022). Tests are parametrized and activate automatically as each skill is implemented.
- **NFR-005**: The `tests/skills/` suite must always pass in CI with zero FAIL-level findings. New skills added to `skills/.curated/` that fail schema, security, or contract tests must not be merged.
- **NFR-006**: The repository MUST maintain two distinct root-level documentation entry points: `README.md` targeting **end users** (clinical teams consuming the skills — install, configure, quickstart, command reference) and `DEVELOPER.md` targeting **contributors** (skill authors and framework developers — dev setup, test suite, skill authoring workflow, spec structure). Content appropriate to one audience MUST NOT be co-mingled into the other file.

### Key Entities

- **Topic**: A clinical knowledge domain under `topics/<name>/`. The primary organizational unit.
- **Source Artifact (L1)**: A raw input file registered via `rh-skills ingest`. Tracked by path, type, SHA-256 checksum, and timestamp.
- **Structured Artifact (L2)**: A semi-structured YAML file in `topics/<name>/structured/` produced by `rh-skills promote derive`.
- **Computable Artifact (L3)**: A fully structured YAML file in `topics/<name>/computable/` produced by `rh-skills promote combine`. Contains FHIR-compatible pathways, measures, and value sets.
- **Plan Artifact**: A Markdown file with YAML front matter in `topics/<name>/process/plans/<skill>-plan.md`. Required input for the corresponding `implement` mode. **Exception**: `rh-inf-discovery` uses `discovery-plan.yaml` (pure YAML) + `discovery-readout.md` (generated narrative) instead of a single `.md` file.
- **tracking.yaml**: Repo-root YAML file recording all topics, sources, artifacts, and lifecycle events.
- **Event**: A named entry appended to `tracking.yaml` by any skill mode that modifies state.

### Assumptions

- Python 3.13+ and `uv` are installed by all end users and contributors.
- SHA-256 is computed via Python `hashlib` — no external tools required.
- `pdftotext` and `pandoc` are optional — their absence is detected at runtime and handled gracefully.
- All clinical content stays inside the repo; no PHI in any artifact.
- All topics are scoped to this repo; multi-repo federation is out of scope.

---

## Deliverables

All items below are implemented and committed on branch `002-rh-agent-skills`.

### CLI (`src/hi/commands/`)
- `init.py` — `rh-skills init`
- `list_cmd.py` — `rh-skills list`
- `status.py` — `rh-skills status` group: `show`, `progress`, `next-steps`, `check-changes`
- `ingest.py` — `rh-skills ingest` group: `plan`, `implement`, `verify`
- `promote.py` — `rh-skills promote` group: `derive`, `combine`
- `validate.py` — `rh-skills validate`
- `test_cmd.py` — `rh-skills test`

### Tests (`tests/`)
- `unit/test_init.py`, `test_list.py`, `test_status.py`, `test_status_extended.py`
- `unit/test_ingest.py`, `test_promote.py`, `test_validate.py`, `test_test_cmd.py`
- `skills/conftest.py` — shared skill test fixtures
- `skills/test_skill_schema.py` — schema + template validation (FR-023, FR-024)
- `skills/test_skill_security.py` — security audit (FR-025, FR-026)
- `skills/test_skill_audit.py` — framework contract compliance (FR-016–FR-022)

### Skill Template (`skills/_template/`)
- `SKILL.md` — canonical three-level progressive disclosure template
- `reference.md` — Level 3: schemas, clinical standards, glossary
- `examples/plan.md`, `examples/output.md` — worked examples

### Documentation
- `README.md` — end-user guide (install, quickstart, command reference)
- `DEVELOPER.md` — contributor guide (dev setup, skill authoring, test suite)
- `docs/GETTING_STARTED.md` — first topic walkthrough
- `docs/WORKFLOW.md` — lifecycle diagram, many-to-many artifact topology
- `docs/COMMANDS.md` — full `rh-skills` CLI reference
- `docs/SKILL_AUTHORING.md` — step-by-step skill implementation guide

### Open (deferred)
- **T040** — End-to-end integration test (`rh-skills init` → `rh-skills ingest` → `rh-skills promote` → `rh-skills validate` with `diabetes-screening` fixture). Deferred; will be revisited once skill specs 003–008 are in place.
