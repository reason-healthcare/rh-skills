# Care Pathway Alignment Example

## Overview

Use this example when a temporal or procedural decision table includes
`sections.pathway_phases[]` and you want the paired care-pathway artifact to
stay aligned with that phase model, especially if direct care-pathway authoring
is struggling to preserve recommendation linkage cleanly.

This example is intentionally written in the **current L2 shapes**:
- decision-table uses `sections.pathway_phases[]`
- rules use `then: [...]`
- care-pathway uses flat `steps[]` with optional `parent_id`
- recommendation linkage belongs on leaf pathway steps via `rule_id` or
  `rule_ids[]`

---

## When This Pattern Fits

Use this pattern when:
- a decision-table already captures the recommendation logic
- the guideline has major temporal or procedural phases
- you want the care-pathway to mirror those phases without re-encoding ECA logic
- you need a fallback scaffold to repair recommendation-to-pathway alignment

Do not use this pattern when:
- the workflow has no paired decision-table
- the source is primarily a diagnostic tree or screening eligibility algorithm
- the pathway needs to combine recommendations from multiple different tables
- direct care-pathway authoring is already producing clear, well-aligned linkage

Fallback command:

```sh
rh-skills promote derive pathway --from-decision-table <decision-table-id>
```

---

## Example Source Pair

### Decision Table

```yaml
id: diabetes-foot-care-decisions
artifact_type: decision-table
domain: diabetes
clinical_question: "What recommendation-scoped decisions govern diabetic foot screening and follow-up?"
sections:
  pathway_phases:
    - id: screening
      label: Annual foot screening
      description: Assess diabetic foot risk
    - id: classification
      label: Risk classification
      description: Stratify patients by ulcer and amputation risk
    - id: intervention
      label: Prevention interventions
      description: Apply targeted interventions based on risk level
    - id: monitoring
      label: Ongoing monitoring
      description: Schedule follow-up based on risk tier
  events:
    - id: annual-foot-screen
      label: Annual foot screening review
      phase: screening
    - id: risk-stratification
      label: Risk stratification review
      phase: classification
    - id: patient-education-review
      label: Patient education review
      phase: intervention
    - id: podiatry-referral-review
      label: Podiatry referral review
      phase: intervention
    - id: followup-scheduling-review
      label: Follow-up scheduling review
      phase: monitoring
  conditions:
    - id: has-diabetes
      label: Diabetes diagnosis confirmed
      values: [Yes, No]
    - id: high-risk-features
      label: High-risk foot features present
      values: [Yes, No]
  actions:
    - id: perform-foot-exam
      label: Perform annual comprehensive foot examination
    - id: assign-risk-category
      label: Assign diabetic foot risk category
    - id: deliver-foot-care-education
      label: Deliver foot care education
    - id: refer-to-podiatry
      label: Refer to podiatry
    - id: schedule-3-month-followup
      label: Schedule 3-month follow-up
    - id: schedule-12-month-followup
      label: Schedule 12-month follow-up
  rules:
    - id: rule-perform-foot-exam
      event: annual-foot-screen
      phase: screening
      when: {has-diabetes: Yes}
      then: [perform-foot-exam]
    - id: rule-assign-risk-category
      event: risk-stratification
      phase: classification
      when: {has-diabetes: Yes}
      then: [assign-risk-category]
    - id: rule-deliver-foot-care-education
      event: patient-education-review
      phase: intervention
      when: {has-diabetes: Yes}
      then: [deliver-foot-care-education]
    - id: rule-refer-to-podiatry
      event: podiatry-referral-review
      phase: intervention
      when: {high-risk-features: Yes}
      then: [refer-to-podiatry]
    - id: rule-schedule-3-month-followup
      event: followup-scheduling-review
      phase: monitoring
      when: {high-risk-features: Yes}
      then: [schedule-3-month-followup]
    - id: rule-schedule-12-month-followup
      event: followup-scheduling-review
      phase: monitoring
      when: {high-risk-features: No}
      then: [schedule-12-month-followup]
```

### Aligned Care Pathway

```yaml
id: diabetes-foot-care-pathway
artifact_type: care-pathway
clinical_question: "How should diabetic foot care recommendations be sequenced across the care pathway?"
metadata:
  derived_from:
    - diabetes-foot-care-decisions
sections:
  steps:
    - id: diabetic-foot-care-pathway
      label: Diabetic foot care pathway
      description: Overall diabetic foot screening and follow-up journey
    - id: screening-phase
      label: Annual foot screening
      description: Screening phase of the pathway
      parent_id: diabetic-foot-care-pathway
    - id: perform-exam-step
      label: Perform annual foot examination
      description: Conduct the annual comprehensive foot exam
      parent_id: screening-phase
      rule_id: rule-perform-foot-exam
      action_labels:
        - Perform annual comprehensive foot examination
    - id: classification-phase
      label: Risk classification
      description: Classification phase of the pathway
      parent_id: diabetic-foot-care-pathway
    - id: assign-risk-step
      label: Assign risk category
      description: Determine diabetic foot risk tier
      parent_id: classification-phase
      rule_id: rule-assign-risk-category
      action_labels:
        - Assign diabetic foot risk category
    - id: intervention-phase
      label: Prevention interventions
      description: Intervention phase of the pathway
      parent_id: diabetic-foot-care-pathway
    - id: education-and-referral-step
      label: Education and referral recommendations
      description: Deliver education and refer high-risk patients when indicated
      parent_id: intervention-phase
      rule_ids:
        - rule-deliver-foot-care-education
        - rule-refer-to-podiatry
      action_labels:
        - Deliver foot care education
        - Refer to podiatry
    - id: monitoring-phase
      label: Ongoing monitoring
      description: Monitoring phase of the pathway
      parent_id: diabetic-foot-care-pathway
    - id: schedule-followup-step
      label: Schedule follow-up
      description: Schedule follow-up according to risk tier
      parent_id: monitoring-phase
      rule_ids:
        - rule-schedule-3-month-followup
        - rule-schedule-12-month-followup
      action_labels:
        - Schedule 3-month follow-up
        - Schedule 12-month follow-up
  transitions:
    - from_id: screening-phase
      to_id: classification-phase
      description: Proceed after screening assessment
    - from_id: classification-phase
      to_id: intervention-phase
      description: Proceed after assigning risk category
    - from_id: intervention-phase
      to_id: monitoring-phase
      description: Proceed to follow-up planning
```

---

## Alignment Rules Illustrated

1. `sections.pathway_phases[]` belongs inside the decision-table `sections` block.
2. Events and rules reference phase IDs via `event.phase` and `rule.phase`.
3. Recommendation logic stays in the decision-table; the care-pathway only
   sequences and groups that logic.
4. Parent pathway steps do not carry `rule_id` or `rule_ids[]` when they also
   have children.
5. A leaf pathway step can link:
   - one recommendation with `rule_id`
   - a tight recommendation cluster with `rule_ids[]`

---

## Practical Guidance

- If several recommendations share the same workflow moment, keep one event in
  the decision-table and separate them into distinct `rules[]` and `actions[]`.
- Mirror the major phase model in the care-pathway, but push recommendation
  linkage down to the most specific leaf step.
- Use grouped `rule_ids[]` only when the linked recommendations genuinely form
  one tight pathway node with the same actor, timing, and clinical meaning.
