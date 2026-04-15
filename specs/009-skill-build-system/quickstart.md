# Quickstart: RH Skills Build System

## Prerequisites

```bash
uv sync
yq --version
```

Canonical RH skills must already exist in the curated skill library.

## Build one platform

```bash
scripts/build-skills.sh --platform copilot
```

Expected outcome:

- generates platform-specific bundles from the canonical curated skills
- writes derived output under `dist/`
- reports per-skill success, warning, or failure

## Build all bundled platforms

```bash
scripts/build-skills.sh --all
```

Expected outcome:

- processes GitHub Copilot, Claude Code, and Gemini CLI in one workflow
- reports a contributor-facing build summary across all requested platforms

## Preview without writing files

```bash
scripts/build-skills.sh --all --dry-run
```

Expected outcome:

- writes no files
- previews what would be generated
- still reports blocking errors such as unresolved placeholders or invalid profiles

## Validate generated bundles

```bash
scripts/build-skills.sh --all --validate
```

Expected outcome:

- checks generated bundles against platform validation rules
- reports per-platform, per-skill pass/fail details

## CI readiness

Repository CI should run the build workflow, validation, and installability
smoke checks before contributors treat generated bundles as ready to distribute.

009 does not include transcript-ranking or scenario-based model evaluation; it
establishes the build-and-installability baseline that later evaluation work can
extend.
