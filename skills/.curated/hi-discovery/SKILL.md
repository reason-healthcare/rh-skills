---
# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED FRONTMATTER — Level 1 disclosure (loaded into system prompt at startup)
# ─────────────────────────────────────────────────────────────────────────────
name: "hi-discovery"
description: >
  Interactive research assistant for healthcare informatics evidence discovery.
  Searches PubMed, PMC, ClinicalTrials.gov, and curated government/society
  sources to build an evidence-based discovery plan (L1 → L2 lifecycle stage).
  Modes: session · verify.
compatibility: "hi-skills-framework >= 0.1.0"
context_files:
  - reference.md          # domain advice checklist, source taxonomies, US gov coverage
  - examples/plan.md      # worked example: diabetes-ccm discovery-plan.md
  - examples/output.md    # worked example: session transcript excerpt
metadata:
  author: "HI Skills Framework"
  version: "1.0.0"
  source: "skills/.curated/hi-discovery/SKILL.md"
  lifecycle_stage: "l1-discovery"
  reads_from:
    - tracking.yaml
    - RESEARCH.md
    - topics/<name>/process/research.md
  writes_via_cli:
    - "hi search pubmed"
    - "hi search pmc"
    - "hi search clinicaltrials"
    - "hi init"
    - "hi validate --plan"
---

# hi-discovery

<!-- ─────────────────────────────────────────────────────────────────────────
  LEVEL 2 DISCLOSURE — full instructions, loaded when skill is triggered.
  ───────────────────────────────────────────────────────────────────────── -->

## Overview

`hi-discovery` is the **L1 evidence discovery** stage of the HI lifecycle. It
guides a clinical informaticist through finding, evaluating, and documenting
evidence-based source material for a healthcare informatics topic. The result is
a `discovery-plan.md` that `hi-ingest` consumes to acquire and register all
sources, and that downstream skills (`hi-extract`, `hi-formalize`) use to
advance artifacts toward L2 and L3.

The skill acts as an **interactive research assistant** — it does not stop at a
single search pass. After each pass the agent explicitly prompts the user with
expansion suggestions and awaits direction. The plan is a **living document**
written to disk only when the user approves it.

**Guiding principle**: Discovery is a pure research and planning activity.
All searches are delegated to `hi` CLI commands. All clinical reasoning, source
evaluation, and research synthesis happen in this skill. Discovery does **not**
download or register any source files — that is entirely `hi-ingest`'s
responsibility. This means the plan can be re-run, revised, and reviewed before
any file-system side effects occur.

---

## User Input

```text
$ARGUMENTS
```

Inspect `$ARGUMENTS` before proceeding. The first word is the **mode**
(`session` or `verify`). The second positional argument is `<topic>` — the
kebab-case topic identifier previously initialized with `hi init`.

| Mode | Arguments | Example |
|------|-----------|---------|
| `session` | `<topic> [--force]` | `session diabetes-ccm` |
| `verify` | `<topic>` | `verify diabetes-ccm` |

- `--force`: overwrite an existing `discovery-plan.md` (session mode only).
- If `$ARGUMENTS` is empty or the mode is unrecognized, print this table and exit.

---

## Pre-Execution Checks

Before entering either mode, verify the topic is initialized:

```sh
hi status show <topic>
```

If the topic does not exist, print a helpful error and suggest `hi init <topic>`.

For **session** mode only: check whether a plan already exists:

```sh
ls topics/<topic>/process/plans/discovery-plan.md 2>/dev/null
```

- If it exists **and** `--force` was not passed: warn the user, offer to load it
  for continuation or start fresh with `--force`. Wait for the user's choice.
- If it exists **and** `--force` was passed: proceed, overwriting on save.
- If it does not exist: proceed normally.

---

## Output Contract

Every agent response during a `session` MUST end with a status block in this
exact format:

```
─── hi-discovery · <topic> ──────────────────────────────────
  Step:   <N> — <Step Name>
  Plan:   <N source(s) in memory | saved · <N> sources>
  Next:   <concrete command or choice presented to the user>
─────────────────────────────────────────────────────────────
```

Rules:
- **Always present** — every response, without exception. The user must never
  have to ask "what do I do next?"
- **Step** reflects the current step number and name from the session workflow.
  Use `Complete` suffix once a step is fully done (e.g., `3 — ClinicalTrials
  Search · Complete`).
- **Plan** shows live source count while unsaved; switches to `saved ·` once
  `discovery-plan.md` has been written.
- **Next** must be a concrete, copy-pasteable command OR a specific choice
  prompt (e.g., `approve list / modify / add sources`). Never vague.
- After `verify` mode, the block uses `Mode: verify` and `Result: PASS / FAIL`
  in place of Step/Plan, and `Next` gives the exact `hi-ingest` command on
  PASS or the specific fix required on FAIL.

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

This advice is captured in the **Domain Advice** section of `discovery-plan.md`
and guides which sources to prioritize.

Emit status block:
```
  Step:   1 — Domain Advice · Complete
  Plan:   0 sources in memory
  Next:   Step 2 — run PubMed/PMC searches
```

### Step 2 — PubMed Search

```sh
hi search pubmed --query "<terms>" --max 20 --json
hi search pmc   --query "<terms>" --max 20 --json
```

Choose search terms based on the topic name, clinical synonyms, and domain
advice from Step 1. Run at least one PubMed search AND one PMC search per
session.

Parse the JSON results. For each result evaluate:

- **Relevance** to the topic
- **Evidence level** (see `reference.md` Evidence Level Taxonomy)
- **Access**: PMC articles are `open`; PubMed abstracts are `open` (URL to
  abstract); full-text may require institutional access → `authenticated`

Emit status block:
```
  Step:   2 — PubMed/PMC Search · Complete
  Plan:   <N> sources in memory
  Next:   Step 3 — ClinicalTrials.gov search
```

### Step 3 — ClinicalTrials.gov Search

```sh
hi search clinicaltrials --query "<terms>" --max 20 --json
```

Include active or completed trials relevant to the topic. These are `registry`
type with `evidence_level: n/a` (trials are not yet evidence until published).

Emit status block:
```
  Step:   3 — ClinicalTrials.gov Search · Complete
  Plan:   <N> sources in memory
  Next:   Step 4 — US government sources
```

### Step 4 — US Government Healthcare Sources

For any topic with a US clinical care or population health angle, **actively
search** the following (not via `hi search` — reason from your knowledge and
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
`hi-ingest`.

Ask the user: approve all, modify the list, or add/remove sources?
Incorporate feedback and loop back if needed.

Emit status block:
```
  Step:   7 — Source Review
  Plan:   <N> sources in memory
  Next:   approve list / modify / add sources
```

### Step 8 — Access Advisories

For each **approved** `access: authenticated` or `access: manual` source, print
an access advisory so the user knows what to gather before running `hi-ingest`:

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
3. The first `hi` command the user would run to explore it

Cover at minimum (when applicable):
- (a) Adjacent comorbidities or closely related conditions
- (b) Healthcare economics angle (cost, burden, cost-effectiveness)
- (c) Health equity or disparate-population angle
- (d) Implementation science gap (barriers to guideline adoption)
- (e) Data/registry gap (limited evidence or active trial inquiry)

**Do NOT add suggestions to `sources[]` automatically.** They are offered for
the user to act on.

Emit status block:
```
  Step:   9 — Expansion Suggestions · Complete
  Plan:   <N> sources in memory
  Next:   explore an expansion area / save the plan
```

### Step 10 — Interactive Prompt

After presenting the plan and suggestions, explicitly ask:

1. Which (if any) expansion areas to explore next?
2. Are there sources to add, remove, or modify?
3. Ready to save the plan? (Or continue researching?)

If the user wants to explore an expansion area, loop back to Steps 2–9 for that
area and merge the findings into the living plan.

Emit status block reflecting current state, e.g.:
```
  Step:   10 — Awaiting Direction
  Plan:   <N> sources in memory
  Next:   explore "<area>" / save the plan / modify list
```

### Step 11 — Save Checkpoint

When the user approves saving:

1. Write `topics/<topic>/process/plans/discovery-plan.md` (see Level 3 below
   for the required format)
2. Update `process/research.md` — move all approved sources to Pending Review
   (awaiting `hi-ingest`); move rejected sources to Ruled Out
3. Update `RESEARCH.md` root portfolio row for the topic (source count, date)
4. Create `process/conflicts.md` stub (create-unless-exists)

After saving, recommend:

```sh
hi-discovery verify <topic>
```

Emit status block:
```
  Step:   11 — Save Checkpoint · Complete
  Plan:   saved · <N> sources
  Next:   hi-discovery verify <topic>
```

### Step 12 — Verify Recommendation

Remind the user that `verify` mode runs non-destructive checks on the saved
plan. Once it passes, the plan is ready to hand off to `hi-ingest`, which
handles all source acquisition (downloading open sources, registering manual
files) in a single dedicated step.

---

## Mode: `verify`

**Read-only** — no file writes, no `tracking.yaml` modifications.

```sh
hi validate --plan topics/<topic>/process/plans/discovery-plan.md
```

Report the output verbatim. Exit with the same code as `hi validate --plan`.

On exit 0, emit:
```
─── hi-discovery · <topic> ──────────────────────────────────
  Mode:   verify
  Result: PASS
  Next:   hi-ingest session <topic>
─────────────────────────────────────────────────────────────
```

On exit 1, emit:
```
─── hi-discovery · <topic> ──────────────────────────────────
  Mode:   verify
  Result: FAIL — <N> check(s) failed
  Next:   fix: <specific issue(s) listed above>, then re-run verify
─────────────────────────────────────────────────────────────
```

---

## Level 3 — discovery-plan.md Format

<!-- LEVEL 3 DISCLOSURE — detailed schemas, loaded on-demand -->

The discovery plan is a Markdown file with YAML frontmatter followed by prose
sections. This exact structure is required for `hi validate --plan` to pass.

```markdown
---
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
---

## Domain Advice

<Prose addressing the Domain Advice Checklist from reference.md:
 CMS program alignment, SDOH relevance, health equity, quality measure landscape,
 terminology systems, health economics angle.>

## Research Expansion Suggestions

1. **<Adjacent Topic>** — <Why relevant to primary topic>.
   Start with: `hi search pubmed --query "<terms>" --max 20`

2. ...
```

See `examples/plan.md` for a complete worked example.

---

## Error Handling

| Condition | Action |
|-----------|--------|
| `hi status show` exits non-zero | Print error, suggest `hi init <topic>`, exit |
| Fewer than 5 sources after all searches | Search additional databases; do not save |
| More than 25 sources | Select top 25, log extras in expansion suggestions |
| `hi validate --plan` exits 1 | Report failures; do not proceed to ingest |
| Plan already exists (no `--force`) | Offer continuation or fresh start |
