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
        evaluation-context.json ← subject, evaluation date, period, generic parameters (optional)
        terminology.json     ← pre-expanded ValueSet or Bundle of ValueSets (optional)
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

For SDC extraction workflows, `bundle.json` should contain the Observations
actually produced by the extraction step. A separate `terminology.json` may
contain one complete, versioned FHIR `ValueSet` or a Bundle containing complete
ValueSets; the CQL runner passes it to `rh cql eval --terminology`. Do not use
an expected normalized extraction Bundle as proof that a live extraction
produced those Observations.

### `patient.json` (optional)

A standalone `Patient` resource. When present, it can be used as the evaluation
context (`context Patient`). If omitted, exactly one `Patient` resource in
`bundle.json` may be inferred. A Bundle with multiple Patients requires an
explicit `subject`; the runner never chooses by entry order.

### `evaluation-context.json` (optional)

Provide explicit evaluation context when a bundle contains multiple Patients or
the CQL depends on a fixed clock, measurement period, or other named parameter:

```json
{
  "subject": "Patient/test-patient",
  "evaluationDate": "2026-06-15T09:20:00Z",
  "measurementPeriod": {
    "start": "2026-01-01T00:00:00Z",
    "end": "2026-12-31T23:59:59Z",
    "startInclusive": true,
    "endInclusive": true
  },
  "parameters": {
    "IncludeHistoricalData": false
  }
}
```

`subject` accepts a FHIR reference (`Patient/id`) or an id (normalized to
`Patient/id`), and the selected Patient must exist in the Bundle or
`patient.json`. If omitted, the runner infers one Patient only when the input
is unambiguous; multiple Patients require an explicit `subject`.
`evaluationDate` is passed as the evaluator clock.
`measurementPeriod` is sent both as evaluator boundary flags and as the full
`Measurement Period` CQL parameter, preserving the supplied inclusivity flags.
Other `parameters` are sent as JSON values. Values from
`evaluation-context.json` override same-named entries from `parameters.json`.

`rh-skills cql test` passes the topic computable directory as `--lib-path`, so
versioned local includes are available during evaluation. Direct `rh cql eval`
calls must pass the same `--lib-path` explicitly.

When `input/terminology.json` exists, `rh-skills cql test` also passes that
path as `--terminology`. The runtime resolves only the complete ValueSet
expansions supplied there; it does not fetch expansions during evaluation.

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
2. Loads optional `evaluation-context.json`, `parameters.json`, and
   `patient.json` from the case input.
3. For each `<define>` in `expected/expression-results.json`, runs:
   ```bash
   rh cql eval <LibraryName>.cql "<define>" --data input/bundle.json \
     --subject Patient/test-patient \
     --evaluation-date 2026-06-15T09:20:00Z \
     --measurement-period-start 2026-01-01T00:00:00Z \
     --measurement-period-end 2026-12-31T23:59:59Z \
     --parameter 'Measurement Period={"start":"2026-01-01T00:00:00Z","end":"2026-12-31T23:59:59Z","startInclusive":true,"endInclusive":true}'
   ```
   Context flags are included only when present. The full interval is passed as
   JSON under the exact CQL parameter name, so inclusive/exclusive semantics are
   not inferred from the start/end flags.
4. Compares stdout to the expected JSON value with strict type matching
   (`true` differs from `1`; `null` remains distinct).
5. Reports `PASS` or `FAIL` per expression per case
6. Exits non-zero if any case fails

---

## Minimal Worked Example

See `tests/cql/example-library/case-001-basic-positive/` for a minimal
structurally-valid fixture pair.
