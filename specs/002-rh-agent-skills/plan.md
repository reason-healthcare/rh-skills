# Implementation Plan: HI Agent Skills Suite

**Branch**: `002-rh-agent-skills` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-rh-agent-skills/spec.md`

## Summary

Build the deterministic infrastructure for the RH skills framework: the repository layout (`topics/<name>/structured/`, `computable/`, `process/`), the `rh-skills` CLI commands (`init`, `list`, `ingest`, `promote`, `validate`, `status`, `tasks`, `test`), and `tracking.yaml`. This spec covers framework infrastructure only. Each of the six HI agent skills (`rh-inf-discovery` through `rh-inf-status`) has its own specification (003–008) covering SKILL.md authoring. The guiding principle: all deterministic work in `rh-skills` CLI commands; all reasoning in SKILL.md agent prompts.

## Technical Context

**Language/Version**: Python 3.13.4
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, `uv 0.10.3`. Optional: `pdftotext` (poppler), `pandoc` for binary file extraction.
**Storage**: YAML (`tracking.yaml` at repo root, plan artifacts as `.md` files with YAML front matter in `topics/<name>/process/plans/` subdir)
**Testing**: pytest 8.0+ (via uv)
**Target Platform**: macOS + Linux
**Project Type**: Agent skills (SKILL.md prompt files) + CLI command extensions (Python modules in `src/rh_skills/commands/`)
**Performance Goals**: No LLM calls in plan mode — plan generation is pure LLM reasoning in SKILL.md context; implement mode calls existing `rh-skills promote` commands
**Constraints**: Python 3.13+ required; uv for package management; graceful degradation for optional tools; SKILL.md follows anthropic skills-developer template
**Scale/Scope**: 6 SKILL.md files + supporting CLI subcommands; skills apply to all clinical skills in the repo

## Constitution Check

*No project constitution defined — standard quality gates apply:*

- [X] No PHI in any artifact
- [X] All code Python 3.13+ (click + ruamel.yaml)
- [X] Deterministic work in `rh-skills` CLI commands; reasoning in SKILL.md prompts
- [X] New CLI commands follow existing exit code contract (0/1/2)
- [X] All new commands have pytest unit tests
- [X] No new mandatory dependencies (optional tools degrade gracefully)

## Project Structure

### Documentation (this feature)

```text
specs/002-rh-agent-skills/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (framework CLI tasks only)

specs/003-rh-inf-discovery/spec.md   # rh-inf-discovery skill spec
specs/004-rh-inf-ingest/spec.md      # rh-inf-ingest skill spec
specs/005-rh-inf-extract/spec.md     # rh-inf-extract skill spec
specs/006-rh-inf-formalize/spec.md   # rh-inf-formalize skill spec
specs/007-rh-inf-verify/spec.md      # rh-inf-verify skill spec
specs/008-rh-inf-status/spec.md      # rh-inf-status skill spec
```

### Source Code (repository root)

```text
skills/.curated/             # Framework-level agent skills
  rh-inf-discovery/
    SKILL.md                 # plan | implement modes
  rh-inf-ingest/
    SKILL.md                 # plan | implement | verify modes
  rh-inf-extract/
    SKILL.md                 # plan | implement | verify modes
  rh-inf-formalize/
    SKILL.md                 # plan | implement | verify modes
  rh-inf-verify/
    SKILL.md                 # standalone
  rh-inf-status/
    SKILL.md                 # progress | next-steps | check-changes modes

src/rh_skills/commands/
  ingest.py                  # rh-skills ingest subcommands (plan/implement/verify)

sources/                     # Raw source files (repo root, shared across topics)

topics/<name>/
  structured/                # Semi-structured L2 artifacts (prominent)
  computable/                # Computable L3 artifacts (prominent)
  process/
    plans/                   # Per-topic plan artifacts
      discovery-plan.md      # YAML front matter + prose
      ingest-plan.md
      extract-plan.md
      formalize-plan.md
      tasks.md               # rh-skills tasks tracking
    contracts/               # YAML validation contracts
    checklists/              # Clinical review checklists
    fixtures/                # LLM test fixtures
      results/               # Test run results
    research.md              # Evidence and citations
    notes.md                 # Human annotations (open questions, decisions, source conflicts)

tests/unit/
  test_ingest.py             # Unit tests for rh-skills ingest
tests/integration/
  test_lifecycle.py          # End-to-end lifecycle with stub LLM
```

**Structure Decision**: Single-project layout extending the existing `src/rh_skills/commands/` + `skills/` + `tests/` tree. Framework skills live under `skills/.curated/` (separate namespace from clinical skills, dot-prefix excluded from topic listings). New CLI functionality goes in `src/rh_skills/commands/ingest.py` as a click command group.


---

## Phase 0 Research Complete

See [research.md](research.md) for all decisions. No NEEDS CLARIFICATION items remain.

**Key decisions**:
1. SKILL.md modes dispatched via `$ARGUMENTS` first positional arg + narrative conditionals
2. Plan artifacts: YAML front matter + Markdown prose; extracted via `ruamel.yaml`
3. Skill location: `skills/.curated/<name>/SKILL.md`
4. SHA-256: Python `hashlib.sha256` — no external tools required
5. Optional tools: `pdftotext`, `pandoc` — degrade gracefully, `text_extracted: false`
6. Re-run: warn + stop; `--force` to override

## Phase 1 Design Complete

| Artifact | Status |
|----------|--------|
| [research.md](research.md) | ✅ |
| [data-model.md](data-model.md) | ✅ |
| [contracts/cli-schema.md](contracts/cli-schema.md) | ✅ |
| [quickstart.md](quickstart.md) | ✅ |

**Post-design Constitution Check**: All gates pass. No new mandatory deps. Bash 3.2+ portable. Deterministic work in CLI commands only.

Ready for `/speckit-tasks`.
