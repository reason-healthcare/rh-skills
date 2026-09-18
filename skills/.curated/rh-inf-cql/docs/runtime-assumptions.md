# Runtime Assumptions

Runtime details are part of the behavior of the logic. Always capture them
explicitly before reasoning about CQL correctness or test failures.

## Environment to Capture

- evaluator: `rh` CLI — validate, compile, and eval are available
- translator: built into the `rh` binary
- model info: FHIR 4.0.1 (default)
- terminology service: no implicit runtime lookup; pin and package required expansions
- CLI flags: see `context/runtime/cli/flags.md`
- timezone / date precision: pass an explicit evaluation date when logic uses the clock; document date precision

## FHIRHelpers and Portable FHIR Types

The runtime does not inject helper calls. When converting FHIR primitive values,
date/time values, or choice types, include the versioned helper explicitly:

```cql
include FHIRHelpers version '4.0.1' called FHIRHelpers
```

This include must resolve to a pinned local dependency during validation and
evaluation. Use the supported `rh-skills cql import-library` workflow to import
the CQL, ELM, and FHIR Library together. Do not assume an engine will find a
helper through a network lookup or auto-inject conversions.

For FHIR choice elements, use the FHIR logical type so ELM remains portable;
for example, `(A.value as FHIR.boolean).value` for a Boolean
`QuestionnaireResponse.answer.value[x]`. For a CodeableConcept, traverse
`coding` and compare both `system.value` and `code.value`.

## FHIR dateTime Strings and Date Comparison

**This is the most common source of silent false results.**

FHIR date/dateTime values use FHIR model types. Convert them explicitly with
the pinned FHIRHelpers library when comparing with CQL system Date or DateTime
values.

| Pattern | Result | Notes |
|---------|--------|-------|
| `E.period.start` compared directly with a CQL DateTime | avoid | FHIR primitive and CQL system values are different model types |
| `FHIRHelpers.ToDateTime(E.period.start)` | CQL `DateTime` | explicit conversion through the declared helper |
| `(A.value as FHIR.boolean).value` | CQL `Boolean` | use the logical FHIR choice type for portable ELM |

**Correct pattern for date-range membership:**

```cql
parameter "Measurement Period" Interval<DateTime>
  default Interval[@2024-01-01T00:00:00.0Z, @2024-12-31T23:59:59.0Z]

define "In Period":
  exists (
    [MedicationRequest] M
      where FHIRHelpers.ToDateTime(M.authoredOn) is not null
        and "Measurement Period" contains FHIRHelpers.ToDateTime(M.authoredOn)
  )
```

Rules:
- Convert FHIR date/time primitives with the pinned FHIRHelpers conversion matching the CQL interval type
- Use `Interval<Date>` for date-only comparisons and `Interval<DateTime>` for timestamp comparisons
- Keep a `is not null` guard before interval membership when missing dates should not match an open interval boundary

## ValueSet Membership

Use `code in "ValueSetName"` for membership testing. The engine resolves
ValueSets by name without requiring expanded ValueSet resources in the bundle.

```cql
// ✓ correct
define "Has ASCVD":
  exists ([Condition] C where C.code in "ASCVD Conditions")

// ✗ wrong — manual expansion matching; do not do this
define "Has ASCVD":
  exists (
    [Condition] C
      where exists (
        "ASCVD ValueSet Resources" V
          where exists (
            V.expansion.contains E
              where E.system = C.code.coding[0].system
                and E.code = C.code.coding[0].code
          )
      )
  )
```

Test bundles do NOT need to include ValueSet resources. The engine uses the
declared `valueset` URL/name from the CQL library header.

## Why This Matters

Many apparent CQL logic failures are caused by:
- model mismatches (FHIR version, profile choice)
- FHIR string → CQL type coercion (see FHIR dateTime section above)
- terminology expansion differences
- fixture shape issues (bundle structure doesn't match model expectations)
- translator options (ELM generation flags)
- engine-specific handling of edge cases (especially interval and null semantics)

When a test fails unexpectedly, first check the runtime environment, local
include path, library version, evaluator clock, subject, and complete parameter
context before changing the CQL.

## Missing Binary

If `rh` is not found, the skill halts and emits:

```
rh CLI not found. Install with: cargo install rh
```

Alternatively, set `RH_CLI_PATH` or configure `.rh-skills.toml`:

```toml
[cql]
rh_cli_path = "/path/to/rh"
```
