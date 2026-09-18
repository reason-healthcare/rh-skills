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
- In `context Patient`, rely on the context to scope retrieves when the pinned
  FHIR ModelInfo declares the relevant Patient-to-resource relationship and the
  engine honors it; do not repeat the intended scope with
  `resource.subject.reference` comparisons against `Patient.id`. Preserve
  separate code, status, date, encounter, and provenance constraints that define
  the clinical relationship. The CQL
  [Context](https://cql.hl7.org/02-authorsguide.html#context) and
  [Retrieve Context](https://cql.hl7.org/02-authorsguide.html#retrieve-context)
  sections describe this scoping behavior; the model and engine must implement
  the relevant Patient-to-resource context relationship.
- If a runtime leaks another patient's resources through a `Patient`-context
  retrieve, treat it as an engine defect and block that runtime path; do not add
  a CQL subject-reference workaround.
- Do not replace unresolved clinical evidence with Boolean input parameters.
  Parameters are for runtime context such as `"Measurement Period"` or other
  explicitly external inputs, not for patient findings like diagnosis status,
  questionnaire burden, prior therapy history, or imaging evidence.
- For decision-table-derived logic, create retrieve-level helper defines for the
  underlying patient evidence, then derive the higher-level branch condition
  from those helpers.
- When a threshold is implied but not fully specified, keep the retrieve in CQL
  and attach an explicit TODO or named threshold helper. Do not collapse the
  evidence into a `default false` parameter.

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

## FHIR logical types and FHIRHelpers

The `rh` evaluator does not inject helper calls. For portable FHIR CQL, include
the versioned helper explicitly and make choice/primitive conversions through
FHIR logical types. For example, use
`FHIRHelpers.ToDateTime(E.period.start)` for a FHIR dateTime primitive and
`(A.value as FHIR.boolean).value` for a Boolean choice answer. For coded
concepts, declare a CodeSystem and Code or ValueSet and use a typed CQL
terminology operator; do not rebuild code identity with separate
`Coding.system`/`Coding.code` string comparisons. Name a non-primary code path
in the retrieve filter. Primitive status codes such as
`Observation.status = 'final'` remain ordinary status filters. See the focused
[CQL Style Guide](cql-style-guide.md) for before/after examples and model-path
checks.

Resolve the include through the topic's checked-in dependency files. For a
pinned external library, use `rh-skills cql import-library <topic>
<manifest.json>`; do not fetch helper source as an unverified side effect of
validation or packaging.

## Documentation expectations

For libraries with meaningful clinical impact, document:
- purpose
- major dependencies
- terminology assumptions
- runtime expectations
- known edge cases
