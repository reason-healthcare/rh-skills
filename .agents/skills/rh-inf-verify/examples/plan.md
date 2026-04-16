# Example Unified Verification Context

This worked example is a reviewer-facing run context for `rh-inf-verify`. It is
not a durable plan artifact and should not be written to a topic directory.

```markdown
Topic: diabetes-ccm

Observed topic state
- discovery-plan.yaml exists
- normalized ingest outputs exist under sources/normalized/
- extract-plan.md is approved and structured artifacts exist
- no formalize-plan.md yet

Expected stage applicability
| Stage | Applicability | Why |
|-------|---------------|-----|
| discovery | applicable | discovery plan exists and can be re-verified |
| ingest | applicable | source registration and normalized outputs exist |
| extract | applicable | extract plan and structured outputs exist |
| formalize | not-yet-ready | no formalize plan or computable artifact exists yet |

Delegation plan
- run `rh-inf-discovery verify diabetes-ccm`
- run `rh-inf-ingest verify diabetes-ccm`
- run `rh-inf-extract verify diabetes-ccm`
- do not launch formalize verify; report applicability explicitly instead

Reviewer expectation
- one consolidated report
- stage-attributed failures and warnings preserved
- no file writes and no tracking updates
```
