# Implementation Plan: `rh-inf-ingest` Skill

**Branch**: `004-rh-inf-ingest` | **Date**: 2026-04-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-rh-inf-ingest/spec.md`

## Summary

`rh-inf-ingest` is the operational ingest stage between discovery and extract. It consumes the approved `discovery-plan.yaml` from `rh-inf-discovery` and moves sources through four deterministic stages — download, normalize, classify, and annotate — while maintaining source provenance in `tracking.yaml`, writing normalized Markdown to `sources/normalized/`, and building a de-duped `topics/<topic>/process/concepts.yaml` vocabulary for downstream extraction. Unlike most workflow skills, its `plan` mode should remain a transient pre-flight summary rather than a durable plan artifact because `discovery-plan.yaml` is already the machine-readable work queue.

## Technical Context

**Language/Version**: Python 3.13+ (existing `rh-skills` CLI stack)  
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx >= 0.27`, `markdownify >= 0.13`, Python stdlib `html.parser`, external tools `pdftotext` and `pandoc` when available  
**Storage**: File system (`sources/`, `sources/normalized/`, `topics/<name>/process/`, `tracking.yaml`)  
**Testing**: `pytest`, `pytest-httpx`, `click.testing.CliRunner`  
**Target Platform**: macOS/Linux CLI environment  
**Project Type**: CLI extension + curated SKILL.md  
**Performance Goals**: Per-source registration and metadata operations complete in <2s locally; normalization time is dominated by external tools and file size; verify should scan typical topic inventories (<50 sources) in a few seconds  
**Constraints**: Optional external tools must degrade gracefully; verify must remain read-only; authenticated/manual sources must never hard-fail the pipeline solely due to access barriers; no PHI/PII in normalized or tracking artifacts  
**Scale/Scope**: Per-topic ingest runs over 1–50 sources, mixed open/manual/authenticated access, single-user CLI workflow with repeatable re-runs

## Constitution Check

*Constitution is an unfilled template, so project-specific gates cannot be enforced. Applying framework principles from `002-rh-agent-skills/spec.md` instead.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Deterministic work via `rh-skills` CLI | ✅ Pass | Download, normalize, classify, annotate, and verify remain CLI-owned |
| Skill resides at `skills/.curated/<name>/SKILL.md` | ✅ Pass | Target: `skills/.curated/rh-inf-ingest/SKILL.md` |
| `verify` is strictly read-only | ✅ Pass | Required by spec FR-014 |
| State-changing modes append tracking events | ✅ Pass | Download/normalize/classify/annotate all write named events |
| Workflow skills use reviewable plan artifacts | ⚠️ Exception | 004 intentionally uses a transient pre-flight summary because `discovery-plan.yaml` from 003 is already the durable machine-readable plan |
| No PHI in workflow artifacts | ✅ Pass | Normalized sources and concepts remain topic knowledge only |

No blocking gate violations. The plan-mode exception is intentional and justified below.

## Project Structure

### Documentation (this feature)

```text
specs/004-rh-inf-ingest/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── ingest-cli.md
│   └── concepts-schema.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/hi/commands/
└── ingest.py                      # plan / implement / normalize / classify / annotate / verify

skills/.curated/rh-inf-ingest/
├── SKILL.md                       # to be authored from this plan
├── reference.md                   # detailed source handling rules
└── examples/
    ├── plan.md                    # worked pre-flight summary example
    └── output.md                  # worked pipeline output example

tests/unit/
├── test_ingest.py                 # plan / implement / verify behavior
├── test_ingest_url.py             # URL download and auth redirect handling
├── test_ingest_normalize.py       # normalization paths and metadata capture
├── test_ingest_classify.py        # classification writes to tracking
└── test_ingest_annotate.py        # concepts.yaml + normalized frontmatter updates
```

**Structure Decision**: Single-project Python CLI. The feature extends the existing `src/hi/commands/ingest.py` command group and its unit tests while producing design artifacts under `specs/004-rh-inf-ingest/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No durable `ingest-plan.md` topic artifact in skill `plan` mode | `discovery-plan.yaml` is already the canonical work queue and adding another plan file would duplicate source inventory and access state | Forcing a second durable plan artifact would drift from 003 and create two competing ingest inputs |
