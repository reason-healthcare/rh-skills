# Research: `rh-inf-status` Skill — Phase 0

**Branch**: `008-rh-inf-status` | **Date**: 2026-04-14

---

## Decision 1: Use `rh-skills status` as the single status engine

**Decision**: `rh-inf-status` should reuse the existing `rh-skills status`
command family as the canonical source of status summaries and next-step
recommendations.

**Rationale**:
- The feature goal is UX consistency across the RH workflow, which depends on a
  single deterministic status surface.
- The constitution prefers extending existing primitives over creating parallel
  commands or duplicated reasoning.

**Alternatives considered**:
- Keep separate status reasoning in `SKILL.md` — rejected because it would drift
  from the CLI and weaken determinism.
- Introduce a new standalone status CLI — rejected because `rh-skills status`
  already owns the relevant read-only status boundary.

---

## Decision 2: Replace lettered choices with deterministic bullet next steps

**Decision**: All status-driven follow-up suggestions should be emitted as bullet
items, not A/B/C-style choice menus.

**Rationale**:
- Lettered menus are model-specific presentation, not a stable workflow
  contract.
- Bullet lists preserve user guidance while staying deterministic and portable
  across models and interfaces.

**Alternatives considered**:
- Keep lettered options in the skill layer only — rejected because the UX would
  still vary by model behavior.
- Remove next-step guidance entirely — rejected because the user explicitly wants
  status to always suggest what to do next.

---

## Decision 3: Generate next steps from deterministic lifecycle logic

**Decision**: The next-step set should be produced by deterministic CLI logic
based on topic or portfolio state, not by freeform agent reasoning.

**Rationale**:
- The recommendations need to be reproducible, testable, and consistent across
  environments.
- The existing status command already contains lifecycle-aware recommendation
  logic that can be extended rather than replaced.

**Alternatives considered**:
- Let the skill improvise recommendations from status text — rejected because it
  weakens testability and consistency.
- Emit only one next action with no alternatives — rejected because the spec
  calls for a next-steps section, not just a single command.

---

## Decision 4: Keep topic, portfolio, and drift views under one UX contract

**Decision**: Single-topic status, portfolio status, and drift reporting should
share the same status vocabulary and next-steps presentation contract.

**Rationale**:
- Users should not have to learn a different interaction model for each status
  mode.
- A common contract simplifies testing and documentation.

**Alternatives considered**:
- Keep drift reporting as a special-case output with different follow-up wording
  — rejected because it preserves the inconsistency the feature is meant to fix.

---

## Decision 5: Preserve read-only behavior and explicit no-action states

**Decision**: `rh-inf-status` should remain fully read-only and must still emit a
next-steps section even when no immediate action is recommended.

**Rationale**:
- Read-only behavior aligns with the constitution's status-only exemption from
  plan/implement/verify flow.
- An explicit "no action required" message is more trustworthy than omitting the
  next-step section entirely.

**Alternatives considered**:
- Omit next steps when the topic looks complete — rejected because the user
  expects status to always say what to do next.
- Allow the skill to write reminder artifacts — rejected because status is a
  read-only feature.
