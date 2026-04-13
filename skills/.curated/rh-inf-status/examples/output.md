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
  Next:    rh-inf-extract plan juvenile-diabetes-onset

hypertension-young-adults — Hypertension in Young Adults
  Stage:  Discovery
  Next:    rh-inf-discovery session hypertension-young-adults
```

Two topics in the portfolio. `juvenile-diabetes-onset` has 9 sources ingested
and a discovery plan — the recommended next step is extraction. `hypertension-young-adults`
is still in the Discovery stage with no sources yet.

```
▸ rh-inf-status  portfolio
  Topics:   2
  Sources:  9
  Next:     rh-inf-extract plan juvenile-diabetes-onset
```

**What would you like to do next?**

A) Run `rh-inf-extract plan juvenile-diabetes-onset` — begin extraction
B) Run `rh-inf-discovery session hypertension-young-adults` — start source discovery for the second topic
C) Run `rh-skills status check-changes juvenile-diabetes-onset` — check for source drift before extracting

You can also ask for `rh-inf-status` at any time.

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
```

Nine sources have been ingested and annotated. No structured (L2) artifacts
exist yet — extraction is the natural next step.

```
▸ rh-inf-status  juvenile-diabetes-onset
  Stage:    Ingest (l1-discovery)
  Sources:  9
  Next:     rh-inf-extract plan juvenile-diabetes-onset
```

**What would you like to do next?**

A) Run `rh-inf-extract plan juvenile-diabetes-onset` — begin extraction
B) Run `rh-skills status check-changes juvenile-diabetes-onset` — verify sources haven't changed since ingest

You can also ask for `rh-inf-status` at any time.

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
  ✓ uspstf-diabetes-grade-b   OK

Action: Re-ingest changed sources with `rh-skills ingest implement <file>`
```

One source has changed: `cochrane-meta-analysis`. The L2 artifact
`criteria-cochrane` was derived from it and is now potentially stale. Re-ingest
the changed source before running extraction to ensure consistency.

```
▸ rh-inf-status  juvenile-diabetes-onset
  Sources:  9 (1 changed)
  Next:     rh-inf-ingest implement juvenile-diabetes-onset
```

**What would you like to do next?**

A) Re-ingest the changed source — `rh-inf-ingest implement juvenile-diabetes-onset`
B) Proceed to extraction anyway (changed source noted)
C) Run `rh-skills status` for a full portfolio overview

You can also ask for `rh-inf-status` at any time.

