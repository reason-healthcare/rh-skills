# Review Mode Example — Input

**Mode**: review
**Topic**: lipid-management
**Library**: LipidManagementLogicDraft

## Task

Review the CQL library below using `rh-cql` in `review` mode. Apply the full
authoring rubric (10 areas), high-risk pattern catalog (7 categories), and
packaging rubric. Produce a structured review report.

## CQL Library to Review

```cql
library LipidManagementLogicDraft version '1.0.0'

using FHIR version '4.0.1'

// No FHIRHelpers included — intentional omission

valueset "Hyperlipidemia": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.103.12.1001'
// Note: no version pinning

valueset "LDL Tests": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.198.12.1016'

parameter "Measurement Period" Interval<DateTime>

context Patient

define "Conditions":
  [Condition] C

define "LDL Obs":
  [Observation] O
    where O.status = 'final'

define "Has Condition":
  exists "Conditions"

define "LDL Value":
  (First("LDL Obs")).value

define "Numerator":
  "LDL Value" < 100
```

## Issues planted (for the reviewer to find)

1. **BLOCKING** — Unpinned valueset versions
2. **ADVISORY** — Overly broad retrieve `[Condition]` without valueset filter
3. **INFO** — No top-level documentation comment block
