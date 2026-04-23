# tests/cql — Fixture Directory Schema

This directory contains fixture-based integration tests for CQL libraries
authored with the `rh-inf-cql` skill. Each library gets its own subdirectory,
which contains one or more test cases.

---

## Directory Layout

```
tests/cql/
  <LibraryName>/
    case-NNN-<description>/
      input/
        bundle.json          ← FHIR R4 Bundle (required)
        patient.json         ← standalone Patient resource (optional)
        parameters.json      ← CQL parameter overrides (optional)
      expected/
        expression-results.json  ← expected define-name → value map
      notes.md               ← brief description of what the case tests
```

---

## Input Files

### `bundle.json` (required)

A FHIR R4 Bundle used as the data context for evaluation. Minimum structure:

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "test-patient",
        "birthDate": "1970-01-15",
        "gender": "male"
      }
    }
  ]
}
```

Additional entries (Condition, Observation, MedicationRequest, …) provide
the clinical data the CQL expressions retrieve.

### `patient.json` (optional)

A standalone `Patient` resource. When present, it is used as the evaluation
context (`context Patient`). If omitted, the first `Patient` resource in
`bundle.json` is used.

### `parameters.json` (optional)

CQL parameter overrides in FHIR Parameters format. Use this to set the
`"Measurement Period"` or other named parameters:

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "Measurement Period",
      "valuePeriod": {
        "start": "2024-01-01",
        "end": "2024-12-31"
      }
    }
  ]
}
```

---

## Expected Output

### `expected/expression-results.json`

A JSON object mapping each CQL `define` name to its expected evaluated value.
Only the defines you want to assert need to be listed.

```json
{
  "IsAdult": true,
  "HasHyperlipidemia": false,
  "MostRecentLDLValue": null
}
```

Supported value types follow CQL → JSON mapping:
- Boolean: `true` / `false`
- Integer: `42`
- Decimal: `3.14`
- String: `"active"`
- Null/unknown: `null`
- Interval (serialized): `{ "low": "2024-01-01", "high": "2024-12-31" }`

---

## Case Naming Convention

Use the pattern `case-NNN-<description>` where:
- `NNN` is a zero-padded sequence (001, 002, …)
- `<description>` is a short kebab-case label for what the case exercises

Recommended case families for each rule:

| Suffix | What it tests |
|--------|---------------|
| `basic-positive` | Nominal true/meet scenario |
| `basic-negative` | Nominal false/not-meet scenario |
| `null-absent` | Missing/null required resource |
| `boundary-<aspect>` | Edge value (age, date, count) |
| `terminology-match` | Code in valueset |
| `terminology-no-match` | Code not in valueset |
| `multi-event` | Multiple qualifying events |
| `conflicting-evidence` | Conflicting data, expected tie-breaking |

---

## Test Runner

The `rh-skills cql test` command discovers and runs all cases automatically:

```bash
rh-skills cql test <topic> <LibraryName>
```

For each case it:
1. Resolves `topics/<topic>/computable/<LibraryName>.cql`
2. For each `<define>` in `expected/expression-results.json`, runs:
   ```bash
   rh cql eval --expr "<define>" --data input/bundle.json <LibraryName>.cql
   ```
3. Compares stdout to the expected value (JSON then string fallback)
4. Reports `PASS` or `FAIL` per expression per case
5. Exits non-zero if any case fails

---

## Minimal Worked Example

See `tests/cql/example-library/case-001-basic-positive/` for a minimal
structurally-valid fixture pair.
