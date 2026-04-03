# Implementation Plan: HI Agent Skills Suite

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-hi-agent-skills/spec.md`

## Summary

Build 6 framework-level agent skills (`hi-discovery`, `hi-ingest`, `hi-extract`, `hi-formalize`, `hi-verify`, `hi-status`) that guide users through the full clinical knowledge lifecycle — from literature discovery through L1 ingest, L2 extraction, and L3 formalization — with a mandatory plan → implement → verify pattern and human review gates at each step. Skills live at `skills/_framework/<skill>/SKILL.md` and invoke `hi` CLI commands for all deterministic work. Plan artifacts use structured Markdown with YAML front matter for machine parseability and human readability.

## Technical Context

**Language/Version**: Bash 3.2+ (portable macOS/Linux)
**Primary Dependencies**: `yq` (Go binary), `jq`, `curl`, `bash 3.2+` — same as existing `hi` CLI stack. Optional: `pdftotext` (poppler), `pandoc` for binary file extraction.
**Storage**: YAML (`tracking.yaml` per skill, plan artifacts as `.md` files with YAML front matter in `plans/` subdir)
**Testing**: bats-core 1.13.0 (via npm) — same as existing test suite
**Target Platform**: macOS (bash 3.2 / BSD tools) + Linux (GNU tools) — no GNU-isms
**Project Type**: Agent skills (SKILL.md prompt files) + CLI command extensions (bash scripts in `bin/`)
**Performance Goals**: No LLM calls in plan mode — plan generation is pure LLM reasoning in SKILL.md context; implement mode calls existing `hi promote` commands
**Constraints**: BSD/Linux portable bash 3.2+; no new mandatory runtime deps; graceful degradation for optional tools; SKILL.md follows anthropic skills-developer template
**Scale/Scope**: 6 SKILL.md files + supporting CLI subcommands; skills apply to all clinical skills in the repo

## Constitution Check

*No project constitution defined — standard quality gates apply:*

- [X] No PHI in any artifact
- [X] All scripts portable bash 3.2+ (BSD + Linux)
- [X] Deterministic work in `hi` CLI commands; reasoning in SKILL.md prompts
- [X] New CLI commands follow existing exit code contract (0/1/2)
- [X] All new commands have bats unit tests
- [X] No new mandatory dependencies (optional tools degrade gracefully)

## Project Structure

### Documentation (this feature)

```text
specs/002-hi-agent-skills/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (speckit-tasks)
```

### Source Code (repository root)

```text
skills/_framework/           # New: framework-level agent skills
  hi-discovery/
    SKILL.md                 # plan | implement modes
  hi-ingest/
    SKILL.md                 # plan | implement | verify modes
  hi-extract/
    SKILL.md                 # plan | implement | verify modes
  hi-formalize/
    SKILL.md                 # plan | implement | verify modes
  hi-verify/
    SKILL.md                 # standalone
  hi-status/
    SKILL.md                 # progress | next-steps | check-changes modes

bin/
  hi-ingest                  # New: ingest command (plan/implement/verify subcommands)
  hi-ingest-lib.sh           # New: checksum + file registration helpers

skills/<name>/
  plans/                     # New: per-skill plan artifacts directory
    discovery-plan.md        # YAML front matter + prose
    ingest-plan.md
    extract-plan.md
    formalize-plan.md

tests/unit/
  ingest.bats                # New: unit tests for hi-ingest
tests/integration/
  agent-skills-lifecycle.bats # New: end-to-end lifecycle with stub LLM
```

**Structure Decision**: Single-project layout extending the existing `bin/` + `skills/` + `tests/` tree. Framework skills live under `skills/_framework/` (separate namespace from clinical skills). New CLI functionality goes in `bin/hi-ingest` following the existing dispatcher pattern.


---

## Phase 0 Research Complete

See [research.md](research.md) for all decisions. No NEEDS CLARIFICATION items remain.

**Key decisions**:
1. SKILL.md modes dispatched via `$ARGUMENTS` first positional arg + narrative conditionals
2. Plan artifacts: YAML front matter + Markdown prose; extracted via `awk` + `yq`
3. Skill location: `skills/_framework/<name>/SKILL.md`
4. SHA-256: runtime detect `sha256sum` vs `shasum -a 256` (bash 3.2 compatible)
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
