# Implementation Plan: L2 Artifact Catalog Expansion

**Branch**: `010-l2-artifact-catalog` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-l2-artifact-catalog/spec.md`

## Summary

Expand the L2 Hybrid Artifact Catalog from 8 to 12 types by adding clinical-frame,
decision-table, assessment, and policy. Restructure the `structured/` directory from
flat files to per-artifact subdirectories (`structured/<name>/<name>.yaml`) with a
`views/` folder for generated representations. Add a new `rh-skills render` CLI
command that deterministically generates type-specific views (mermaid, markdown tables,
CSV, completeness reports) from L2 YAML control files. Update all path references
across promote, validate, tracking, extract SKILL/reference, eval fixtures, and tests.

## Technical Context

**Language/Version**: Python 3.13+ (click 8.3, ruamel.yaml 0.19)  
**Primary Dependencies**: click, ruamel.yaml, pathlib (stdlib)  
**Storage**: YAML files on filesystem under `topics/<topic>/structured/`  
**Testing**: pytest (493 passing, 11 skipped — baseline)  
**Target Platform**: macOS/Linux CLI  
**Project Type**: CLI tool (rh-skills)  
**Performance Goals**: N/A (local file processing, deterministic)  
**Constraints**: No LLM invocation for render; pure file transformation  
**Scale/Scope**: 12 artifact types × ~5 view templates; ~30 path references to update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Deterministic CLI Boundary**: ✅ PASS
  - `rh-skills render` is the new canonical CLI command owning view writes.
  - `rh-skills promote derive` continues to own L2 artifact writes (path change only).
  - `rh-skills validate` continues to own schema validation.
  - No durable writes happen outside CLI commands.

- **II. Reviewable Lifecycle Artifacts**: ✅ PASS
  - L2 artifacts remain durable, human-reviewable files.
  - `clinical-frame` is scoping metadata (no L3 target) — this is intentional and
    does not bypass the lifecycle; it simply has no `combine` participation.
  - The existing plan→derive→approve→formalize flow is unchanged; new types slot
    into the same lifecycle.

- **III. Spec-Linked Validation**: ✅ PASS
  - Spec has 6 independently testable user stories, 18 functional requirements,
    6 measurable success criteria.
  - Validation tasks are included for changed CLI contracts (derive path, validate
    path, render command, tracking schema references).

- **IV. Safety and Evidence Integrity**: ✅ PASS
  - No changes to injection boundaries or evidence traceability.
  - New artifact types (clinical-frame, decision-table, assessment, policy) carry
    the same `evidence_traceability` and `conflicts` structures as existing types.
  - Decision-table completeness checks add a new safety signal (missing rules).

- **V. Minimal Surface Area**: ✅ PASS — with justification for new command
  - `rh-skills render` is a new command (not extending existing). Justification:
    render is a pure deterministic transformation with no lifecycle state change.
    It does not fit under `promote` (which owns LLM-driven state transitions) or
    `validate` (which owns schema checks). A dedicated command keeps the boundary
    clean: render reads YAML → writes views; no tracking events appended.
  - The 4 new artifact types extend `EXTRACT_ARTIFACT_PROFILES` (existing tuple);
    no new data structures or parallel schemas are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/010-l2-artifact-catalog/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/rh_skills/
├── cli.py                           # Add render command registration
├── commands/
│   ├── promote.py                   # Update EXTRACT_ARTIFACT_PROFILES (+4 types)
│   │                                # Update _formalize_required_sections (+3 mappings)
│   │                                # Update derive path: structured/<name>/<name>.yaml
│   │                                # Update tracking entry file path
│   ├── validate.py                  # Update artifact path resolution
│   └── render.py                    # NEW — render command module
├── schemas/
│   ├── l2-schema.yaml               # No changes (metadata-only validation)
│   └── tracking-schema.yaml         # Update structured file path comment

skills/.curated/rh-inf-extract/
├── SKILL.md                         # Update catalog list (step 4)
└── reference.md                     # Add 4 types to catalog, document section shapes

tests/unit/
├── test_promote.py                  # Update path expectations, add new type tests
├── test_validate.py                 # Update path expectations
└── test_render.py                   # NEW — render command tests
```

**Structure Decision**: Single-project layout. New `render.py` command module follows
the existing pattern (one module per CLI command group). No new directories beyond the
new command file and test file.

## Complexity Tracking

> No constitution violations. The new `render` command is justified above (V. Minimal
> Surface Area). No entries needed.
