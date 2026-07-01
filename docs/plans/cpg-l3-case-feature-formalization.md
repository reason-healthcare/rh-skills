# CPG-Aligned L3 Case Feature Formalization

## Summary

Decision-table L3 formalization should keep L2 simple while representing case
features using the CPG pattern:

```text
data elements -> CQL data-element logic -> case feature definitions -> action inputs and rule conditions
```

Do not introduce an eCase report or Composition layer for now. Do not generate a
separate Library for every case feature. Keep all decision-table data-element,
case-feature, applicability, and rule expressions in the decision-table CQL
Library.

## L3 Artifacts

For each decision table, generate:

- One decision-table `Library` containing all CQL expressions.
- One `StructureDefinition` per L2 `conditions[]` case feature, profiled as a
  CPG case feature definition.
- One local case-feature `CodeSystem`.
- One case-feature `ValueSet` that includes the generated case-feature codes.
- Existing `PlanDefinition` and `ActivityDefinition` resources, with action
  conditions, inputs, and outputs linked to the generated logic and definitions.

## Case Feature Definitions

Each L2 `conditions[]` entry represents a case feature for now. Formalization
should generate a corresponding case-feature `StructureDefinition`.

Use CPG case-feature extensions where available:

- `caseFeatureType`: asserted, inferred, or combined.
- `caseFeatureOf`: the decision table, recommendation, strategy, or pathway that
  uses the feature.
- `assertionExpression`: CQL expression for directly asserted record data.
- `inferenceExpression`: CQL expression for derived/calculated feature logic.
- `featureExpression`: normalized expression consumed by decision logic.

The expression extensions should reference named expressions in the single
decision-table CQL Library.

## CQL Library

The decision-table Library should define data elements first, then resolved case
features, then polarity-aware rule/applicability helpers.

Example:

```cql
define "BonyErosion":
  exists([Observation: "Bony erosion value set"])

define "Osteitis":
  exists([Observation: "Osteitis value set"])

define "AdvancedSinusDiseaseFeaturePresent":
  "BonyErosion" or "Osteitis"

define "HasAdvancedSinusDiseaseFeaturePresent":
  "AdvancedSinusDiseaseFeaturePresent"
```

If an L2 data element lacks enough terminology to generate a real retrieve,
generate a named placeholder expression with a clear comment rather than
inventing retrieval logic.

## Case Feature CodeSystem and ValueSet

Generate a local `CodeSystem` with one code per case feature and a companion
`ValueSet` that includes those codes. Use stable codes derived from
`conditions[].id`.

The ValueSet supports discoverability and gives action input DataRequirements a
consistent coded surface when a feature-specific profile alone is not enough.

## PlanDefinition Conditions and Inputs

`rules[].when` should continue to formalize to
`PlanDefinition.action.condition.expression`, using `text/cql-identifier`
references to the decision-table Library.

For every action reached by a rule, include the case features used by that rule
as `PlanDefinition.action.input[]` entries. Because FHIR R4 action inputs are
`DataRequirement`, represent case-feature inputs with:

- `profile`: the generated case-feature `StructureDefinition` canonical URL when
  available.
- `codeFilter.valueSet`: the generated case-feature ValueSet, or a narrower
  feature-specific value set/code when appropriate.

Hoist repeated action conditions and inputs to the highest shared branch where
all child actions require the same feature context.

## Action Outputs

`actions[].produces_data_elements[]` should map to action output metadata:

- `PlanDefinition.action.output[]` where the output belongs to the rule/action
  branch.
- `ActivityDefinition` output metadata where the produced data is intrinsic to
  the reusable activity.

Do not model action output as producing a condition by default. The expected
flow is:

```text
activity performed -> data element available -> CQL case feature resolves -> rule condition applies
```

## Validation

L3 validation should verify:

- Every PlanDefinition condition references an existing CQL define.
- Every generated case-feature StructureDefinition expression references an
  existing CQL define.
- Every rule condition has a generated case-feature definition or a deliberate
  reason for omission.
- Every action input that represents a case feature references a known generated
  StructureDefinition and/or the case-feature ValueSet.
- Repeated sibling action conditions are hoisted to the highest shared branch
  and removed from lower branches.
