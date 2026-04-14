# Feature Specification: rh-inf-formalize Skill

**Feature Branch**: `006-rh-inf-formalize`  
**Created**: 2026-04-14  
**Status**: Draft  
**Depends On**: [002 — RH Skills](../002-rh-agent-skills/), [005 — rh-inf-extract](../005-rh-inf-extract/)
**Input**: User description: "formalize structured artifacts into a computable format (L3)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan computable artifact scope (Priority: P1)

After a topic has approved structured (L2) artifacts, a clinical informaticist
wants `rh-inf-formalize plan` to produce a durable review packet that proposes
the computable artifact to build, identifies which L2 artifacts should converge,
and names the L3 sections that must be created before any computable file is
written.

**Why this priority**: A reviewable formalization plan is the safety gate
between structured reasoning and durable computable output. Without it, teams
could converge the wrong artifacts or omit required computable sections.

**Independent Test**: Run `rh-inf-formalize plan <topic>` on a topic with one or
more structured artifacts and confirm that
`topics/<topic>/process/plans/formalize-plan.md` is written with candidate L3
artifact details, selected L2 inputs, required computable sections, and no L3
file creation.

**Acceptance Scenarios**:

1. **Given** a topic with approved structured artifacts, **When**
   `rh-inf-formalize plan <topic>` is invoked, **Then**
   `topics/<topic>/process/plans/formalize-plan.md` is written as a review
   packet describing the proposed computable artifact and its input artifacts.
2. **Given** a topic has no structured artifacts ready for convergence, **When**
   `rh-inf-formalize plan <topic>` is invoked, **Then** the skill warns and exits
   without creating a formalize plan.

---

### User Story 2 - Implement approved computable artifact (Priority: P1)

After a reviewer approves the formalize plan, a clinical informaticist wants
`rh-inf-formalize implement` to create only the approved computable artifact,
using the exact structured inputs and computable sections recorded in the plan.

**Why this priority**: Formalization is the point where RH outputs become
durable L3 artifacts for downstream use. The approved plan must control which
inputs are merged and what computable content is emitted.

**Independent Test**: Approve `formalize-plan.md`, run
`rh-inf-formalize implement <topic>`, and confirm that only approved artifact
entries are formalized into `topics/<topic>/computable/` and immediately
validated.

**Acceptance Scenarios**:

1. **Given** a formalize plan is still pending review or contains a target
   artifact not approved for implementation, **When**
   `rh-inf-formalize implement <topic>` is invoked, **Then** the skill fails
   immediately and writes no computable artifact.
2. **Given** a formalize plan has been approved, **When**
   `rh-inf-formalize implement <topic>` is invoked, **Then** the skill calls
   `rh-skills promote combine` for the approved artifact, using the planned L2
   inputs, and then runs `rh-skills validate <topic> <artifact>` on the result.

---

### User Story 3 - Verify computable artifact completeness (Priority: P2)

After formalization, a reviewer wants `rh-inf-formalize verify` to confirm that
the computable artifact exists, passes schema validation, and contains the
planned computable sections needed for downstream execution or export.

**Why this priority**: Verification prevents incomplete or mismatched L3
artifacts from being treated as production-ready computable knowledge.

**Independent Test**: Run `rh-inf-formalize verify <topic>` after implement and
confirm per-artifact pass/fail reporting for plan alignment, file existence, and
required computable sections without modifying any files.

**Acceptance Scenarios**:

1. **Given** an approved formalize plan and a derived computable artifact,
   **When** `rh-inf-formalize verify <topic>` is invoked, **Then** the skill
   reports pass/fail per planned artifact and highlights missing required
   computable sections.
2. **Given** verify mode is run repeatedly, **When** `rh-inf-formalize verify`
   is invoked, **Then** it performs read-only checks and does not create,
   modify, or delete any file.

### Edge Cases

- What happens when a formalize plan references an L2 artifact that no longer
  exists in `topics/<topic>/structured/`?
- How does the system handle a plan that names multiple candidate computable
  artifacts but only one is approved?
- What happens when required computable sections are partially present but empty?
- How does the workflow respond when one structured input overlaps in meaning
  with another and the reviewer wants one excluded from convergence?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `rh-inf-formalize plan` MUST analyze structured topic inputs and
  write `topics/<name>/process/plans/formalize-plan.md` as a review packet for
  proposed computable (L3) artifacts.
- **FR-002**: The formalize plan MUST use structured Markdown with YAML front
  matter. YAML front matter MUST include: `topic`, `plan_type: formalize`,
  `status` (`pending-review | approved | rejected`), `reviewer`,
  `reviewed_at`, and an `artifacts[]` list.
- **FR-003**: Each `artifacts[]` entry in the formalize plan MUST include:
  `name`, `artifact_type`, `input_artifacts[]`, `rationale`,
  `required_sections[]`, `reviewer_decision`
  (`pending-review | approved | needs-revision | rejected`), and
  `approval_notes`.
- **FR-004**: The formalize plan body MUST be organized for human review and
  include these sections in order: `Review Summary`, `Proposed Artifacts`,
  `Cross-Artifact Issues`, and `Implementation Readiness`.
- **FR-005**: `rh-inf-formalize plan` MUST warn and stop unless `--force` is
  passed when `formalize-plan.md` already exists.
- **FR-006**: Successful `plan` mode MUST append `formalize_planned` to
  `tracking.yaml`.
- **FR-007**: `rh-inf-formalize implement` MUST NOT proceed without a valid
  `topics/<name>/process/plans/formalize-plan.md`.
- **FR-008**: `rh-inf-formalize implement` MUST fail unless the plan
  `status` is `approved`. It MUST also fail if any artifact intended for
  implementation has `reviewer_decision` other than `approved`.
- **FR-009**: `rh-inf-formalize implement` MUST call
  `rh-skills promote combine` for each approved computable artifact using the
  approved artifact name and the `input_artifacts[]` set defined in the plan.
- **FR-010**: After each `rh-skills promote combine`,
  `rh-inf-formalize implement` MUST run `rh-skills validate <topic> <name>`. If
  validation fails, the specific missing fields or sections MUST be surfaced and
  the artifact MUST be reported as failed.
- **FR-011**: `rh-inf-formalize verify` MUST run `rh-skills validate` on each
  computable artifact expected by the approved formalize plan and report
  pass/fail per artifact with field-level detail on failures.
- **FR-012**: `rh-inf-formalize verify` MUST additionally confirm that each
  computable artifact contains the required computable sections declared in the
  approved plan.
- **FR-013**: Successful per-artifact `implement` MUST append
  `computable_converged`.
- **FR-014**: A single computable artifact MAY converge multiple structured
  artifacts, and the plan MUST record the full `input_artifacts[]` set for each
  proposed computable artifact.
- **FR-015**: Formalize planning and verification MUST preserve review-visible
  notes about unresolved modeling choices or overlapping inputs instead of
  silently dropping them from the plan.

### Key Entities *(include if feature involves data)*

- **Formalize Review Packet**: The durable Markdown + YAML artifact at
  `topics/<topic>/process/plans/formalize-plan.md` that records the proposed L3
  artifact, selected L2 inputs, required computable sections, review state, and
  approval notes.
- **Proposed Computable Artifact Entry**: A plan entry that identifies one L3
  artifact by name, type, `input_artifacts[]`, rationale, required sections, and
  reviewer disposition.
- **Computable Artifact**: The resulting L3 artifact in
  `topics/<topic>/computable/` that converges approved L2 inputs into a
  machine-usable representation for downstream execution or export.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Reviewers can inspect a generated formalize plan and identify the
  proposed computable artifact, its selected structured inputs, and its required
  sections within 2 minutes.
- **SC-002**: 100% of approved formalize implementations either produce a
  computable artifact that passes validation or fail with artifact-specific
  error reporting and no partial success.
- **SC-003**: 100% of verify runs on approved formalize plans report whether
  each expected computable artifact exists and whether required sections are
  present.
- **SC-004**: Formalize plan mode never creates a computable artifact before the
  reviewer approval gate is satisfied.

## Assumptions

- Approved structured artifacts from `rh-inf-extract` are the only inputs to
  this feature; raw sources and L1 ingest behavior are out of scope.
- Formalize v1 focuses on one topic at a time and typically produces one primary
  computable artifact per plan, though the plan may describe multiple
  candidates.
- Reviewers are comfortable editing Markdown + YAML front matter plan artifacts
  directly before running implement.
- Downstream FHIR export or runtime execution is out of scope for this feature;
  006 only produces and verifies computable repository artifacts.
