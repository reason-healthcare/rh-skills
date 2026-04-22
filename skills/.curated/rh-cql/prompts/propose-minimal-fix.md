# Propose Minimal Fix

Use this prompt after `explain-failure.md` to propose the smallest safe change.

## Prompt

Propose the smallest safe change to address the identified issue.

## Output Format

### What Changes Semantically
Describe the behavioral difference introduced by the fix.
Be specific: which expression, which operator, which boundary.

### What Remains Unchanged
Confirm that no other definitions or behaviors are affected by the change.
If uncertain, say so explicitly.

### Before / After

```diff
- define "ObservationInPeriod":
-   exists([Observation] O where O.effective during "Measurement Period")
+ define "ObservationInPeriod":
+   exists([Observation: "LDL Test"] O where O.effective during "Measurement Period")
```

### Test Cases to Add or Update

List the cases that must be created or modified:

| Case | Type | Change |
|------|------|--------|
| case-005-terminology-filter | positive | New case: in-valueset code passes |
| case-006-terminology-negative | negative | New case: out-of-valueset code excluded |

### Validation Steps

After applying the fix:

1. Run `rh-skills cql validate <topic> <LibraryName>` — expect exit 0.
2. Run `rh-skills cql test <topic> <LibraryName>` — all cases should pass.
3. Confirm the original failure case now produces the expected result.
