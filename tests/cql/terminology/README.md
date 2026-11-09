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
| `paired-positive` | Concept matches only the source-defined positive category — expect true |
| `paired-negative` | Concept matches only the source-defined contrasting category — expect false |
| `paired-neither` | Concept matches neither category — expect null |
| `paired-conflict` | A multi-coded Concept matches both categories — expect null or a separately authored data-quality result |
| `paired-wrong-type` | The FHIR choice value is absent or not a CodeableConcept — expect null |
| `paired-unresolved` | A required category ValueSet is missing, incomplete, or the wrong canonical/version — expect execution failure |

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
- For paired classifications, the source contract for both categories and
  evidence that their versioned memberships are mutually exclusive

## Offline Evaluation Notes

The `rh` evaluator resolves terminology offline by default. Pre-expand value
sets and bundle them in the fixture, or configure a terminology service.
See `skills/.curated/rh-inf-cql/docs/terminology-policy.md`.
