# Example Formalize Workflow Output

```text
$ rh-inf-formalize plan diabetes-ccm
Loaded approved structured inputs from extract-plan.md
Wrote topics/diabetes-ccm/process/plans/formalize-plan.md

$ rh-inf-formalize implement diabetes-ccm
Validated structured input: screening-decisions
Validated structured input: care-pathway
Validated structured input: terminology
Running: rh-skills promote combine diabetes-ccm screening-decisions care-pathway terminology diabetes-ccm-pathway
Running: rh-skills validate diabetes-ccm diabetes-ccm-pathway
✓ diabetes-ccm-pathway

$ rh-inf-formalize verify diabetes-ccm
✓ approved implementation target exists
✓ converged_from matches approved plan inputs
✓ required sections present
✓ required sections minimally complete
```
