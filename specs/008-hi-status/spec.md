# Feature Specification: hi-status Skill

**Feature Branch**: `008-hi-status`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — HI Framework](../002-hi-agent-skills/)

## Overview

`hi-status` is an agent skill providing lifecycle housekeeping for clinical topics. It gives teams actionable progress summaries, next-step recommendations, and drift detection without modifying any artifacts. It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `progress` | Plain-language lifecycle summary | `hi status <name>` |
| `next-steps` | Single recommended next action + exact command | `hi status <name>` |
| `check-changes` | Changed/missing sources report | `hi ingest verify` (+ checksum comparison) |

This skill also requires CLI extensions to `hi status` (`--progress`, `next-steps` subcommand, `check-changes` subcommand) as part of its implementation work.

## User Story

A team lead wants a quick summary of where a topic stands and what action should happen next. They invoke `hi-status progress`, which reads tracking.yaml and produces a plain-language summary. `hi-status next-steps` recommends the single most important next action with the exact command to run. `hi-status check-changes` detects any source files whose checksum has drifted since ingest.

**Why this priority**: Without actionable progress summaries, teams lose track of where topics stand across multi-week projects.

**Independent Test**: Invoke `hi-status progress` on the `diabetes-screening` example and verify that accurate artifact counts and meaningful next-step suggestions are produced.

## Acceptance Scenarios

1. **Given** any topic at any lifecycle stage, **When** `hi-status progress` is invoked, **Then** a summary is produced showing source/structured/computable artifact counts, validation status, and last event timestamp.
2. **Given** a topic with missing validation, **When** `hi-status next-steps` is invoked, **Then** the first recommended action is to run `hi validate` on the unvalidated artifact, with the exact command shown.
3. **Given** a topic where an ingested file has changed checksum, **When** `hi-status check-changes` is invoked, **Then** all changed files are listed with original vs. current checksum and the downstream structured/computable artifacts that depend on them.
4. **Given** an ingested file is deleted from disk, **When** `hi-status check-changes` is invoked, **Then** it is reported as missing (not just changed).
5. **Given** a source file has changed, **When** `hi-status check-changes` is invoked, **Then** it lists the structured artifacts derived from that source as potentially stale.

## Requirements

### Functional Requirements

**CLI Extensions (src/hi/commands/status.py)**

- **FR-001**: `hi status --progress <topic>` MUST output lifecycle stage (Discovery / Ingest / Extract / Formalize), source/structured/computable artifact counts, validation status summary, last event timestamp, and completeness percentage.
- **FR-002**: `hi status next-steps <topic>` MUST analyze tracking.yaml state machine and emit the single most important next action with the exact `hi` CLI command (e.g., no sources → suggest `hi ingest implement`).
- **FR-003**: `hi status check-changes <topic>` MUST re-checksum all sources from tracking.yaml, report changed/missing sources, and for each changed source list derived structured artifacts as potentially stale.

**SKILL.md Narratives**

- **FR-004**: `hi-status progress` mode MUST invoke `hi status --progress <name>` and present results with contextual guidance (e.g., what a low completeness percentage means, what to do next).
- **FR-005**: `hi-status next-steps` mode MUST invoke `hi status next-steps <name>` and present the recommendation with context.
- **FR-006**: `hi-status check-changes` mode MUST invoke `hi status check-changes <name>` and present results as a clear table of changed/missing sources with downstream impact.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/hi-status/SKILL.md` and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: All deterministic operations (checksum comparison, state analysis) MUST be delegated to `hi status` CLI commands.
- **NFR-003**: `hi-status` MUST be non-destructive in all modes — it never modifies any artifact or tracking entry.

## Notes

- This spec covers both the CLI extensions (`hi status` subcommands, FR-001 through FR-003) and the SKILL.md narratives (FR-004 through FR-006). The CLI extensions are deterministic and belong in `src/hi/commands/status.py`.
- Change detection is complementary to `hi-ingest verify` (004) — `check-changes` adds downstream impact analysis (which L2 artifacts are stale).
- The `next-steps` logic implements a simple state machine over tracking.yaml: no sources → ingest; sources but no structured → extract; structured but no computable → formalize; etc.
