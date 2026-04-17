# CLI Contract: `rh-skills render`

**Feature**: 010-l2-artifact-catalog  
**Date**: 2026-04-17

## Command Signature

```
rh-skills render <topic> <artifact>
```

**Arguments**:
- `topic` (required): Topic name (kebab-case)
- `artifact` (required): Artifact name (kebab-case)

**Options**: None (single artifact only, no batch mode)

## Behavior

1. Resolve artifact path: `topics/<topic>/structured/<artifact>/<artifact>.yaml`
2. If file does not exist → exit 1 with error: `Artifact not found: <path>`
3. Load YAML and read `artifact_type`
4. Validate type-specific required sections exist:
   - `clinical-frame` requires: `sections.frames`
   - `decision-table` requires: `sections.conditions`, `sections.actions`, `sections.rules`
   - `assessment` requires: `sections.instrument`, `sections.items`, `sections.scoring`
   - `policy` requires: `sections.applicability`, `sections.criteria`, `sections.actions`
   - All other types: no type-specific validation (generic renderer)
5. If required sections missing → exit 1 with error listing missing sections
6. Create `views/` directory alongside the artifact YAML
7. Dispatch to type-specific renderer (or generic fallback)
8. Write generated view files to `views/`
9. Print summary of files written → exit 0

## Output Files

Written to: `topics/<topic>/structured/<artifact>/views/`

All files are overwritten on each invocation (idempotent).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Views generated successfully |
| 1 | Artifact not found or missing required sections |
| 2 | Usage error (missing arguments) |

## No Tracking Events

The render command does NOT append tracking events. It is a stateless
transformation with no lifecycle side effects.
