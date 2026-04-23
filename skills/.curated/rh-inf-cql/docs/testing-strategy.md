# Testing Strategy

This project uses CLI-driven testing to validate CQL behavior through focused
fixtures and expected outputs.

## Principles

- Test semantic points in isolation whenever possible.
- Prefer many small focused cases over a few broad, hard-to-debug cases.
- Preserve regression cases forever unless they are intentionally obsolete.
- Compare expected outputs for key intermediate definitions, not only final outputs.

## Scenario Types

For each important definition, consider these scenario types:

### Positive case
The condition should clearly evaluate as true or produce the expected result.

### Negative case
Similar input that should clearly evaluate as false or produce a contrasting result.

### Null or missing-data case
Exercise absent values, omitted resources, missing dates, or incomplete evidence.

### Boundary case
Exercise just below, exactly at, and just above a threshold.

### Conflicting evidence case
Include multiple facts that might lead to ambiguity if the logic is too loose.

### Terminology case
Verify behavior when a concept is in-value-set, out-of-value-set, or subject
to version drift.

### Multi-event case
Verify whether earliest, latest, first, or any-match semantics work as intended.

## Folder Pattern

```text
tests/cql/<LibraryName>/
  case-NNN-<description>/
    input/
      bundle.json       # FHIR Bundle with patient and clinical data
    expected/
      expression-results.json   # { "ExpressionName": <expected value> }
    notes.md            # Why this case exists; what semantic point it isolates
```

## Expression-Level Evaluation

Run the evaluator per expression to isolate failures:

```bash
rh cql eval \
  topics/<topic>/computable/<LibraryName>.cql \
  "ExpressionName" \
  --data tests/cql/<LibraryName>/<case>/input/bundle.json
```

Or use `rh-skills cql test <topic> <LibraryName>` to run all cases at once.

## Regression Discipline

Every production bug or meaningful review finding should become:
- a minimal failing fixture bundle
- an expected result
- a short `notes.md` describing the defect category (from the Failure Categories table)

These live in `tests/cql/regression/`.

## Test Subdirectories

| Directory | Purpose |
|-----------|---------|
| `tests/cql/<LibraryName>/` | Per-library nominal cases |
| `tests/cql/regression/` | Bugs that have been fixed; run every time |
| `tests/cql/boundary-cases/` | Threshold and interval edge cases |
| `tests/cql/terminology/` | Value set membership and version sensitivity |
| `tests/cql/unit-expressions/` | Isolated single-expression tests |
