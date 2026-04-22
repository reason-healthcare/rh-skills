# Terminology Tests

This directory contains test fixtures that exercise terminology membership,
version sensitivity, and resolution behavior in CQL logic.

## Purpose

Terminology failures are often silent — a code is simply not found and the
expression returns null or false without an obvious error. These tests make
terminology assumptions explicit and testable.

## Case Types

| Type | Description |
|------|-------------|
| `in-valueset` | Code is a member of the value set — expect inclusion |
| `out-of-valueset` | Code is not a member — expect exclusion |
| `missing-code` | No code present on the resource — expect null/false |
| `version-sensitive` | Code is in one version but not another — test both |

## Folder Pattern

```text
terminology/
  <LibraryName>/
    case-NNN-snomed-in-valueset/
      input/bundle.json
      expected/expression-results.json
      notes.md
```

## Notes File Requirements

Each `notes.md` should record:
- The value set URL and version being tested
- The specific code used in the fixture
- Whether the code is expected to be in or out of the value set
- The code system and code (e.g., SNOMED 44054006)

## Offline Evaluation Notes

The `rh` evaluator resolves terminology offline by default. Pre-expand value
sets and bundle them in the fixture, or configure a terminology service.
See `skills/.curated/rh-cql/docs/terminology-policy.md`.
