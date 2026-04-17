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
    rationale: "Combines guideline and preventive screening evidence into one criteria artifact."
    key_questions:
      - Who should be screened?
      - At what interval?
    required_sections:
      - summary
      - evidence_traceability
      - conflicts
    conflicts:
      - conflict: "ADA interval language is more explicit than USPSTF interval framing."
        resolution: ""
    reviewer_decision: pending-review
    approval_notes: ""
  - name: risk-factors
    artifact_type: risk-factors
    source_files:
      - sources/normalized/ada-2024-guideline.md
      - sources/normalized/cdc-surveillance.md
    rationale: "Captures evidence-backed patient and population risk factors."
    key_questions:
      - Which factors materially elevate diabetes risk?
    required_sections:
      - summary
      - evidence_traceability
    conflicts: []
    reviewer_decision: pending-review
    approval_notes: ""
---

# Review Summary

Two extract artifacts are proposed from the current ingested corpus. The first
captures screening criteria synthesized from guideline and preventive-service
evidence. The second isolates risk factors useful for downstream reasoning and
formalization.

# Proposed Artifacts

## screening-criteria

- **Type**: eligibility-criteria
- **Sources**: ADA guideline, USPSTF screening statement
- **Open issue**: interval language differs between sources

## risk-factors

- **Type**: risk-factors
- **Sources**: ADA guideline, CDC surveillance summary
- **Open issue**: none blocking

# Cross-Artifact Issues

- Overlap between patient-level risk factors and screening eligibility logic
- Terminology normalization still needed for formalization

# Implementation Readiness

- Reviewer approval required before any derive step
- `screening-criteria` likely needs explicit conflict disposition before approval
