# Feature Specification: rh-inf-verify Skill

**Feature Branch**: `007-rh-inf-verify`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — RH Skills](../002-hi-agent-skills/)

## Overview

`rh-inf-verify` is a standalone, non-modal agent skill that validates any named artifact (L2 or L3) at any point in the lifecycle. It can be invoked at any time without a plan — it is always safe to run.

| Invocation | CLI Commands Used |
|------------|-------------------|
| `rh-inf-verify <topic> <artifact-name>` | `rh-skills validate <topic> <artifact>` |

Unlike the workflow skills (rh-inf-extract, rh-inf-formalize), `rh-inf-verify` has no `plan` or `implement` modes. It is a point-in-time diagnostic tool — non-destructive and always informational.

## User Story

A clinical reviewer wants to confirm that a specific structured artifact meets the required schema before it is used as input to `rh-inf-formalize`. They invoke `rh-inf-verify diabetes-screening screening-criteria`, which runs `rh-skills validate` and presents the results as a clear pass/fail report with field-level detail on any errors.

**Why this is useful**: Validation failures deep in the pipeline (e.g., during formalize) are harder to debug. `rh-inf-verify` lets teams check artifacts proactively at any stage.

**Independent Test**: Run `rh-inf-verify` on a known-invalid fixture artifact and confirm that all required-field errors are reported with field-level detail.

## Acceptance Scenarios

1. **Given** a valid L2 or L3 artifact, **When** `rh-inf-verify <topic> <artifact>` is invoked, **Then** a pass report is produced confirming all required fields are present.
2. **Given** an artifact with missing required fields, **When** `rh-inf-verify` is invoked, **Then** all errors are reported with field names and expected types.
3. **Given** an artifact with optional fields missing, **When** `rh-inf-verify` is invoked, **Then** warnings are shown but the command exits zero (non-blocking).
4. **Given** a non-existent artifact name, **When** `rh-inf-verify` is invoked, **Then** the skill fails with a clear error indicating the artifact was not found.
5. **When** `rh-inf-verify` is run, **Then** no files are created, modified, or deleted — it is always non-destructive.

## Requirements

### Functional Requirements

- **FR-001**: `rh-inf-verify` MUST be invokable at any point to validate any named artifact (L2 or L3) by calling `rh-skills validate <topic> <artifact>`.
- **FR-002**: `rh-inf-verify` MUST present required-field errors (blocking) distinctly from optional-field warnings (advisory) in the output.
- **FR-003**: `rh-inf-verify` MUST exit zero if only warnings are present (no required-field errors).
- **FR-004**: `rh-inf-verify` MUST be strictly non-destructive — it MUST NOT modify any artifact, tracking entry, or plan file.
- **FR-005**: `rh-inf-verify` MUST fail with a clear error if the named artifact does not exist.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/rh-inf-verify/SKILL.md` and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: All validation logic MUST be delegated to `rh-skills validate` CLI commands.

## Notes

- `rh-inf-verify` is non-modal — there is no `plan`/`implement` pattern. Arguments are `<topic>` and `<artifact-name>`.
- This skill is the companion to the per-lifecycle `verify` modes in rh-inf-extract (005) and rh-inf-formalize (006). It provides on-demand validation outside the workflow sequence.
- No events are appended to tracking.yaml (non-destructive by design).
