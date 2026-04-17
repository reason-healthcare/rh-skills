# Quickstart: L2→L3 Formalization Strategies

**Feature**: 011-formalize-strategies

## New Commands

| Command | Purpose | Replaces |
|---------|---------|----------|
| `rh-skills formalize <topic> <artifact>` | Generate FHIR JSON + CQL from approved L2 artifact | `rh-skills promote combine` |
| `rh-skills package <topic>` | Bundle computable resources into FHIR NPM package | (new) |

## Typical Workflow

```bash
# 1. Plan (existing — now type-aware)
# Agent runs rh-inf-formalize plan <topic>
# → writes formalize-plan.md with type-specific strategies

# 2. Review + approve the plan
# Reviewer sets reviewer_decision: approved

# 3. Formalize each artifact
rh-skills formalize my-topic decision-rules
rh-skills formalize my-topic lab-value-sets
rh-skills formalize my-topic screening-tool

# 4. Verify (existing — now type-aware)
# Agent runs rh-inf-formalize verify <topic>
# → checks type-specific completeness per strategy

# 5. Package
rh-skills package my-topic
# → writes FHIR NPM package to topics/my-topic/package/
```

## Strategy Mapping (Quick Reference)

| L2 Type | → | Primary FHIR Resource | Tracking Event |
|---------|---|----------------------|----------------|
| evidence-summary | → | Evidence, EvidenceVariable, Citation | `computable_converged` |
| decision-table | → | PlanDefinition (eca-rule), Library | `computable_converged` |
| care-pathway | → | PlanDefinition (clinical-protocol), ActivityDefinition | `computable_converged` |
| terminology | → | ValueSet, ConceptMap | `computable_converged` |
| measure | → | Measure, Library | `computable_converged` |
| assessment | → | Questionnaire, QuestionnaireResponse | `computable_converged` |
| policy | → | PlanDefinition (eca-rule), Questionnaire (DTR) | `computable_converged` |

## Output Layout

```
topics/<topic>/
├── computable/                  # rh-skills formalize writes here
│   ├── PlanDefinition-<id>.json
│   ├── Library-<id>.json
│   ├── ValueSet-<id>.json
│   ├── <LibraryName>.cql
│   └── ...
└── package/                     # rh-skills package writes here
    ├── package.json
    ├── ImplementationGuide-<id>.json
    └── ... (all resources copied)
```

## Key Design Decisions

- **FHIR R4 (4.0.1) + CQL 1.5**: All output targets the US Core / QI-Core ecosystem
- **Individual files**: One FHIR JSON per resource (not monolithic YAML)
- **MCP failure**: Placeholder `TODO:MCP-UNREACHABLE` codes; verify catches them
- **Partial failure**: Keep written files, report failures, exit non-zero
- **Deprecation**: `promote combine` still works but shows deprecation warning

## Reference

- Business rules: [`docs/FORMALIZE_STRATEGIES.md`](../../docs/FORMALIZE_STRATEGIES.md)
- Spec: [`specs/011-formalize-strategies/spec.md`](spec.md)
- Data model: [`specs/011-formalize-strategies/data-model.md`](data-model.md)
- Contracts: [`specs/011-formalize-strategies/contracts/`](contracts/)
