# Quickstart: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03

This quickstart walks through the full lifecycle for a new `diabetes-screening` skill using the 6 framework agent skills. Each step shows what the skill does, what human review is expected, and what `hi` CLI command the skill invokes.

---

## Prerequisites

```bash
# Install the hi CLI (end users)
uv tool install hi

# Or for development
git clone ... && cd reason-skills-2
uv sync
export PATH="$PATH:$(pwd)/bin"  # or use: uv run hi

# Optional (for binary file ingest)
brew install poppler      # provides pdftotext (PDF text extraction)
brew install pandoc       # Word/Excel text extraction
```

---

## Step 0: Initialize the topic

```bash
hi init diabetes-screening \
  --title "Diabetes Screening" \
  --author "Clinical Informatics Team"
```

Creates `topics/diabetes-screening/` with `TOPIC.md`, `structured/`, `computable/`, `process/` (`plans/`, `contracts/`, `checklists/`, `fixtures/`, `research.md`, `conflicts.md`). Also ensures `sources/` exists at the repo root and registers the topic in `tracking.yaml`.

---

## Step 1: Discovery — find your sources

Invoke the `hi-discovery` skill in **plan** mode. The agent generates a research plan for the domain.

**Agent invokes**: `hi-discovery plan`  
**Reads**: `tracking.yaml` (domain: `diabetes`)  
**Writes**: `topics/diabetes-screening/process/plans/discovery-plan.yaml` (machine-readable source list) and `topics/diabetes-screening/process/plans/discovery-readout.md` (narrative)

**Human review**: Open `topics/diabetes-screening/process/plans/discovery-plan.yaml`. Edit the YAML to remove sources you don't need or add any you know of. Review `discovery-readout.md` for domain advice and expansion suggestions, then proceed.

Then invoke **verify** mode to validate the plan before ingesting:

**Agent invokes**: `hi validate --plan topics/diabetes-screening/process/plans/discovery-plan.yaml`  
**Reads**: `topics/diabetes-screening/process/plans/discovery-plan.yaml`  
**Writes**: nothing (read-only)

---

## Step 2: Ingest — register your raw sources

You've downloaded `ada-care-2024.pdf`. `hi-ingest` reads `discovery-plan.yaml` directly to determine which sources to acquire.

**Agent invokes**: `hi ingest implement <file>`  
**Reads**: file path argument  
**Writes**:
- `sources/ada-guidelines-2024.md` (copy of the source file)
- `tracking.yaml` root `sources[]` entry with SHA-256 checksum

```bash
# Ingest a source file
hi ingest implement ~/Downloads/ada-care-2024.pdf

# Verify all sources are registered correctly
hi ingest verify
# ✓ ada-guidelines-2024            OK
```

---

## Step 3: Extract — derive structured artifacts

**Agent invokes**: `hi-extract plan`  
**Reads**: `sources/`  
**Writes**: `topics/diabetes-screening/process/plans/extract-plan.md`

**Human review**: Open `topics/diabetes-screening/process/plans/extract-plan.md`. The YAML front matter lists proposed structured artifact names and which source file each derives from. Edit names, add artifacts, remove proposals that aren't needed. The prose explains the clinical intent of each.

Then implement:

**Agent invokes**: `hi-extract implement`  
**Reads**: `topics/diabetes-screening/process/plans/extract-plan.md`  
**Executes**: `hi promote derive` for each artifact  
**Writes**: `topics/diabetes-screening/structured/screening-criteria.yaml`, `topics/diabetes-screening/structured/risk-factors.yaml`

Verify:

**Agent invokes**: `hi-extract verify`  
**Executes**: `hi validate diabetes-screening structured <each artifact>`

```
✓ Validating diabetes-screening/structured/screening-criteria...
VALID — topics/diabetes-screening/structured/screening-criteria.yaml
✓ Validating diabetes-screening/structured/risk-factors...
VALID (with 2 optional field warning(s))
```

---

## Step 4: Formalize — converge to computable artifact

**Agent invokes**: `hi-formalize plan`  
**Reads**: `topics/diabetes-screening/structured/`  
**Writes**: `topics/diabetes-screening/process/plans/formalize-plan.md`

**Human review**: Edit `topics/diabetes-screening/process/plans/formalize-plan.md`. The YAML front matter lists which structured artifacts to combine and which sections to include (pathways, measures, value_sets, etc.). Edit the outline prose to guide the LLM on what the computable artifact should emphasize.

Then implement:

**Agent invokes**: `hi-formalize implement`  
**Reads**: `topics/diabetes-screening/process/plans/formalize-plan.md`  
**Executes**: `hi promote combine diabetes-screening screening-criteria risk-factors diabetes-screening-computable`  
**Writes**: `topics/diabetes-screening/computable/diabetes-screening-computable.yaml`

Verify:

**Agent invokes**: `hi-formalize verify`  
**Checks**: Required fields + FHIR-compatible section completeness

---

## Step 5: Check status at any time

```bash
# Where is this topic in its lifecycle?
hi status diabetes-screening
```

> **Note**: `hi status progress`, `hi status next-steps`, and `hi status check-changes` are planned features (tasks T030-T032) and not yet implemented. The current `hi status <topic>` provides basic lifecycle info (stage, artifact counts, last event).

---

## Step 6: Handle a changed source file

Six months later, ADA publishes updated guidelines. You download the new PDF.

```bash
hi ingest verify
# ✗ ada-guidelines-2024            CHANGED
#   was: e3b0c442...
#   now: 9f86d081...
```

Re-ingest the updated file:

```bash
hi ingest implement ~/Downloads/ada-care-2024-updated.pdf --force
```

Then re-extract and re-formalize affected artifacts following Steps 3–4.

---

## Re-run safety

All `plan` and `implement` modes are **safe by default**:

- If a plan already exists → warns and stops (edit it or use `--force`)
- If L2/L3 artifacts already exist → `hi promote` warns; use `--force` to regenerate
- `verify` and `check-changes` are always read-only and safe to run at any time

---

## Framework skill locations

```
skills/.curated/
  hi-discovery/SKILL.md   → invoke for literature search planning
  hi-ingest/SKILL.md      → invoke for source registration
  hi-extract/SKILL.md     → invoke for structured derivation
  hi-formalize/SKILL.md   → invoke for computable convergence
  hi-verify/SKILL.md      → invoke for on-demand artifact validation
  hi-status/SKILL.md      → invoke for progress/next-steps/change-detection
```
