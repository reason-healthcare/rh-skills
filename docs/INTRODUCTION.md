# Introduction to RH Skills

## What is RH Skills?

RH Skills is an agentic workflow toolset that transforms clinical evidence — guidelines, quality measures, assessments, prior-authorization policies — into **deterministic, computable rules** that can be embedded directly into EHRs, quality programs, and clinical decision support systems.

It bridges the well-documented gap between narrative clinical knowledge and implementable logic. Research shows it takes up to 17 years for findings to reach routine practice; computable rules close that gap by encoding guidelines so they fire consistently at the point of care.

## Who is it for?

- **Clinical informaticists** building computable content for healthcare organizations
- **Quality measure developers** encoding eCQMs, HEDIS, and NQF measures
- **CDS authors** creating decision support rules from evidence-based guidelines
- **Health IT teams** maintaining terminology value sets and care pathways

## Core Concepts

### Three Artifact Levels

```
  PDF, DOCX, HTML, XLSX, ...          (L1 raw — any format)
           │
           │  ingest + normalize
           ▼
       Markdown                        (L1 normalized)
           │
           │  extract  ┌─────────────────────────┐
           ├──────────▶│  Structured artifact    │  (L2)
           ├──────────▶│  Structured artifact    │  (L2)
           └──────────▶│  Structured artifact    │  (L2)
                       └───────┬───────────┬─────┘
                               │           │
                               │ formalize │
                               ▼           ▼
                        ┌────────────────────────┐
                        │  Computable artifact   │  (L3)
                        │  (FHIR R4 JSON + CQL)  │
                        └────────────────────────┘
```

| Level | Format | What it represents |
|-------|--------|--------------------|
| **L1 (raw)** | Any | Original source files as-obtained — PDFs, Word docs, web pages, spreadsheets |
| **L1 (normalized)** | Markdown | Source content converted to plain Markdown for consistent downstream processing |
| **L2** | Structured YAML | Discrete clinical criteria, coded concepts, decision logic — human-editable |
| **L3** | FHIR R4 JSON + CQL | Computable resources ready for EHR integration (PlanDefinition, Measure, ValueSet, etc.) |

Raw files are ingested and normalized to Markdown (L1) before extraction. The relationships are many-to-many: one L1 source can yield several L2 artifacts; multiple L2 artifacts can converge into a single L3.

### Four Pipeline Stages

```
Discovery → Ingest → Extract → Formalize
```

1. **Discovery** — Find and evaluate evidence sources (PubMed, ClinicalTrials.gov, guidelines, terminologies)
2. **Ingest** — Acquire sources, normalize to Markdown, classify by evidence level, annotate clinical concepts
3. **Extract** — Derive structured L2 artifacts from 7 standard types (evidence-summary, decision-table, care-pathway, terminology, measure, assessment, policy)
4. **Formalize** — Convert L2 artifacts into L3 FHIR R4 resources using type-specific strategies

### Plan → Implement → Verify

Every stage transition follows a mandatory three-step pattern:

- **Plan** — Agent proposes what to do; writes a review packet
- **Implement** — After human approval, agent executes via deterministic CLI commands
- **Verify** — Non-destructive validation confirms correctness

This ensures no artifacts are created without explicit reviewer approval.

### Separation of Concerns

> All deterministic work in `rh-skills` CLI commands. All reasoning in SKILL.md agent prompts.

- The CLI handles: file I/O, checksums, YAML reads/writes, schema validation, event tracking
- The agent handles: clinical reasoning, artifact naming, source evaluation, convergence strategy

## Two Usage Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| **CLI-first** | You call `rh-skills` commands directly; use any LLM provider | Full control, CI/CD, bring-your-own-model |
| **Agent-native** | Your AI agent reads RH skills and calls `rh-skills` on your behalf | Conversational UX, clinical teams |

Both modes use the same underlying CLI — the agent simply automates the reasoning layer.

## What You Produce

A completed topic yields a **FHIR NPM package** containing:

- `PlanDefinition` resources (clinical protocols, decision rules, coverage policies)
- `Measure` + `Library` resources (quality measures with CQL logic)
- `ValueSet` + `ConceptMap` resources (coded terminology)
- `Questionnaire` resources (screening instruments, DTR forms)
- `Evidence` + `EvidenceVariable` resources (graded clinical findings)
- `ImplementationGuide` resource (package metadata)

These are standard FHIR R4 artifacts deployable to any FHIR-compatible system.

## Next Steps

- [Getting Started](GETTING_STARTED.md) — Install and run your first topic
- [Workflow](WORKFLOW.md) — Detailed lifecycle model and directory structure
- [Commands](COMMANDS.md) — Full CLI reference
