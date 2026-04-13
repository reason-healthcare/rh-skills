# Skill Authoring Guide

This guide explains how to author a new RH skills framework skill using the canonical
template at `skills/_template/`.

---

## Design Principles

### 1. Progressive Disclosure

Anthropic's Agent Skills standard defines three disclosure levels:

| Level | Location | Loaded When |
|-------|----------|-------------|
| **1** — Metadata | YAML frontmatter in `SKILL.md` | Always (injected into system prompt at startup) |
| **2** — Instructions | SKILL.md body | When the agent determines the skill is relevant |
| **3** — Reference | `reference.md`, `examples/` | On demand, only when SKILL.md instructs the agent to read them |

**Keep SKILL.md lean.** Move large schemas, detailed field definitions, and worked
examples into Level 3 companion files. The agent will load them only when needed,
keeping the context window efficient.

### 2. Determinism / Reasoning Separation

> **All deterministic work in `rh-skills` CLI commands. All reasoning in SKILL.md.**

| Lives in `rh-skills` CLI | Lives in SKILL.md |
|-------------------|-------------------|
| File I/O | Clinical reasoning |
| SHA-256 checksums | Artifact naming decisions |
| YAML reads/writes | Evidence synthesis |
| Schema validation | Source prioritisation |
| tracking.yaml updates | Convergence strategy |
| Exit code handling | Human review prompts |

Never compute checksums, write YAML, or touch the filesystem from a skill.
Invoke `rh-skills` commands for everything deterministic.

### 3. Plan → Human Review → Implement

The `plan` and `implement` modes are always separate steps with a mandatory
human review gate between them. Never combine them without explicit user
confirmation. The plan artifact (Markdown + YAML front matter) is the contract
between agent reasoning and machine execution.

### 4. Fail Loudly and Early

Check all prerequisites before doing any work. A partial `implement` that fails
midway is worse than a clean early exit with a clear error message.

---

## File Structure

```
skills/.curated/<skill-name>/
├── SKILL.md          ← Copy from _template/SKILL.md; fill in the blanks
├── reference.md      ← Copy from _template/reference.md; fill in schemas
└── examples/
    ├── plan.md       ← Copy from _template/examples/plan.md; add worked example
    └── output.md     ← Copy from _template/examples/output.md; add worked example
```

---

## Step-by-Step Authoring

### Step 1: Copy the template

```bash
cp -r skills/_template skills/.curated/<skill-name>
```

### Step 2: Fill in SKILL.md frontmatter

Update every field in the YAML frontmatter:

| Field | Guidance |
|-------|----------|
| `name` | Must match directory name exactly (e.g., `rh-inf-extract`) |
| `description` | One sentence + `Modes: plan · implement · verify` |
| `version` | Start at `"1.0.0"`; bump minor for new fields, major for breaking changes |
| `modes` | Remove modes not supported by this skill (e.g., `rh-inf-status` has no `plan`) |
| `context_files` | List only files that exist in the skill directory |
| `lifecycle_stage` | One of: `l1-discovery`, `l2-semi-structured`, `l3-computable` |
| `reads_from` | All files/sources the skill reads |
| `writes_via_cli` | All `rh-skills` CLI commands that modify state |
| `metadata.author` | Your name or team |
| `metadata.source` | Canonical path: `skills/.curated/<skill-name>/SKILL.md` |

### Step 3: Write the Overview

2–4 sentences explaining:
- What clinical/informatics problem this skill solves
- What level it operates at (L1→L2 or L2→L3 or standalone)
- How it fits in the plan → implement → verify workflow

### Step 4: Fill in each Mode section

For each mode (`plan`, `implement`, `verify`):

1. **Steps** — numbered, concrete, ordered. Each step should be actionable.
2. **Plan artifact format** — copy the template format and fill in skill-specific
   YAML front matter fields. Cross-reference `reference.md` for the schema.
3. **Events** — list every tracking.yaml event written by this mode.
4. **Must NOT** — list prohibited actions to prevent common mistakes.

### Step 5: Fill in reference.md

Document all schemas with full field tables:
- Plan artifact YAML front matter schema (required + optional fields)
- L2 and/or L3 output artifact schema
- Validation rules for each artifact type
- Clinical standards applicable to this skill
- Domain glossary

### Step 6: Write worked examples

In `examples/plan.md`:
- A realistic plan artifact for a concrete topic (e.g., `diabetes-screening`)
- Realistic clinical content (not Lorem Ipsum)
- Annotations explaining key authoring decisions

In `examples/output.md`:
- A realistic output artifact (L2 YAML and/or L3 YAML)
- The corresponding `tracking.yaml` entries that `rh-skills` CLI would write

### Step 7: Test the skill

```bash
rh-skills test <topic> <skill-name>
```

Runs the skill against fixtures in `topics/<topic>/process/fixtures/` and
writes results to `topics/<topic>/process/fixtures/results/`.

---

## Mode Reference

### Supported Mode Combinations

| Skill | plan | implement | verify |
|-------|------|-----------|--------|
| `rh-inf-discovery` | ✓ | ✓ | — |
| `rh-inf-ingest` | ✓ | ✓ | ✓ |
| `rh-inf-extract` | ✓ | ✓ | ✓ |
| `rh-inf-formalize` | ✓ | ✓ | ✓ |
| `rh-inf-verify` | — | — | ✓ |
| `rh-inf-status` | — | — | — (custom modes) |

### Standard `plan` Mode Contract (FR-018)

- **Writes to**: `topics/<topic>/process/plans/<skill-name>-plan.md`
- **Format**: Markdown with YAML front matter
- **Must NOT** create or modify any other file
- **Must warn and exit** if plan already exists and `--force` not set
- **Event**: append `<skill-name>_planned` to topic events

### Standard `implement` Mode Contract (FR-019, FR-020)

- **Reads from**: the plan artifact's YAML front matter
- **Must fail** if plan does not exist
- **Must delegate** all file I/O to `rh-skills` CLI commands
- **Must stop** on first CLI command failure
- **Events**: written by the `rh-skills` CLI commands invoked

### Standard `verify` Mode Contract (FR-022)

- **Must NOT** create, modify, or delete any file
- **Must NOT** write to tracking.yaml
- **Exit 0** if all required checks pass (warnings OK)
- **Exit 1** if any required check fails
- Safe to rerun at any time

---

## Error Message Templates

Use these verbatim for consistency across all skills:

```
# Missing prerequisite
Error: tracking.yaml not found. Run `rh-skills init <topic>` first.
Error: Topic '<topic>' not found. Run `rh-skills list` to see available topics.

# Plan missing (implement mode)
Error: No plan found at topics/<topic>/process/plans/<skill-name>-plan.md.
Run `<skill-name> plan <topic>` first, review the plan, then re-run implement.

# Plan field missing
Error: Plan missing required field '<field>'. Edit the plan and re-run.

# Plan exists (no --force)
Warning: Plan already exists at topics/<topic>/process/plans/<skill-name>-plan.md.
Pass --force to overwrite, or run `<skill-name> implement <topic>` to use the existing plan.

# CLI command failure
Error: `rh-skills <command>` failed (exit <code>): <stderr>. Stopping.

# Artifact exists (no --force)
Warning: <artifact> already exists. Pass --force to overwrite.
```

---

## Checklist for New Skills

Before marking a skill implementation complete:

- [ ] `SKILL.md` frontmatter complete with all required fields
- [ ] `description` includes mode list: `Modes: plan · implement · verify`
- [ ] `context_files` lists only files that exist
- [ ] All placeholder comments (`<!-- ... -->`) removed or replaced
- [ ] All `<skill-name>` tokens replaced with actual skill name
- [ ] Pre-execution checks are complete and use standard error messages
- [ ] All three modes documented with concrete numbered steps
- [ ] Plan artifact format documented with skill-specific YAML fields
- [ ] Events table complete for each mode
- [ ] `reference.md` schemas filled in with actual field names and constraints
- [ ] `examples/plan.md` contains realistic clinical content (not Lorem Ipsum)
- [ ] `examples/output.md` contains realistic output artifacts
- [ ] Skill tested with `rh-skills test <topic> <skill-name>`
- [ ] Skill spec (003–008) acceptance scenarios pass
