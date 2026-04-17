# Example Formalize Workflow Output

## Plan Phase

```text
$ rh-inf-formalize plan diabetes-ccm
Loaded 3 approved structured inputs from extract-plan.md
  screening-decisions (decision-table)
  care-pathway (care-pathway)
  lab-value-sets (terminology)
⚠ Overlap detected: decision-table + care-pathway → PlanDefinition
  Default: separate resources (eca-rule vs clinical-protocol)
Wrote topics/diabetes-ccm/process/plans/formalize-plan.md
  3 artifacts proposed (1 per L2 type)
```

## Implement Phase

```text
$ rh-inf-formalize implement diabetes-ccm
Processing artifact 1/3: screening-decisions (decision-table)
  Running: rh-skills formalize diabetes-ccm screening-decisions
  ✓ PlanDefinition-screening-decisions.json
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
  ✓ package.json
  ✓ ImplementationGuide-diabetes-ccm.json
  6 resources bundled
```

## Verify Phase

```text
$ rh-inf-formalize verify diabetes-ccm
Checking decision-table artifact (screening-decisions):
  ✓ PlanDefinition has action[] with conditions
  ✓ Library has type and content
  ✓ CQL syntactically valid
  ✓ converged_from matches approved plan inputs

Checking care-pathway artifact (care-pathway):
  ✓ PlanDefinition has action[] with relatedAction
  ✓ ActivityDefinition has kind and code
  ✓ converged_from matches approved plan inputs

Checking terminology artifact (lab-value-sets):
  ✓ ValueSet has compose with include[]
  ✓ All codes verified via MCP
  ✓ converged_from matches approved plan inputs

Summary: 3/3 artifacts pass, 0 warnings, 0 errors
```
