---
# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED FRONTMATTER — loaded into system prompt at startup (Level 1 disclosure)
# Keep name and description tight — this is all the agent sees until it triggers
# the skill. Name must match the directory name exactly.
# ─────────────────────────────────────────────────────────────────────────────
name: "<skill-name>"
description: >
  <One sentence: what this skill does and for whom.>
  Modes: plan · implement · verify.
compatibility: "rh-skills >= 0.1.0"
context_files:
  - reference.md        # full schemas, field definitions, validation rules
  - examples/plan.md    # worked example of a plan artifact
  - examples/output.md  # worked example of an output artifact
metadata:
  author: "<Author Name or Team>"
  version: "1.0.0"
  source: "skills/.curated/<skill-name>/SKILL.md"
  lifecycle_stage: "<l1-discovery | l2-semi-structured | l3-computable>"
  reads_from:
    - tracking.yaml
    - "<e.g., topics/<name>/process/plans/<skill-name>-plan.md>"
  writes_via_cli:
    - "<e.g., rh-skills promote derive>"
    - "<e.g., rh-skills validate>"
---

# <Skill Name>

<!-- ─────────────────────────────────────────────────────────────────────────
  LEVEL 2 DISCLOSURE — full instructions, loaded when skill is triggered.
  Keep this file focused. Move large schemas and examples to companion files
  (reference.md, examples/) and link to them. Claude will load them on demand.
  ───────────────────────────────────────────────────────────────────────── -->

## Overview

<!-- 3–5 sentences. Answer: what does this skill do, why does it exist in the
     L1→L2→L3 lifecycle, and what distinguishes this stage from adjacent ones. -->

This skill handles the **<stage>** stage of the HI lifecycle, transforming
<describe input artifacts and their level> into <describe output artifacts and
their level>. It follows the plan → implement → verify pattern: the agent reasons
about the clinical domain in `plan` mode, executes deterministic work via `rh-skills`
CLI commands in `implement` mode, and performs non-destructive validation in
`verify` mode.

**Guiding principle**: All file I/O, checksums, YAML writes, and schema
validation are delegated to `rh-skills` CLI commands. All clinical reasoning, artifact
naming decisions, and evidence synthesis happen in this skill.

---

## User Input

```text
$ARGUMENTS
```

You **MUST** inspect `$ARGUMENTS` before proceeding. The first word is the
**mode** (`plan`, `implement`, or `verify`). Additional arguments follow:

| Mode | Arguments | Example |
|------|-----------|---------|
| `plan` | `<topic>` | `plan diabetes-screening` |
| `implement` | `<topic>` | `implement diabetes-screening` |
| `verify` | `<topic>` | `verify diabetes-screening` |

If `$ARGUMENTS` is empty or the mode is unrecognized, print the table above and
exit without doing any work.

---

## Pre-Execution Checks

Run these checks **before** dispatching to a mode. Exit immediately with a clear
error if any required check fails — do not attempt partial work.

**1. Verify `tracking.yaml` exists:**
```
rh-skills list
```
If the command returns "No tracking.yaml found", exit:
> `Error: tracking.yaml not found at repo root. Run \`rh-skills init <topic>\` first.`

**2. Verify topic exists:**
Confirm the topic name from `$ARGUMENTS` appears in `rh-skills list` output. If not:
> `Error: Topic '<topic>' not found. Run \`rh-skills list\` to see available topics.`

**3. For `implement` mode only — verify plan artifact exists:**
Check that `topics/<topic>/process/plans/<skill-name>-plan.md` exists.
If not:
> `Error: No plan found at topics/<topic>/process/plans/<skill-name>-plan.md.`
> `Run \`<skill-name> plan <topic>\` first, review the plan, then re-run implement.`

**4. For `implement` mode only — parse plan YAML front matter:**
Read the plan artifact. If YAML front matter is missing or any required field
is absent (see [reference.md](reference.md) §Plan Schema), exit:
> `Error: Plan is missing required field '<field>'. Edit the plan and re-run.`

---

## Mode: `plan`

**Goal**: Reason about the topic and produce a plan artifact for human review.
No files are created or modified other than the plan artifact itself.

### Steps

1. **Read context** — Run `rh-skills status show <topic>` and review current lifecycle
   state. Note artifact counts and last event. Also read:
   <!-- List the exact files/outputs the agent should read for this skill -->
   - `tracking.yaml` sources list (to understand what raw material is available)
   - Any prior plan artifact (warn if one already exists; do not overwrite unless
     `--force` flag is in `$ARGUMENTS`)

2. **Reason** — Based on the context:
   <!-- Replace with skill-specific reasoning instructions -->
   - <Describe what the agent should analyse and what decisions it must make>
   - <Be specific: which sources to prioritise, what naming conventions to use,
     how many artifacts to propose, what evidence quality criteria to apply>
   - <Refer to [reference.md](reference.md) for detailed guidance on artifact
     types, required fields, and clinical standards>

3. **Write plan artifact** — Write to
   `topics/<topic>/process/plans/<skill-name>-plan.md` using the format below.
   If the file already exists and `--force` is not set, warn and exit without
   overwriting.

4. **Summarise** — After writing, print a summary of what was planned and
   instruct the user:
   > "Review `topics/<topic>/process/plans/<skill-name>-plan.md`. Edit the
   > YAML front matter to adjust the plan, then run:
   > `<skill-name> implement <topic>`"

### Plan Artifact Format

> For full schema and field definitions, see [reference.md](reference.md)
> §Plan Schema. For a worked example, see [examples/plan.md](examples/plan.md).

```markdown
---
topic: <topic-name>
plan_type: <skill-name>
version: "1.0"
created: "<ISO-8601 timestamp>"
# ── Skill-specific fields ─────────────────────────────────────────────────
# <field>: <value>   # required — <description>
# <field>: <value>   # optional — <description>
# ─────────────────────────────────────────────────────────────────────────
---

## <Title> Plan — <Topic>

### Clinical Rationale
<Why these artifacts are needed; what clinical question they answer.>

### Evidence Summary
<Key sources, their quality, and how they inform the plan.>

### Proposed Artifacts
<Human-readable description of each planned artifact; one paragraph each.>

### Open Questions
<List any ambiguities for the reviewer to resolve before implementing.>
```

### Events Appended
- `<skill-name>_planned` — appended to `topics[<topic>].events[]` in tracking.yaml

---

## Mode: `implement`

**Goal**: Execute the plan by invoking `rh-skills` CLI commands. Never write files
directly — all I/O must go through `rh-skills` commands.

### Steps

1. **Read and validate plan** — Parse YAML front matter from the plan artifact.
   Confirm all required fields are present (see Pre-Execution Checks above).

2. **Execute** — For each item in the plan:
   <!-- Replace with the exact rh-skills CLI commands this skill calls -->
   ```
   rh-skills <command> <topic> <args>
   ```
   - Report progress after each command: `✓ Created <name>` or `✗ Failed: <reason>`
   - If any `rh-skills` command exits non-zero, **stop immediately** and report the
     error. Do not continue with remaining items.

3. **Validate outputs** — After all items are created, run:
   ```
   rh-skills validate <topic> <artifact>
   ```
   for each produced artifact. Report required-field errors (blocking) and
   advisory warnings separately.

4. **Report** — Print a completion summary:
   > "Implemented <N> artifacts. Validation: <N> passed, <N> warnings, <N> errors."
   > "Next step: run `<skill-name> verify <topic>` to confirm all outputs are valid."

### Must NOT
- Write any file directly (all I/O via `rh-skills` CLI)
- Silently skip failed `rh-skills` commands
- Continue past a blocking error

### Events Appended (by the `rh-skills` CLI commands invoked)
<!-- List the events that the rh-skills commands will write to tracking.yaml -->
- `<event-name>` — appended by `rh-skills <command>` for each item

---

## Mode: `verify`

**Goal**: Non-destructive validation. **MUST NOT** create, modify, or delete any
file or tracking.yaml entry. Safe to run at any time.

### Steps

1. **List expected outputs** — Read the plan artifact (if present) to know what
   artifacts should exist. If no plan exists, verify all artifacts currently
   present in `topics/<topic>/<structured|computable>/`.

2. **Validate each artifact:**
   ```
   rh-skills validate <topic> <artifact-name>
   ```
   Collect results.

3. **Check referential integrity:**
   <!-- Skill-specific integrity checks; remove or adapt -->
   - Confirm that `derived_from` sources in each structured artifact's
     tracking entry still exist in `sources[]`
   - Confirm that `converged_from` entries in computable artifacts still exist
     in `structured[]`

4. **Report per artifact:**
   ```
   ✓ screening-criteria       — all required fields present
   ✗ risk-factors             — missing required field: 'value_set_url'
   ⚠ diagnostic-thresholds   — optional field 'evidence_grade' not set
   ```

5. **Exit behaviour**: Exit 0 if all required checks pass (warnings are OK).
   Exit 1 if any required check fails.

### Must NOT
- Create, modify, or delete any file
- Write to tracking.yaml
- Re-run `implement` steps

---

## Error Messages

Use these standard templates for consistency across all RH skills.

| Situation | Message |
|-----------|---------|
| No tracking.yaml | `Error: tracking.yaml not found. Run \`rh-skills init <topic>\` first.` |
| Unknown topic | `Error: Topic '<topic>' not found. Run \`rh-skills list\` to see available topics.` |
| No plan (implement) | `Error: No plan found. Run \`<skill-name> plan <topic>\` first.` |
| Missing plan field | `Error: Plan missing required field '<field>'. Edit the plan and re-run.` |
| Plan exists (no --force) | `Warning: Plan already exists. Pass --force to overwrite, or run implement to execute the existing plan.` |
| rh-skills command failure | `Error: \`rh-skills <command>\` failed (exit <code>): <stderr>. Stopping.` |
| Artifact exists (no --force) | `Warning: <artifact> already exists. Pass --force to overwrite.` |

---

## Companion Files

Load these on demand — do not load all of them upfront.

| File | When to load |
|------|--------------|
| [`reference.md`](reference.md) | When you need full schema definitions, field constraints, or validation rules |
| [`examples/plan.md`](examples/plan.md) | When writing a plan artifact and you need a worked example |
| [`examples/output.md`](examples/output.md) | When implementing and you need to understand expected output structure |

---

## Guiding Principles

> **All deterministic work in `rh-skills` CLI commands. All reasoning in this SKILL.md.**

1. **Delegate everything deterministic** — file I/O, checksums, YAML reads/writes,
   schema validation, tracking updates — to `rh-skills` CLI. Never replicate this logic
   in the skill.
2. **Fail loudly and early** — run all prerequisite checks before doing any work.
   A partial implement is worse than no implement.
3. **Human review gate** — `plan` and `implement` are always separate steps.
   Never combine them without explicit user confirmation.
4. **Idempotent verify** — `verify` is always safe to re-run. Never skip it
   before proceeding to the next lifecycle stage.
5. **Respect the front matter** — the plan artifact is the contract between
   human review and machine execution. Never invent items not in the plan.
6. **Prefer structured output** — use tables and `✓/✗/⚠` symbols in status
   reports; prefer prose only in clinical rationale sections.
