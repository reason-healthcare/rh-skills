# Feature Specification: rh-inf-extract Skill

**Feature Branch**: `005-rh-inf-extract`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — RH Skills](../002-hi-agent-skills/), [004 — rh-inf-ingest](../004-rh-inf-ingest/)

## Overview

`rh-inf-extract` is an agent skill that plans and executes the derivation of structured (L2) artifacts from raw source (L1) files, with a mandatory human review gate between planning and implementation. It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | `topics/<name>/process/plans/extract-plan.md` | `rh-skills status <name>`, `rh-skills list` |
| `implement` | L2 artifacts in `topics/<name>/structured/` | `rh-skills promote derive`, `rh-skills validate` |
| `verify` | Validation report for all L2 artifacts | `rh-skills validate <topic> <artifact>` |

The plan → implement gate prevents low-quality or redundant artifacts by requiring clinical review of the proposed artifact list before any files are written.

## User Story

After ingesting ADA guideline PDFs, a clinical informaticist wants to derive structured artifacts from the raw content. They invoke `rh-inf-extract plan`, which generates a list of candidate structured (L2) artifacts to derive (e.g., "screening-criteria", "risk-factors", "diagnostic-thresholds"). The user reviews and edits the plan, then invokes `rh-inf-extract implement`, which calls `rh-skills promote derive` for each planned artifact. Finally, `rh-inf-extract verify` confirms required fields are present in all produced artifacts.

**Why this priority**: Extraction is where clinical reasoning is captured in structured form; human review at the plan stage prevents low-quality or redundant artifacts.

**Independent Test**: Run `rh-inf-extract plan` on a topic with source artifacts and confirm a candidate structured artifact task list is produced before any L2 files are written.

## Acceptance Scenarios

1. **Given** a topic with one or more source artifacts, **When** `rh-inf-extract plan` is invoked, **Then** a list of candidate structured artifact names and descriptions is written to `topics/<name>/process/plans/extract-plan.md` for review.
2. **Given** an extract plan has been reviewed, **When** `rh-inf-extract implement` is invoked, **Then** `rh-skills promote derive` is called for each planned artifact and results are validated with `rh-skills validate`.
3. **Given** `rh-inf-extract implement` runs and a validation failure occurs, **Then** the failure is surfaced with the specific missing fields and no tracking event is written for that artifact.
4. **Given** no extract plan exists, **When** `rh-inf-extract implement` is invoked, **Then** the skill fails immediately with a clear error.
5. **Given** a topic has no source artifacts, **When** `rh-inf-extract plan` is invoked, **Then** the skill warns and exits without producing a plan.

## Requirements

### Functional Requirements

- **FR-001**: `rh-inf-extract plan` MUST analyze existing source artifacts and write `topics/<name>/process/plans/extract-plan.md` proposing a named list of structured (L2) artifacts, each with a one-sentence description of intended content.
- **FR-002**: The extract plan MUST use structured Markdown with a YAML front matter block. YAML front matter MUST include an `artifacts[]` list where each entry has: `name`, `description`, and `source_files[]`.
- **FR-003**: `rh-inf-extract implement` MUST NOT proceed without a valid `topics/<name>/process/plans/extract-plan.md`; it MUST call `rh-skills promote derive <topic> <name>` for each planned artifact.
- **FR-004**: After each `rh-skills promote derive`, `rh-inf-extract implement` MUST run `rh-skills validate <topic> <name>`. If validation fails, the specific missing fields MUST be surfaced and no `structured_derived` event written for that artifact.
- **FR-005**: `rh-inf-extract verify` MUST run `rh-skills validate` on each L2 artifact produced in the last extract-implement run and report pass/fail per artifact with field-level detail on failures.
- **FR-006**: If `extract-plan.md` already exists, the skill MUST warn and stop unless `--force` is passed.
- **FR-007**: Successful `plan` mode MUST append `extract_planned` to tracking.yaml events. Successful per-artifact `implement` MUST append `structured_derived`.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/rh-inf-extract/SKILL.md` and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: All file writes and validation MUST be delegated to `rh-skills promote derive` and `rh-skills validate` CLI commands.

## Notes

- A single L1 source file may produce multiple L2 artifacts (e.g., one guideline PDF → "screening-criteria", "risk-factors", "diagnostic-thresholds").
- The human review step between `plan` and `implement` is critical — the plan file is intentionally editable.
- L2 artifacts in `topics/<name>/structured/` become inputs to `rh-inf-formalize` (006).
