# Feature Specification: rh-inf-formalize Skill

**Feature Branch**: `006-rh-inf-formalize`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — RH Skills](../002-hi-agent-skills/), [005 — rh-inf-extract](../005-rh-inf-extract/)

## Overview

`rh-inf-formalize` is an agent skill that plans and executes the convergence of multiple structured (L2) artifacts into a single computable (L3) artifact, with a mandatory human review gate. It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | `topics/<name>/process/plans/formalize-plan.md` | `rh-skills status <name>` |
| `implement` | L3 artifact in `topics/<name>/computable/` | `rh-skills promote combine`, `rh-skills validate` |
| `verify` | FHIR-completeness report | `rh-skills validate <topic> <artifact>` |

The plan → implement gate is critical here: errors at the L3 level propagate to clinical decision support systems. Human review before implementation is mandatory.

## User Story

A team has produced several structured (L2) artifacts across screening criteria, risk factors, and diagnostic thresholds. They invoke `rh-inf-formalize plan`, which generates a convergence plan identifying which structured artifacts should be combined and what the resulting computable (L3) artifact's sections should contain. After review, `rh-inf-formalize implement` calls `rh-skills promote combine` and validates the result. `rh-inf-formalize verify` then confirms FHIR-compatible section completeness.

**Why this priority**: Formalization produces computable artifacts used in clinical decision support; errors here have downstream clinical impact, making the human review gate critical.

**Independent Test**: Run `rh-inf-formalize plan` on a topic with ≥2 structured artifacts and confirm a convergence plan is written before any computable files are created.

## Acceptance Scenarios

1. **Given** a topic with two or more validated structured artifacts, **When** `rh-inf-formalize plan` is invoked, **Then** a convergence plan is written to `topics/<name>/process/plans/formalize-plan.md` showing which structured artifacts will be combined and a draft outline of the computable artifact's sections.
2. **Given** a formalize plan has been reviewed, **When** `rh-inf-formalize implement` is invoked, **Then** `rh-skills promote combine` is called and the resulting computable artifact is validated with `rh-skills validate`.
3. **Given** the formalize step completes, **When** `rh-inf-formalize verify` is invoked, **Then** FHIR-compatible section completeness is confirmed (value sets have `codes[]`, measures have `numerator` and `denominator`).
4. **Given** no formalize plan exists, **When** `rh-inf-formalize implement` is invoked, **Then** the skill fails immediately with a clear error.
5. **Given** all structured artifacts have required-field validation errors, **When** `rh-inf-formalize plan` is invoked, **Then** the skill surfaces the validation errors before allowing the convergence plan to proceed.

## Requirements

### Functional Requirements

- **FR-001**: `rh-inf-formalize plan` MUST identify which structured (L2) artifacts will be combined and write `topics/<name>/process/plans/formalize-plan.md` with a draft outline of the computable (L3) artifact's sections for human review.
- **FR-002**: The formalize plan MUST use structured Markdown with a YAML front matter block. YAML front matter MUST include: `sources_structured[]`, `target_name`, and `sections[]` (each with `name`, `description`, `source_files[]`).
- **FR-003**: `rh-inf-formalize implement` MUST NOT proceed without a valid `topics/<name>/process/plans/formalize-plan.md`; it MUST call `rh-skills promote combine <topic> <sources…> <target>` with sources from the plan.
- **FR-004**: After `rh-skills promote combine`, `rh-inf-formalize implement` MUST run `rh-skills validate <topic> <target>` and surface any errors before writing the `computable_converged` event.
- **FR-005**: `rh-inf-formalize verify` MUST validate the L3 artifact and additionally check FHIR-compatible completeness: `measures[]` entries have `numerator` and `denominator`; `value_sets[]` entries have `codes[]`. Sub-field gaps MUST be reported.
- **FR-006**: If `formalize-plan.md` already exists, the skill MUST warn and stop unless `--force` is passed.
- **FR-007**: Successful `plan` mode MUST append `formalize_planned` to tracking.yaml. Successful `implement` MUST append `computable_converged`.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/rh-inf-formalize/SKILL.md` and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: All file writes and validation MUST be delegated to `rh-skills promote combine` and `rh-skills validate` CLI commands.

## Notes

- Multiple L2 structured artifacts combine into one L3 computable artifact (many-to-one convergence).
- The computable artifact's YAML structure must be FHIR-compatible; `rh-inf-formalize verify` enforces this.
- The L3 artifact in `topics/<name>/computable/` is the terminal output of the full lifecycle.
