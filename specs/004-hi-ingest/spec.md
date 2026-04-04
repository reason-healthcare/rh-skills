# Feature Specification: hi-ingest Skill

**Feature Branch**: `004-hi-ingest`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — HI Framework](../002-hi-agent-skills/)

## Overview

`hi-ingest` is an agent skill that wraps the `hi ingest` CLI commands to guide a user through registering raw source artifacts (L1) and detecting changes over time. It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | Display of `plans/ingest-plan.md` for review | `hi ingest plan` |
| `implement` | Sources registered in tracking.yaml | `hi ingest implement <file>` |
| `verify` | Change/missing report for all registered sources | `hi ingest verify` |

The skill wraps CLI commands with guided narrative — explaining what was done, what to review, and what comes next.

## User Story

A team member downloads a PDF of the latest ADA guidelines and wants to register it as a source artifact. They invoke `hi-ingest plan`, which lists the files to be registered for review. After confirming the list, they invoke `hi-ingest implement`, which records each file with its checksum. Later, when the PDF is updated, `hi-ingest verify` detects the checksum mismatch and flags it for re-ingestion.

**Why this priority**: Ingest is the data entry point; without reliable tracking and change detection, downstream L2 and L3 artifacts may be based on stale sources.

**Independent Test**: Ingest a fixture file, modify it, run `hi-ingest verify` — the changed file must be flagged with the original vs. current checksum.

## Acceptance Scenarios

1. **Given** a raw source file (PDF, Word, Excel, web article), **When** `hi-ingest implement` is invoked, **Then** the file is registered in tracking.yaml with checksum, file type, source path, and ingest timestamp.
2. **Given** an already-ingested file is modified on disk, **When** `hi-ingest verify` runs, **Then** the file is flagged as changed with original vs. current checksum shown.
3. **Given** an ingested file is unchanged, **When** `hi-ingest verify` runs, **Then** no change alert is raised for that file.
4. **Given** an online article URL is ingested, **When** `hi-ingest implement` runs, **Then** a local snapshot of the content is saved alongside the URL and timestamp.
5. **Given** `pdftotext` is not installed, **When** a PDF is ingested, **Then** metadata and checksum are registered with a warning that text extraction was skipped — the command does not fail.

## Requirements

### Functional Requirements

- **FR-001**: `hi-ingest plan` MUST invoke `hi ingest plan`, display the generated `plans/ingest-plan.md` content, and guide the user to review the YAML front matter (paths/URLs are editable) before proceeding.
- **FR-002**: `hi-ingest implement` MUST invoke `hi ingest implement <file>` for each source in the ingest plan, report per-source results (✓ registered / ✗ failed), and surface any `text_extracted: false` warnings with remediation hints (`brew install poppler` / `brew install pandoc`).
- **FR-003**: `hi-ingest verify` MUST invoke `hi ingest verify` and format results as a human-readable table (source name, status, checksum delta if changed). It MUST recommend `hi ingest implement --force` for changed files.
- **FR-004**: Supported ingest source types MUST include: PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), and online article URLs.
- **FR-005**: If a required extraction tool is absent (`pdftotext`, `pandoc`), the skill MUST register metadata and checksum but emit a warning — it MUST NOT fail hard.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/hi-ingest/SKILL.md` and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: All deterministic operations (file registration, checksum, tracking writes) MUST be delegated to `hi ingest` CLI commands.

## Notes

- The `hi ingest` CLI commands are fully implemented in `src/hi/commands/ingest.py` as part of spec 002.
- This skill spec covers the SKILL.md narrative that wraps those commands for guided agent use.
- Change detection via `hi-ingest verify` is the precursor to `hi-status check-changes` (008).
