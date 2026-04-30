---
topic: diabetes-ccm
plan_type: extract
status: pending-review
reviewer: ""
reviewed_at: null
artifacts:
  - name: screening-decisions
    artifact_type: decision-table
    source_files:
      - sources/normalized/ada-2024-guideline.md
      - sources/normalized/uspstf-screening.md
    rationale: "Combines guideline and preventive screening evidence into decision logic with eligibility conditions."
    key_questions:
      - Who should be screened?
      - At what interval?
      - What are the exclusion criteria?
    required_sections:
      - summary
      - events
      - conditions
      - actions
      - rules
      - evidence_traceability
      - concerns
    concerns:
      - concern: "ADA interval language is more explicit than USPSTF interval framing."
        resolution: ""
    reviewer_decision: pending-review
    approval_notes: ""
  - name: diabetes-evidence
    artifact_type: evidence-summary
    source_files:
      - sources/normalized/ada-2024-guideline.md
      - sources/normalized/cdc-surveillance.md
    rationale: "Captures evidence findings and risk factors for downstream reasoning."
    key_questions:
      - What does the evidence say about diabetes risk?
      - Which factors materially elevate diabetes risk?
    required_sections:
      - summary_points
      - risk_factors
      - evidence_traceability
    concerns: []
    reviewer_decision: pending-review
    approval_notes: ""
---

# Review Summary

Two extract artifacts are proposed from the current ingested corpus. The first
captures screening decision logic (eligibility, exclusions, thresholds) as a
decision-table. The second synthesizes evidence findings and risk factors.

# Proposed Artifacts

## screening-decisions

- **Type**: decision-table
- **Sources**: ADA guideline, USPSTF screening statement
- **Open issue**: interval language differs between sources

## diabetes-evidence

- **Type**: evidence-summary
- **Sources**: ADA guideline, CDC surveillance summary
- **Open issue**: none blocking

# Cross-Artifact Issues

- Overlap between patient-level risk factors and screening eligibility logic
- Terminology normalization still needed for formalization

# Implementation Readiness

- Reviewer approval required before any derive step
- `screening-decisions` likely needs explicit conflict disposition before approval
