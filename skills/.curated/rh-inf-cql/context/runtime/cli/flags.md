# CLI Flags

Flags supported by the `rh cql` subcommand for translation and evaluation.

## Compilation / Translation

```
rh cql compile <file.cql>
  --elm-output <path>     Write ELM JSON to the specified path
  --model <FHIR|QI-Core>  Override the default model (default: FHIR)
  --fhir-version <ver>    FHIR version string (default: 4.0.1)
```

## Evaluation

```
rh cql eval <file.cql>
  --expr <name>           Evaluate a single named expression (can repeat)
  --data <bundle.json>    FHIR Bundle to use as patient data
  --context <Patient>     Evaluation context (default: Patient)
```

## rh-skills Wrappers

The `rh-skills cql` commands wrap the above with project-aware path resolution:

```
rh-skills cql validate <topic> <LibraryName>
rh-skills cql translate <topic> <LibraryName>
rh-skills cql test <topic> <LibraryName>
```

See `context/runtime/cli/usage.md` for full examples.

## Hints

If the `rh` binary is not found, the skill emits:
```
rh CLI not found. Install with: cargo install rh
```

Configure the path via `RH_CLI_PATH` or `.rh-skills.toml [cql] rh_cli_path`.
