# Quickstart: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03

This quickstart walks through the full lifecycle for a new `diabetes-screening` skill using the 6 framework agent skills. Each step shows what the skill does, what human review is expected, and what `hi` CLI command the skill invokes.

---

## Prerequisites

```bash
# Existing framework stack
brew install yq jq curl   # or apt equivalents

# Optional (for binary file ingest)
brew install poppler      # provides pdftotext (PDF text extraction)
brew install pandoc       # Word/Excel text extraction

# Test suite
npm install               # installs bats-core

export PATH="$PATH:$(pwd)/bin"
```

---

## Step 0: Initialize the skill

```bash
hi init diabetes-screening \
  --title "Diabetes Screening" \
  --author "Clinical Informatics Team"
```

Creates `skills/diabetes-screening/` with `SKILL.md`, `tracking.yaml`, `l1/`, `l2/`, `l3/`, `fixtures/`, `plans/`.

---

## Step 1: Discovery — find your sources

Invoke the `hi-discovery` skill in **plan** mode. The agent generates a research plan for the domain.

**Agent invokes**: `hi-discovery plan`  
**Reads**: `skills/diabetes-screening/tracking.yaml` (domain: `diabetes`)  
**Writes**: `skills/diabetes-screening/plans/discovery-plan.md`

**Human review**: Open `plans/discovery-plan.md`. Edit the YAML front matter to remove sources you don't need, add any you know of. The prose body explains each source — review it, then proceed.

Then invoke **implement** mode to convert the plan into ingest tasks:

**Agent invokes**: `hi-discovery implement`  
**Reads**: `plans/discovery-plan.md`  
**Writes**: `skills/diabetes-screening/plans/ingest-plan.md`

---

## Step 2: Ingest — register your raw sources

You've downloaded `ada-care-2024.pdf`. The ingest plan lists it. Review and edit `plans/ingest-plan.md` — update file paths to match where your files actually are.

**Agent invokes**: `hi-ingest implement`  
**Reads**: `plans/ingest-plan.md`  
**Writes**:
- `skills/diabetes-screening/l1/ada-guidelines-2024.md` (text extracted from PDF)
- `tracking.yaml` `sources[]` entry with SHA-256 checksum

```bash
# Verify all sources are registered correctly
hi ingest verify diabetes-screening
# ✓ ada-guidelines-2024  OK
```

---

## Step 3: Extract — derive L2 artifacts

**Agent invokes**: `hi-extract plan`  
**Reads**: `skills/diabetes-screening/l1/`  
**Writes**: `skills/diabetes-screening/plans/extract-plan.md`

**Human review**: Open `plans/extract-plan.md`. The YAML front matter lists proposed L2 artifact names and which L1 source each derives from. Edit names, add artifacts, remove proposals that aren't needed. The prose explains the clinical intent of each.

Then implement:

**Agent invokes**: `hi-extract implement`  
**Reads**: `plans/extract-plan.md`  
**Executes**: `hi promote derive` for each artifact  
**Writes**: `skills/diabetes-screening/l2/screening-criteria.yaml`, `l2/risk-factors.yaml`

Verify:

**Agent invokes**: `hi-extract verify`  
**Executes**: `hi validate diabetes-screening l2 <each artifact>`

```
✓ screening-criteria  VALID
✓ risk-factors        VALID (2 optional field warnings)
```

---

## Step 4: Formalize — converge to L3

**Agent invokes**: `hi-formalize plan`  
**Reads**: `skills/diabetes-screening/l2/`  
**Writes**: `skills/diabetes-screening/plans/formalize-plan.md`

**Human review**: Edit `plans/formalize-plan.md`. The YAML front matter lists which L2 artifacts to combine and which L3 sections to include (pathways, measures, value_sets, etc.). Edit the outline prose to guide the LLM on what the L3 should emphasize.

Then implement:

**Agent invokes**: `hi-formalize implement`  
**Reads**: `plans/formalize-plan.md`  
**Executes**: `hi promote combine --sources screening-criteria,risk-factors --name diabetes-screening-computable`  
**Writes**: `skills/diabetes-screening/l3/diabetes-screening-computable.yaml`

Verify:

**Agent invokes**: `hi-formalize verify`  
**Checks**: Required fields + FHIR-compatible section completeness

---

## Step 5: Check status at any time

```bash
# Where is this skill in its lifecycle?
hi status progress diabetes-screening

# What should I do next?
hi status next-steps diabetes-screening

# Have any source files changed since ingest?
hi status check-changes diabetes-screening
```

---

## Step 6: Handle a changed source file

Six months later, ADA publishes updated guidelines. You download the new PDF.

```bash
hi status check-changes diabetes-screening
# ✗ CHANGED: ada-guidelines-2024
#   ⚠ Potentially stale L2: screening-criteria, risk-factors
```

Re-ingest the updated file:

```bash
# Update the ingest plan with the new file path, then:
hi ingest implement diabetes-screening --force
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
skills/_framework/
  hi-discovery/SKILL.md   → invoke for literature search planning
  hi-ingest/SKILL.md      → invoke for source registration
  hi-extract/SKILL.md     → invoke for L2 derivation
  hi-formalize/SKILL.md   → invoke for L3 convergence
  hi-verify/SKILL.md      → invoke for on-demand artifact validation
  hi-status/SKILL.md      → invoke for progress/next-steps/change-detection
```
