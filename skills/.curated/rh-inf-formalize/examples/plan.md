# Example Formalize Review Packet (Multi-Type)

This example shows a topic with 3 L2 artifact types, each producing a
type-specific formalize plan artifact.

```markdown
---
topic: diabetes-ccm
plan_type: formalize
status: pending-review
reviewer: ""
reviewed_at: null
artifacts:
  - name: diabetes-ccm-decision-table
    artifact_type: decision-table
    strategy: decision-table
    l3_targets:
      - PlanDefinition
      - Library
    input_artifacts:
      - screening-decisions
    rationale: "L2 type decision-table → PlanDefinition (ECA rules) + Library (CQL). ⚠ Overlaps care-pathway on PlanDefinition."
    required_sections:
      - actions
      - libraries
    implementation_target: true
    reviewer_decision: pending-review
    approval_notes: ""
  - name: diabetes-ccm-care-pathway
    artifact_type: care-pathway
    strategy: care-pathway
    l3_targets:
      - PlanDefinition
      - ActivityDefinition
    input_artifacts:
      - care-pathway
    rationale: "L2 type care-pathway → PlanDefinition (clinical-protocol) + ActivityDefinition. ⚠ Overlaps decision-table on PlanDefinition."
    required_sections:
      - pathways
      - actions
    implementation_target: false
    reviewer_decision: pending-review
    approval_notes: ""
  - name: diabetes-ccm-terminology
    artifact_type: terminology
    strategy: terminology
    l3_targets:
      - ValueSet
      - ConceptMap
    input_artifacts:
      - lab-value-sets
    rationale: "L2 type terminology → ValueSet + ConceptMap."
    required_sections:
      - value_sets
    implementation_target: false
    reviewer_decision: pending-review
    approval_notes: ""
---

# Review Summary

- Topic: `diabetes-ccm`
- Proposed computable artifacts: 3 (one per L2 type)
- Primary implementation target: `diabetes-ccm-decision-table`
- ⚠ Overlap detected: decision-table and care-pathway both produce PlanDefinition
- Reviewer action required before any L3 file is written.

# Proposed Artifacts

## diabetes-ccm-decision-table

- Strategy: `decision-table`
- L3 targets: PlanDefinition (ECA rules), Library (CQL)
- Input: screening-decisions
- Required sections: actions, libraries
- Implementation target: `yes`

## diabetes-ccm-care-pathway

- Strategy: `care-pathway`
- L3 targets: PlanDefinition (clinical-protocol), ActivityDefinition
- Input: care-pathway
- Required sections: pathways, actions

## diabetes-ccm-terminology

- Strategy: `terminology`
- L3 targets: ValueSet, ConceptMap
- Input: lab-value-sets
- Required sections: value_sets

# Cross-Artifact Issues

- **PlanDefinition overlap**: decision-table and care-pathway both produce PlanDefinition.
  Default resolution: separate resources with distinct `type` values (eca-rule vs clinical-protocol).
  Reviewer should confirm this is appropriate or request compose resolution.
- Terminology ValueSet canonical URLs should be referenced by PlanDefinition condition expressions.

# Implementation Readiness

- Current plan status: `pending-review`
- Implement MUST NOT proceed until `status: approved` and all targets have `reviewer_decision: approved`.
```
