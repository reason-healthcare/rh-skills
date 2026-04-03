# Data Model: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03

---

## Core Entities

### SkillDirectory (existing, extended)

The existing `skills/<name>/` directory structure gains a new `plans/` subdirectory.

```
skills/<name>/
  SKILL.md            # clinical skill description (existing)
  tracking.yaml       # audit log (existing, extended with sources[])
  l1/                 # raw L1 artifacts (existing)
  l2/                 # semi-structured L2 artifacts (existing)
  l3/                 # computable L3 artifacts (existing)
  fixtures/           # LLM test fixtures (existing)
  plans/              # NEW: plan artifacts from framework skills
    discovery-plan.md
    ingest-plan.md
    extract-plan.md
    formalize-plan.md
```

---

### PlanArtifact

A human-reviewable Markdown file with YAML front matter produced by a `plan` mode. Consumed by the corresponding `implement` mode.

**File path**: `skills/<name>/plans/<skill>-plan.md`

**Format**:
```markdown
---
# YAML front matter — machine-readable, parsed by implement mode
skill: <skill-name>            # string, required
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
skill: diabetes-screening
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
skill: diabetes-screening
plan_type: ingest
version: "1.0"
created: "2026-04-03T19:00:00Z"
items:
  - name: ada-guidelines-2024       # kebab-case, becomes l1 artifact name
    path: ~/Downloads/ada-care-2024.pdf   # local file path or URL
    type: pdf                       # pdf | docx | xlsx | txt | md | url
    extract_text: true              # whether to attempt text extraction
    target: l1/ada-guidelines-2024  # destination path (without extension)
```

---

### ExtractPlan (PlanArtifact subtype)

**Front matter schema**:
```yaml
skill: diabetes-screening
plan_type: extract
version: "1.0"
created: "2026-04-03T19:00:00Z"
artifacts:
  - name: screening-criteria        # kebab-case L2 artifact name
    source: ada-guidelines-2024     # L1 artifact name (without extension)
    description: "Discrete criteria for identifying adults who should be screened"
  - name: risk-factors
    source: ada-guidelines-2024
    description: "Enumerated risk factor definitions with clinical thresholds"
```

---

### FormalizePlan (PlanArtifact subtype)

**Front matter schema**:
```yaml
skill: diabetes-screening
plan_type: formalize
version: "1.0"
created: "2026-04-03T19:00:00Z"
output_name: diabetes-screening-computable   # L3 artifact name
sources:                                     # L2 artifact names to combine
  - screening-criteria
  - risk-factors
sections:                                    # L3 sections to include
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

New `sources[]` array added to `tracking.yaml` to store ingest metadata. Existing `artifacts` block tracks L1/L2/L3; `sources` tracks registered raw files.

```yaml
# tracking.yaml — new sources block
sources:
  - name: ada-guidelines-2024       # matches ingest plan item name
    path: skills/diabetes-screening/l1/ada-guidelines-2024.md
    original_path: ~/Downloads/ada-care-2024.pdf   # source before copy
    type: pdf                       # pdf | docx | xlsx | txt | md | url
    ingested_at: "2026-04-03T19:00:00Z"
    checksum: "e3b0c44298fc1c..."   # SHA-256 of file at ingest time
    text_extracted: true            # false if pdftotext/pandoc unavailable
    url: null                       # populated for URL-type sources
```

**Checksum comparison** (used by `hi-status check-changes`):
- At ingest: compute `checksum = sha256(file)`, store in `sources[].checksum`
- At check-changes: compute `sha256(current_file)`, compare to stored value
- If mismatch: flag as CHANGED; list downstream L2 artifacts from `artifacts.l2[].derived_from`

---

### FrameworkSkill

A SKILL.md file in `skills/_framework/<name>/SKILL.md`. Not a clinical skill — excluded from `hi list` output.

**Frontmatter**:
```yaml
name: "hi-extract"
description: "Extract L2 artifacts from L1 sources. Modes: plan | implement | verify"
compatibility: "hi-skills-framework >= 0.1.0"
metadata:
  author: "Clinical Informatics Team"
  source: "skills/_framework/hi-extract/SKILL.md"
```

**Modes** (dispatched via `$ARGUMENTS` first positional arg):

| Skill | Mode | Reads | Writes |
|-------|------|-------|--------|
| `hi-discovery` | `plan` | tracking.yaml (domain) | `plans/discovery-plan.md` |
| `hi-discovery` | `implement` | `plans/discovery-plan.md` | `plans/ingest-plan.md` |
| `hi-ingest` | `plan` | `plans/discovery-plan.md` or user input | `plans/ingest-plan.md` |
| `hi-ingest` | `implement` | `plans/ingest-plan.md` | `l1/*`, tracking.yaml `sources[]` |
| `hi-ingest` | `verify` | tracking.yaml `sources[]` | *(none — read-only)* |
| `hi-extract` | `plan` | `l1/*`, tracking.yaml | `plans/extract-plan.md` |
| `hi-extract` | `implement` | `plans/extract-plan.md` | `l2/*` via `hi promote derive` |
| `hi-extract` | `verify` | `l2/*` | *(none)* via `hi validate` |
| `hi-formalize` | `plan` | `l2/*`, tracking.yaml | `plans/formalize-plan.md` |
| `hi-formalize` | `implement` | `plans/formalize-plan.md` | `l3/*` via `hi promote combine` |
| `hi-formalize` | `verify` | `l3/*` | *(none)* via `hi validate` |
| `hi-verify` | *(standalone)* | `l2/*` or `l3/*` | *(none)* |
| `hi-status` | `progress` | tracking.yaml | *(none)* |
| `hi-status` | `next-steps` | tracking.yaml, `plans/*`, `l1/*`, `l2/*`, `l3/*` | *(none)* |
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
[l1-ingested]
    │
    ▼ hi-extract plan
[extract-planned]
    │
    ▼ hi-extract implement
[l2-extracted]
    │
    ▼ hi-extract verify
[l2-verified]
    │
    ▼ hi-formalize plan
[formalize-planned]
    │
    ▼ hi-formalize implement
[l3-formalized]
    │
    ▼ hi-formalize verify
[l3-verified] ← terminal "computable" state
```

At any stage: `hi-status check-changes` may surface CHANGED sources → re-run from `hi-ingest implement`

---

## Validation Rules

### PlanArtifact
- `skill` must match an existing directory under `skills/`
- `plan_type` must be one of: `discovery | ingest | extract | formalize`
- `created` must be ISO-8601
- Plan-type-specific required fields (see subtypes above)

### IngestRecord
- `name` must be kebab-case
- `type` must be one of: `pdf | docx | xlsx | txt | md | url`
- `checksum` must be 64-char hex string (SHA-256)
- `ingested_at` must be ISO-8601

### FrameworkSkill (SKILL.md)
- Frontmatter `name` must match directory name (e.g., `hi-extract`)
- `compatibility` must reference `hi-skills-framework`
- Modes listed in `description` must be documented in body

---

## Relationships

```
SkillDirectory (1) ──── (0..4) PlanArtifact
SkillDirectory (1) ──── (0..*) IngestRecord    [in tracking.yaml sources[]]
SkillDirectory (1) ──── (0..*) L1Artifact
L1Artifact     (1) ──── (0..*) L2Artifact      [via derived_from]
L2Artifact     (1..*)──── (0..*) L3Artifact    [via converged_from]
IngestRecord   (1) ──── (0..1) L1Artifact      [same name]
IngestRecord   (1) ──── (0..*) L2Artifact      [via l1→l2 derived_from chain]
```
