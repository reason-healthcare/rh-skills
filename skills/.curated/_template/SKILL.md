---
name: "<skill-name>"
description: "<One-line description of what this skill does. Include modes: plan | implement | verify>"
compatibility: "hi-skills-framework >= 0.1.0"
metadata:
  author: "<Author Name or Team>"
  source: "skills/.curated/<skill-name>/SKILL.md"
---

# <Skill Name>

## Overview

<2–4 sentence description of the skill's clinical / informatics purpose and how it fits in the L1→L2→L3 lifecycle.>

## User Input

```text
$ARGUMENTS
```

The first positional argument is the **mode**: `plan`, `implement`, or `verify`. Additional arguments vary by mode (e.g., `<topic>`, `<file>`). You MUST check `$ARGUMENTS` before proceeding and dispatch to the correct mode section below.

## Pre-Execution Checks

Before dispatching by mode:

1. Verify the topic exists in `tracking.yaml` (run `hi list` and confirm the topic name is present).
2. Verify `tracking.yaml` is present at the repo root — if not, exit with a clear error message.
3. If mode is `implement`, verify the corresponding plan artifact exists at `topics/<topic>/process/plans/<skill-name>-plan.md`. If missing, exit with:
   ```
   Error: No plan found. Run `<skill-name> plan` first.
   ```

## Modes

### `plan`

**Goal**: Reason about the topic and produce a plan artifact for human review. No other files are created or modified.

**Steps**:
1. <Describe what context the agent should read — tracking.yaml fields, source files, prior artifacts, etc.>
2. <Describe the reasoning process — what the agent should produce based on that context.>
3. Write the plan to `topics/<topic>/process/plans/<skill-name>-plan.md` with YAML front matter (see format below). If the file already exists and `--force` is not set, warn and exit without overwriting.
4. Summarize what was written and prompt the user to review and edit the plan before running `implement`.

**Plan artifact format**:
```markdown
---
topic: <topic-name>
plan_type: <skill-name>
version: "1.0"
created: "<ISO-8601 timestamp>"
# <skill-specific fields here — see spec for required front matter fields>
---

## <Title>
<Human-readable prose for review — clinical rationale, evidence summary, etc.>
```

**Event to append** (via `hi` CLI or direct tracking.yaml write): `<skill-name>_planned`

---

### `implement`

**Goal**: Execute the plan by invoking `hi` CLI commands. All file I/O MUST go through `hi` CLI commands — never write files directly.

**Pre-check**: Read `topics/<topic>/process/plans/<skill-name>-plan.md`. Parse the YAML front matter. If any required field is missing, exit with a clear error before doing any work.

**Steps**:
1. <For each item in the plan's front matter array, call the appropriate `hi` command.>
2. <Example: `hi promote derive <topic> <name>` for each artifact in an extract plan.>
3. Report progress after each step. If any `hi` command fails, stop and report the error — do not continue with remaining steps.

**Event appended by**: The `hi` CLI commands invoked (e.g., `hi promote derive` appends `structured_derived`).

**Must NOT**:
- Write any files directly (all I/O via `hi` CLI)
- Proceed if the plan artifact does not exist
- Silently skip failed `hi` commands

---

### `verify`

**Goal**: Non-destructive validation only. MUST NOT create, modify, or delete any file or tracking.yaml entry.

**Steps**:
1. <Describe what to validate — schema conformance, referential integrity, required fields, etc.>
2. For each artifact, call `hi validate <topic> <artifact>` and collect the result.
3. Print a per-artifact report:
   - `✓ <name>` — all checks passed
   - `✗ <name>: <reason>` — required field missing or schema error
   - `⚠ <name>: <reason>` — advisory warning (optional field missing)
4. Exit 0 if all required checks pass; exit 1 if any required check fails.

**Must NOT**: Modify any file or tracking.yaml entry. This mode is always safe to re-run.

---

## Guiding Principles

> **All deterministic work in `hi` CLI commands. All reasoning in this SKILL.md.**

- Never compute checksums, read/write YAML directly, or perform file I/O outside of `hi` CLI commands.
- Always read the plan artifact's YAML front matter — never ask the user to repeat information already in the plan.
- Fail loudly and early: check prerequisites before doing any work.
- Be concise in output: prefer structured lists over prose for status reporting.
