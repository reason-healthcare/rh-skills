# Engine Notes

Behavior specific to the `rh` CQL evaluator.

## Key Differences from Reference Java Evaluator

### Pinned FHIRHelpers dependency

The `rh` evaluator does not inject FHIRHelpers automatically. Portable CQL
declares a versioned include:

`include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers`

Prefer `fhir.cqf.common@4.0.1`; do not create local `FHIRHelpers` or
`FHIRCommon` shadow libraries. Resolve the namespaced include directly from the
verified package or package cache; do not copy helper/common CQL into
first-party computable content. Ignore ELM supplied by the package and run
`rh-skills cql translate` with the pinned project translator. Record package
and source hashes, translator identity/options/model, and generated ELM hash.
The primary FHIR Library must declare the helper in `relatedArtifact`.

`fhir.cqf.common@4.0.1` does not publish the fluent `references` functions. If
logic needs them, pin a package/version that does publish them and keep the
external include package-qualified; do not patch a local `FHIRCommon`.

For choice elements, use FHIR logical types (for example,
`(A.value as FHIR.boolean).value`). Traverse CodeableConcept `coding` and compare
each Coding to a declared Code (for example, `S ~ "Active"`) so system and code
are matched through typed CQL terminology semantics. Do not reproduce that
identity with separate `.system.value` and `.code.value` string predicates.
Validate portable CQL with a reference translator too.

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
