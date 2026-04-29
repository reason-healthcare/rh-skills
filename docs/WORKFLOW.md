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
 │  source lists, or convergence strategy. Depending on the stage, │
 │  the plan step either writes a durable plan artifact or emits a │
 │  transient read-only pre-flight summary to stdout.              │
 └───────────────────────┬─────────────────────────────────────────┘
                         │
               Human reviews the plan
               artifact or pre-flight
                    summary output
                         │
 ┌───────────────────────▼─────────────────────────────────────────┐
 │  IMPLEMENT                                                      │
 │  Agent executes the approved plan by invoking rh-skills CLI     │
 │  commands. When a durable plan artifact exists, implement reads │
 │  it directly; when plan mode is transient, implement proceeds   │
 │  from the confirmed pre-flight summary. Human review gate is    │
 │  enforced in both cases.                                        │
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
| **Discovery** | `rh-inf-discovery` | plan · verify | `topics/<topic>/process/plans/discovery-plan.yaml` | Source registry + domain narrative | [→ DISCOVERY.md](DISCOVERY.md) |
| **Ingest** | `rh-inf-ingest` | plan · implement · verify | Transient stdout pre-flight summary (no durable plan file; optionally informed by `topics/<topic>/process/plans/discovery-plan.yaml`) | Normalized L1 sources + concepts | [→ INGEST.md](INGEST.md) |
| **Extract** | `rh-inf-extract` | plan · implement · verify | `extract-plan.yaml` | L2 artifacts in `structured/` | [→ EXTRACT.md](EXTRACT.md) |
| **Formalize** | `rh-inf-formalize` + `rh-inf-cql` | plan · implement · verify | `formalize-plan.md` | L3 FHIR resources + authored CQL in `computable/` | [→ FORMALIZE.md](FORMALIZE.md) |
| **Verify** | `rh-inf-verify` | *(standalone)* | — | Consolidated topic verification report | |
| **Status** | `rh-inf-status` | progress · next-steps · check-changes | — | Lifecycle summary + deterministic next steps | |

`rh-inf-verify` is a read-only coordinator, not a parallel lifecycle stage. It
determines stage applicability for the current topic, runs the applicable
stage-specific verify workflows, and reports later stages explicitly as
`not-yet-ready` / `not-applicable` instead of silently omitting them.

## Stage Deep Dives

Each stage has a detailed workflow document covering CLI commands, data flow, key files, and design decisions:

- **[Discovery](DISCOVERY.md)** — Topic-centered interactive research workflow: search PubMed/PMC/ClinicalTrials.gov, build a curated source registry with domain advice, enforce source constraints (5–25 sources, ≥1 terminology), write topic-scoped discovery artifacts, then download approved open-access sources.
- **[Ingest](INGEST.md)** — Five-stage pipeline: register local sources → normalize (PDF/DOCX/HTML→Markdown) → classify (evidence level) → annotate (clinical concepts). Open-access downloads are handled in discovery before ingest begins, and `topics/<topic>/process/plans/discovery-plan.yaml` may be used as optional enrichment during ingest. Serial annotation constraint prevents concepts.yaml corruption
- **[Extract](EXTRACT.md)** — Plan-gated derivation: propose L2 artifacts from 7-type catalog, reviewer approves per-artifact, LLM generates structured YAML, validate + render reports with Mermaid diagrams
- **[Formalize](FORMALIZE.md)** — Type-aware L3 conversion: 7 strategies map L2 types to specific FHIR R4 resources. For CQL strategies (`decision-table`, `measure`, `policy`), `rh-inf-formalize` generates the FHIR JSON wrappers + CQL scaffold, then hands off directly to `rh-inf-cql` within the same implement step to author, validate, and compile the full CQL library.

## Directory Structure

```
sources/                         ← L1 raw source files (repo-wide)
tracking.yaml                    ← lifecycle state for all topics

topics/<name>/
├── process/
│   ├── plans/
│   │   ├── discovery-plan.yaml
│   │   ├── discovery-readout.md
│   │   ├── extract-plan.md
│   │   ├── formalize-plan.md
│   │   └── tasks.md             ← rh-skills tasks tracking
│   ├── fixtures/                ← LLM test fixtures
│   │   └── results/             ← test run results
│   └── notes.md                 ← open questions, decisions, source conflicts, notes (human-maintained)
├── structured/                  ← L2 artifacts (prominent, at root)
│   ├── screening-criteria.yaml
│   ├── risk-factors.yaml
│   └── diagnostic-thresholds.yaml
├── computable/                  ← L3 artifacts (prominent, at root)
│   └── diabetes-pathway.yaml
```

`rh-inf-ingest` does not create a durable `ingest-plan.md`. Its `plan` mode is
a transient pre-flight summary derived from the current state of `sources/`,
`tracking.yaml`, and optionally `topics/<topic>/process/plans/discovery-plan.yaml`
when that discovery output is available.

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
| `source_added` | `rh-skills ingest implement`; `rh-skills source download` |
| `source_changed` | `rh-skills ingest implement` (re-registration); `rh-skills source download` (re-download) |
| `source_classified` | `rh-skills ingest classify` |
| `source_annotated` | `rh-skills ingest annotate` |
| `discovery_planned` | `rh-inf-discovery plan` mode |
| `extract_planned` | `rh-skills promote plan` |
| `structured_derived` | `rh-skills promote derive` |
| `formalize_planned` | `rh-skills promote formalize-plan` |
| `computable_converged` | `rh-skills formalize` |
| `package_created` | `rh-skills package` |
| `validated` | `rh-skills validate` (pass) |
| `task_completed` | `rh-skills tasks complete` |
