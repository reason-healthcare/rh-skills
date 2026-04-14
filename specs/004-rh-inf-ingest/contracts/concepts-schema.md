# Contract: `concepts.yaml`

**Phase 1 Design Artifact** | **Branch**: `004-rh-inf-ingest`

---

## File

`topics/<topic>/process/concepts.yaml`

## Schema

```yaml
topic: <topic-name>
generated: <ISO-8601 timestamp>
concepts:
  - name: <canonical concept name>
    type: <condition | medication | procedure | measure | code | term>
    sources:
      - <source-name>
```

## Rules

- `topic` is required and must match the topic directory
- `generated` is required and records last regeneration/update time
- `concepts[]` may be empty but must exist
- `name` is required and used as the canonical de-duplication key
- `type` is required
- `sources[]` is required and contains source names, not file paths

## De-duplication

- De-dupe is case-insensitive on `name`
- When the same concept appears in multiple sources, merge them into one concept entry and append source names to `sources[]`
- Duplicate source names within a single concept entry are not allowed

## Downstream Use

- `rh-inf-extract` uses this file as a topic vocabulary for proposing structured artifact candidates
- The file is read-only to downstream skills unless a future spec explicitly transfers ownership
