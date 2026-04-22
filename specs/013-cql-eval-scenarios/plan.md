# Implementation Plan: CQL Eval Scenarios — Full Measure Pipeline

**Branch**: `013-cql-eval-scenarios` | **Date**: 2026-04-22 | **Spec**: `specs/013-cql-eval-scenarios/spec.md`
**Input**: Feature specification from `/specs/013-cql-eval-scenarios/spec.md`

## Summary

Add four eval scenario YAML files covering the complete clinical quality measure
authoring pipeline (ingest → extract → formalize × 2) for the `lipid-management`
topic (ACC/AHA cholesterol guideline). The scenarios are data-only additions — no
new CLI commands or Python code. The formalize scenarios specifically test CQL
Library authoring: `context Patient`, population define-statement chaining,
date-interval arithmetic, FHIR Library wrapping, and Measure + PlanDefinition
cross-linking.

## Technical Context

**Language/Version**: YAML (data files only — no Python code changes)
**Primary Dependencies**: N/A (no new dependencies)
**Storage**: Files — four new YAML scenario files in `eval/scenarios/`
**Testing**: YAML parse validation (`python -c 'import yaml; yaml.safe_load(open(...))'`); eval harness schema check via `scripts/eval-skill.sh --dry-run`
**Target Platform**: N/A
**Project Type**: Data/content addition (eval scenario fixtures)
**Performance Goals**: N/A
**Constraints**: Scenario YAML must parse without errors; all `content:` fields with CQL must use YAML literal block scalars (`|`)
**Scale/Scope**: 4 new YAML files (~300–500 lines each)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Deterministic CLI Boundary**: ✅ N/A — these are read-only data files (eval scenario fixtures). No state-changing operations. The scenarios describe CLI commands that agents execute; they do not implement new CLI paths.
- **II. Reviewable Lifecycle Artifacts**: ✅ N/A — eval scenarios are not lifecycle artifacts. They are inputs to the eval harness, not outputs of a clinical workflow.
- **III. Spec-Linked Validation**: ✅ Each scenario file has `expected_outputs` with explicit `contains:` and `event:` checks traceable to FR-001–FR-010. The tasks file will include a YAML-parse validation task per scenario.
- **IV. Safety and Evidence Integrity**: ✅ Workspace fixtures use representative clinical content (ACC/AHA LDL thresholds, VSAC URLs as realistic placeholders). No real patient data; no source content used as instructions. Clinical facts are embedded in `content:` blocks clearly marked as fixture data.
- **V. Minimal Surface Area**: ✅ Pure data additions. No new commands, schemas, abstractions, or alternate write paths. Scenarios auto-discovered by existing eval harness.

No violations; Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/013-cql-eval-scenarios/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (speckit.tasks)
```

### New Files (repository root)

```text
eval/scenarios/
├── rh-inf-ingest/
│   └── quality-measure-source.yaml        # NEW — US-1
├── rh-inf-extract/
│   └── measure-logic-extraction.yaml      # NEW — US-2
└── rh-inf-formalize/
    ├── cql-library-authoring.yaml         # NEW — US-3
    └── measure-bundle-complete.yaml       # NEW — US-4
```

No source code changes. No schema changes.

## Complexity Tracking

> No violations — not applicable for this data-only feature.
