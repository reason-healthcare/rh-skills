---
# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED FRONTMATTER — Level 1 disclosure (loaded into system prompt at startup)
# ─────────────────────────────────────────────────────────────────────────────
name: "rh-inf-discovery"
description: >
  Interactive research assistant for healthcare informatics evidence discovery.
  Searches PubMed, PMC, ClinicalTrials.gov, and curated government/society
  sources to build an evidence-based discovery plan (L1 → L2 lifecycle stage).
  Modes: plan · verify.
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
    - RESEARCH.md
    - sources/
  reads_via_cli:
    - "rh-skills search pubmed"
    - "rh-skills search pubmed --offline"
    - "rh-skills search pmc"
    - "rh-skills search clinicaltrials"
    - "rh-skills source scan"
    - "rh-skills validate --plan"
  writes_via_cli:
    - "rh-skills source add"
    - "rh-skills source download --url"
---

# rh-inf-discovery


## Overview

`rh-inf-discovery` is the **L1 evidence discovery** stage of the lifecycle. It
guides a clinical informaticist through finding, evaluating, and documenting
evidence-based source material for a clinical research area. The result is
a `discovery-plan.yaml` (structured source list, the single source of truth),
`discovery-readout.md` (generated domain narrative), and downloaded open-access
source files. `rh-inf-ingest` consumes these to normalize, classify, and annotate
sources and infer the appropriate topic(s).

The skill acts as an **interactive research assistant** — it does not stop at a
single search pass. After each pass the agent explicitly prompts the user with
expansion suggestions and awaits direction. The plan is a **living document**
written to disk only when the user approves it.

**Discovery is topic-free.** No `rh-skills init` call is required before or
during discovery. Topic naming and initialization happen later in `rh-inf-ingest`
after sources are normalized.

---

## Guiding Principles

- **Discovery is pure research.** All searches are delegated to `rh-skills` CLI commands.
  All clinical reasoning, source evaluation, and research synthesis happen in
  this skill.
- **Download at the end, not during research.** Source files are only downloaded
  after the user approves and saves the plan (Step 12). The plan can be freely
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
(`plan` or `verify`). The optional `--domain <label>` flag names the clinical
research area (freeform label used for status output and file naming — not a
tracked topic identifier).

| Mode | Arguments | Example |
|------|-----------|---------|
| `plan` | `[--domain <label>] [--force]` | `plan --domain diabetes-ccm` |
| `verify` | — | `verify` |

**Mode Defaulting**: If `$ARGUMENTS` is empty or contains only flags (no mode), default to `plan` mode.

- `--domain <label>`: optional freeform research area label used for status output and naming context. If omitted, infer from current research context.
- `--force`: overwrite existing `discovery-plan.yaml` and `discovery-readout.md` (plan mode only).
- If the mode is unrecognized (neither `plan` nor `verify`), print this table and exit with an error.

---

## Pre-Execution Checks

For **plan** mode only: check whether a plan already exists at the repo root:

```sh
ls discovery-plan.yaml 2>/dev/null
```

- If it exists **and** `--force` was not passed: warn the user, offer to load it
  for continuation or start fresh with `--force`. Wait for the user's choice.
- If it exists **and** `--force` was passed: proceed, overwriting on save.
- If it does not exist: proceed normally.

> **When continuing an existing plan:** Load the saved plan into memory as the
> starting `sources[]` list. Resume at Step 1 to refresh domain advice, then run
> Steps 2–5 to fill any identified gaps. **Always run the full Steps 7–10 before
> saving** — source review table, access advisories (for any authenticated/manual
> sources), expansion suggestions, and interactive prompt. Do not skip these steps
> even when the session prompt is task-framed ("add them and re-validate") or when
> running in an automated eval context.

---

## Mode: `plan`

The session is an **interactive research loop**. Complete all steps; prompt the
user after each major pass before proceeding.

### Step 0 — Scan for Manually Placed Files

Before starting searches, check whether the user has pre-placed any source
files (PDFs, CSVs, etc.) in the `sources/` directory:

```sh
rh-skills source scan
```

Interpret the output:

- **UNTRACKED** files — the user has placed a file that is not yet in the plan.
  Read the filename and use `head -20 sources/<file>` (for text/CSV) to infer
  content. Preview each as an `access: manual` source entry via
  `rh-skills source add --dry-run --access manual ...` to generate and review
  the YAML snippet. Hold these entries in memory — do **not** use
  `--append-to-plan` here because no plan file exists yet. They are merged
  into `sources[]` when the plan is written in Step 11.
  Infer `--type` from extension: `.pdf`/`.md`/`.txt` → `document` or
  `clinical-guideline`; `.csv`/`.tsv`/`.xlsx` → `dataset`.
- **SHA-CHANGED** files — a previously tracked file has changed on disk.
  Warn the user and suggest re-running ingest to pick up changes.
- **TRACKED** files — already registered; nothing to do.

If `sources/` does not exist or is empty, skip this step silently and proceed
to Step 1.

Emit status block:
```
  Step:   0 — Manual File Scan · Complete
  Found:  <N> untracked, <N> SHA-changed, <N> tracked
  Plan:   <N> sources in memory
  Next:   Step 1 — Domain Advice
```

### Step 1 — Domain Advice

Read `reference.md` → **Domain Advice Checklist**. Present domain-specific
guidance for the research area, addressing all checklist items relevant to the domain:

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
present URLs for the user to confirm). **Do not use web search tools.** Supply URLs
from domain knowledge; if uncertain about a specific URL, record the field as `tbd`
with a note to verify rather than searching the web:

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
- At least one `terminology` entry (SNOMED, LOINC, ICD-10, RxNorm, etc.). Add a
  `terminology` source for **each** system explicitly named in the domain advice —
  one entry is the floor, not the target. For most clinical topics, domain advice
  will identify SNOMED CT, LOINC, ICD-10-CM, and RxNorm; each should have its own
  entry.
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
must retrieve. Open-access sources are downloaded in Step 12 of this discovery
workflow via `rh-skills source download --url ...`; authenticated/manual sources
remain advisory and are gathered by the user.

Ask the user to approve, modify, or add/remove sources.
Incorporate feedback and loop back if needed.

Emit status block:

> ```
> ▸ rh-inf-discovery  <domain>
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

Command usage boundary:
- Use `rh-skills source scan` during discovery for inventory and drift detection (`UNTRACKED`, `TRACKED`, `SHA-CHANGED`).
- Use `rh-skills ingest list-manual [<topic>]` during ingest plan as a registration pre-check to list untracked files and print per-file `rh-skills ingest implement ...` commands.

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
> ▸ rh-inf-discovery  <domain>
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

1. Write `discovery-plan.yaml` at the repo root — the structured source list
   (see Level 3 below for the required format)
2. Write `discovery-readout.md` at the repo root — the generated domain
   narrative (Domain Advice + Research Expansion Suggestions prose);
   add a note at the top that it is derived from `discovery-plan.yaml`
3. Update `RESEARCH.md` root portfolio row for the domain area (source count, date)

After saving, emit status block:

> ```
> ▸ rh-inf-discovery  <domain>
>   Step:   11 — Save Checkpoint · Complete
>   Plan:   saved · <N> sources → discovery-plan.yaml
>   Next:   Step 12 — Download open-access sources
> ```
> 
> **What would you like to do next?**
> 
> A) Proceed to download open-access sources now
> B) Return to the plan to revise sources
> 
> You can also ask for `rh-inf-status` at any time.

### Step 12 — Download Open-Access Sources

After the plan is saved, download all `access: open` sources immediately.
Launch one subagent per source **in parallel**:

```sh
rh-skills source download --url <url> --name <name> --type <source-type> [--topic <topic-slug>]
```

**Type passthrough policy**: For each open-access source, pass the source
`type` from `discovery-plan.yaml` into `source download --type` so tracking has
an initial classification hint at registration time. `rh-skills ingest classify`
remains authoritative and may refine or replace this value later.

**Topic passthrough**: If a topic slug is already established for this research domain — because it was provided in the session prompt, an existing topic was identified in `tracking.yaml`, or the user confirmed a slug during the session — pass `--topic <slug>` on every download call. This ensures sources are associated with the topic at registration time and are not left as orphaned root-level entries. If no topic slug is known, omit `--topic` and note in the status block that sources will need topic assignment during `rh-inf-ingest`.

**NEVER use curl, wget, Python requests, or any other download method.**
`rh-skills source download --url` is the only permitted download mechanism.

Once all subagents complete, display a summary:
```
Downloads complete:
  ✓ ada-guidelines-2024       sources/ada-guidelines-2024.pdf
  ✓ cms-ecqm-cms122           sources/cms-ecqm-cms122.html
  ⊘ cochrane-review           exit 3 — auth redirect (see auth_note)
  ⛔ nice-guidelines           exit 4 — network blocked (sandbox)
```

- Exit 3 → authentication redirect — print the `auth_note` advisory and skip
- Exit 2 → file already exists and checksum matches — skip (idempotent)
- Exit 1 → network error — report and continue
- Exit 4 → **sandbox network restriction** — outbound network is blocked.
  **Stop retrying downloads.** Inform the user:
  > "Downloads require outbound network access, which is blocked in this
  > sandbox. Please run the following commands in a shell with network access:"
   > Then list every blocked `rh-skills source download --url …` command (include `--topic <slug>` on each if a topic slug is known).

For `access: authenticated` or `access: manual` sources: print the `auth_note`
advisory only. Do not attempt to download them.

`--append-to-plan` boundary: use `rh-skills search ... --append-to-plan <topic>`
only when appending to an existing topic plan file. During the initial
discovery planning loop, keep entries in memory and write once in Step 11.

Emit status block:
```
  Step:   12 — Download · Complete
  Downloaded: <N> open · <M> skipped (auth) · <P> skipped (manual)
  Next:   Step 13 — Verify Recommendation
```

### Step 13 — Verify Recommendation

Remind the user that `verify` mode runs non-destructive checks on the saved
plan. Once it passes, the plan and downloaded sources are ready to hand off
to `rh-inf-ingest` for normalization, classification, and annotation.

---

## Mode: `verify`

**Read-only** — no file writes, no `tracking.yaml` modifications.

```sh
rh-skills validate --plan ./discovery-plan.yaml
```

Report the output verbatim. Exit with the same code as `rh-skills validate --plan`.

On exit 0, before emitting the status block, emit:

> Verification passed! Your discovery plan is well-formed and ready for `rh-inf-ingest`.
> 
> ```
> ▸ rh-inf-discovery  <domain>
>   Mode:    verify
>   Result:  PASS
>   Next:    rh-inf-ingest plan
> ```
> 
> **What would you like to do next?**
> 
> A) Run `rh-inf-ingest plan` — begin source acquisition
> B) Return to the discovery plan to revise sources
> 
> You can also ask for status `rh-inf-status` at any time.


On exit 1, emit:

> Verification failed. Please address the following issues in `discovery-plan.yaml`:
> 
> ```
> ▸ rh-inf-discovery  <domain>
>   Mode:    verify
>   Result:  FAIL — <N> check(s) failed
>   Next:    fix: <specific issue(s) listed above>, then re-run verify
> ```
> 
> **What would you like to do next?**
> 
> A) Fix the listed issues and re-run `rh-inf-discovery verify`
> B) Return to the plan to modify sources
> 
> You can also ask for status `rh-inf-status` at any time.

---

## Level 3 — Discovery Plan Format

<!-- LEVEL 3 DISCLOSURE — detailed schemas, loaded on-demand -->

The discovery plan is **two files** written to the same directory:

### `discovery-plan.yaml` — Structured Source List

Pure YAML. This is what `rh-skills validate --plan` and `rh-inf-ingest` operate on.

```yaml
date: "YYYY-MM-DD"
domain: "<freeform research area label>"   # optional, from --domain flag or inferred
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
| Fewer than 5 sources after all searches | Search additional databases; do not save |
| More than 25 sources | Select top 25, log extras in expansion suggestions |
| `rh-skills validate --plan` exits 1 | Report failures; do not proceed to ingest |
| Plan already exists (no `--force`) | Offer continuation or fresh start |
| `rh-skills search` network error | Retry with `--offline` flag; mark step `SKIPPED (offline)`; continue with domain knowledge |

## CLI Quick Reference

| Command | Purpose |
|---------|---------|
| `rh-skills search pubmed --query "..." --json` | Search PubMed (live) |
| `rh-skills search pubmed --query "..." --append-to-plan <topic>` | Append PubMed results to an existing topic plan |
| `rh-skills search pubmed --offline --query "..."` | Record query; get reference links (no network) |
| `rh-skills search pmc --query "..." --json` | Search PMC open-access (live) |
| `rh-skills search pmc --query "..." --append-to-plan <topic>` | Append PMC results to an existing topic plan |
| `rh-skills search clinicaltrials --query "..." --json` | Search ClinicalTrials.gov (live) |
| `rh-skills search clinicaltrials --query "..." --append-to-plan <topic>` | Append ClinicalTrials results to an existing topic plan |
| `rh-skills source scan` | List untracked/SHA-changed files in sources/ |
| `rh-skills source add --type <type> --title "..." --rationale "..."` | Add a single source entry |
| `rh-skills source add --dry-run ...` | Preview source entry without writing |
| `rh-skills schema show discovery-plan` | Show plan schema and allowed taxonomies |
| `rh-skills validate --plan <file>` | Validate a saved discovery plan |
| `rh-skills validate --plan -` | Validate via stdin (pipe or heredoc) |
