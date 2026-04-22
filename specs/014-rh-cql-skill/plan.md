# Implementation Plan: rh-cql — First-Class CQL Authoring Skill

**Branch**: `014-rh-cql-skill` | **Date**: 2026-04-22 | **Spec**: `specs/014-rh-cql-skill/spec.md`
**Input**: Feature specification from `/specs/014-rh-cql-skill/spec.md`

## Summary

Promote CQL authoring from an implicit stub in `rh-inf-formalize` to a first-class
curated skill (`rh-cql`) with four operating modes: `author`, `review`, `debug`,
and `test-plan`. Adds a new `rh-skills cql` CLI command group (validate / translate
/ test) that wraps the CQFramework translator and AHRQ CQL Testing Framework.
Updates `rh-inf-formalize` to delegate `.cql` content generation to `rh-cql` rather
than producing stubs inline.

## Technical Context

**Language/Version**: Python 3.13 + click + ruamel.yaml (existing stack)
**Primary Dependencies**: existing (`httpx`, `ruamel.yaml`, `click`); external runtime: CQFramework `cql-to-elm` JAR (optional, path-configured); AHRQ CQL Testing Framework (optional, for `cql test`)
**Storage**: Files — `.cql` in `topics/<topic>/computable/`; ELM JSON in same dir; review reports in `topics/<topic>/process/reviews/`; test plans in `topics/<topic>/process/test-plans/`; test fixtures in `tests/cql/<library-name>/`
**Testing**: pytest (existing); new unit tests for `rh-skills cql` commands; new skill audit tests for `rh-cql`
**Target Platform**: macOS / Linux (same as project)
**Project Type**: CLI + curated skill (content + code)
**Performance Goals**: `rh-skills cql validate` returns result within 30s for ≤500-line library (SC-004)
**Constraints**: CQL translator is optional external binary — all three `cql` sub-commands must degrade gracefully when absent; no new Python dependencies unless unavoidable
**Scale/Scope**: 1 new curated skill, 1 new CLI command group (3 sub-commands), ~200 lines Python, ~600 lines SKILL.md, formalize.py refactor (~30 lines)

## Constitution Check

- **I. Deterministic CLI Boundary**: ✅ All CQL file writes go through `rh-skills formalize` (FHIR Library wrapper) and the new `rh-skills cql validate/translate/test` commands. `rh-cql` SKILL.md is agent instruction only — it specifies which CLI commands own each write. The CQL `.cql` file itself is written by the agent via `RH_STUB_RESPONSE` / `rh-skills formalize` (same pattern as other L3 artifacts).
- **II. Reviewable Lifecycle Artifacts**: ✅ Review reports and test plans are durable files in `topics/<topic>/process/`. The skill operates within the existing L3-computable stage; no new lifecycle state is introduced.
- **III. Spec-Linked Validation**: ✅ 33 FRs are concrete and independently testable. Skill audit tests (`tests/skills/test_skill_audit.py`) will be extended to cover `rh-cql`. CLI contract tests will cover the three new sub-commands.
- **IV. Safety and Evidence Integrity**: ✅ CQL is authored from L2 structured artifacts (not raw source prose). Terminology resolution happens upstream in `rh-inf-extract`. No clinical source content flows into CQL generation as instructions.
- **V. Minimal Surface Area**: ✅ New `cql` command group justified by translator integration (external binary, not existing primitives). SKILL.md content files are additive. `formalize.py` CQL stub generation (~8 lines) is removed and replaced with a documented delegation boundary.

No violations; Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/014-rh-cql-skill/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (speckit.tasks)
```

### New Files (repository root)

```text
skills/.curated/rh-cql/
├── SKILL.md                          # NEW — four-mode agent instructions
├── reference.md                      # NEW — standards corpus with URLs
└── examples/
    ├── author-example/
    │   ├── plan.md                   # NEW — author mode worked example input
    │   └── output.md                 # NEW — author mode worked example output
    └── review-example/
        ├── plan.md                   # NEW — review mode worked example input
        └── output.md                 # NEW — review mode worked example output

src/rh_skills/commands/cql.py         # NEW — `rh-skills cql` command group
tests/unit/test_cql.py                # NEW — unit tests for cql commands
tests/skills/test_skill_audit.py      # MODIFIED — extend for rh-cql contracts
```

### Modified Files

```text
src/rh_skills/cli.py (or equivalent entry point)
  — add `cql` command group registration

src/rh_skills/commands/formalize.py
  — remove inline CQL stub generation (lines ~357–376)
  — add documented delegation comment referencing rh-cql

skills/.curated/rh-inf-formalize/SKILL.md
  — document boundary: CQL content → rh-cql; FHIR Library wrapper → rh-skills formalize
```

## Complexity Tracking

> No violations — not applicable.

---


## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Confirm the deterministic write boundary is assigned to concrete `rh-skills`
  CLI commands.
- Confirm any state-changing workflow uses an explicit
  `plan -> implement -> verify` lifecycle or justify why it does not.
- Confirm validation coverage exists for changed CLI contracts, schemas, events,
  or safety-sensitive behavior.
- Record any principle violation in Complexity Tracking with explicit
  justification.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
