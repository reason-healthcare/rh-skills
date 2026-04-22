# Translator Options

Options controlling ELM generation from the `rh cql compile` command.

## Recommended Options

| Option | Purpose | Recommended |
|--------|---------|-------------|
| `EnableAnnotations` | Adds source location annotations to ELM | Yes, for debugging |
| `EnableLocators` | Adds line/column locators to ELM nodes | Yes, for debugging |
| `DisableListDemotion` | Prevents automatic list demotion for singletons | Situational |
| `DisableListPromotion` | Prevents automatic singleton promotion to list | Situational |
| `EnableResultTypes` | Adds result type annotations to ELM | Optional |

## Default Behavior

By default, `rh cql compile` generates ELM with no extra options. For
production libraries, use `EnableAnnotations` and `EnableLocators` to
support debugging.

## Declaring Options in a Library

Translator options can be declared in the Library FHIR resource using the
`cqlOptions` extension defined in the Using CQL with FHIR IG. Document the
options used for each library in `src/manifests/libraries.yaml`.

## Notes

- The `rh` evaluator reads ELM directly if it exists alongside the `.cql` file.
- Always re-generate ELM after changing CQL source; stale ELM causes silent
  behavior differences.
