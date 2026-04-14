# Research: `rh-inf-formalize` Skill — Phase 0

**Branch**: `006-rh-inf-formalize` | **Date**: 2026-04-14

---

## Decision 1: `formalize-plan.md` is a durable review packet

**Decision**: `rh-inf-formalize plan <topic>` should write
`topics/<topic>/process/plans/formalize-plan.md` as a durable, reviewer-facing
artifact.

**Rationale**:
- Formalize changes the highest-value artifact in the RH lifecycle and requires
  explicit review before any L3 file is written.
- Reviewers need a stable artifact that records the selected structured inputs,
  required computable sections, alternates considered, and approval state.

**Alternatives considered**:
- Stdout-only planning summary — rejected because it cannot serve as a durable
  approval gate.
- YAML-only machine file — rejected because the primary audience is a human
  reviewer comparing formalization choices.

---

## Decision 2: Formalize v1 centers on one primary pathway-oriented package

**Decision**: Formalize v1 should implement one primary pathway-oriented
computable artifact package per approved plan. The plan may still include
alternate candidates for reviewer comparison.

**Rationale**:
- One primary output keeps approval, implementation, and verification simple.
- Pathway-oriented packages best match the existing RH lifecycle framing for L3
  outputs while still allowing supporting sections such as actions, measures,
  value sets, assessments, or libraries.

**Alternatives considered**:
- Support multiple approved outputs in one run — rejected because it complicates
  approval semantics, reporting, and validation.
- Treat every L3 section type as equally primary — rejected because it leaves
  v1 too open-ended.

---

## Decision 3: Only approved and currently valid L2 inputs are eligible

**Decision**: Formalize plan generation and implement should only consider
structured artifacts that were approved in extract and still pass validation at
formalize time.

**Rationale**:
- Formalize should not compound unresolved upstream quality issues.
- The extract review gate is the source-of-truth handoff into L3 work.

**Alternatives considered**:
- Allow any structured artifact in the topic — rejected because it weakens the
  extract approval gate.
- Let reviewers override invalid inputs inside formalize — rejected because it
  hides upstream remediation needs.

---

## Decision 4: Reuse `promote combine`, but extend plan-aware validation

**Decision**: Keep deterministic L3 writes in `rh-skills promote combine` and
extend surrounding plan/validation contracts rather than adding a second L3
writer.

**Rationale**:
- The constitution requires durable writes to live in canonical CLI commands.
- `promote combine` already owns computable artifact creation and
  `computable_converged` events.
- Reusing one writer avoids contract drift between formalize and the underlying
  L3 schema.

**Alternatives considered**:
- New `formalize combine` writer — rejected because it duplicates persistence
  responsibilities already present in `promote combine`.

---

## Decision 5: Verify must check section completeness, not just existence

**Decision**: `rh-inf-formalize verify` should combine base L3 schema validation
with plan-aware completeness checks for each required section type.

**Rationale**:
- A pathway section without steps or a value set without codes is not
  operationally useful even if it satisfies top-level schema requirements.
- Reviewers need actionable, section-specific failures instead of a generic
  “schema valid” result.

**Minimum completeness rules**:
- `pathways` require one or more steps
- `value_sets` require codes
- `measures` require numerator and denominator
- `actions` require intent plus description or conditions
- `libraries` require language and content

**Alternatives considered**:
- Presence-only checks — rejected because they would allow empty but technically
  present sections.
- Schema-only checks — rejected because the base schema treats these sections as
  optional.

---

## Decision 6: Preserve unresolved modeling choices in the plan

**Decision**: Formalize planning should carry forward unresolved modeling choices
or overlapping structured inputs as explicit reviewer-visible notes.

**Rationale**:
- Structured artifacts may overlap in scope or support multiple computable
  representations.
- Silent omission of overlap decisions would weaken review quality and create
  unexplained implementation behavior.

**Alternatives considered**:
- Silently pick one modeling approach — rejected because it hides meaningful
  tradeoffs.
