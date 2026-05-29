# Care Pathway Auto-Derivation Example

## Overview

When a decision table artifact includes **pathway_phases** metadata, the corresponding care pathway can be **auto-generated** using the `rh-skills derive pathway` command.

This eliminates manual pathway authoring, ensures consistency, and reduces duplication.

---

## When to Use Auto-Derivation

✅ **Use auto-derivation when:**
- A decision-table artifact with `pathway_phases` metadata exists
- Guideline has temporal/procedural workflow structure
- Events are organized into sequential clinical phases

❌ **Do NOT use auto-derivation when:**
- No decision table exists for the workflow
- Guideline describes workflow without decision logic
- Decision table lacks `pathway_phases` (diagnostic, screening, treatment optimization guidelines)

---

## Example: Diabetes Foot Care Pathway

### Step 1: Decision Table with pathway_phases

Source decision table: `diabetes-foot-care-decisions.yaml`

```yaml
id: diabetes-foot-care-decisions
artifact_type: decision-table
pathway_phases:
  - id: screening
    label: "Annual Foot Screening"
    description: "Assess diabetic foot risk"
    order: 1
  - id: classification
    label: "Risk Classification"
    description: "Stratify patients by ulcer/amputation risk"
    order: 2
  - id: intervention
    label: "Prevention Interventions"
    description: "Targeted interventions based on risk level"
    order: 3
  - id: monitoring
    label: "Ongoing Monitoring"
    description: "Follow-up schedule based on risk tier"
    order: 4

sections:
  events:
    - id: e1-annual-screen
      label: "Annual Foot Examination"
      phase: screening
      phase_order: 1
    - id: e2-risk-assessment
      label: "Risk Stratification Decision"
      phase: classification
      phase_order: 1
    - id: e3-education
      label: "Patient Education Decision"
      phase: intervention
      phase_order: 1
    - id: e4-podiatry-referral
      label: "Podiatry Referral Decision"
      phase: intervention
      phase_order: 2
    - id: e5-schedule-followup
      label: "Follow-Up Scheduling Decision"
      phase: monitoring
      phase_order: 1
  
  conditions:
    - id: has-diabetes
      description: "Patient has type 1 or type 2 diabetes"
    - id: high-risk-features
      description: "Neuropathy, deformity, or prior ulcer present"
  
  actions:
    - id: conduct-screen
      description: "Perform annual comprehensive foot examination"
    - id: classify-risk
      description: "Assign risk category (low/moderate/high)"
    - id: provide-education
      description: "Deliver foot care education"
    - id: refer-podiatry
      description: "Refer to podiatry"
    - id: schedule-3mo
      description: "Schedule 3-month follow-up"
    - id: schedule-12mo
      description: "Schedule 12-month follow-up"
  
  rules:
    - id: r1
      event: e1-annual-screen
      when: {has-diabetes: true}
      action: conduct-screen
      rationale: "ADA Standards of Care 2024, Recommendation 11.18"
    - id: r2
      event: e2-risk-assessment
      when: {has-diabetes: true}
      action: classify-risk
      rationale: "ADA Standards of Care 2024, Recommendation 11.19"
    - id: r3
      event: e3-education
      when: {has-diabetes: true}
      action: provide-education
      rationale: "ADA Standards of Care 2024, Recommendation 11.20"
    - id: r4
      event: e4-podiatry-referral
      when: {high-risk-features: true}
      action: refer-podiatry
      rationale: "ADA Standards of Care 2024, Recommendation 11.21"
    - id: r5
      event: e5-schedule-followup
      when: {high-risk-features: true}
      action: schedule-3mo
      rationale: "ADA Standards of Care 2024, Recommendation 11.22a"
    - id: r6
      event: e5-schedule-followup
      when: {high-risk-features: false}
      action: schedule-12mo
      rationale: "ADA Standards of Care 2024, Recommendation 11.22b"
```

---

### Step 2: Auto-Generate Care Pathway

Run the derive command:

```bash
rh-skills derive pathway --from-decision-table diabetes-foot-care-decisions
```

**Output**: `diabetes-foot-care-decisions-pathway.yaml` generated in `topics/diabetes-ccm/structured/`

---

### Step 3: Generated Pathway Structure

```yaml
id: diabetes-foot-care-decisions-pathway
name: diabetes-foot-care-decisions-pathway
title: "Pathway For Diabetes Foot Care Workflow"
version: "0.1.0"
status: draft
domain: diabetes-ccm
description: |
  Auto-generated care pathway from diabetes-foot-care-decisions decision table.
  Organizes clinical decision points into workflow phases.
  
  NOTE: This artifact is auto-generated. Do not edit manually.
  Regenerate using: rh-skills derive pathway --from-decision-table diabetes-foot-care-decisions --force

derived_from:
  - diabetes-foot-care-decisions
artifact_type: care-pathway
clinical_question: "How should the diabetes-ccm workflow be organized across care phases?"

fhir_mapping:
  profile: "http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-pathwaydefinition"
  plan_definition_type: "clinical-protocol"
  library: "diabetes-foot-care-decisions"
  subject: "Patient"
  auto_generated: true
  source_artifact: "diabetes-foot-care-decisions"
  generation_timestamp: "2026-05-28T20:31:00Z"

sections:
  summary: |
    This pathway organizes the diabetes-ccm care continuum into 4 clinical phases.
    Each phase contains decision points and activities derived from the 
    diabetes-foot-care-decisions decision table.
  
  steps:
    - id: screening
      label: "Annual Foot Screening"
      description: "Assess diabetic foot risk"
      actor: "Clinician"
      substeps:
        - id: screening-decision
          label: "Screening Decision"
          description: "Annual Foot Examination"
          event: "e1-annual-screen"
    
    - id: classification
      label: "Risk Classification"
      description: "Stratify patients by ulcer/amputation risk"
      actor: "Clinician"
      substeps:
        - id: risk-assessment
          label: "Risk Stratification Decision"
          description: "Risk Stratification Decision"
          event: "e2-risk-assessment"
    
    - id: intervention
      label: "Prevention Interventions"
      description: "Targeted interventions based on risk level"
      actor: "Clinician"
      substeps:
        - id: education
          label: "Patient Education Decision"
          description: "Patient Education Decision"
          event: "e3-education"
        - id: podiatry-referral
          label: "Podiatry Referral Decision"
          description: "Podiatry Referral Decision"
          event: "e4-podiatry-referral"
    
    - id: monitoring
      label: "Ongoing Monitoring"
      description: "Follow-up schedule based on risk tier"
      actor: "Clinician"
      substeps:
        - id: followup-scheduling
          label: "Follow-Up Scheduling Decision"
          description: "Follow-Up Scheduling Decision"
          event: "e5-schedule-followup"
```

---

## Key Benefits of Auto-Derivation

1. **No duplication**: Pathway structure derived directly from decision table metadata
2. **Consistency**: Events, phases, and sequencing guaranteed to match decision logic
3. **Traceability**: `derived_from` and `auto_generated` metadata explicit
4. **Maintainability**: Regenerate pathway when decision table changes (single source of truth)
5. **Speed**: Instant generation vs manual pathway authoring

---

## Workflow Integration

### Extract Plan Entry

When planning L2 extraction, include **both** artifacts:

```yaml
artifacts:
  - name: diabetes-foot-care-decisions
    artifact_type: decision-table
    source_files:
      - sources/normalized/ada-2024-standards.md
    required_sections:
      - summary
      - events
      - conditions
      - actions
      - rules
      - pathway_phases  # ← Required for auto-derivation
      - evidence_traceability
  
  # Do NOT manually author this pathway — auto-derive it instead
  # - name: diabetes-foot-care-pathway
  #   artifact_type: care-pathway
  #   ...
```

### Derivation Command

After decision table is implemented and validated:

```bash
rh-skills validate diabetes-ccm l2 diabetes-foot-care-decisions
rh-skills derive pathway --from-decision-table diabetes-foot-care-decisions
rh-skills validate diabetes-ccm l2 diabetes-foot-care-decisions-pathway
```

---

## When Manual Pathway Authoring is Appropriate

**Only manually author a care-pathway when:**

1. **No decision table exists** — Guideline describes workflow without conditional decision logic
2. **Non-temporal guideline** — Diagnostic tree or screening eligibility (no sequential phases)
3. **Pathway spans multiple decision tables** — Complex pathways combining logic from multiple tables

**Example of manual pathway (no decision table)**:

```yaml
id: patient-onboarding-pathway
artifact_type: care-pathway
description: |
  Onboarding workflow for new chronic disease patients.
  No conditional decision logic; purely procedural checklist.

sections:
  steps:
    - step: 1
      code: "Welcome and Enrollment"
      description: "Register patient, collect demographics"
      substeps:
        - substep: "1.1"
          description: "Verify insurance eligibility"
        - substep: "1.2"
          description: "Complete intake forms"
    - step: 2
      code: "Baseline Assessment"
      description: "Initial clinical evaluation"
      substeps:
        - substep: "2.1"
          description: "Collect vital signs and labs"
        - substep: "2.2"
          description: "Review medication history"
```

---

## Summary

**Default approach**: If a decision table with `pathway_phases` exists, **always use auto-derivation**.

**Command**: `rh-skills derive pathway --from-decision-table <decision-table-id>`

**Only manually author pathways** when no decision table exists or pathway spans multiple tables.
