# Data Model: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03

---

## Core Entities

### TopicDirectory

The `topics/<name>/` directory structure holds all artifacts for a clinical topic. Raw source files are shared at the repo root in `sources/`.

```
topics/<name>/
  TOPIC.md            # topic description (created by hi init)
  structured/         # semi-structured L2 artifacts
  computable/         # computable L3 artifacts
  process/
    research.md       # evidence and citations stub
    conflicts.md      # source contradictions stub
    fixtures/         # LLM test fixtures
    contracts/        # YAML assertions for validation
    checklists/       # clinical review checklists
    plans/            # plan artifacts from framework skills
      discovery-plan.md
      ingest-plan.md
      extract-plan.md
      formalize-plan.md
      tasks.md

sources/              # Raw source files (repo root, shared across topics)
  ada-guidelines-2024.md
```

---

### PlanArtifact

A human-reviewable Markdown file with YAML front matter produced by a `plan` mode. Consumed by the corresponding `implement` mode.

**File path**: `topics/<name>/process/plans/<skill>-plan.md`

**Format**:
```markdown
---
# YAML front matter — machine-readable, parsed by implement mode
topic: <topic-name>            # string, required
plan_type: <discovery|ingest|extract|formalize>  # string, required
version: "1.0"                 # string, required
created: "<ISO-8601>"          # string, required
force_overwrite: false         # bool, optional, default false

# plan_type-specific fields (see per-plan schemas below)
---

## <Title>
<human-readable prose for clinician review>
```

**State transitions**:
- Created by: `plan` mode (fails if exists and `--force` not set)
- Consumed by: `implement` mode (fails if does not exist)
- Overwritten by: `plan --force`

---

### DiscoveryPlan (PlanArtifact subtype)

**Front matter schema**:
```yaml
topic: diabetes-screening
plan_type: discovery
version: "1.0"
created: "2026-04-03T19:00:00Z"
domain: diabetes                    # clinical domain from tracking.yaml
sources:
  - type: guideline                 # guideline | paper | terminology | dataset | other
    name: "ADA Standards of Care 2024"
    url: "https://diabetesjournals.org/care/..."  # optional
    priority: high                  # high | medium | low
    rationale: "Primary evidence base for diabetes screening"
  - type: terminology
    name: "SNOMED CT Diabetes Subset"
    priority: medium
    rationale: "Coded concepts for risk factors"
```

---

### IngestPlan (PlanArtifact subtype)

**Front matter schema**:
```yaml
topic: diabetes-screening
plan_type: ingest
version: "1.0"
created: "2026-04-03T19:00:00Z"
items:
  - name: ada-guidelines-2024       # kebab-case, becomes source artifact name
    path: ~/Downloads/ada-care-2024.pdf   # local file path or URL
    type: pdf                       # pdf | docx | xlsx | txt | md | url
    extract_text: true              # whether to attempt text extraction
    target: sources/ada-guidelines-2024  # destination path in sources/ (optional)
```

---

### ExtractPlan (PlanArtifact subtype)

**Front matter schema**:
```yaml
topic: diabetes-screening
plan_type: extract
version: "1.0"
created: "2026-04-03T19:00:00Z"
artifacts:
  - name: screening-criteria        # kebab-case structured artifact name
    source_file: ada-guidelines-2024     # file in sources/ (without extension)
    description: "Discrete criteria for identifying adults who should be screened"
  - name: risk-factors
    source_file: ada-guidelines-2024
    description: "Enumerated risk factor definitions with clinical thresholds"
```

---

### FormalizePlan (PlanArtifact subtype)

**Front matter schema**:
```yaml
topic: diabetes-screening
plan_type: formalize
version: "1.0"
created: "2026-04-03T19:00:00Z"
output_name: diabetes-screening-computable   # computable artifact name
sources:                                     # structured artifact names to combine
  - screening-criteria
  - risk-factors
sections:                                    # computable sections to include
  - pathways
  - measures
  - value_sets
outline: |
  Pathway: eligibility → diagnostic ordering → result interpretation
  Measure: diabetes screening rate (proportion)
  Value sets: LOINC diagnostic labs, SNOMED risk conditions
```

---

### IngestRecord (tracking.yaml extension)

Root-level `sources[]` array in `tracking.yaml` stores ingest metadata. The `topics[].structured` and `topics[].computable` arrays track derived artifacts.

```yaml
# tracking.yaml — current structure
schema_version: "1.0"
sources:                          # root-level: registered raw source files
  - name: ada-guidelines-2024     # kebab-case, unique
    file: sources/ada-guidelines-2024.md  # path relative to repo root
    type: document                # pdf | docx | xlsx | txt | md | url
    ingested_at: "2026-04-03T19:00:00Z"
    checksum: "e3b0c44298fc1c..."  # SHA-256 of file at ingest time
    text_extracted: false         # false if pdftotext/pandoc unavailable
topics:
  - name: diabetes-screening
    title: Diabetes Screening
    structured: []                # L2 artifact entries
    computable: []                # L3 artifact entries
    events: []
events: []                        # root-level events
```

**Checksum comparison** (used by `hi ingest verify`):
- At ingest: compute `checksum = hashlib.sha256(file)`, store in `sources[].checksum`
- At verify: compute `sha256(current_file)`, compare to stored value
- If mismatch: flag as CHANGED

---

### FrameworkSkill

A SKILL.md file in `skills/.curated/<name>/SKILL.md`. Not a clinical skill — excluded from `hi list` output via dot-prefix convention.

**Frontmatter**:
```yaml
name: "hi-extract"
description: "Extract structured artifacts from sources. Modes: plan | implement | verify"
compatibility: "hi-skills-framework >= 0.1.0"
metadata:
  author: "Clinical Informatics Team"
  source: "skills/.curated/hi-extract/SKILL.md"
```

**Modes** (dispatched via `$ARGUMENTS` first positional arg):

| Skill | Mode | Reads | Writes |
|-------|------|-------|--------|
| `hi-discovery` | `plan` | tracking.yaml (domain) | `topics/<name>/process/plans/discovery-plan.md` |
| `hi-discovery` | `implement` | `topics/<name>/process/plans/discovery-plan.md` | `topics/<name>/process/plans/ingest-plan.md` |
| `hi-ingest` | `plan` | `topics/<name>/process/plans/discovery-plan.md` or user input | `plans/ingest-plan.md` |
| `hi-ingest` | `implement` | `<file>` (path argument) | `sources/*`, tracking.yaml `sources[]` |
| `hi-ingest` | `verify` | tracking.yaml `sources[]` | *(none — read-only)* |
| `hi-extract` | `plan` | `sources/*`, tracking.yaml | `topics/<name>/process/plans/extract-plan.md` |
| `hi-extract` | `implement` | `topics/<name>/process/plans/extract-plan.md` | `topics/<name>/structured/*` via `hi promote derive` |
| `hi-extract` | `verify` | `topics/<name>/structured/*` | *(none)* via `hi validate` |
| `hi-formalize` | `plan` | `topics/<name>/structured/*`, tracking.yaml | `topics/<name>/process/plans/formalize-plan.md` |
| `hi-formalize` | `implement` | `topics/<name>/process/plans/formalize-plan.md` | `topics/<name>/computable/*` via `hi promote combine` |
| `hi-formalize` | `verify` | `topics/<name>/computable/*` | *(none)* via `hi validate` |
| `hi-verify` | *(standalone)* | `topics/<name>/structured/*` or `topics/<name>/computable/*` | *(none)* |
| `hi-status` | `progress` | tracking.yaml | *(none)* |
| `hi-status` | `next-steps` | tracking.yaml, `topics/<name>/process/plans/*`, `sources/*`, `structured/*`, `computable/*` | *(none)* |
| `hi-status` | `check-changes` | tracking.yaml `sources[]`, disk files | *(none)* |

---

## State Machine: Skill Lifecycle

```
[initialized]
    │
    ▼ hi-discovery plan
[discovery-planned]
    │
    ▼ hi-discovery implement
[ingest-tasks-ready]
    │
    ▼ hi-ingest implement
[sources-ingested]
    │
    ▼ hi-extract plan
[extract-planned]
    │
    ▼ hi-extract implement
[structured-extracted]
    │
    ▼ hi-extract verify
[structured-verified]
    │
    ▼ hi-formalize plan
[formalize-planned]
    │
    ▼ hi-formalize implement
[computable-formalized]
    │
    ▼ hi-formalize verify
[computable-verified] ← terminal "computable" state
```

At any stage: `hi ingest verify` may surface CHANGED sources → re-run from `hi ingest implement`

---

## Validation Rules

### PlanArtifact
- `topic` must match an existing directory under `topics/`
- `plan_type` must be one of: `discovery | ingest | extract | formalize`
- `created` must be ISO-8601
- Plan-type-specific required fields (see subtypes above)

### IngestRecord
- `name` must be kebab-case
- `type` must be one of: `pdf | docx | xlsx | txt | md | url`
- `checksum` must be 64-char hex string (SHA-256)
- `ingested_at` must be ISO-8601
- `file` path must be under `sources/`

### FrameworkSkill (SKILL.md)
- Frontmatter `name` must match directory name (e.g., `hi-extract`)
- `compatibility` must reference `hi-skills-framework`
- Modes listed in `description` must be documented in body

---

## Relationships

```
TopicDirectory (1) ──── (0..4) PlanArtifact
TopicDirectory (1) ──── (0..*) StructuredArtifact   [in topics/<name>/structured/]
TopicDirectory (1) ──── (0..*) ComputableArtifact   [in topics/<name>/computable/]
SourceFile     (1) ──── (0..*) StructuredArtifact   [via tracking sources → structured.derived_from]
StructuredArtifact (1..*)──── (0..*) ComputableArtifact [via tracking computable.converged_from]
IngestRecord   (1) ──── (0..1) SourceFile            [same name in sources/]
```
