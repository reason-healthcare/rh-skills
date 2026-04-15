# Implementation Plan: `RH Skills Build System`

**Branch**: `009-skill-build-system` | **Date**: 2026-04-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-skill-build-system/spec.md`

## Summary

009 adds a developer-facing build system that turns the canonical curated RH
skill library into deterministic, platform-specific distribution bundles from a
single source of truth. The plan centers on a portable Bash build entrypoint,
declarative platform profiles, generated output under `dist/`, and automated CI
validation/installability checks for bundled platforms. Scenario-based model
evaluation and transcript ranking remain explicitly out of scope.

## Technical Context

**Language/Version**: Bash 3.2+ for build orchestration; Python 3.13+ for
fixture-driven validation and test helpers  
**Primary Dependencies**: `yq` v4 for YAML profile parsing, existing `pytest`
suite for validation coverage, GitHub Actions for CI installability checks  
**Storage**: File system only (`skills/.curated/`, `skills/_profiles/`, `dist/`,
`.github/workflows/`)  
**Testing**: `pytest`, fixture-based build/validation tests, GitHub Actions
smoke/installability checks for bundled targets  
**Target Platform**: macOS/Linux contributor environments plus GitHub-hosted
Linux CI  
**Project Type**: Developer tooling / build pipeline for skill bundle
distribution  
**Performance Goals**: Primary formal target is SC-001: a contributor can
produce bundled-platform output from a clean clone in under 10 minutes after
documented setup. Local build/validate flows should remain interactive; 009 does
not introduce an additional latency SLA beyond that threshold.  
**Constraints**: Single canonical skill source; deterministic/idempotent output;
build entrypoint must stay Bash 3.2-compatible; generated artifacts must remain
separate from curated sources; 009 includes CI installability validation but
excludes transcript-ranking and scenario-based model evaluation  
**Scale/Scope**: Initial support for GitHub Copilot, Claude Code, and Gemini CLI
across the current curated skill library, with profile-driven expansion to
additional targets later

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Gate | Status | Notes |
|------------------|--------|-------|
| Deterministic CLI Boundaries | ✅ Pass | The feature uses one command surface, `scripts/build-skills.sh`, for repeatable build, preview, and validation work. |
| Canonical Sources, Derived Outputs | ✅ Pass | `skills/.curated/` remains the only authored skill source; generated bundles are written under `dist/`. |
| Test-Backed Changes | ✅ Pass | The design includes pytest coverage for build behavior plus GitHub Actions installability checks. |
| Reviewable Spec Flow | ✅ Pass | `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, and `tasks.md` define a reviewable delivery trail. |
| Explicit Safety and Failure Modes | ✅ Pass | Placeholder content, missing profiles, conflicting outputs, and validation/installability failures are explicit blocking conditions. |
| Governance metadata | ⚠ Advisory | `constitution.md` still carries `TODO(RATIFICATION_DATE)`, but the operative principles are concrete and enforceable for planning. |

**Post-design re-check**: Pass. Phase 1 artifacts continue to align with the
constitution: one canonical source of truth, derived output kept separate,
explicit validation gates, and test-backed build behavior.

## Project Structure

### Documentation (this feature)

```text
specs/009-skill-build-system/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── build-command-contract.md
│   ├── ci-validation-contract.md
│   └── profile-schema-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
scripts/
└── build-skills.sh

skills/
├── .curated/
└── _profiles/
    ├── copilot.yaml
    ├── claude.yaml
    ├── gemini.yaml
    └── agents-md.yaml

dist/
└── <platform>/...

tests/
├── build/
│   ├── fixtures/
│   ├── conftest.py
│   └── test_build_skills.py
└── skills/

.github/
└── workflows/
    └── skill-build.yml

docs/
└── SKILL_DISTRIBUTION.md
```

**Structure Decision**: 009 uses one developer-facing build entrypoint under
`scripts/`, declarative platform profiles under `skills/_profiles/`, generated
artifacts under `dist/`, pytest coverage in `tests/build/`, and a CI workflow
under `.github/workflows/`. Contributor-facing workflow details live in
`docs/SKILL_DISTRIBUTION.md` and the aligned README/DEVELOPER surfaces.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dual-runtime plan (Bash build + Python tests) | Bash preserves contributor portability while Python/pytest reuses the repository's existing validation stack. | A pure Bash test harness would duplicate existing validation infrastructure and be harder to extend for CI assertions. |
