# Implementation Plan: `rh-inf-extract` Skill

**Branch**: `005-rh-inf-extract` | **Date**: 2026-04-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-rh-inf-extract/spec.md`

## Summary

`rh-inf-extract` is the reviewer-gated L2 derivation stage between ingest and formalize. It analyzes normalized sources plus `concepts.yaml`, writes a durable `extract-plan.md` review packet in `topics/<topic>/process/plans/`, and only derives approved L2 artifacts after explicit reviewer sign-off. The implementation should reuse the deterministic `rh-skills promote derive` and `rh-skills validate` primitives, but extend them to support multi-source derivation, claim-level evidence traceability, explicit conflict recording, and richer structured artifact schemas than the current generic `promote derive` stub.

## Technical Context

**Language/Version**: Python 3.13+ (existing `rh-skills` CLI stack)  
**Primary Dependencies**: `click >= 8.0`, `ruamel.yaml >= 0.18`, existing `promote`/`validate` command stack, LLM provider abstraction in `src/hi/commands/promote.py`  
**Storage**: File system (`topics/<topic>/process/plans/`, `topics/<topic>/structured/`, `topics/<topic>/process/concepts.yaml`, `sources/normalized/`, `tracking.yaml`)  
**Testing**: `pytest`, `click.testing.CliRunner`, curated skill audit/security tests under `tests/skills/`  
**Target Platform**: macOS/Linux CLI environment  
**Project Type**: CLI extension + curated SKILL.md  
**Performance Goals**: Plan generation should stay interactive for typical topics (5–25 ingested sources); per-artifact derive/validate loops should complete in seconds in stub/test mode and scale linearly with artifact count  
**Constraints**: Implement mode must not write any L2 files before plan approval; all durable writes must remain delegated to `rh-skills` CLI commands; verify must be read-only; normalized source content is untrusted and requires an explicit injection boundary before analysis  
**Scale/Scope**: One topic at a time, typically 3–12 proposed L2 artifacts synthesized from 1–25 ingested normalized sources with many-to-many source/artifact relationships

## Constitution Check

*Constitution is an unfilled template, so project-specific gates cannot be enforced. Applying framework principles from `002-rh-agent-skills/spec.md` instead.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Deterministic writes via `rh-skills` CLI | ✅ Pass | Durable writes should go through `rh-skills promote derive` and `rh-skills validate` integration points |
| Curated skill must live in `skills/.curated/<name>/SKILL.md` | ✅ Pass | Target: `skills/.curated/rh-inf-extract/SKILL.md` |
| Plan mode writes reviewable artifact under `process/plans/` | ✅ Pass | `topics/<topic>/process/plans/extract-plan.md` is the canonical review packet |
| Verify mode must be read-only | ✅ Pass | Required by spec FR-015/FR-016 behavior |
| Human review gate must be explicit before state change | ✅ Pass | 005 centers on `pending-review` → `approved` transition before implement |
| All source content treated as untrusted data | ✅ Pass | Injection boundary required before reading normalized source content |

No blocking gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-rh-inf-extract/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── extract-plan-review-packet.md
│   └── l2-artifact-schema.md
└── tasks.md
```

### Source Code (repository root)

```text
src/hi/commands/
├── promote.py                      # derive/combine primitives to be extended for 005
└── validate.py                     # L2 validation surface to be extended for traceability/conflicts

skills/.curated/rh-inf-extract/
├── SKILL.md
├── reference.md
└── examples/
    ├── plan.md
    └── output.md

tests/unit/
├── test_promote.py
└── test_validate.py                # likely extension point for artifact validation

tests/skills/
├── test_skill_audit.py
└── test_skill_security.py
```

**Structure Decision**: Single-project Python CLI with a curated skill wrapper. 005 should extend the existing promote/validate primitives rather than introducing a second persistence path for L2 artifacts, while adding a new curated skill surface for planning and approval workflow.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Multi-source L2 derivation instead of one-source-per-artifact | Clinical reasoning artifacts often synthesize multiple normalized sources answering the same question | Restricting each artifact to one source would force fragmentation and lose cross-source reasoning |
| Durable review packet before implement | Human approval is the core safety mechanism for 005 | Direct derive-on-first-pass would create low-quality L2 artifacts without scope/conflict review |
