# Example Formalize Workflow Output

```text
$ rh-inf-formalize plan diabetes-ccm
Loaded approved structured inputs from extract-plan.md
Wrote topics/diabetes-ccm/process/plans/formalize-plan.md

$ rh-inf-formalize implement diabetes-ccm
Validated structured input: screening-criteria
Validated structured input: workflow-steps
Validated structured input: terminology-value-sets
Running: rh-skills promote combine diabetes-ccm screening-criteria workflow-steps terminology-value-sets diabetes-ccm-pathway
Running: rh-skills validate diabetes-ccm diabetes-ccm-pathway
✓ diabetes-ccm-pathway

$ rh-inf-formalize verify diabetes-ccm
✓ approved implementation target exists
✓ converged_from matches approved plan inputs
✓ required sections present
✓ required sections minimally complete
```
