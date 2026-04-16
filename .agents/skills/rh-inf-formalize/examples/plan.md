# Example Formalize Review Packet

```markdown
---
topic: diabetes-ccm
plan_type: formalize
status: pending-review
reviewer: ""
reviewed_at: null
artifacts:
  - name: diabetes-ccm-pathway
    artifact_type: pathway-package
    input_artifacts:
      - screening-criteria
      - workflow-steps
      - terminology-value-sets
    rationale: Combines approved structured inputs into a single care pathway package.
    required_sections:
      - pathways
      - actions
      - value_sets
    implementation_target: true
    reviewer_decision: pending-review
    approval_notes: ""
---

# Review Summary

- Topic: `diabetes-ccm`
- Proposed computable artifacts: 1
- Primary implementation target: `diabetes-ccm-pathway`
- Reviewer action required before any L3 file is written.

# Proposed Artifacts

## diabetes-ccm-pathway

- Type: `pathway-package`
- Eligible structured inputs: screening-criteria, workflow-steps, terminology-value-sets
- Rationale: Combines approved L2 artifacts into one pathway-oriented package for downstream use.
- Required computable sections: pathways, actions, value_sets
- Implementation target: `yes`
- Unresolved modeling notes: confirm whether terminology notes stay inline or become a future alternate package.
- Reviewer decision: `pending-review`

# Cross-Artifact Issues

- Confirm overlapping workflow and eligibility logic are represented once in the final pathway.

# Implementation Readiness

- Current plan status: `pending-review`
- Implement MUST NOT proceed until `status: approved` and the target has `reviewer_decision: approved`.
```
