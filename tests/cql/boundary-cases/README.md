# Boundary Cases

This directory contains test fixtures that exercise threshold and interval
edge cases in CQL logic.

## Purpose

Boundary cases are the most common source of off-by-one errors in CQL,
especially for:
- date-based inclusion/exclusion criteria
- age thresholds
- observation value ranges
- measurement period boundaries

## Case Design

For each threshold, create three cases:

| Variant | Description |
|---------|-------------|
| `just-below` | Input is one unit below the boundary — expect exclusion |
| `exactly-at` | Input is exactly at the boundary — expect inclusion (or exclusion, state clearly) |
| `just-above` | Input is one unit above the boundary — expect inclusion |

## Folder Pattern

```text
boundary-cases/
  <LibraryName>/
    case-NNN-age-threshold-just-below/
      input/bundle.json
      expected/expression-results.json
      notes.md
```

## Notes File Requirements

Each `notes.md` should state:
- Which threshold or interval is being tested
- Whether the boundary is inclusive or exclusive in the CQL
- The clinical intent
- What value or date is used and why
