# Feature Specification: `hi-discovery` Skill

**Feature Branch**: `003-hi-discovery`
**Created**: 2026-04-04 | **Updated**: 2026-04-04
**Status**: Draft
**Depends On**: [002 — HI Framework CLI](../002-hi-agent-skills/)

## Overview

`hi-discovery` is the entry point skill for every new clinical topic. It guides an agent through structured source discovery — establishing the evidence landscape before any files are registered or extracted.

**Guiding principle**: all deterministic work via `hi` CLI; all reasoning by the agent.

The skill has three modes:

| Mode | What the agent does | `hi` CLI called | Output |
|------|--------------------|--------------------|--------|
| `plan` | Reasons about the topic domain; identifies source types, specific sources, search strategies, and evidence levels | `hi status show` | `process/plans/discovery-plan.md` |
| `implement` | Converts approved plan entries into actionable ingest tasks | `hi ingest plan` (read-only) | `process/plans/ingest-plan.md` (populated) |
| `verify` | Validates plan structure, evidence coverage, and terminology presence | `hi validate` (read-only) | Exit report (no file writes) |

Discovery is intentionally **read-only with respect to `tracking.yaml`**. No sources are registered; no checksums computed. The sole outputs are plan artifacts for human review.

### Many-to-Many Awareness

Discovery does not name L2 artifacts (that is `hi-extract`'s responsibility). However, the plan should group sources by their expected *contribution type* (criteria source, terminology source, measure reference, FHIR IG) so downstream skills have semantic context.

---

## User Scenarios & Testing

### User Story 1 — Plan discovery for a new topic (Priority: P1)

A clinical informaticist initializes a new topic ("sepsis-early-detection") and wants to know what sources to gather before starting. They invoke `hi-discovery plan`. The agent reasons about the clinical domain, identifies authoritative guidelines, relevant terminology systems, existing measure libraries, and FHIR IGs, and writes a structured, human-reviewable plan.

**Why this priority**: Discovery is the entry point for every topic. Without it, teams skip sources and produce incomplete artifacts.

**Independent Test**: Running `plan` on an initialized empty topic produces a well-formed `discovery-plan.md` with at least one entry per required source category.

**Acceptance Scenarios**:

1. **Given** an initialized topic with no sources, **When** `hi-discovery plan` runs, **Then** `process/plans/discovery-plan.md` is created with YAML frontmatter containing a `sources[]` list; each entry has `name`, `type`, `rationale`, `search_terms[]`, `evidence_level`, and optional `url`.
2. **Given** a topic domain implying coded clinical concepts, **When** `plan` runs, **Then** the plan includes at least one source with `type: terminology` (SNOMED CT, LOINC, ICD-10, or RxNorm).
3. **Given** a plan is produced, **When** the human reviews it, **Then** `research.md` and `conflicts.md` stubs exist in `process/` (created-unless-exists by the plan step).
4. **Given** `discovery-plan.md` already exists, **When** `plan` runs without `--force`, **Then** the skill warns and stops; the existing plan is not modified.
5. **Given** `--force` is passed, **When** `plan` runs, **Then** the existing plan is overwritten and a new `discovery_planned` event is appended to `tracking.yaml`.
6. **Given** `--dry-run` is passed, **When** `plan` runs, **Then** the agent's proposed plan is printed to stdout; no files are written and no events appended.

---

### User Story 2 — Implement the discovery plan (Priority: P1)

After reviewing and editing `discovery-plan.md`, the informaticist runs `hi-discovery implement`. The agent reads the approved plan and populates `ingest-plan.md` with one entry per source, preserving source metadata (type, rationale, evidence level) so `hi-ingest` can execute efficiently.

**Why this priority**: Implement is the bridge from discovery reasoning to actionable ingest tasks. Without it, the plan is advisory only.

**Independent Test**: Running `implement` on a valid plan produces a populated `ingest-plan.md` with one entry per source entry in the plan.

**Acceptance Scenarios**:

1. **Given** a valid `discovery-plan.md`, **When** `hi-discovery implement` runs, **Then** `process/plans/ingest-plan.md` is created (or updated) with one entry per source in the plan's `sources[]` list; each entry carries over `name`, `type`, `url`, `rationale`, and `evidence_level`.
2. **Given** no `discovery-plan.md` exists, **When** `implement` runs, **Then** the skill exits non-zero with a clear error: `discovery-plan.md not found — run hi-discovery plan first`.
3. **Given** `ingest-plan.md` already contains entries, **When** `implement` runs without `--force`, **Then** the skill warns and stops; no entries are overwritten.
4. **Given** `implement` succeeds, **When** complete, **Then** a `discovery_implemented` event is appended to `tracking.yaml`.
5. **Given** `research.md` does not yet exist, **When** `implement` runs, **Then** it creates a stub (create-unless-exists); if it already exists it is not modified.

---

### User Story 3 — Verify discovery quality (Priority: P2)

Before handing off to `hi-ingest`, the informaticist wants confidence that the plan is well-formed and covers the required source categories. `hi-discovery verify` reads the plan and reports any structural issues or coverage gaps without modifying anything.

**Why this priority**: Prevents ingesting from an incomplete plan, which would propagate gaps into L2 and L3.

**Independent Test**: Running `verify` on a complete plan exits 0; running it on a plan missing a terminology source exits 1 with a gap report.

**Acceptance Scenarios**:

1. **Given** a complete, well-formed plan, **When** `hi-discovery verify` runs, **Then** exit 0 and a per-check summary: `✓ frontmatter valid`, `✓ terminology source present`, `✓ all entries have rationale`, etc.
2. **Given** a plan with no terminology source, **When** `verify` runs, **Then** exit 1 with: `✗ No terminology source found — L3 computable artifacts require at least one SNOMED/LOINC/ICD/RxNorm source`.
3. **Given** a plan entry missing `rationale`, **When** `verify` runs, **Then** exit 1 with the source name and missing field identified.
4. **Given** no `discovery-plan.md` exists, **When** `verify` runs, **Then** exit 1 with a clear message; no partial output.
5. **Given** `verify` runs under any condition, **Then** no files are written and `tracking.yaml` is not modified.

---

### Edge Cases

- Topic name contains spaces or special characters — `hi` CLI normalises; skill should pass topic name as-is.
- Plan `sources[]` list is empty — `implement` fails with a clear error before writing anything; `verify` flags as a gap.
- Plan frontmatter is syntactically invalid YAML — `implement` and `verify` both fail at parse time with a line-level error.
- Source `type` is an unrecognised value — `verify` emits a warning (not an error); forward-compatible.
- `ingest-plan.md` is partially populated (some entries from a prior run) — `implement` without `--force` warns; with `--force` replaces all entries.
- `--dry-run` on `implement` — prints the entries that would be written to `ingest-plan.md`; no writes.
- Network is unavailable — discovery is offline; agent reasons from domain knowledge, not live search results. URLs in the plan are suggestions, not fetched resources.

---

## Requirements

### Functional Requirements

**plan mode**

- **FR-001**: `hi-discovery plan` MUST produce `topics/<name>/process/plans/discovery-plan.md` with YAML frontmatter containing a `sources[]` list. Each entry MUST have: `name` (string), `type` (see FR-003), `rationale` (non-empty string), `search_terms[]` (non-empty list), and `evidence_level` (see FR-004). `url` is optional.
- **FR-002**: `plan` MUST create `process/research.md` and `process/conflicts.md` as stubs (create-unless-exists). If they already exist they MUST NOT be modified.
- **FR-003**: Valid `type` values: `guideline`, `systematic-review`, `terminology`, `value-set`, `measure-library`, `fhir-ig`, `cds-library`, `registry`, `other`. At least one entry with `type: terminology` MUST be present in any plan that passes `verify`.
- **FR-004**: Valid `evidence_level` values: `grade-a`, `grade-b`, `grade-c`, `grade-d`, `uspstf-a`, `uspstf-b`, `uspstf-c`, `uspstf-d`, `uspstf-i`, `expert-consensus`, `reference-standard`, `n/a`. Required on every source entry.
- **FR-005**: If `discovery-plan.md` already exists, `plan` MUST warn and stop unless `--force` is passed. With `--force`, existing file is overwritten.
- **FR-006**: `--dry-run` on `plan` MUST print the proposed plan to stdout without writing any file or appending any event.
- **FR-007**: Successful `plan` (non-dry-run) MUST append a `discovery_planned` event to `tracking.yaml`.

**implement mode**

- **FR-008**: `hi-discovery implement` MUST read `discovery-plan.md` and write one entry per source into the `sources[]` list in `process/plans/ingest-plan.md` YAML frontmatter. Each entry MUST carry over: `name`, `type`, `url` (if present), `rationale`, `evidence_level`.
- **FR-009**: If `discovery-plan.md` does not exist, `implement` MUST exit non-zero with: `discovery-plan.md not found — run hi-discovery plan first`.
- **FR-010**: If `sources[]` in the plan is empty, `implement` MUST exit non-zero before writing anything.
- **FR-011**: If `ingest-plan.md` already has entries, `implement` MUST warn and stop unless `--force` is passed.
- **FR-012**: `implement` MUST create `process/research.md` stub (create-unless-exists). MUST NOT modify existing file.
- **FR-013**: Successful `implement` MUST append a `discovery_implemented` event to `tracking.yaml`.
- **FR-014**: `--dry-run` on `implement` MUST print the entries that would be written; no file writes, no events.

**verify mode**

- **FR-015**: `hi-discovery verify` MUST be strictly read-only — no file writes, no `tracking.yaml` modifications.
- **FR-016**: `verify` MUST exit 0 only when ALL checks pass; exit 1 if any check fails.
- **FR-017**: `verify` MUST check: (a) `discovery-plan.md` exists and is parseable YAML; (b) `sources[]` is non-empty; (c) at least one entry has `type: terminology`; (d) every entry has a non-empty `rationale`; (e) every entry has a non-empty `search_terms[]`; (f) every `evidence_level` value is from the allowed set (FR-004); (g) every `type` value is from the allowed set (FR-003) — unknown types produce warnings, not failures.
- **FR-018**: `verify` MUST produce a per-check report with `✓` for pass and `✗` for fail, naming the source entry when the failure is entry-specific.

**General**

- **FR-019**: The skill MUST reside at `skills/.curated/hi-discovery/SKILL.md` and follow the three-level progressive disclosure template from `skills/_template/`.
- **FR-020**: All modes MUST accept a `TOPIC` positional argument identifying the topic name.
- **FR-021**: All modes MUST support `--dry-run`.
- **FR-022**: `plan` and `implement` MUST support `--force`.

### Non-Functional Requirements

- **NFR-001**: `verify` is strictly non-destructive (FR-015) — consistent with FR-022 in 002 spec.
- **NFR-002**: The skill requires no runtime dependencies beyond `hi` CLI, `yq`, and bash 3.2+.
- **NFR-003**: The SKILL.md MUST pass all `tests/skills/` checks (schema, security, framework contracts) with zero failures.
- **NFR-004**: Evidence levels and source types are forward-compatible — unknown values produce warnings, not hard failures in `verify`.

### Key Entities

- **Discovery Plan** (`discovery-plan.md`): YAML frontmatter + Markdown prose. The primary output of `plan` mode. Human-editable between `plan` and `implement`. `sources[]` list is the machine-readable core.
- **Ingest Plan** (`ingest-plan.md`): YAML frontmatter populated by `implement`. Consumed by `hi-ingest` (004). Not human-authored; generated from the discovery plan.
- **Source Entry**: One item in `sources[]`. Fields: `name`, `type`, `rationale`, `search_terms[]`, `evidence_level`, `url` (optional).
- **Research Stub** (`research.md`): Created-unless-exists by `plan` and `implement`. Template for the human to fill with evidence notes and citations.
- **Conflicts Stub** (`conflicts.md`): Created-unless-exists by `plan`. Template for the human to record guideline contradictions discovered during review.

---

## Success Criteria

- **SC-001**: A clinical informaticist with no prior knowledge of the topic can produce a discovery plan in a single agent conversation covering all required source categories.
- **SC-002**: `verify` catches a missing terminology source and exits 1 with an actionable error message identifying the gap.
- **SC-003**: `implement` produces an `ingest-plan.md` that `hi-ingest` (004) can consume without modification.
- **SC-004**: The SKILL.md passes all 31 `tests/skills/` parametrized checks (schema, security, contracts) with zero failures.
- **SC-005**: `--dry-run` on both `plan` and `implement` produces zero file writes while still surfacing any validation errors.

---

## Assumptions

- The agent has domain knowledge sufficient to identify relevant guidelines and terminology systems for common clinical topics without live internet search.
- URLs in source entries are suggestions for the human to verify; the skill does not fetch or validate them.
- `research.md` and `conflicts.md` are human-maintained after scaffolding; the skill writes stubs only.
- `ingest-plan.md` is the handoff artifact to `hi-ingest` (004); the schema of its `sources[]` entries must be compatible with what 004 expects.
- Evidence grading uses GRADE and USPSTF scales as the two dominant frameworks in clinical informatics; other frameworks (Oxford CEBM, SIGN) are accommodated via `expert-consensus` or `reference-standard`.
