# RH Skills — Workflow

## Lifecycle Overview

The RH Skills pipeline progresses clinical knowledge through three artifact levels:

```
L1 Discovery & Ingest           L2 Extract                      L3 Formalize
─────────────────────           ──────────                      ────────────
Find + acquire sources   ──→    Structure into typed       ──→  Convert to FHIR R4
(PDFs, guidelines,              artifacts (YAML,                computable resources
 web articles)                  human-editable)                 (JSON + CQL)
```

```
sources/                        topics/<name>/structured/       topics/<name>/computable/
────────────────────            ─────────────────────────       ─────────────────────────
L1 Raw Sources                  L2 Structured Artifacts         L3 Computable Artifacts
(PDFs, guidelines,              (semi-structured YAML,          (FHIR JSON + CQL,
 Word docs, web articles)        human-editable)                 machine-executable)

  guideline-2024.pdf     ──→    screening-criteria.yaml  ─┐
  ada-standards.pdf      ──→    risk-factors.yaml         ├──→  PlanDefinition.json
  cdc-statistics.pdf     ──→    diagnostic-thresholds.yaml┘     Library.cql
```

**Many-to-many relationships:**
- A single L1 source can produce multiple L2 artifacts
- Multiple L2 artifacts converge into a single L3 artifact
- Multiple L3 artifacts can exist per topic

## Plan → Implement → Verify

Every lifecycle transition follows this mandatory three-step pattern:

```
 ┌─────────────────────────────────────────────────────────────────┐
 │  PLAN                                                           │
 │  Agent reasons about the topic and proposes artifact names,     │
 │  source lists, or convergence strategy. Output is written to    │
 │  topics/<name>/process/plans/<skill>-plan.md (YAML front matter │
 │  + human-readable prose). No files are created or modified.     │
 └───────────────────────┬─────────────────────────────────────────┘
                         │
                   Human reviews and
                   edits the plan file
                         │
 ┌───────────────────────▼─────────────────────────────────────────┐
 │  IMPLEMENT                                                      │
 │  Agent reads the YAML front matter from the plan file and       │
 │  executes it by invoking rh-skills CLI commands. Fails          │
 │  immediately if no plan exists. Human review gate is enforced.  │
 └───────────────────────┬─────────────────────────────────────────┘
                         │
 ┌───────────────────────▼─────────────────────────────────────────┐
 │  VERIFY                                                         │
 │  Non-destructive validation. Runs schema checks and reports     │
 │  required-field errors (blocking) vs warnings (advisory).       │
 └─────────────────────────────────────────────────────────────────┘
```

## Skill Stages

| Stage | Skill | Modes | Plan Artifact | Output | Details |
|-------|-------|-------|---------------|--------|---------|
| **Discovery** | `rh-inf-discovery` | plan · implement | `discovery-plan.yaml` | Source registry + domain narrative | [→ DISCOVERY.md](DISCOVERY.md) |
| **Ingest** | `rh-inf-ingest` | plan · implement · verify | `ingest-plan.md` | Normalized L1 sources + concepts | [→ INGEST.md](INGEST.md) |
| **Extract** | `rh-inf-extract` | plan · implement · verify | `extract-plan.yaml` | L2 artifacts in `structured/` | [→ EXTRACT.md](EXTRACT.md) |
| **Formalize** | `rh-inf-formalize` | plan · implement · verify | `formalize-plan.md` | L3 FHIR resources in `computable/` | [→ FORMALIZE.md](FORMALIZE.md) |
| **CQL Authoring** | `rh-inf-cql` | author · review · test | — | Validated `.cql` libraries in `computable/` | [→ SKILLS.md](SKILLS.md) |
| **Verify** | `rh-inf-verify` | *(standalone)* | — | Consolidated topic verification report | |
| **Status** | `rh-inf-status` | progress · next-steps · check-changes | — | Lifecycle summary + deterministic next steps | |

`rh-inf-verify` is a read-only coordinator, not a parallel lifecycle stage. It
determines stage applicability for the current topic, runs the applicable
stage-specific verify workflows, and reports later stages explicitly as
`not-yet-ready` / `not-applicable` instead of silently omitting them.

## Stage Deep Dives

Each stage has a detailed workflow document covering CLI commands, data flow, key files, and design decisions:

- **[Discovery](DISCOVERY.md)** — Interactive research session: search PubMed/PMC/ClinicalTrials.gov, build curated source registry with domain advice, enforce source constraints (5–25 sources, ≥1 terminology)
- **[Ingest](INGEST.md)** — Four-stage pipeline: download → normalize (PDF/DOCX/HTML→Markdown) → classify (evidence level) → annotate (clinical concepts). Serial annotation constraint prevents concepts.yaml corruption
- **[Extract](EXTRACT.md)** — Plan-gated derivation: propose L2 artifacts from 7-type catalog, reviewer approves per-artifact, LLM generates structured YAML, validate + render reports with Mermaid diagrams
- **[Formalize](FORMALIZE.md)** — Type-aware L3 conversion: 7 strategies map L2 types to specific FHIR R4 resources (Evidence, PlanDefinition, ValueSet, Questionnaire, Measure), multi-type overlap detection, FHIR NPM packaging
- **CQL Authoring** (`rh-inf-cql`) — Used after formalize when the strategy produces CQL (strategies: `decision-table`, `measure`). Authors and validates `.cql` libraries via `rh-skills cql validate` and `rh-skills cql translate`; designs fixture cases for expression coverage. See [SKILLS.md](SKILLS.md).

## Directory Structure

```
topics/<name>/
├── structured/                  ← L2 artifacts (prominent, at root)
│   ├── screening-criteria.yaml
│   ├── risk-factors.yaml
│   └── diagnostic-thresholds.yaml
├── computable/                  ← L3 artifacts (prominent, at root)
│   └── diabetes-pathway.yaml
└── process/                     ← workflow support files
    ├── plans/
    │   ├── discovery-plan.md    ← YAML front matter + prose
    │   ├── ingest-plan.md
    │   ├── extract-plan.md
    │   ├── formalize-plan.md
    │   └── tasks.md             ← rh-skills tasks tracking
    ├── contracts/               ← YAML validation contracts
    ├── checklists/              ← clinical review checklists
    ├── fixtures/                ← LLM test fixtures
    │   └── results/             ← test run results
    └── notes.md                 ← open questions, decisions, source conflicts, notes (human-maintained)

sources/                         ← L1 raw source files (repo-wide)
tracking.yaml                    ← lifecycle state for all topics
```

## Guiding Principle

> **All deterministic work in `rh-skills` CLI commands. All reasoning in SKILL.md agent prompts.**

The framework makes this separation explicit:
- `rh-skills` commands handle: file I/O, SHA-256 checksums, YAML reads/writes, schema validation
- SKILL.md prompts handle: clinical reasoning, artifact naming, source discovery, convergence strategy

## Event Tracking

Every state-changing operation appends a named event to `tracking.yaml`:

| Event | Triggered By |
|-------|-------------|
| `topic_created` | `rh-skills init` |
| `source_added` | `rh-skills ingest implement` |
| `source_changed` | `rh-skills ingest implement` (re-registration) |
| `source_classified` | `rh-skills ingest classify` |
| `source_annotated` | `rh-skills ingest annotate` |
| `discovery_planned` | `rh-inf-discovery plan` mode |
| `discovery_implemented` | `rh-inf-discovery implement` mode |
| `extract_planned` | `rh-skills promote plan` |
| `structured_derived` | `rh-skills promote derive` |
| `formalize_planned` | `rh-skills promote formalize-plan` |
| `computable_converged` | `rh-skills formalize` |
| `package_created` | `rh-skills package` |
| `validated` | `rh-skills validate` (pass) |
| `task_completed` | `rh-skills tasks complete` |
