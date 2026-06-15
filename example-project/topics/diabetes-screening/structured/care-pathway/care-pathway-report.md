# Care Pathway — Care Pathway

**Clinical Question**: What clinical phases, transitions, and follow-up steps define the screening pathway?


## Pathway Tree

```text
Adult diabetes screening pathway
    |-- Review screening eligibility
    |   |-- Assess age, weight, and risk factors
    |   |-- Route pregnancy to gestational diabetes criteria
    |   |-- Proceed to adult screening testing
    |   `-- Defer routine screening
    `-- Interpret screening results
        |-- Diagnose diabetes
        |-- Diagnose prediabetes and refer lifestyle intervention
        `-- Repeat normal screening in at least 3 years
```

## Steps

| Step | Description | Actor | Parent |
|------|-------------|-------|--------|
| Adult diabetes screening pathway | Overall ADA 2024 pathway for adult diabetes and prediabetes screening. | clinician | - |
| Review screening eligibility | Assess age, weight status, risk factors, and pregnancy status. | clinician | adult-diabetes-screening-pathway |
| Assess age, weight, and risk factors | Perform the general eligibility review before branching to testing, pregnancy-specific criteria, or deferral. | clinician | eligibility-phase |
| Route pregnancy to gestational diabetes criteria | Use gestational diabetes screening criteria at 24-28 weeks for pregnant patients. | clinician | eligibility-phase |
| Proceed to adult screening testing | Screen when age-based or weight-risk-based ADA criteria are met. | clinician | eligibility-phase |
| Defer routine screening | Defer routine asymptomatic screening until ADA eligibility criteria are met. | clinician | eligibility-phase |
| Interpret screening results | Apply ADA diabetes and prediabetes thresholds after testing. | clinician | adult-diabetes-screening-pathway |
| Diagnose diabetes | Diagnose diabetes when a screening result meets ADA diabetes thresholds. | clinician | interpretation-phase |
| Diagnose prediabetes and refer lifestyle intervention | Identify prediabetes and refer to a DPP-modeled lifestyle intervention program. | clinician | interpretation-phase |
| Repeat normal screening in at least 3 years | Schedule repeat screening after a normal result. | clinician | interpretation-phase |

## Rule Links

| Step | Rule ID | Action Labels |
|------|---------|---------------|
| Adult diabetes screening pathway | - | - |
| Review screening eligibility | - | - |
| Assess age, weight, and risk factors | rule-assess-general-eligibility | Assess diabetes screening eligibility |
| Route pregnancy to gestational diabetes criteria | rule-route-pregnancy | Apply gestational diabetes screening criteria |
| Proceed to adult screening testing | - | Perform ADA diabetes screening tests |
| Defer routine screening | rule-defer-not-yet-eligible | Defer routine screening until criteria are met |
| Interpret screening results | - | - |
| Diagnose diabetes | rule-diagnose-diabetes | Diagnose diabetes |
| Diagnose prediabetes and refer lifestyle intervention | rule-diagnose-prediabetes | Diagnose prediabetes, Refer to intensive behavioral lifestyle intervention |
| Repeat normal screening in at least 3 years | rule-repeat-normal-screen | Repeat screening at least every 3 years |

