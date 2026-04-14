# Data Model: `rh-inf-verify` Skill

**Phase 1 Design Artifact** | **Branch**: `007-rh-inf-verify`

---

## Entity 1: Verification Run

Represents one read-only invocation of `rh-inf-verify verify <topic>`.

**Fields**:
- `topic`: topic slug being verified
- `started_at`: report start timestamp
- `overall_status`: `ready | blocked | review-required`
- `applicable_stages`: ordered list of lifecycle stages considered
- `results[]`: list of `Stage Verification Result`

**Rules**:
- One verification run covers one topic only.
- A verification run must not write files or update tracking.
- The stage order should be stable across reruns for the same unchanged topic.

---

## Entity 2: Stage Verification Result

Represents the outcome for one lifecycle stage within the consolidated report.

**Fields**:
- `stage`: one of `discovery | ingest | extract | formalize`
- `skill_name`: stage-specific skill invoked
- `applicability`: `applicable | not-applicable | not-yet-ready | unavailable`
- `status`: `pass | fail | warning-only | not-applicable | invocation-error`
- `summary`: short reviewer-facing outcome line
- `blocking_findings[]`: blocking failures for the stage
- `advisory_findings[]`: warnings or non-blocking issues
- `next_action`: recommended reviewer action for this stage

**Rules**:
- `status` should be present for every stage result, even if the stage is not
  applicable or could not be invoked.
- `not-yet-ready` remains an applicability decision; it normalizes to the
  report status `not-applicable`.
- `blocking_findings[]` and `advisory_findings[]` must remain attributable to
  the stage that produced them.

---

## Entity 3: Consolidated Verification Report

The user-facing output returned by `rh-inf-verify`.

**Fields**:
- `topic_header`: topic identity and overall verification status
- `stage_results[]`: ordered per-stage results
- `overall_summary`: topic-level readiness statement
- `recommended_next_action`: first reviewer action to unblock progress

**Rules**:
- The report must show every applicable stage explicitly.
- Inapplicable or unavailable stages must be called out rather than omitted.
- The first failing or warning stage should be easy to locate visually.

---

## Entity 4: Stage Applicability Decision

Read-only determination of whether a stage should be verified in the current run.

**Signals**:
- topic lifecycle state from `tracking.yaml`
- existence of expected plan artifacts under `topics/<topic>/process/plans/`
- existence of expected output artifacts under `structured/` or `computable/`
- stage readiness inferred from previous lifecycle completion

**Outcomes**:
- `applicable`
- `not-yet-ready`
- `not-applicable`
- `unavailable`

---

## State Transitions

```text
verification run starts
  ├── applicable stage verify succeeds → stage status: pass or warning-only
  ├── applicable stage verify fails → stage status: fail
  ├── stage verify cannot be invoked → stage status: invocation-error
  └── stage not ready / not applicable → explicit non-pass status in report

all stage results collected
  └── overall summary rendered (ready | blocked | review-required)
```

- Verification never changes topic state.
- Verification never appends tracking events.

---

## Relationships

- One topic can have many verification runs over time.
- One verification run contains many stage verification results.
- One stage verification result maps to one lifecycle skill and one applicability
  decision.
