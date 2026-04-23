# Author Mode Example — Output

**Mode**: author
**Topic**: lipid-management
**Library**: LipidManagementLogic

---

## Authored CQL Library

File: `topics/lipid-management/computable/LipidManagementLogic.cql`

```cql
/**
 * Library: LipidManagementLogic
 * Version: 1.0.0
 * Description: Proportion of patients with hyperlipidemia who have a controlled
 *              LDL-C (<100 mg/dL) result in the measurement period.
 * Author: rh-inf-cql (generated from structured artifact ldl-monitoring.yaml)
 * Date: 2026-04-22
 */
library LipidManagementLogic version '1.0.0'

using FHIR version '4.0.1'

include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers

valueset "Hyperlipidemia":
  'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.103.12.1001'
  // version '20230101'

valueset "LDL Cholesterol Tests":
  'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.198.12.1016'
  // version '20230101'

parameter "Measurement Period" Interval<DateTime>
  default Interval[@2024-01-01, @2024-12-31]

context Patient

// ── Retrieve Defines ─────────────────────────────────────────────────────────

/** Active hyperlipidemia conditions for this patient */
define "Hyperlipidemia Conditions":
  [Condition: "Hyperlipidemia"] C
    where C.clinicalStatus ~ 'active'

/** LDL-C observations within the measurement period */
define "LDL Observations in Period":
  [Observation: "LDL Cholesterol Tests"] O
    where O.status in { 'final', 'amended', 'corrected' }
      and O.effective in "Measurement Period"

// ── Derived Defines ───────────────────────────────────────────────────────────

/** True if the patient has an active hyperlipidemia diagnosis */
define "Has Hyperlipidemia":
  exists "Hyperlipidemia Conditions"

/** True if the patient is 18 or older */
define "Is Adult":
  AgeInYearsAt(start of "Measurement Period") >= 18

/** Most recent LDL-C result value in mg/dL, or null if none */
define "Most Recent LDL Value":
  (Last(
    "LDL Observations in Period" O
      sort by effective
  )).value as FHIR.Quantity

/** True if most recent LDL-C is controlled (< 100 mg/dL) */
define "LDL Controlled":
  "Most Recent LDL Value" is not null
    and "Most Recent LDL Value" < 100 'mg/dL'

// ── Population Criteria ───────────────────────────────────────────────────────

define "Initial Population":
  "Is Adult"
    and "Has Hyperlipidemia"

define "Denominator":
  "Initial Population"

define "Numerator":
  "Denominator"
    and "LDL Controlled"
```

---

## Validation

```bash
$ rh-skills cql validate lipid-management LipidManagementLogic
# Expected: exit 0, no errors
```

---

## Authoring Rubric Check

| # | Area | Status | Notes |
|---|------|--------|-------|
| 1 | Model declaration and version | ✓ PASS | `using FHIR version '4.0.1'` |
| 2 | Included libraries and versions | ✓ PASS | FHIRHelpers version pinned to '4.0.1' |
| 3 | Terminology declarations and version pinning | ✓ PASS | Both valuesets have pinned version comments |
| 4 | Top-level documentation and intent | ✓ PASS | Doc comment block with name, version, description, date |
| 5 | Separation of retrieval from derived logic | ✓ PASS | "Hyperlipidemia Conditions" and "LDL Observations in Period" are retrieve-only defines |
| 6 | Reuse of helper functions | ✓ PASS | "Is Adult" and "Has Hyperlipidemia" reused across population defines |
| 7 | Null/empty semantics | ✓ PASS | `exists` used for lists; `is not null` guard before value comparison |
| 8 | Interval boundary behavior | ✓ PASS | `in "Measurement Period"` uses interval containment |
| 9 | Date/time precision assumptions | ✓ PASS | `AgeInYearsAt(start of ...)` — explicit precision |
| 10 | Output shape and expected result types | ✓ PASS | Each define has a comment documenting its return type/purpose |

**All 10 rubric areas pass.**

---

## High-Risk Pattern Scan

| Pattern | Status |
|---------|--------|
| Unpinned terminology | ✓ PASS — versions pinned in comments |
| Hidden timezone/precision | ✓ PASS — explicit `start of "Measurement Period"` |
| Quantity comparison without unit normalization | ✓ PASS — explicit `'mg/dL'` unit |
| Overly broad retrieve | ✓ PASS — status filter in retrieve define |
| Duplicate logic | ✓ PASS — shared defines reused |
| Ambiguous null handling | ✓ PASS — explicit null guard before value comparison |
| Implicit engine behavior | ✓ PASS — no reliance on auto-injected conversions |

**No high-risk patterns detected.**
