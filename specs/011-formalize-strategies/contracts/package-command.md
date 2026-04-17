# Contract: `rh-skills package` Command

**Feature**: 011-formalize-strategies | **FR**: FR-011

## Command Signature

```
rh-skills package <topic> [--dry-run] [--output-dir PATH]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `topic` | Yes | Topic name (kebab-case) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dry-run` | flag | false | Print the package manifest without writing files |
| `--output-dir` | path | `topics/<topic>/package/` | Override output directory |

## Preconditions

1. Topic exists in tracking.yaml
2. At least one entry exists in `topic_entry["computable"]`
3. All computable entries have corresponding files on disk

## Behavior

1. Load tracking.yaml and locate the topic
2. Collect all files from `topics/<topic>/computable/` (FHIR JSON + CQL)
3. Generate `package.json`:
   - `name`: `@reason/<topic-slug>`
   - `version`: from topic metadata or `1.0.0`
   - `fhirVersions`: `["4.0.1"]`
   - `type`: `fhir.ig`
   - `dependencies`: Infer from resources present (always include `hl7.fhir.us.core`, `hl7.fhir.uv.crmi`; add `hl7.fhir.uv.cql` if CQL present; add domain-specific IGs based on resource profiles)
4. Generate `ImplementationGuide-<topic-slug>.json`:
   - List all resources in `definition.resource[]`
   - Set `fhirVersion: ["4.0.1"]`
   - Set `packageId` matching package.json name
5. Copy all FHIR JSON + CQL files from `computable/` to `package/`
6. Write `package.json` and `ImplementationGuide` to `package/`
7. Update tracking.yaml:
   - Append `package_created` event via `append_topic_event()`
8. Save tracking.yaml

## Output (stdout)

```
Packaged '<topic>' as FHIR package:
  package: @reason/sepsis-bundle v1.0.0
  resources: 12 FHIR JSON + 3 CQL
  dependencies: hl7.fhir.us.core@6.1.0, hl7.fhir.uv.crmi@1.0.0, hl7.fhir.uv.cql@2.0.0

Wrote package to topics/<topic>/package/
Event: package_created
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Package created successfully |
| 2 | Failure — precondition not met (no computable resources, topic not found) |

## Tracking Event

```yaml
- timestamp: "2026-04-17T20:30:00Z"
  type: package_created
  description: "Packaged 'sepsis-bundle' → @reason/sepsis-bundle v1.0.0 (12 resources)"
```

## File System Writes

All writes go to `topics/<topic>/package/` (or `--output-dir`):
- `package.json` — NPM-compatible FHIR package manifest
- `ImplementationGuide-<topic-slug>.json` — FHIR IG resource
- `<ResourceType>-<id>.json` — Copied FHIR resources
- `<LibraryName>.cql` — Copied CQL sources

## Package Directory Layout

```
topics/<topic>/package/
├── package.json
├── ImplementationGuide-<topic-slug>.json
├── PlanDefinition-<id>.json
├── Library-<id>.json
├── ValueSet-<id>.json
├── Measure-<id>.json
├── ...
├── <LibraryName>.cql
└── ...
```
