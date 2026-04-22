# Example: Conflict Resolution Plan

## Topic: `diabetes-ccm`

This example shows the state of `extract-plan.yaml` before and after running
`rh-inf-resolve`.

---

### Before resolution

```yaml
topic: diabetes-ccm
plan_type: extract
status: pending-review
artifacts:
  - name: screening-decisions
    artifact_type: decision-table
    source_files:
      - sources/normalized/ada-2024-guideline.md
      - sources/normalized/uspstf-screening.md
    conflicts:
      - conflict: "ADA interval language is more explicit than USPSTF interval framing."
        resolution: ""
    reviewer_decision: pending-review
```

---

### After running `rh-inf-resolve diabetes-ccm`

The reviewer provided:

> ADA 2024 is the primary guideline. Use ADA interval language (every 3 years
> for low-risk, annually for high-risk). USPSTF framing is supplementary context.

```yaml
topic: diabetes-ccm
plan_type: extract
status: pending-review
artifacts:
  - name: screening-decisions
    artifact_type: decision-table
    source_files:
      - sources/normalized/ada-2024-guideline.md
      - sources/normalized/uspstf-screening.md
    conflicts:
      - conflict: "ADA interval language is more explicit than USPSTF interval framing."
        resolution: >-
          ADA 2024 is the primary guideline. Use ADA interval language (every 3
          years for low-risk, annually for high-risk). USPSTF framing is
          supplementary context only.
    reviewer_decision: pending-review
```

After this, `rh-skills promote conflicts diabetes-ccm` returns:

```
No open conflicts for topic 'diabetes-ccm'.
```

The topic is clear to proceed to `rh-skills promote approve`.
