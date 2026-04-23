# Runtime Assumptions

Runtime details are part of the behavior of the logic. Always capture them
explicitly before reasoning about CQL correctness or test failures.

## Environment to Capture

- evaluator: `rh` CLI (configured via `RH_CLI_PATH`, `.rh-skills.toml [cql] rh_cli_path`, or `rh` on PATH)
- translator: built into the `rh` binary
- model info: FHIR 4.0.1 (default)
- terminology service: local expansion or none (offline by default)
- CLI flags: see `context/runtime/cli/flags.md`
- timezone / date precision: explicit in CQL; no silent defaults assumed

## FHIRHelpers-Agnostic Behavior

The `rh` CQL evaluator does **not** inject `FHIRHelpers.ToConcept` wrapper
calls automatically. This means:

- FHIR → CQL type coercions are not automatic
- Authors must `include fhir.cqf.common.FHIRHelpers` explicitly for explicit conversions
- Unexpected `null` results for coded values often indicate a missing
  FHIRHelpers include or an unsupported coercion path

## FHIR dateTime Strings and Date Comparison

**This is the most common source of silent false results.**

FHIR stores dates as strings (e.g., `"2024-02-01T00:00:00Z"`). The `rh` engine
does NOT automatically coerce these strings to CQL Date or DateTime.

| Pattern | Result | Notes |
|---------|--------|-------|
| `M.authoredOn during Interval<DateTime>` | silently `false` | string ≠ DateTime; no error |
| `date from M.authoredOn` | runtime error | only works on native CQL DateTime, not strings |
| `ToDate(M.authoredOn)` | CQL `Date` ✓ | correct coercion from FHIR string |

**Correct pattern for date-range membership:**

```cql
parameter "Measurement Period" Interval<Date>
  default Interval[@2024-01-01, @2024-12-31]

define "In Period":
  exists (
    [MedicationRequest] M
      where ToDate(M.authoredOn) is not null
        and "Measurement Period" contains ToDate(M.authoredOn)
  )
```

Rules:
- Always use `ToDate()` to coerce FHIR `date`/`dateTime` strings before interval comparison
- Use `Interval<Date>` parameters, not `Interval<DateTime>`, for date-only comparisons
- Include a `is not null` guard after `ToDate()` — a null authoredOn would otherwise match an open interval boundary

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

When a test fails unexpectedly, check the runtime environment before changing
the CQL.

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
