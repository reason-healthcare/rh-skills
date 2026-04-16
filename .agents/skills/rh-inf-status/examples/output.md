# rh-inf-status — Example Sessions

---

## Example 1: Portfolio summary (no arguments)

**User:**
> What's the status of my research project?

**Agent:**

Running portfolio status.

```sh
rh-skills status
```

```
Research Portfolio
  Topics:   2
  Sources:  9

juvenile-diabetes-onset — Juvenile Diabetes Onset Screening
  Stage:  Ingest · discovery plan ✓
  Sources:     9
  Next steps:
    - Extract structured criteria from ingested sources (L2): rh-inf-extract plan juvenile-diabetes-onset
    - Check whether any source files have changed since ingest: rh-skills status check-changes juvenile-diabetes-onset
    - Re-run ingest if sources need refreshing: rh-inf-ingest implement juvenile-diabetes-onset

hypertension-young-adults — Hypertension in Young Adults
  Stage:  Discovery
  Next steps:
    - Start source discovery for this topic: rh-inf-discovery session hypertension-young-adults
    - Ingest sources if you already have a discovery plan: rh-inf-ingest plan hypertension-young-adults
    - Full pipeline summary: rh-skills status progress hypertension-young-adults
```

Two topics in the portfolio. `juvenile-diabetes-onset` has 9 sources ingested
and a discovery plan — the recommended next step is extraction. `hypertension-young-adults`
is still in the Discovery stage with no sources yet.

---

## Example 2: Single-topic detail

**User:**
> Show me the details for juvenile-diabetes-onset

**Agent:**

```sh
rh-skills status show juvenile-diabetes-onset
```

```
Topic:    juvenile-diabetes-onset
Title:    Juvenile Diabetes Onset Screening
Author:   Research Team
Created:  2026-04-05T18:00:00Z
Stage:    l1-discovery

Artifacts:
  L1 (sources):          9
  L2 (structured):       0
  L3 (computable):       0

Last event: source_annotated (2026-04-05T18:22:11Z)

Next steps:
  - Extract structured criteria from ingested sources (L2): rh-inf-extract plan juvenile-diabetes-onset
  - Check whether any source files have changed since ingest: rh-skills status check-changes juvenile-diabetes-onset
  - Re-run ingest if sources need refreshing: rh-inf-ingest implement juvenile-diabetes-onset
```

Nine sources have been ingested and annotated. No structured (L2) artifacts
exist yet — extraction is the natural next step.

---

## Example 3: Source drift detection

**User:**
> Check whether any sources have changed since ingest

**Agent:**

```sh
rh-skills status check-changes juvenile-diabetes-onset
```

```
Topic: juvenile-diabetes-onset

Source Change Report:
--------------------------------------------------
  ✓ ada-guidelines-2024       OK
  ✓ cms-ecqm-cms122           OK
  ✗ cochrane-meta-analysis    CHANGED
    was: 8f3a21c4d7e6b9f1...
    now: 2b9e44a7f18c3d05...
    Potentially stale L2 artifacts: criteria-cochrane
    Potentially stale L3 artifacts: diabetes-pathway
  ✓ uspstf-diabetes-grade-b   OK

Next steps:
  - Re-ingest or refresh the affected sources for this topic: rh-inf-ingest implement juvenile-diabetes-onset
  - Re-check drift after source refresh: rh-skills status check-changes juvenile-diabetes-onset
  - Review topic status before continuing: rh-skills status show juvenile-diabetes-onset
```

One source has changed: `cochrane-meta-analysis`. The L2 artifact
`criteria-cochrane` was derived from it and is now potentially stale. Re-ingest
the changed source before running extraction to ensure consistency.
