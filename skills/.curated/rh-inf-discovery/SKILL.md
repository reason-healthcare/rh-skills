---
# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED FRONTMATTER — Level 1 disclosure (loaded into system prompt at startup)
# ─────────────────────────────────────────────────────────────────────────────
name: "rh-inf-discovery"
description: >
  Interactive research assistant for healthcare informatics evidence discovery.
  Searches PubMed, PMC, ClinicalTrials.gov, and curated government/society
  sources to build an evidence-based discovery plan (L1 → L2 lifecycle stage).
  Modes: session · verify.
compatibility: "rh-skills >= 0.1.0"
context_files:
  - reference.md          # domain advice checklist, source taxonomies, US gov coverage
  - examples/plan.yaml    # worked example: diabetes-ccm discovery-plan.yaml (structured sources)
  - examples/readout.md   # worked example: diabetes-ccm discovery-readout.md (domain narrative)
  - examples/output.md    # worked example: session transcript excerpt
metadata:
  author: "RH Skills"
  version: "1.0.0"
  source: "skills/.curated/rh-inf-discovery/SKILL.md"
  lifecycle_stage: "l1-discovery"
  reads_from:
    - tracking.yaml
    - RESEARCH.md
    - topics/<name>/process/notes.md
  writes_via_cli:
    - "rh-skills search pubmed"
    - "rh-skills search pubmed --offline"
    - "rh-skills search pmc"
    - "rh-skills search clinicaltrials"
    - "rh-skills search pubmed --append-to-plan"
    - "rh-skills source add"
    - "rh-skills init"
    - "rh-skills validate --plan"
---

# rh-inf-discovery

<!-- ─────────────────────────────────────────────────────────────────────────
  LEVEL 2 DISCLOSURE — full instructions, loaded when skill is triggered.
  ───────────────────────────────────────────────────────────────────────── -->

## Overview

`rh-inf-discovery` is the **L1 evidence discovery** stage of the HI lifecycle. It
guides a clinical informaticist through finding, evaluating, and documenting
evidence-based source material for a healthcare informatics topic. The result is
a `discovery-plan.yaml` (structured source list, the single source of truth) and
`discovery-readout.md` (generated domain narrative) that `rh-inf-ingest` consumes
to acquire and register all sources, and that downstream skills
(`rh-inf-extract`, `rh-inf-formalize`) use to advance artifacts toward L2 and L3.

The skill acts as an **interactive research assistant** — it does not stop at a
single search pass. After each pass the agent explicitly prompts the user with
expansion suggestions and awaits direction. The plan is a **living document**
written to disk only when the user approves it.

---

## Guiding Principles

- **Discovery is pure research.** All searches are delegated to `rh-skills` CLI commands.
  All clinical reasoning, source evaluation, and research synthesis happen in
  this skill.
- **No file-system side effects.** Discovery does not download or register any
  source files — that is entirely `rh-inf-ingest`'s responsibility. The plan can be
  re-run, revised, and reviewed before any acquisition occurs.
- **Single source of truth.** `discovery-plan.yaml` is the authoritative source
  list. `discovery-readout.md` is a generated narrative derived from it and
  should never be edited directly.
- **Always close the loop.** Every response must end with a status block
  followed by a friendly user prompt and lettered next-step options. The user
  must never have to ask "what do I do next?"

---

## User Input

```text
$ARGUMENTS
```

Inspect `$ARGUMENTS` before proceeding. The first word is the **mode**
(`session` or `verify`). The second positional argument is `<topic>` — the
kebab-case topic identifier previously initialized with `rh-skills init`.

| Mode | Arguments | Example |
|------|-----------|---------|
| `session` | `<topic> [--force]` | `session diabetes-ccm` |
| `verify` | `<topic>` | `verify diabetes-ccm` |

- `--force`: overwrite existing `discovery-plan.yaml` and `discovery-readout.md` (session mode only).
- If `$ARGUMENTS` is empty or the mode is unrecognized, print this table and exit.

---

## Pre-Execution Checks

Before entering either mode, verify the topic is initialized:

```sh
rh-skills status show <topic>
```

If the topic does not exist, print a helpful error and suggest `rh-skills init <topic>`.

For **session** mode only: check whether a plan already exists:

```sh
ls topics/<topic>/process/plans/discovery-plan.yaml 2>/dev/null
```

- If it exists **and** `--force` was not passed: warn the user, offer to load it
  for continuation or start fresh with `--force`. Wait for the user's choice.
- If it exists **and** `--force` was passed: proceed, overwriting on save.
- If it does not exist: proceed normally.

---

## session Mode

The session is an **interactive research loop**. Complete all steps; prompt the
user after each major pass before proceeding.

### Step 1 — Domain Advice

Read `reference.md` → **Domain Advice Checklist**. Present domain-specific
guidance for `<topic>`, addressing all checklist items relevant to the domain:

- CMS program alignment (eCQMs, MIPS/QPP, Medicaid, CMMI models)
- SDOH relevance (Gravity Project domain taxonomy)
- Health equity considerations
- Existing quality measure landscape
- Key terminology systems likely needed (SNOMED, LOINC, ICD-10, RxNorm)
- Health economics angle (cost of care, disease burden) — required when the
  topic involves a chronic condition, preventive intervention, or CMS program

This advice is captured in the **Domain Advice** section of `discovery-readout.md`
(the generated narrative file) and guides which sources to prioritize.

Emit status block:
```
  Step:   1 — Domain Advice · Complete
  Plan:   0 sources in memory
  Next:   Step 2 — run PubMed/PMC searches
```

### Step 2 — PubMed Search

```sh
rh-skills search pubmed --query "<terms>" --max 20 --json
rh-skills search pmc   --query "<terms>" --max 20 --json
```

Choose search terms based on the topic name, clinical synonyms, and domain
advice from Step 1. Run at least one PubMed search AND one PMC search per
session.

Parse the JSON results. For each result evaluate:

- **Relevance** to the topic
- **Evidence level** (see `reference.md` Evidence Level Taxonomy)
- **Access**: PMC articles are `open`; PubMed abstracts are `open` (URL to
  abstract); full-text may require institutional access → `authenticated`

**If the search commands fail** (e.g. network/DNS error in a sandboxed
environment), retry with `--offline` to get reference links and record the
query, then continue with domain-knowledge-based source selection:

```sh
rh-skills search pubmed --offline --query "<terms>"
rh-skills search pmc    --offline --query "<terms>"
```

Mark the step as `SKIPPED (offline)` in the status block and log the
attempted queries in the plan's `notes` field so they can be re-run later.

Emit status block — use the appropriate variant:
```
  Step:   2 — PubMed/PMC Search · Complete         ← network available
  Step:   2 — PubMed/PMC Search · SKIPPED (offline) ← network unavailable
  Plan:   <N> sources in memory
  Next:   Step 3 — ClinicalTrials.gov search
```

### Step 3 — ClinicalTrials.gov Search

```sh
rh-skills search clinicaltrials --query "<terms>" --max 20 --json
```

Include active or completed trials relevant to the topic. These are `registry`
type with `evidence_level: n/a` (trials are not yet evidence until published).

**If the search command fails**, retry with `--offline`:

```sh
rh-skills search clinicaltrials --offline --query "<terms>"
```

Mark as `SKIPPED (offline)` and add a note in the plan to check
ClinicalTrials.gov manually.

Emit status block:
```
  Step:   3 — ClinicalTrials.gov Search · Complete          ← network available
  Step:   3 — ClinicalTrials.gov Search · SKIPPED (offline) ← network unavailable
  Plan:   <N> sources in memory
  Next:   Step 4 — US government sources
```

### Step 4 — US Government Healthcare Sources

For any topic with a US clinical care or population health angle, **actively
search** the following (not via `rh-skills search` — reason from your knowledge and
present URLs for the user to confirm):

| Source | Check for |
|--------|-----------|
| CMS eCQM Library / CMIT | Existing quality measures for the condition |
| QPP / MIPS | Clinician performance measures (if clinician-facing) |
| USPSTF | Preventive service grades (A/B especially) |
| Gravity Project | SDOH domain taxonomy and FHIR IGs |
| AHRQ | Evidence-based practice reports, PCORI-funded studies |
| CDC / MMWR | Surveillance data, epidemiological burden |
| HCUP / MEPS / GBD | Health economics and cost-of-care data |

See `reference.md` → **US Government Healthcare Coverage** for full URLs and
guidance.

Emit status block:
```
  Step:   4 — US Government Sources · Complete
  Plan:   <N> sources in memory
  Next:   Step 5 — medical society and journal sources
```

### Step 5 — Medical Society and Journal Sources

Identify the relevant medical societies and journals for the topic. Present
these with recommended search terms even if they require authentication:

- Include society clinical practice guidelines
- Include specialty-specific journals from `reference.md` → **Medical Journals**
- For authenticated sources, set `access: authenticated` and include `auth_note`
  with the specific login mechanism and suggested search terms

Do not attempt to download authenticated sources — flag them in the plan with
`recommended: true` where they are high-value, and include an inline access
advisory (FR-011a/FR-011b).

Emit status block:
```
  Step:   5 — Medical Society Sources · Complete
  Plan:   <N> sources in memory
  Next:   Step 6 — compile and validate source list
```

### Step 6 — Build the Living Plan

Maintain a `sources[]` list in memory throughout the session. After Steps 2–5,
compile the list applying these rules:

- **Minimum 5 sources**: if fewer than 5, search additional databases or
  source categories before presenting
- **Maximum 25 sources**: if more than 25 high-quality candidates, select the
  25 most relevant; log extras as expansion candidates
- At least one `terminology` entry (SNOMED, LOINC, ICD-10, RxNorm, etc.)
- At least one `health-economics` entry when topic involves chronic conditions,
  preventive interventions, or CMS programs
- All mandatory fields per FR-005: `name`, `type`, `rationale`, `search_terms[]`,
  `evidence_level`, `access`. Plus `url` when `access: open`.

Emit status block:
```
  Step:   6 — Source List · Complete
  Plan:   <N> sources in memory
  Next:   Step 7 — present list for approval
```

### Step 7 — Present to User

Present a formatted summary table of proposed sources:

```
| # | Name | Type | Evidence | Access | Notes |
|---|------|------|----------|--------|-------|
| 1 | ADA Standards of Care | guideline | grade-a | open | URL provided |
| 2 | NEJM article ... | pubmed-article | grade-b | authenticated | requires login |
...
```

For `access: open` sources, confirm a URL is recorded. For `access: authenticated`
sources, note the auth method. For `access: manual` sources, note what the user
must retrieve. None of these are downloaded here — all acquisition happens in
`rh-inf-ingest`.

Ask the user to approve, modify, or add/remove sources.
Incorporate feedback and loop back if needed.

Emit status block:

> ```
> ▸ rh-inf-discovery  <topic>
>   Step:   7 — Source Review
>   Plan:   <N> sources in memory
>   Next:   approve list / modify / add sources
> ```
> 
> **What would you like to do next?**
> 
> A) Approve all sources — proceed to access advisories
> B) Modify the list — add, remove, or edit sources
> C) Ask a question about a specific source
> 
> You can also ask for status `rh-inf-status` at any time.

### Step 8 — Access Advisories

For each **approved** `access: authenticated` or `access: manual` source, print
an access advisory so the user knows what to gather before running `rh-inf-ingest`:

```
⊘ <Source Name>
   Why relevant: <rationale for this topic>
   Access URL:   <url>
   Auth method:  <institutional login | free registration | society membership | library proxy>
   Search terms: <specific terms to use once authenticated>
```

For `access: manual` sources without a URL, describe where to find the artifact
and what filename convention to use when placing it in `sources/`.

Emit status block:
```
  Step:   8 — Access Advisories · Complete
  Plan:   <N> sources in memory
  Next:   Step 9 — expansion suggestions
```

### Step 9 — Research Expansion Suggestions

After the source pass, generate 3–7 **Research Expansion Suggestions**. These
are prospective adjacent areas — NOT sources already in the plan. Each must
include:

1. The adjacent topic
2. Why it is relevant to the primary topic
3. The first `rh-skills` command the user would run to explore it

Cover at minimum (when applicable):
- (a) Adjacent comorbidities or closely related conditions
- (b) Healthcare economics angle (cost, burden, cost-effectiveness)
- (c) Health equity or disparate-population angle
- (d) Implementation science gap (barriers to guideline adoption)
- (e) Data/registry gap (limited evidence or active trial inquiry)

**Do NOT add suggestions to `sources[]` automatically.** They are offered for
the user to act on.

Present the suggestions as a numbered list and explicitly offer to explore any
of them now. Example:

```
Research Expansion Suggestions:
  1. Diabetic kidney disease — comorbidity with shared CMS quality measures
     → rh-skills search pubmed --query "diabetic nephropathy CKD quality measures"
  2. Health equity in diabetes management — disparities by race/ethnicity
     → rh-skills search pubmed --query "diabetes management disparities SDOH"
  ...

Would you like to explore any of these now? Reply with the number, or proceed
to save the plan.
```

If the user selects an expansion area, loop back to Steps 2–9 for that area,
merge new findings into the living plan, then return here.

Emit status block:
```
  Step:   9 — Expansion Suggestions · Complete
  Plan:   <N> sources in memory
  Next:   explore an expansion area / save the plan
```

### Step 10 — Interactive Prompt

After presenting the plan and suggestions, emit the status block followed by
the options below. No lead-in, no preamble before the status block. Do not
pre-answer choices not yet made. Do not add guidance like "if you choose C..."
or "the next step would be...". Wait for the user's reply.

If the user wants to explore an expansion area, loop back to Steps 2–9 for that
area and merge the findings into the living plan.

Emit status block:

> ```
> ▸ rh-inf-discovery  <topic>
>   Step:   10 — Awaiting Direction
>   Plan:   <N> sources in memory
>   Next:   explore expansion / modify / save plan
> ```
> 
> **What would you like to do next?**
> 
> A) Explore expansion area — reply with the number (e.g. "explore 2")
> B) Add, remove, or modify sources
> C) Save the plan and move on to `rh-inf-ingest`
> 
> You can also ask for status `rh-inf-status` at any time.

### Step 11 — Save Checkpoint

When the user approves saving:

1. Write `topics/<topic>/process/plans/discovery-plan.yaml` — the structured
   source list (see Level 3 below for the required format)
2. Write `topics/<topic>/process/plans/discovery-readout.md` — the generated
   domain narrative (Domain Advice + Research Expansion Suggestions prose);
   add a note at the top that it is derived from `discovery-plan.yaml`
2. Create `process/notes.md` stub (create-unless-exists — do not overwrite if user has added content)
3. Update `RESEARCH.md` root portfolio row for the topic (source count, date)

After saving, emit status block:

> ```
> ▸ rh-inf-discovery  <topic>
>   Step:   11 — Save Checkpoint · Complete
>   Plan:   saved · <N> sources
>   Next:   rh-inf-discovery verify <topic>
> ```
> 
> **What would you like to do next?**
> 
> A) Run `rh-inf-discovery verify <topic>` — validate the plan before handing off
> B) Return to the session to revise sources
> 
> You can also ask for `rh-inf-status` at any time.

### Step 12 — Verify Recommendation

Remind the user that `verify` mode runs non-destructive checks on the saved
plan. Once it passes, the plan is ready to hand off to `rh-inf-ingest`, which
handles all source acquisition (downloading open sources, registering manual
files) in a single dedicated step.

---

## Mode: `verify`

**Read-only** — no file writes, no `tracking.yaml` modifications.

```sh
rh-skills validate --plan topics/<topic>/process/plans/discovery-plan.yaml
```

Report the output verbatim. Exit with the same code as `rh-skills validate --plan`.

On exit 0, before emitting the status block, emit:

> Verification passed! Your discovery plan is well-formed and ready for `rh-inf-ingest`.
> 
> ```
> ▸ rh-inf-discovery  <topic>
>   Mode:    verify
>   Result:  PASS
>   Next:    rh-inf-ingest plan <topic>
> ```
> 
> **What would you like to do next?**
> 
> A) Run `rh-inf-ingest plan <topic>` — begin source acquisition
> B) Return to the discovery session to revise sources
> 
> You can also ask for status `rh-inf-status` at any time.


On exit 1, emit:

> Verification failed. Please address the following issues in `discovery-plan.yaml`:
> 
> ```
> ▸ rh-inf-discovery  <topic>
>   Mode:    verify
>   Result:  FAIL — <N> check(s) failed
>   Next:    fix: <specific issue(s) listed above>, then re-run verify
> ```
> 
> **What would you like to do next?**
> 
> A) Fix the listed issues and re-run `rh-inf-discovery verify <topic>`
> B) Return to the session to modify sources
> 
> You can also ask for status `rh-inf-status` at any time.

---

## Level 3 — Discovery Plan Format

<!-- LEVEL 3 DISCLOSURE — detailed schemas, loaded on-demand -->

The discovery plan is **two files** written to the same directory:

### `discovery-plan.yaml` — Structured Source List

Pure YAML. This is what `rh-skills validate --plan` and `rh-inf-ingest` operate on.

```yaml
topic: "<topic>"
date: "YYYY-MM-DD"
sources:
  - name: "<display name>"
    type: "<source type>"            # see reference.md Source Type Taxonomy
    rationale: "<why this source>"
    search_terms:
      - "<term1>"
      - "<term2>"
    evidence_level: "<level>"        # see reference.md Evidence Level Taxonomy
    access: "<open|authenticated|manual>"
    url: "<url>"                     # required when access: open
    auth_note: "<how to access>"     # required when access: authenticated
    recommended: true                # optional; true for high-value authenticated sources
```

See `examples/plan.yaml` for a complete worked example.

### `discovery-readout.md` — Generated Domain Narrative

Markdown prose. Generated by the agent; consumed by agents and humans for context; **not machine-parsed**. Must begin with the derivation note.

```markdown
> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
> The structured source list in `discovery-plan.yaml` is the single source of truth.

## Domain Advice

<Prose addressing the Domain Advice Checklist from reference.md:
 CMS program alignment, SDOH relevance, health equity, quality measure landscape,
 terminology systems, health economics angle.>

## Research Expansion Suggestions

1. **<Adjacent Topic>** — <Why relevant to primary topic>.
   Start with: `rh-skills search pubmed --query "<terms>" --max 20`

2. ...
```

See `examples/readout.md` for a complete worked example.

---

## Error Handling

| Condition | Action |
|-----------|--------|
| `rh-skills status show` exits non-zero | Print error, suggest `rh-skills init <topic>`, exit |
| Fewer than 5 sources after all searches | Search additional databases; do not save |
| More than 25 sources | Select top 25, log extras in expansion suggestions |
| `rh-skills validate --plan` exits 1 | Report failures; do not proceed to ingest |
| Plan already exists (no `--force`) | Offer continuation or fresh start |
| `rh-skills search` network error | Retry with `--offline` flag; mark step `SKIPPED (offline)`; continue with domain knowledge |

## CLI Quick Reference

| Command | Purpose |
|---------|---------|
| `rh-skills search pubmed --query "..." --json` | Search PubMed (live) |
| `rh-skills search pubmed --offline --query "..."` | Record query; get reference links (no network) |
| `rh-skills search pmc --query "..." --json` | Search PMC open-access (live) |
| `rh-skills search clinicaltrials --query "..." --json` | Search ClinicalTrials.gov (live) |
| `rh-skills search pubmed --append-to-plan <topic> --query "..."` | Search and append results to plan |
| `rh-skills source add --type <type> --title "..." --rationale "..." [--append-to-plan <topic>]` | Add a single source entry |
| `rh-skills source add --dry-run ...` | Preview source entry without writing |
| `rh-skills schema show discovery-plan` | Show plan schema and allowed taxonomies |
| `rh-skills validate --plan <file>` | Validate a saved discovery plan |
| `rh-skills validate --plan -` | Validate via stdin (pipe or heredoc) |
