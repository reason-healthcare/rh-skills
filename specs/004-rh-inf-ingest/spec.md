# Feature Specification: rh-inf-ingest Skill

**Feature Branch**: `004-rh-inf-ingest`  
**Created**: 2026-04-04  
**Updated**: 2026-04-05  
**Status**: Draft  
**Depends On**: [002 — RH Skills](../002-rh-agent-skills/), [003 — rh-inf-discovery](../003-rh-inf-discovery/)

## Overview

`rh-inf-ingest` is an agent skill that takes sources from a `discovery-plan.yaml` (or manually placed files) through four sequential stages: **Download → Normalize → Classify → Annotate**. The result is a set of normalized Markdown files, classification metadata in `tracking.yaml`, inline concept annotations in each normalized file, and a de-duped `concepts.yaml` for the topic.

It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | Summary of sources to process; access advisories for authenticated sources | `rh-skills status <topic>`, `rh-skills validate --plan` |
| `implement` | Normalized `.md` per source; classifications in `tracking.yaml`; annotated `.md`; `concepts.yaml` | `rh-skills ingest implement --url`, `rh-skills ingest normalize`, `rh-skills ingest classify`, `rh-skills ingest annotate` |
| `verify` | Per-source report: normalized ✓/✗, classified ✓/✗, annotated ✓/✗; `concepts.yaml` validity | `rh-skills ingest verify` |

All four stages run in sequence during `implement`. A user may enter mid-pipeline — manually placing a file in `sources/` skips the download stage.

## Pipeline Stages

### 1. Download
Reads `topics/<topic>/process/plans/discovery-plan.yaml` and fetches each source with `access: open`:
- Downloads to `sources/<name>.<ext>`, computes SHA-256, registers in `tracking.yaml`
- For `access: authenticated` or `access: manual` sources: prints the `auth_note` advisory and skips — user must place the file manually
- Idempotent: skips sources already present in `sources/` with matching checksum

### 2. Normalize
Converts each source file to a clean Markdown file at `sources/<name>/normalized.md`:
- PDF → `pdftotext` (poppler); fallback: register with `text_extracted: false` warning
- Word (`.docx`) / Excel (`.xlsx`) → `pandoc`
- HTML → `pandoc` or Python `html2text`
- Plain text / Markdown → copied as-is
- Soft failure: if tool is absent, register metadata + checksum and warn; do not halt

### 3. Classify
Assigns `type`, `evidence_level`, and `domain_tags` to each source:
- Discovery sources: classification already present in `discovery-plan.yaml` → copy to `tracking.yaml` record
- Manually placed sources: agent proposes classification; user confirms before writing
- Writes `source_classified` event to `tracking.yaml`

### 4. Annotate
Reads each `normalized.md` and adds inline concept markers; produces de-duped `concepts.yaml`:
- Agent identifies key concepts (clinical terms, codes, guideline references, quality measures)
- Annotates the normalized file with `<!-- concept: <name> -->` markers
- Aggregates all concepts across sources into `topics/<topic>/process/concepts.yaml`, de-duped by name
- Writes `source_annotated` event to `tracking.yaml`

## User Stories

### US1 — Ingest from Discovery Plan
A clinical informaticist has completed `rh-inf-discovery` and has a `discovery-plan.yaml` with 12 sources (8 open-access, 4 authenticated). They run `rh-inf-ingest plan young-adult-hypertension` — the agent summarizes what will be downloaded, what requires manual placement, and what normalization tools are available. After confirming, `rh-inf-ingest implement` downloads 8 PDFs, normalizes all 12 (including 4 already placed manually), classifies each, and annotates them — producing `concepts.yaml` with 47 de-duped terms.

### US2 — Manual Source Entry (No Discovery Plan)
A researcher drops a society guideline PDF into `sources/` directly without running discovery. They run `rh-inf-ingest implement <topic>` — the agent detects the untracked file, normalizes it, prompts for classification, annotates it, and adds its concepts to `concepts.yaml`.

**Independent Test**: Place a fixture PDF in `sources/`, run `rh-inf-ingest implement` — confirm `normalized.md` exists, classification is written to `tracking.yaml`, and `concepts.yaml` contains at least one concept from the file.

## Acceptance Scenarios

1. **Given** a `discovery-plan.yaml` with `access: open` sources, **When** `rh-inf-ingest implement` runs, **Then** each open source is downloaded to `sources/<name>.<ext>`, normalized to `sources/<name>/normalized.md`, classified in `tracking.yaml`, and annotated.
2. **Given** a `discovery-plan.yaml` with `access: authenticated` sources, **When** `rh-inf-ingest implement` runs, **Then** the agent prints the `auth_note` advisory for each and skips download — it does not fail.
3. **Given** a manually placed file in `sources/` not in the discovery plan, **When** `rh-inf-ingest implement` runs, **Then** the agent detects it, normalizes it, prompts for classification, and annotates it.
4. **Given** `pdftotext` is not installed, **When** a PDF source is normalized, **Then** checksum and metadata are registered with `text_extracted: false`; the command does not halt.
5. **Given** `rh-inf-ingest implement` has run, **When** `rh-inf-ingest verify` runs, **Then** every source shows normalized ✓/✗, classified ✓/✗, annotated ✓/✗; and `concepts.yaml` is reported valid or lists schema errors.
6. **Given** `rh-inf-ingest implement` has already downloaded a source, **When** run again, **Then** the download step is skipped for that source (idempotent on checksum match).
7. **Given** all sources are annotated, **Then** `concepts.yaml` contains de-duped entries with `name`, `type`, `sources[]` (list of source names that reference the concept).

## Requirements

### Functional Requirements

**Plan mode**
- **FR-001**: `rh-inf-ingest plan <topic>` MUST read `topics/<topic>/process/plans/discovery-plan.yaml` (if present) and display a pre-flight summary: count of open-access sources to download, authenticated sources requiring manual placement (with `auth_note`), manually placed files already in `sources/`, and normalization tool availability (`pdftotext`, `pandoc`).
- **FR-002**: If no `discovery-plan.yaml` exists, the plan summary MUST list only manually placed files found in `sources/` not yet tracked in `tracking.yaml`.
- **FR-003**: Plan mode MUST NOT download, normalize, classify, or annotate any source.

**Implement mode**
- **FR-004**: `rh-inf-ingest implement <topic>` MUST run all four stages in order: Download → Normalize → Classify → Annotate. Each stage reports per-source results before the next begins.
- **FR-005**: Download stage MUST call `rh-skills ingest implement --url <url> --name <name> --topic <topic>` for each `access: open` source in `discovery-plan.yaml`; skip sources already present with matching checksum.
- **FR-006**: For `access: authenticated` or `access: manual` sources, the agent MUST print the `auth_note` advisory and skip without error. If the file is already present in `sources/` (manually placed), it MUST proceed to normalize.
- **FR-007**: Normalize stage MUST call `rh-skills ingest normalize <file> --topic <topic>` for each source, producing `sources/<name>/normalized.md`. If a normalization tool is absent, register `text_extracted: false` in `tracking.yaml` and continue.
- **FR-008**: Classify stage MUST copy classification fields (`type`, `evidence_level`, `domain_tags`) from `discovery-plan.yaml` into `tracking.yaml` for discovery sources. For manually placed sources not in the plan, the agent MUST propose classification and wait for user confirmation before calling `rh-skills ingest classify`.
- **FR-009**: Annotate stage MUST call `rh-skills ingest annotate <file> --topic <topic>` for each normalized source, which adds `<!-- concept: <name> -->` markers to `normalized.md` and appends new concepts to `concepts.yaml`. Concepts MUST be de-duped by canonical name across all sources.
- **FR-010**: Successful download MUST append `source_downloaded` event to `tracking.yaml`. Successful normalize → `source_normalized`. Successful classify → `source_classified`. Successful annotate → `source_annotated`.
- **FR-011**: `rh-inf-ingest implement` with `--dry-run` MUST report what would happen per stage without writing any files or events.

**Verify mode**
- **FR-012**: `rh-inf-ingest verify <topic>` MUST check and report per source: file present in `sources/` ✓/✗, `normalized.md` exists ✓/✗, classified in `tracking.yaml` ✓/✗, annotated ✓/✗.
- **FR-013**: Verify mode MUST also validate `concepts.yaml` schema (each entry has `name`, `type`, `sources[]`) and report any errors.
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
| Downloaded source | `sources/<name>.<ext>` | Original format |
| Normalized source | `sources/<name>/normalized.md` | Markdown |
| Concept YAML | `topics/<topic>/process/concepts.yaml` | YAML |

### `concepts.yaml` schema

```yaml
topic: <topic-name>
generated: <ISO-8601>
concepts:
  - name: Hypertension
    type: condition          # condition | medication | procedure | measure | code | term
    sources:
      - ada-guidelines-2024
      - cms-ecqm-cms122
  - name: CMS122
    type: measure
    sources:
      - cms-ecqm-cms122
```

### `tracking.yaml` events added

| Event | Stage | Key fields |
|-------|-------|------------|
| `source_downloaded` | Download | `name`, `url`, `path`, `sha256`, `timestamp` |
| `source_normalized` | Normalize | `name`, `path`, `normalized_path`, `text_extracted`, `timestamp` |
| `source_classified` | Classify | `name`, `type`, `evidence_level`, `domain_tags`, `timestamp` |
| `source_annotated` | Annotate | `name`, `concept_count`, `timestamp` |

## Edge Cases

- **No discovery plan**: skill operates on manually placed files only; classify stage always prompts for all sources.
- **Mixed entry point**: some sources from discovery plan, some manually placed — handled transparently.
- **Duplicate concept names across sources**: de-duped by canonical name; `sources[]` lists all referencing sources.
- **Partial run recovery**: each stage is idempotent — re-running skips sources that already have the corresponding `tracking.yaml` event.
- **Auth source placed manually**: if an `access: authenticated` source appears in both `discovery-plan.yaml` and `sources/`, classification is copied from the plan (no prompt needed).

## Notes

- `rh-skills ingest normalize`, `rh-skills ingest classify`, and `rh-skills ingest annotate` are new CLI subcommands to be implemented in this spec; `rh-skills ingest implement --url` is already implemented (T012/T013 from spec 003).
- `concepts.yaml` feeds into `rh-inf-extract` (005) as the structured concept vocabulary for L2 artifact derivation.
- Change detection (checksum drift) surfaced by `rh-inf-ingest verify` is also the precursor to `rh-inf-status check-changes` (008).
- The injection boundary (NFR-003) is critical: normalized source content is user-supplied and may contain prompt injection attempts.
