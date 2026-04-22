# Engine Notes

Behavior specific to the `rh` CQL evaluator.

## Key Differences from Reference Java Evaluator

### FHIRHelpers-Agnostic

The `rh` evaluator does **not** inject FHIRHelpers automatically.
Unlike the reference Java translator, it does not wrap FHIR coded values
with `FHIRHelpers.ToConcept()` calls during compilation.

**Impact**: Expressions that rely on implicit FHIR → CQL type coercion will
evaluate to `null` or error when FHIRHelpers is not explicitly included.

**Required mitigation**: Every CQL library that uses FHIR coded, quantity, or
date types should include:

```cql
include FHIRHelpers version '4.0.1' called FHIRHelpers
```

### Terminology Resolution

The evaluator resolves terminology offline by default. Value set membership
checks require either:
- pre-expanded value set resources bundled in the fixture
- an online terminology service configured via CLI options

### Context Resolution

Default context is `Patient`. Multi-patient evaluation is not currently supported
via the CLI test workflow.

## Reporting

Warnings are printed to stderr; errors cause non-zero exit.
Expression-level output is written to stdout as JSON.
