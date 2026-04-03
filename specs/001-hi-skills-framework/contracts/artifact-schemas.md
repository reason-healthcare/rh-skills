# Artifact Schemas: Healthcare Informatics Skills Framework

**Phase**: 1 — Design  
**Branch**: `001-hi-skills-framework`  
**Date**: 2026-04-03

---

## L2 Artifact Schema (`schemas/l2-schema.yaml`)

Semi-structured YAML with defined fields. Schema-guided, not fully computable.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | kebab-case string | Unique artifact identifier within the skill |
| `name` | PascalCase string | Machine-friendly name |
| `title` | string | Human-readable display name |
| `version` | semver string | e.g., `"1.0.0"` |
| `status` | enum | `draft` \| `active` \| `retired` |
| `description` | multi-line string | Clinical purpose statement (2+ sentences) |
| `domain` | string | Clinical domain (e.g., `"Hypertension Management"`) |
| `derived_from` | list of strings | L1 artifact names that produced this L2 |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `notes` | string | Author annotations |
| `references` | list of strings | Source citations |
| `tags` | list of strings | Searchable labels |
| `subject_area` | string | Clinical sub-domain |

### Example

```yaml
id: screening-criteria
name: ScreeningCriteria
title: "Diabetes Screening Criteria"
version: "1.0.0"
status: draft
domain: "Diabetes Management"
description: |
  Semi-structured representation of evidence-based diabetes screening criteria.
  Derived from ADA clinical practice guidelines excerpt.
derived_from:
  - ada-guidelines-excerpt
notes: "Focus on Type 2 diabetes; Type 1 excluded from this artifact"
references:
  - "ADA Standards of Medical Care in Diabetes, 2024"
tags:
  - diabetes
  - screening
  - primary-care
```

---

## L3 Artifact Schema (`schemas/l3-schema.yaml`)

Computable YAML with a custom domain schema. FHIR-compatible (mappable to FHIR R4/R5) but usable without FHIR tooling.

### Required Fields (metadata block)

| Field | Type | FHIR Mapping | Description |
|-------|------|-------------|-------------|
| `artifact_schema_version` | string | — | Always `"1.0"` |
| `metadata.id` | kebab-case string | Resource.id | Unique artifact identifier |
| `metadata.name` | PascalCase string | Resource.name | Machine-friendly name |
| `metadata.title` | string | Resource.title | Human-readable display name |
| `metadata.version` | semver string | Resource.version | Semantic version |
| `metadata.status` | enum | Resource.status | `draft` \| `active` \| `retired` |
| `metadata.domain` | string | — | Clinical domain |
| `metadata.created_date` | YYYY-MM-DD | Resource.date | Creation date |
| `metadata.description` | multi-line string | Resource.description | Clinical purpose (2+ sentences) |
| `converged_from` | list of strings | — | L2 artifact names that contributed |

### Optional Sections

At least one section beyond `metadata` is expected, but no single section is required.

#### `pathways` → FHIR `PlanDefinition`

| Field | FHIR Mapping |
|-------|-------------|
| `identifier` | `PlanDefinition.id` |
| `name` | `PlanDefinition.name` |
| `title` | `PlanDefinition.title` |
| `canonical` | `PlanDefinition.url` |
| `type` | `PlanDefinition.type` — `clinical-protocol` \| `workflow-definition` \| `eca-rule` |
| `strategies[].actions[].condition.expression` | `PlanDefinition.action.condition.expression` |
| `strategies[].actions[].activity_definition` | `PlanDefinition.action.definitionCanonical` |

#### `actions` → FHIR `ActivityDefinition`

| Field | FHIR Mapping |
|-------|-------------|
| `kind` | `ActivityDefinition.kind` — `MedicationRequest` \| `ServiceRequest` \| `Task` |
| `intent` | `ActivityDefinition.intent` — always `proposal` |
| `options[].code` | `ActivityDefinition.code` |
| `options[].dose` / `unit` | `ActivityDefinition.dosage` |

#### `libraries` → FHIR `Library`

| Field | FHIR Mapping |
|-------|-------------|
| `name` | `Library.name` — must end in `Logic` |
| `cql_file` | `Library.content[0]` reference |
| `data_requirements[].resource_type` | `Library.dataRequirement.type` |
| `data_requirements[].code_binding` | `Library.dataRequirement.codeFilter` |
| `defines[].name` | CQL `define` name (case-sensitive match required) |

#### `measures` → FHIR `Measure`

| Field | FHIR Mapping |
|-------|-------------|
| `scoring` | `Measure.scoring` — `proportion` \| `ratio` \| `continuous-variable` \| `cohort` |
| `populations[].code` | `Measure.group.population.code` — `initial-population` \| `denominator` \| `numerator` |
| `populations[].expression` | `Measure.group.population.criteria.expression` |

#### `assessments` → FHIR `Questionnaire` (SDC)

| Field | FHIR Mapping |
|-------|-------------|
| `items[].link_id` | `Questionnaire.item.linkId` |
| `items[].type` | `Questionnaire.item.type` — `choice` \| `string` \| `integer` \| `boolean` \| `date` |
| `items[].answer_value_set` | `Questionnaire.item.answerValueSet` |
| `items[].calculated_expression` | SDC extension `sdc-questionnaire-calculatedExpression` |

#### `value_sets` → FHIR `ValueSet`

| Field | FHIR Mapping |
|-------|-------------|
| `includes[].system` | `ValueSet.compose.include.system` |
| `includes[].codes` | `ValueSet.compose.include.concept[]` |

#### `code_systems` → FHIR `CodeSystem`

| Field | FHIR Mapping |
|-------|-------------|
| `concepts[].code` | `CodeSystem.concept.code` |
| `concepts[].display` | `CodeSystem.concept.display` |
| `concepts[].definition` | `CodeSystem.concept.definition` |

### Preferred Standard Code Systems

| Content | System URI |
|---------|-----------|
| Observations, labs, questionnaire items | `http://loinc.org` |
| Conditions, procedures | `http://snomed.info/sct` |
| Diagnoses | `http://hl7.org/fhir/sid/icd-10-cm` |
| Medications | `http://www.nlm.nih.gov/research/umls/rxnorm` |

### Example (minimal valid L3 artifact)

```yaml
artifact_schema_version: "1.0"

metadata:
  id: diabetes-screening-guideline
  name: DiabetesScreeningGuideline
  title: "Diabetes Screening Clinical Guideline"
  version: "1.0.0"
  status: draft
  domain: "Diabetes Management"
  created_date: "2026-04-03"
  description: |
    Computable representation of evidence-based diabetes screening criteria.
    Covers risk stratification, testing recommendations, and follow-up intervals.

converged_from:
  - screening-criteria
  - risk-factors

pathways:
  - identifier: dm-screening
    name: DiabetesScreeningPathway
    title: "Diabetes Screening Pathway"
    canonical: "http://example.org/fhir/PlanDefinition/dm-screening"
    type: clinical-protocol
    strategies:
      - identifier: risk-assessment
        title: "Risk Assessment and Screening"
        actions:
          - identifier: rec-screen-a1c
            title: "Recommend A1C or fasting glucose testing"
            condition:
              library: DiabetesScreeningLogic
              expression: "Is Screening Recommended"
            populations:
              - "Age >= 35 with BMI >= 25"
              - "Any age with additional risk factors"
            strength: strong
            grade: B

libraries:
  - identifier: dm-screening-logic
    name: DiabetesScreeningLogic
    version: "1.0.0"
    type: logic-library
    data_requirements:
      - name: HasDiabetesRiskFactors
        resource_type: Condition
        code_binding:
          value_set: "http://example.org/fhir/ValueSet/dm-risk-conditions"
    defines:
      - name: "Is Screening Recommended"
        description: "Patient meets ADA criteria for diabetes screening"

value_sets:
  - identifier: dm-risk-conditions
    name: DiabetesRiskConditions
    title: "Diabetes Risk Factor Conditions"
    canonical: "http://example.org/fhir/ValueSet/dm-risk-conditions"
    version: "1.0.0"
    status: draft
    includes:
      - system: "http://hl7.org/fhir/sid/icd-10-cm"
        codes:
          - code: E11
            display: "Type 2 diabetes mellitus"
          - code: R73.09
            display: "Prediabetes"
```

---

## Tracking Artifact Schema (`schemas/tracking-schema.yaml`)

Written and updated exclusively by CLI commands. Never manually edited.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Always `"1.0"` |
| `skill.name` | kebab-case string | Matches skill directory name |
| `skill.created_at` | ISO-8601 | Set at `hi init` time |
| `artifacts.l1` | list | L1 artifact inventory |
| `artifacts.l2` | list | L2 artifact inventory with derivation links |
| `artifacts.l3` | list | L3 artifact inventory with convergence links |
| `events` | list | Append-only event log |

### Event Types

| Type | Triggered By | Key Fields |
|------|-------------|-----------|
| `created` | `hi init` | `—` |
| `l1_added` | Author adds a file to `l1/` and registers | `target_artifacts` |
| `l2_derived` | `hi promote --to l2` | `source_artifacts`, `target_artifacts`, `validation_status` |
| `l3_converged` | `hi promote --combine` | `source_artifacts`, `target_artifacts`, `validation_status` |
| `validated` | `hi validate` | `target_artifacts`, `outcome`, `warnings` |
| `test_run` | `hi test` | `outcome` (summary), `result_file` |
