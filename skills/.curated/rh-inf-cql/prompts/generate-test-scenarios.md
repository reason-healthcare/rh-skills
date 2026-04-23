# Generate Test Scenarios

Use this prompt to generate focused test scenarios for a CQL library or definition.

## Prompt

Generate test scenarios for the target CQL definition or library. Use the
testing strategy in `docs/testing-strategy.md`.

## Required Scenario Types

For each important definition, produce at minimum:

| Case type | Purpose |
|-----------|---------|
| Positive | Nominal true / expected-result path |
| Negative | Nominal false / contrasting result |
| Null / missing-data | Absent resource, missing date, incomplete evidence |
| Boundary | Just below / exactly at / just above a threshold |
| Conflicting evidence | Multiple facts that might cause ambiguity |
| Terminology | In-valueset / out-of-valueset / version-drift behavior |
| Multi-event | Earliest, latest, first, or any-match semantics (when relevant) |

## Output Format

For each scenario:

```
### case-NNN-<description>

**Type**: boundary
**Expression under test**: "ObservationInPeriod"
**Expected result**: false
**Semantic point**: date exactly one day before the period start is excluded

**Input summary**:
- Patient: 45-year-old male
- Observation: LDL result dated 2023-12-31 (one day before period start 2024-01-01)

**Fixture path**: tests/cql/<LibraryName>/case-NNN-<description>/

**Bundle structure**:
- Patient resource
- Observation resource with effectiveDateTime 2023-12-31
```

## Fixture Skeleton

Also provide a minimal `bundle.json` structure the fixture should use:

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "id": "p1", ... } },
    { "resource": { "resourceType": "Observation", "id": "obs1", ... } }
  ]
}
```

And a corresponding `expected/expression-results.json`:

```json
{
  "ExpressionName": false
}
```

Use `rh-skills cql test <topic> <LibraryName>` to run all cases against the library.
