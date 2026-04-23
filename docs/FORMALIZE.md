# Formalize Workflow Report

## Overview

The formalize workflow converts **L2 structured artifacts** into **L3 FHIR R4 computable resources** through a type-aware 4-step lifecycle: **plan → approve → implement → verify**, with an optional **package** step.

---

## CLI Commands

| Command | Purpose | Writes To |
|---------|---------|-----------|
| `rh-skills promote formalize-plan <topic>` | Generate review packet with per-type strategies | `process/plans/formalize-plan.md` |
| `rh-skills formalize <topic> <artifact>` | Generate FHIR JSON + CQL from approved L2 artifact | `computable/*.json`, `*.cql` |
| `rh-skills package <topic>` | Bundle into FHIR NPM package | `package/` |
| `rh-skills validate <topic> l3 <artifact>` | Verify type-specific structural completeness | (read-only) |

---

## Strategy Map (7 L2 Types)

| L2 Type | Primary FHIR Resource | Supporting | Required Sections |
|---------|----------------------|-----------|-------------------|
| evidence-summary | Evidence | EvidenceVariable, Citation | evidence |
| decision-table | PlanDefinition (eca-rule) | Library (CQL) | actions, libraries |
| care-pathway | PlanDefinition (clinical-protocol) | ActivityDefinition | pathways, actions |
| terminology | ValueSet | ConceptMap | value_sets |
| measure | Measure | Library (CQL) | measures, libraries |
| assessment | Questionnaire | — | assessments |
| policy | PlanDefinition (eca-rule) | Questionnaire (DTR), Library | actions, libraries |

---

## Workflow

```
1. PLAN: rh-skills promote formalize-plan <topic>
   ├─ Reads approved L2 artifacts from extract-plan.yaml
   ├─ Maps each artifact_type → strategy via _L3_TARGET_MAP
   ├─ Detects overlapping FHIR resource types (multi-type topics)
   ├─ Writes formalize-plan.md with per-artifact strategy proposals
   └─ Event: formalize_planned

2. APPROVE: Reviewer sets status: approved + reviewer_decision: approved

3. IMPLEMENT: rh-skills formalize <topic> <artifact> (per artifact)
   ├─ Looks up strategy in STRATEGY_REGISTRY
   ├─ Builds type-specific LLM system prompt
   ├─ Invokes LLM → raw FHIR JSON
   ├─ normalize_resource() → fix ids, urls, dates
   ├─ validate_resource() → per-type required fields
   ├─ Writes ResourceType-id.json + .cql scaffold to computable/
   ├─ If strategy includes CQL (decision-table, measure, policy):
   │    └─ rh-inf-cql authors full CQL from scaffold → validate + translate
   └─ Event: computable_converged

4. VERIFY: rh-inf-formalize verify (invokes rh-skills validate)
   ├─ Plan consistency: strategy match, input_artifacts match
   ├─ L3 target coverage: every l3_targets[] has a file
   ├─ Per-type structural checks (see table above)
   ├─ MCP-UNREACHABLE placeholder detection
   └─ Non-destructive, safe to rerun

5. PACKAGE: rh-skills package <topic>
   ├─ Collects all *.json + *.cql from computable/
   ├─ Generates package.json (FHIR NPM, @reason/<topic>)
   ├─ Generates ImplementationGuide-<topic>.json
   └─ Event: package_created
```

---

## Key Files

| File | Role |
|------|------|
| `src/rh_skills/commands/promote.py` | Plan generation (`_L3_TARGET_MAP`, `_build_formalize_artifacts`, overlap detection) |
| `src/rh_skills/commands/formalize.py` | `rh-skills formalize` command (LLM invocation, strategy registry) |
| `src/rh_skills/commands/package.py` | `rh-skills package` command |
| `src/rh_skills/fhir/normalize.py` | Post-LLM normalization (ids, urls, dates) |
| `src/rh_skills/fhir/validate.py` | Per-resource-type structural validation (9 types) |
| `src/rh_skills/fhir/packaging.py` | FHIR NPM bundle generation |
| `src/rh_skills/commands/validate.py` | `_validate_fhir_json_files()` for verify mode |
| `skills/.curated/rh-inf-formalize/SKILL.md` | Agent skill instructions (plan/implement/verify modes) |
| `skills/.curated/rh-inf-formalize/reference.md` | Conversion rules, schemas, verify rules |

---

## CQL Libraries

Two formalize strategies produce a `.cql` source file alongside the FHIR JSON:

| Strategy | CQL Library | Supporting FHIR Resource |
|----------|-------------|--------------------------|
| `decision-table` | Library (CQL) | PlanDefinition (eca-rule) |
| `measure` | Library (CQL) | Measure |

`rh-skills formalize` writes a `.cql` scaffold to `topics/<topic>/computable/<Library>.cql`. The **`rh-inf-cql` skill** is responsible for authoring, reviewing, and validating the CQL content after the scaffold is generated. The FHIR JSON wrapper (Library.json, Measure.json) remains `rh-inf-formalize`'s responsibility.

**CQL workflow after formalize:**

```
rh-skills cql validate <topic> <library>   # validate syntax + semantics
rh-skills cql translate <topic> <library>  # compile to ELM JSON
rh-skills cql test <topic> <library>       # list fixture cases (eval pending)
```

Fixture cases live at `tests/cql/<Library>/case-<N>-<name>/` with `input/bundle.json` and `expected/expression-results.json`.

See [SKILLS.md](SKILLS.md) for when to invoke `rh-inf-cql` and [COMMANDS.md](COMMANDS.md) for the full `rh-skills cql` command reference.

---

## Multi-Type Convergence

When a topic has multiple L2 types:
- Each type gets its **own artifact entry** in the plan with its specific strategy
- **Overlap detection**: If two strategies produce the same FHIR resource (e.g., decision-table + care-pathway both → PlanDefinition), flagged with ⚠ for reviewer
- Default resolution: separate resources with different `type` values
- Cross-references via canonical URLs (e.g., PlanDefinition references ValueSet)
