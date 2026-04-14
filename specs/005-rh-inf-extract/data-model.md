# Data Model: `rh-inf-extract` Skill

**Phase 1 Design Artifact** | **Branch**: `005-rh-inf-extract`

---

## Entity 1: Extract Review Packet (`topics/<topic>/process/plans/extract-plan.md`)

This is a Markdown review packet with YAML frontmatter.

```markdown
---
topic: diabetes-ccm
plan_type: extract
status: pending-review
reviewer: ""
reviewed_at: null
artifacts:
  - name: screening-criteria
    artifact_type: eligibility-criteria
    source_files:
      - sources/normalized/ada-2024-guideline.md
      - sources/normalized/uspstf-screening.md
    rationale: "Combines guideline and preventive-service evidence for screening criteria."
    key_questions:
      - Who should be screened?
      - At what interval?
    required_sections:
      - summary
      - criteria
      - evidence_traceability
      - conflicts
    unresolved_conflicts:
      - "ADA annual screening language differs from USPSTF interval framing."
    reviewer_decision: pending-review
    approval_notes: ""
---

# Review Summary
...
```

**Rules**:
- `topic`, `plan_type`, `status`, `reviewer`, `reviewed_at`, and `artifacts[]` are required in frontmatter.
- `plan_type` is always `extract`.
- `status` is one of `pending-review`, `approved`, `rejected`.
- The plan body must include these sections in order:
  1. `Review Summary`
  2. `Proposed Artifacts`
  3. `Cross-Artifact Issues`
  4. `Implementation Readiness`

---

## Entity 2: Proposed Artifact Entry (`extract-plan.md` → `artifacts[]`)

```yaml
- name: risk-factors
  artifact_type: risk-factors
  custom_artifact_type: null
  source_files:
    - sources/normalized/ada-2024-guideline.md
    - sources/normalized/cdc-surveillance.md
  rationale: "Captures cross-source patient and contextual risk factors."
  key_questions:
    - Which factors materially increase risk?
  required_sections:
    - summary
    - factors
    - evidence_traceability
    - conflicts
  unresolved_conflicts:
    - "Some sources distinguish obesity thresholds differently."
  reviewer_decision: needs-revision
  approval_notes: "Clarify age-band handling before derive."
```

**Rules**:
- `name` must be kebab-case and unique within the plan.
- `artifact_type` is required and should come from the hybrid catalog when possible.
- `custom_artifact_type` is optional and only used when the artifact falls outside the standard catalog.
- `source_files[]` contains normalized source paths, not raw source files.
- `reviewer_decision` is one of `pending-review`, `approved`, `needs-revision`, `rejected`.

---

## Entity 3: Derived L2 Artifact (`topics/<topic>/structured/<name>.yaml`)

005 extends the existing generic L2 schema with extract-specific structure.

```yaml
id: screening-criteria
name: screening-criteria
title: Diabetes Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: "Structured screening criteria synthesized from ADA and USPSTF sources."
derived_from:
  - ada-2024-guideline
  - uspstf-screening
artifact_type: eligibility-criteria
clinical_question: Who should be screened for diabetes and at what interval?
sections:
  summary: "Adults with risk factors should receive periodic screening."
  criteria:
    - claim_id: crit-001
      statement: "Adults aged 35 to 70 with overweight or obesity should be screened."
      evidence:
        - source: ada-2024-guideline
          locator: "Section 2"
        - source: uspstf-screening
          locator: "Recommendation Statement"
conflicts:
  - issue: "Interval language differs across sources."
    positions:
      - source: ada-2024-guideline
        statement: "Annual screening in high-risk patients"
      - source: uspstf-screening
        statement: "Screening interval depends on prior results and risk"
    preferred_interpretation:
      source: ada-2024-guideline
      rationale: "More explicit for chronic disease management workflow"
```

**Rules**:
- Existing required metadata (`id`, `name`, `title`, `version`, `status`, `domain`, `description`, `derived_from`) remains intact.
- `artifact_type`, `clinical_question`, `sections`, and `conflicts` are 005 additions.
- Claims under structured sections should support explicit evidence references.
- `conflicts[]` may be empty but must be present when the plan required conflict handling.

---

## Entity 4: Extract Verification Result

Read-only report rendered by skill verify.

Per artifact:
- approval state aligned with plan ✓/✗
- file exists ✓/✗
- schema-valid ✓/✗
- evidence traceability present ✓/✗
- conflict handling present when required ✓/✗

Topic-wide:
- all approved artifacts derived ✓/✗
- no rejected/unapproved artifacts implemented ✓/✗

---

## State Transitions

```text
planned (pending-review)
  ├── reviewer approves plan + artifacts → approved
  ├── reviewer marks needs-revision → pending-review
  └── reviewer rejects plan → rejected

approved artifact
  └── implement → structured artifact created + validated
```

- Implement may only proceed from `status: approved`.
- Artifact-level `reviewer_decision` must be `approved` to derive that artifact.
- Verify never changes state.

---

## Relationships

- One topic has one active extract review packet.
- One review packet contains many proposed artifacts.
- One proposed artifact references many normalized sources.
- One normalized source may contribute to many proposed artifacts.
- One proposed artifact, once approved and implemented, maps to one L2 structured artifact file.
