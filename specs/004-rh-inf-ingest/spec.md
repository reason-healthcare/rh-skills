# Feature Specification: rh-inf-ingest Skill

**Feature Branch**: `004-rh-inf-ingest`  
**Created**: 2026-04-04  
**Updated**: 2026-04-05  
**Status**: ✅ Complete  
**Depends On**: [002 — RH Skills](../002-rh-agent-skills/), [003 — rh-inf-discovery](../003-rh-inf-discovery/)

## Overview

`rh-inf-ingest` is an agent skill that takes all files present in `sources/` (downloaded by `rh-inf-discovery` or placed manually) through three sequential stages: **Normalize → Classify → Annotate**. The result is a set of normalized Markdown files, classification metadata in `tracking.yaml`, and concept annotations in normalized source frontmatter.

It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | Summary of sources to process; access advisories for authenticated sources | `rh-skills status <topic>`, `rh-skills validate --plan` |
| `implement` | Normalized `.md` per source; classifications in `tracking.yaml`; annotated `.md` with `concepts[]` in frontmatter | `rh-skills ingest normalize`, `rh-skills ingest classify`, `rh-skills ingest annotate` |
| `verify` | Per-source report: normalized ✓/✗, classified ✓/✗, annotated ✓/✗ | `rh-skills ingest verify` |

All three stages run in sequence during `implement`. Sources arrive in `sources/` via `rh-inf-discovery` downloads or manual placement — ingest treats them identically.

## Pipeline Stages

### 1. Normalize
Converts each source file to a clean Markdown file at `sources/normalized/<name>.md`:
- PDF → `pdftotext` (poppler); fallback: register with `text_extracted: false` warning
- Word (`.docx`) / Excel (`.xlsx`) → `pandoc`
- HTML → `pandoc` or Python `html2text`
- Plain text / Markdown → copied as-is
- Soft failure: if tool is absent, register metadata + checksum and warn; do not halt

### 2. Classify
Assigns `type`, `evidence_level`, and `domain_tags` to each source:
- Agent proposes classification based on normalized content and filename
- If `discovery-plan.yaml` is present with a matching entry, uses its `type` and `evidence_level` as the starting proposal
- User confirms before writing; writes `source_classified` event to `tracking.yaml`

### 3. Annotate
Reads each `sources/normalized/<name>.md` and updates concept frontmatter:
- Agent identifies key concepts (clinical terms, codes, guideline references, quality measures)
- Writes `concepts[]` entries in normalized frontmatter
- Writes `source_annotated` event to `tracking.yaml`

## User Stories

### US1 — Ingest After Discovery
A clinical informaticist has completed `rh-inf-discovery` — open-access sources are already downloaded to `sources/`. They run `rh-inf-ingest plan young-adult-hypertension` — the agent lists files present and checks normalization tool availability. After confirming, `rh-inf-ingest implement` normalizes all sources, classifies each (using discovery-plan.yaml as enrichment if present), and annotates them — writing concept entries into each source's normalized frontmatter.

### US2 — Manual Source Entry
A researcher drops a society guideline PDF into `sources/` directly. They run `rh-inf-ingest implement <topic>` — the agent normalizes it, proposes classification based on content, waits for confirmation, and annotates it with concept entries in normalized frontmatter.

**Independent Test**: Place a fixture PDF in `sources/`, run `rh-inf-ingest implement` — confirm `sources/normalized/<name>.md` exists, classification is written to `tracking.yaml`, and the normalized file's frontmatter contains at least one `concepts[]` entry.

## Acceptance Scenarios

1. **Given** files are present in `sources/`, **When** `rh-inf-ingest implement` runs, **Then** each file is normalized to `sources/normalized/<name>.md`, classified in `tracking.yaml`, and annotated — regardless of how it arrived.
2. **Given** `discovery-plan.yaml` is present, **When** the classify stage runs, **Then** the agent uses its `type` and `evidence_level` as the starting classification proposal and confirms with the user before writing.
3. **Given** no `discovery-plan.yaml` exists, **When** the classify stage runs, **Then** the agent proposes classification from file content and confirms with the user.
4. **Given** `pdftotext` is not installed, **When** a PDF source is normalized, **Then** checksum and metadata are registered with `text_extracted: false`; the command does not halt.
5. **Given** `rh-inf-ingest implement` has run, **When** `rh-inf-ingest verify` runs, **Then** every source shows normalized ✓/✗, classified ✓/✗, annotated ✓/✗.
6. **Given** `rh-inf-ingest implement` has already processed a source, **When** run again, **Then** each stage is skipped for that source (idempotent on tracking events).
7. **Given** all sources are annotated, **Then** each normalized source's frontmatter contains `concepts[]` entries with `name` and `type` fields.

## Requirements

### Functional Requirements

**Plan mode**
- **FR-001**: `rh-inf-ingest plan <topic>` MUST list source files present in `sources/`, check normalization tool availability (`pdftotext`, `pandoc`), and display a pre-flight summary. Does not require a discovery plan.
- **FR-002**: Plan mode MUST NOT normalize, classify, or annotate any source.

**Implement mode**
- **FR-004**: `rh-inf-ingest implement <topic>` MUST run all three stages in order: Normalize → Classify → Annotate. Each stage reports per-source results before the next begins.
- **FR-007**: Normalize stage MUST call `rh-skills ingest normalize <file> --topic <topic>` for each source in `sources/`, producing `sources/normalized/<name>.md`. If a normalization tool is absent, register `text_extracted: false` in `tracking.yaml` and continue.
- **FR-008**: Classify stage MUST propose classification for every source. If `discovery-plan.yaml` is present and contains a matching entry, use its `type` and `evidence_level` as the starting proposal. The agent MUST confirm with the user before calling `rh-skills ingest classify`.
- **FR-009**: Annotate stage MUST call `rh-skills ingest annotate <name> --topic <topic>` for each normalized source, which writes `concepts[]` entries into `sources/normalized/<name>.md` frontmatter. Existing concepts are preserved unless `--overwrite` is used for a source.
- **FR-010**: Successful normalize → `source_normalized` event in `tracking.yaml`. Successful classify → `source_classified`. Successful annotate → `source_annotated`.
- **FR-011**: `rh-inf-ingest implement` with `--dry-run` MUST report what would happen per stage without writing any files or events.

**Verify mode**
- **FR-012**: `rh-inf-ingest verify <topic>` MUST check and report per source: file present in `sources/` ✓/✗, `sources/normalized/<name>.md` exists ✓/✗, classified in `tracking.yaml` ✓/✗, annotated ✓/✗.
- **FR-013**: Verify mode MUST check that annotated normalized sources have valid `concepts[]` frontmatter entries (each entry has `name` and `type`) and report any malformed entries.
- **FR-014**: Verify mode MUST NOT write any files or append events to `tracking.yaml`.
- **FR-015**: If a source's checksum in `tracking.yaml` differs from the file on disk, verify MUST flag it as `CHANGED` and recommend `rh-skills ingest implement --force`.
- **FR-016** *(future)*: `rh-skills ingest normalize` SHOULD support a `--js-render` flag for HTML sources whose content is rendered by JavaScript (SPAs, dynamically loaded pages). When `--js-render` is given, the CLI MUST use Playwright (`playwright install chromium`) to load the page in a headless browser, wait for network idle, then capture `page.content()` before passing to markdownify. Playwright MUST be an optional dependency (`pip install playwright`) — absence of Playwright with `--js-render` MUST exit 1 with an install hint rather than silently returning empty content. Without `--js-render`, static HTML is assumed.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/rh-inf-ingest/SKILL.md` and follow the SKILL.md template.
- **NFR-002**: All deterministic operations (download, normalize, classify, annotate, checksum, tracking writes) MUST be delegated to `rh-skills ingest` CLI subcommands — never raw file writes from the agent.
- **NFR-003**: Skill MUST declare an injection boundary before reading any normalized source content (source files may contain adversarial text).

## Data Model

### New artifacts produced

| Artifact | Path | Format |
|----------|------|--------|
| Normalized source | `sources/normalized/<name>.md` | Markdown |

### `tracking.yaml` events added

| Event | Stage | Key fields |
|-------|-------|------------|
| `source_normalized` | Normalize | `name`, `path`, `normalized_path`, `text_extracted`, `timestamp` |
| `source_classified` | Classify | `name`, `type`, `evidence_level`, `domain_tags`, `timestamp` |
| `source_annotated` | Annotate | `name`, `concept_count`, `timestamp` |

## Edge Cases

- **No discovery plan**: classify stage proposes classification from normalized content for all sources.
- **Duplicate concept names across sources**: preserved as separate entries; each entry carries its own `sources[]` backlink.
- **Partial run recovery**: each stage is idempotent — re-running skips sources that already have the corresponding `tracking.yaml` event.
- **Source from discovery with plan enrichment**: if `discovery-plan.yaml` is present and has a matching entry, classify uses its `type`/`evidence_level` as the starting proposal — user still confirms.

## Notes

- `rh-skills ingest normalize`, `rh-skills ingest classify`, and `rh-skills ingest annotate` are new CLI subcommands to be implemented in this spec; `rh-skills source download --url` is the URL acquisition command (owned by spec 003).
- Source frontmatter `concepts[]` feeds into `rh-inf-extract` (005) via `concepts-plan.yaml`, where they are aggregated, enriched with standardized codes, and reviewed before L2 artifact derivation.
- Change detection (checksum drift) surfaced by `rh-inf-ingest verify` is also the precursor to `rh-inf-status check-changes` (008).
- The injection boundary (NFR-003) is critical: normalized source content is user-supplied and may contain prompt injection attempts.
