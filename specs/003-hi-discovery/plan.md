# Implementation Plan: `hi-discovery` Skill

**Branch**: `003-hi-discovery` | **Date**: 2026-04-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-hi-discovery/spec.md`

## Summary

`hi-discovery` is an interactive research assistant SKILL.md that guides clinical informaticists through evidence-based source discovery for a new topic. It operates as a single conversational session (pure planning — no downloads): the agent searches PubMed, PubMed Central, and ClinicalTrials.gov via `hi search` CLI commands; maintains a living `discovery-plan.yaml` (pure YAML, machine-readable source of truth) and `discovery-readout.md` (generated narrative) written to disk on user approval; and produces Research Expansion Suggestions after each research pass. A `verify` mode validates saved plans for structural completeness. `hi-ingest` (004) handles all source acquisition by reading `discovery-plan.yaml` directly. Two new `hi` CLI command groups are required: `hi search` (PubMed/PMC/ClinicalTrials API wrappers) and an extension to `hi validate` for `--plan <path>.yaml`.

## Technical Context

**Language/Version**: Python 3.13+ (existing `hi` CLI stack)
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx` (async-capable HTTP for URL download + PubMed API calls), `requests` (fallback for simple GET), `lxml` or `xmltodict` (PubMed XML parsing)
**Storage**: File system (`sources/`, `topics/<name>/process/plans/`, `tracking.yaml`, `RESEARCH.md`)
**Testing**: `pytest` + `pytest-httpx` (for mocking PubMed/ClinicalTrials HTTP calls) — existing suite
**Target Platform**: macOS/Linux CLI (same as existing `hi`)
**Project Type**: CLI extension + SKILL.md (agent skill)
**Performance Goals**: `hi search pubmed` returns structured results in ≤5 seconds (SC-004); downloads via `hi ingest implement --url` subject to network speed
**Constraints**: No API key required for PubMed (≤3 req/s without key; ≤10 req/s with `NCBI_API_KEY`); ClinicalTrials.gov v2 is free/public; no auth for PMC open-access
**Scale/Scope**: Per-topic usage; plans hold 5–25 sources; single-user CLI session

## Constitution Check

*Constitution is a blank template — no project-specific principles defined. Applying framework principles from `002-hi-agent-skills/spec.md` instead.*

| Principle | Status | Notes |
|-----------|--------|-------|
| All deterministic work via `hi` CLI | ✅ Pass | `hi search`, `hi ingest implement --url` handle all I/O; skill provides reasoning only |
| Skill resides at `skills/.curated/<name>/SKILL.md` | ✅ Pass | Target: `skills/.curated/hi-discovery/SKILL.md` |
| `verify` is strictly read-only | ✅ Pass | FR-018 explicit; no file writes or tracking.yaml modifications |
| All plan/implement modes append event to `tracking.yaml` | ✅ Pass | FR-017: `discovery_planned` event on session save |
| Skill passes `tests/skills/` suite | ✅ Pass | SC-005; NFR-003 |
| No PHI in skill output or tracking artifacts | ✅ Pass | Discovery deals with literature, not patient data |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-hi-discovery/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── hi-search.md     # hi search command contract
│   └── discovery-plan-schema.md  # discovery-plan.yaml YAML schema
└── tasks.md             # Phase 2 output (speckit-tasks)
```

### Source Code (repository root)

```text
src/hi/commands/
├── search.py            # NEW: hi search pubmed/pmc/clinicaltrials
├── ingest.py            # EXTEND: add --url flag to implement subcommand
└── init.py              # EXTEND: create RESEARCH.md + process/research.md stubs

skills/.curated/hi-discovery/
├── SKILL.md             # NEW: interactive research assistant skill
├── reference.md         # EXISTING: full source taxonomy + access guidance
└── examples/
    ├── plan.yaml        # NEW: worked example discovery-plan.yaml
    └── readout.md       # NEW: worked example discovery-readout.md

tests/
├── unit/
│   ├── test_search_pubmed.py        # NEW: PubMed API wrapper tests (httpx mock)
│   ├── test_search_clinicaltrials.py # NEW: ClinicalTrials API tests
│   ├── test_ingest_url.py           # NEW: URL download + registration tests
│   └── test_init_research.py        # NEW: RESEARCH.md + research.md creation
└── skills/
    └── (existing parametrized suite — hi-discovery skill activates automatically)
```

