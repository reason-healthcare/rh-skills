# Author Mode Example — Input

**Mode**: author
**Topic**: lipid-management
**Library**: LipidManagementLogic

## Task

Author a CQL library for LDL-C monitoring in patients with hyperlipidemia, based
on the structured artifact below. The library should identify:

1. Patients with a hyperlipidemia diagnosis
2. Patients who have had an LDL-C lab result in the measurement period
3. Patients whose most recent LDL-C is controlled (< 100 mg/dL)

Use `rh-inf-cql` in `author` mode. After authoring, validate with
`rh-skills cql validate lipid-management LipidManagementLogic`.

## Structured Artifact (input)

```yaml
# topics/lipid-management/structured/ldl-monitoring.yaml
artifact_type: measure
name: ldl-monitoring
display: LDL-C Monitoring for Hyperlipidemia
description: >
  Proportion of patients with hyperlipidemia who have a controlled LDL-C
  (<100 mg/dL) result in the measurement period.
fhir_version: "4.0.1"
valuesets:
  - name: Hyperlipidemia
    url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.103.12.1001"
    version: "20230101"
  - name: LDL Cholesterol Tests
    url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.198.12.1016"
    version: "20230101"
population:
  initial_population: >
    Patients 18 years and older with an active hyperlipidemia diagnosis
  denominator: >
    Initial Population
  numerator: >
    Patients with an LDL-C result < 100 mg/dL in the measurement period
```

## Requirements

- Follow the CQL style guide from SKILL.md
- Pass all 10 authoring rubric areas
- Valueset versions must be pinned
- Include a top-level documentation comment block
- Separate retrieve logic from derived logic
