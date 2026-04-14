# Quickstart: `rh-inf-formalize`

**A minimal worked example of the review-gated formalization workflow.**

---

## Prerequisites

```bash
uv sync

rh-skills init diabetes-ccm
# complete discovery + ingest + extract first
# ensure topics/diabetes-ccm/structured/*.yaml exist and pass validation
```

The topic should already have:
- approved extract review packet in `topics/<topic>/process/plans/extract-plan.md`
- valid structured artifacts in `topics/<topic>/structured/`
- tracking metadata showing structured derivation

---

## Step 1: Generate the formalize review packet

```bash
rh-inf-formalize plan diabetes-ccm
```

Expected outcome:
- writes `topics/diabetes-ccm/process/plans/formalize-plan.md`
- proposes one primary pathway-oriented computable artifact package
- may include alternate candidate artifacts for reviewer comparison
- records eligible structured inputs and required computable sections
- stops for reviewer approval before any L3 files are written
- delegates the deterministic plan write to `rh-skills promote formalize-plan`
- keeps the primary target, selected inputs, and required sections visible in the review summary or first artifact card for quick reviewer scanning

---

## Step 2: Reviewer edits and approves the plan

The reviewer updates frontmatter and per-artifact decisions in
`formalize-plan.md`, for example:

```yaml
status: approved
reviewer: "B. Kaney"
reviewed_at: 2026-04-14T18:30:00Z
artifacts:
  - name: diabetes-care-pathway
    implementation_target: true
    reviewer_decision: approved
    approval_notes: "Proceed with this pathway package"
  - name: diabetes-measure-package
    implementation_target: false
    reviewer_decision: rejected
    approval_notes: "Defer measure package to a later phase"
```

Only the approved implementation target should be created.

---

## Step 3: Implement the approved computable artifact

```bash
rh-inf-formalize implement diabetes-ccm
```

Expected behavior:
- refuses to run if plan status is not `approved`
- refuses to run if the target artifact is not marked
  `implementation_target: true` and `reviewer_decision: approved`
- confirms each selected L2 input is approved in extract and still valid
- calls `rh-skills promote combine` with the approved `input_artifacts[]`
- runs `rh-skills validate <topic> <artifact>` after the L3 artifact is written

Resulting artifact:

```text
topics/diabetes-ccm/computable/
└── diabetes-care-pathway.yaml
```

---

## Step 4: Verify formalization results

```bash
rh-inf-formalize verify diabetes-ccm
```

Expected report:
- the approved implementation target file exists
- the artifact passes base L3 schema validation
- `converged_from[]` matches the approved `input_artifacts[]`
- required sections from the approved plan are present
- required sections are minimally complete for their section type

---

## Output shape to expect

```text
topics/diabetes-ccm/process/plans/formalize-plan.md
topics/diabetes-ccm/computable/*.yaml
tracking.yaml
```

The output of 006 becomes the terminal computable repository artifact for the
current RH lifecycle.
