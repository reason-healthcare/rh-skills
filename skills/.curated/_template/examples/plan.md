# Example: Plan Artifact — `<skill-name> plan`

<!-- This file is LEVEL 3 disclosure — loaded by the agent on demand when
     writing a plan artifact and needing a worked example to follow. -->

This is a complete worked example of a plan artifact produced by
`<skill-name> plan diabetes-screening`. Use it as a structural reference —
the clinical content here is illustrative only.

---

## File Location

```
topics/diabetes-screening/process/plans/<skill-name>-plan.md
```

---

## Full Example

```markdown
---
topic: diabetes-screening
plan_type: <skill-name>
version: "1.0"
created: "2026-04-04T14:00:00Z"

# ── Skill-specific fields (replace with actual schema) ────────────────────
# Example: for hi-extract, this would be the artifacts_to_derive[] array
items:
  - name: screening-criteria
    source_file: ada-guidelines-2024
    description: "Discrete criteria for identifying adults who should be screened for type 2 diabetes"

  - name: risk-factors
    source_file: ada-guidelines-2024
    description: "Enumerated risk factor definitions with clinical thresholds (BMI ≥ 25, age ≥ 35, etc.)"

  - name: diagnostic-thresholds
    source_file: ada-guidelines-2024
    description: "Laboratory thresholds for diagnostic confirmation (HbA1c, FPG, OGTT)"
# ─────────────────────────────────────────────────────────────────────────
---

## <Skill Name> Plan — Diabetes Screening

### Clinical Rationale

Type 2 diabetes affects approximately 37 million Americans, with an estimated
one-third undiagnosed. The ADA Standards of Medical Care in Diabetes (2024)
provides the primary evidence base for discrete, computable screening criteria.
Three structured artifacts are needed to capture the full clinical picture:
screening eligibility criteria, modifiable and non-modifiable risk factors, and
laboratory diagnostic thresholds.

### Evidence Summary

| Source | Grade | Key Contribution |
|--------|-------|-----------------|
| ADA Standards of Care 2024 (ada-guidelines-2024) | A | Primary evidence base; Section 2 covers screening |
| USPSTF Diabetes Screening Recommendation (2021) | A | Confirms 35-year age threshold for BMI ≥ 25 |

### Proposed Artifacts

**screening-criteria** — Computable eligibility criteria for identifying
adults who should be offered diabetes screening. Will encode the age,
BMI, and risk-factor thresholds from ADA Section 2.2.

**risk-factors** — Enumerated risk factors with clinical definitions and
thresholds. Will include both modifiable (BMI, physical activity, diet) and
non-modifiable factors (family history, race/ethnicity, gestational diabetes
history).

**diagnostic-thresholds** — Laboratory test thresholds for diagnosing
prediabetes and diabetes: HbA1c ≥ 6.5%, FPG ≥ 126 mg/dL, or 2-hr OGTT
≥ 200 mg/dL. Will include both diagnostic and prediabetes ranges.

### Open Questions

1. Should the `screening-criteria` artifact include high-risk group criteria
   (PCOS, HIV, sleep apnea) from ADA Table 2.3, or scope only to primary
   risk factors?
2. The CDC statistics source (cdc-statistics.pdf) has not yet been ingested.
   Should `plan` wait for it, or proceed with ADA evidence only?
```

---

## Key Points for Plan Authors

- **YAML front matter drives `implement`** — the prose below the `---` is for
  human review only. `implement` reads only the YAML front matter.
- **Required front matter fields** — see [reference.md](../reference.md) §Plan Schema.
- **One artifact per plan item** — each entry in the items array produces one
  CLI invocation during `implement`.
- **Open Questions** — list any ambiguities so the reviewer can resolve them
  before running `implement`. If a question cannot be resolved, do not include
  the affected item in the front matter.
- **Evidence grade** — use A/B/C/D grades from the GRADE methodology (see
  [reference.md](../reference.md) §Evidence Grading).
