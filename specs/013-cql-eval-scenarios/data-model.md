# Data Model: CQL Eval Scenarios — Full Measure Pipeline

**Branch**: `013-cql-eval-scenarios` | **Phase**: 1

This is a data-only feature. There are no new database tables, Python classes,
or CLI schemas. This document describes the content structure of the four new
eval scenario YAML files.

---

## Shared Clinical Fixture — `acc-aha-cholesterol-2023.md`

This normalized Markdown appears inline in the extract scenario workspace and
is referenced (trimmed) in formalize scenario prompts. It must contain at least
these 8 distinct clinical facts (SC-003):

| Fact | Value | Used in scenario |
|------|-------|-----------------|
| Age eligibility | Adults 40–75 years | US-2, US-3, US-4 |
| LDL-C threshold (high risk) | ≥70 mg/dL | US-2 |
| LDL-C threshold (high-intensity) | ≥190 mg/dL | US-2 |
| 10-year ASCVD risk (statin consideration) | ≥7.5% | US-2 |
| 10-year ASCVD risk (high-intensity) | ≥20% | US-2 |
| Denominator exclusion 1 | Pregnancy or planned pregnancy | US-2, US-4 |
| Denominator exclusion 2 | Active liver disease | US-2, US-4 |
| Denominator exclusion 3 | ESRD (eGFR <15 or dialysis) | US-2, US-4 |
| Denominator exclusion 4 | Documented statin allergy | US-2, US-4 |
| Numerator criterion | Statin prescription during measurement period | US-2, US-3, US-4 |

---

## Scenario 1 — `quality-measure-source.yaml`

**Path**: `eval/scenarios/rh-inf-ingest/quality-measure-source.yaml`

| Field | Value |
|-------|-------|
| `name` | `quality-measure-source` |
| `skill` | `rh-inf-ingest` |
| `topic` | `lipid-management` |
| Starting state | `discovery_planned` |
| Source ID | `acc-aha-cholesterol-2023` |
| Source type | `clinical-guideline` |
| Evidence level | `ia` |

**Workspace files**:
- `topics/lipid-management/process/plans/discovery-plan.yaml` — discovery plan with one open-access source

**Expected outputs**:
- `sources/normalized/acc-aha-cholesterol-2023.md` — exists
- `topics/lipid-management/process/concepts.yaml` — exists, contains `"LDL-C"`, contains `"statin"`
- `tracking.yaml` — event `ingest_complete`

---

## Scenario 2 — `measure-logic-extraction.yaml`

**Path**: `eval/scenarios/rh-inf-extract/measure-logic-extraction.yaml`

| Field | Value |
|-------|-------|
| `name` | `measure-logic-extraction` |
| `skill` | `rh-inf-extract` |
| `topic` | `lipid-management` |
| Starting state | `ingest_complete` |
| Artifact name | `lipid-statin-therapy` |
| Artifact type | `measure` |

**Workspace files**:
- `sources/normalized/acc-aha-cholesterol-2023.md` — full normalized source content
- `topics/lipid-management/process/plans/discovery-plan.yaml` — approved
- `topics/lipid-management/process/concepts.yaml` — with LDL-C, statin, ASCVD concepts

**L2 artifact structure** (output; also used as input fixture for US-3 and US-4):

```yaml
artifact_type: measure
sections:
  populations:
    initial_population:
      age_range: "40-75"
      diagnosis_value_set: "hyperlipidemia-disorders"
    denominator:
      description: "Equals initial population"
    numerator:
      medication_value_set: "statin-medications"
    denominator_exclusion:
      description: "Active liver disease, pregnancy, ESRD, or statin allergy"
  scoring:
    type: proportion
    improvement_notation: increase
  value_sets:
    - id: hyperlipidemia-disorders
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.9"
    - id: statin-medications
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1047.97"
```

**Expected outputs**:
- `topics/lipid-management/process/plans/extract-plan.yaml` — exists, contains `"measure"`, contains `"populations"`
- `topics/lipid-management/structured/` — any file with `artifact_type: measure`, `populations:`, `value_sets:`
- `tracking.yaml` — events `extract_planned`, `structured_derived`

---

## Scenario 3 — `cql-library-authoring.yaml`

**Path**: `eval/scenarios/rh-inf-formalize/cql-library-authoring.yaml`

| Field | Value |
|-------|-------|
| `name` | `cql-library-authoring` |
| `skill` | `rh-inf-formalize` |
| `topic` | `lipid-management` |
| Starting state | `extract_complete` |
| L2 input artifact | `lipid-statin-therapy` (measure, status: approved) |

**Workspace files**:
- `topics/lipid-management/process/plans/extract-plan.yaml` — approved
- `topics/lipid-management/structured/lipid-statin-therapy/lipid-statin-therapy.yaml` — measure L2 artifact

**CQL structure the agent must produce**:

```cql
library LipidStatinTherapy version '1.0.0'
using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1' called FHIRHelpers
valueset "Hyperlipidemia Disorders": '<vsac-url>'
valueset "Statin Medications": '<vsac-url>'
parameter "Measurement Period" Interval<DateTime>
context Patient
define "Initial Population": ...
define "Denominator": "Initial Population"
define "Numerator": ...[MedicationRequest] during "Measurement Period"...
define "Denominator Exclusion": ...
```

**Expected outputs**:
- `topics/lipid-management/process/plans/formalize-plan.md` — exists, contains `"Library"`, `"CQL"`
- `topics/lipid-management/computable/Library-lipid-statin-therapy.json` — exists, contains `"resourceType": "Library"`, `"text/cql"`
- `topics/lipid-management/computable/Measure-lipid-statin-therapy.json` — exists, contains `"resourceType": "Measure"`, `"group"`
- CQL content — contains `"context Patient"`, `'define "InitialPopulation"'` or `'define "Initial Population"'`, `"valueset"`

---

## Scenario 4 — `measure-bundle-complete.yaml`

**Path**: `eval/scenarios/rh-inf-formalize/measure-bundle-complete.yaml`

| Field | Value |
|-------|-------|
| `name` | `measure-bundle-complete` |
| `skill` | `rh-inf-formalize` |
| `topic` | `lipid-management` |
| Starting state | `extract_complete` |
| L2 input artifacts | `lipid-statin-therapy` (measure) + `lipid-exclusions` (decision-table) |

**Workspace files**:
- `topics/lipid-management/process/plans/extract-plan.yaml` — two artifacts approved
- `topics/lipid-management/structured/lipid-statin-therapy/lipid-statin-therapy.yaml` — measure L2
- `topics/lipid-management/structured/lipid-exclusions/lipid-exclusions.yaml` — decision-table L2

**Decision-table L2 fixture** (`lipid-exclusions`):

```yaml
artifact_type: decision-table
sections:
  conditions:
    - id: exc-liver   / exc-pregnancy / exc-esrd / exc-allergy
  value_sets:
    - liver-disease-disorders, pregnancy-disorders, esrd-disorders
```

**Expected outputs** (cross-link checks are key):
- `computable/Library-lipid-statin-therapy.json` — exists
- `computable/Measure-lipid-statin-therapy.json` — exists, contains `"library"`, contains `"lipid-statin-therapy"`
- `computable/PlanDefinition-lipid-statin-therapy.json` — exists, contains `"definitionCanonical"`
- Measure JSON contains `"Library-lipid-statin-therapy"` (cross-link)
- PlanDefinition JSON contains `"Measure-lipid-statin-therapy"` (cross-link)
- `tracking.yaml` — events `formalize_planned`, `computable_converged`

---

## Validation approach

Since this is a data-only feature, validation consists of:

1. **YAML parse check** — `python -c 'import yaml; yaml.safe_load(open("<file>"))'` for all four files
2. **Required fields check** — all fields in the schema (`name`, `skill`, `description`, `topic`, `workspace`, `prompt`, `expected_outputs`, `efficiency_focus`, `quality_focus`) present and non-empty
3. **Eval harness dry-run** — `scripts/eval-skill.sh --scenario <name> --dry-run` where supported
4. **Manual review** — content coherence across the four scenarios (workspace fixtures match pipeline order)
