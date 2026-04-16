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
| `rh-inf-verify` | Run consolidated verification across lifecycle stages |
| `rh-inf-status` | Surface deterministic status and next-step guidance |

## How they relate to the CLI

In CLI-first mode, you can call `rh-skills` commands directly and use these
skills as optional guidance. In agent-native mode, the skills are the primary
interface and call the CLI on your behalf.

See also:

- [Usage Modes](USAGE_MODES.md)
- [Getting Started](GETTING_STARTED.md)
- [Skill Distribution](SKILL_DISTRIBUTION.md)
