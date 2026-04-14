# Quickstart: `rh-inf-extract`

**A minimal worked example of the review-gated extraction workflow.**

---

## Prerequisites

```bash
uv sync

rh-skills init diabetes-ccm
# complete discovery + ingest first
# ensure sources/normalized/*.md and topics/diabetes-ccm/process/concepts.yaml exist
```

The topic should already have:
- ingested source records in `tracking.yaml`
- normalized source Markdown in `sources/normalized/`
- optional `topics/<topic>/process/concepts.yaml`

---

## Step 1: Generate the extract review packet

```bash
rh-inf-extract plan diabetes-ccm
```

Expected outcome:
- writes `topics/diabetes-ccm/process/plans/extract-plan.md`
- proposes a set of candidate L2 artifacts
- includes source coverage, key questions, required sections, and unresolved conflicts
- stops for reviewer approval before any L2 files are written

---

## Step 2: Reviewer edits and approves the plan

The reviewer updates frontmatter and per-artifact decisions in `extract-plan.md`, for example:

```yaml
status: approved
reviewer: "B. Kaney"
reviewed_at: 2026-04-14T15:00:00Z
artifacts:
  - name: screening-criteria
    reviewer_decision: approved
    approval_notes: "Proceed"
  - name: risk-factors
    reviewer_decision: needs-revision
    approval_notes: "Clarify age-stratified risk handling"
```

Only approved artifacts should be implemented.

---

## Step 3: Implement approved artifacts

```bash
rh-inf-extract implement diabetes-ccm
```

Expected behavior:
- refuses to run if plan status is not `approved`
- skips or blocks artifacts without `reviewer_decision: approved`
- calls `rh-skills promote derive` for each approved artifact, mapping plan metadata
  into `--artifact-type`, `--clinical-question`, `--required-section`,
  `--evidence-ref`, and `--conflict` arguments as needed
- runs `rh-skills validate <topic> <artifact>` after each derived file

Resulting artifacts:

```text
topics/diabetes-ccm/structured/
├── screening-criteria.yaml
└── workflow-steps.yaml
```

---

## Step 4: Verify extraction results

```bash
rh-inf-extract verify diabetes-ccm
```

Expected report:
- each approved artifact file exists
- each artifact passes schema validation
- traceability fields are present
- conflict records are present when required by the approved plan

---

## Output shape to expect

```text
topics/diabetes-ccm/process/plans/extract-plan.md
topics/diabetes-ccm/structured/*.yaml
tracking.yaml
```

The output of 005 becomes the L2 input set for `rh-inf-formalize`.
