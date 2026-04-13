# Quickstart: `rh-inf-discovery` Skill

**A minimal worked example of a discovery session.**

---

## Prerequisites

```bash
# Install rh-skills CLI
uv pip install -e .

# Initialize a new topic
rh-skills init diabetes-ccm
# → creates topics/diabetes-ccm/process/ and tracking.yaml entry
# → creates RESEARCH.md at repo root (if not exists)
# → creates topics/diabetes-ccm/process/notes.md (stub — human-maintained)
```

---

## Step 1: Start a discovery session

Tell your agent (Claude, Copilot, Gemini) to activate the rh-inf-discovery skill:

```
Use the rh-inf-discovery skill to help me research sources for chronic care management in diabetes.
Topic: diabetes-ccm
```

The agent loads `skills/.curated/rh-inf-discovery/SKILL.md` and begins in `session` mode.

---

## Step 2: Agent provides domain advice

The agent responds with domain-specific research advice:

```
Before searching, here's what to consider for chronic care management in diabetes:
• Clinical guidelines: ADA Standards of Care, AACE/ACE guidelines
• CMS alignment: CCM CPT codes, Diabetes Prevention Program (DPP), MIPS quality measures
• SDOH factors: food insecurity, housing instability, health literacy
• Evidence hierarchy: prefer RCTs and systematic reviews for interventions
• Healthcare economics: total cost of diabetes care, CCM program ROI
...
```

---

## Step 3: Agent searches and returns sources

The agent calls `rh-skills search` commands internally:

```bash
# (run by agent, not user)
rh-skills search pubmed --query "chronic care management diabetes systematic review" --max 20 --json
rh-skills search pubmed --query "diabetes CCM quality measures CMS" --max 20 --json
rh-skills search clinicaltrials --query "diabetes chronic care management" --max 20 --json
rh-skills search pmc --query "diabetes population health intervention" --max 20 --json
```

The agent presents curated results:

```
Found 14 sources across PubMed, PMC, and ClinicalTrials.gov.

Open-access sources:
  [1] ADA Standards of Care 2024 — PMC open access
      Evidence: Level Ia (clinical guideline) | Type: clinical-guideline
      Rationale: Primary authoritative guidance for diabetes management

  [2] Systematic Review: CCM Programs and Diabetes Outcomes (JAMA, 2023) — PMC
      Evidence: Level Ia | Type: systematic-review
      Rationale: Directly addresses intervention effectiveness

Authenticated sources (requires institutional access):
  [3] NEJM — Empagliflozin vs. Standard Care (2022) — authenticated
      Note: Available via institutional library access or interlibrary loan

Government sources:
  [4] CMS Diabetes Prevention Program — open access
      Evidence: Level Ib (program evidence) | Type: government-program

Which sources do you want to include? [all / select numbers / none]
```

---

## Step 4: User selects sources; agent records access advisories

User: `include 1, 2, 4`

Agent records sources in the in-session plan and prints access advisories:
```
Open-access sources:
  ✓ ada-standards-2024         access: open   url: https://pmc.ncbi.nlm.nih.gov/articles/PMC...
  ✓ ccm-diabetes-jama-2023     access: open   url: https://pmc.ncbi.nlm.nih.gov/articles/PMC...
  ✓ cms-dpp-program            access: open   url: https://www.cms.gov/priorities/innovation/...

Authenticated sources (advisory):
  ⊘ nejm-empagliflozin-2022    access: authenticated
    Requires institutional access. Search: 'Empagliflozin Standard Care 2022'
    URL: https://www.nejm.org/...
    Add to discovery-plan.yaml with auth_note when confirmed accessible.

All sources are recorded in discovery-plan.yaml. rh-inf-ingest will handle acquisition.
```

---

## Step 5: Research Expansion Suggestions

```
Based on your current sources, consider expanding into:
1. Pediatric diabetes management — current evidence base is adult-focused
2. Health equity in diabetes outcomes — SDOH interactions not yet addressed
3. Remote monitoring / telehealth for CCM — growing evidence post-COVID
4. Cost-effectiveness of CCM vs. usual care — healthcare economics dimension
5. MIPS quality measure specifications for diabetes — CMS alignment

**What would you like to do next?**

> A) Explore an expansion area — tell me the number
> B) Add, remove, or modify sources
> C) Save the plan and move on to `rh-inf-ingest`
```

---

## Step 6: Save the plan

User: `save`

Agent writes `topics/diabetes-ccm/process/plans/discovery-plan.yaml` (machine-readable source list) and `topics/diabetes-ccm/process/plans/discovery-readout.md` (narrative), and updates research tracking:

```
✓ Discovery plan saved: topics/diabetes-ccm/process/plans/discovery-plan.yaml
✓ Discovery readout saved: topics/diabetes-ccm/process/plans/discovery-readout.md
  Sources: 3 (2 open-access, 1 government)
  Coverage warnings:
    ⚠ Health-economics source not included — consider adding for comprehensive coverage

Research tracking updated:
  RESEARCH.md: Active Topics row updated (3 sources, 2026-04-04)
```

---

## Step 7: Verify the plan (optional)

```bash
# (agent-run, or user-run directly)
rh-skills validate --plan topics/diabetes-ccm/process/plans/discovery-plan.yaml
```

Output:
```
✓ Schema valid
✓ 3 sources (above 5-source minimum? NO — below minimum: only 3)
⚠ Source count below minimum (5). Consider expanding discovery session.
⚠ health-economics source type not present
✓ All open-access sources have url populated
✓ All authenticated sources have auth_note
```

---

## Files produced by this quickstart

```
topics/diabetes-ccm/process/
├── plans/
│   ├── discovery-plan.yaml
│   └── discovery-readout.md
└── notes.md              (stub — human-maintained)

RESEARCH.md                  (updated by hi)
tracking.yaml                (updated by hi)
```

> Note: `sources/` files are produced by `rh-inf-ingest` (004), not by rh-inf-discovery.
```
