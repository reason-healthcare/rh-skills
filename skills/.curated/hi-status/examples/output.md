# hi-status — Example Session

This example shows an agent using `hi-status` to orient a team during a
multi-topic project on juvenile diabetes onset.

---

## Example 1: progress

**User:**
> hi-status progress juvenile-diabetes-onset

**Agent:**

Running a progress check on the `juvenile-diabetes-onset` topic.

```sh
hi status show juvenile-diabetes-onset --json
```

Topic found. Running progress:

```sh
hi status progress juvenile-diabetes-onset
```

```
Topic:      juvenile-diabetes-onset
Title:      Juvenile Diabetes Onset Screening
Stage:      Discovery → [Ingest] → Extract → Formalize
Complete:   50%

Artifact Counts:
  L1 sources:     9
  L2 structured:  0
  L3 computable:  0

Last event: source_annotated (2026-04-05T18:22:11Z)
Total events: 14
```

Nine sources have been ingested and annotated, placing the topic at 50%
completeness. The next stage is **Extract** — generating structured criteria
from the normalized source material.

```
▸ hi-status  juvenile-diabetes-onset
  Mode:     progress
  Stage:    l1-discovery
  Complete: 50%
  Next:     hi-extract plan juvenile-diabetes-onset
```

**What would you like to do next?**

A) Run `hi-extract plan juvenile-diabetes-onset` — begin extraction
B) Run `hi-status next-steps juvenile-diabetes-onset` — get a recommendation
C) Run `hi-status check-changes juvenile-diabetes-onset` — check source drift

You can also ask for `hi-status` at any time.

---

## Example 2: next-steps

**User:**
> hi-status next-steps juvenile-diabetes-onset

**Agent:**

```sh
hi status next-steps juvenile-diabetes-onset
```

```
Topic: juvenile-diabetes-onset

Recommended next step:
  Extract structured (L2) artifacts from ingested sources

Run:
  hi-extract plan
```

Nine sources are ingested but no L2 structured artifacts exist yet. The
recommended step is to load `hi-extract` and run plan mode to begin extracting
structured eligibility criteria from the normalized source material.

```
▸ hi-status  juvenile-diabetes-onset
  Mode:     next-steps
  Stage:    l1-discovery
  Complete: 50%
  Next:     hi-extract plan juvenile-diabetes-onset
```

**What would you like to do next?**

A) Run `hi-extract plan juvenile-diabetes-onset` — begin extraction
B) Check source drift first — `hi-status check-changes juvenile-diabetes-onset`

You can also ask for `hi-status` at any time.

---

## Example 3: check-changes (drift detected)

**User:**
> hi-status check-changes juvenile-diabetes-onset

**Agent:**

```sh
hi status check-changes juvenile-diabetes-onset
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

Action: Re-ingest changed sources with `hi ingest implement <file>`
```

One source has changed on disk: `cochrane-meta-analysis`. The L2 structured
artifact `criteria-cochrane` was derived from this source and is now potentially
stale. Re-ingest the changed source to refresh it, then re-run extraction for
that artifact.

```
▸ hi-status  juvenile-diabetes-onset
  Mode:     check-changes
  Stage:    l1-discovery
  Complete: 50%
  Next:     re-ingest cochrane-meta-analysis → hi-ingest implement juvenile-diabetes-onset
```

**What would you like to do next?**

A) Re-ingest the changed source — `hi-ingest implement juvenile-diabetes-onset`
B) Skip re-ingest and proceed to extraction anyway
C) Run `hi-status progress` for a full overview

You can also ask for `hi-status` at any time.
