# Feature Specification: rh-inf-status Skill

**Feature Branch**: `008-rh-inf-status`  
**Created**: 2026-04-14  
**Status**: ✅ Complete  
**Depends On**: [002 — RH Skills](../002-rh-agent-skills/), [003 — rh-inf-discovery](../003-rh-inf-discovery/), [004 — rh-inf-ingest](../004-rh-inf-ingest/), [005 — rh-inf-extract](../005-rh-inf-extract/), [006 — rh-inf-formalize](../006-rh-inf-formalize/), [007 — rh-inf-verify](../007-rh-inf-verify/)  
**Input**: User description: "008 we should create this skill to use the same CLI to report status we use elsewhere to have a consistent UX. Status skill should always suggest the user what to do next. Let's remove the A, B, C choice as this is not consistent across models, rather a simple bullet list of what they can do. This should be deterministic, so we should be able to build into the CLI command"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See current topic status with deterministic next steps (Priority: P1)

A reviewer or operator wants `rh-inf-status` to show the current lifecycle state
of a topic using the same underlying status readout used elsewhere in the RH
workflow, and to always include a deterministic set of next actions.

**Why this priority**: Status is only useful if it is consistent across skills
and immediately tells the user what to do next without relying on model-specific
phrasing.

**Independent Test**: Run `rh-inf-status <topic>` on a topic at any lifecycle
stage and confirm that the output shows the topic's current state plus a
deterministic bullet list of recommended next actions.

**Acceptance Scenarios**:

1. **Given** a valid topic, **When** `rh-inf-status <topic>` is invoked,
   **Then** the status report uses the canonical RH status view and shows the
   current lifecycle state for that topic.
2. **Given** a valid topic, **When** `rh-inf-status <topic>` is invoked,
   **Then** the output includes a bullet list of recommended next actions rather
   than lettered choices such as A, B, or C.
3. **Given** no immediate action is needed, **When** `rh-inf-status <topic>` is
    invoked, **Then** the output still includes an explicit next-steps section
    stating that no action is currently required.
4. **Given** the requested topic does not exist, **When** `rh-inf-status <topic>`
   is invoked, **Then** the command fails with a clear explanation and tells the
   user how to inspect available topics or initialize the requested topic.

---

### User Story 2 - Review portfolio status with consistent UX (Priority: P1)

A team lead wants `rh-inf-status` to summarize the portfolio or multiple topics
using the same status language and next-step format that single-topic views use,
so that status checking feels consistent across the RH workflow.

**Why this priority**: The skill should not present one format for topic status
and a different one for portfolio status. Consistency makes the workflow easier
to learn and trust.

**Independent Test**: Run `rh-inf-status` with no topic and confirm that the
portfolio output shows consistent lifecycle summaries and deterministic bullet
next steps for follow-up actions.

**Acceptance Scenarios**:

1. **Given** multiple topics exist, **When** `rh-inf-status` is invoked without a
   topic argument, **Then** it shows a portfolio status summary using the same
   canonical status surface and next-step style as the single-topic view.
2. **Given** multiple topics have different lifecycle states, **When**
    `rh-inf-status` is invoked, **Then** the output makes the most relevant next
    actions for the portfolio directly visible as bullet items.
3. **Given** no topics exist yet, **When** `rh-inf-status` is invoked, **Then**
   the command explains that the portfolio is empty and recommends how to start
   a topic next.

---

### User Story 3 - Detect drift and still guide the next action (Priority: P2)

When source files have changed or expected workflow inputs are missing, a user
wants `rh-inf-status` to report that drift clearly and still tell them what to
do next in the same deterministic bullet-list format.

**Why this priority**: Drift detection is only actionable if users immediately
understand the consequence and the next corrective step.

**Independent Test**: Run the status drift-checking flow on a topic with changed
or missing sources and confirm that the output reports the problem and includes
deterministic bullet next steps for remediation.

**Acceptance Scenarios**:

1. **Given** a topic has changed or missing source inputs, **When** the
   status drift-checking flow is invoked, **Then** the output reports the drift
   and includes bullet next steps for remediation.
2. **Given** a topic has downstream artifacts that may now be stale, **When**
   the drift-checking flow is invoked, **Then** the output makes the stale-risk
   consequence and the recommended next actions directly visible.

### Edge Cases

- What happens when `rh-inf-status` is invoked for a topic that does not exist?
- What happens when no topics exist yet?
- How does the system behave when a topic exists but has no meaningful next
  action beyond monitoring or review?
- How does the status output behave when multiple next actions are reasonable?
- What happens when the canonical status view can be shown but drift detection
  cannot complete successfully?

For 008, drift reporting is in scope for deterministic filesystem-observable
states (`ok`, `changed`, `missing`) and explicit user-facing command failures.
Partial drift reports for unexpected runtime I/O failures are out of scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `rh-inf-status` MUST use the canonical `rh-skills status`
  reporting surface for status readouts so that users see the same status model
  across the RH workflow.
- **FR-002**: Every `rh-inf-status` response MUST include a deterministic
  next-steps section.
- **FR-003**: The next-steps section MUST be presented as a simple bullet list
  of actions the user can take; it MUST NOT rely on lettered options such as A,
  B, or C.
- **FR-004**: For a single topic, `rh-inf-status` MUST show the topic's current
  lifecycle state, artifact counts, and latest recorded event so that a user can
  understand whether the topic is ready to advance, needs review, or is blocked.
- **FR-005**: For a portfolio view, `rh-inf-status` MUST summarize current topic
  state using the same status language and next-step style as the single-topic
  view.
- **FR-006**: When drift or missing-input checks are requested, `rh-inf-status`
  MUST report changed or missing inputs and identify downstream work that may be
  affected.
- **FR-007**: The recommended next actions shown by `rh-inf-status` MUST come
  from deterministic RH status logic rather than model-specific freeform choice
  generation.
- **FR-008**: `rh-inf-status` MUST remain strictly read-only. It MUST NOT create,
  modify, or delete artifacts, plans, checklists, or tracking entries.
- **FR-009**: If a topic or portfolio state has no immediate action, the
  next-steps section MUST still communicate that clearly instead of being
  omitted.
- **FR-010**: If the requested topic does not exist or status cannot be
  determined, `rh-inf-status` MUST fail with a clear, user-facing explanation of
  what to do next, including the relevant recovery command when one is available.

### Key Entities *(include if feature involves data)*

- **Topic Status View**: The user-facing summary of a topic's current RH
  lifecycle state, readiness, and recommended next actions.
- **Portfolio Status View**: The user-facing summary across topics that highlights
  current state and recommended follow-up work.
- **Next-Step Recommendation Set**: The deterministic bullet list of actions a
  user can take after reviewing status.
- **Drift Finding**: A reported changed or missing input, along with the
  downstream work that may now require re-review or rework.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can identify the current state of a topic and at least one
  recommended next action within 1 minute of opening a status report.
- **SC-002**: 100% of `rh-inf-status` outputs include an explicit next-steps
  section, even when no action is required.
- **SC-003**: 100% of recommended next actions are presented as bullet items,
  with no lettered A/B/C-style choices in the status UX.
- **SC-004**: Users reviewing a drift report can identify the affected topic
  inputs and the recommended corrective action without cross-referencing another
  command output.

## Assumptions

- The existing RH workflow already has a canonical status model that can be used
  as the single source of truth for status reporting.
- Status recommendations can be expressed deterministically from current topic or
  portfolio state.
- A topic-level status view and a portfolio-level status view are both in scope
  for this feature.
- Drift reporting remains read-only and is intended to guide follow-up work
  rather than repair anything automatically.
