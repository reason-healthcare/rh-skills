# Feature Specification: rh-inf-verify Skill

**Feature Branch**: `007-rh-inf-verify`  
**Created**: 2026-04-14  
**Status**: Ready for Review  
**Depends On**: [002 — RH Skills](../002-rh-agent-skills/), [003 — rh-inf-discovery](../003-rh-inf-discovery/), [004 — rh-inf-ingest](../004-rh-inf-ingest/), [005 — rh-inf-extract](../005-rh-inf-extract/), [006 — rh-inf-formalize](../006-rh-inf-formalize/)  
**Input**: User description: "Since our skills all have verify mode, the verify skill should use subagents to call each specific verify."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a unified topic verification report (Priority: P1)

After a topic has progressed through one or more lifecycle stages, a reviewer
wants `rh-inf-verify` to run the available stage-specific verify workflows and
return one consolidated report showing whether the topic is ready to advance or
needs remediation.

**Why this priority**: Reviewers need one trusted verification entry point for a
topic. Without unified verification, they must remember which stage-specific
verify commands to run and manually stitch together the results.

**Independent Test**: Run `rh-inf-verify verify <topic>` on a topic with completed
workflow artifacts and confirm that the output includes a per-stage verification
result for each applicable lifecycle skill, plus an overall topic status,
without modifying any file.

**Acceptance Scenarios**:

1. **Given** a topic with artifacts across multiple lifecycle stages, **When**
   `rh-inf-verify verify <topic>` is invoked, **Then** the skill runs the applicable
   stage-specific verify workflows and returns one consolidated report covering
   each applicable stage.
2. **Given** all applicable stage verifications pass, **When**
   `rh-inf-verify verify <topic>` is invoked, **Then** the report clearly indicates that
   the topic is verification-ready end to end.

---

### User Story 2 - Preserve stage-specific failures and warnings (Priority: P1)

When one or more stage-specific verifications fail or emit warnings, a reviewer
wants `rh-inf-verify` to preserve that stage-level detail in the consolidated
report so they can identify what failed, what is advisory only, and what to fix
next.

**Why this priority**: A unified report is only useful if it does not flatten
important diagnostic detail. Reviewers need the failing stage, blocking issues,
and advisory warnings to remain attributable.

**Independent Test**: Run `rh-inf-verify verify <topic>` on a topic where at least one
applicable stage fails verification and confirm that the output attributes each
blocking failure or warning to the correct stage and distinguishes blocking
issues from advisory findings.

**Acceptance Scenarios**:

1. **Given** one stage returns blocking verification failures, **When**
   `rh-inf-verify verify <topic>` is invoked, **Then** the consolidated report marks
   that stage as failed and preserves its stage-specific failure details.
2. **Given** one stage returns only advisory warnings, **When**
   `rh-inf-verify verify <topic>` is invoked, **Then** the consolidated report marks
   that stage as warning-only rather than failed.
3. **Given** a stage-specific verify workflow cannot be run successfully,
   **When** `rh-inf-verify verify <topic>` is invoked, **Then** the report surfaces the
   invocation problem distinctly from domain validation failures.
4. **Given** a stage is otherwise applicable but its expected artifacts are
   missing or stale relative to the topic lifecycle state, **When**
   `rh-inf-verify verify <topic>` is invoked, **Then** the consolidated report
   marks that stage as failed rather than as an invocation problem.

---

### User Story 3 - Handle partial lifecycle topics safely (Priority: P2)

For a topic that has not reached every lifecycle stage, a reviewer wants
`rh-inf-verify` to verify only the stages that are applicable, explicitly mark
later stages with applicability such as `not-yet-ready` or `not-applicable`,
render them with an explicit non-pass status, and remain strictly
non-destructive.

**Why this priority**: Topics will often be mid-lifecycle. The unified verify
skill must still provide useful guidance without pretending later-stage checks
apply before their prerequisites exist.

**Independent Test**: Run `rh-inf-verify verify <topic>` on a partially
completed topic and confirm that the report verifies eligible stages, marks
later stages explicitly through applicability plus non-pass status, and makes no
file or tracking changes.

**Acceptance Scenarios**:

1. **Given** a topic has completed ingest and extract but not formalize, **When**
   `rh-inf-verify verify <topic>` is invoked, **Then** the report verifies the
   applicable earlier stages, marks formalize applicability as `not-yet-ready`,
   and renders formalize with an explicit `not-applicable` status rather than
   omitting it.
2. **Given** `rh-inf-verify verify <topic>` is run repeatedly on the same topic, **When** it is
   invoked multiple times, **Then** it performs read-only checks and does not
   create, modify, or delete any file.

### Edge Cases

- What happens when a topic exists but none of the lifecycle stages are ready
  for verification yet?
- How does the system report a stage that has expected artifacts missing or
  stale relative to the topic's current lifecycle state? Applicable stages with
  missing or stale expected artifacts should report `fail`; `invocation-error`
  is reserved for verify workflows that cannot run.
- What happens when one stage-specific verify workflow fails to execute while
  others complete successfully?
- How does the consolidated report behave when a stage is intentionally
  inapplicable because the topic has not advanced that far yet?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `rh-inf-verify` MUST be invokable as a standalone topic-level
  verification skill that assesses a topic's current lifecycle state.
- **FR-002**: `rh-inf-verify` MUST determine which lifecycle-stage verify
  workflows are applicable for the topic based on the topic's current artifacts
  and workflow state.
- **FR-003**: For each applicable lifecycle stage, `rh-inf-verify` MUST invoke
  that stage's verify workflow and include the result in a consolidated topic
  verification report.
- **FR-004**: The consolidated report MUST include one result per lifecycle stage
  with a status of pass, fail, warning-only, not-applicable, or invocation-error.
- **FR-005**: `rh-inf-verify` MUST preserve stage-specific blocking failures and
  advisory warnings rather than collapsing them into a generic topic status.
- **FR-006**: When a stage-specific verify workflow cannot be run,
  `rh-inf-verify` MUST report that as an invocation problem distinct from the
  domain verification findings of stages that did run.
- **FR-006a**: When a lifecycle stage is otherwise applicable but its expected
  artifacts are missing or stale relative to the topic's current workflow
  state, `rh-inf-verify` MUST report that stage as `fail` rather than as an
  invocation problem.
- **FR-007**: `rh-inf-verify` MUST provide an overall topic verification summary
  that makes clear whether the topic is ready to advance, blocked, or requires
  review.
- **FR-008**: `rh-inf-verify` MUST explicitly mark lifecycle stages that are not
  yet applicable or not yet ready for verification instead of treating them as
  silent passes or failures. `not-yet-ready` is an applicability decision; the
  normalized stage status remains one of `pass`, `fail`, `warning-only`,
  `not-applicable`, or `invocation-error`.
- **FR-009**: `rh-inf-verify` MUST remain strictly non-destructive. It MUST NOT
  create, modify, or delete any artifact, plan file, checklist, or tracking
  entry.
- **FR-010**: Re-running `rh-inf-verify` on the same unchanged topic MUST
  produce a consistent stage inventory and equivalent verification conclusions.
- **FR-011**: The consolidated report MUST make the failing or warning stage and
  its next recommended reviewer action directly visible without requiring manual
  cross-referencing across separate verify runs.
- **FR-012**: `rh-inf-verify` MUST support topics that are only partially through
  the RH lifecycle and still return a useful verification report for the stages
  that apply.

### Key Entities *(include if feature involves data)*

- **Verification Run**: A single read-only execution of `rh-inf-verify` for one
  topic that collects stage-specific verification outcomes into one report.
- **Stage Verification Result**: The per-stage outcome containing the stage
  name, applicability status, overall result, and any blocking or advisory
  findings produced by that stage's verify workflow.
- **Consolidated Verification Report**: The user-facing topic-level verification
  summary that combines all stage results into one readiness view and next-step
  recommendation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Reviewers can identify the overall topic verification status and
  the first failing or warning stage within 2 minutes of opening a consolidated
  verification report.
- **SC-002**: 100% of lifecycle stages that are applicable to a topic appear in
  the report with an explicit status rather than being omitted silently.
- **SC-003**: 100% of blocking failures and advisory warnings shown in the
  consolidated report remain attributable to the stage that produced them.
- **SC-004**: Re-running unified verification on an unchanged topic produces no
  file modifications and no tracking updates.

## Assumptions

- Each lifecycle skill either already exposes a verify workflow or will do so by
  the time `rh-inf-verify` is implemented for production use.
- Reviewers invoke `rh-inf-verify` for one topic at a time rather than for a
  whole portfolio.
- The unified verify report is read-only and does not replace the underlying
  stage-specific verify workflows; it coordinates and summarizes them.
- Topic lifecycle state and artifact presence provide enough context to decide
  whether a stage is applicable, not yet ready, or unavailable.
