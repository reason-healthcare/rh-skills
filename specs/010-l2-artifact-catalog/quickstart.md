# Quickstart: L2 Artifact Catalog Expansion

**Feature**: 010-l2-artifact-catalog

## What Changed

1. **4 new L2 artifact types**: `clinical-frame`, `decision-table`, `assessment`, `policy`
2. **Directory restructure**: L2 artifacts now live at `structured/<name>/<name>.yaml`
3. **New command**: `rh-skills render <topic> <artifact>` generates SME-reviewable views

## Try It

### 1. Extract with new types

Run the extract skill against a guideline containing decision tables, assessments,
or policy language. The planner will propose the new artifact types automatically.

### 2. Derive an artifact (new path)

```bash
rh-skills promote derive <topic> <artifact-name>
# Output: topics/<topic>/structured/<artifact-name>/<artifact-name>.yaml
```

### 3. Render views

```bash
rh-skills render <topic> <artifact-name>
# Output: topics/<topic>/structured/<artifact-name>/views/
#   - Type-specific views (mermaid, markdown, completeness reports)
```

### 4. Validate

```bash
rh-skills validate <topic> l2 <artifact-name>
# Resolves at the new subdirectory path
```

## New Artifact Types at a Glance

| Type | Purpose | Generated Views |
|------|---------|----------------|
| `clinical-frame` | PICOTS scope framing | PICOTS summary table |
| `decision-table` | Condition-action rules | Rules table, decision tree, completeness report |
| `assessment` | Screening instruments | Questionnaire, scoring summary |
| `policy` | Prior auth / coverage | Criteria flowchart, requirements checklist |
