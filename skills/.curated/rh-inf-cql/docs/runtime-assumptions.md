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

## Patient Context Scoping

With `context Patient`, retrieves are scoped to the selected patient when the
pinned FHIR ModelInfo defines the Patient-to-resource context relationship and
the evaluator honors that relationship. Do not encode the intended scope again as
`resource.subject.reference = 'Patient/' + Patient.id`; that hides a runtime
context-scoping failure and makes otherwise portable logic depend on a
workaround. Keep independent constraints for the selected encounter, dates,
status, and provenance. The official CQL Author's Guide describes the
[Patient context](https://cql.hl7.org/02-authorsguide.html#context) and
[retrieve scoping](https://cql.hl7.org/02-authorsguide.html#retrieve-context).

When validating an engine or investigating suspected leakage, evaluate with a
Bundle containing a second patient's Encounter/clinical resources and an
explicit `--subject`. Results for the selected patient must be unchanged by
those foreign resources. If they change, report and block the runtime path; do
not add subject-reference predicates to the authored library.

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
`QuestionnaireResponse.answer.value[x]`. For a CodeableConcept or Coding,
declare the relevant CodeSystem/Code or ValueSet and use typed CQL terminology
operators on the intended model path. Do not split a coded comparison into
independent system/code string tests. This rule does not prohibit ordinary
FHIR primitive status checks such as `Observation.status = 'final'`; see the
[CQL Style Guide](cql-style-guide.md).

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

Use `code in "ValueSetName"` for membership testing. The CQL declaration names
the terminology dependency; it does not supply the membership expansion. For
the `rh` runtime, provide the matching complete, versioned expansion through
the `--terminology` sidecar or the packaged knowledge Bundle. The runtime
resolves the declared canonical and version from that input and fails closed
when the expansion is absent, incomplete, or version-mismatched. Treat this as
a terminology availability/contract error, not clinical `null` evidence.

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

The patient-data Bundle and terminology input are separate: a fixture may keep
its Bundle focused on clinical data while its `terminology.json` sidecar
contains the required expanded ValueSets. Packaged evaluation must carry the
same verified expansion in the knowledge Bundle.

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
