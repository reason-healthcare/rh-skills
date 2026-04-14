# Research: `rh-inf-verify` Skill — Phase 0

**Branch**: `007-rh-inf-verify` | **Date**: 2026-04-14

---

## Decision 1: 007 remains a read-only standalone orchestrator

**Decision**: `rh-inf-verify` should remain a standalone, topic-level verification
skill with no `plan` or `implement` mode and no durable artifact output.

**Rationale**:
- The feature is intentionally read-only, so the constitution does not require a
  new `plan -> implement -> verify` artifact flow.
- Reviewers need a unified verification entry point, not another state-advancing
  stage.

**Alternatives considered**:
- Add a new durable verification report file — rejected because it creates a new
  artifact surface for a read-only workflow.
- Convert 007 into another lifecycle stage — rejected because verification is a
  cross-stage readout, not a state transition.

---

## Decision 2: Reuse stage-specific verify workflows via subagents

**Decision**: `rh-inf-verify` should invoke the applicable lifecycle-specific
verify workflows via subagents instead of re-implementing their validation rules
directly.

**Rationale**:
- Each lifecycle skill owns its own verification semantics and safety checks.
- Reusing the existing verify flows preserves the constitution's minimal-surface
  requirement and reduces drift.

**Alternatives considered**:
- Call `rh-skills validate` directly for every stage from 007 — rejected because
  that bypasses stage-specific reporting logic and applicability checks.
- Create a new umbrella CLI validator — rejected because it duplicates logic the
  stage skills already own.

---

## Decision 3: Applicability should be derived from topic state and artifacts

**Decision**: 007 should determine whether a stage is applicable, not yet ready,
or unavailable by inspecting topic lifecycle state, expected artifacts, and
existing review-plan context.

**Rationale**:
- Topics will often be partial, and later-stage verify workflows should not be
  treated as hard failures when prerequisites are absent.
- Applicability is part of the reviewer-facing output, not an implementation
  detail to hide.

**Alternatives considered**:
- Always run every stage verify unconditionally — rejected because partial topics
  would generate noisy and misleading failures.
- Omit inapplicable stages entirely — rejected because silent omission weakens
  reviewer trust in the consolidated report.

---

## Decision 4: Standardize consolidated stage result statuses

**Decision**: The unified report should use a normalized per-stage status set:
`pass`, `fail`, `warning-only`, `not-applicable`, and `invocation-error`.

**Rationale**:
- Reviewers need one consistent vocabulary across heterogeneous stage-specific
  verify outputs.
- Invocation problems must be distinguishable from domain validation failures.

**Alternatives considered**:
- Binary pass/fail only — rejected because warnings and applicability decisions
  would be lost.
- Preserve raw stage outputs without normalization — rejected because the unified
  report would be harder to scan and compare.

---

## Decision 5: Preserve stage attribution and next actions

**Decision**: The consolidated report should preserve which stage produced each
failure or warning and surface the next reviewer action per affected stage.

**Rationale**:
- The main value of unified verify is reducing manual cross-referencing while
  keeping remediation actionable.
- Flattened summaries would weaken evidence integrity and make troubleshooting
  slower.

**Alternatives considered**:
- Show only a topic-level readiness verdict — rejected because it hides where
  remediation must happen.

---

## Decision 6: Prefer skill/docs/tests changes over new Python helpers

**Decision**: 007 should primarily land as a curated skill, companion files, and
skill/docs/test updates, only adding Python helper logic if implementation
proves that applicability inference cannot be expressed clearly with existing
CLI surfaces.

**Rationale**:
- The current repo already has `status` and `validate` CLI surfaces that expose
  most of the information needed for applicability and reporting.
- Staying in the curated-skill layer minimizes surface area.

**Alternatives considered**:
- Start by adding a new orchestration CLI command — rejected because the spec
  does not require a new deterministic command boundary for this read-only flow.
