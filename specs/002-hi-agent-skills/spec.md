# Feature Specification: HI Framework — CLI & Repository Layout

**Feature Branch**: `002-hi-agent-skills`  
**Created**: 2026-04-03 | **Updated**: 2026-04-04  
**Status**: In Progress

## Overview

The HI Framework provides the **deterministic infrastructure** that all HI agent skills depend on. The guiding principle: all deterministic work is handled by `hi` CLI commands — only reasoning lives in agent skill prompts. This spec covers the shared infrastructure:

1. **Repository layout** — a predictable directory structure for topics, sources, and artifacts
2. **`hi` CLI** — Python commands for file tracking, checksums, artifact promotion, validation, and task management
3. **`tracking.yaml`** — the single source of truth for topic lifecycle state
4. **Framework contracts** — conventions all skill specs (003–008) must follow

Each of the six HI agent skills has its own specification:

| Skill | Spec | Purpose |
|-------|------|---------|
| `hi-discovery` | [003-hi-discovery](../003-hi-discovery/) | Guide literature search; produce ingest tasks |
| `hi-ingest` | [004-hi-ingest](../004-hi-ingest/) | Register raw files/URLs with checksums |
| `hi-extract` | [005-hi-extract](../005-hi-extract/) | Derive L2 structured artifacts from L1 sources |
| `hi-formalize` | [006-hi-formalize](../006-hi-formalize/) | Converge L2 artifacts into computable L3 |
| `hi-verify` | [007-hi-verify](../007-hi-verify/) | Validate any artifact at any point |
| `hi-status` | [008-hi-status](../008-hi-status/) | Lifecycle summaries and drift detection |

---

## Repository Layout

```text
sources/                     # Raw source files (L1), repo-wide
plans/                       # Repo-level plan artifacts (hi ingest plan, etc.)
topics/<name>/
  structured/                # Semi-structured L2 artifacts (YAML) — prominent
  computable/                # Computable L3 artifacts (YAML) — prominent
  process/
    plans/                   # Per-topic plan artifacts
      discovery-plan.md      # YAML front matter + prose
      ingest-plan.md         # YAML front matter + prose
      extract-plan.md        # YAML front matter + prose
      formalize-plan.md      # YAML front matter + prose
      tasks.md               # hi tasks tracking
    contracts/               # YAML validation contracts
    checklists/              # Clinical review checklists
    fixtures/                # LLM test fixtures
      results/               # Test run results
    research.md              # Evidence and citations
    conflicts.md             # Source contradictions
skills/.curated/             # Framework-level agent skills (excluded from hi list)
  hi-discovery/SKILL.md
  hi-ingest/SKILL.md
  hi-extract/SKILL.md
  hi-formalize/SKILL.md
  hi-verify/SKILL.md
  hi-status/SKILL.md
tracking.yaml                # Single source of truth for lifecycle state
```

`structured/` and `computable/` are at the topic root for immediate visibility. Process support files are grouped under `process/`.

---

## Skill Framework Conventions

All HI agent skills follow these conventions. They are defined here as the framework contract that specs 003–008 must conform to.

### Mode Pattern

Workflow skills use three modes — `plan` → `implement` → `verify` — passed as the first positional argument:

```
hi-discovery plan
hi-extract implement
hi-ingest verify
```

- **`plan`** — Writes `topics/<name>/process/plans/<skill>-plan.md` with YAML front matter (machine-readable) + Markdown prose (human review). No other files created or modified.
- **`implement`** — Reads YAML front matter from the plan artifact and executes it by invoking `hi` CLI commands. Fails immediately if no plan exists.
- **`verify`** — Non-destructive validation only. Never modifies any file.

### Re-run Guard

Every `plan` and `implement` mode MUST warn and stop if its expected output already exists. A `--force` flag MUST be supported to overwrite.

### Event Tracking

Every skill mode that modifies state MUST append a named event to `tracking.yaml`.

### Skill File Location

All skills reside at `skills/.curated/<skill-name>/SKILL.md`, following the anthropic skills-developer SKILL.md template. The `.curated/` dot-prefix excludes framework skills from `hi list` output.

---

## CLI Commands

The `hi` CLI handles all deterministic operations. Skills invoke these; they never perform deterministic work directly.

| Command | Description |
|---------|-------------|
| `hi init <name>` | Create topic scaffold + register in tracking.yaml |
| `hi list` | List topics (excludes dot-prefixed dirs) |
| `hi ingest plan` | Generate `plans/ingest-plan.md` with sources to register |
| `hi ingest implement <file>` | Register a source: path, type, checksum, timestamp |
| `hi ingest verify` | Confirm all sources unchanged since ingest |
| `hi promote derive <topic> <name>` | Create L2 structured artifact scaffold |
| `hi promote combine <topic> <sources…> <target>` | Merge L2 artifacts into L3 computable artifact |
| `hi validate <topic> <artifact>` | Schema-validate any named artifact |
| `hi status show <topic>` | Show lifecycle state from tracking.yaml |
| `hi status progress <topic>` | Pipeline bar + completeness % |
| `hi status next-steps <topic>` | Recommend single next action with exact command |
| `hi status check-changes <topic>` | Re-checksum sources; report drift and stale artifacts |
| `hi tasks list [<topic>]` | List tasks from tasks.md |
| `hi tasks add <topic> <task>` | Append a task |
| `hi tasks complete <topic> <task-id>` | Mark task complete |
| `hi test <topic> <skill>` | Run skill against fixtures; write results |

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

A user installs `hi` via `uv tool install hi` and initializes a new clinical topic. `hi init diabetes-screening` creates the full directory scaffold and registers the topic. `hi list` confirms it is visible. The user can immediately start working with agent skills.

**Acceptance Scenarios**:
1. **Given** an empty repo, **When** `hi init <name>` runs, **Then** `topics/<name>/structured/`, `computable/`, and `process/` (with all subdirs) are created and tracking.yaml is updated.
2. **Given** a topic exists, **When** `hi list` runs, **Then** the topic name and title are shown.
3. **Given** a topic exists, **When** `hi init <name>` runs again, **Then** it warns about existing topic and stops.

### User Story: Source Registration via CLI

A team member registers a downloaded PDF directly with the CLI. `hi ingest implement guidelines.pdf` records the file path, type, SHA-256 checksum, and timestamp in tracking.yaml. Later, `hi ingest verify` confirms the file is unchanged.

**Acceptance Scenarios**:
1. **Given** a source file, **When** `hi ingest implement <file>` runs, **Then** path, type, checksum, and timestamp are in tracking.yaml.
2. **Given** an ingested file is modified, **When** `hi ingest verify` runs, **Then** the file is flagged with original vs. current checksum.
3. **Given** a file path does not exist, **When** `hi ingest implement <file>` runs, **Then** it exits non-zero with a clear error.

### User Story: Artifact Promotion

A team member runs `hi promote derive diabetes-screening screening-criteria` to scaffold a new L2 structured artifact. After editing the YAML file, they run `hi promote combine diabetes-screening screening-criteria risk-factors diabetes-pathway` to create the L3 computable artifact.

**Acceptance Scenarios**:
1. **Given** a topic exists, **When** `hi promote derive <topic> <name>` runs, **Then** `topics/<topic>/structured/<name>.yaml` is created with a schema-valid scaffold and the topic's `structured[]` array in tracking.yaml is updated.
2. **Given** a structured artifact already exists, **When** `hi promote derive <topic> <name>` runs **without** `--force`, **Then** it warns and exits non-zero without modifying the existing file.
3. **Given** structured artifacts exist, **When** `hi promote combine <topic> <sources…> <target>` runs, **Then** `topics/<topic>/computable/<target>.yaml` is created and tracking.yaml `computable[]` is updated with the source artifact names listed in `converged_from`.
4. **Given** a named source artifact does not exist, **When** `hi promote combine` runs, **Then** it exits non-zero with a clear error identifying the missing artifact.

### User Story: Artifact Validation

A team member runs `hi validate diabetes-screening screening-criteria` to confirm the L2 artifact meets schema requirements before proceeding to formalize.

**Acceptance Scenarios**:
1. **Given** a valid L2 artifact, **When** `hi validate <topic> <artifact>` runs, **Then** it exits 0 and prints a pass summary.
2. **Given** an L2 artifact with missing required fields, **When** `hi validate` runs, **Then** it exits 1 and reports each missing required field with its location.
3. **Given** an L2 artifact with missing optional fields, **When** `hi validate` runs, **Then** it exits 0 and emits advisory warnings only.
4. **Given** an artifact name that does not exist in either `structured/` or `computable/`, **When** `hi validate` runs, **Then** it exits non-zero with a clear error.

### User Story: Skill Validation & Security

A skill author implements `hi-extract` by copying `skills/_template/`, filling in the SKILL.md, and adding companion files. Before merging, the CI suite runs `tests/skills/` which automatically picks up the new skill via the parametrized `curated_skill` fixture. The author must address any schema, security, or framework contract findings before the PR is accepted.

**Acceptance Scenarios**:
1. **Given** a new skill dir with a valid SKILL.md, **When** `uv run pytest tests/skills/` runs, **Then** all schema and contract tests pass for the new skill.
2. **Given** a SKILL.md with an unfilled `<skill-name>` placeholder, **When** the test suite runs, **Then** `test_no_unfilled_placeholders` fails with a clear message identifying the placeholder.
3. **Given** a SKILL.md whose `name` field does not match its directory name, **When** the test suite runs, **Then** `test_name_matches_directory` fails.
4. **Given** a SKILL.md that reads external files without a prompt-injection boundary rule, **When** the test suite runs, **Then** `test_no_prompt_injection_without_boundary` fails with a PROMPT_INJECTION finding.
5. **Given** a SKILL.md `verify` mode that directly writes to `tracking.yaml`, **When** the test suite runs, **Then** `test_verify_mode_does_not_write_tracking_directly` fails.
6. **Given** all six curated skills are implemented and passing, **When** `uv run pytest tests/` runs, **Then** all 31 previously-skipped skill tests activate and pass.

### Edge Cases

- `hi init` on an already-initialized topic — warn and stop.
- `hi promote derive` for an artifact that already exists — warn and stop.
- `hi validate` for a non-existent artifact — exit with clear error.
- `hi ingest verify` when tracking.yaml has no sources — exit cleanly with informational message.
- `hi list` when no `tracking.yaml` exists — exit 0 with informational message; do not create the file.
- `hi status show` / `hi status progress` for a topic not in tracking.yaml — exit non-zero with clear error identifying the unknown topic.

---

## Requirements

### Functional Requirements

**Repository Initialization**

- **FR-001**: `hi init <name>` MUST create `topics/<name>/structured/`, `topics/<name>/computable/`, and `topics/<name>/process/` with the full subdirectory scaffold (`plans/`, `contracts/`, `checklists/`, `fixtures/`, `fixtures/results/`). It MUST create stub files: `process/research.md`, `process/conflicts.md`, `process/plans/tasks.md`.
- **FR-002**: `hi init <name>` MUST register the new topic in `tracking.yaml` with `name`, `title`, `created_at`, and empty `structured`, `computable`, and `events` lists.
- **FR-003**: `hi list` MUST enumerate directories under `topics/`, excluding dot-prefixed directories.

**Source Registration**

- **FR-004**: `hi ingest plan` MUST generate `plans/ingest-plan.md` at the repo root as a structured Markdown file with YAML front matter listing source paths/URLs to register.
- **FR-005**: `hi ingest implement <file>` MUST register the source in `tracking.yaml` with: file path (relative to repo root), detected file type, SHA-256 checksum, and ISO 8601 ingest timestamp. It MUST exit non-zero if the file does not exist.
- **FR-006**: Supported file types MUST include: PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), and online article URLs. For PDF, `pdftotext` (poppler) enables text extraction; for Word/Excel, `pandoc`. If the tool is absent, ingest MUST register metadata and checksum but emit a warning — it MUST NOT fail hard.
- **FR-007**: `hi ingest verify` MUST compare current SHA-256 checksums of all registered sources against stored values and report any changed or missing files.

**Artifact Promotion**

- **FR-008**: `hi promote derive <topic> <name>` MUST create `topics/<topic>/structured/<name>.yaml` with a schema-valid scaffold. It MUST fail if the artifact already exists (unless `--force`).
- **FR-009**: `hi promote combine <topic> <sources…> <target>` MUST create `topics/<topic>/computable/<target>.yaml` by merging content from all named structured source artifacts. It MUST fail if any source artifact does not exist.

**Artifact Validation**

- **FR-010**: `hi validate <topic> <artifact>` MUST validate the named artifact against its schema (L2 or L3 based on location) and report required-field errors (exit non-zero) and optional-field warnings (exit zero).

**Task Tracking**

- **FR-011**: `hi tasks list [<topic>]` MUST read `topics/<topic>/process/plans/tasks.md` (or root `plans/tasks.md`) and display tasks with completion state.
- **FR-012**: `hi tasks add <topic> <task>` MUST append a new unchecked task to `topics/<topic>/process/plans/tasks.md`.
- **FR-013**: `hi tasks complete <topic> <task-id>` MUST mark the specified task complete in tasks.md.

**Skill Testing**

- **FR-014**: `hi test <topic> <skill>` MUST run the named skill against fixture inputs in `topics/<topic>/process/fixtures/` and write results to `topics/<topic>/process/fixtures/results/`.

**Topic Status**

- **FR-015**: `hi status show <topic>` MUST display current lifecycle state from tracking.yaml: source count, structured artifact count, computable artifact count, current stage, and last event timestamp. `hi status progress <topic>` MUST display a pipeline bar, completeness percentage, and per-level artifact counts. `hi status next-steps <topic>` MUST output a single recommended next action and the exact `hi` or skill command to run. `hi status check-changes <topic>` MUST re-checksum all registered sources and report any changed or missing files (exit 1) and any structured artifacts derived from changed sources (stale downstream). `hi status check-changes` MUST be read-only — it MUST NOT modify tracking.yaml or any artifact.

**Framework Contracts for Skills**

- **FR-016**: All skill SKILL.md files MUST reside at `skills/.curated/<skill-name>/SKILL.md` and MUST follow the anthropic skills-developer SKILL.md template.
- **FR-017**: Skills MUST NOT perform deterministic operations directly — all file I/O, checksum computation, schema validation, and tracking updates MUST be delegated to `hi` CLI commands.
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

- **NFR-001**: CLI implemented in Python 3.13+ using `click >= 8.0` and `ruamel.yaml >= 0.18`. End users install via `uv tool install hi`.
- **NFR-002**: All CLI commands must have pytest unit tests in `tests/unit/`. No external tool required for core operations (`pdftotext`, `pandoc` optional with graceful degradation).
- **NFR-003**: Exit codes: 0 = success, 1 = user error, 2 = usage error. Consistent across all commands.
- **NFR-004**: All curated skills must pass the pytest skill test suite in `tests/skills/` before merging. The suite covers schema validation (FR-023–FR-024), security audit (FR-025–FR-026), and framework contract compliance (FR-016–FR-022). Tests are parametrized and activate automatically as each skill is implemented.
- **NFR-005**: The `tests/skills/` suite must always pass in CI with zero FAIL-level findings. New skills added to `skills/.curated/` that fail schema, security, or contract tests must not be merged.

### Key Entities

- **Topic**: A clinical knowledge domain under `topics/<name>/`. The primary organizational unit.
- **Source Artifact (L1)**: A raw input file registered via `hi ingest`. Tracked by path, type, SHA-256 checksum, and timestamp.
- **Structured Artifact (L2)**: A semi-structured YAML file in `topics/<name>/structured/` produced by `hi promote derive`.
- **Computable Artifact (L3)**: A fully structured YAML file in `topics/<name>/computable/` produced by `hi promote combine`. Contains FHIR-compatible pathways, measures, and value sets.
- **Plan Artifact**: A Markdown file with YAML front matter in `topics/<name>/process/plans/<skill>-plan.md`. Required input for the corresponding `implement` mode.
- **tracking.yaml**: Repo-root YAML file recording all topics, sources, artifacts, and lifecycle events.
- **Event**: A named entry appended to `tracking.yaml` by any skill mode that modifies state.

### Assumptions

- Python 3.13+ and `uv` are installed by all end users and contributors.
- SHA-256 is computed via Python `hashlib` — no external tools required.
- `pdftotext` and `pandoc` are optional — their absence is detected at runtime and handled gracefully.
- All clinical content stays inside the repo; no PHI in any artifact.
- All topics are scoped to this repo; multi-repo federation is out of scope.
