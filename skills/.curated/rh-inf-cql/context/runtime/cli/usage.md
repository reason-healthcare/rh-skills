# CLI Usage

Practical usage examples for the `rh-skills cql` commands.

## Validate a CQL library

```bash
rh-skills cql validate hyperlipidemia-treatment-monitoring HyperlipidemiaMonitoring
```

- Resolves the `.cql` file from `topics/<topic>/computable/<LibraryName>.cql`
- Runs `rh cql compile` on the file
- Reports translator errors and warnings
- Exits 0 on success, non-zero on error

## Translate CQL to ELM

```bash
rh-skills cql translate hyperlipidemia-treatment-monitoring HyperlipidemiaMonitoring
```

- Writes ELM JSON to `topics/<topic>/computable/<LibraryName>.elm.json`
- Same path resolution as validate

## Run Test Fixtures

```bash
rh-skills cql test hyperlipidemia-treatment-monitoring HyperlipidemiaMonitoring
```

- Discovers fixture cases under `tests/cql/HyperlipidemiaMonitoring/case-*/`
- For each case, runs `rh cql eval` for every expression in `expected/expression-results.json`
- Diffs actual vs expected output
- Reports pass/fail summary

## Per-Expression Evaluation (debug)

To evaluate a single expression manually:

```bash
rh cql eval \
  topics/hyperlipidemia-treatment-monitoring/computable/HyperlipidemiaMonitoring.cql \
  "Initial Population" \
  --data tests/cql/HyperlipidemiaMonitoring/case-001-basic-positive/input/bundle.json
```

## Where Outputs Are Written

| Output | Path |
|--------|------|
| ELM JSON | `topics/<topic>/computable/<LibraryName>.elm.json` |
| Test results | stdout / stderr (not persisted) |
| Validation report | stdout |

## Notes

- The `rh` CLI resolves library includes relative to the `.cql` file location.
- Fixture `bundle.json` must be a FHIR Bundle (type: collection or transaction).
- Expression names in `expression-results.json` must match CQL `define` names exactly (case-sensitive).
