# Pattern: Condition Reuse in Decision Tables

## Core Principle

Define each distinct clinical criterion once in `conditions[]`, then reference
that same condition ID from every rule that needs it.

This avoids:
- duplicated condition definitions
- inconsistent rule references
- unnecessary divergence between similar recommendation branches

---

## Synthetic Example

### Source Idea

The guideline says:
- adults age 35 and older should be screened
- adults with BMI 25 or greater plus risk factors should be screened
- eligible patients may receive HbA1c or fasting plasma glucose screening
- positive screens should be repeated to confirm diagnosis
- confirmed diagnosis should trigger lifestyle counseling
- negative screens should lead to different rescreening intervals depending on risk factors

### Extracted Condition Set

```yaml
conditions:
  - id: screening-eligible
    label: Screening eligibility established
    values: [Yes, No]
  - id: age-35-or-older
    label: Age 35 years or older
    values: [Yes, No]
  - id: bmi-25-or-greater
    label: BMI 25 kg per square meter or greater
    values: [Yes, No]
  - id: has-risk-factors
    label: Diabetes risk factors present
    values: [Yes, No]
  - id: elevated-hba1c
    label: HbA1c at or above the positive-screen threshold
    values: [Yes, No]
  - id: elevated-fpg
    label: Fasting plasma glucose at or above the positive-screen threshold
    values: [Yes, No]
  - id: diagnosis-confirmed
    label: Repeat testing confirms diagnosis
    values: [Yes, No]
```

### Extracted Decision Table

```yaml
id: diabetes-screening-protocol
artifact_type: decision-table
clinical_question: "How should diabetes screening eligibility, testing, and follow-up be handled?"
sections:
  events:
    - id: determine-eligibility
      label: Determine screening eligibility
    - id: select-screening-test
      label: Select screening test
    - id: evaluate-positive-screen
      label: Evaluate positive screening result
    - id: confirmed-diagnosis-review
      label: Confirmed diagnosis review
    - id: repeat-screening-review
      label: Repeat screening review
  conditions:
    - id: screening-eligible
      label: Screening eligibility established
      values: [Yes, No]
    - id: age-35-or-older
      label: Age 35 years or older
      values: [Yes, No]
    - id: bmi-25-or-greater
      label: BMI 25 kg per square meter or greater
      values: [Yes, No]
    - id: has-risk-factors
      label: Diabetes risk factors present
      values: [Yes, No]
    - id: elevated-hba1c
      label: HbA1c at or above the positive-screen threshold
      values: [Yes, No]
    - id: elevated-fpg
      label: Fasting plasma glucose at or above the positive-screen threshold
      values: [Yes, No]
    - id: diagnosis-confirmed
      label: Repeat testing confirms diagnosis
      values: [Yes, No]
  actions:
    - id: mark-screening-eligible
      label: Mark patient as screening eligible
    - id: order-hba1c
      label: Order HbA1c
    - id: order-fpg
      label: Order fasting plasma glucose
    - id: repeat-testing
      label: Repeat testing to confirm diagnosis
    - id: initiate-lifestyle-counseling
      label: Initiate lifestyle counseling
    - id: schedule-3-year-rescreen
      label: Schedule rescreening in 3 years
    - id: schedule-annual-rescreen
      label: Schedule annual rescreening
  rules:
    - id: rule-age-based-eligibility
      event: determine-eligibility
      when: {age-35-or-older: Yes}
      then: [mark-screening-eligible]
    - id: rule-risk-based-eligibility
      event: determine-eligibility
      when:
        bmi-25-or-greater: Yes
        has-risk-factors: Yes
      then: [mark-screening-eligible]
    - id: rule-order-hba1c
      event: select-screening-test
      when: {screening-eligible: Yes}
      then: [order-hba1c]
    - id: rule-order-fpg
      event: select-screening-test
      when: {screening-eligible: Yes}
      then: [order-fpg]
    - id: rule-repeat-after-hba1c
      event: evaluate-positive-screen
      when:
        screening-eligible: Yes
        elevated-hba1c: Yes
      then: [repeat-testing]
    - id: rule-repeat-after-fpg
      event: evaluate-positive-screen
      when:
        screening-eligible: Yes
        elevated-fpg: Yes
      then: [repeat-testing]
    - id: rule-initiate-counseling
      event: confirmed-diagnosis-review
      when: {diagnosis-confirmed: Yes}
      then: [initiate-lifestyle-counseling]
    - id: rule-3-year-rescreen
      event: repeat-screening-review
      when:
        screening-eligible: Yes
        has-risk-factors: No
      then: [schedule-3-year-rescreen]
    - id: rule-annual-rescreen
      event: repeat-screening-review
      when:
        screening-eligible: Yes
        has-risk-factors: Yes
      then: [schedule-annual-rescreen]
```

---

## What This Example Shows

- `screening-eligible` is defined once and reused across multiple later rules.
- `has-risk-factors` is also defined once and reused with different values
  (`Yes` and `No`) in different recommendation branches.
- Alternative recommendations at the same workflow moment are modeled as
  separate rules, not collapsed into one broad rule.
- Rules always reference action IDs through `then: [...]`.

---

## Anti-Pattern to Avoid

Do not do this:

```yaml
conditions:
  - id: eligible-for-testing
    label: Patient qualifies for screening test
  - id: screening-criteria-met
    label: Patient meets screening eligibility
  - id: can-order-test
    label: Patient is eligible for diabetes screening
```

Those three conditions are the same idea written three times. Extract one
condition, give it a stable ID, and reuse it everywhere.
