# hi-status — Example Plan

Not applicable. `hi-status` is a read-only housekeeping skill that produces
no plan artifact. It reads `tracking.yaml` and reports lifecycle state.

## When to use hi-status

Use `hi-status` at any point during a research session:

- **Beginning of a session** — run `progress` to orient the team
- **After completing a stage** — run `next-steps` to get the recommended action
- **Before re-ingesting sources** — run `check-changes` to detect drift

## Sample invocations

```sh
# Overview of where a topic stands
hi-status progress juvenile-diabetes-onset

# What should we do next?
hi-status next-steps juvenile-diabetes-onset

# Have any source files changed since ingest?
hi-status check-changes juvenile-diabetes-onset
```
