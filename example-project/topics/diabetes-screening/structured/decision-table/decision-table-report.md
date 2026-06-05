# Decision Table — Diabetes Screening Decision Table

**Clinical Question**: When should an adult receive diabetes screening?
**Derived From**: ada-guidelines-2024

## Summary

Screening is recommended for adults age 35 and older, and earlier for adults with a diabetes risk factor.

## Rules

| Event Pattern | age-35-or-older Age 35 or older | has-risk-factor Has a diabetes risk factor | Actions |
|---|---|---|---|
| screening-review-started Screening review started | True | - | recommend-fasting-glucose Recommend fasting plasma glucose, recommend-a1c Recommend hemoglobin A1C |
| screening-review-started Screening review started | - | True | recommend-fasting-glucose Recommend fasting plasma glucose, recommend-a1c Recommend hemoglobin A1C |
| follow-up-review-due Follow-up review due | - | - | - | recommend-follow-up Recommend follow-up |

## Evidence Traceability

- **age-based-screening**: Adults age 35 and older should be screened.
  - Source: ada-guidelines-2024, Locator: screening age threshold
- **risk-based-screening**: Adults with a diabetes risk factor should also be screened.
  - Source: ada-guidelines-2024, Locator: risk-factor guidance
