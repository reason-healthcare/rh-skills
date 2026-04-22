# Authoring Guidelines

These guidelines define how CQL should be written in this environment.

## Goals

- make logic readable and reviewable
- make runtime assumptions explicit
- reduce ambiguity around dates, intervals, nulls, and terminology
- make test design straightforward

## Library structure

Prefer this shape:

1. header and version
2. model declaration (`using FHIR version '4.0.1'`)
3. library includes (with explicit versions)
4. code system, value set, and code declarations (pinned)
5. parameter declarations
6. context declaration (`context Patient`)
7. helper definitions
8. derived logic
9. final output definitions

## Naming

- Use stable, descriptive names.
- Definition names should reflect actual behavior.
- Avoid vague labels such as `Check`, `Logic1`, or `Result`.
- If a definition expresses a boolean claim, phrase it as a question or assertion.

## Retrieve patterns

- Prefer narrow retrieves over broad retrieves with large downstream filtering.
- Encapsulate repeated retrieve filters in helpers when they represent a reusable
  semantic concept.
- Keep terminology-based filters close to the retrieve unless there is strong reuse value.

## Date and interval handling

- Make interval boundaries explicit (open vs closed).
- Be clear whether a threshold is inclusive or exclusive.
- Avoid hidden precision assumptions.
- When comparing timing to external events, document clinical intent in a comment.

## Null handling

- Treat null handling as a semantic decision, not an afterthought.
- If missing data should behave as false, make that visible in tests.
- If missing data should propagate uncertainty, keep that behavior visible to reviewers.

## Quantities and units

- Compare quantities only when unit assumptions are explicit on both sides.
- Prefer helper definitions when normalization logic is needed.

## Helper definitions

Use helpers when:
- logic repeats
- a retrieve/filter combination represents a named clinical concept
- a complex condition becomes easier to test in isolation

Avoid helpers that merely hide simple logic without adding clarity.

## FHIRHelpers note

The `rh` CLI evaluator is FHIRHelpers-agnostic — it does **not** inject
`FHIRHelpers.ToConcept` calls automatically. Include
`include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers` explicitly when
type coercions between FHIR and CQL system types are needed.

## Documentation expectations

For libraries with meaningful clinical impact, document:
- purpose
- major dependencies
- terminology assumptions
- runtime expectations
- known edge cases
