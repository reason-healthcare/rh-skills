# Engine Notes

Behavior specific to the `rh` CQL evaluator.

## Key Differences from Reference Java Evaluator

### Pinned FHIRHelpers dependency

The `rh` evaluator does not inject FHIRHelpers automatically. Portable CQL
declares a versioned include:

`include FHIRHelpers version '4.0.1' called FHIRHelpers`

Resolve the include from pinned local CQL/ELM files. Use
`rh-skills cql import-library <topic> <manifest.json>` to verify hashes and
identity, add the FHIR Library, and record dependency provenance. The primary
FHIR Library must declare the helper in `relatedArtifact`.

For choice elements, use FHIR logical types (for example,
`(A.value as FHIR.boolean).value`). Traverse CodeableConcept `coding` and match
both system and code. Validate portable CQL with a reference translator too.

### Terminology Resolution

The evaluator performs no implicit terminology lookup. Pin terminology
membership, and include a verified expansion in executable packaging when the
target runtime requires one.

### Context Resolution

Default context is `Patient`. A fixture with multiple Patients must provide an
explicit subject; the test runner fails rather than selecting by entry order.
Put the evaluation date, measurement period, and named parameters in
`input/evaluation-context.json` or `input/parameters.json`.

## Reporting

Warnings are printed to stderr; errors cause non-zero exit.
Expression-level output is written to stdout as JSON.
