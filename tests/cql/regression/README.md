# Regression Tests

This directory contains regression test fixtures for CQL logic bugs that have
been identified and fixed.

## Purpose

- Ensure fixed bugs do not reoccur.
- Provide a concrete defect taxonomy over time.
- Serve as reference cases for the rh-inf-cql skill when explaining failures.

## Adding a Regression Case

1. Create `<LibraryName>/case-NNN-<description>/`:

   ```text
   regression/
     HyperlipidemiaMonitoring/
       case-001-null-ldl-observation/
         input/bundle.json
         expected/expression-results.json
         notes.md
   ```

2. In `notes.md`, record:
   - The defect category (from the Failure Categories table in SKILL.md)
   - What the bug was
   - What the fix was
   - Why this case isolates the problem

3. Run `rh-skills cql test <topic> <LibraryName>` to confirm the case passes.

## Defect Categories

Refer to `skills/.curated/rh-inf-cql/SKILL.md` for the full Failure Categories table.
Common regression categories:
- `null-propagation`
- `interval-boundary`
- `terminology-resolution`
- `temporal-precision`
- `fixture-or-data-shape`
