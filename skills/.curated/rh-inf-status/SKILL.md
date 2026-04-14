---
name: "rh-inf-status"
description: >
  Lifecycle status skill for the HI evidence pipeline.
  Runs rh-skills status to show project-level state and per-topic recommendations
  derived from tracking.yaml. Read-only. Modes: show · check-changes.
compatibility: "rh-skills >= 0.1.0"
context_files:
  - reference.md
  - examples/output.md
metadata:
  author: "RH Skills"
  version: "1.0.0"
  source: "skills/.curated/rh-inf-status/SKILL.md"
  lifecycle_stage: "any"
  reads_from:
    - tracking.yaml
  writes_via_cli: []
---

# rh-inf-status

## Overview

`rh-inf-status` shows the current state of the research portfolio and recommends
next steps for each topic. It reads `tracking.yaml` and checks for
`discovery-plan.yaml` to surface context-aware recommendations. It never
modifies any file.

---

## Guiding Principles

- **Read-only.** `rh-inf-status` never writes files, modifies `tracking.yaml`, or
  creates artifacts.
- **Deterministic operations via `rh-skills` CLI.** All status queries and
  recommendations are produced by `rh-skills status` CLI commands. The agent presents
  output and may add one sentence of context per topic; it does not invent
  recommendations beyond what the CLI produces.
- **One status contract everywhere.** Status, portfolio, and drift output should
  all end with the same deterministic `Next steps` bullet list emitted by the
  canonical CLI surface. Do not append A/B/C-style menus.

---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is optional. If a topic name is supplied, show status for that
topic only. If empty, show the full portfolio.

---

## Pre-Execution Checks

1. Confirm `tracking.yaml` exists. If absent, advise `rh-skills init <topic>`.
2. If a topic name was supplied, validate it before use:
   - Topic names must be kebab-case (lowercase letters, digits, hyphens only).
   - Reject and report an error if the name contains spaces, uppercase letters,
     slashes, or other special characters.
3. If validated topic name was supplied, confirm it exists in `tracking.yaml`.
   If not found, suggest `rh-skills init <topic>`.

---

## Mode: `verify`

All operations are read-only. No files are written.

**Step 1 — Run status**

```sh
rh-skills status              # full portfolio
rh-skills status show <topic> # single topic (when topic supplied)
```

Present the CLI output as-is. For each topic, you may add one sentence of
context if the recommended next step is non-obvious (e.g., explain what
`rh-inf-extract` does if the user may not know).

If the user explicitly asks for drift detection or changed-source checks, run:

```sh
rh-skills status check-changes <topic>
```

---

## Output Contract

Present the canonical `rh-skills status` output as-is. If you add any context,
limit it to one brief sentence before the CLI output. Do not append a second
menu, alternate recommendations, or lettered choices after the CLI output.

```
<canonical rh-skills status output>
Next steps:
  - <deterministic action>
  - <deterministic action>
```

---

## Error Handling

| Condition | Action |
|-----------|--------|
| `tracking.yaml` missing | Advise `rh-skills init <topic>`; exit |
| Topic not found | Advise `rh-skills list` and `rh-skills init <topic>`; exit |
| `rh-skills status` exits non-zero | Surface the error verbatim; do not continue |
