# Contract: `rh-skills formalize` Command

**Feature**: 011-formalize-strategies | **FR**: FR-004, FR-010

## Command Signature

```
rh-skills formalize <topic> <artifact> [--dry-run] [--force]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `topic` | Yes | Topic name (kebab-case) |
| `artifact` | Yes | L2 artifact name to formalize |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dry-run` | flag | false | Print the strategy selection and expected outputs without writing files |
| `--force` | flag | false | Overwrite existing computable files for this artifact |

## Preconditions

1. Topic exists in tracking.yaml
2. Named artifact exists in `topic_entry["structured"]`
3. Artifact has `status: approved` (or passed validation)
4. A formalize plan exists and the artifact's plan entry has `reviewer_decision: approved`
5. Artifact's `artifact_type` is recognized (7 standard types or `custom` fallback)

## Behavior

1. Load tracking.yaml and locate the topic
2. Load the L2 artifact YAML from `topics/<topic>/structured/<artifact>.yaml`
3. Read `artifact_type` from the L2 artifact
4. Dispatch to the strategy registry: `REGISTRY.get(artifact_type, generic_fallback)`
5. If `artifact_type` is unknown, warn: `"Unknown artifact type '<type>'; falling back to generic pathway-package strategy"`
6. Execute the strategy handler: `resources = handler.build(l2_artifact, topic_metadata)`
   - Handler resolves terminology via MCP tools where applicable
   - On MCP failure: insert `TODO:MCP-UNREACHABLE` placeholder codes, emit warning
7. Write each resource to `topics/<topic>/computable/<ResourceType>-<id>.json`
8. Write CQL files (if any) to `topics/<topic>/computable/<LibraryName>.cql`
9. Update tracking.yaml:
   - Append entry to `topic_entry["computable"]` with `name`, `files`, `checksums`, `converged_from`, `strategy`
   - Append `computable_converged` event via `append_topic_event()`
10. Save tracking.yaml

## Output (stdout)

```
Formalized '<artifact>' using <strategy> strategy:
  ✓ PlanDefinition-<id>.json
  ✓ Library-<id>.json
  ✓ <LibraryName>.cql
  ⚠ ValueSet-<id>.json (2 codes with TODO:MCP-UNREACHABLE)

Wrote 4 files to topics/<topic>/computable/
Event: computable_converged
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All resources generated successfully |
| 1 | Partial failure — some resources written, some failed |
| 2 | Total failure — no resources written (precondition failure, no valid L2 artifact) |

## Partial Failure Behavior

If generation fails partway through:
- Successfully written files are kept
- Failed resources are reported in stderr
- Exit code 1
- No tracking event appended (verify will catch incomplete set)

## Tracking Event

```yaml
- timestamp: "2026-04-17T20:00:00Z"
  type: computable_converged
  description: "Formalized 'sepsis-decision-rules' using decision-table strategy → 3 resources"
```

## File System Writes

All writes go to `topics/<topic>/computable/`:
- `<ResourceType>-<id>.json` — FHIR R4 JSON resources
- `<LibraryName>.cql` — CQL source files

No writes outside this directory. No writes to `package/` (that's the package command's concern).
