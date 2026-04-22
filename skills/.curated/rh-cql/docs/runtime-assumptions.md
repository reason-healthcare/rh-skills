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
- Authors must `include FHIRHelpers` explicitly for explicit conversions
- Unexpected `null` results for coded values often indicate a missing
  FHIRHelpers include or an unsupported coercion path

## Why This Matters

Many apparent CQL logic failures are caused by:
- model mismatches (FHIR version, profile choice)
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
