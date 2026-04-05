---
name: "hi-status"
description: >
  Lifecycle housekeeping skill for the HI evidence pipeline.
  Provides actionable progress summaries, next-step recommendations, and
  source drift detection without modifying any artifact.
  Modes: progress · next-steps · check-changes.
compatibility: "hi-skills-framework >= 0.1.0"
context_files:
  - reference.md
  - examples/output.md
metadata:
  author: "HI Skills Framework"
  version: "1.0.0"
  source: "skills/.curated/hi-status/SKILL.md"
  lifecycle_stage: "any"
  reads_from:
    - tracking.yaml
  writes_via_cli: []
---

# hi-status

## Overview

`hi-status` is the **lifecycle housekeeping** skill for the HI evidence
pipeline. Use it at any point in a research session to orient the team,
decide what to do next, or detect source drift.

| Sub-command | What it does |
|-------------|--------------|
| `progress` | Pipeline stage bar, completeness %, artifact counts |
| `next-steps` | Single recommended next action + exact `hi` command to run |
| `check-changes` | Re-checksum all registered sources; report drift and stale artifacts |

All operations are **read-only** — `hi-status` never modifies any file or
tracking entry.

---

## Guiding Principles

- **Read-only in all modes.** `hi-status` never writes files, modifies
  `tracking.yaml`, or creates artifacts. All I/O is via `hi status` CLI
  sub-commands.
- **Deterministic operations via `hi` CLI.** All status queries, checksum
  comparisons, and next-step analysis are performed by running `hi status`
  sub-commands. The agent provides reasoning and contextual guidance;
  all deterministic I/O is delegated to the CLI.
- **Single recommendation.** `next-steps` emits one action. Do not suggest
  additional steps; the CLI output is authoritative.
- **Always close the loop.** Every response ends with the standard output
  contract: status block + "**What would you like to do next?**" + lettered
  options.

---

## User Input

```text
$ARGUMENTS
```

Inspect `$ARGUMENTS` before proceeding. The first word is the **sub-command**:
`progress`, `next-steps`, or `check-changes`. The second positional argument is
`<topic>` — the kebab-case topic identifier.

| Sub-command | Example |
|-------------|---------|
| `progress` | `hi-status progress diabetes-screening` |
| `next-steps` | `hi-status next-steps diabetes-screening` |
| `check-changes` | `hi-status check-changes diabetes-screening` |

---

## Pre-Execution Checks

Before any sub-command:

1. **Confirm topic exists** — run `hi status show <topic> --json`. If exit
   code is non-zero, tell the user the topic was not found and suggest
   `hi init <topic>`.
2. **Confirm `tracking.yaml`** exists in the repo root. If absent, advise
   `hi init <topic>` to scaffold the project.

Topic names must be kebab-case. If the supplied topic contains spaces,
uppercase letters, or special characters, reject it and tell the user the
expected format (e.g., `diabetes-type-2-screening`).

---

## Mode: `verify`

> All three sub-commands are read-only verification operations.
> No files are written in any mode.

### Sub-command: `progress`

Run:
```sh
hi status progress <topic>
```

Present the output. Add brief contextual guidance based on completeness:

| Completeness | Guidance |
|---|---|
| 25% | Topic initialized only — no sources yet. Discovery planning is the first step. |
| 50% | Sources ingested. Extraction of structured criteria is next. |
| 75% | Structured artifacts present. Formalization to computable format is next. |
| 100% | All artifact levels present. Run `hi validate` to confirm quality. |

### Sub-command: `next-steps`

Run:
```sh
hi status next-steps <topic>
```

Present the single recommended action exactly as printed by the CLI.
Do not add additional suggestions. You may briefly explain *why* this is the
recommended next step (one sentence based on the current lifecycle stage).

### Sub-command: `check-changes`

Run:
```sh
hi status check-changes <topic>
```

Present the source change report as-is. For each changed or missing source,
add context:

- Which downstream structured artifacts are potentially stale (the CLI lists
  these under "Potentially stale L2 artifacts")
- Recommend running `hi-ingest implement <topic>` to re-acquire the changed
  source

On exit 0 (all unchanged): reassure the user — no re-ingest is needed.
On exit 1 (changes found): list changed sources and recommend re-ingest.

---

## Output Contract

After every response, emit a status block and friendly user prompt as the
**last thing** in the response. No text after the user prompt.

```
▸ hi-status  <topic>
  Mode:     <progress | next-steps | check-changes>
  Stage:    <lifecycle stage>
  Complete: <pct>%
  Next:     <action>
```

**What would you like to do next?**

<lettered options for next steps, each on new line>

You can also ask for `hi-status` at any time.

---

## Error Handling

| Condition | Action |
|-----------|--------|
| `tracking.yaml` missing | Advise `hi init <topic>`; exit |
| Topic not in `tracking.yaml` | Advise `hi init <topic>`; exit non-zero |
| Unknown sub-command | Print usage table; exit |
| `hi status` exits non-zero | Surface the error verbatim; do not continue |
