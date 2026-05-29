# Example Formalize Workflow Output

## Plan Phase

```text
$ rh-inf-formalize plan diabetes-ccm
Loaded 3 approved structured inputs from extract-plan.yaml
  screening-decisions (decision-table)
  care-pathway (care-pathway)
  lab-value-sets (terminology)
⚠ Overlap detected: decision-table + care-pathway → PlanDefinition
  Default: separate resources (eca-rule vs clinical-protocol)
  Care-pathway phases mirror decision-table.pathway_phases[] when present
Wrote topics/diabetes-ccm/process/plans/formalize-plan.yaml
  3 artifacts proposed (1 per L2 type)
```

## Implement Phase

```text
$ rh-inf-formalize implement diabetes-ccm
Processing artifact 1/3: screening-decisions (decision-table)
  Running: rh-skills formalize diabetes-ccm screening-decisions
  ✓ PlanDefinition-screening-decisions.json
  ✓ ActivityDefinition-recommend-action.json
  ✓ Library-screening-decisions.json
  ✓ ScreeningDecisions.cql

Processing artifact 2/3: care-pathway (care-pathway)
  Running: rh-skills formalize diabetes-ccm care-pathway
  ✓ PlanDefinition-care-pathway.json
  ✓ ActivityDefinition-assess-patient.json

Processing artifact 3/3: lab-value-sets (terminology)
  Running: rh-skills formalize diabetes-ccm lab-value-sets
  ✓ ValueSet-diabetes-lab-codes.json

Packaging:
  Running: rh-skills package diabetes-ccm
  ✓ process/package-workspace/packager.toml
  ✓ process/package-workspace/ImplementationGuide.json
  6 resources bundled
```

## Verify Phase

```text
$ rh-inf-formalize verify diabetes-ccm
Checking decision-table artifact (screening-decisions):
  ✓ PlanDefinition has action[] with conditions
  ✓ ActivityDefinition outputs are referenced by definitionCanonical
  ✓ Library has type and content
  ✓ CQL syntactically valid
  ✓ converged_from matches approved plan inputs

Checking care-pathway artifact (care-pathway):
  ✓ Top-level phases align with decision-table.pathway_phases[]
  ✓ PlanDefinition has action[] with relatedAction
  ✓ ActivityDefinition has kind and code
  ✓ converged_from matches approved plan inputs

Checking terminology artifact (lab-value-sets):
  ✓ ValueSet has compose with include[]
  ✓ All codes verified via MCP
  ✓ converged_from matches approved plan inputs

Summary: 3/3 artifacts pass, 0 warnings, 0 errors
```
