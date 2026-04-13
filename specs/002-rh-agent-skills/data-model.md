# Data Model: HI Agent Skills Suite (002)

**Branch**: `002-rh-agent-skills` | **Date**: 2026-04-03

---

## Core Entities

### TopicDirectory

The `topics/<name>/` directory structure holds all artifacts for a clinical topic. Raw source files are shared at the repo root in `sources/`.

```
topics/<name>/
  TOPIC.md            # topic description (created by rh-skills init)
  structured/         # semi-structured L2 artifacts
  computable/         # computable L3 artifacts
  process/
    research.md       # evidence and citations stub (NOTE: superseded by notes.md in 003+)
    notes.md          # open questions, decisions, source conflicts, free notes (human-maintained)
    fixtures/         # LLM test fixtures
    contracts/        # YAML assertions for validation
    checklists/       # clinical review checklists
    plans/            # plan artifacts from framework skills
      discovery-plan.yaml
      discovery-readout.md
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
# tracking.yaml — full structure
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
    description: ""
    author: ""
    created_at: "2026-04-03T19:00:00Z"
    stage: initialized            # computed: initialized | l1-discovery | l2-semi-structured | l3-computable
    structured:                   # L2 artifact entries
      - name: screening-criteria          # kebab-case, matches filename without .yaml
        file: topics/diabetes-screening/structured/screening-criteria.yaml
        derived_from:                     # source file names this artifact was extracted from
          - ada-guidelines-2024
        created_at: "2026-04-03T20:00:00Z"
    computable:                   # L3 artifact entries
      - name: diabetes-pathway            # kebab-case, matches filename without .yaml
        file: topics/diabetes-screening/computable/diabetes-pathway.yaml
        converged_from:                   # structured artifact names combined into this L3 artifact
          - screening-criteria
          - risk-factors
        created_at: "2026-04-03T21:00:00Z"
    events: []                    # topic-scoped lifecycle events (see Event schema below)
events: []                        # repo-level events (see Event schema below)
```

**Stage values** (computed from artifact counts — not stored in tracking.yaml, derived at read time):

| Stage value | Condition |
|-------------|-----------|
| `initialized` | No sources registered |
| `l1-discovery` | At least 1 source, no structured artifacts |
| `l2-semi-structured` | At least 1 structured artifact, no computable artifacts |
| `l3-computable` | At least 1 computable artifact |

**schema_version strategy**: The value `"1.0"` is bumped to `"2.0"` only on breaking structural changes (field renames, required field additions, removal of fields). Additive changes (new optional fields) do not require a version bump. The `rh-skills` CLI always writes the version it was built for; no migration tool is provided in v1.

**Checksum comparison** (used by `rh-skills ingest verify`):
- At ingest: compute `checksum = hashlib.sha256(file)`, store in `sources[].checksum`
- At verify: compute `sha256(current_file)`, compare to stored value
- If mismatch: flag as CHANGED

---

### Event

Every state-changing `rh-skills` CLI command or skill mode appends a named event to `tracking.yaml`. Events are append-only and never modified after creation.

**Schema** (applies to both root-level `events[]` and topic-level `topics[].events[]`):

```yaml
- event: topic_created            # string: event name (see table below)
  timestamp: "2026-04-03T19:00:00Z"  # ISO-8601
  actor: "jane.smith"             # string: user identifier (optional; from git config if available)
  payload: {}                     # object: event-specific data (optional, varies by event type)
```

**Named events** (all events currently emitted by `rh-skills` CLI and skills):

| Event name | Emitted by | Scope | Payload fields |
|------------|-----------|-------|----------------|
| `topic_created` | `rh-skills init` | topic | `name`, `title`, `author` |
| `source_added` | `rh-skills ingest implement` | root | `name`, `file`, `type`, `checksum` |
| `source_changed` | `rh-skills ingest implement` (re-registration) | root | `name`, `old_checksum`, `new_checksum` |
| `structured_derived` | `rh-skills promote derive` | topic | `name`, `file`, `derived_from[]` |
| `computable_converged` | `rh-skills promote combine` | topic | `name`, `file`, `converged_from[]` |
| `validated` | `rh-skills validate` (pass) | topic | `artifact`, `level` (`l2`\|`l3`) |
| `task_completed` | `rh-skills tasks complete` | topic | `task_id`, `task_text` |
| `discovery_planned` | `rh-inf-discovery plan` | topic | `plan_file` |
| `discovery_implemented` | `rh-inf-discovery implement` | topic | `items_count` |
| `ingest_planned` | `rh-inf-ingest plan` | root | `plan_file` |
| `extract_planned` | `rh-inf-extract plan` | topic | `plan_file`, `artifact_count` |
| `extract_implemented` | `rh-inf-extract implement` | topic | `artifacts[]` |
| `formalize_planned` | `rh-inf-formalize plan` | topic | `plan_file`, `output_name` |
| `formalize_implemented` | `rh-inf-formalize implement` | topic | `name`, `converged_from[]` |

Events marked **root scope** are appended to the top-level `events[]`. Events marked **topic scope** are appended to `topics[<name>].events[]`.

---

### FrameworkSkill

A SKILL.md file in `skills/.curated/<name>/SKILL.md`. Not a clinical skill — excluded from `rh-skills list` output via dot-prefix convention.

The canonical SKILL.md template is at `skills/_template/SKILL.md` in this repo and follows the [anthropic skills-developer](https://github.com/anthropics/anthropic-cookbook) format. Contributors creating new framework skills MUST copy and fill in this template.

**Skill directory structure** (progressive disclosure architecture):
```
skills/.curated/<skill-name>/
  SKILL.md          ← Level 2: primary instructions (loaded when skill triggers)
  reference.md      ← Level 3: full schemas, field definitions, validation rules
  examples/
    plan.md         ← Level 3: worked example plan artifact
    output.md       ← Level 3: worked example output artifact(s)
```

Level 3 files are **loaded on demand** by the agent only when the primary SKILL.md
instructs it to read them — keeping the core context window lean.

**Frontmatter**:
```yaml
name: "rh-inf-extract"
description: "Extract structured artifacts from sources. Modes: plan | implement | verify"
compatibility: "rh-skills >= 0.1.0"
metadata:
  author: "Clinical Informatics Team"
  source: "skills/.curated/rh-inf-extract/SKILL.md"
```

**Modes** (dispatched via `$ARGUMENTS` first positional arg):

| Skill | Mode | Reads | Writes |
|-------|------|-------|--------|
| `rh-inf-discovery` | `session` | tracking.yaml (domain) | `topics/<name>/process/plans/discovery-plan.yaml`, `topics/<name>/process/plans/discovery-readout.md` |
| `rh-inf-discovery` | `verify` | `topics/<name>/process/plans/discovery-plan.yaml` | *(none — read-only)* |
| `rh-inf-ingest` | `plan` | `topics/<name>/process/plans/discovery-plan.yaml` or user input | sources queue |
| `rh-inf-ingest` | `implement` | `<file>` (path argument) | `sources/*`, tracking.yaml `sources[]` |
| `rh-inf-ingest` | `verify` | tracking.yaml `sources[]` | *(none — read-only)* |
| `rh-inf-extract` | `plan` | `sources/*`, tracking.yaml | `topics/<name>/process/plans/extract-plan.md` |
| `rh-inf-extract` | `implement` | `topics/<name>/process/plans/extract-plan.md` | `topics/<name>/structured/*` via `rh-skills promote derive` |
| `rh-inf-extract` | `verify` | `topics/<name>/structured/*` | *(none)* via `rh-skills validate` |
| `rh-inf-formalize` | `plan` | `topics/<name>/structured/*`, tracking.yaml | `topics/<name>/process/plans/formalize-plan.md` |
| `rh-inf-formalize` | `implement` | `topics/<name>/process/plans/formalize-plan.md` | `topics/<name>/computable/*` via `rh-skills promote combine` |
| `rh-inf-formalize` | `verify` | `topics/<name>/computable/*` | *(none)* via `rh-skills validate` |
| `rh-inf-verify` | *(standalone)* | `topics/<name>/structured/*` or `topics/<name>/computable/*` | *(none)* |
| `rh-inf-status` | `progress` | tracking.yaml | *(none)* |
| `rh-inf-status` | `next-steps` | tracking.yaml, `topics/<name>/process/plans/*`, `sources/*`, `structured/*`, `computable/*` | *(none)* |
| `rh-inf-status` | `check-changes` | tracking.yaml `sources[]`, disk files | *(none)* |

---

## State Machine: Skill Lifecycle

The state machine below describes the full granular progression. The four **stage values** stored in `tracking.yaml` (and shown by `rh-skills list`) represent coarser checkpoints that collapse multiple state machine states:

| Stage value | Covers states |
|-------------|--------------|
| `initialized` | `[initialized]` |
| `l1-discovery` | `[discovery-planned]` → `[ingest-tasks-ready]` → `[sources-ingested]` |
| `l2-semi-structured` | `[extract-planned]` → `[structured-extracted]` → `[structured-verified]` |
| `l3-computable` | `[formalize-planned]` → `[computable-formalized]` → `[computable-verified]` |

**Stage transition logic** (computed by `_compute_stage()` in `list_cmd.py` and `status.py`):
- `initialized` → `l1-discovery`: when `len(sources) > 0`
- `l1-discovery` → `l2-semi-structured`: when `len(structured) > 0`
- `l2-semi-structured` → `l3-computable`: when `len(computable) > 0`

```
[initialized]
    │
    ▼ rh-inf-discovery plan
[discovery-planned]
    │
    ▼ rh-inf-discovery implement
[ingest-tasks-ready]
    │
    ▼ rh-inf-ingest implement
[sources-ingested]
    │
    ▼ rh-inf-extract plan
[extract-planned]
    │
    ▼ rh-inf-extract implement
[structured-extracted]
    │
    ▼ rh-inf-extract verify
[structured-verified]
    │
    ▼ rh-inf-formalize plan
[formalize-planned]
    │
    ▼ rh-inf-formalize implement
[computable-formalized]
    │
    ▼ rh-inf-formalize verify
[computable-verified] ← terminal "computable" state
```

At any stage: `rh-skills ingest verify` may surface CHANGED sources → re-run from `rh-skills ingest implement`

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

### StructuredArtifactEntry (topics[].structured[])
- `name` must be kebab-case and match the file basename (without `.yaml`)
- `file` path must be under `topics/<name>/structured/`
- `derived_from` must be a non-empty list of names present in root `sources[]`
- `created_at` must be ISO-8601

### ComputableArtifactEntry (topics[].computable[])
- `name` must be kebab-case and match the file basename (without `.yaml`)
- `file` path must be under `topics/<name>/computable/`
- `converged_from` must be a non-empty list of names present in `topics[].structured[]`
- `created_at` must be ISO-8601

### Event
- `event` must be one of the named events in the Named Events table above
- `timestamp` must be ISO-8601
- `actor` is optional; if present, must be a non-empty string
- `payload` is optional; fields vary by event type (see Named Events table)

### FrameworkSkill (SKILL.md)
- Frontmatter `name` must match directory name (e.g., `rh-inf-extract`)
- `compatibility` must reference `rh-skills`
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
