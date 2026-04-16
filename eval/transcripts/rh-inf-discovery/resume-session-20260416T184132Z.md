
|-------|-------|
| skill | `rh-inf-discovery` |
| scenario | resume-session |
| agent | codex |
| model | default |
| timestamp | 20260416T184132Z |
| rh_skills_version | 0.1.0 |

## Opening Prompt

```
You are a clinical informaticist. The following is your active skill:

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

---

Use the rh-inf-discovery skill in **session** mode for the topic
`young-adult-hypertension`.

Working directory: /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
Topic: young-adult-hypertension

A partial discovery plan already exists at
`topics/young-adult-hypertension/process/plans/discovery-plan.yaml`.
It has 3 sources (2 clinical guidelines, 1 RCT) but is missing:
- A health-economics or value-based care source
- A US government program or USPSTF source

Resume the session: identify the gaps, search for the missing source types,
add them to the plan, and re-validate.
```

## Session

Reading prompt from stdin...
OpenAI Codex v0.118.0 (research preview)
--------
workdir: /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
model: gpt-5.4
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/bkaney/.codex/memories]
reasoning effort: high
reasoning summaries: none
session id: 019d9799-3efd-7db2-8c4c-20a4c32250b0
--------
user
You are a clinical informaticist. The following is your active skill:

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

---

Use the rh-inf-discovery skill in **session** mode for the topic
`young-adult-hypertension`.

Working directory: /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
Topic: young-adult-hypertension

A partial discovery plan already exists at
`topics/young-adult-hypertension/process/plans/discovery-plan.yaml`.
It has 3 sources (2 clinical guidelines, 1 RCT) but is missing:
- A health-economics or value-based care source
- A US government program or USPSTF source

Resume the session: identify the gaps, search for the missing source types,
add them to the plan, and re-validate.

codex
Using `rh-inf-discovery` in `session` mode for `young-adult-hypertension`. I’m checking the topic state, the existing plan, and the skill reference material first so I can fill the specific source gaps without disturbing unrelated content.
exec
/bin/zsh -lc "sed -n '1,220p' /private/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/.agents/skills/rh-inf-discovery/SKILL.md" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
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
  - .agents/skills/rh-inf-discovery/reference.md          # domain advice checklist, source taxonomies, US gov coverage
  - .agents/skills/rh-inf-discovery/examples/plan.yaml    # worked example: diabetes-ccm discovery-plan.yaml (structured sources)
  - .agents/skills/rh-inf-discovery/examples/readout.md   # worked example: diabetes-ccm discovery-readout.md (domain narrative)
  - .agents/skills/rh-inf-discovery/examples/output.md    # worked example: session transcript excerpt
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

Read `.agents/skills/rh-inf-discovery/reference.md` → **Domain Advice Checklist**. Present domain-specific
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
- **Evidence level** (see `.agents/skills/rh-inf-discovery/reference.md` Evidence Level Taxonomy)
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

exec
/bin/zsh -lc "sed -n '1,240p' topics/young-adult-hypertension/process/plans/discovery-plan.yaml" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
topic: young-adult-hypertension
clinical_question: >
  What are the diagnostic thresholds, treatment targets, and lifestyle
  interventions for hypertension in adults aged 18–39?
sources:
  - id: acc-aha-2017-hypertension
    title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
    url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
    type: clinical-guideline
    evidence_level: ia
    rationale: >
      Primary US clinical guideline redefining hypertension thresholds;
      directly addresses young-adult treatment targets.
    open_access: true
  - id: jnc8-hypertension-management
    title: "2014 Evidence-Based Guideline for High Blood Pressure (JNC 8)"
    url: https://jamanetwork.com/journals/jama/fullarticle/1791497
    type: clinical-guideline
    evidence_level: ia
    rationale: Previous guideline; useful for threshold comparison.
    open_access: false
  - id: sprint-trial
    title: "SPRINT: Systolic BP Intervention Trial"
    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
    type: rct
    evidence_level: ib
    rationale: >
      Landmark RCT supporting intensive BP targets; note exclusion of
      adults < 50 limits direct applicability to this age group.
    open_access: true
status: draft

exec
/bin/zsh -lc "sed -n '1,260p' /private/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/.agents/skills/rh-inf-discovery/reference.md" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
# rh-inf-discovery Reference

Companion reference for `SKILL.md`. Loaded on demand during session mode.

---

## Domain Advice Checklist

Apply the relevant sections below when generating domain advice in Step 1 of
session mode. Address each applicable item in the **Domain Advice** section of
`discovery-plan.md` (the narrative file).

### CMS Program Alignment
- Does an existing CMS eCQM (electronic clinical quality measure) cover this
  condition? Check [eCQM Library](https://ecqi.healthit.gov/ecqms) and
  [CMIT](https://cmit.cms.gov/).
- Is there a MIPS/QPP performance measure? Check
  [QPP Measures](https://qpp.cms.gov/mips/explore-measures).
- Is there a Medicaid or CMMI model that incentivizes this intervention?
- Are there CMS national or local coverage determinations (NCD/LCD) affecting
  clinical decision support?

### SDOH Relevance
- Does this condition have known SDOH drivers? Map to Gravity Project domains:
  Food Insecurity · Housing Instability / Homelessness · Transportation Access ·
  Utility Difficulties · Interpersonal Safety · Financial Strain · Social
  Isolation · Education / Employment · Health Behaviors.
- Is there a standardized SDOH screening tool in use? (PRAPARE, AHC HRSN, etc.)
- Is the [Gravity SDOH FHIR IG](https://hl7.org/fhir/us/sdoh-clinicalcare/)
  relevant for interoperability planning?

### Health Equity
- Are there documented disparities (race, ethnicity, language, geography,
  disability) in screening, treatment, or outcomes for this condition?
- Are there CMS health equity goals or HEDIS equity stratification requirements?
- Does the USPSTF or specialty society address disparate populations explicitly?

### Quality Measure Landscape
- What HEDIS measures apply? (Check NCQA measure list)
- What NQF-endorsed measures exist? (Check NQF Quality Positioning System)
- Are there Joint Commission quality standards?
- Is there a FHIR-based measure using QI-Core / US Core profiles?

### Terminology Systems
Identify which coding systems are likely needed (include at least one in `sources[]`):
- **Diagnoses**: ICD-10-CM ([NLM](https://www.nlm.nih.gov/research/umls/sourcereleasedocs/current/ICD10CM/))
- **Clinical findings / procedures**: SNOMED CT ([SNOMED International](https://www.snomed.org/))
- **Lab / observations**: LOINC ([Regenstrief](https://loinc.org/))
- **Medications**: RxNorm ([NLM](https://www.nlm.nih.gov/research/umls/rxnorm/))
- **Units**: UCUM ([Unitsofmeasure.org](https://ucum.org/))
- **Social determinants**: Gravity Project SDOH value sets ([VSAC](https://vsac.nlm.nih.gov/))

### Health Economics Angle
Required when the topic involves a **chronic condition**, **preventive intervention**,
or **CMS quality program**. Address in domain advice and include at least one
`health-economics` source in `sources[]`:
- Total cost of care / disease burden (HCUP, MEPS, GBD)
- Cost per QALY or cost-effectiveness analysis (CEA Registry, ICER, NICE HTA)
- CMS National Health Expenditure Data for population-level spend
- Employer or payer burden if applicable

---

## US Government Healthcare Coverage

For any topic with a US clinical or population health angle, include sources from:

| Source | URL | What to find |
|--------|-----|--------------|
| CMS eCQM Library | https://ecqi.healthit.gov/ecqms | Existing quality measures |
| CMS CMIT | https://cmit.cms.gov/ | Model tests and initiatives |
| QPP / MIPS Measures | https://qpp.cms.gov/mips/explore-measures | Clinician performance measures |
| USPSTF | https://www.uspreventiveservicestaskforce.org/uspstf/recommendation-topics | Preventive service grades |
| Gravity Project | https://thegravityproject.net/ | SDOH domains, FHIR IG |
| AHRQ | https://www.ahrq.gov/research/findings/evidence-based-reports/ | Evidence-based practice reports |
| CDC / MMWR | https://www.cdc.gov/mmwr/ | Epidemiological data |
| HCUP | https://www.hcup-us.ahrq.gov/ | Hospital utilization + costs |
| MEPS | https://meps.ahrq.gov/ | Medical expenditure panel survey |
| GBD (IHME) | https://vizhub.healthdata.org/gbd-results | Global burden of disease |
| NLM VSAC | https://vsac.nlm.nih.gov/ | Value sets for eCQMs |
| CMS NCD/LCD | https://www.cms.gov/medicare-coverage-database | Coverage policies |
| HRSA | https://www.hrsa.gov/ | Underserved populations, safety net |

### Accessing CMS Data Without Authentication
- eCQM measure packages: downloadable as FHIR JSON bundles from eCQI
- HCUP: most summary statistics are publicly available; microdata requires DUA
- MEPS: public use files downloadable at no cost from AHRQ

---

## Medical Journals

Use these when identifying high-value publication sources. Most require
institutional access; include as `access: authenticated` with `auth_note`.

For a comprehensive list see: https://en.wikipedia.org/wiki/List_of_medical_journals

### High-Impact General Medicine
| Journal | Publisher | Access |
|---------|-----------|--------|
| NEJM | Massachusetts Medical Society | Institutional |
| JAMA (+ JAMA Network) | AMA | Institutional / open abstracts |
| The Lancet (+ family) | Elsevier | Institutional |
| BMJ | BMJ Publishing | Free registration for abstracts |
| Annals of Internal Medicine | ACP | Institutional |

### Healthcare Informatics / Health IT
| Journal | Publisher | Access |
|---------|-----------|--------|
| JAMIA | Oxford / AMIA | Institutional |
| J Biomed Informatics | Elsevier | Institutional |
| npj Digital Medicine | Nature | Open access |
| Applied Clinical Informatics | Thieme | Institutional |

### Quality, Safety, and Policy
| Journal | Publisher | Access |
|---------|-----------|--------|
| Health Affairs | Project HOPE | Institutional |
| JAMA Health Forum | AMA | Open access |
| Milbank Quarterly | Wiley | Open access |
| BMJ Quality & Safety | BMJ | Institutional |

### Specialty (examples — expand based on topic)
| Specialty | Key Journal | Access |
|-----------|-------------|--------|
| Cardiology | JACC, Circulation | Institutional |
| Endocrinology / Diabetes | Diabetes Care, Diabetologia | Institutional |
| Oncology | JCO, JNCI | Institutional |
| Nephrology | JASN, CJASN | Institutional |
| Pulmonology | AJRCCM | Institutional |
| Psychiatry / Behavioral | Lancet Psychiatry | Institutional |

---

## Source Type Taxonomy

| `type` value | Examples |
|---|---|
| `guideline` | ADA Standards, ACC/AHA guidelines, USPSTF recommendations, NICE guidance |
| `clinical-guideline` | Alias for `guideline` |
| `systematic-review` | Cochrane reviews, AHRQ evidence reports |
| `rct` | Randomized controlled trials |
| `cohort-study` | Prospective or retrospective cohort studies |
| `case-control` | Case-control studies |
| `cross-sectional` | Cross-sectional surveys and prevalence studies |
| `case-report` | Case reports and case series |
| `expert-opinion` | Expert opinion, editorial, or commentary |
| `terminology` | SNOMED CT, LOINC, ICD-10-CM, RxNorm, UCUM |
| `value-set` | VSAC (NLM), FHIR value sets, PHIN VADS |
| `measure-library` | CMS eCQMs, HEDIS, MIPS/QPP measures, NQF-endorsed measures |
| `quality-measure` | Alias for `measure-library` |
| `fhir-ig` | US Core, QI-Core, CARIN BB, Gravity SDOH FHIR IG |
| `cds-library` | CDS Hooks registry, OpenCDS |
| `sdoh-assessment` | PRAPARE, AHC HRSN Tool, CDC SVI, CDC PLACES |
| `health-economics` | HCUP, MEPS, GBD, CEA Registry, ICER, NICE HTA |
| `government-program` | CMS CMMI models, Medicaid state plans, CMS LCD/NCD, HRSA |
| `registry` | ClinicalTrials.gov, disease registries |
| `pubmed-article` | PubMed / PMC research articles |
| `textbook` | Textbooks and reference manuals |
| `document` | General documents not covered above |
| `other` | Anything not covered above |

**At least one `terminology` entry is required** for any plan that passes `verify`.

---

## Evidence Level Taxonomy

| Value | Meaning |
|-------|---------|
| `grade-a` | GRADE high-certainty evidence |
| `grade-b` | GRADE moderate-certainty evidence |
| `grade-c` | GRADE low-certainty evidence |
| `grade-d` | GRADE very low-certainty evidence |
| `uspstf-a` | USPSTF Grade A (high certainty of substantial net benefit) |
| `uspstf-b` | USPSTF Grade B (high certainty of moderate net benefit) |
| `uspstf-c` | USPSTF Grade C (moderate certainty of small net benefit) |
| `uspstf-d` | USPSTF Grade D (moderate/high certainty of no net benefit or harm) |
| `uspstf-i` | USPSTF Grade I (insufficient evidence) |
| `ia` | Oxford Level 1a — systematic review of RCTs |
| `ib` | Oxford Level 1b — individual RCT |
| `iia` | Oxford Level 2a — systematic review of cohort studies |
| `iib` | Oxford Level 2b — individual cohort study |
| `iii` | Oxford Level 3 — case-control study |
| `iv` | Oxford Level 4 — case series |
| `v` | Oxford Level 5 — expert opinion |
| `expert-consensus` | No formal systematic review; expert opinion or consensus statement |
| `reference-standard` | Authoritative reference (terminology, value set, coding system) |
| `n/a` | Not applicable (e.g., clinical trials, registries, government data sets) |

---

## rh-skills search Command Reference

```sh
# Search PubMed articles
rh-skills search pubmed --query "<terms>" --max 20 [--json]

# Search PubMed Central (open-access full text)
rh-skills search pmc --query "<terms>" --max 20 [--json]

# Search ClinicalTrials.gov
rh-skills search clinicaltrials --query "<terms>" --max 20 [--json]
```

The `--json` flag outputs a structured array for programmatic parsing:
```json
[
  {
    "id": "...",
    "title": "...",
    "authors": ["..."],
    "year": "2024",
    "journal": "...",
    "abstract": "...",
    "url": "https://pubmed.ncbi.nlm.nih.gov/...",
    "open_access": false
  }
]
```

Set `NCBI_API_KEY` environment variable to increase PubMed rate limits from
3 req/s to 10 req/s (register free at https://www.ncbi.nlm.nih.gov/account/).

---

## rh-skills ingest implement --url Reference

```sh
rh-skills ingest implement --url <url> --name <slug> [--type <mime>]
```

Exit codes:
- `0`: success — file downloaded to `sources/`, registered in `tracking.yaml`
- `1`: network or HTTP error
- `2`: file already exists (idempotent — treat as already downloaded)
- `3`: auth redirect detected — reclassify source as `access: authenticated`

exec
/bin/zsh -lc 'rh-skills status show young-adult-hypertension' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 237ms:
Topic:    young-adult-hypertension
Title:    
Author:   
Created:  
Stage:    initialized

Artifacts:
  L1 (sources):          0
  L2 (structured):       0
  L3 (computable):       0

Last event:  (2026-04-14T09:00:00Z)

Next steps:
  - Update your discovery plan: rh-inf-discovery session young-adult-hypertension
  - Ingest sources using your existing discovery plan: rh-inf-ingest plan young-adult-hypertension
  - Full pipeline summary: rh-skills status progress young-adult-hypertension

codex
The existing file is in an older schema (`title`, `open_access`, no `search_terms`/`access`), so I’m checking the current discovery-plan format and validating the file as-is before I patch it.
Resume the discovery session by normalizing the partial plan to the current schema, filling the identified source gaps, and verifying the saved result.
  ✓ Inspect current plan, schema, and existing discovery artifacts
  → Search for missing US government and health-economics/value-based sources
  • Update discovery-plan.yaml and derived readout to current validated schema
  • Run plan validation and report outcome
exec
/bin/zsh -lc "ls -la topics/young-adult-hypertension/process/plans && printf '\\n---\\n' && sed -n '1,220p' topics/young-adult-hypertension/process/plans/discovery-readout.md 2>/dev/null" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 exited 1 in 0ms:
total 4
drwxr-xr-x 3 bkaney staff   96 Apr 16 14:41 .
drwxr-xr-x 3 bkaney staff   96 Apr 16 14:41 ..
-rw-r--r-- 1 bkaney staff 1259 Apr 16 14:41 discovery-plan.yaml

---

exec
/bin/zsh -lc 'rh-skills schema show discovery-plan' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
exec
/bin/zsh -lc 'rh-skills validate --plan topics/young-adult-hypertension/process/plans/discovery-plan.yaml' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 215ms:

discovery-plan.yaml — L1 source evidence plan consumed by rh-inf-ingest

Top-level fields:
  topic                string — topic slug, e.g. diabetes-ccm (required)
  sources              list of source entries (required, 5–25 items)

Source entry fields:
  name                 string — unique kebab-case identifier (required)
  type                 string — source type from taxonomy (required, see source_types)
  title                string — human-readable title (required)
  url                  string — canonical URL to the source (required when access: open)
  rationale            string — why this source is included (required)
  evidence_level       string — from evidence_levels vocabulary (required)
  search_terms         list of strings — terms used to find this source (required)
  access               string — open | authenticated | manual (optional)
  year                 string or int — publication year (optional)
  authors              list of strings (optional)
  notes                string — additional context (optional)

Valid source types (23):
  case-control                    case-report                     cds-library                     clinical-guideline            
  cohort-study                    cross-sectional                 document                        expert-opinion                
  fhir-ig                         government-program              guideline                       health-economics              
  measure-library                 other                           pubmed-article                  quality-measure               
  rct                             registry                        sdoh-assessment                 systematic-review             
  terminology                     textbook                        value-set                     

Valid evidence levels (19):
  expert-consensus  grade-a  grade-b  grade-c  grade-d  ia  ib  iia  iib  iii  iv  n/a  reference-standard  uspstf-a  uspstf-b  uspstf-c  uspstf-d  uspstf-i  v

Valid access values (3):
  authenticated  manual  open

Validation checks:
  • YAML parses successfully
  • sources[] count between 5 and 25
  • at least one 'terminology' type source present
  • every entry has non-empty rationale
  • every entry has non-empty search_terms
  • every evidence_level is from the allowed vocabulary
  • every type is from the allowed taxonomy (warning if unknown)
  • access value, if present, is open|authenticated|manual (warning if unknown)
  • at least one 'health-economics' source (warning if missing)

Validate with: rh-skills validate --plan <path>  OR  rh-skills validate --plan -  (stdin)

 exited 1 in 217ms:
Validating discovery plan: topics/young-adult-hypertension/process/plans/discovery-plan.yaml

✓ Parses as valid YAML
✗ Source count too low: 3 (minimum 5)
✗ No terminology source (SNOMED/LOINC/ICD/RxNorm) — required for L3 computable output
✓ All entries have rationale
✗ Missing search_terms: [index 0]
✗ Missing search_terms: [index 1]
✗ Missing search_terms: [index 2]
✓ All evidence levels are valid
✓ All source types are from the taxonomy
⚠ No health-economics source found — recommended for chronic conditions and preventive interventions

INVALID — 5 check(s) failed, 1 warning(s)

codex
I’ve confirmed the current file fails validation for three reasons: too few sources, no terminology source, and missing `search_terms` on every existing entry. I’m running targeted PubMed/PMC/ClinicalTrials searches now for health-economics and young-adult hypertension evidence, then I’ll pair that with a direct US government source to close the remaining gap.
exec
/bin/zsh -lc "ls topics/young-adult-hypertension/process/notes.md 2>/dev/null && sed -n '1,200p' topics/young-adult-hypertension/process/notes.md || true
sed -n '1,200p' RESEARCH.md 2>/dev/null || true" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
exec
/bin/zsh -lc 'rh-skills search pubmed --query "young adult hypertension economic burden healthcare expenditures" --max 10 --json' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
exec
/bin/zsh -lc 'rh-skills search clinicaltrials --query "young adult hypertension" --max 10 --json' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
exec
/bin/zsh -lc 'rh-skills search pmc --query "young adult hypertension economic burden healthcare expenditures" --max 10 --json' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 exited 1 in 257ms:
Error: NCBI esearch failed: Network error: [Errno 8] nodename nor servname provided, or not known

Network access may be restricted in this environment.
Re-run with --offline to get reference links and record the query:
  rh-skills search pmc --offline --query "..."

Or build a discovery plan manually:
  1. Gather source URLs from your browser or a web search tool
  2. Use: rh-skills source add --type <type> --url <url> ...
  3. Validate with: rh-skills validate --plan <file>

 exited 1 in 260ms:
Error: ClinicalTrials.gov API failed: Network error: [Errno 8] nodename nor servname provided, or not known

Network access may be restricted in this environment.
Re-run with --offline to get reference links and record the query:
  rh-skills search clinicaltrials --offline --query "..."

Or build a discovery plan manually:
  1. Gather source URLs from your browser or a web search tool
  2. Use: rh-skills source add --type <type> --url <url> ...
  3. Validate with: rh-skills validate --plan <file>

Network access may be restricted in this environment.
Re-run with --offline to get reference links and record the query:
  rh-skills search clinicaltrials --offline --query "..."

Or build a discovery plan manually:
  1. Gather source URLs from your browser or a web search tool
  2. Use: rh-skills source add --type registry --url <url> ...
  3. Validate with: rh-skills validate --plan <file>

 exited 1 in 261ms:
Error: NCBI esearch failed: Network error: [Errno 8] nodename nor servname provided, or not known

Network access may be restricted in this environment.
Re-run with --offline to get reference links and record the query:
  rh-skills search pubmed --offline --query "..."

Or build a discovery plan manually:
  1. Gather source URLs from your browser or a web search tool
  2. Use: rh-skills source add --type <type> --url <url> ...
  3. Validate with: rh-skills validate --plan <file>

web search: 
web search: site:uspreventiveservicestaskforce.org hypertension in adults screening recommendation 2021
web search: 
web search: site:meps.ahrq.gov MEPS hypertension expenditures adults
web search: 
web search: site:loinc.org "LOINC" official home
web search: 
web search: site:qpp.cms.gov/docs/QPP_quality_measure_specifications 2026 Measure 236 Controlling High Blood Pressure PDF
web search: 
web search: site:meps.ahrq.gov hypertension MEPS topic
codex
The live literature APIs are blocked in this sandbox, which is consistent with the skill’s offline path. I’m switching to offline query logging plus official primary-source URLs for USPSTF, AHRQ/MEPS, CMS/QPP, and LOINC so the saved plan is still evidence-based and validator-clean.
exec
/bin/zsh -lc "sed -n '1,220p' /private/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/.agents/skills/rh-inf-discovery/examples/plan.yaml" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
topic: "diabetes-ccm"
version: "1.0"
created: "2026-04-15T12:00:00Z"
last_updated: "2026-04-15T12:00:00Z"
status: "approved"
session_id: "disc-2026-04-15-diabetes-ccm"
domain_advice:
  cms_program_alignment:
    - "CMS122 (HbA1c Poor Control) is a core diabetes quality measure for CMS and MIPS/QPP alignment."
    - "CCM billing codes 99490/99491 and complex CCM codes 99487/99489 support the operational case for a diabetes CCM workflow."
  sdoh_relevance:
    - "Food insecurity, transportation access, and financial strain directly affect diabetes outcomes and medication adherence."
    - "Gravity Project artifacts are relevant when the workflow includes SDOH capture or exchange."
  health_equity:
    - "Diabetes burden and complications are disproportionately high in Black, Hispanic/Latino, and American Indian/Alaska Native populations."
    - "Measure stratification and outreach design should explicitly consider underserved populations."
  terminology_systems:
    - "SNOMED CT for diabetes condition concepts"
    - "LOINC for HbA1c and glucose laboratory observations"
    - "ICD-10-CM for claims-oriented cohort definition"
    - "RxNorm for anti-diabetic medication classes"
  health_economics:
    - "Use HCUP or MEPS to quantify preventable utilization and cost burden."
    - "Include at least one cost-of-care source because this is a chronic-condition topic."
  coverage_gaps:
    - "Pediatric diabetes subgroup evidence"
    - "Implementation barriers in safety-net primary care"
expansion_suggestions:
  - area: "Diabetic kidney disease prevention"
    why_relevant: "Diabetes is the leading cause of CKD and ESRD, and nephropathy measures are common in quality programs."
    first_command: 'rh-skills search pubmed --query "diabetic kidney disease prevention SGLT2 CKD" --max 15'
  - area: "Medication adherence economics"
    why_relevant: "Insulin and GLP-1 adherence gaps drive avoidable admissions and are often addressed in CCM business cases."
    first_command: 'rh-skills search pubmed --query "diabetes medication adherence cost effectiveness pharmacist" --max 10'
  - area: "Health equity in underserved populations"
    why_relevant: "FQHC and safety-net populations have disproportionate diabetes burden and outcome gaps."
    first_command: 'rh-skills search pubmed --query "diabetes disparities racial ethnic minority FQHC" --max 10'
  - area: "Continuous glucose monitoring integration"
    why_relevant: "CGM interoperability and CMS coverage policy affect modern diabetes workflows."
    first_command: 'rh-skills search clinicaltrials --query "continuous glucose monitoring type 2 diabetes outcomes" --max 10'
  - area: "Implementation science barriers"
    why_relevant: "CCM adoption depends on workflow feasibility, staffing, and EHR template fit."
    first_command: 'rh-skills search pubmed --query "chronic care model implementation barriers primary care diabetes" --max 10'
sources:
  - name: "ada-standards-2024"
    title: "ADA Standards of Medical Care in Diabetes 2024"
    type: "guideline"
    url: "https://diabetesjournals.org/care/issue/47/Supplement_1"
    access: "open"
    evidence_level: "grade-a"
    open_access: true
    rationale: >
      Core clinical guidance for screening, diagnosis, glycemic targets, and
      treatment. This is the anchor guideline for any diabetes CCM topic.
    search_terms:
      - "ADA standards of care diabetes 2024"
      - "diabetes clinical practice guideline 2024"

  - name: "cms122-hba1c-poor-control"
    title: "CMS122 — Diabetes: Hemoglobin A1c Poor Control (>9%)"
    type: "measure-library"
    url: "https://ecqi.healthit.gov/ecqm/ec/2024/cms0122v13"
    access: "open"
    evidence_level: "n/a"
    open_access: true
    rationale: >
      Representative CMS quality measure for diabetes. Critical for measure
      alignment, denominator logic, and value set planning.
    search_terms:
      - "CMS122 HbA1c poor control"
      - "eCQM diabetes poor control"

  - name: "snomed-diabetes-hierarchy"
    title: "SNOMED CT — Diabetes Mellitus Hierarchy"
    type: "terminology"
    url: "https://browser.ihtsdotools.org/?perspective=full&conceptId1=73211009"
    access: "open"
    evidence_level: "reference-standard"
    open_access: true
    rationale: >
      Provides the computable disease concept hierarchy needed for problem-list,
      registry, and CDS use cases.
    search_terms:
      - "SNOMED diabetes mellitus"
      - "73211009 diabetes mellitus"

  - name: "loinc-hba1c-glucose-codes"
    title: "LOINC — HbA1c and Glucose Observation Codes"
    type: "terminology"
    url: "https://loinc.org/4548-4/"
    access: "open"
    evidence_level: "reference-standard"
    open_access: true
    rationale: >
      LOINC is required for interoperable HbA1c and glucose result capture in
      US Core and downstream computable artifacts.
    search_terms:
      - "LOINC HbA1c 4548-4"
      - "LOINC glucose 1558-6"

  - name: "gravity-sdoh-fhir-ig"
    title: "Gravity SDOH Clinical Care FHIR Implementation Guide"
    type: "fhir-ig"
    url: "https://hl7.org/fhir/us/sdoh-clinicalcare/"
    access: "open"
    evidence_level: "reference-standard"
    open_access: true
    rationale: >
      Covers interoperable representation of food insecurity and related SDOH
      concepts that commonly affect diabetes control and care coordination.
    search_terms:
      - "Gravity Project SDOH FHIR IG"
      - "food insecurity diabetes FHIR"

  - name: "hcup-diabetes-hospitalization-costs"
    title: "HCUP National Inpatient Sample — Diabetes Hospitalization Costs"
    type: "health-economics"
    url: "https://www.hcup-us.ahrq.gov/nisoverview.jsp"
    access: "open"
    evidence_level: "n/a"
    open_access: true
    rationale: >
      Provides cost and utilization context for preventable admissions, helping
      justify the economics of a diabetes CCM intervention.
    search_terms:
      - "HCUP diabetes hospitalization costs"
      - "diabetes preventable admissions NIS"

  - name: "cochrane-intensive-glycemic-control"
    title: "Cochrane Review — Intensive Glycemic Control in Type 2 Diabetes"
    type: "systematic-review"
    url: "https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD008143.pub2/full"
    access: "authenticated"
    evidence_level: "grade-a"
    open_access: false
    recommended: true
    auth_note: >
      Retrieve via institutional library proxy or Wiley-hosted Cochrane access.
      Search for "intensive glycemic control type 2 diabetes cardiovascular"
      after login.
    rationale: >
      High-value synthesis of glycemic target evidence that can shape CCM
      target-setting and shared-decision support.
    search_terms:
      - "Cochrane intensive glycemic control type 2 diabetes"
      - "HbA1c target cardiovascular outcomes"

  - name: "nct04512345-diabetes-ccm-trial"
    title: "Chronic Care Management for Diabetes Mellitus"
    type: "registry"
    url: "https://clinicaltrials.gov/study/NCT04512345"
    access: "open"
    evidence_level: "n/a"
    open_access: true
    nct_id: "NCT04512345"
    rationale: >
      Active or recently completed registry evidence highlights intervention
      designs and implementation approaches that may not yet be fully published.
    search_terms:
      - "diabetes chronic care management clinical trial"
      - "team-based diabetes care clinicaltrials"

exec
/bin/zsh -lc "sed -n '1,220p' /private/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/.agents/skills/rh-inf-discovery/examples/readout.md" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
> The structured source list in `discovery-plan.yaml` is the single source of truth.

## Domain Advice

### CMS Program Alignment

Diabetes mellitus (T2D) has one of the largest footprints in CMS quality
programs. Key alignment points for a CCM initiative:

- **eCQMs**: CMS122 (HbA1c Poor Control), CMS125 (Breast Cancer Screening, if
  population overlap), CMS130 (Colorectal Cancer Screening) — all commonly
  co-tracked in diabetes management. CMS122 is a MIPS mandatory outcome measure.
- **MIPS/QPP**: Diabetes is a MIPS Improvement Activity focus area. QPP
  measure 001 (Diabetes: HbA1c Poor Control) and measure 119 (Diabetes:
  Medical Attention for Nephropathy) are widely used.
- **CMMI models**: Comprehensive Primary Care Plus (CPC+), ACO Realizing Equity,
  Access, and Community Health (REACH) Model, and Kidney Care Choices (KCC)
  all include diabetes management components.
- **Chronic Care Management (CCM) codes**: CPT 99490/99491 and complex CCM
  codes (99487/99489) are CMS-billable for eligible beneficiaries with T2D.

### SDOH Relevance

Food insecurity and housing instability are the most evidence-backed SDOH
drivers of poor glycemic control. Relevant Gravity Project domains:

- **Food Insecurity** — most directly linked to HbA1c variation
- **Transportation Access** — barrier to medication adherence and appointments
- **Financial Strain** — insulin affordability, meter/supplies access
- **Housing Instability** — associated with hypoglycemia risk

Use the [Gravity SDOH FHIR IG](https://hl7.org/fhir/us/sdoh-clinicalcare/) for
interoperable SDOH data capture. PRAPARE and AHC HRSN Tool both screen for
diabetes-relevant SDOH domains.

### Health Equity

Documented disparities in T2D management:
- Higher prevalence and worse glycemic control in Black, Hispanic/Latino, and
  American Indian/Alaska Native populations
- Lower rates of statin co-prescription and nephropathy screening in minority
  populations despite higher CKD risk
- HEDIS stratification now required for race/ethnicity in many measures

Include at least one equity-focused search: `rh-skills search pubmed --query
"diabetes disparities race ethnicity HbA1c" --max 10`.

### Quality Measure Landscape

Active diabetes quality measures (2024):
- CMS eCQM: CMS122, CMS134, CMS136 (adolescent), CMS149
- HEDIS: CDC (Comprehensive Diabetes Care) — HbA1c testing, control, retinal
  exam, nephropathy monitoring, BP control
- NQF #0059 (HbA1c control), #0061 (BP control), #0062 (LDL-C control)

### Terminology Systems

Required for this topic:
- **SNOMED CT**: disease concepts, procedure hierarchy
- **LOINC**: HbA1c (4548-4), fasting glucose (1558-6), urinary albumin-creatinine ratio
- **ICD-10-CM**: E08–E13 diabetes spectrum
- **RxNorm**: metformin (860975), insulin analogs, GLP-1 agonists, SGLT-2 inhibitors
- **UCUM**: percent (%) for HbA1c, mg/dL for glucose

### Health Economics

T2D has a documented economic burden of ~$327 billion annually in the US (ADA
2022 cost estimates). Key economic considerations for a CCM initiative:
- Average per-patient annual cost for T2D: $16,752 (vs. $6,153 without diabetes)
- Preventable hospitalizations (DKA, hypoglycemia, foot complications) represent
  significant avoidable cost
- CCM billing revenue offsets program costs for eligible practices
- HCUP NIS and MEPS provide population-level cost data for business case modeling

---

## Research Expansion Suggestions

1. **Diabetic Kidney Disease (DKD) Prevention** — T2D is the leading cause of
   end-stage renal disease. A CCM initiative should address nephropathy
   surveillance and early CKD intervention. Relevant eCQM: CMS134.
   Start with: `rh-skills search pubmed --query "diabetic kidney disease prevention SGLT2 CKD" --max 15`

2. **Healthcare Economics of Medication Adherence** — Insulin and GLP-1 agonist
   adherence gaps drive hospitalizations. Cost-effectiveness of pharmacist-led
   adherence programs in T2D is well-studied.
   Start with: `rh-skills search pubmed --query "diabetes medication adherence cost effectiveness pharmacist" --max 10`

3. **Health Equity: Diabetes Disparities in Underserved Populations** — FQHC and
   safety-net populations have disproportionate T2D burden. HRSA Uniform Data
   System (UDS) provides FQHC-specific quality benchmarks.
   Start with: `rh-skills search pubmed --query "diabetes disparities racial ethnic minority FQHC" --max 10`

4. **Continuous Glucose Monitoring (CGM) Integration** — CGM data interoperability
   via FHIR is an emerging area. DARIO, Dexcom, and Abbott have SMART on FHIR apps.
   Coverage policy (CMS LCD) is evolving.
   Start with: `rh-skills search clinicaltrials --query "continuous glucose monitoring type 2 diabetes outcomes" --max 10`

5. **Implementation Science: CCM Adoption Barriers** — Known barriers include
   care coordination workflow burden and EHR template limitations. Implementation
   frameworks (CFIR, RE-AIM) applied to diabetes CCM are published.
   Start with: `rh-skills search pubmed --query "chronic care model implementation barriers primary care diabetes" --max 10`

exec
/bin/zsh -lc 'rh-skills search pubmed --offline --query "young adult hypertension economic burden healthcare expenditures"' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
exec
/bin/zsh -lc 'rh-skills search clinicaltrials --offline --query "young adult hypertension"' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
exec
/bin/zsh -lc 'rh-skills search pmc --offline --query "young adult hypertension economic burden healthcare expenditures"' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 158ms:

Network access unavailable — returning offline reference links.
Re-run this command in a network-enabled environment to retrieve live results.
Attempted query recorded; use it manually at the URL above.

Offline: query recorded → 'young adult hypertension economic burden healthcare expenditures'
PMC: 2 of 2 results for: young adult hypertension economic burden healthcare expenditures

[1] PubMed — MEDLINE literature database (NLM) (n/d)
    ID:  | PMC | open-access: yes
    Authors: National Library of Medicine
    https://pubmed.ncbi.nlm.nih.gov/
    Search PubMed for peer-reviewed biomedical literature including systematic reviews, RCTs, and clinical guidelines....

[2] PubMed Central (PMC) — Open Access full-text archive (n/d)
    ID:  | PMC | open-access: yes
    Authors: National Library of Medicine
    https://pmc.ncbi.nlm.nih.gov/
    Free full-text archive of biomedical and life sciences journal articles at the National Institutes of Health....

 succeeded in 200ms:

Network access unavailable — returning offline reference links.
Re-run this command in a network-enabled environment to retrieve live results.
Attempted query recorded; use it manually at the URL above.

Offline: query recorded → 'young adult hypertension economic burden healthcare expenditures'
PubMed: 2 of 2 results for: young adult hypertension economic burden healthcare expenditures

[1] PubMed — MEDLINE literature database (NLM) (n/d)
    ID:  | PubMed | open-access: yes
    Authors: National Library of Medicine
    https://pubmed.ncbi.nlm.nih.gov/
    Search PubMed for peer-reviewed biomedical literature including systematic reviews, RCTs, and clinical guidelines....

[2] PubMed Central (PMC) — Open Access full-text archive (n/d)
    ID:  | PubMed | open-access: yes
    Authors: National Library of Medicine
    https://pmc.ncbi.nlm.nih.gov/
    Free full-text archive of biomedical and life sciences journal articles at the National Institutes of Health....

 succeeded in 159ms:

Network access unavailable — returning offline reference links.
Re-run this command in a network-enabled environment to retrieve live results.
Attempted query recorded; use it manually at the URL above.

Offline: query recorded → 'young adult hypertension'
ClinicalTrials.gov: 1 of 1 results for: young adult hypertension

[1] ClinicalTrials.gov — Registry of clinical studies (n/d)
    ID:  | ClinicalTrials.gov | open-access: yes
    Status: n/d | Phase: n/d
    https://clinicaltrials.gov/
    Registry and results database of publicly and privately supported clinical studies conducted around the world....

web search: 
web search: 
web search: 
web search: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
web search: 
web search: 'most complete source' in https://meps.ahrq.gov/mepsweb/index.jsp
web search: 
web search: 'universal' in https://loinc.org/
web search: 
web search: site:meps.ahrq.gov hypertension expenditures adults statistical brief AHRQ
web search: 
web search: site:qpp.cms.gov/docs/QPP_quality_measure_specifications 2025 Measure 236 controlling high blood pressure pdf
codex
I’ve got the replacement sources. The file edit will do three things together: normalize the plan to the current schema, append the missing USPSTF/AHRQ/CMS/terminology entries, and record the offline search attempts so the session remains reproducible.
exec
/bin/zsh -lc 'find topics/young-adult-hypertension -maxdepth 3 -type f | sort' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
topics/young-adult-hypertension/process/plans/discovery-plan.yaml

exec
/bin/zsh -lc "rg --files -g 'RESEARCH.md' -g 'topics/young-adult-hypertension/**'" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
topics/young-adult-hypertension/process/plans/discovery-plan.yaml

exec
/bin/zsh -lc 'ls -la' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
total 32
drwx------  13 bkaney staff   416 Apr 16 14:41 .
drwx------ 644 bkaney staff 20608 Apr 16 14:44 ..
drwxr-xr-x   3 bkaney staff    96 Apr 16 14:41 .agents
drwxr-xr-x   9 bkaney staff   288 Apr 16 14:41 .git
-rw-r--r--   1 bkaney staff   109 Apr 16 14:41 .gitignore
-rw-r--r--   1 bkaney staff     5 Apr 16 14:41 .python-version
drwxr-xr-x   8 bkaney staff   256 Apr 16 14:41 .venv
-rw-r--r--   1 bkaney staff     0 Apr 16 14:41 README.md
-rw-r--r--   1 bkaney staff    90 Apr 16 14:41 main.py
-rw-r--r--   1 bkaney staff   279 Apr 16 14:41 pyproject.toml
drwxr-xr-x   3 bkaney staff    96 Apr 16 14:41 topics
-rw-r--r--   1 bkaney staff   251 Apr 16 14:41 tracking.yaml
-rw-r--r--   1 bkaney staff 11218 Apr 16 14:41 uv.lock

web search: 
web search: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
web search: 
web search: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
web search: 
web search: site:ecqi.healthit.gov CMS165 hypertension eCQM 2025
web search: 
web search: site:loinc.org 8480-6 systolic blood pressure
apply patch
patch: completed
/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/RESEARCH.md
/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/notes.md
/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/plans/discovery-readout.md
diff --git a/RESEARCH.md b/RESEARCH.md
new file mode 100644
index 0000000000000000000000000000000000000000..4b5afafeca337ef73ad08a9de120d3b26439fd42
--- /dev/null
+++ b/RESEARCH.md
@@ -0,0 +1,5 @@
+# Research Portfolio
+
+| Topic | Stage | Sources | Updated | Notes |
+|---|---|---:|---|---|
+| young-adult-hypertension | L1 discovery | 7 | 2026-04-16 | Resumed partial discovery plan; added USPSTF, CMS165v14, MEPS, and LOINC sources. |
diff --git a/topics/young-adult-hypertension/process/notes.md b/topics/young-adult-hypertension/process/notes.md
new file mode 100644
index 0000000000000000000000000000000000000000..9acf840cae9638ddb78313101eb813dcda870c01
--- /dev/null
+++ b/topics/young-adult-hypertension/process/notes.md
@@ -0,0 +1,7 @@
+# young-adult-hypertension notes
+
+- Discovery session resumed on 2026-04-16.
+- Normalized the existing plan to the current schema and added missing USPSTF,
+  CMS measure, health-economics, and terminology sources.
+- Live PubMed, PMC, and ClinicalTrials.gov searches were unavailable in this
+  sandbox; offline queries are recorded in `process/plans/discovery-plan.yaml`.
diff --git a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
index 5068ecee324801787a97bb301b39f88e38fe9ceb..08d37a9dfc5063e9cb6366dc86c31a9f26c0b4bc
--- a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
+++ b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
@@ -1,31 +1,133 @@
 topic: young-adult-hypertension
+version: "1.0"
+created: "2026-04-16"
+last_updated: "2026-04-16"
+status: draft
 clinical_question: >
-  What are the diagnostic thresholds, treatment targets, and lifestyle
-  interventions for hypertension in adults aged 18–39?
+  What are the diagnostic thresholds, treatment targets, screening intervals,
+  and lifestyle interventions most relevant to hypertension in adults aged
+  18–39, and how should those rules be represented for quality measurement,
+  CDS, and interoperable data capture?
+notes:
+  - >
+    Resumed an existing partial plan on 2026-04-16 and normalized it to the
+    current discovery-plan schema before re-validation.
+  - >
+    PubMed live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    PMC live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    ClinicalTrials.gov live search was unavailable in this sandbox; offline
+    query recorded: "young adult hypertension".
 sources:
-  - id: acc-aha-2017-hypertension
+  - name: acc-aha-2017-hypertension
     title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
-    type: clinical-guideline
+    access: open
     evidence_level: ia
+    year: 2017
     rationale: >
-      Primary US clinical guideline redefining hypertension thresholds;
-      directly addresses young-adult treatment targets.
-    open_access: true
-  - id: jnc8-hypertension-management
-    title: "2014 Evidence-Based Guideline for High Blood Pressure (JNC 8)"
+      Primary US clinical guideline redefining hypertension thresholds and
+      treatment targets. It anchors adult threshold logic that affects young
+      adult diagnosis, staging, and follow-up.
+    search_terms:
+      - "2017 ACC AHA hypertension guideline"
+      - "young adults hypertension threshold ACC AHA"
+
+  - name: jnc8-hypertension-management
+    title: "2014 Evidence-Based Guideline for Management of High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://jamanetwork.com/journals/jama/fullarticle/1791497
-    type: clinical-guideline
+    access: authenticated
     evidence_level: ia
-    rationale: Previous guideline; useful for threshold comparison.
-    open_access: false
-  - id: sprint-trial
-    title: "SPRINT: Systolic BP Intervention Trial"
-    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    year: 2014
+    notes: "JAMA abstract page is open; full text may require institutional or library access."
+    rationale: >
+      Previous major US guideline, useful for threshold and treatment-target
+      comparison when building longitudinal decision support or explaining
+      historical variation in care policies.
+    search_terms:
+      - "JNC 8 hypertension guideline 2014"
+      - "adult hypertension threshold comparison JNC 8"
+
+  - name: sprint-trial
+    title: "A Randomized Trial of Intensive versus Standard Blood-Pressure Control"
     type: rct
+    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    access: authenticated
     evidence_level: ib
+    year: 2015
+    notes: "NEJM abstract page is open; institutional access may be needed for the full article."
+    rationale: >
+      Landmark RCT supporting intensive blood pressure control. Applicability to
+      adults under age 50 is limited, but the trial remains important context
+      for target-setting logic and escalation discussions.
+    search_terms:
+      - "SPRINT trial blood pressure control"
+      - "intensive blood pressure target randomized trial"
+
+  - name: uspstf-hypertension-screening-2021
+    title: "Recommendation: Hypertension in Adults: Screening"
+    type: guideline
+    url: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
+    access: open
+    evidence_level: uspstf-a
+    year: 2021
+    rationale: >
+      Fills the missing US government and preventive-care gap. The USPSTF
+      recommendation applies to adults 18 years or older and explicitly notes
+      less frequent screening for lower-risk adults aged 18 to 39.
+    search_terms:
+      - "USPSTF hypertension in adults screening 2021"
+      - "young adults 18 to 39 hypertension screening USPSTF"
+
+  - name: cms165-controlling-high-blood-pressure
+    title: "CMS165v14 / MIPS Quality ID 236 — Controlling High Blood Pressure"
+    type: measure-library
+    url: https://ecqi.healthit.gov/ecqm/ec/2026/cms0165v14
+    access: open
+    evidence_level: n/a
+    year: 2026
+    rationale: >
+      Adds the CMS value-based care and quality-measure perspective. This
+      measure is directly relevant to informatics work because it defines the
+      adult hypertension denominator, outcome threshold, and computable data
+      elements used in reporting and CDS.
+    search_terms:
+      - "CMS165v14 controlling high blood pressure"
+      - "MIPS Quality ID 236 hypertension"
+
+  - name: meps-hypertension-expenditures
+    title: "AHRQ MEPS Statistical Brief #487: Expenditures for Commonly Treated Conditions among Adults Age 18 and Older in the U.S. Civilian Noninstitutionalized Population, 2013"
+    type: health-economics
+    url: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
+    access: open
+    evidence_level: n/a
+    year: 2016
     rationale: >
-      Landmark RCT supporting intensive BP targets; note exclusion of
-      adults < 50 limits direct applicability to this age group.
-    open_access: true
-status: draft
+      Fills the missing health-economics gap with a primary US expenditure
+      source. MEPS gives treated prevalence and spending context for
+      hypertension that can support business-case, utilization, and value-based
+      care framing for younger adults.
+    search_terms:
+      - "MEPS hypertension expenditures adults"
+      - "AHRQ hypertension treated prevalence expenditures"
+
+  - name: loinc-blood-pressure-observation-codes
+    title: "LOINC 8480-6 / 8462-4 — Systolic and Diastolic Blood Pressure Observation Codes"
+    type: terminology
+    url: https://loinc.org/8480-6/
+    access: open
+    evidence_level: reference-standard
+    year: 2025
+    notes: "Companion diastolic code: https://loinc.org/8462-4/"
+    rationale: >
+      Required terminology source for interoperable capture of systolic and
+      diastolic blood pressure observations in US Core, eCQM logic, and
+      downstream computable artifacts.
+    search_terms:
+      - "LOINC 8480-6 systolic blood pressure"
+      - "LOINC 8462-4 diastolic blood pressure"
diff --git a/topics/young-adult-hypertension/process/plans/discovery-readout.md b/topics/young-adult-hypertension/process/plans/discovery-readout.md
new file mode 100644
index 0000000000000000000000000000000000000000..35d12f7fac1b84e4605539c385a6009aaa3fd816
--- /dev/null
+++ b/topics/young-adult-hypertension/process/plans/discovery-readout.md
@@ -0,0 +1,76 @@
+> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
+> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
+> The structured source list in `discovery-plan.yaml` is the single source of truth.
+
+## Domain Advice
+
+### CMS Program Alignment
+
+Young-adult hypertension has a clear CMS and informatics footprint even though
+the target cohort skews younger than many traditional Medicare workflows.
+`CMS165v14 / MIPS Quality ID 236` covers adults 18-85 with essential
+hypertension and therefore supplies directly reusable denominator and numerator
+logic for registry design, CDS, and quality reporting.
+
+### SDOH Relevance
+
+Relevant Gravity-aligned domains include financial strain, food insecurity,
+housing instability, transportation barriers, and health behaviors. For young
+adults, insurance churn, employment instability, and disrupted primary-care
+continuity can affect both screening and sustained treatment.
+
+### Health Equity
+
+Earlier-onset and less-controlled hypertension disproportionately affects some
+racialized populations, especially Black adults, and may be worsened by access
+barriers, neighborhood stressors, and variable primary-care engagement. Equity
+analyses should be designed early rather than appended after measure logic is
+complete.
+
+### Quality Measure Landscape
+
+In addition to ACC/AHA and USPSTF guidance, the practical measurement anchor is
+`CMS165v14 / MIPS 236`. For informatics implementation, this measure is more
+actionable than narrative guidance alone because it defines computable adult
+hypertension control logic and associated data elements.
+
+### Terminology Systems
+
+Minimum terminology set for this topic:
+
+- `SNOMED CT` for essential hypertension and related problem-list concepts
+- `LOINC` for systolic and diastolic blood pressure observations
+- `ICD-10-CM` for claims-facing cohort identification
+- `RxNorm` for antihypertensive medication classes
+
+### Health Economics
+
+Hypertension is a high-prevalence chronic condition with policy significance
+even when per-person spending is lower than some other chronic diseases.
+`MEPS` is an appropriate primary economics source because it supports national
+prevalence, utilization, and payer-mix framing for value-based care arguments.
+
+## Research Expansion Suggestions
+
+1. **Masked hypertension and ambulatory confirmation in younger adults** —
+   young adults may have missed or delayed diagnosis if office-only screening is
+   used.
+   Start with: `rh-skills search pubmed --query "masked hypertension ambulatory blood pressure monitoring young adults" --max 10`
+
+2. **Health equity in early-onset hypertension** — disparities in onset,
+   diagnosis, and control can materially affect cohort design and follow-up
+   logic.
+   Start with: `rh-skills search pubmed --query "young adult hypertension disparities race ethnicity" --max 10`
+
+3. **Home blood pressure monitoring implementation** — confirmation and
+   longitudinal control workflows depend on validated home devices and patient
+   adherence.
+   Start with: `rh-skills search pubmed --query "home blood pressure monitoring implementation young adults primary care" --max 10`
+
+4. **Transition from adolescent to adult hypertension care** — transitional
+   populations may have different thresholds, workups, and documentation needs.
+   Start with: `rh-skills search pubmed --query "transition adolescent to adult hypertension care" --max 10`
+
+5. **Productivity and long-horizon economic burden of early hypertension** —
+   early-onset disease can affect lifetime cost and cardiovascular risk.
+   Start with: `rh-skills search pubmed --query "young adult hypertension economic burden productivity costs" --max 10`

diff --git a/RESEARCH.md b/RESEARCH.md
new file mode 100644
index 0000000000000000000000000000000000000000..4b5afafeca337ef73ad08a9de120d3b26439fd42
--- /dev/null
+++ b/RESEARCH.md
@@ -0,0 +1,5 @@
+# Research Portfolio
+
+| Topic | Stage | Sources | Updated | Notes |
+|---|---|---:|---|---|
+| young-adult-hypertension | L1 discovery | 7 | 2026-04-16 | Resumed partial discovery plan; added USPSTF, CMS165v14, MEPS, and LOINC sources. |
diff --git a/topics/young-adult-hypertension/process/notes.md b/topics/young-adult-hypertension/process/notes.md
new file mode 100644
index 0000000000000000000000000000000000000000..9acf840cae9638ddb78313101eb813dcda870c01
--- /dev/null
+++ b/topics/young-adult-hypertension/process/notes.md
@@ -0,0 +1,7 @@
+# young-adult-hypertension notes
+
+- Discovery session resumed on 2026-04-16.
+- Normalized the existing plan to the current schema and added missing USPSTF,
+  CMS measure, health-economics, and terminology sources.
+- Live PubMed, PMC, and ClinicalTrials.gov searches were unavailable in this
+  sandbox; offline queries are recorded in `process/plans/discovery-plan.yaml`.
diff --git a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
index 5068ecee324801787a97bb301b39f88e38fe9ceb..08d37a9dfc5063e9cb6366dc86c31a9f26c0b4bc
--- a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
+++ b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
@@ -1,31 +1,133 @@
 topic: young-adult-hypertension
+version: "1.0"
+created: "2026-04-16"
+last_updated: "2026-04-16"
+status: draft
 clinical_question: >
-  What are the diagnostic thresholds, treatment targets, and lifestyle
-  interventions for hypertension in adults aged 18–39?
+  What are the diagnostic thresholds, treatment targets, screening intervals,
+  and lifestyle interventions most relevant to hypertension in adults aged
+  18–39, and how should those rules be represented for quality measurement,
+  CDS, and interoperable data capture?
+notes:
+  - >
+    Resumed an existing partial plan on 2026-04-16 and normalized it to the
+    current discovery-plan schema before re-validation.
+  - >
+    PubMed live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    PMC live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    ClinicalTrials.gov live search was unavailable in this sandbox; offline
+    query recorded: "young adult hypertension".
 sources:
-  - id: acc-aha-2017-hypertension
+  - name: acc-aha-2017-hypertension
     title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
-    type: clinical-guideline
+    access: open
     evidence_level: ia
+    year: 2017
     rationale: >
-      Primary US clinical guideline redefining hypertension thresholds;
-      directly addresses young-adult treatment targets.
-    open_access: true
-  - id: jnc8-hypertension-management
-    title: "2014 Evidence-Based Guideline for High Blood Pressure (JNC 8)"
+      Primary US clinical guideline redefining hypertension thresholds and
+      treatment targets. It anchors adult threshold logic that affects young
+      adult diagnosis, staging, and follow-up.
+    search_terms:
+      - "2017 ACC AHA hypertension guideline"
+      - "young adults hypertension threshold ACC AHA"
+
+  - name: jnc8-hypertension-management
+    title: "2014 Evidence-Based Guideline for Management of High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://jamanetwork.com/journals/jama/fullarticle/1791497
-    type: clinical-guideline
+    access: authenticated
     evidence_level: ia
-    rationale: Previous guideline; useful for threshold comparison.
-    open_access: false
-  - id: sprint-trial
-    title: "SPRINT: Systolic BP Intervention Trial"
-    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    year: 2014
+    notes: "JAMA abstract page is open; full text may require institutional or library access."
+    rationale: >
+      Previous major US guideline, useful for threshold and treatment-target
+      comparison when building longitudinal decision support or explaining
+      historical variation in care policies.
+    search_terms:
+      - "JNC 8 hypertension guideline 2014"
+      - "adult hypertension threshold comparison JNC 8"
+
+  - name: sprint-trial
+    title: "A Randomized Trial of Intensive versus Standard Blood-Pressure Control"
     type: rct
+    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    access: authenticated
     evidence_level: ib
+    year: 2015
+    notes: "NEJM abstract page is open; institutional access may be needed for the full article."
+    rationale: >
+      Landmark RCT supporting intensive blood pressure control. Applicability to
+      adults under age 50 is limited, but the trial remains important context
+      for target-setting logic and escalation discussions.
+    search_terms:
+      - "SPRINT trial blood pressure control"
+      - "intensive blood pressure target randomized trial"
+
+  - name: uspstf-hypertension-screening-2021
+    title: "Recommendation: Hypertension in Adults: Screening"
+    type: guideline
+    url: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
+    access: open
+    evidence_level: uspstf-a
+    year: 2021
+    rationale: >
+      Fills the missing US government and preventive-care gap. The USPSTF
+      recommendation applies to adults 18 years or older and explicitly notes
+      less frequent screening for lower-risk adults aged 18 to 39.
+    search_terms:
+      - "USPSTF hypertension in adults screening 2021"
+      - "young adults 18 to 39 hypertension screening USPSTF"
+
+  - name: cms165-controlling-high-blood-pressure
+    title: "CMS165v14 / MIPS Quality ID 236 — Controlling High Blood Pressure"
+    type: measure-library
+    url: https://ecqi.healthit.gov/ecqm/ec/2026/cms0165v14
+    access: open
+    evidence_level: n/a
+    year: 2026
+    rationale: >
+      Adds the CMS value-based care and quality-measure perspective. This
+      measure is directly relevant to informatics work because it defines the
+      adult hypertension denominator, outcome threshold, and computable data
+      elements used in reporting and CDS.
+    search_terms:
+      - "CMS165v14 controlling high blood pressure"
+      - "MIPS Quality ID 236 hypertension"
+
+  - name: meps-hypertension-expenditures
+    title: "AHRQ MEPS Statistical Brief #487: Expenditures for Commonly Treated Conditions among Adults Age 18 and Older in the U.S. Civilian Noninstitutionalized Population, 2013"
+    type: health-economics
+    url: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
+    access: open
+    evidence_level: n/a
+    year: 2016
     rationale: >
-      Landmark RCT supporting intensive BP targets; note exclusion of
-      adults < 50 limits direct applicability to this age group.
-    open_access: true
-status: draft
+      Fills the missing health-economics gap with a primary US expenditure
+      source. MEPS gives treated prevalence and spending context for
+      hypertension that can support business-case, utilization, and value-based
+      care framing for younger adults.
+    search_terms:
+      - "MEPS hypertension expenditures adults"
+      - "AHRQ hypertension treated prevalence expenditures"
+
+  - name: loinc-blood-pressure-observation-codes
+    title: "LOINC 8480-6 / 8462-4 — Systolic and Diastolic Blood Pressure Observation Codes"
+    type: terminology
+    url: https://loinc.org/8480-6/
+    access: open
+    evidence_level: reference-standard
+    year: 2025
+    notes: "Companion diastolic code: https://loinc.org/8462-4/"
+    rationale: >
+      Required terminology source for interoperable capture of systolic and
+      diastolic blood pressure observations in US Core, eCQM logic, and
+      downstream computable artifacts.
+    search_terms:
+      - "LOINC 8480-6 systolic blood pressure"
+      - "LOINC 8462-4 diastolic blood pressure"
diff --git a/topics/young-adult-hypertension/process/plans/discovery-readout.md b/topics/young-adult-hypertension/process/plans/discovery-readout.md
new file mode 100644
index 0000000000000000000000000000000000000000..35d12f7fac1b84e4605539c385a6009aaa3fd816
--- /dev/null
+++ b/topics/young-adult-hypertension/process/plans/discovery-readout.md
@@ -0,0 +1,76 @@
+> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
+> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
+> The structured source list in `discovery-plan.yaml` is the single source of truth.
+
+## Domain Advice
+
+### CMS Program Alignment
+
+Young-adult hypertension has a clear CMS and informatics footprint even though
+the target cohort skews younger than many traditional Medicare workflows.
+`CMS165v14 / MIPS Quality ID 236` covers adults 18-85 with essential
+hypertension and therefore supplies directly reusable denominator and numerator
+logic for registry design, CDS, and quality reporting.
+
+### SDOH Relevance
+
+Relevant Gravity-aligned domains include financial strain, food insecurity,
+housing instability, transportation barriers, and health behaviors. For young
+adults, insurance churn, employment instability, and disrupted primary-care
+continuity can affect both screening and sustained treatment.
+
+### Health Equity
+
+Earlier-onset and less-controlled hypertension disproportionately affects some
+racialized populations, especially Black adults, and may be worsened by access
+barriers, neighborhood stressors, and variable primary-care engagement. Equity
+analyses should be designed early rather than appended after measure logic is
+complete.
+
+### Quality Measure Landscape
+
+In addition to ACC/AHA and USPSTF guidance, the practical measurement anchor is
+`CMS165v14 / MIPS 236`. For informatics implementation, this measure is more
+actionable than narrative guidance alone because it defines computable adult
+hypertension control logic and associated data elements.
+
+### Terminology Systems
+
+Minimum terminology set for this topic:
+
+- `SNOMED CT` for essential hypertension and related problem-list concepts
+- `LOINC` for systolic and diastolic blood pressure observations
+- `ICD-10-CM` for claims-facing cohort identification
+- `RxNorm` for antihypertensive medication classes
+
+### Health Economics
+
+Hypertension is a high-prevalence chronic condition with policy significance
+even when per-person spending is lower than some other chronic diseases.
+`MEPS` is an appropriate primary economics source because it supports national
+prevalence, utilization, and payer-mix framing for value-based care arguments.
+
+## Research Expansion Suggestions
+
+1. **Masked hypertension and ambulatory confirmation in younger adults** —
+   young adults may have missed or delayed diagnosis if office-only screening is
+   used.
+   Start with: `rh-skills search pubmed --query "masked hypertension ambulatory blood pressure monitoring young adults" --max 10`
+
+2. **Health equity in early-onset hypertension** — disparities in onset,
+   diagnosis, and control can materially affect cohort design and follow-up
+   logic.
+   Start with: `rh-skills search pubmed --query "young adult hypertension disparities race ethnicity" --max 10`
+
+3. **Home blood pressure monitoring implementation** — confirmation and
+   longitudinal control workflows depend on validated home devices and patient
+   adherence.
+   Start with: `rh-skills search pubmed --query "home blood pressure monitoring implementation young adults primary care" --max 10`
+
+4. **Transition from adolescent to adult hypertension care** — transitional
+   populations may have different thresholds, workups, and documentation needs.
+   Start with: `rh-skills search pubmed --query "transition adolescent to adult hypertension care" --max 10`
+
+5. **Productivity and long-horizon economic burden of early hypertension** —
+   early-onset disease can affect lifetime cost and cardiovascular risk.
+   Start with: `rh-skills search pubmed --query "young adult hypertension economic burden productivity costs" --max 10`

codex
The edit is in place. I’m validating the plan now and checking the saved files for any schema mismatch or formatting problem before I close the loop.
exec
/bin/zsh -lc "sed -n '1,260p' topics/young-adult-hypertension/process/plans/discovery-plan.yaml" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
topic: young-adult-hypertension
version: "1.0"
created: "2026-04-16"
last_updated: "2026-04-16"
status: draft
clinical_question: >
  What are the diagnostic thresholds, treatment targets, screening intervals,
  and lifestyle interventions most relevant to hypertension in adults aged
  18–39, and how should those rules be represented for quality measurement,
  CDS, and interoperable data capture?
notes:
  - >
    Resumed an existing partial plan on 2026-04-16 and normalized it to the
    current discovery-plan schema before re-validation.
  - >
    PubMed live search was unavailable in this sandbox; offline query recorded:
    "young adult hypertension economic burden healthcare expenditures".
  - >
    PMC live search was unavailable in this sandbox; offline query recorded:
    "young adult hypertension economic burden healthcare expenditures".
  - >
    ClinicalTrials.gov live search was unavailable in this sandbox; offline
    query recorded: "young adult hypertension".
sources:
  - name: acc-aha-2017-hypertension
    title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
    type: clinical-guideline
    url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
    access: open
    evidence_level: ia
    year: 2017
    rationale: >
      Primary US clinical guideline redefining hypertension thresholds and
      treatment targets. It anchors adult threshold logic that affects young
      adult diagnosis, staging, and follow-up.
    search_terms:
      - "2017 ACC AHA hypertension guideline"
      - "young adults hypertension threshold ACC AHA"

  - name: jnc8-hypertension-management
    title: "2014 Evidence-Based Guideline for Management of High Blood Pressure in Adults"
    type: clinical-guideline
    url: https://jamanetwork.com/journals/jama/fullarticle/1791497
    access: authenticated
    evidence_level: ia
    year: 2014
    notes: "JAMA abstract page is open; full text may require institutional or library access."
    rationale: >
      Previous major US guideline, useful for threshold and treatment-target
      comparison when building longitudinal decision support or explaining
      historical variation in care policies.
    search_terms:
      - "JNC 8 hypertension guideline 2014"
      - "adult hypertension threshold comparison JNC 8"

  - name: sprint-trial
    title: "A Randomized Trial of Intensive versus Standard Blood-Pressure Control"
    type: rct
    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
    access: authenticated
    evidence_level: ib
    year: 2015
    notes: "NEJM abstract page is open; institutional access may be needed for the full article."
    rationale: >
      Landmark RCT supporting intensive blood pressure control. Applicability to
      adults under age 50 is limited, but the trial remains important context
      for target-setting logic and escalation discussions.
    search_terms:
      - "SPRINT trial blood pressure control"
      - "intensive blood pressure target randomized trial"

  - name: uspstf-hypertension-screening-2021
    title: "Recommendation: Hypertension in Adults: Screening"
    type: guideline
    url: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
    access: open
    evidence_level: uspstf-a
    year: 2021
    rationale: >
      Fills the missing US government and preventive-care gap. The USPSTF
      recommendation applies to adults 18 years or older and explicitly notes
      less frequent screening for lower-risk adults aged 18 to 39.
    search_terms:
      - "USPSTF hypertension in adults screening 2021"
      - "young adults 18 to 39 hypertension screening USPSTF"

  - name: cms165-controlling-high-blood-pressure
    title: "CMS165v14 / MIPS Quality ID 236 — Controlling High Blood Pressure"
    type: measure-library
    url: https://ecqi.healthit.gov/ecqm/ec/2026/cms0165v14
    access: open
    evidence_level: n/a
    year: 2026
    rationale: >
      Adds the CMS value-based care and quality-measure perspective. This
      measure is directly relevant to informatics work because it defines the
      adult hypertension denominator, outcome threshold, and computable data
      elements used in reporting and CDS.
    search_terms:
      - "CMS165v14 controlling high blood pressure"
      - "MIPS Quality ID 236 hypertension"

  - name: meps-hypertension-expenditures
    title: "AHRQ MEPS Statistical Brief #487: Expenditures for Commonly Treated Conditions among Adults Age 18 and Older in the U.S. Civilian Noninstitutionalized Population, 2013"
    type: health-economics
    url: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
    access: open
    evidence_level: n/a
    year: 2016
    rationale: >
      Fills the missing health-economics gap with a primary US expenditure
      source. MEPS gives treated prevalence and spending context for
      hypertension that can support business-case, utilization, and value-based
      care framing for younger adults.
    search_terms:
      - "MEPS hypertension expenditures adults"
      - "AHRQ hypertension treated prevalence expenditures"

  - name: loinc-blood-pressure-observation-codes
    title: "LOINC 8480-6 / 8462-4 — Systolic and Diastolic Blood Pressure Observation Codes"
    type: terminology
    url: https://loinc.org/8480-6/
    access: open
    evidence_level: reference-standard
    year: 2025
    notes: "Companion diastolic code: https://loinc.org/8462-4/"
    rationale: >
      Required terminology source for interoperable capture of systolic and
      diastolic blood pressure observations in US Core, eCQM logic, and
      downstream computable artifacts.
    search_terms:
      - "LOINC 8480-6 systolic blood pressure"
      - "LOINC 8462-4 diastolic blood pressure"

exec
/bin/zsh -lc "sed -n '1,220p' topics/young-adult-hypertension/process/plans/discovery-readout.md" in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
> The structured source list in `discovery-plan.yaml` is the single source of truth.

## Domain Advice

### CMS Program Alignment

Young-adult hypertension has a clear CMS and informatics footprint even though
the target cohort skews younger than many traditional Medicare workflows.
`CMS165v14 / MIPS Quality ID 236` covers adults 18-85 with essential
hypertension and therefore supplies directly reusable denominator and numerator
logic for registry design, CDS, and quality reporting.

### SDOH Relevance

Relevant Gravity-aligned domains include financial strain, food insecurity,
housing instability, transportation barriers, and health behaviors. For young
adults, insurance churn, employment instability, and disrupted primary-care
continuity can affect both screening and sustained treatment.

### Health Equity

Earlier-onset and less-controlled hypertension disproportionately affects some
racialized populations, especially Black adults, and may be worsened by access
barriers, neighborhood stressors, and variable primary-care engagement. Equity
analyses should be designed early rather than appended after measure logic is
complete.

### Quality Measure Landscape

In addition to ACC/AHA and USPSTF guidance, the practical measurement anchor is
`CMS165v14 / MIPS 236`. For informatics implementation, this measure is more
actionable than narrative guidance alone because it defines computable adult
hypertension control logic and associated data elements.

### Terminology Systems

Minimum terminology set for this topic:

- `SNOMED CT` for essential hypertension and related problem-list concepts
- `LOINC` for systolic and diastolic blood pressure observations
- `ICD-10-CM` for claims-facing cohort identification
- `RxNorm` for antihypertensive medication classes

### Health Economics

Hypertension is a high-prevalence chronic condition with policy significance
even when per-person spending is lower than some other chronic diseases.
`MEPS` is an appropriate primary economics source because it supports national
prevalence, utilization, and payer-mix framing for value-based care arguments.

## Research Expansion Suggestions

1. **Masked hypertension and ambulatory confirmation in younger adults** —
   young adults may have missed or delayed diagnosis if office-only screening is
   used.
   Start with: `rh-skills search pubmed --query "masked hypertension ambulatory blood pressure monitoring young adults" --max 10`

2. **Health equity in early-onset hypertension** — disparities in onset,
   diagnosis, and control can materially affect cohort design and follow-up
   logic.
   Start with: `rh-skills search pubmed --query "young adult hypertension disparities race ethnicity" --max 10`

3. **Home blood pressure monitoring implementation** — confirmation and
   longitudinal control workflows depend on validated home devices and patient
   adherence.
   Start with: `rh-skills search pubmed --query "home blood pressure monitoring implementation young adults primary care" --max 10`

4. **Transition from adolescent to adult hypertension care** — transitional
   populations may have different thresholds, workups, and documentation needs.
   Start with: `rh-skills search pubmed --query "transition adolescent to adult hypertension care" --max 10`

5. **Productivity and long-horizon economic burden of early hypertension** —
   early-onset disease can affect lifetime cost and cardiovascular risk.
   Start with: `rh-skills search pubmed --query "young adult hypertension economic burden productivity costs" --max 10`

exec
/bin/zsh -lc 'git status --short' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
 succeeded in 0ms:
?? .agents/
?? .gitignore
?? .python-version
?? README.md
?? RESEARCH.md
?? main.py
?? pyproject.toml
?? topics/
?? tracking.yaml
?? uv.lock

exec
/bin/zsh -lc 'rh-skills validate --plan topics/young-adult-hypertension/process/plans/discovery-plan.yaml' in /var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst
diff --git a/RESEARCH.md b/RESEARCH.md
new file mode 100644
index 0000000000000000000000000000000000000000..4b5afafeca337ef73ad08a9de120d3b26439fd42
--- /dev/null
+++ b/RESEARCH.md
@@ -0,0 +1,5 @@
+# Research Portfolio
+
+| Topic | Stage | Sources | Updated | Notes |
+|---|---|---:|---|---|
+| young-adult-hypertension | L1 discovery | 7 | 2026-04-16 | Resumed partial discovery plan; added USPSTF, CMS165v14, MEPS, and LOINC sources. |
diff --git a/topics/young-adult-hypertension/process/notes.md b/topics/young-adult-hypertension/process/notes.md
new file mode 100644
index 0000000000000000000000000000000000000000..9acf840cae9638ddb78313101eb813dcda870c01
--- /dev/null
+++ b/topics/young-adult-hypertension/process/notes.md
@@ -0,0 +1,7 @@
+# young-adult-hypertension notes
+
+- Discovery session resumed on 2026-04-16.
+- Normalized the existing plan to the current schema and added missing USPSTF,
+  CMS measure, health-economics, and terminology sources.
+- Live PubMed, PMC, and ClinicalTrials.gov searches were unavailable in this
+  sandbox; offline queries are recorded in `process/plans/discovery-plan.yaml`.
diff --git a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
index 5068ecee324801787a97bb301b39f88e38fe9ceb..08d37a9dfc5063e9cb6366dc86c31a9f26c0b4bc
--- a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
+++ b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
@@ -1,31 +1,133 @@
 topic: young-adult-hypertension
+version: "1.0"
+created: "2026-04-16"
+last_updated: "2026-04-16"
+status: draft
 clinical_question: >
-  What are the diagnostic thresholds, treatment targets, and lifestyle
-  interventions for hypertension in adults aged 18–39?
+  What are the diagnostic thresholds, treatment targets, screening intervals,
+  and lifestyle interventions most relevant to hypertension in adults aged
+  18–39, and how should those rules be represented for quality measurement,
+  CDS, and interoperable data capture?
+notes:
+  - >
+    Resumed an existing partial plan on 2026-04-16 and normalized it to the
+    current discovery-plan schema before re-validation.
+  - >
+    PubMed live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    PMC live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    ClinicalTrials.gov live search was unavailable in this sandbox; offline
+    query recorded: "young adult hypertension".
 sources:
-  - id: acc-aha-2017-hypertension
+  - name: acc-aha-2017-hypertension
     title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
-    type: clinical-guideline
+    access: open
     evidence_level: ia
+    year: 2017
     rationale: >
-      Primary US clinical guideline redefining hypertension thresholds;
-      directly addresses young-adult treatment targets.
-    open_access: true
-  - id: jnc8-hypertension-management
-    title: "2014 Evidence-Based Guideline for High Blood Pressure (JNC 8)"
+      Primary US clinical guideline redefining hypertension thresholds and
+      treatment targets. It anchors adult threshold logic that affects young
+      adult diagnosis, staging, and follow-up.
+    search_terms:
+      - "2017 ACC AHA hypertension guideline"
+      - "young adults hypertension threshold ACC AHA"
+
+  - name: jnc8-hypertension-management
+    title: "2014 Evidence-Based Guideline for Management of High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://jamanetwork.com/journals/jama/fullarticle/1791497
-    type: clinical-guideline
+    access: authenticated
     evidence_level: ia
-    rationale: Previous guideline; useful for threshold comparison.
-    open_access: false
-  - id: sprint-trial
-    title: "SPRINT: Systolic BP Intervention Trial"
-    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    year: 2014
+    notes: "JAMA abstract page is open; full text may require institutional or library access."
+    rationale: >
+      Previous major US guideline, useful for threshold and treatment-target
+      comparison when building longitudinal decision support or explaining
+      historical variation in care policies.
+    search_terms:
+      - "JNC 8 hypertension guideline 2014"
+      - "adult hypertension threshold comparison JNC 8"
+
+  - name: sprint-trial
+    title: "A Randomized Trial of Intensive versus Standard Blood-Pressure Control"
     type: rct
+    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    access: authenticated
     evidence_level: ib
+    year: 2015
+    notes: "NEJM abstract page is open; institutional access may be needed for the full article."
+    rationale: >
+      Landmark RCT supporting intensive blood pressure control. Applicability to
+      adults under age 50 is limited, but the trial remains important context
+      for target-setting logic and escalation discussions.
+    search_terms:
+      - "SPRINT trial blood pressure control"
+      - "intensive blood pressure target randomized trial"
+
+  - name: uspstf-hypertension-screening-2021
+    title: "Recommendation: Hypertension in Adults: Screening"
+    type: guideline
+    url: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
+    access: open
+    evidence_level: uspstf-a
+    year: 2021
+    rationale: >
+      Fills the missing US government and preventive-care gap. The USPSTF
+      recommendation applies to adults 18 years or older and explicitly notes
+      less frequent screening for lower-risk adults aged 18 to 39.
+    search_terms:
+      - "USPSTF hypertension in adults screening 2021"
+      - "young adults 18 to 39 hypertension screening USPSTF"
+
+  - name: cms165-controlling-high-blood-pressure
+    title: "CMS165v14 / MIPS Quality ID 236 — Controlling High Blood Pressure"
+    type: measure-library
+    url: https://ecqi.healthit.gov/ecqm/ec/2026/cms0165v14
+    access: open
+    evidence_level: n/a
+    year: 2026
+    rationale: >
+      Adds the CMS value-based care and quality-measure perspective. This
+      measure is directly relevant to informatics work because it defines the
+      adult hypertension denominator, outcome threshold, and computable data
+      elements used in reporting and CDS.
+    search_terms:
+      - "CMS165v14 controlling high blood pressure"
+      - "MIPS Quality ID 236 hypertension"
+
+  - name: meps-hypertension-expenditures
+    title: "AHRQ MEPS Statistical Brief #487: Expenditures for Commonly Treated Conditions among Adults Age 18 and Older in the U.S. Civilian Noninstitutionalized Population, 2013"
+    type: health-economics
+    url: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
+    access: open
+    evidence_level: n/a
+    year: 2016
     rationale: >
-      Landmark RCT supporting intensive BP targets; note exclusion of
-      adults < 50 limits direct applicability to this age group.
-    open_access: true
-status: draft
+      Fills the missing health-economics gap with a primary US expenditure
+      source. MEPS gives treated prevalence and spending context for
+      hypertension that can support business-case, utilization, and value-based
+      care framing for younger adults.
+    search_terms:
+      - "MEPS hypertension expenditures adults"
+      - "AHRQ hypertension treated prevalence expenditures"
+
+  - name: loinc-blood-pressure-observation-codes
+    title: "LOINC 8480-6 / 8462-4 — Systolic and Diastolic Blood Pressure Observation Codes"
+    type: terminology
+    url: https://loinc.org/8480-6/
+    access: open
+    evidence_level: reference-standard
+    year: 2025
+    notes: "Companion diastolic code: https://loinc.org/8462-4/"
+    rationale: >
+      Required terminology source for interoperable capture of systolic and
+      diastolic blood pressure observations in US Core, eCQM logic, and
+      downstream computable artifacts.
+    search_terms:
+      - "LOINC 8480-6 systolic blood pressure"
+      - "LOINC 8462-4 diastolic blood pressure"
diff --git a/topics/young-adult-hypertension/process/plans/discovery-readout.md b/topics/young-adult-hypertension/process/plans/discovery-readout.md
new file mode 100644
index 0000000000000000000000000000000000000000..35d12f7fac1b84e4605539c385a6009aaa3fd816
--- /dev/null
+++ b/topics/young-adult-hypertension/process/plans/discovery-readout.md
@@ -0,0 +1,76 @@
+> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
+> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
+> The structured source list in `discovery-plan.yaml` is the single source of truth.
+
+## Domain Advice
+
+### CMS Program Alignment
+
+Young-adult hypertension has a clear CMS and informatics footprint even though
+the target cohort skews younger than many traditional Medicare workflows.
+`CMS165v14 / MIPS Quality ID 236` covers adults 18-85 with essential
+hypertension and therefore supplies directly reusable denominator and numerator
+logic for registry design, CDS, and quality reporting.
+
+### SDOH Relevance
+
+Relevant Gravity-aligned domains include financial strain, food insecurity,
+housing instability, transportation barriers, and health behaviors. For young
+adults, insurance churn, employment instability, and disrupted primary-care
+continuity can affect both screening and sustained treatment.
+
+### Health Equity
+
+Earlier-onset and less-controlled hypertension disproportionately affects some
+racialized populations, especially Black adults, and may be worsened by access
+barriers, neighborhood stressors, and variable primary-care engagement. Equity
+analyses should be designed early rather than appended after measure logic is
+complete.
+
+### Quality Measure Landscape
+
+In addition to ACC/AHA and USPSTF guidance, the practical measurement anchor is
+`CMS165v14 / MIPS 236`. For informatics implementation, this measure is more
+actionable than narrative guidance alone because it defines computable adult
+hypertension control logic and associated data elements.
+
+### Terminology Systems
+
+Minimum terminology set for this topic:
+
+- `SNOMED CT` for essential hypertension and related problem-list concepts
+- `LOINC` for systolic and diastolic blood pressure observations
+- `ICD-10-CM` for claims-facing cohort identification
+- `RxNorm` for antihypertensive medication classes
+
+### Health Economics
+
+Hypertension is a high-prevalence chronic condition with policy significance
+even when per-person spending is lower than some other chronic diseases.
+`MEPS` is an appropriate primary economics source because it supports national
+prevalence, utilization, and payer-mix framing for value-based care arguments.
+
+## Research Expansion Suggestions
+
+1. **Masked hypertension and ambulatory confirmation in younger adults** —
+   young adults may have missed or delayed diagnosis if office-only screening is
+   used.
+   Start with: `rh-skills search pubmed --query "masked hypertension ambulatory blood pressure monitoring young adults" --max 10`
+
+2. **Health equity in early-onset hypertension** — disparities in onset,
+   diagnosis, and control can materially affect cohort design and follow-up
+   logic.
+   Start with: `rh-skills search pubmed --query "young adult hypertension disparities race ethnicity" --max 10`
+
+3. **Home blood pressure monitoring implementation** — confirmation and
+   longitudinal control workflows depend on validated home devices and patient
+   adherence.
+   Start with: `rh-skills search pubmed --query "home blood pressure monitoring implementation young adults primary care" --max 10`
+
+4. **Transition from adolescent to adult hypertension care** — transitional
+   populations may have different thresholds, workups, and documentation needs.
+   Start with: `rh-skills search pubmed --query "transition adolescent to adult hypertension care" --max 10`
+
+5. **Productivity and long-horizon economic burden of early hypertension** —
+   early-onset disease can affect lifetime cost and cardiovascular risk.
+   Start with: `rh-skills search pubmed --query "young adult hypertension economic burden productivity costs" --max 10`

 succeeded in 178ms:
Validating discovery plan: topics/young-adult-hypertension/process/plans/discovery-plan.yaml

✓ Parses as valid YAML
✓ Source count: 7 (within 5–25 range)
✓ Terminology source present
✓ All entries have rationale
✓ All entries have search_terms
✓ All evidence levels are valid
✓ All source types are from the taxonomy

VALID — all checks passed

  ✓ Inspect current plan, schema, and existing discovery artifacts
  ✓ Search for missing US government and health-economics/value-based sources
  ✓ Update discovery-plan.yaml and derived readout to current validated schema
  ✓ Run plan validation and report outcome
diff --git a/RESEARCH.md b/RESEARCH.md
new file mode 100644
index 0000000000000000000000000000000000000000..4b5afafeca337ef73ad08a9de120d3b26439fd42
--- /dev/null
+++ b/RESEARCH.md
@@ -0,0 +1,5 @@
+# Research Portfolio
+
+| Topic | Stage | Sources | Updated | Notes |
+|---|---|---:|---|---|
+| young-adult-hypertension | L1 discovery | 7 | 2026-04-16 | Resumed partial discovery plan; added USPSTF, CMS165v14, MEPS, and LOINC sources. |
diff --git a/topics/young-adult-hypertension/process/notes.md b/topics/young-adult-hypertension/process/notes.md
new file mode 100644
index 0000000000000000000000000000000000000000..9acf840cae9638ddb78313101eb813dcda870c01
--- /dev/null
+++ b/topics/young-adult-hypertension/process/notes.md
@@ -0,0 +1,7 @@
+# young-adult-hypertension notes
+
+- Discovery session resumed on 2026-04-16.
+- Normalized the existing plan to the current schema and added missing USPSTF,
+  CMS measure, health-economics, and terminology sources.
+- Live PubMed, PMC, and ClinicalTrials.gov searches were unavailable in this
+  sandbox; offline queries are recorded in `process/plans/discovery-plan.yaml`.
diff --git a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
index 5068ecee324801787a97bb301b39f88e38fe9ceb..08d37a9dfc5063e9cb6366dc86c31a9f26c0b4bc
--- a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
+++ b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
@@ -1,31 +1,133 @@
 topic: young-adult-hypertension
+version: "1.0"
+created: "2026-04-16"
+last_updated: "2026-04-16"
+status: draft
 clinical_question: >
-  What are the diagnostic thresholds, treatment targets, and lifestyle
-  interventions for hypertension in adults aged 18–39?
+  What are the diagnostic thresholds, treatment targets, screening intervals,
+  and lifestyle interventions most relevant to hypertension in adults aged
+  18–39, and how should those rules be represented for quality measurement,
+  CDS, and interoperable data capture?
+notes:
+  - >
+    Resumed an existing partial plan on 2026-04-16 and normalized it to the
+    current discovery-plan schema before re-validation.
+  - >
+    PubMed live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    PMC live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    ClinicalTrials.gov live search was unavailable in this sandbox; offline
+    query recorded: "young adult hypertension".
 sources:
-  - id: acc-aha-2017-hypertension
+  - name: acc-aha-2017-hypertension
     title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
-    type: clinical-guideline
+    access: open
     evidence_level: ia
+    year: 2017
     rationale: >
-      Primary US clinical guideline redefining hypertension thresholds;
-      directly addresses young-adult treatment targets.
-    open_access: true
-  - id: jnc8-hypertension-management
-    title: "2014 Evidence-Based Guideline for High Blood Pressure (JNC 8)"
+      Primary US clinical guideline redefining hypertension thresholds and
+      treatment targets. It anchors adult threshold logic that affects young
+      adult diagnosis, staging, and follow-up.
+    search_terms:
+      - "2017 ACC AHA hypertension guideline"
+      - "young adults hypertension threshold ACC AHA"
+
+  - name: jnc8-hypertension-management
+    title: "2014 Evidence-Based Guideline for Management of High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://jamanetwork.com/journals/jama/fullarticle/1791497
-    type: clinical-guideline
+    access: authenticated
     evidence_level: ia
-    rationale: Previous guideline; useful for threshold comparison.
-    open_access: false
-  - id: sprint-trial
-    title: "SPRINT: Systolic BP Intervention Trial"
-    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    year: 2014
+    notes: "JAMA abstract page is open; full text may require institutional or library access."
+    rationale: >
+      Previous major US guideline, useful for threshold and treatment-target
+      comparison when building longitudinal decision support or explaining
+      historical variation in care policies.
+    search_terms:
+      - "JNC 8 hypertension guideline 2014"
+      - "adult hypertension threshold comparison JNC 8"
+
+  - name: sprint-trial
+    title: "A Randomized Trial of Intensive versus Standard Blood-Pressure Control"
     type: rct
+    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    access: authenticated
     evidence_level: ib
+    year: 2015
+    notes: "NEJM abstract page is open; institutional access may be needed for the full article."
+    rationale: >
+      Landmark RCT supporting intensive blood pressure control. Applicability to
+      adults under age 50 is limited, but the trial remains important context
+      for target-setting logic and escalation discussions.
+    search_terms:
+      - "SPRINT trial blood pressure control"
+      - "intensive blood pressure target randomized trial"
+
+  - name: uspstf-hypertension-screening-2021
+    title: "Recommendation: Hypertension in Adults: Screening"
+    type: guideline
+    url: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
+    access: open
+    evidence_level: uspstf-a
+    year: 2021
+    rationale: >
+      Fills the missing US government and preventive-care gap. The USPSTF
+      recommendation applies to adults 18 years or older and explicitly notes
+      less frequent screening for lower-risk adults aged 18 to 39.
+    search_terms:
+      - "USPSTF hypertension in adults screening 2021"
+      - "young adults 18 to 39 hypertension screening USPSTF"
+
+  - name: cms165-controlling-high-blood-pressure
+    title: "CMS165v14 / MIPS Quality ID 236 — Controlling High Blood Pressure"
+    type: measure-library
+    url: https://ecqi.healthit.gov/ecqm/ec/2026/cms0165v14
+    access: open
+    evidence_level: n/a
+    year: 2026
+    rationale: >
+      Adds the CMS value-based care and quality-measure perspective. This
+      measure is directly relevant to informatics work because it defines the
+      adult hypertension denominator, outcome threshold, and computable data
+      elements used in reporting and CDS.
+    search_terms:
+      - "CMS165v14 controlling high blood pressure"
+      - "MIPS Quality ID 236 hypertension"
+
+  - name: meps-hypertension-expenditures
+    title: "AHRQ MEPS Statistical Brief #487: Expenditures for Commonly Treated Conditions among Adults Age 18 and Older in the U.S. Civilian Noninstitutionalized Population, 2013"
+    type: health-economics
+    url: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
+    access: open
+    evidence_level: n/a
+    year: 2016
     rationale: >
-      Landmark RCT supporting intensive BP targets; note exclusion of
-      adults < 50 limits direct applicability to this age group.
-    open_access: true
-status: draft
+      Fills the missing health-economics gap with a primary US expenditure
+      source. MEPS gives treated prevalence and spending context for
+      hypertension that can support business-case, utilization, and value-based
+      care framing for younger adults.
+    search_terms:
+      - "MEPS hypertension expenditures adults"
+      - "AHRQ hypertension treated prevalence expenditures"
+
+  - name: loinc-blood-pressure-observation-codes
+    title: "LOINC 8480-6 / 8462-4 — Systolic and Diastolic Blood Pressure Observation Codes"
+    type: terminology
+    url: https://loinc.org/8480-6/
+    access: open
+    evidence_level: reference-standard
+    year: 2025
+    notes: "Companion diastolic code: https://loinc.org/8462-4/"
+    rationale: >
+      Required terminology source for interoperable capture of systolic and
+      diastolic blood pressure observations in US Core, eCQM logic, and
+      downstream computable artifacts.
+    search_terms:
+      - "LOINC 8480-6 systolic blood pressure"
+      - "LOINC 8462-4 diastolic blood pressure"
diff --git a/topics/young-adult-hypertension/process/plans/discovery-readout.md b/topics/young-adult-hypertension/process/plans/discovery-readout.md
new file mode 100644
index 0000000000000000000000000000000000000000..35d12f7fac1b84e4605539c385a6009aaa3fd816
--- /dev/null
+++ b/topics/young-adult-hypertension/process/plans/discovery-readout.md
@@ -0,0 +1,76 @@
+> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
+> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
+> The structured source list in `discovery-plan.yaml` is the single source of truth.
+
+## Domain Advice
+
+### CMS Program Alignment
+
+Young-adult hypertension has a clear CMS and informatics footprint even though
+the target cohort skews younger than many traditional Medicare workflows.
+`CMS165v14 / MIPS Quality ID 236` covers adults 18-85 with essential
+hypertension and therefore supplies directly reusable denominator and numerator
+logic for registry design, CDS, and quality reporting.
+
+### SDOH Relevance
+
+Relevant Gravity-aligned domains include financial strain, food insecurity,
+housing instability, transportation barriers, and health behaviors. For young
+adults, insurance churn, employment instability, and disrupted primary-care
+continuity can affect both screening and sustained treatment.
+
+### Health Equity
+
+Earlier-onset and less-controlled hypertension disproportionately affects some
+racialized populations, especially Black adults, and may be worsened by access
+barriers, neighborhood stressors, and variable primary-care engagement. Equity
+analyses should be designed early rather than appended after measure logic is
+complete.
+
+### Quality Measure Landscape
+
+In addition to ACC/AHA and USPSTF guidance, the practical measurement anchor is
+`CMS165v14 / MIPS 236`. For informatics implementation, this measure is more
+actionable than narrative guidance alone because it defines computable adult
+hypertension control logic and associated data elements.
+
+### Terminology Systems
+
+Minimum terminology set for this topic:
+
+- `SNOMED CT` for essential hypertension and related problem-list concepts
+- `LOINC` for systolic and diastolic blood pressure observations
+- `ICD-10-CM` for claims-facing cohort identification
+- `RxNorm` for antihypertensive medication classes
+
+### Health Economics
+
+Hypertension is a high-prevalence chronic condition with policy significance
+even when per-person spending is lower than some other chronic diseases.
+`MEPS` is an appropriate primary economics source because it supports national
+prevalence, utilization, and payer-mix framing for value-based care arguments.
+
+## Research Expansion Suggestions
+
+1. **Masked hypertension and ambulatory confirmation in younger adults** —
+   young adults may have missed or delayed diagnosis if office-only screening is
+   used.
+   Start with: `rh-skills search pubmed --query "masked hypertension ambulatory blood pressure monitoring young adults" --max 10`
+
+2. **Health equity in early-onset hypertension** — disparities in onset,
+   diagnosis, and control can materially affect cohort design and follow-up
+   logic.
+   Start with: `rh-skills search pubmed --query "young adult hypertension disparities race ethnicity" --max 10`
+
+3. **Home blood pressure monitoring implementation** — confirmation and
+   longitudinal control workflows depend on validated home devices and patient
+   adherence.
+   Start with: `rh-skills search pubmed --query "home blood pressure monitoring implementation young adults primary care" --max 10`
+
+4. **Transition from adolescent to adult hypertension care** — transitional
+   populations may have different thresholds, workups, and documentation needs.
+   Start with: `rh-skills search pubmed --query "transition adolescent to adult hypertension care" --max 10`
+
+5. **Productivity and long-horizon economic burden of early hypertension** —
+   early-onset disease can affect lifetime cost and cardiovascular risk.
+   Start with: `rh-skills search pubmed --query "young adult hypertension economic burden productivity costs" --max 10`

codex
Updated [discovery-plan.yaml](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/plans/discovery-plan.yaml), created the derived [discovery-readout.md](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/plans/discovery-readout.md), added a [notes stub](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/notes.md), and initialized [RESEARCH.md](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/RESEARCH.md).

The plan was normalized from the older schema and expanded from 3 to 7 sources. I added the missing gap-fillers: USPSTF hypertension screening (2021), CMS165v14 / MIPS 236, AHRQ MEPS Statistical Brief #487 for health economics, and LOINC blood-pressure terminology. I also added `search_terms` and `access` metadata to the existing guideline/RCT entries and recorded the offline PubMed/PMC/ClinicalTrials queries because live API search was blocked in this sandbox.

`rh-skills validate --plan topics/young-adult-hypertension/process/plans/discovery-plan.yaml` exited `0` with: `VALID — all checks passed`.

```text
▸ rh-inf-discovery  young-adult-hypertension
  Step:   11 — Save Checkpoint · Complete
  Plan:   saved · 7 sources
  Verify: PASS
  Next:   rh-inf-ingest plan young-adult-hypertension
```

**What would you like to do next?**

A) Run `rh-inf-ingest plan young-adult-hypertension`  
B) Return to the discovery session to revise sources  
C) Ask for a quick review of the final source mix before handoff
diff --git a/RESEARCH.md b/RESEARCH.md
new file mode 100644
index 0000000000000000000000000000000000000000..4b5afafeca337ef73ad08a9de120d3b26439fd42
--- /dev/null
+++ b/RESEARCH.md
@@ -0,0 +1,5 @@
+# Research Portfolio
+
+| Topic | Stage | Sources | Updated | Notes |
+|---|---|---:|---|---|
+| young-adult-hypertension | L1 discovery | 7 | 2026-04-16 | Resumed partial discovery plan; added USPSTF, CMS165v14, MEPS, and LOINC sources. |
diff --git a/topics/young-adult-hypertension/process/notes.md b/topics/young-adult-hypertension/process/notes.md
new file mode 100644
index 0000000000000000000000000000000000000000..9acf840cae9638ddb78313101eb813dcda870c01
--- /dev/null
+++ b/topics/young-adult-hypertension/process/notes.md
@@ -0,0 +1,7 @@
+# young-adult-hypertension notes
+
+- Discovery session resumed on 2026-04-16.
+- Normalized the existing plan to the current schema and added missing USPSTF,
+  CMS measure, health-economics, and terminology sources.
+- Live PubMed, PMC, and ClinicalTrials.gov searches were unavailable in this
+  sandbox; offline queries are recorded in `process/plans/discovery-plan.yaml`.
diff --git a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
index 5068ecee324801787a97bb301b39f88e38fe9ceb..08d37a9dfc5063e9cb6366dc86c31a9f26c0b4bc
--- a/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
+++ b/topics/young-adult-hypertension/process/plans/discovery-plan.yaml
@@ -1,31 +1,133 @@
 topic: young-adult-hypertension
+version: "1.0"
+created: "2026-04-16"
+last_updated: "2026-04-16"
+status: draft
 clinical_question: >
-  What are the diagnostic thresholds, treatment targets, and lifestyle
-  interventions for hypertension in adults aged 18–39?
+  What are the diagnostic thresholds, treatment targets, screening intervals,
+  and lifestyle interventions most relevant to hypertension in adults aged
+  18–39, and how should those rules be represented for quality measurement,
+  CDS, and interoperable data capture?
+notes:
+  - >
+    Resumed an existing partial plan on 2026-04-16 and normalized it to the
+    current discovery-plan schema before re-validation.
+  - >
+    PubMed live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    PMC live search was unavailable in this sandbox; offline query recorded:
+    "young adult hypertension economic burden healthcare expenditures".
+  - >
+    ClinicalTrials.gov live search was unavailable in this sandbox; offline
+    query recorded: "young adult hypertension".
 sources:
-  - id: acc-aha-2017-hypertension
+  - name: acc-aha-2017-hypertension
     title: "2017 ACC/AHA Guideline for High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065
-    type: clinical-guideline
+    access: open
     evidence_level: ia
+    year: 2017
     rationale: >
-      Primary US clinical guideline redefining hypertension thresholds;
-      directly addresses young-adult treatment targets.
-    open_access: true
-  - id: jnc8-hypertension-management
-    title: "2014 Evidence-Based Guideline for High Blood Pressure (JNC 8)"
+      Primary US clinical guideline redefining hypertension thresholds and
+      treatment targets. It anchors adult threshold logic that affects young
+      adult diagnosis, staging, and follow-up.
+    search_terms:
+      - "2017 ACC AHA hypertension guideline"
+      - "young adults hypertension threshold ACC AHA"
+
+  - name: jnc8-hypertension-management
+    title: "2014 Evidence-Based Guideline for Management of High Blood Pressure in Adults"
+    type: clinical-guideline
     url: https://jamanetwork.com/journals/jama/fullarticle/1791497
-    type: clinical-guideline
+    access: authenticated
     evidence_level: ia
-    rationale: Previous guideline; useful for threshold comparison.
-    open_access: false
-  - id: sprint-trial
-    title: "SPRINT: Systolic BP Intervention Trial"
-    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    year: 2014
+    notes: "JAMA abstract page is open; full text may require institutional or library access."
+    rationale: >
+      Previous major US guideline, useful for threshold and treatment-target
+      comparison when building longitudinal decision support or explaining
+      historical variation in care policies.
+    search_terms:
+      - "JNC 8 hypertension guideline 2014"
+      - "adult hypertension threshold comparison JNC 8"
+
+  - name: sprint-trial
+    title: "A Randomized Trial of Intensive versus Standard Blood-Pressure Control"
     type: rct
+    url: https://www.nejm.org/doi/10.1056/NEJMoa1511939
+    access: authenticated
     evidence_level: ib
+    year: 2015
+    notes: "NEJM abstract page is open; institutional access may be needed for the full article."
+    rationale: >
+      Landmark RCT supporting intensive blood pressure control. Applicability to
+      adults under age 50 is limited, but the trial remains important context
+      for target-setting logic and escalation discussions.
+    search_terms:
+      - "SPRINT trial blood pressure control"
+      - "intensive blood pressure target randomized trial"
+
+  - name: uspstf-hypertension-screening-2021
+    title: "Recommendation: Hypertension in Adults: Screening"
+    type: guideline
+    url: https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/hypertension-in-adults-screening
+    access: open
+    evidence_level: uspstf-a
+    year: 2021
+    rationale: >
+      Fills the missing US government and preventive-care gap. The USPSTF
+      recommendation applies to adults 18 years or older and explicitly notes
+      less frequent screening for lower-risk adults aged 18 to 39.
+    search_terms:
+      - "USPSTF hypertension in adults screening 2021"
+      - "young adults 18 to 39 hypertension screening USPSTF"
+
+  - name: cms165-controlling-high-blood-pressure
+    title: "CMS165v14 / MIPS Quality ID 236 — Controlling High Blood Pressure"
+    type: measure-library
+    url: https://ecqi.healthit.gov/ecqm/ec/2026/cms0165v14
+    access: open
+    evidence_level: n/a
+    year: 2026
+    rationale: >
+      Adds the CMS value-based care and quality-measure perspective. This
+      measure is directly relevant to informatics work because it defines the
+      adult hypertension denominator, outcome threshold, and computable data
+      elements used in reporting and CDS.
+    search_terms:
+      - "CMS165v14 controlling high blood pressure"
+      - "MIPS Quality ID 236 hypertension"
+
+  - name: meps-hypertension-expenditures
+    title: "AHRQ MEPS Statistical Brief #487: Expenditures for Commonly Treated Conditions among Adults Age 18 and Older in the U.S. Civilian Noninstitutionalized Population, 2013"
+    type: health-economics
+    url: https://meps.ahrq.gov/data_files/publications/st487/stat487.shtml
+    access: open
+    evidence_level: n/a
+    year: 2016
     rationale: >
-      Landmark RCT supporting intensive BP targets; note exclusion of
-      adults < 50 limits direct applicability to this age group.
-    open_access: true
-status: draft
+      Fills the missing health-economics gap with a primary US expenditure
+      source. MEPS gives treated prevalence and spending context for
+      hypertension that can support business-case, utilization, and value-based
+      care framing for younger adults.
+    search_terms:
+      - "MEPS hypertension expenditures adults"
+      - "AHRQ hypertension treated prevalence expenditures"
+
+  - name: loinc-blood-pressure-observation-codes
+    title: "LOINC 8480-6 / 8462-4 — Systolic and Diastolic Blood Pressure Observation Codes"
+    type: terminology
+    url: https://loinc.org/8480-6/
+    access: open
+    evidence_level: reference-standard
+    year: 2025
+    notes: "Companion diastolic code: https://loinc.org/8462-4/"
+    rationale: >
+      Required terminology source for interoperable capture of systolic and
+      diastolic blood pressure observations in US Core, eCQM logic, and
+      downstream computable artifacts.
+    search_terms:
+      - "LOINC 8480-6 systolic blood pressure"
+      - "LOINC 8462-4 diastolic blood pressure"
diff --git a/topics/young-adult-hypertension/process/plans/discovery-readout.md b/topics/young-adult-hypertension/process/plans/discovery-readout.md
new file mode 100644
index 0000000000000000000000000000000000000000..35d12f7fac1b84e4605539c385a6009aaa3fd816
--- /dev/null
+++ b/topics/young-adult-hypertension/process/plans/discovery-readout.md
@@ -0,0 +1,76 @@
+> **Note:** This file is a narrative readout derived from `discovery-plan.yaml`.
+> It is generated by the `rh-inf-discovery` skill and should not be edited directly.
+> The structured source list in `discovery-plan.yaml` is the single source of truth.
+
+## Domain Advice
+
+### CMS Program Alignment
+
+Young-adult hypertension has a clear CMS and informatics footprint even though
+the target cohort skews younger than many traditional Medicare workflows.
+`CMS165v14 / MIPS Quality ID 236` covers adults 18-85 with essential
+hypertension and therefore supplies directly reusable denominator and numerator
+logic for registry design, CDS, and quality reporting.
+
+### SDOH Relevance
+
+Relevant Gravity-aligned domains include financial strain, food insecurity,
+housing instability, transportation barriers, and health behaviors. For young
+adults, insurance churn, employment instability, and disrupted primary-care
+continuity can affect both screening and sustained treatment.
+
+### Health Equity
+
+Earlier-onset and less-controlled hypertension disproportionately affects some
+racialized populations, especially Black adults, and may be worsened by access
+barriers, neighborhood stressors, and variable primary-care engagement. Equity
+analyses should be designed early rather than appended after measure logic is
+complete.
+
+### Quality Measure Landscape
+
+In addition to ACC/AHA and USPSTF guidance, the practical measurement anchor is
+`CMS165v14 / MIPS 236`. For informatics implementation, this measure is more
+actionable than narrative guidance alone because it defines computable adult
+hypertension control logic and associated data elements.
+
+### Terminology Systems
+
+Minimum terminology set for this topic:
+
+- `SNOMED CT` for essential hypertension and related problem-list concepts
+- `LOINC` for systolic and diastolic blood pressure observations
+- `ICD-10-CM` for claims-facing cohort identification
+- `RxNorm` for antihypertensive medication classes
+
+### Health Economics
+
+Hypertension is a high-prevalence chronic condition with policy significance
+even when per-person spending is lower than some other chronic diseases.
+`MEPS` is an appropriate primary economics source because it supports national
+prevalence, utilization, and payer-mix framing for value-based care arguments.
+
+## Research Expansion Suggestions
+
+1. **Masked hypertension and ambulatory confirmation in younger adults** —
+   young adults may have missed or delayed diagnosis if office-only screening is
+   used.
+   Start with: `rh-skills search pubmed --query "masked hypertension ambulatory blood pressure monitoring young adults" --max 10`
+
+2. **Health equity in early-onset hypertension** — disparities in onset,
+   diagnosis, and control can materially affect cohort design and follow-up
+   logic.
+   Start with: `rh-skills search pubmed --query "young adult hypertension disparities race ethnicity" --max 10`
+
+3. **Home blood pressure monitoring implementation** — confirmation and
+   longitudinal control workflows depend on validated home devices and patient
+   adherence.
+   Start with: `rh-skills search pubmed --query "home blood pressure monitoring implementation young adults primary care" --max 10`
+
+4. **Transition from adolescent to adult hypertension care** — transitional
+   populations may have different thresholds, workups, and documentation needs.
+   Start with: `rh-skills search pubmed --query "transition adolescent to adult hypertension care" --max 10`
+
+5. **Productivity and long-horizon economic burden of early hypertension** —
+   early-onset disease can affect lifetime cost and cardiovascular risk.
+   Start with: `rh-skills search pubmed --query "young adult hypertension economic burden productivity costs" --max 10`

tokens used
127,882
Updated [discovery-plan.yaml](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/plans/discovery-plan.yaml), created the derived [discovery-readout.md](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/plans/discovery-readout.md), added a [notes stub](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/topics/young-adult-hypertension/process/notes.md), and initialized [RESEARCH.md](/var/folders/w_/1kxcn0r925ng0ml6mwd78z5m0000gp/T/rh-skills-eval-OUtSst/RESEARCH.md).

The plan was normalized from the older schema and expanded from 3 to 7 sources. I added the missing gap-fillers: USPSTF hypertension screening (2021), CMS165v14 / MIPS 236, AHRQ MEPS Statistical Brief #487 for health economics, and LOINC blood-pressure terminology. I also added `search_terms` and `access` metadata to the existing guideline/RCT entries and recorded the offline PubMed/PMC/ClinicalTrials queries because live API search was blocked in this sandbox.

`rh-skills validate --plan topics/young-adult-hypertension/process/plans/discovery-plan.yaml` exited `0` with: `VALID — all checks passed`.

```text
▸ rh-inf-discovery  young-adult-hypertension
  Step:   11 — Save Checkpoint · Complete
  Plan:   saved · 7 sources
  Verify: PASS
  Next:   rh-inf-ingest plan young-adult-hypertension
```

**What would you like to do next?**

A) Run `rh-inf-ingest plan young-adult-hypertension`  
B) Return to the discovery session to revise sources  
C) Ask for a quick review of the final source mix before handoff

*(session end)*
