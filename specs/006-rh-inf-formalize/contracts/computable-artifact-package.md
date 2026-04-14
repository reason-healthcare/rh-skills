# Contract: Computable Artifact Package for 006

**Phase 1 Design Artifact** | **Branch**: `006-rh-inf-formalize`

---

## File

`topics/<topic>/computable/<artifact-name>.yaml`

## Required Top-Level Fields

Existing required fields retained from `rh-skills promote combine`:

```yaml
artifact_schema_version: "1.0"
metadata:
  id: <kebab-case>
  name: <machine-name>
  title: <human title>
  version: "1.0.0"
  status: <draft | active | retired>
  domain: <clinical domain>
  created_date: <YYYY-MM-DD>
  description: <string>
converged_from:
  - <l2-artifact-name>
```

## Primary Output Shape

Formalize v1 produces a pathway-oriented package. The approved plan may require
supporting sections such as:
- `pathways`
- `actions`
- `value_sets`
- `measures`
- `assessments`
- `libraries`

## Section Completeness Expectations

When a section is required by the approved plan:

- `pathways` must contain at least one pathway with one or more `steps`
- `actions` must contain at least one action with `intent` and either
  `description` or `conditions`
- `value_sets` must contain one or more coded entries in `codes`
- `measures` must contain both `numerator` and `denominator`
- `libraries` must contain both `language` and `content`
- `assessments` must contain one or more `items`

## Convergence Rules

- `converged_from[]` must match the approved `input_artifacts[]` set exactly.
- Duplicate L2 input names are not allowed.
- Only the single approved implementation target from the formalize plan may be
  created during implement.

## Validation Implications

`rh-inf-formalize verify` should fail an artifact when:
- any required top-level field is missing
- `converged_from[]` is empty or differs from the approved plan
- a required section from the approved plan is absent
- a required section is present but incomplete for its section type
