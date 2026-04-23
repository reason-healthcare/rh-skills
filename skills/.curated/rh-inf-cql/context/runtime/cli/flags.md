# CLI Flags

Flags supported by the `rh cql` subcommand for translation and evaluation.

## Compilation / Translation

```
rh cql compile <file.cql>
  -o, --output <path>     Write ELM JSON to the specified path (defaults to stdout)
  --debug                 Enable debug mode (annotations, locators, result types)
  --strict                Enable strict mode (disable implicit conversions)
```

## Evaluation

```
rh cql eval <file.cql> <name>
  --data <bundle.json>    FHIR Bundle to use as patient data
  --lib-path <dir>        Additional directory to search for included CQL libraries (repeatable)
  --trace                 Output a step-by-step evaluation trace
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
