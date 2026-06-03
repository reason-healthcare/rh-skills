# Pattern: Condition Reuse in Decision Tables

## Problem: Duplicated Conditions

A common anti-pattern when extracting decision tables is **defining the same clinical criterion multiple times** with slightly different names.

**Example anti-pattern**:
```yaml
conditions:
  - id: diabetes-dx
    description: "Patient has diabetes diagnosis"
  - id: diabetes-confirmed
    description: "Diabetes diagnosis has been confirmed"
  - id: has-diabetes
    description: "Patient diagnosed with diabetes"
```

These are semantically identical but defined separately, leading to:
- **Inconsistent references** in rules
- **Harder maintenance** (updating logic requires changing multiple definitions)
- **Validation failures** (different IDs for same concept)

---

## Solution: Extract Once, Reference Multiple Times

**Core principle**: Define each unique clinical criterion **once**, then reference the same condition ID in all rules that need it.

---

## Synthetic Example: Diabetes Screening Protocol

### Source Guideline (Simplified)

> **Diabetes Screening Recommendations**
>
> 1. **Initial screening**: Adults age ≥35 should be screened for prediabetes and diabetes.
> 2. **High-risk screening**: Adults with BMI ≥25 and one or more risk factors should be screened regardless of age.
> 3. **Screening test selection**: When screening eligible patient, order HbA1c or fasting plasma glucose.
> 4. **Positive screen**: When HbA1c ≥5.7% or FPG ≥100 mg/dL, repeat testing to confirm diagnosis.
> 5. **Follow-up**: When diagnosis confirmed, initiate lifestyle counseling.
> 6. **Repeat screening**: When screening negative and patient has no risk factors, rescreen in 3 years.
> 7. **Intensified screening**: When screening negative and patient has risk factors, rescreen annually.

---

## Condition Extraction: Identify Shared Criteria

**Step 1**: List all clinical criteria from guideline:

1. "Adults age ≥35"
2. "BMI ≥25"
3. "One or more risk factors"
4. "Screening eligible patient"
5. "HbA1c ≥5.7%"
6. "FPG ≥100 mg/dL"
7. "Diagnosis confirmed"
8. "No risk factors"
9. "Has risk factors"

**Step 2**: Identify semantic overlap:

- "One or more risk factors" (item 3) = "Has risk factors" (item 9) → **SAME CONDITION**
- "No risk factors" (item 8) = NOT "has risk factors" → **INVERSE OF SAME CONDITION**
- "Screening eligible patient" (item 4) appears in multiple rules → **PRE-REQUISITE CONDITION**

**Step 3**: Define conditions once, with clear IDs:

```yaml
conditions:
  # PRE-REQUISITE (appears in multiple rules)
  - id: screening-eligible
    description: "Patient meets age or risk-based screening criteria"
    cql_stub: "define ScreeningEligible: AgeOver35 or HighRiskCriteria"
  
  # SHARED CRITERIA (reused across rules)
  - id: age-over-35
    description: "Patient age ≥35 years"
    cql_stub: "define AgeOver35: AgeInYears() >= 35"
  
  - id: bmi-over-25
    description: "BMI ≥25 kg/m²"
    cql_stub: "define BMIOver25: BMI() >= 25 'kg/m2'"
  
  - id: has-risk-factors
    description: "One or more diabetes risk factors present (hypertension, dyslipidemia, family history, gestational diabetes, PCOS)"
    cql_stub: "define HasRiskFactors: ..."
  
  - id: elevated-hba1c
    description: "HbA1c ≥5.7%"
    cql_stub: "define ElevatedHbA1c: MostRecentHbA1c() >= 5.7 '%'"
  
  - id: elevated-fpg
    description: "Fasting plasma glucose ≥100 mg/dL"
    cql_stub: "define ElevatedFPG: MostRecentFPG() >= 100 'mg/dL'"
  
  - id: diagnosis-confirmed
    description: "Repeat testing confirms diabetes or prediabetes diagnosis"
    cql_stub: "define DiagnosisConfirmed: ..."
```

---

## Rule Extraction: Reference Shared Conditions

### Event 1: Eligibility Determination

**Multiple rules reference SAME conditions**:

```yaml
rules:
  # Rule 1: Age-based screening
  - id: r1
    event: e1-determine-eligibility
    when: {age-over-35: Yes}  # ← Condition referenced
    action: mark-screening-eligible
    rationale: "ADA 2024, Recommendation 2.1"
  
  # Rule 2: Risk-based screening
  - id: r2
    event: e1-determine-eligibility
    when:
      bmi-over-25: true     # ← Condition referenced
      has-risk-factors: true  # ← Condition referenced
    action: mark-screening-eligible
    rationale: "ADA 2024, Recommendation 2.2"
```

**Notice**: Both rules reference different combinations of shared conditions.

---

### Event 2: Test Selection

**Pre-requisite condition appears in ALL rules for this event**:

```yaml
  # Rule 3: Order HbA1c
  - id: r3
    event: e2-select-test
    when: {screening-eligible: Yes}  # ← Pre-requisite (same condition in r3, r4)
    action: order-hba1c
    rationale: "ADA 2024, Recommendation 2.3a"
  
  # Rule 4: Order FPG (alternative)
  - id: r4
    event: e2-select-test
    when: {screening-eligible: Yes}  # ← Pre-requisite (reused)
    action: order-fpg
    rationale: "ADA 2024, Recommendation 2.3b"
```

**Notice**: `screening-eligible` is a **layered condition** — it serves as a pre-requisite for the event (both rules need it).

---

### Event 3: Positive Screen Follow-Up

**Branch conditions (OR logic modeled as separate rules)**:

```yaml
  # Rule 5a: Positive HbA1c
  - id: r5a
    event: e3-positive-screen
    when:
      screening-eligible: true  # ← Pre-requisite (reused again)
      elevated-hba1c: true      # ← Branch criterion
    action: repeat-testing
    rationale: "ADA 2024, Recommendation 2.4"
  
  # Rule 5b: Positive FPG
  - id: r5b
    event: e3-positive-screen
    when:
      screening-eligible: true  # ← Pre-requisite (reused)
      elevated-fpg: true        # ← Branch criterion (alternative)
    action: repeat-testing
    rationale: "ADA 2024, Recommendation 2.4"
```

**Notice**: `screening-eligible` appears in **both** rules (pre-requisite), while `elevated-hba1c` vs `elevated-fpg` differentiate the branches.

---

### Event 4: Confirmed Diagnosis Actions

```yaml
  # Rule 6: Initiate counseling
  - id: r6
    event: e4-diagnosis-confirmed
    when: {diagnosis-confirmed: Yes}
    action: initiate-lifestyle-counseling
    rationale: "ADA 2024, Recommendation 2.5"
```

---

### Event 5: Repeat Screening Schedule

**Inverse condition usage (has-risk-factors vs NOT has-risk-factors)**:

```yaml
  # Rule 7: No risk factors → 3-year rescreen
  - id: r7
    event: e5-repeat-screening
    when:
      screening-eligible: true
      has-risk-factors: false  # ← Inverse of has-risk-factors
    action: schedule-3yr-rescreen
    rationale: "ADA 2024, Recommendation 2.6a"
  
  # Rule 8: Has risk factors → annual rescreen
  - id: r8
    event: e5-repeat-screening
    when:
      screening-eligible: true
      has-risk-factors: true   # ← Same condition, different value
    action: schedule-annual-rescreen
    rationale: "ADA 2024, Recommendation 2.6b"
```

**Notice**: `has-risk-factors` appears in **three different rules** (r2, r7, r8), with different boolean values. This is correct reuse.

---

## Condition Usage Summary

| Condition ID | Used in Rules | Role |
|--------------|---------------|------|
| `age-over-35` | r1 | Eligibility criterion |
| `bmi-over-25` | r2 | Eligibility criterion |
| `has-risk-factors` | r2, r7, r8 | Eligibility + follow-up criterion |
| `screening-eligible` | r3, r4, r5a, r5b, r7, r8 | **PRE-REQUISITE** (layered condition) |
| `elevated-hba1c` | r5a | Positive screen detection |
| `elevated-fpg` | r5b | Positive screen detection |
| `diagnosis-confirmed` | r6 | Diagnosis trigger |

**Key insight**: `screening-eligible` is used in **6 rules** (pre-requisite for test selection, positive screen handling, and repeat screening). Defining it once ensures consistency.

---

## Anti-Pattern Examples

### ❌ Bad: Duplicating Pre-Requisite Conditions

```yaml
conditions:
  - id: eligible-for-testing
    description: "Patient qualifies for screening test"
  - id: screening-criteria-met
    description: "Patient meets screening eligibility"
  - id: can-order-test
    description: "Patient is eligible for diabetes screening"

rules:
  - id: r3
    when: {eligible-for-testing: Yes}
    action: order-hba1c
  - id: r4
    when: {screening-criteria-met: Yes}  # ← Different ID, same meaning
    action: order-fpg
```

**Problem**: Same concept, different IDs → inconsistency, validation errors

---

### ❌ Bad: Duplicating Risk Factor Checks

```yaml
conditions:
  - id: risk-factor-present
    description: "Patient has diabetes risk factors"
  - id: diabetes-risk
    description: "Risk factors for diabetes present"
  - id: at-risk-for-diabetes
    description: "One or more risk factors present"
```

**Problem**: Three conditions for the same clinical criterion

---

### ✅ Good: Single Definition, Multiple References

```yaml
conditions:
  - id: has-risk-factors
    description: "One or more diabetes risk factors present (hypertension, dyslipidemia, family history, gestational diabetes, PCOS)"

rules:
  - id: r2
    when: {has-risk-factors: Yes}
    action: mark-screening-eligible
  - id: r7
    when: {has-risk-factors: No}
    action: schedule-3yr-rescreen
  - id: r8
    when: {has-risk-factors: Yes}
    action: schedule-annual-rescreen
```

**Benefit**: Single source of truth, consistent references

---

## Extraction Workflow

### Step 1: Extract all clinical criteria from guideline

List every "when", "if", "with", "having" clause.

### Step 2: Normalize descriptions

Identify semantically identical criteria with different wording:
- "diabetes diagnosis" = "diagnosed with diabetes" = "has diabetes"
- "risk factors present" = "one or more risk factors" = "at-risk"

### Step 3: Define each unique criterion once

Choose the clearest, most clinical description.

### Step 4: Map rules to conditions

When writing rules, reference existing condition IDs. If a new criterion appears, check if it's semantically similar to an existing condition before defining a new one.

### Step 5: Validate condition coverage

Run validator to check for:
- **Orphaned conditions** (defined but never used)
- **Duplicate descriptions** (identical text, different IDs)

---

## Validation Checks

The decision-table validator (Phase 5) detects reuse issues:

**Check 1: Orphaned conditions**
```
⚠ decision-table: condition 'eligible-for-testing' defined but never used in rules
```

**Check 2: Duplicate descriptions**
```
⚠ decision-table: conditions 'risk-factor-present' and 'diabetes-risk' have 
   identical descriptions (possible duplication?)
```

---

## Summary

**Condition reuse pattern**:

1. **Extract all criteria** from guideline narrative
2. **Identify overlaps** (same concept, different wording)
3. **Define once** with clear ID and description
4. **Reference multiple times** in rules with same condition ID
5. **Use boolean values** (true/false) for inverse conditions instead of defining separate conditions
6. **Track usage** to detect orphaned or duplicate conditions

**Result**: Consistent, maintainable decision logic with single source of truth for each clinical criterion.
