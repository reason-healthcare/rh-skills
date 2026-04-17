# Data Model: L2 Artifact Catalog Expansion

**Feature**: 010-l2-artifact-catalog  
**Date**: 2026-04-17

## Entities

### Artifact Profile (EXTRACT_ARTIFACT_PROFILES entry)

Defines planner keyword matching for a single artifact type.

| Field | Type | Description |
|-------|------|-------------|
| artifact_type | string | Kebab-case type identifier (e.g., `decision-table`) |
| keywords | tuple[str] | Keywords that trigger this profile during plan extraction |
| section | string | Default section name in L2 YAML |
| key_question | string | Clinical question the planner poses for this type |

**4 new entries**:

| artifact_type | keywords | section | key_question |
|---------------|----------|---------|--------------|
| `clinical-frame` | `("picot", "pico", "clinical question", "scope", "framing")` | `frames` | What are the clinical questions this topic must answer (PICOTS)? |
| `decision-table` | `("decision table", "condition", "action", "rule", "if-then")` | `decision_table` | What conditions and actions form the decision logic? |
| `assessment` | `("assessment", "screening", "questionnaire", "instrument", "phq", "gad", "score")` | `assessment` | What assessment instruments or scoring tools are specified? |
| `policy` | `("policy", "prior auth", "authorization", "coverage", "documentation requirement", "payer")` | `policy` | What coverage, authorization, or documentation policies apply? |

### L2 Artifact — Type-Specific Section Shapes

All L2 artifacts share the common metadata fields (id, name, title, version, status,
domain, description, derived_from, artifact_type, clinical_question, sections,
evidence_traceability, conflicts). The following defines the type-specific section
content.

#### clinical-frame

```yaml
sections:
  frames:
    - id: frame-1
      population: <string>       # P — target population
      intervention: <string>     # I — intervention or exposure
      comparison: <string>       # C — comparator (may be "none" or "standard of care")
      outcomes:                  # O — expected outcomes (list)
        - <string>
      timing: <string>           # T — time horizon
      setting: <string>          # S — clinical setting
```

#### decision-table (Shiffman augmented model)

```yaml
sections:
  conditions:
    - id: c1
      label: <string>           # Human-readable condition name
      values:                   # Possible values (modulus = len(values))
        - <string>
  actions:
    - id: a1
      label: <string>           # Human-readable action name
  rules:
    - id: r1
      when:                     # Map of condition_id → value (or "-" for irrelevant)
        c1: <value | "-">
      then:                     # List of action IDs triggered
        - a1
```

**Completeness invariant**: `product(len(c.values) for c in conditions)` should equal
the sum of coverage counts across all rules, where a rule's coverage =
`product(len(c.values) for c where rule.when[c.id] == "-")`.

#### assessment

```yaml
sections:
  instrument:
    name: <string>              # e.g., "PHQ-9"
    purpose: <string>           # What the instrument measures
    population: <string>        # Target population
  items:
    - id: q1
      text: <string>            # Question text
      type: <ordinal|boolean|choice|numeric|text>
      options:                  # Required for ordinal/choice types
        - value: <int|string>
          label: <string>
  scoring:
    method: <sum|weighted|algorithm>
    ranges:
      - range: <string>         # e.g., "0-4"
        interpretation: <string> # e.g., "Minimal depression"
```

#### policy

```yaml
sections:
  applicability:
    payer_types:                # Which payer contexts apply
      - <string>
    service_category: <string>  # e.g., "outpatient behavioral health"
    codes:                      # Applicable procedure/diagnosis codes
      - system: <string>        # e.g., "CPT", "ICD-10"
        values:
          - <string>
  criteria:
    - id: cr1
      description: <string>
      requirement_type: <clinical|documentation|temporal>
      rule: <string>            # Human-readable rule statement
  actions:
    approve:
      conditions: <string>      # When to approve
    deny:
      conditions: <string>      # When to deny
      details: <string>         # Denial details/appeal info
    pend:
      conditions: <string>      # When to pend for review
```

### Generated View

| Field | Type | Description |
|-------|------|-------------|
| path | string | `structured/<name>/views/<filename>` |
| format | string | `.mmd` (mermaid), `.md` (markdown) |
| source | string | Artifact type that generated it |

**Type → View mapping**:

| Artifact Type | Generated Views |
|---------------|----------------|
| `clinical-frame` | `picots-summary.md` (PICOTS table) |
| `decision-table` | `rules-table.md` (markdown table), `decision-tree.mmd` (mermaid), `completeness-report.md` |
| `assessment` | `questionnaire.md` (rendered items), `scoring-summary.md` (ranges table) |
| `policy` | `criteria-flowchart.mmd` (mermaid), `requirements-checklist.md` |
| *(any other)* | `summary.md` (generic metadata + sections dump) |

### Formalize Section Mappings

| Artifact Type | L3 Required Section |
|---------------|-------------------|
| `decision-table` | `actions` |
| `assessment` | `assessments` |
| `policy` | `actions` |
| `clinical-frame` | *(none — scoping only)* |

## State Transitions

No new state transitions. L2 artifacts follow the existing lifecycle:
`plan → derive → (validate) → approve → formalize(combine)`

The `render` command is stateless — it can be run at any lifecycle point after derive.
It does not append tracking events or change artifact status.

## Relationships

```
EXTRACT_ARTIFACT_PROFILES  ──defines──▶  artifact_type
L2 Artifact                ──has──▶      artifact_type
L2 Artifact                ──generates──▶ Generated Views (via render)
_formalize_required_sections ──maps──▶   artifact_type → L3 section
```
