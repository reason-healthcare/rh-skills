# Review Mode Example — Output

**Mode**: review
**Topic**: lipid-management
**Library**: LipidManagementLogicDraft

---

# CQL Review Report: LipidManagementLogicDraft
**Reviewed**: 2026-04-22
**File**: `topics/lipid-management/computable/LipidManagementLogicDraft.cql`
**Reviewer**: rh-inf-cql (automated review)

## Summary
- BLOCKING: 2
- ADVISORY: 2
- INFO: 1

---

## Findings

### BLOCKING: Unpinned Terminology
**Area**: Rubric Area 3 — Terminology declarations and version pinning
**Evidence**:
```cql
valueset "Hyperlipidemia": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.103.12.1001'
valueset "LDL Tests": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.198.12.1016'
```
**Issue**: Neither valueset has a pinned version. If the valueset expands in a
future release, measure results will silently change. This is non-reproducible.
**Recommended fix**: Add `version` annotations:
```cql
valueset "Hyperlipidemia":
  'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.103.12.1001'
  // version '20230101'
```

---

### BLOCKING: Null Comparison Without Guard
**Area**: Rubric Area 7 — Null/empty semantics + High-risk pattern 6
**Evidence**:
```cql
define "LDL Value":
  (First("LDL Obs")).value

define "Numerator":
  "LDL Value" < 100
```
**Issue**: `First("LDL Obs")` returns null when the list is empty. Accessing
`.value` on null propagates null. Comparing null to `100` with `<` returns null
(not false) under CQL three-valued logic — this expression silently excludes
patients with no LDL result rather than explicitly returning false.
**Recommended fix**:
```cql
define "LDL Value":
  (Last(
    "LDL Obs" O sort by effective
  )).value as FHIR.Quantity

define "Numerator":
  "LDL Value" is not null
    and "LDL Value" < 100 'mg/dL'
```

---

### ADVISORY: Overly Broad Retrieve
**Area**: High-risk pattern 4 — Overly broad retrieves filtered ad hoc
**Evidence**:
```cql
define "Conditions":
  [Condition] C
```
**Issue**: This retrieves all Condition resources regardless of code, then
`Has Condition` tests existence with no code filter. The Hyperlipidemia valueset
is declared but never applied in the retrieve or filter. Clinical correctness
and query performance both suffer.
**Recommended fix**:
```cql
define "Hyperlipidemia Conditions":
  [Condition: "Hyperlipidemia"] C
    where C.clinicalStatus ~ 'active'
```

---

### ADVISORY: `First` Without Ordering
**Area**: Anti-pattern — `First` without a sort expression
**Evidence**:
```cql
define "LDL Value":
  (First("LDL Obs")).value
```
**Issue**: `First` without a `sort by` clause returns an arbitrary element
(implementation-dependent ordering). For clinical logic, the most recent
observation should be used explicitly.
**Recommended fix**: Use `Last(... sort by effective)` to get the most recent.

---

### INFO: No Documentation Comment Block
**Area**: Rubric Area 4 — Top-level documentation and intent
**Evidence**: Library header has no `/** ... */` comment block.
**Issue**: Missing author, date, description, and version context.
**Recommended fix**: Add a doc comment block above the `library` declaration:
```cql
/**
 * Library: LipidManagementLogicDraft
 * Version: 1.0.0
 * Description: ...
 * Author: ...
 * Date: 2026-04-22
 */
```

---

## Rubric Coverage

| Area | Status | Notes |
|------|--------|-------|
| 1. Model declaration and version | ✓ PASS | `using FHIR version '4.0.1'` present |
| 2. Included libraries and versions | ✓ PASS | No includes required for this library |
| 3. Terminology declarations and version pinning | ✗ FAIL | Both valuesets unpinned — BLOCKING |
| 4. Top-level documentation and intent | ✗ FAIL | No doc comment block — INFO |
| 5. Separation of retrieval from derived logic | ✗ FAIL | `[Condition]` retrieve has no valueset — ADVISORY |
| 6. Reuse of helper functions | ✓ PASS | Small library; no duplication |
| 7. Null/empty semantics | ✗ FAIL | No null guard before value comparison — BLOCKING |
| 8. Interval boundary behavior | ✓ PASS | No interval operators used |
| 9. Date/time precision assumptions | ✓ PASS | No date arithmetic present |
| 10. Output shape and expected result types | ✓ PASS | Numerator returns Boolean |

---

## High-Risk Pattern Scan

| Pattern | Status | Notes |
|---------|--------|-------|
| Unpinned terminology | ✗ FOUND | Both valuesets — BLOCKING |
| Hidden timezone/precision | ✓ PASS | No date/time operations |
| Quantity comparison without unit normalization | ✗ FOUND | `< 100` without explicit unit — BLOCKING (merged with null finding above) |
| Overly broad retrieve | ✗ FOUND | `[Condition]` without code filter — ADVISORY |
| Duplicate logic | ✓ PASS | No duplication |
| Ambiguous null handling | ✗ FOUND | `First(...).value < 100` — BLOCKING |
| Implicit engine behavior | ✓ PASS | No auto-injection reliance |

---

## Packaging

| Concern | Status | Notes |
|---------|--------|-------|
| CQL source present | ✓ | Source file exists |
| Translator options explicit | ✗ | No `cql-options` in Library — should be added |
| Library metadata consistent | ✓ | version declared in library header |
| Dependencies declared | ✓ | No external dependencies required |
