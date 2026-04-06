---
name: "hi-status"
description: >
  Lifecycle status skill for the HI evidence pipeline.
  Runs hi status to show project-level state and per-topic recommendations
  derived from tracking.yaml. Read-only. Modes: show · check-changes.
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

`hi-status` shows the current state of the research portfolio and recommends
next steps for each topic. It reads `tracking.yaml` and checks for
`discovery-plan.yaml` to surface context-aware recommendations. It never
modifies any file.

---

## Guiding Principles

- **Read-only.** `hi-status` never writes files, modifies `tracking.yaml`, or
  creates artifacts.
- **Deterministic operations via `hi` CLI.** All status queries and
  recommendations are produced by `hi status` CLI commands. The agent presents
  output and may add one sentence of context per topic; it does not invent
  recommendations beyond what the CLI produces.
- **Always close the loop.** Every response ends with the standard output
  contract: status block + "**What would you like to do next?**" + lettered
  options.

---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is optional. If a topic name is supplied, show status for that
topic only. If empty, show the full portfolio.

---

## Pre-Execution Checks

1. Confirm `tracking.yaml` exists. If absent, advise `hi init <topic>`.
2. If a topic name was supplied, validate it before use:
   - Topic names must be kebab-case (lowercase letters, digits, hyphens only).
   - Reject and report an error if the name contains spaces, uppercase letters,
     slashes, or other special characters.
3. If validated topic name was supplied, confirm it exists in `tracking.yaml`.
   If not found, suggest `hi init <topic>`.

---

## Mode: `verify`

All operations are read-only. No files are written.

**Step 1 — Run status**

```sh
hi status              # full portfolio
hi status show <topic> # single topic (when topic supplied)
```

Present the CLI output as-is. For each topic, you may add one sentence of
context if the recommended next step is non-obvious (e.g., explain what
`hi-extract` does if the user may not know).

**Step 2 — Offer check-changes (when sources exist)**

If any topic shows sources registered, offer drift detection as an option:

```sh
hi status check-changes <topic>
```

Do not run this automatically — offer it as a lettered option.

---

## Output Contract

After every response, emit a status block and friendly user prompt as the
**last thing** in the response. No text after the user prompt.

```
▸ hi-status  <topic or "portfolio">
  Topics:   <N>
  Sources:  <N>
  Next:     <primary recommended action>
```

**What would you like to do next?**

<lettered options derived from the CLI output, each on a new line>

You can also ask for `hi-status` at any time.

---

## Error Handling

| Condition | Action |
|-----------|--------|
| `tracking.yaml` missing | Advise `hi init <topic>`; exit |
| Topic not found | Advise `hi init <topic>`; exit |
| `hi status` exits non-zero | Surface the error verbatim; do not continue |

