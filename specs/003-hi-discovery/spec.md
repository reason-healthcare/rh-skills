# Feature Specification: hi-discovery Skill

**Feature Branch**: `003-hi-discovery`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — HI Framework](../002-hi-agent-skills/)

## Overview

`hi-discovery` guides a clinical informaticist through structured source discovery for a new topic. It operates in two modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | `topics/<name>/process/plans/discovery-plan.md` | `hi status <name>` |
| `implement` | Entries in `topics/<name>/process/plans/ingest-plan.md` | *(pure reasoning over plan file)* |

No files are downloaded or registered during discovery — the skill's sole output is a human-reviewable plan artifact. This makes it safe to run at any point.

## User Story

A clinical informaticist starting a new topic for "sepsis early detection" needs help identifying what sources to look for. They invoke `hi-discovery plan`, which generates a research plan listing guidelines, terminology systems, and peer-reviewed sources relevant to the domain. After reviewing and optionally editing the plan, they invoke `hi-discovery implement`, which converts the plan into tracked ingest tasks — without downloading or registering anything yet.

**Why this priority**: Discovery is the entry point for every new topic. Without a structured research plan, teams skip important sources and produce incomplete artifacts.

**Independent Test**: Run discovery-plan on a new empty topic and verify that a structured source list is produced as a reviewable artifact.

## Acceptance Scenarios

1. **Given** a new initialized topic with no sources, **When** `hi-discovery plan` is invoked, **Then** a discovery plan is written to `topics/<name>/process/plans/discovery-plan.md` with suggested source types and specific examples for the topic's domain.
2. **Given** a reviewed discovery plan, **When** `hi-discovery implement` is invoked, **Then** each source in the plan becomes an entry in `topics/<name>/process/plans/ingest-plan.md` — no files are registered yet.
3. **Given** a discovery plan exists, **When** `hi-discovery plan` is re-invoked, **Then** the skill warns and stops unless `--force` is provided.
4. **Given** no discovery plan exists, **When** `hi-discovery implement` is invoked, **Then** the skill fails with a clear error.

## Requirements

### Functional Requirements

- **FR-001**: `hi-discovery plan` MUST produce `topics/<name>/process/plans/discovery-plan.md` with a structured list of suggested sources relevant to the topic's domain. No other files may be created or modified.
- **FR-002**: The discovery plan MUST use structured Markdown with a YAML front matter block. YAML front matter MUST include a `sources[]` list where each entry has: `name`, `type`, `rationale`, `search_terms[]`, and optional `url_or_path`.
- **FR-003**: `hi-discovery implement` MUST read `topics/<name>/process/plans/discovery-plan.md` and add each source as an entry in `topics/<name>/process/plans/ingest-plan.md` YAML front matter. It MUST fail with a clear error if no discovery plan exists.
- **FR-004**: If `discovery-plan.md` already exists, the skill MUST warn and stop unless `--force` is passed.
- **FR-005**: Successful `plan` mode MUST append a `discovery_planned` event to `tracking.yaml`. Successful `implement` mode MUST append `discovery_implemented`.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/hi-discovery/SKILL.md` and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: Skill requires no runtime dependencies beyond the standard `hi` framework stack.

## Notes

- `implement` populates `ingest-plan.md` entries but does NOT register files in tracking.yaml — that is `hi-ingest`'s responsibility (004).
- Sources can include any format: guidelines PDFs, clinical databases, terminology systems, web articles.
- The plan file is intentionally human-editable between `plan` and `implement` — clinical review is expected.
