# Discovery Workflow Report

## Overview

The **rh-inf-discovery** skill is the **Level 1 (L1) evidence discovery** stage of the healthcare informatics lifecycle. It guides clinical informaticists through finding, evaluating, and documenting evidence-based source material for a clinical research area. The output is a `discovery-plan.yaml` (structured source registry) and `discovery-readout.md` (domain narrative) written to the **repo root** — no topic initialization required.

The skill acts as an **interactive research assistant** through a plan-based workflow. After each research pass, the agent prompts the user with expansion suggestions and awaits direction. The discovery plan is a living document written to disk only when the user approves it. After approving, the skill downloads all open-access sources.

**Discovery is topic-free.** `rh-skills init` is called later, during `rh-inf-ingest`, after sources are normalized and a topic name can be inferred. There is no `<topic>` argument to `rh-inf-discovery`.

**Key Principles:**
- Discovery is pure research — all searches delegated to CLI commands
- Downloads happen only after the user approves and saves the plan
- Single source of truth: `./discovery-plan.yaml` (repo root)
- Always close the loop with status blocks and clear next-step options

---

## CLI Commands

| Command | Purpose | Writes To |
|---------|---------|-----------|
| `rh-skills search pubmed --query "<terms>" [--max N] [--json] [--offline]` | Search PubMed peer-reviewed literature via NCBI E-utilities | None (stdout) |
| `rh-skills search pmc --query "<terms>" [--json] [--offline]` | Search PubMed Central (open-access full-text) | None (stdout) |
| `rh-skills search clinicaltrials --query "<terms>" [--max N] [--status S] [--json]` | Search ClinicalTrials.gov registry via REST API v2 | None (stdout) |
| `rh-skills source scan` | Scan for manually placed files in `sources/` | None (stdout) |
| `rh-skills source add --type TYPE --url URL [--name SLUG]` | Add a manual source entry to plan | `discovery-plan.yaml` |
| `rh-skills validate --plan <file>` | Validate discovery-plan.yaml structure | None (read-only) |
| `rh-skills source download --url <url> --name <name> [--topic <topic>]` | Download an open-access source after plan save | `sources/<name>.<ext>` |

**`--append-to-plan` boundary:** Use `rh-skills search ... --append-to-plan <topic>`
only when appending into an existing topic plan file. During an initial
discovery planning loop, keep entries in memory and save once at checkpoint.

---

## Source Types Supported

| Type | Examples | Evidence Level |
|------|----------|---------------|
| `guideline` | ADA Standards, ACC/AHA, USPSTF, NICE | grade-a, grade-b |
| `systematic-review` | Cochrane, AHRQ Evidence Reports | grade-a, ia |
| `rct` | Randomized controlled trials | grade-a, grade-b, ib |
| `cohort-study` | Prospective/retrospective cohorts | grade-b, grade-c |
| `terminology` | SNOMED CT, LOINC, ICD-10-CM, RxNorm | reference-standard |
| `value-set` | VSAC, FHIR ValueSets, PHIN VADS | reference-standard |
| `measure-library` | CMS eCQMs, HEDIS, MIPS/QPP, NQF | grade-b |
| `fhir-ig` | US Core, QI-Core, CARIN BB, Gravity SDOH | reference-standard |
| `cds-library` | CDS Hooks registry, OpenCDS | n/a |
| `sdoh-assessment` | PRAPARE, AHC HRSN, CDC SVI | n/a |
| `health-economics` | HCUP, MEPS, GBD, CEA Registry, ICER | grade-a |
| `government-program` | CMS CMMI, Medicaid, LCD/NCD, HRSA | n/a |
| `registry` | ClinicalTrials.gov, disease registries | n/a |
| `pubmed-article` | General PubMed/PMC articles | variable |

**Mandatory Constraints:**
- At least one `terminology` source required
- At least one `health-economics` source for chronic/preventive/CMS topics
- Minimum 5 sources total; maximum 25

---

## Workflow

```
1. SOURCE SCAN: rh-skills source scan
   ├─ Find untracked files in sources/
   ├─ Categorize as access:manual
   └─ Hold in memory for plan merge

2. DOMAIN ADVICE (from reference.md checklist)
   ├─ CMS program alignment (eCQMs, MIPS/QPP, Medicaid, CMMI)
   ├─ SDOH relevance (Gravity Project domains)
   ├─ Health equity considerations
   ├─ Quality measure landscape (HEDIS, NQF, Joint Commission)
   ├─ Terminology systems needed
   └─ Health economics angle

3. LITERATURE SEARCH
   ├─ rh-skills search pubmed --query "<terms>" --json
   ├─ rh-skills search pmc --query "<terms>" --json
   ├─ rh-skills search clinicaltrials --query "<terms>" --json
   └─ [--offline fallback with reference links if network unavailable]

4. MANUAL RESEARCH
   ├─ US Government sources (CMS, USPSTF, AHRQ, CDC)
   ├─ Medical society guidelines (ADA, ACC, etc.)
   └─ Specialty journals (flagged as authenticated)

5. BUILD LIVING PLAN (in-memory)
   ├─ Enforce constraints (5–25 sources, ≥1 terminology, etc.)
   ├─ Validate all fields: name, type, rationale, evidence_level, access
   └─ Present formatted source table to user

6. USER APPROVAL
   ├─ Review source table
   ├─ Modify / add / remove sources
   └─ Approve when satisfied

7. EXPANSION SUGGESTIONS
   ├─ 3–7 adjacent topics not already covered
   ├─ Cover: comorbidities, health econ, equity, data gaps
   └─ Option to explore any (loops back to Step 3)

8. SAVE CHECKPOINT
   ├─ Write ./discovery-plan.yaml (repo root)
   ├─ Write ./discovery-readout.md (repo root)
   ├─ Update RESEARCH.md portfolio row
   └─ Event: discovery_planned → tracking.yaml

9. DOWNLOAD OPEN-ACCESS SOURCES
   ├─ rh-skills source download --url <url> --name <name> [--topic <topic>] (parallel, one per source)
   ├─ Skip auth/manual sources (print advisories)
   └─ Report download summary

10. HANDOFF → rh-inf-ingest
```

---

## Key Files

| File | Role |
|------|------|
| `src/rh_skills/commands/search.py` | CLI implementation (~700 lines); pubmed, pmc, clinicaltrials subcommands |
| `skills/.curated/rh-inf-discovery/SKILL.md` | Skill definition; agent system prompt (12 steps + modes) |
| `skills/.curated/rh-inf-discovery/reference.md` | Domain advice checklists, source taxonomies, US gov URLs |
| `skills/.curated/rh-inf-discovery/examples/plan.yaml` | Worked example: discovery-plan.yaml for diabetes-ccm |
| `skills/.curated/rh-inf-discovery/examples/readout.md` | Worked example: discovery-readout.md narrative |
| `./discovery-plan.yaml` | **Output**: authoritative source registry (repo root) |
| `./discovery-readout.md` | **Output**: domain narrative for reviewer (repo root) |
| `RESEARCH.md` | Portfolio tracking (topic, question, scope, status) |
| `tracking.yaml` | Records `discovery_planned` event |

---

## Design Details

### Offline Fallback
When network is unavailable, `--offline` returns reference links (PubMed, PMC, ClinicalTrials.gov main pages) and records the query for manual follow-up.

### Rate Limiting
- PubMed: 3 req/s without API key, 10 req/s with `NCBI_API_KEY`
- Intra-request delays built into `_entrez_search_fetch()` and `_clinicaltrials_search()`

### JSON Output Schema
```json
{
  "query": "diabetes ccm",
  "source": "pubmed",
  "retrieved_at": "2026-04-15T12:34:56Z",
  "total_found": 847,
  "returned": 20,
  "results": [
    {
      "id": "12345678",
      "pmid": "12345678",
      "title": "...",
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      "year": "2024",
      "journal": "Diabetes Care",
      "authors": ["Smith J", "Patel R"],
      "doi": "10.1000/...",
      "open_access": true,
      "pmcid": "PMC9999001",
      "abstract_snippet": "..."
    }
  ]
}
```
