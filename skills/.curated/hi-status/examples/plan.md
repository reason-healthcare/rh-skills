# hi-status — Example Plan

Not applicable. `hi-status` is a read-only skill that produces no plan artifact.
It reads `tracking.yaml` and reports lifecycle state.

## When to use hi-status

Use `hi-status` at any point during a research session:

- **Start of a session** — run `hi status` to see the full portfolio and orient yourself
- **Focused topic check** — run `hi status show <topic>` for artifact counts and last event
- **Before extracting or formalizing** — run `hi status check-changes <topic>` to detect source drift

## Sample invocations

```sh
# Full portfolio — all topics with stage and primary next step
hi status

# Single-topic detail — stage, artifact counts, last event
hi status show juvenile-diabetes-onset

# Drift detection — re-checksum all registered sources
hi status check-changes juvenile-diabetes-onset

# Power-user: detailed pipeline bar with completeness %
hi status progress juvenile-diabetes-onset

# Power-user: ranked next-step recommendations
hi status next-steps juvenile-diabetes-onset
```

