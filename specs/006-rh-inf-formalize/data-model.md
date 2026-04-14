# Data Model: `rh-inf-formalize` Skill

**Phase 1 Design Artifact** | **Branch**: `006-rh-inf-formalize`

---

## Entity 1: Formalize Review Packet (`topics/<topic>/process/plans/formalize-plan.md`)

This is a Markdown review packet with YAML frontmatter.

```markdown
---
topic: diabetes-ccm
plan_type: formalize
status: pending-review
reviewer: ""
reviewed_at: null
artifacts:
  - name: diabetes-care-pathway
    artifact_type: pathway-package
    input_artifacts:
      - screening-criteria
      - risk-factors
      - workflow-steps
    rationale: "Combines approved L2 artifacts into one computable care pathway."
    required_sections:
      - pathways
      - actions
      - value_sets
    implementation_target: true
    reviewer_decision: pending-review
    approval_notes: ""
---

# Review Summary
...
```

**Rules**:
- `topic`, `plan_type`, `status`, `reviewer`, `reviewed_at`, and `artifacts[]`
  are required.
- `plan_type` is always `formalize`.
- `status` is one of `pending-review`, `approved`, `rejected`.
- The plan body must include these sections in order:
  1. `Review Summary`
  2. `Proposed Artifacts`
  3. `Cross-Artifact Issues`
  4. `Implementation Readiness`

---

## Entity 2: Proposed Computable Artifact Entry

```yaml
- name: diabetes-care-pathway
  artifact_type: pathway-package
  input_artifacts:
    - screening-criteria
    - risk-factors
    - workflow-steps
  rationale: "Single computable package for downstream execution and export."
  required_sections:
    - pathways
    - actions
    - value_sets
    - measures
  implementation_target: true
  reviewer_decision: approved
  approval_notes: "Use the pathway package as the primary output."
```

**Rules**:
- `name` must be kebab-case and unique within the plan.
- `input_artifacts[]` must refer only to approved and currently valid L2
  artifacts in `topics/<topic>/structured/`.
- At most one entry may set `implementation_target: true`.
- `reviewer_decision` is one of `pending-review`, `approved`,
  `needs-revision`, `rejected`.

---

## Entity 3: Computable Artifact (`topics/<topic>/computable/<name>.yaml`)

```yaml
artifact_schema_version: "1.0"
metadata:
  id: diabetes-care-pathway
  name: diabetes-care-pathway
  title: Diabetes Care Pathway
  version: "1.0.0"
  status: draft
  domain: diabetes
  created_date: 2026-04-14
  description: Computable package derived from approved L2 artifacts.
converged_from:
  - screening-criteria
  - risk-factors
  - workflow-steps
pathways:
  - id: pathway-1
    title: Initial Screening Pathway
    description: Screening and escalation flow.
    steps:
      - id: step-1
        title: Evaluate screening eligibility
actions:
  - id: action-1
    title: Order HbA1c
    intent: order
    description: Order confirmatory testing
value_sets:
  - id: value-set-1
    title: Diabetes Diagnoses
    description: Diabetes-related diagnostic codes
    system: http://snomed.info/sct
    codes:
      - code: "44054006"
        display: Diabetes mellitus type 2
```

**Rules**:
- All base `l3-schema.yaml` required metadata remains required.
- `converged_from[]` should match the approved `input_artifacts[]` set.
- Formalize v1 treats a pathway-oriented package as the primary output shape.
- Required sections must exist and satisfy minimum completeness rules from the
  approved plan.

---

## Entity 4: Formalize Verification Result

Read-only report rendered by verify.

Per artifact:
- approval state aligned with plan ✓/✗
- file exists ✓/✗
- schema-valid ✓/✗
- required sections present ✓/✗
- required sections minimally complete ✓/✗

Topic-wide:
- approved implementation target derived ✓/✗
- no alternate candidate implemented as the primary output ✓/✗

---

## State Transitions

```text
planned (pending-review)
  ├── reviewer approves plan + target → approved
  ├── reviewer marks needs-revision → pending-review
  └── reviewer rejects plan → rejected

approved target
  └── implement → computable artifact created + validated
```

- Implement may only proceed from `status: approved`.
- Exactly one approved entry may be the implementation target.
- Verify never changes state.

---

## Relationships

- One topic has one active formalize review packet.
- One review packet contains one or more candidate computable artifacts.
- One candidate computable artifact references many structured inputs.
- One structured input may contribute to many formalize candidates over time.
- One approved implementation target maps to one L3 computable artifact file.
