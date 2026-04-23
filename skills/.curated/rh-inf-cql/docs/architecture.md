# Architecture

This skill is designed to support a CQL-focused AI agent with strong grounding
in standards, runtime behavior, and reproducible tests.

## Layers

### 1. Standards Context

Material in `reference.md` and (optionally) `context/standards/` provides the
authoritative background for:
- language semantics (CQL spec, ELM)
- FHIR usage (FHIR Clinical Reasoning, Using CQL with FHIR)
- packaging and lifecycle (CRMI, Quality Measure IG)

### 2. Local Policy

Material under `docs/` captures project-specific expectations not fully
determined by the standards:
- naming and versioning (`authoring-guidelines.md`)
- runtime constraints (`runtime-assumptions.md`)
- terminology policy (`terminology-policy.md`)
- review rules (`review-checklist.md`)
- test scenario design (`testing-strategy.md`)

### 3. Agent Behavior

`SKILL.md` and `prompts/` define how the agent should:
- gather context before making changes
- analyze a problem using the standard operating sequence
- propose changes (minimal, explained)
- generate test scenarios and fixture skeletons

### 4. Execution and Validation

`tests/cql/` and `src/manifests/` define the practical evaluation loop:
- translate CQL → `rh-skills cql translate`
- run the CLI evaluator → `rh-skills cql test`
- compare outputs → `expression-results.json`
- report failures by category
- preserve regressions in `tests/cql/regression/`

## Design Intent

The skill separates authoring knowledge from runtime knowledge because many CQL
issues arise from mismatches between the two. ELM and test fixtures are treated
as first-class artifacts, not side effects.

## Integration with rh-skills Workflow

```text
any CQL input  →  rh-inf-cql (author mode)    →  .cql source + ELM JSON
               →  rh-inf-cql (review mode)    →  review report
               →  rh-inf-cql (test-plan mode) →  fixtures
```

The `rh-inf-cql` skill owns `.cql` source files and fixture cases. FHIR JSON
packaging (Library wrapper, Measure, PlanDefinition) is outside its scope.
