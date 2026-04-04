# Feature Specification: HI Agent Skills Suite

**Feature Branch**: `002-hi-agent-skills`  
**Created**: 2026-04-03  
**Status**: In Progress  
**Input**: User description: "scaffold out the actual skills. I was thinking we have: a) discovery skills to help with research b) ingest skills to keep track of raw artifacts (PDFs, MS Word, Excel, online articles, research papers) c) extract to build the L2 artifacts d) formalize to build the L3 artifacts. I want to use a pattern where the user can review, so there is a pattern of the skill to build the tasks for that step, and then a skill to implement them. Also we need verification skills along the way. Last, we should have housekeeping skills to show progress, suggest next steps, and show if a file has changed (e.g. the PDF was updated, based on a checksum)"

## Overview

The HI Skills Framework ships a set of **agent skills** — structured prompts invoked by an LLM agent — that guide users through the full clinical knowledge lifecycle. There are **6 skills**, each with **explicit modes** (`plan`, `implement`, `verify`) rather than a flat list of individual skill files. This design keeps the skill library small and predictable: the agent chooses a *stage* (which skill) and a *mode* (what to do), making the plan → implement pattern impossible to accidentally skip.

### Skills and Modes

| Skill | Modes | Purpose |
|-------|-------|---------|
| `hi-discovery` | `plan` · `implement` | Guide literature search; convert to ingest tasks |
| `hi-ingest` | `plan` · `implement` · `verify` | Register raw files/URLs with checksums |
| `hi-extract` | `plan` · `implement` · `verify` | Derive L2 artifacts from L1 sources |
| `hi-formalize` | `plan` · `implement` · `verify` | Converge L2 artifacts into computable L3 |
| `hi-verify` | *(standalone)* | Validate any artifact at any time |
| `hi-status` | `progress` · `next-steps` · `check-changes` | Lifecycle summaries and drift detection |

### Mode semantics

- **`plan`** — Produces a human-reviewable plan artifact at `skills/<name>/plans/<skill>-plan.md`. Format is **structured Markdown with a YAML front matter block** (machine-parseable header for `implement` + human-readable prose body for clinician review). No files outside `plans/` are created or modified. If a plan already exists, the skill warns and stops — use `--force` to overwrite.
- **`implement`** — Reads the YAML front matter from the plan artifact and executes it by calling `hi` CLI commands. Fails immediately if no plan artifact exists. If outputs already exist (e.g. L2 files), warns and stops — use `--force` to overwrite.
- **`verify`** — Runs non-destructive validation against existing artifacts. Never modifies any file.

### Mode invocation

Modes are passed as the **first positional argument** after the skill name:

```
hi-discovery plan
hi-extract implement
hi-status check-changes
```

Skills are invoked by the agent or user via the `$ARGUMENTS` slot in each SKILL.md.

### Skill file location

All 6 framework skills live under `skills/.curated/`:

```
skills/.curated/
  hi-discovery/SKILL.md
  hi-ingest/SKILL.md
  hi-extract/SKILL.md
  hi-formalize/SKILL.md
  hi-verify/SKILL.md
  hi-status/SKILL.md
```

This keeps framework skills separate from clinical skills while remaining inside the skills tree.

### Binary file extraction

`hi-ingest` supports PDF and Word/Excel via optional tools:
- **PDF**: `pdftotext` (part of `poppler-utils`) — `brew install poppler` / `apt install poppler-utils`
- **Word/Excel**: `pandoc` — `brew install pandoc` / `apt install pandoc`

If a required tool is not installed, ingest registers the file's metadata and checksum but emits a warning that text extraction was skipped. Plain text, Markdown, and URL snapshots require no additional tools.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided Discovery (Priority: P1)

A clinical informaticist starting a new topic for "sepsis early detection" needs help identifying what sources to look for. They invoke `hi-discovery plan`, which generates a research plan listing guidelines, terminology systems, and peer-reviewed sources relevant to the domain. After reviewing and optionally editing the plan, they invoke `hi-discovery implement`, which converts the plan into tracked ingest tasks — without downloading or registering anything yet.

**Why this priority**: Discovery is the entry point for every new topic. Without a structured research plan, teams skip important sources and produce incomplete source artifacts.

**Independent Test**: Can be fully tested by running the discovery-plan skill on a new empty topic and verifying that a structured source list is produced as a reviewable artifact.

**Acceptance Scenarios**:

1. **Given** a new initialized topic with no source artifacts, **When** `hi-discovery plan` is invoked, **Then** a discovery plan is written to `topics/<name>/process/plans/discovery-plan.md` with suggested source types and specific examples for the topic's domain.
2. **Given** a discovery plan has been reviewed and approved, **When** `hi-discovery implement` is invoked, **Then** each source in the plan becomes a tracked ingest task in `plans/ingest-plan.md` — no files are registered yet.
3. **Given** a discovery plan artifact exists, **When** `hi-discovery plan` is re-invoked after the domain description changes, **Then** only new or changed source suggestions are added without duplicating existing ones.

---

### User Story 2 - Raw Artifact Ingest with Change Detection (Priority: P1)

A team member downloads a PDF of the latest ADA guidelines and wants to register it as a source artifact. They invoke `hi-ingest plan`, which lists the files to be registered for review. After confirming the list, they invoke `hi-ingest implement`, which records each file with its checksum. Later, when the PDF is updated, `hi-status check-changes` detects the checksum mismatch and flags it for re-ingestion.

**Why this priority**: Ingest is the data entry point; without reliable tracking and change detection, downstream L2 and L3 artifacts may be based on stale sources.

**Independent Test**: Can be tested by ingesting a file, modifying it, and running the housekeeping skill — the changed file must be flagged.

**Acceptance Scenarios**:

1. **Given** a raw source file (PDF, Word, Excel, web article), **When** `hi-ingest implement` is invoked, **Then** the file is registered in tracking with its checksum, file type, source URL or path, and ingest timestamp.
2. **Given** an already-ingested file is modified on disk, **When** `hi-status check-changes` runs, **Then** the file is flagged as changed with the original vs. current checksum shown.
3. **Given** an ingested file is unchanged, **When** `hi-status check-changes` runs, **Then** no change alert is raised for that file.
4. **Given** an online article URL is ingested, **When** `hi-ingest implement` runs, **Then** a local snapshot of the content is saved alongside the URL and timestamp.

---

### User Story 3 - Structured L2 Extraction with Human Review (Priority: P2)

After ingesting ADA guideline PDFs and extracting text, a clinical informaticist wants to derive structured artifacts from the raw content. They invoke `hi-extract plan`, which generates a list of candidate structured (L2) artifacts to be derived (e.g., "screening-criteria", "risk-factors", "diagnostic-thresholds"). The user reviews and edits the plan, then invokes `hi-extract implement`, which calls `hi promote derive` for each planned artifact. Finally, `hi-extract verify` confirms required fields are present in all produced artifacts.

**Why this priority**: Extraction is where clinical reasoning is captured in structured form; human review at the plan stage prevents low-quality or redundant artifacts.

**Independent Test**: Can be tested by running extract-plan on a topic with source artifacts and confirming a candidate structured artifact task list is produced before any files are written.

**Acceptance Scenarios**:

1. **Given** a topic with one or more source artifacts, **When** `hi-extract plan` is invoked, **Then** a list of candidate structured artifact names and their intended content is written to `topics/<name>/process/plans/extract-plan.md` for review.
2. **Given** an extract plan has been reviewed, **When** `hi-extract implement` is invoked, **Then** `hi promote derive` is called for each planned artifact and results are validated with `hi validate`.
3. **Given** `hi-extract implement` runs and a validation failure occurs, **Then** the failure is surfaced with the specific missing fields and no tracking event is written for that artifact.

---

### User Story 4 - L3 Formalization with Human Review (Priority: P2)

A team has produced several structured (L2) artifacts across screening criteria, risk factors, and diagnostic thresholds. They invoke `hi-formalize plan`, which generates a convergence plan identifying which structured artifacts should be combined and what the resulting computable (L3) artifact's sections should contain. After review, `hi-formalize implement` calls `hi promote combine` and validates the result. `hi-formalize verify` then confirms FHIR-compatible section completeness.

**Why this priority**: Formalization produces computable artifacts; errors here propagate to clinical decision support systems, making human review before implementation critical.

**Independent Test**: Can be tested by running formalize-plan on a topic with ≥2 structured artifacts and confirming a convergence plan is written before any computable files are created.

**Acceptance Scenarios**:

1. **Given** a topic with two or more validated structured artifacts, **When** `hi-formalize plan` is invoked, **Then** a convergence plan is written to `topics/<name>/process/plans/formalize-plan.md` showing which structured artifacts will be combined and a draft outline of the computable artifact's sections.
2. **Given** a formalize plan has been reviewed, **When** `hi-formalize implement` is invoked, **Then** `hi promote combine` is called and the resulting computable artifact is validated with `hi validate`.
3. **Given** the formalize step completes, **When** `hi-formalize verify` is invoked, **Then** FHIR-compatible section completeness is confirmed (value sets have codes, measures have numerator/denominator).

---

### User Story 5 - Housekeeping: Progress and Next Steps (Priority: P3)

A team lead wants a quick summary of where a skill stands and what action should happen next. They invoke `hi-status progress`, which reads tracking.yaml and produces a plain-language summary. `hi-status next-steps` recommends the single most important next action with the exact command to run. `hi-status check-changes` detects any source files whose checksum has drifted since ingest.

**Why this priority**: Without actionable progress summaries, teams lose track of where skills stand across multi-week projects.

**Independent Test**: Can be tested by invoking the progress skill on the `diabetes-screening` example and verifying that accurate artifact counts and meaningful next-step suggestions are produced.

**Acceptance Scenarios**:

1. **Given** any topic at any lifecycle stage, **When** `hi-status progress` is invoked, **Then** a summary is produced showing source/structured/computable artifact counts, validation status, and last event timestamp.
2. **Given** a topic with missing validation, **When** `hi-status next-steps` is invoked, **Then** the first recommended action is to run `hi validate` on the unvalidated artifact, with the exact command shown.
3. **Given** a topic where an ingested file has changed checksum, **When** `hi-status check-changes` is invoked, **Then** all changed files are listed with original vs. current checksum and the downstream structured/computable artifacts that depend on them.

---

### Edge Cases

- A topic with no source artifacts attempts to run extract-plan — skill must warn and exit without producing a plan.
- An ingested file is deleted from disk — housekeeping must report it as missing, not just changed.
- A structured artifact's source file has changed — housekeeping must flag the structured artifact as potentially stale.
- extract-implement is run without an extract plan — skill must require a plan artifact before proceeding.
- formalize-plan is invoked when all structured artifacts have required-field validation errors — skill must surface these errors before allowing convergence.
- A source file type is unsupported (e.g., `.zip`) — ingest skill must reject it with a clear message listing supported types.

---

## Requirements *(mandatory)*

### Functional Requirements

**Discovery Skill (`hi-discovery`)**

- **FR-001**: `hi-discovery plan` MUST produce a structured list of suggested source types and specific examples relevant to the topic's domain, saved as `topics/<name>/process/plans/discovery-plan.md`. No other files may be created or modified.
- **FR-002**: `hi-discovery implement` MUST read `topics/<name>/process/plans/discovery-plan.md` and convert each source into a tracked ingest task in `topics/<name>/process/plans/ingest-plan.md`. It MUST fail with a clear error if no discovery plan exists.

**Ingest Skill (`hi-ingest`)**

- **FR-003**: `hi-ingest plan` MUST list all sources to be ingested (from the discovery plan or user-provided) as a reviewable `topics/<name>/process/plans/ingest-plan.md` with YAML front matter listing source paths/URLs before any files are registered.
- **FR-004**: `hi-ingest implement` MUST read `topics/<name>/process/plans/ingest-plan.md` YAML front matter and register each source by recording: file path or URL, file type, ingestion timestamp, and SHA-256 checksum in tracking.yaml. It MUST fail if no ingest plan exists.
- **FR-005**: Supported ingest source types MUST include: PDF, Microsoft Word (.docx), Microsoft Excel (.xlsx), plain text, Markdown, and online article URLs. For PDF, text extraction requires `pdftotext` (poppler); for Word/Excel, `pandoc`. If the required tool is absent, ingest MUST register metadata and checksum but emit a warning that text extraction was skipped — it MUST NOT fail hard.
- **FR-006**: `hi-ingest verify` MUST confirm that all registered sources are still present on disk with matching checksums, reporting any missing or changed files.

**Extract Skill (`hi-extract`)**

- **FR-007**: `hi-extract plan` MUST analyze existing source artifacts and write a `topics/<name>/process/plans/extract-plan.md` proposing a named list of structured (L2) artifacts with a one-sentence description of each artifact's intended content.
- **FR-008**: `hi-extract implement` MUST NOT proceed without a valid `topics/<name>/process/plans/extract-plan.md`; it MUST call `hi promote derive` for each planned structured artifact.
- **FR-009**: `hi-extract verify` MUST run `hi validate` on each L2 artifact produced in the last extract-implement run and report pass/fail per artifact.

**Formalize Skill (`hi-formalize`)**

- **FR-010**: `hi-formalize plan` MUST identify which structured (L2) artifacts will be combined and write a `topics/<name>/process/plans/formalize-plan.md` with a draft outline of the computable (L3) artifact's sections (pathways, measures, value sets, etc.) for human review.
- **FR-011**: `hi-formalize implement` MUST NOT proceed without a valid `topics/<name>/process/plans/formalize-plan.md`; it MUST call `hi promote combine` with the sources listed in the plan.
- **FR-012**: `hi-formalize verify` MUST validate the L3 artifact and check that FHIR-compatible sections (measures, value_sets) contain the minimum required sub-fields.

**Verify Skill (`hi-verify`)**

- **FR-013**: `hi-verify` MUST be invokable at any point to validate any named artifact (L2 or L3) and report required-field errors and optional-field warnings.
- **FR-014**: `hi-verify` MUST be non-destructive — it must never modify any artifact or tracking entry.

**Status Skill (`hi-status`)**

- **FR-015**: `hi-status progress` MUST read tracking.yaml and produce a plain-language summary of lifecycle stage, source/structured/computable artifact counts, last event, and overall completeness percentage.
- **FR-016**: `hi-status next-steps` MUST analyze current skill state and recommend the single most important next action with the exact `hi` CLI command to run.
- **FR-017**: `hi-status check-changes` MUST compare current file checksums against those recorded at ingest time and list all changed, missing, or newly added files. For changed source files, it MUST also list the structured (L2) artifacts derived from them as potentially stale.

**General**

- **FR-018**: Every `plan` mode MUST write its output to `topics/<name>/process/plans/<skill>-plan.md` using **structured Markdown with a YAML front matter block**. The YAML front matter MUST contain all machine-readable fields needed by the corresponding `implement` mode. The Markdown body MUST contain human-readable prose for clinician review. No files outside `topics/<name>/process/plans/` may be created or modified.
- **FR-019**: Every `implement` mode MUST parse the YAML front matter from its corresponding plan file and MUST fail immediately with a clear error if that file does not exist.
- **FR-020**: Every `plan` or `implement` mode MUST warn and stop if its expected output already exists, and MUST support a `--force` flag to overwrite.
- **FR-021**: Every skill mode that modifies the skill state MUST append an event to tracking.yaml.
- **FR-022**: Skills MUST be invokable with the mode as the **first positional argument** (e.g., `hi-discovery plan`). The mode is passed via the `$ARGUMENTS` slot in each SKILL.md.
- **FR-023**: All 6 skill SKILL.md files MUST reside under `skills/.curated/<skill-name>/SKILL.md` and MUST follow the existing anthropic skills-developer SKILL.md template pattern.
- **FR-024**: Skills MUST require no runtime dependencies beyond the existing framework stack (`uv`, `python 3.13+`, `click`, `ruamel.yaml`) for core operations. Optional tools (`pdftotext`, `pandoc`) are permitted for binary file extraction with graceful degradation. End users install the `hi` CLI via `uv tool install hi`.

### Key Entities

- **Topic**: A clinical knowledge domain managed under `topics/<name>/`. Contains source files, structured artifacts, computable artifacts, plans, contracts, checklists, research, and conflicts.
- **Skill** (agent skill): A SKILL.md file in `skills/.curated/<name>/` that an LLM agent invokes. Contains instructions for a specific stage and mode. Six skills total: `hi-discovery`, `hi-ingest`, `hi-extract`, `hi-formalize`, `hi-verify`, `hi-status`.
- **Mode**: The operational phase within a skill — `plan`, `implement`, or `verify` for workflow skills; `progress`, `next-steps`, or `check-changes` for `hi-status`.
- **Plan Artifact**: A human-reviewable Markdown file written by a `plan` mode to `topics/<name>/process/plans/<skill>-plan.md`. Required input for the corresponding `implement` mode.
- **Source Artifact (L1)**: A raw input file (PDF, Word, web snapshot, etc.) registered in `sources/` via `hi-ingest`. Tracked by path, type, SHA-256 checksum, and timestamp.
- **Structured Artifact (L2)**: A semi-structured YAML file in `topics/<name>/structured/` produced by `hi promote derive`. Captures clinical concepts in a human-editable but machine-readable format.
- **Computable Artifact (L3)**: A fully structured YAML file in `topics/<name>/computable/` produced by `hi promote combine`. Contains FHIR-compatible pathways, measures, and value sets.
- **Ingest Record**: An entry in tracking.yaml capturing source path/URL, file type, SHA-256 checksum, and timestamp for a registered raw source.
- **Checksum**: A SHA-256 hash of a source file's content, stored at ingest time and compared on every `hi-status check-changes` invocation.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clinical informaticist with no prior framework experience can complete the full L1 → L2 → L3 lifecycle for a new skill by following skill prompts alone, without consulting additional documentation.
- **SC-002**: Housekeeping-check-changes detects a modified source file within one run after the file is changed on disk, for 100% of tracked files.
- **SC-003**: No implement skill writes any artifact unless a corresponding plan artifact exists — verified across all six skill groups.
- **SC-004**: All plan artifacts produced by plan skills can be understood and edited by a clinician without informatics or engineering background.
- **SC-005**: The full set of skills (all groups, plan + implement + verify) covers the complete lifecycle without requiring the user to invoke the `hi` CLI directly for any core workflow step.
- **SC-006**: Each skill's SKILL.md follows the existing anthropic skills-developer template pattern, making skills immediately invokable without modification.

---

## Assumptions

- Skills are SKILL.md prompt files located at `skills/.curated/<skill-name>/SKILL.md`. Each supports multiple modes via the `$ARGUMENTS` positional convention (first argument = mode).
- Six skills replace what might have been ~14 individual skill files; each SKILL.md uses conditional sections to handle its modes.
- Plan artifacts use **structured Markdown with YAML front matter**: the front matter is parsed by `implement` mode; the prose body is read by clinicians.
- Checksum computation uses Python's `hashlib.sha256` (no external tools required).
- PDF text extraction requires `pdftotext` (poppler); Word/Excel requires `pandoc`. Both are optional — ingest degrades gracefully if absent.
- Online article ingest captures a plain-text snapshot via `curl`; full browser rendering is out of scope.
- Re-running `plan` or `implement` when output already exists results in a warning + stop. `--force` overrides this.
- Skills target a single clinical topic at a time; cross-topic operations are out of scope for this feature.
- The existing `hi promote derive` and `hi promote combine` commands handle LLM invocation; `hi-extract` and `hi-formalize` orchestrate these commands rather than invoking LLMs directly.
- `hi-verify` and all `hi-status` modes are read-only and do not modify any artifact or tracking entry.
- The `hi` CLI is implemented in Python (click + ruamel.yaml) and installed via `uv tool install hi`. Dev setup uses `uv sync`.
