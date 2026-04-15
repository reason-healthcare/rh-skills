# Implementation Plan: Healthcare Informatics Skills Framework

**Branch**: `001-rh-skills-framework` | **Date**: 2026-04-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-rh-skills-framework/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build a CLI-driven repository framework for authoring healthcare informatics skills. Skills progress through three artifact levels — L1 (unstructured discovery), L2 (semi-structured YAML), and L3 (computable YAML with a custom schema designed for FHIR/FHIRPath/CQL compatibility). The artifact topology is many-to-many: one L1 may yield multiple L2 artifacts; multiple L2 artifacts may converge into one L3. Every workflow step (scaffolding, promotion, validation, testing) is handled by Bash CLI commands; domain reasoning is left to the human or agent. Skills follow the anthropic skills-developer (SKILL.md) convention and are locally testable via LLM invocation against author-defined fixtures.

## Technical Context

**Language/Version**: Bash / POSIX shell (sh-compatible; tested on bash 3.2+ for macOS compatibility)
**Primary Dependencies**: `yq` (YAML parsing + validation), `jq` (JSON parsing for LLM API responses), `curl` (LLM API calls), `git` (version tracking); all installable via `brew install yq jq` / `apt-get install yq jq curl`
**Storage**: File system — plain text/Markdown for L1, YAML for L2/L3 artifacts, YAML for tracking artifacts and schemas
**Testing**: bats-core (Bash Automated Testing System); installable via brew/npm; no language runtime required
**Target Platform**: POSIX-compliant systems (macOS 12+, Linux/Ubuntu 20.04+)
**Project Type**: CLI tool + skill repository framework
**Performance Goals**: All CLI commands (init, promote, validate, status, list) complete in <3s for typical skill sizes; LLM test latency depends on configured endpoint
**Constraints**: Zero runtime dependencies beyond POSIX shell + yq + jq + curl; fully offline except for `rh-skills test` (requires LLM endpoint); no sudo required for CLI installation
**Scale/Scope**: Dozens to hundreds of skills per repository; 2–10 artifacts per skill per level; single-repository multi-author workflow via git

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> **Note**: The project constitution (`/.specify/memory/constitution.md`) is an unfilled template — no project-specific principles have been ratified yet. Constitution check is deferred; no gates can be violated against an empty constitution. The constitution should be established (via `/speckit.constitution`) before implementation begins.

| Principle | Status | Notes |
|-----------|--------|-------|
| Constitution not yet defined | ⚠️ Deferred | No violations possible; recommend establishing constitution before tasks phase |

## Project Structure

### Documentation (this feature)

```text
specs/001-rh-skills-framework/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli-schema.md    # CLI command contracts
│   └── artifact-schemas.md  # L2/L3 YAML schema contracts
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
bin/
└── rh-skills              # Main CLI entry point (routes subcommands)

skills/                  # Healthcare informatics skill definitions (anthropic SKILL.md convention)
└── {skill-name}/
    ├── SKILL.md         # Skill prompt/instructions (anthropic skills-developer pattern)
    ├── l1/              # L1 raw/unstructured artifacts
    │   └── {name}.md
    ├── l2/              # L2 semi-structured YAML artifacts
    │   └── {name}.yaml
    ├── l3/              # L3 computable YAML artifacts
    │   └── {name}.yaml
    ├── fixtures/        # Test fixtures for rh-skills test
    │   └── {fixture-name}/
    │       ├── input.yaml
    │       └── expected.yaml
    └── tracking.yaml    # Tracking artifact (authoritative lifecycle state)

schemas/                 # YAML schemas for validation
├── l2-schema.yaml       # L2 artifact schema
├── l3-schema.yaml       # L3 artifact schema (FHIR-compatible custom schema)
└── tracking-schema.yaml # Tracking artifact schema

templates/               # Artifact templates for scaffolding
├── l1/
│   └── discovery.md
├── l2/
│   └── artifact.yaml
├── l3/
│   └── artifact.yaml
└── tracking.yaml

tests/                   # bats-core test suite
├── unit/
│   ├── rh-skills-init.bats
│   ├── rh-skills-promote.bats
│   ├── rh-skills-validate.bats
│   ├── rh-inf-status.bats
│   └── rh-skills-list.bats
└── integration/
    └── skill-lifecycle.bats
```

**Structure Decision**: Single-project CLI layout. The `bin/` directory contains the dispatcher and all subcommand scripts. The `skills/` directory is both the runtime location for HI skill definitions and the source-of-truth for anthropic-style SKILL.md prompts. `schemas/` and `templates/` are framework internals used by CLI commands. `tests/` uses bats-core for both unit (per-command) and integration (full lifecycle) coverage.

## Complexity Tracking

> No constitution violations to justify — constitution not yet defined.
