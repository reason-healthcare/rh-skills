# Decision Table — Decision Table

**Clinical Question**: What recommendation-scoped triggers, local conditions, and actions form the decision logic?
**Derived From**: ada-guidelines-2024_md

## Summary

ADA 2024 screening logic starts with screening eligibility review, moves to test selection and interpretation, then branches to repeat screening, diabetes diagnosis, prediabetes referral, or pregnancy-specific criteria.

## Event Tree

```text
Event: Screening eligibility review [trigger: adult-diabetes-screening-review]
|   |-- Rule: assess-screening-eligibility
|   |   `-- Then
|   |       `-- assess-screening-eligibility Assess diabetes screening eligibility
|   |-- Rule: perform-screening-tests
|   |   |-- When: Age 35 years or older = Yes
|   |   `-- Then
|   |       `-- perform-screening-tests Perform ADA diabetes screening tests
|   |-- Rule: perform-screening-tests
|   |   |-- When: Overweight or obesity present = Yes
|   |   |-- When: At least one additional diabetes risk factor present = Yes
|   |   `-- Then
|   |       `-- perform-screening-tests Perform ADA diabetes screening tests
|   |-- Rule: apply-pregnancy-specific-criteria
|   |   |-- When: Pregnancy present = Yes
|   |   `-- Then
|   |       `-- apply-pregnancy-specific-criteria Apply gestational diabetes screening criteria
|   `-- Rule: defer-screening-until-criteria-met
|       |-- When: Age 35 years or older = No
|       |-- When: Overweight or obesity present = No
|       |-- When: At least one additional diabetes risk factor present = No
|       |-- When: Pregnancy present = No
|       `-- Then
|           `-- defer-screening-until-criteria-met Defer routine screening until criteria are met
Event: Screening result review [trigger: diabetes-screening-result-review]
    |-- Rule: diagnose-diabetes
    |   |-- When: Diabetes diagnostic threshold met = Yes
    |   `-- Then
    |       `-- diagnose-diabetes Diagnose diabetes
    |-- Rule: diagnose-prediabetes
    |   |-- When: Diabetes diagnostic threshold met = No
    |   |-- When: Prediabetes threshold met = Yes
    |   `-- Then
    |       |-- diagnose-prediabetes Diagnose prediabetes
    |       `-- refer-lifestyle-intervention Refer to intensive behavioral lifestyle intervention
    `-- Rule: repeat-screening-three-years
        |-- When: Screening result normal = Yes
        `-- Then
            `-- repeat-screening-three-years Repeat screening at least every 3 years
```

## Features And Data Elements

| Condition | Data Element | Type | Description |
|---|---|---|---|
| age-35-or-older Age 35 years or older | de-age Age | demographic | Adult age at time of screening eligibility review. |
| overweight-or-obese Overweight or obesity present | de-bmi-risk BMI-based weight category | finding | BMI threshold meeting overweight or obesity criteria, including lower threshold for Asian American adults. |
| has-additional-risk-factor At least one additional diabetes risk factor present | de-risk-factors Additional diabetes risk factors | finding | Family history, race-ethnicity risk, cardiovascular disease, hypertension, lipid abnormalities, PCOS, inactivity, or insulin resistance syndromes. |
| pregnant Pregnancy present | de-pregnancy Pregnancy status | finding | Determine whether gestational diabetes criteria should be used instead of the adult asymptomatic screening pathway. |
| diabetes-threshold-met Diabetes diagnostic threshold met | de-screening-result Screening laboratory result | laboratory | Fasting plasma glucose, A1C, 2-hour OGTT glucose, or random glucose result with symptoms. |
| prediabetes-threshold-met Prediabetes threshold met | de-prediabetes-threshold Prediabetes threshold result | laboratory | Result pattern consistent with ADA prediabetes thresholds when diabetes thresholds are not met. |
| normal-screen Screening result normal | de-normal-screen Normal screening result | laboratory | Screening result that does not meet ADA diabetes or prediabetes thresholds. |

## Rules

| Event Pattern | age-35-or-older Age 35 years or older | overweight-or-obese Overweight or obesity present | has-additional-risk-factor At least one additional diabetes risk factor present | pregnant Pregnancy present | diabetes-threshold-met Diabetes diagnostic threshold met | prediabetes-threshold-met Prediabetes threshold met | normal-screen Screening result normal | Actions |
|---|---|---|---|---|---|---|---|---|
| eligibility-review Screening eligibility review | - | - | - | - | - | - | - | assess-screening-eligibility Assess diabetes screening eligibility |
| eligibility-review Screening eligibility review | Yes | - | - | - | - | - | - | perform-screening-tests Perform ADA diabetes screening tests |
| eligibility-review Screening eligibility review | - | Yes | Yes | - | - | - | - | perform-screening-tests Perform ADA diabetes screening tests |
| eligibility-review Screening eligibility review | - | - | - | Yes | - | - | - | apply-pregnancy-specific-criteria Apply gestational diabetes screening criteria |
| eligibility-review Screening eligibility review | No | No | No | No | - | - | - | defer-screening-until-criteria-met Defer routine screening until criteria are met |
| result-review Screening result review | - | - | - | - | Yes | - | - | diagnose-diabetes Diagnose diabetes |
| result-review Screening result review | - | - | - | - | No | Yes | - | diagnose-prediabetes Diagnose prediabetes, refer-lifestyle-intervention Refer to intensive behavioral lifestyle intervention |
| result-review Screening result review | - | - | - | - | - | - | Yes | repeat-screening-three-years Repeat screening at least every 3 years |

## Evidence Traceability

- **claim-001**: Screening should begin at age 35 for all adults.
  - Source: ada-guidelines-2024_md, Locator: For all patients, testing should begin at age 35.
- **claim-002**: Adults of any age with overweight or obesity and one or more additional risk factors should be considered for testing.
  - Source: ada-guidelines-2024_md, Locator: Testing should be considered in adults of any age who are overweight or obese and who have one or more additional risk factors.
- **claim-003**: Diabetes diagnostic thresholds include fasting plasma glucose >=126 mg/dL, 2-hour OGTT glucose >=200 mg/dL, A1C >=6.5 percent, or random glucose >=200 mg/dL with classic symptoms.
  - Source: ada-guidelines-2024_md, Locator: Diagnostic Criteria section.
- **claim-004**: Prediabetes thresholds include fasting plasma glucose 100-125 mg/dL, 2-hour OGTT glucose 140-199 mg/dL, or A1C 5.7-6.4 percent.
  - Source: ada-guidelines-2024_md, Locator: Prediabetes Criteria section.
- **claim-005**: Prediabetes should trigger referral to an intensive behavioral lifestyle intervention program and normal results should trigger repeat screening at least every 3 years.
  - Source: ada-guidelines-2024_md, Locator: Prediabetes recommendation and screening interval statement.
- **claim-006**: Pregnant women use different criteria with gestational diabetes screening at 24-28 weeks.
  - Source: ada-guidelines-2024_md, Locator: High-Risk Populations section: pregnant women use different criteria.
