# Contract: Updated Path Convention

**Feature**: 010-l2-artifact-catalog  
**Date**: 2026-04-17

## Path Change

| Context | Old Path | New Path |
|---------|----------|----------|
| L2 artifact file | `topics/<topic>/structured/<name>.yaml` | `topics/<topic>/structured/<name>/<name>.yaml` |
| Tracking entry `file` | `topics/<topic>/structured/<name>.yaml` | `topics/<topic>/structured/<name>/<name>.yaml` |
| Validate resolution | `<topic_dir>/structured/<name>.yaml` | `<topic_dir>/structured/<name>/<name>.yaml` |
| Render views | *(N/A — new)* | `topics/<topic>/structured/<name>/views/` |

## Affected Commands

| Command | Change |
|---------|--------|
| `rh-skills promote derive` | Write L2 to subdirectory; update tracking `file` field |
| `rh-skills validate <topic> l2 <artifact>` | Resolve at `structured/<name>/<name>.yaml` |
| `rh-skills promote combine` | Resolve L2 inputs from subdirectory path |
| `rh-skills render` | New command; reads from subdirectory path |
| `rh-skills status` | Reads tracking.yaml `file` entries (path format change) |

## Affected Schemas/Docs

| File | Change |
|------|--------|
| `tracking-schema.yaml` | Update `structured[].file` comment to show new path |
| `reference.md` | Update L2 Artifact Shape path references |
| `SKILL.md` | Update derive output path references |
