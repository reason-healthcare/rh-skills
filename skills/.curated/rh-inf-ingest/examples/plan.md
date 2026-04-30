# rh-inf-ingest Example Plan

This example shows the transient pre-flight summary for
`rh-inf-ingest plan young-adult-hypertension`.

Unlike later lifecycle stages, ingest plan mode is read-only and does not
create a durable `process/plans` artifact. The durable upstream planning input
for ingest is `topics/<topic>/process/plans/discovery-plan.yaml`.

```text
rh-inf-ingest pre-flight summary — young-adult-hypertension

Untracked files in sources/:
  • sources/acc-aha-2017-hypertension.pdf
  • sources/uspstf-hypertension-screening.html
  • sources/jnc8-hypertension-management.html

Register each with:
  rh-skills ingest implement sources/acc-aha-2017-hypertension.pdf --topic young-adult-hypertension
  rh-skills ingest implement sources/uspstf-hypertension-screening.html --topic young-adult-hypertension
  rh-skills ingest implement sources/jnc8-hypertension-management.html --topic young-adult-hypertension

Tools:
  pdftotext (poppler): ✓
  pandoc: ✓
```

Status block:

```text
▸ rh-inf-ingest  young-adult-hypertension
  Stage:    plan — complete
  Sources:  3 files in sources/
  Next:     confirm to proceed → rh-inf-ingest implement young-adult-hypertension
```
