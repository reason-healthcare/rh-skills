# Unit Expression Tests

This directory contains test fixtures that exercise single CQL `define`
expressions in isolation, independent of full library integration.

## Purpose

Unit expression tests are useful for:
- testing helper definitions independently
- testing complex interval or null logic in isolation
- debugging a specific expression without full library context
- building a golden-output set for regression detection

## Case Design

Each case should test exactly one expression with a focused, minimal fixture.
Prefer these case types:

| Type | Description |
|------|-------------|
| Positive | Expression evaluates as expected (true, non-empty, non-null) |
| Negative | Expression evaluates to false or empty |
| Null | Input missing; expression should produce null or default behavior |
| Boundary | Input at the threshold of the condition |

## Folder Pattern

```text
unit-expressions/
  <LibraryName>/
    <DefineName>/
      case-NNN-<description>/
        input/bundle.json
        expected/expression-results.json
        notes.md
```

## Running a Single Expression

```bash
rh cql eval \
  topics/<topic>/computable/<LibraryName>.cql \
  "DefineName" \
  --data tests/cql/unit-expressions/<LibraryName>/<DefineName>/<case>/input/bundle.json
```

## Notes

- `expression-results.json` should only include the single expression under test.
- Keep fixtures minimal — only the resources needed to drive the expression.
