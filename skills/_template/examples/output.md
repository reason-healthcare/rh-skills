# Example: Output Artifact — `<skill-name> implement`

<!-- LEVEL 3 disclosure — loaded on demand when implementing and the agent
     needs to understand expected output artifact structure. -->

This file shows worked examples of the artifacts produced by `implement` mode.
Clinical content is illustrative only.

---

## L2 Structured Artifact Example

**Location**: `topics/diabetes-screening/structured/screening-criteria.yaml`

```yaml
# ── Provenance ─────────────────────────────────────────────────────────────
name: screening-criteria
topic: diabetes-screening
level: l2
version: "1.0"
created_at: "2026-04-04T15:00:00Z"
derived_from:
  - ada-guidelines-2024

# ── Clinical Content (replace with skill-specific fields) ──────────────────
title: "Diabetes Screening Criteria"
description: >
  Discrete criteria for identifying adults who should be offered type 2
  diabetes screening, based on ADA Standards of Medical Care 2024, Section 2.

eligibility:
  - criterion: age_threshold
    label: "Age ≥ 35 years with BMI ≥ 25 kg/m²"
    logic: "age >= 35 AND bmi >= 25"
    evidence_grade: A
    source_section: "ADA 2024, Section 2.2"

  - criterion: bmi_overweight_any_age
    label: "BMI ≥ 25 with one or more additional risk factors (any age)"
    logic: "bmi >= 25 AND risk_factor_count >= 1"
    evidence_grade: A
    source_section: "ADA 2024, Table 2.3"

  - criterion: previous_abnormal_glucose
    label: "Previous IFG, IGT, HbA1c 5.7–6.4%, or gestational diabetes"
    logic: "prior_prediabetes = true"
    evidence_grade: A
    source_section: "ADA 2024, Section 2.1"

screening_interval:
  value: 3
  unit: years
  condition: "When initial result is normal"
  evidence_grade: B
  source_section: "ADA 2024, Section 2.4"

notes: >
  High-risk groups (PCOS, HIV, sleep apnea, certain medications) may warrant
  earlier or more frequent screening. See risk-factors artifact for full
  enumeration.
```

---

## L3 Computable Artifact Example

**Location**: `topics/diabetes-screening/computable/diabetes-pathway.yaml`

```yaml
# ── Provenance ─────────────────────────────────────────────────────────────
name: diabetes-pathway
topic: diabetes-screening
level: l3
version: "1.0"
created_at: "2026-04-04T16:00:00Z"
converged_from:
  - screening-criteria
  - risk-factors
  - diagnostic-thresholds

# ── FHIR-Compatible Structure ──────────────────────────────────────────────
pathways:
  - id: diabetes-screening-pathway
    title: "Diabetes Screening Clinical Pathway"
    population:
      include:
        - system: SNOMED
          code: "73211009"
          display: "Diabetes mellitus (disorder)"
    steps:
      - step: 1
        label: "Assess eligibility"
        logic_ref: screening-criteria.eligibility
      - step: 2
        label: "Identify risk factors"
        logic_ref: risk-factors.risk_factors
      - step: 3
        label: "Order diagnostic test"
        options:
          - test: HbA1c
            system: LOINC
            code: "4548-4"
          - test: Fasting Plasma Glucose
            system: LOINC
            code: "1558-6"
      - step: 4
        label: "Interpret result"
        logic_ref: diagnostic-thresholds.thresholds

measures:
  - id: diabetes-screening-rate
    title: "Diabetes Screening Rate"
    type: proportion
    numerator: "Eligible patients who received screening in past 3 years"
    denominator: "All eligible patients in the measurement period"
    evidence_grade: B

value_sets:
  - id: diabetes-risk-conditions
    title: "Conditions associated with increased diabetes risk"
    system: SNOMED
    concepts:
      - code: "237599002"
        display: "Impaired fasting glycaemia"
      - code: "44054006"
        display: "Diabetes mellitus type 2"

notes: >
  This pathway encodes ADA 2024 and USPSTF 2021 screening recommendations.
  Thresholds are US-based; international equivalents may differ.
  Reviewed: 2026-04-04. Next review: 2027-04-04.
```

---

## Tracking.yaml Entries (set by `rh-skills` CLI commands)

After `implement` completes, `tracking.yaml` will contain:

```yaml
topics:
  - name: diabetes-screening
    structured:
      - name: screening-criteria
        file: topics/diabetes-screening/structured/screening-criteria.yaml
        derived_from: [ada-guidelines-2024]
        created_at: "2026-04-04T15:00:00Z"
    computable:
      - name: diabetes-pathway
        file: topics/diabetes-screening/computable/diabetes-pathway.yaml
        converged_from: [screening-criteria, risk-factors, diagnostic-thresholds]
        created_at: "2026-04-04T16:00:00Z"
    events:
      - event: structured_derived
        timestamp: "2026-04-04T15:00:00Z"
        payload: {name: screening-criteria, derived_from: [ada-guidelines-2024]}
```
