# rh-inf-status — Example Plan

Not applicable. `rh-inf-status` is a read-only skill that produces no plan artifact.
It reads `tracking.yaml` and reports lifecycle state.

## When to use rh-inf-status

Use `rh-inf-status` at any point during a research session:

- **Start of a session** — run `rh-skills status` to see the full portfolio and orient yourself
- **Focused topic check** — run `rh-skills status show <topic>` for artifact counts and last event
- **Before extracting or formalizing** — run `rh-skills status check-changes <topic>` to detect source drift

## Sample invocations

```sh
# Full portfolio — all topics with stage and primary next step
rh-skills status

# Single-topic detail — stage, artifact counts, last event
rh-skills status show juvenile-diabetes-onset

# Drift detection — re-checksum all registered sources
rh-skills status check-changes juvenile-diabetes-onset

# Power-user: detailed pipeline bar with completeness %
rh-skills status progress juvenile-diabetes-onset

# Power-user: ranked next-step recommendations
rh-skills status next-steps juvenile-diabetes-onset
```

