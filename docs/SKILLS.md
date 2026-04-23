# RH Skills

RH Skills includes a set of AI-facing workflow skills that sit on top of the
deterministic `rh-skills` CLI.

## Design principle

The CLI owns filesystem writes, tracking updates, validation, and repeatable
transformations. The skills provide reasoning, planning, and review flows around
those deterministic operations.

## Current informatics skills

| Skill | Purpose |
|------|---------|
| `rh-inf-discovery` | Discover and prioritize clinical sources for a topic |
| `rh-inf-ingest` | Bring source material into the repo and prepare L1 artifacts |
| `rh-inf-extract` | Derive structured L2 artifacts from reviewed source material |
| `rh-inf-formalize` | Convert approved structured artifacts into computable L3 outputs |
| `rh-inf-cql` | Author, review, validate, and test CQL libraries for computable measures and decision logic |
| `rh-inf-verify` | Run consolidated verification across lifecycle stages |
| `rh-inf-status` | Surface deterministic status and next-step guidance |

## When to use `rh-inf-cql`

`rh-inf-cql` is the CQL authoring and quality skill. It is invoked:

- **During formalize implement** — automatically, when the formalize strategy produces CQL (`decision-table`, `measure`, `policy`). `rh-inf-formalize` generates the FHIR JSON wrappers + CQL scaffold and then hands off directly to `rh-inf-cql` to author, validate, and compile the full CQL library. CQL authoring is part of the formalize implement flow for these strategies, not a separate step.
- **Standalone CQL work** — Authoring or reviewing a CQL library independently of the formalize flow.
- **CQL review or debugging** — Reviewing existing `.cql` files for correctness, safety, or performance.
- **Test fixture authoring** — Designing fixture cases (`tests/cql/<Library>/`) for expression-level coverage.

`rh-inf-cql` owns `.cql` source files under `topics/<topic>/computable/`. It does **not** own the FHIR JSON wrappers (Library, Measure JSON) — those are `rh-inf-formalize`'s responsibility.

## How they relate to the CLI

In CLI-first mode, you can call `rh-skills` commands directly and use these
skills as optional guidance. In agent-native mode, the skills are the primary
interface and call the CLI on your behalf.

See also:

- [Usage Modes](USAGE_MODES.md)
- [Getting Started](GETTING_STARTED.md)
- [Skill Distribution](SKILL_DISTRIBUTION.md)
