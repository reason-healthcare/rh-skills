# Contract: L2 Artifact Schema for 005

**Phase 1 Design Artifact** | **Branch**: `005-rh-inf-extract`

---

## File

`topics/<topic>/structured/<artifact-name>.yaml`

## Required Top-Level Fields

Existing required fields retained from `rh-skills promote derive`:

```yaml
id: <kebab-case>
name: <machine-name>
title: <human title>
version: "1.0.0"
status: draft
domain: <clinical domain>
description: <2-4 sentence description>
derived_from:
  - <source-name>
```

005-specific required additions:

```yaml
artifact_type: <catalog type>
clinical_question: <string>
sections: <mapping>
```

## Traceability Expectations

Structured content should support claim-level evidence references:

```yaml
sections:
  criteria:
    - claim_id: crit-001
      statement: <structured claim text>
      evidence:
        - source: <source-name>
          locator: <section / page / heading>
```

## Conflict Expectations

When the plan lists unresolved conflicts, the artifact must contain a conflict record:

```yaml
conflicts:
  - issue: <summary>
    positions:
      - source: <source-name>
        statement: <source-specific interpretation>
    preferred_interpretation:
      source: <source-name>
      rationale: <why preferred>
```

## Multi-Source Rules

- `derived_from[]` may contain multiple normalized-source names.
- The set of `derived_from[]` should match the approved artifact source set from the review packet.
- Duplicate source names are not allowed.

## Decision Table Phase Support

For `decision-table` artifacts supporting three-tier CPG architecture:

```yaml
sections:
  pathway_phases:  # optional
    - id: assessment
      name: Assessment Phase
      trigger: surgery_considered  # CQL expression or "always"
  
  rules:
    - id: avoid-antibacterial
      phase: assessment  # optional; references pathway_phases[].id
      event: assessment-complete
      when: {...}
      then: [...]
```

**Validation rules**:
- If `pathway_phases` present AND rule has `phase`, validate phase exists in `pathway_phases[].id`
- If `pathway_phases` present, warn if rules missing `phase` assignments
- `phase` and `event` are independent: event triggers evaluation, phase groups organizationally

## Validation Implications

`rh-inf-extract verify` should fail an artifact when:
- any required top-level field is missing
- `derived_from[]` is empty
- required sections declared by the approved plan are absent
- claim/evidence references are missing where required
- conflict records are absent despite unresolved conflicts in the plan
- (decision-table) rule references unknown phase when `pathway_phases` present
