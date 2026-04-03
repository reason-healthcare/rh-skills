# Data Model: Healthcare Informatics Skills Framework

**Phase**: 1 — Design  
**Branch**: `001-hi-skills-framework`  
**Date**: 2026-04-03

---

## Overview

The data model is entirely file-system based — no database. All entities are YAML or Markdown files in a defined directory structure. The tracking artifact is the authoritative state record for each skill.

---

## Entity Definitions

### Skill

The top-level organizational unit. A Skill owns collections of artifacts at each level and a tracking artifact.

**Location**: `skills/{skill-name}/`

**Identity**: Directory name; must be kebab-case; unique within the repository.

**Fields** (from `tracking.yaml`):
```yaml
skill:
  name: {kebab-case}           # Unique skill identifier
  title: {Human-Readable}      # Display name
  description: {text}          # Brief purpose statement
  author: {string}             # Creator
  created_at: {ISO-8601}       # Creation timestamp
```

---

### Artifact (L1)

Raw discovery documents — unstructured or lightly structured Markdown. No schema enforcement.

**Location**: `skills/{skill-name}/l1/{artifact-name}.md`

**Identity**: File name (kebab-case); unique within the skill's `l1/` directory.

**No required fields** — free-form content (notes, transcripts, reference excerpts).

**Tracked in**: `tracking.yaml` → `artifacts.l1[]`

---

### Artifact (L2)

Semi-structured YAML with defined fields. Schema-guided but not fully computable.

**Location**: `skills/{skill-name}/l2/{artifact-name}.yaml`

**Schema**: `schemas/l2-schema.yaml`

**Required fields**:
```yaml
id: {kebab-case}
name: {PascalCase}
title: {string}
version: {semver}
status: draft | active | retired
description: |
  {multi-line text}
domain: {string}
derived_from:             # Many-to-many: which L1 artifact(s) produced this
  - {l1-artifact-name}
```

**Optional fields**: `notes`, `references`, `tags`, `subject_area`

**Tracked in**: `tracking.yaml` → `artifacts.l2[]`

---

### Artifact (L3)

Computable YAML conforming to the custom domain schema. Designed for FHIR/FHIRPath/CQL compatibility. Schema-validated at promotion time.

**Location**: `skills/{skill-name}/l3/{artifact-name}.yaml`

**Schema**: `schemas/l3-schema.yaml`

**Required fields**:
```yaml
artifact_schema_version: "1.0"
metadata:
  id: {kebab-case}
  name: {PascalCase}
  title: {string}
  version: {semver}
  status: draft | active | retired
  domain: {string}
  created_date: YYYY-MM-DD
  description: |
    {multi-line text}
converged_from:           # Many-to-many: which L2 artifact(s) contributed
  - {l2-artifact-name}
```

**Optional sections** (include as needed):
- `pathways` → maps to FHIR `PlanDefinition`
- `actions` → maps to FHIR `ActivityDefinition`
- `libraries` → maps to FHIR `Library` (CQL)
- `measures` → maps to FHIR `Measure`
- `assessments` → maps to FHIR `Questionnaire`
- `value_sets` → maps to FHIR `ValueSet`
- `code_systems` → maps to FHIR `CodeSystem`
- `extensions.fhirpath` / `extensions.cql` → optional logic expressions

**Tracked in**: `tracking.yaml` → `artifacts.l3[]`

---

### Tracking Artifact

The authoritative lifecycle record for a skill. Written and updated exclusively by CLI commands — never manually edited.

**Location**: `skills/{skill-name}/tracking.yaml`

**Schema**: `schemas/tracking-schema.yaml`

```yaml
schema_version: "1.0"
skill:
  name: {kebab-case}
  title: {string}
  description: {string}
  author: {string}
  created_at: {ISO-8601}

artifacts:
  l1:
    - name: {artifact-name}
      created_at: {ISO-8601}
  l2:
    - name: {artifact-name}
      created_at: {ISO-8601}
      promoted_at: {ISO-8601}
      derived_from: [{l1-artifact-name}]   # Many-to-many derivation
      validation_status: passed | warnings | blocked
      validation_warnings: [{field-path}]   # Optional fields that were empty
  l3:
    - name: {artifact-name}
      created_at: {ISO-8601}
      promoted_at: {ISO-8601}
      converged_from: [{l2-artifact-name}]  # Many-to-many convergence
      validation_status: passed | warnings | blocked
      validation_warnings: [{field-path}]

events:                       # Append-only event log
  - timestamp: {ISO-8601}
    type: created             # created | l1_added | l2_derived | l3_converged |
                              #   validated | test_run
    description: {string}
    details:                  # Type-specific fields
      source_artifacts: [{name}]
      target_artifacts: [{name}]
      outcome: {string}
      warnings: [{string}]

test_results:                 # Latest test run summary (full result in fixtures/)
  last_run_at: {ISO-8601}
  provider: {ollama|anthropic|openai}
  model: {string}
  total: {int}
  passed: {int}
  failed: {int}
  errored: {int}
```

---

### Test Fixture

An author-defined input/expected-output pair for validating a skill's LLM behavior.

**Location**: `skills/{skill-name}/fixtures/{fixture-name}/`

**Files**:
```
fixtures/{fixture-name}/
├── input.yaml        # Conversation context sent to LLM
└── expected.yaml     # Expected LLM response + comparison config
```

**`input.yaml`**:
```yaml
description: {string}
messages:
  - role: user
    content: |
      {clinical scenario text}
```

**`expected.yaml`**:
```yaml
comparison_mode: normalized   # exact | normalized | case_insensitive | contains | keywords
expected_output: |
  {expected LLM response text}
tags: [{string}]
```

---

### Test Result Artifact

Produced by `hi test` — a timestamped record of a full test run.

**Location**: `skills/{skill-name}/fixtures/results/{ISO-date}-{run-id}.json`

```json
{
  "test_run_id": "test-20260403-141500",
  "timestamp": "2026-04-03T14:15:00Z",
  "skill_name": "diabetes-screening",
  "llm_config": {
    "provider": "ollama",
    "model": "mistral"
  },
  "summary": {
    "total": 3,
    "passed": 2,
    "failed": 1,
    "errored": 0
  },
  "fixtures": [
    {
      "fixture_id": "basic-screening",
      "status": "PASSED",
      "comparison_mode": "normalized",
      "duration_ms": 1234
    },
    {
      "fixture_id": "edge-case-elderly",
      "status": "FAILED",
      "expected": "...",
      "actual": "...",
      "comparison_mode": "keywords"
    },
    {
      "fixture_id": "timeout-scenario",
      "status": "ERRORED",
      "error_type": "TIMEOUT",
      "error_message": "Request exceeded 30s"
    }
  ]
}
```

---

## Artifact Topology (Many-to-Many)

```
L1 Artifacts          L2 Artifacts          L3 Artifacts
─────────────         ─────────────         ─────────────
discovery-a.md ──┬──► concept-x.yaml ──┬──► guideline.yaml
                 │                      │
discovery-b.md ──┘   concept-y.yaml ──┘
                              │
                      concept-z.yaml ──────► measure.yaml
```

- One L1 may derive **one or more** L2 artifacts (`hi promote --derive`)
- Multiple L2 artifacts may converge into **one** L3 artifact (`hi promote --combine`)
- A skill may have **multiple L3 artifacts** (e.g., one for a guideline, one for a measure)
- Relationships are recorded in `tracking.yaml` as `derived_from` and `converged_from` arrays

---

## Directory Layout (Full Skill Example)

```
skills/
└── diabetes-screening/
    ├── SKILL.md                        # Anthropic skill prompt
    ├── tracking.yaml                   # Authoritative lifecycle state
    ├── l1/
    │   ├── ada-guidelines-excerpt.md   # Raw reference material
    │   └── clinical-interview.md       # Unstructured notes
    ├── l2/
    │   ├── screening-criteria.yaml     # Derived from ada-guidelines-excerpt
    │   └── risk-factors.yaml           # Derived from both l1 artifacts
    ├── l3/
    │   └── screening-guideline.yaml    # Converged from screening-criteria + risk-factors
    └── fixtures/
        ├── basic-case/
        │   ├── input.yaml
        │   └── expected.yaml
        ├── high-risk-case/
        │   ├── input.yaml
        │   └── expected.yaml
        └── results/
            └── 2026-04-03-abc123.json
```
