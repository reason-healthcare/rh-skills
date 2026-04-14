# Feature Specification: rh-inf-extract Skill

**Feature Branch**: `005-rh-inf-extract`  
**Created**: 2026-04-04  
**Status**: Draft  
**Depends On**: [002 — RH Skills](../002-rh-agent-skills/), [004 — rh-inf-ingest](../004-rh-inf-ingest/)

## Overview

`rh-inf-extract` is an agent skill that plans and executes the derivation of
structured (L2) artifacts from ingested L1 source material, with a mandatory
human review gate between planning and implementation. Unlike `rh-inf-ingest`,
whose plan is an operational pre-flight summary, `rh-inf-extract` produces a
**review packet** organized around proposed L2 artifacts. Each proposed artifact
may synthesize one or more normalized sources when they answer the same
clinical question.

The skill uses a **hybrid clinical reasoning catalog**: it starts from standard
artifact types such as eligibility criteria, exclusions, risk factors, decision
points, workflow steps, terminology/value sets, measure logic, and evidence
summaries, but allows custom artifacts when the topic requires them. All L2
artifacts share a common base schema and may require type-specific sections.

It operates in three modes:

| Mode | Output | CLI Commands Used |
|------|--------|-------------------|
| `plan` | `topics/<name>/process/plans/extract-plan.md` | `rh-skills status <name>`, `rh-skills list`, `rh-skills promote plan <name>` |
| `implement` | L2 artifacts in `topics/<name>/structured/` | `rh-skills promote derive`, `rh-skills validate` |
| `verify` | Validation report for all L2 artifacts | `rh-skills validate <topic> <artifact>` |

The plan → implement gate prevents low-quality, redundant, or poorly-scoped
artifacts by requiring explicit reviewer approval of artifact definition, source
coverage, and conflict disposition before any files are written.

## User Story

After ingesting ADA guideline PDFs and related sources, a clinical
informaticist wants to derive structured artifacts from the evidence corpus.
They invoke `rh-inf-extract plan`, which generates an organized review packet of
candidate structured (L2) artifacts to derive (for example:
`screening-criteria`, `risk-factors`, `diagnostic-thresholds`,
`workflow-steps`). For each artifact, the plan shows its type, source coverage,
key questions answered, expected sections, and unresolved conflicts. The
reviewer edits and approves the plan, then invokes `rh-inf-extract implement`,
which calls `rh-skills promote derive` for each approved artifact. Finally,
`rh-inf-extract verify` confirms required fields, claim traceability, and
conflict handling are present in all produced artifacts.

**Why this priority**: Extraction is where clinical reasoning is first captured
in structured form. Human review at the plan stage prevents low-quality,
redundant, or poorly-supported artifacts before they become durable L2 inputs to
formalization.

**Independent Test**: Run `rh-inf-extract plan` on a topic with ingested source
artifacts and confirm a candidate structured artifact review packet is produced
before any L2 files are written.

## Acceptance Scenarios

1. **Given** a topic with one or more ingested source artifacts, **When**
   `rh-inf-extract plan` is invoked, **Then**
   `topics/<name>/process/plans/extract-plan.md` is written as a review packet
   organized around proposed L2 artifacts rather than pipeline stages.
2. **Given** a proposed L2 artifact is based on several normalized sources,
   **When** the plan is generated, **Then** the artifact records all contributing
   `source_files[]`, the clinical question being answered, and the expected
   sections to derive.
3. **Given** an extract plan is still `pending-review` or contains any artifact
   marked `needs-revision`, **When** `rh-inf-extract implement` is invoked,
   **Then** the skill fails immediately with a clear approval error and writes no
   L2 files.
4. **Given** an extract plan has been approved, **When**
   `rh-inf-extract implement` is invoked, **Then** `rh-skills promote derive` is
   called only for approved artifacts and results are validated with
   `rh-skills validate`.
5. **Given** source evidence materially conflicts, **When** the plan is written
   or L2 artifacts are derived, **Then** both positions are preserved,
   unresolved conflicts are surfaced for reviewer resolution, and preferred
   interpretations are explicitly marked rather than silently collapsing the
   disagreement.
6. **Given** a topic has no ingested or normalized source artifacts, **When**
   `rh-inf-extract plan` is invoked, **Then** the skill warns and exits without
   producing a plan.

## Requirements

### Functional Requirements

**Plan mode**
- **FR-001**: `rh-inf-extract plan` MUST analyze ingested topic inputs — at
  minimum tracked source artifacts and normalized source content available from
  `rh-inf-ingest`, plus `concepts.yaml` if present — and write
  `topics/<name>/process/plans/extract-plan.md` as a review packet proposing a
  set of structured (L2) artifacts.
- **FR-002**: The extract plan MUST use structured Markdown with a YAML front
  matter block. YAML front matter MUST include: `topic`, `plan_type: extract`,
  `status` (`pending-review | approved | rejected`), `reviewer`,
  `reviewed_at`, and an `artifacts[]` list.
- **FR-003**: Each `artifacts[]` entry in the plan MUST include:
  `name`, `artifact_type`, `source_files[]`, `rationale`, `key_questions[]`,
  `required_sections[]`, `unresolved_conflicts[]`, `reviewer_decision`
  (`pending-review | approved | needs-revision | rejected`), and
  `approval_notes`. A `custom_artifact_type` field MAY be included when the
  proposal falls outside the standard catalog, but only when no standard type
  preserves the artifact's meaning; reviewer approval notes MUST justify the
  custom type.
- **FR-004**: The plan body MUST be well-organized for human review and include
  these sections in order: `Review Summary`, `Proposed Artifacts`
  (one review card per artifact), `Cross-Artifact Issues`, and
  `Implementation Readiness`.
- **FR-005**: Proposed artifacts MUST use a hybrid clinical reasoning catalog.
  The standard catalog MUST include, at minimum: eligibility or criteria,
  exclusions, risk factors, decision points, workflow steps,
  terminology or value sets, measure logic, and evidence summary. Custom
  artifact types are allowed when the topic requires them.
- **FR-006**: A single L2 artifact MAY synthesize multiple normalized source
  artifacts when they address the same clinical question. The plan MUST record
  the full contributing `source_files[]` set for each artifact.
- **FR-007**: The plan MUST require claim-level evidence traceability. Each
  proposed artifact MUST identify that every key extracted claim, criterion, or
  rule in the resulting L2 artifact will cite one or more supporting source
  references.
- **FR-008**: When source evidence materially conflicts, the plan MUST preserve
  both positions, record the conflict explicitly, and identify any preferred
  interpretation with rationale. Conflicts MUST NOT be silently collapsed.
- **FR-009**: If `extract-plan.md` already exists, the skill MUST warn and stop
  unless `--force` is passed.
- **FR-010**: Successful `plan` mode MUST append `extract_planned` to
  `tracking.yaml`.

**Implement mode**
- **FR-011**: `rh-inf-extract implement` MUST NOT proceed without a valid
  `topics/<name>/process/plans/extract-plan.md`.
- **FR-012**: `rh-inf-extract implement` MUST fail unless the plan
  `status` is `approved`. It MUST also fail if any artifact intended for
  implementation has `reviewer_decision` other than `approved`.
- **FR-013**: `rh-inf-extract implement` MUST call `rh-skills promote derive`
  for each approved artifact using the approved artifact name and the source set
  defined in the plan.
- **FR-014**: After each `rh-skills promote derive`, `rh-inf-extract implement`
  MUST run `rh-skills validate <topic> <name>`. If validation fails, the
  specific missing fields MUST be surfaced and the artifact MUST be reported as
  failed.

**Verify mode**
- **FR-015**: `rh-inf-extract verify` MUST run `rh-skills validate` on each L2
  artifact expected by the approved extract plan and report pass/fail per
  artifact with field-level detail on failures.
- **FR-016**: `rh-inf-extract verify` MUST additionally check that each L2
  artifact preserves claim-level evidence traceability and records unresolved
  conflicts when the plan required them.
- **FR-017**: Successful per-artifact `implement` MUST append
  `structured_derived`.

### Non-Functional Requirements

- **NFR-001**: Skill MUST reside at `skills/.curated/rh-inf-extract/SKILL.md`
  and follow the anthropic skills-developer SKILL.md template.
- **NFR-002**: All file writes and validation MUST be delegated to canonical
  `rh-skills` CLI commands, including `rh-skills promote plan`,
  `rh-skills promote derive`, and `rh-skills validate` as appropriate.
- **NFR-003**: The extract plan UX MUST be optimized for human review. A
  reviewer should be able to identify proposed artifacts, source coverage,
  unresolved conflicts, reviewer decisions, and implementation readiness from
  scan-friendly headings and bullet fields without reading narrative prose in
  full.

## Notes

- `rh-inf-ingest` produces an operational plan; `rh-inf-extract` produces a
  review packet. The two plan files are intentionally different in format and
  UX.
- A single normalized source may contribute to multiple L2 artifacts, and a
  single L2 artifact may synthesize multiple normalized sources.
- The human review step between `plan` and `implement` is critical — the plan
  file is intentionally editable and serves as an approval gate, not just a
  suggestion list.
- L2 artifacts in `topics/<name>/structured/` become inputs to
  `rh-inf-formalize` (006).
