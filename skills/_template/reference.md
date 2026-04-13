# Reference: `<skill-name>` — Schemas, Field Definitions & Validation Rules

<!-- ─────────────────────────────────────────────────────────────────────────
  LEVEL 3 DISCLOSURE — loaded on demand when the agent needs detailed schema
  information. Keep the SKILL.md lean by offloading all field-level detail here.
  ───────────────────────────────────────────────────────────────────────── -->

## Plan Schema

The plan artifact is a Markdown file with YAML front matter written by `plan`
mode and consumed by `implement` mode. Location:
`topics/<topic>/process/plans/<skill-name>-plan.md`

### Required Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `topic` | string | Must match a topic in `rh-skills list` | Topic identifier (kebab-case) |
| `plan_type` | string | Must equal `"<skill-name>"` | Identifies the plan type |
| `version` | string | Semver, e.g. `"1.0"` | Plan artifact schema version |
| `created` | string | ISO-8601 (e.g. `2026-04-04T14:00:00Z`) | When the plan was written |
| <!-- add skill-specific required fields here --> | | | |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `force_overwrite` | bool | `false` | If `true`, implement may overwrite existing outputs |
| <!-- add skill-specific optional fields here --> | | | |

### Skill-Specific Front Matter

```yaml
# Replace this block with the actual plan-type-specific fields.
# See data-model.md for the <PlanType>Plan subtype schema.
<field>:
  - <example-value>   # required — <description>
<optional_field>: <default>  # optional — <description>
```

---

## Output Artifact Schema

<!-- Describe the artifacts this skill produces: L2 (structured/) or L3 (computable/) -->

### L2 Structured Artifact (`topics/<topic>/structured/<name>.yaml`)

```yaml
# Required fields
name: <artifact-name>           # string, kebab-case — must match filename
topic: <topic-name>             # string — must match topic in tracking.yaml
level: l2                       # literal "l2"
version: "1.0"                  # string

# Provenance (required for tracking.yaml linkage)
derived_from:                   # list[string] — source file names in sources[]
  - <source-name>

# Clinical content (skill-specific — replace with actual fields)
# required_clinical_field: ...
# optional_clinical_field: ...

# Metadata
created_at: <ISO-8601>          # string — set by rh-skills promote derive
```

### L3 Computable Artifact (`topics/<topic>/computable/<name>.yaml`)

```yaml
# Required fields
name: <artifact-name>           # string, kebab-case
topic: <topic-name>             # string
level: l3                       # literal "l3"
version: "1.0"                  # string

# Provenance (required for tracking.yaml linkage)
converged_from:                 # list[string] — structured artifact names
  - <structured-artifact-name>

# FHIR-compatible sections (include those applicable to this skill)
pathways: []                    # Clinical decision logic
measures: []                    # Quality measure definitions
value_sets: []                  # Coded concept groupings

# Metadata
created_at: <ISO-8601>
```

---

## Validation Rules

### Plan Artifact Validation

- `topic` — MUST match an entry in `rh-skills list` output
- `plan_type` — MUST equal `"<skill-name>"`
- `version` — MUST be a string in `"MAJOR.MINOR"` format
- `created` — MUST be ISO-8601 with timezone offset
- All items in skill-specific arrays MUST have all their required sub-fields

### L2 Artifact Validation (run by `rh-skills validate`)

| Field | Rule |
|-------|------|
| `name` | Required; kebab-case; matches file basename |
| `level` | Required; must equal `"l2"` |
| `derived_from` | Required; non-empty list; each entry must exist in `sources[]` |
| `<clinical_field>` | Required; <constraint> |
| `<optional_field>` | Optional; <constraint> |

### L3 Artifact Validation (run by `rh-skills validate`)

| Field | Rule |
|-------|------|
| `name` | Required; kebab-case; matches file basename |
| `level` | Required; must equal `"l3"` |
| `converged_from` | Required; non-empty list; each entry must exist in `structured[]` |
| `pathways` OR `measures` | At least one must be non-empty |

---

## Clinical Standards & Terminology

<!-- Document any domain-specific standards this skill applies.
     Link to external standards bodies where appropriate. -->

| Standard | Use In This Skill | Reference |
|----------|--------------------|-----------|
| FHIR R4 | L3 computable artifacts | https://hl7.org/fhir/R4/ |
| SNOMED CT | Coded clinical concepts | https://www.snomed.org/ |
| LOINC | Lab and clinical observation codes | https://loinc.org/ |
| ICD-10-CM | Diagnosis codes | https://www.cdc.gov/nchs/icd/ |
| <!-- add others relevant to this skill --> | | |

---

## Evidence Grading

When synthesising sources in `plan` mode, grade evidence quality using this
scale (aligned with GRADE methodology):

| Grade | Symbol | Description |
|-------|--------|-------------|
| High | `A` | Consistent evidence from well-designed RCTs or overwhelming observational evidence |
| Moderate | `B` | Evidence from RCTs with limitations, or strong observational studies |
| Low | `C` | Observational studies or RCTs with major limitations |
| Very Low | `D` | Expert opinion, case reports, or extrapolated evidence |

Include the evidence grade in the plan's "Evidence Summary" section for each source.

---

## Glossary

<!-- Define domain terms specific to this skill. Keep short — link out for depth. -->

| Term | Definition |
|------|------------|
| L1 (Sources) | Raw clinical source materials (PDFs, guidelines, articles) |
| L2 (Structured) | Semi-structured YAML artifacts derived from L1 sources |
| L3 (Computable) | Fully structured FHIR-compatible YAML artifacts converged from L2 |
| Plan artifact | Markdown + YAML front matter file produced by `plan` mode; reviewed by a human before `implement` runs |
| derived_from | List of L1 source names that a structured artifact was extracted from |
| converged_from | List of L2 structured artifact names combined into a computable artifact |
| <!-- add skill-specific terms --> | |
