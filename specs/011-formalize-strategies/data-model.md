# Data Model: L2→L3 Formalization Strategies

**Feature**: 011-formalize-strategies | **Date**: 2026-04-17

## Entity 1: Strategy Registry

A mapping from L2 `artifact_type` to the strategy handler that produces FHIR resources.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `artifact_type` | string | One of: `evidence-summary`, `decision-table`, `care-pathway`, `terminology`, `measure`, `assessment`, `policy` | L2 type key from hybrid catalog |
| `handler` | callable | Signature: `(l2_artifact: dict, topic_meta: dict) -> list[dict]` | Builder function returning FHIR resource dicts |
| `primary_resource` | string | Valid FHIR R4 resource type | Main output resource (e.g., `PlanDefinition`) |
| `supporting_resources` | list[string] | Valid FHIR R4 resource types | Additional outputs (e.g., `Library`, `ActivityDefinition`) |
| `tracking_event` | string | Always `computable_converged` | Event appended on success |

**Uniqueness**: `artifact_type` is the primary key. Each type maps to exactly one strategy.

**Fallback**: Unknown types map to the generic `pathway-package` handler with a warning.

## Entity 2: FHIR Resource Output

Individual FHIR JSON files written to `topics/<topic>/computable/`.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `resourceType` | string | Valid FHIR R4 type | E.g., `Evidence`, `PlanDefinition`, `ValueSet` |
| `id` | string | kebab-case, unique within topic | Resource identifier, derived from L2 artifact name |
| `url` | string | Pattern: `http://example.org/fhir/<ResourceType>/<id>` | Canonical URL |
| `version` | string | SemVer | Starts at `1.0.0` |
| `status` | string | Always `draft` on initial generation | FHIR publication status |
| `name` | string | PascalCase | Machine-friendly name |
| `title` | string | Human-readable | Derived from L2 title |
| `date` | string | ISO 8601 date | Generation date |

**File naming**: `<ResourceType>-<id>.json` (e.g., `PlanDefinition-sepsis-bundle.json`)

**CQL files**: `<LibraryName>.cql` (PascalCase, e.g., `SepsisBundleLogic.cql`)

**Identity rule**: The `id` is derived from the topic slug + artifact name. The `url` follows the pattern `http://example.org/fhir/<ResourceType>/<id>` (placeholder base URL; real URLs are set during packaging).

## Entity 3: CQL Library

CQL source files generated alongside FHIR Library resources.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `library_name` | string | PascalCase, matches Library.name | CQL library identifier |
| `version` | string | SemVer, matches Library.version | Library version |
| `using` | string | Always `FHIR version '4.0.1'` | FHIR model declaration |
| `includes` | list[string] | At minimum `FHIRHelpers` | Required include libraries |
| `context` | string | `Patient` | CQL evaluation context |
| `defines` | list[CQLDefine] | At least one per required expression | Named expressions |

**CQL Define**:
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Initial Case (e.g., `Numerator Population`) |
| `return_type` | string | CQL type (Boolean, List, etc.) |
| `expression` | string | CQL expression or `// TODO: <reason>` stub |

**Compilation target**: CQL 1.5. Generated CQL must be syntactically valid for CQL-to-ELM translation. Semantic validation (terminology resolution) is deferred to verify mode.

## Entity 4: Tracking Entry (computable)

Entry appended to `topic_entry["computable"]` in tracking.yaml when `rh-skills formalize` succeeds.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | string | kebab-case, unique in topic | Artifact identifier |
| `files` | list[string] | Relative paths to generated FHIR JSON + CQL | All output files |
| `created_at` | string | ISO 8601 timestamp | Generation timestamp |
| `checksums` | dict[string, string] | SHA-256 per file | Integrity verification |
| `converged_from` | list[string] | L2 artifact names | Provenance chain |
| `strategy` | string | L2 artifact_type used | Which strategy produced this |

**Tracking event**: `computable_converged` with description listing artifact name and strategy.

**Difference from 006**: 006 stored a single `file` and `checksum`; 011 stores `files` (list) and `checksums` (dict) because one formalization produces multiple FHIR resources.

## Entity 5: FHIR Package

Output of `rh-skills package <topic>` in `topics/<topic>/package/`.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `package.json` | file | NPM-compatible | Package manifest |
| `ImplementationGuide-<id>.json` | file | FHIR IG resource | Package IG resource |
| `<ResourceType>-<id>.json` | files | Copied from computable/ | All FHIR resources |
| `<LibraryName>.cql` | files | Copied from computable/ | All CQL sources |

**package.json fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | `@reason/<topic-slug>` |
| `version` | string | SemVer (from topic metadata or `1.0.0`) |
| `fhirVersions` | list[string] | `["4.0.1"]` |
| `dependencies` | dict | At minimum: `hl7.fhir.us.core`, `hl7.fhir.uv.crmi` |
| `type` | string | `fhir.ig` |

**Tracking event**: `package_created` with description listing package name and resource count.

## Entity 6: Formalize Plan (updated)

The existing formalize-plan.md entity from 006 is extended to include strategy-specific information.

| Field | Type | Change from 006 | Description |
|-------|------|-----------------|-------------|
| `artifacts[].strategy` | string | NEW | The formalization strategy name (matches `artifact_type`) |
| `artifacts[].l3_targets` | list[string] | NEW | Concrete FHIR resource types this artifact will produce |
| `artifacts[].artifact_type` | string | CHANGED from fixed `pathway-package` | Now reflects actual L2 type |

**State transitions** (unchanged from 006):
- `pending-review` → `approved` | `needs-revision` | `rejected`
- Only `approved` artifacts proceed to implement
- Exactly one artifact may be `implementation_target: true` per plan

## Relationships

```
Strategy Registry (1) ──dispatches──> (N) FHIR Resource Builders
L2 Artifact (1) ──formalize──> (1..N) FHIR Resource Output
L2 Artifact (1) ──formalize──> (0..1) CQL Library
FHIR Resource Output (N) ──package──> (1) FHIR Package
Formalize Plan (1) ──contains──> (1..N) Plan Artifact Entries
Plan Artifact Entry (1) ──selects──> (1) Strategy
Tracking Entry (1) ──references──> (1..N) FHIR Resource Output files
```
