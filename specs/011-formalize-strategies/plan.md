# Implementation Plan: L2→L3 Formalization Strategies

**Branch**: `011-formalize-strategies` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-formalize-strategies/spec.md`

## Summary

Implement type-specific L2→L3 formalization strategies that convert 7 L2 structured artifact types into FHIR R4 JSON resources. This replaces the current generic `promote combine` command (which produces monolithic YAML) with two new commands: `rh-skills formalize <topic> <artifact>` (generates individual FHIR JSON + CQL per artifact) and `rh-skills package <topic>` (bundles all computable resources into a FHIR NPM package). Each of the 7 L2 types (evidence-summary, decision-table, care-pathway, terminology, measure, assessment, policy) has a distinct conversion strategy documented in `docs/FORMALIZE_STRATEGIES.md` that maps L2 sections to specific FHIR resource structures.

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Click 8.0+, ruamel.yaml 0.18+, json (stdlib, for FHIR JSON output)
**Storage**: File-based — FHIR JSON to `topics/<topic>/computable/`, FHIR packages to `topics/<topic>/package/`
**Testing**: pytest (existing test infrastructure)
**Target Platform**: macOS / Linux CLI (Bash 3.2+ compatible)
**Project Type**: CLI tool extension (extends existing `rh-skills` command set)
**Performance Goals**: N/A (batch CLI, not latency-sensitive)
**Constraints**: FHIR R4 (4.0.1), CQL 1.5, US Core / QI-Core / CRMI conformance
**Scale/Scope**: 7 L2 artifact types; typical topic has 1–5 artifacts; each artifact produces 1–5 FHIR JSON resources

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Deterministic CLI Boundary** | ✅ Pass | Two new CLI commands own all writes: `rh-skills formalize` writes FHIR JSON + CQL to `computable/` and appends `computable_converged`; `rh-skills package` writes `package/` directory and appends `package_created`. SKILL.md describes orchestration only. |
| **II. Reviewable Lifecycle** | ✅ Pass | Formalize follows plan→implement→verify. `formalize-plan.md` is the reviewable plan artifact. Implement requires approval gate. Verify is non-destructive and rerunnable. |
| **III. Spec-Linked Validation** | ✅ Pass | Spec defines 12 FRs, 5 SCs, 7 edge cases, 4 clarifications. Eval scenarios required for all 7 L2 types plus convergence (FR-008). Verify covers type-specific completeness (FR-005). |
| **IV. Safety & Evidence Integrity** | ✅ Pass | L2 content treated as untrusted input. `converged_from` preserves provenance. MCP-UNREACHABLE placeholders make gaps explicit. Verify catches unresolved codes. |
| **V. Minimal Surface Area** | ⚠️ Justified | Two new commands replace one (`promote combine`). See Complexity Tracking. |

## Project Structure

### Documentation (this feature)

```text
specs/011-formalize-strategies/
├── plan.md              # This file
├── research.md          # Phase 0: architecture decisions
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: quick reference
├── contracts/           # Phase 1: CLI command contracts
│   ├── formalize-command.md
│   └── package-command.md
└── tasks.md             # Phase 2 (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/rh_skills/commands/
├── formalize.py         # NEW: rh-skills formalize command
├── package.py           # NEW: rh-skills package command
├── promote.py           # MODIFY: deprecate combine, update helpers
└── validate.py          # MODIFY: add type-specific L3 verify rules

src/rh_skills/
├── common.py            # EXISTING: append_topic_event, tracking helpers
├── fhir/                # NEW: FHIR output validation + normalization
│   ├── __init__.py
│   ├── normalize.py     # Post-LLM normalization (ids, urls, dates, required fields)
│   ├── validate.py      # Structural validation per resource type
│   └── packaging.py     # FHIR package (package.json, IG) bundler

skills/.curated/rh-inf-formalize/
├── SKILL.md             # MODIFY: update for new commands + type-specific strategies
└── reference.md         # MODIFY: replace YAML schema with FHIR JSON + strategy rules

eval/scenarios/rh-inf-formalize/
├── converge-l2.yaml             # EXISTING: updated for FHIR JSON output
├── evidence-summary.yaml        # NEW
├── decision-table.yaml          # NEW
├── care-pathway.yaml            # NEW
├── terminology.yaml             # NEW
├── measure.yaml                 # NEW
├── assessment.yaml              # NEW
├── policy.yaml                  # NEW
├── unknown-type-fallback.yaml   # NEW: FR-009 generic fallback
├── multi-type-convergence.yaml  # NEW: US4 multi-type
└── convergence-overlap.yaml     # NEW: US4 overlap detection

docs/
└── FORMALIZE_STRATEGIES.md  # EXISTING: authoritative reference (already complete)
```

**Structure Decision**: Hybrid LLM-driven architecture. The LLM generates FHIR JSON content guided by type-specific strategy instructions in SKILL.md and reference.md. Python code in `src/rh_skills/fhir/` validates and normalizes the LLM output (ensures required fields, correct resourceType, proper id/url format). The CLI commands (`formalize`, `package`) in `promote.py` and `package.py` handle the write boundary and tracking. This follows the existing `promote combine` pattern while adding structural guarantees.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two commands replace one (`promote combine` → `formalize` + `package`) | Formalization (individual resource generation) and packaging (FHIR NPM bundling) are distinct concerns with different inputs, outputs, and tracking events | A single command would conflate "generate resources" with "bundle package," making partial re-generation impossible and violating the principle that each command has a clear write boundary |
