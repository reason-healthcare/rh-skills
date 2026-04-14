# Contract: `formalize-plan.md` Review Packet

**Phase 1 Design Artifact** | **Branch**: `006-rh-inf-formalize`

---

## File

`topics/<topic>/process/plans/formalize-plan.md`

## Frontmatter Schema

```yaml
topic: <topic-slug>
plan_type: formalize
status: <pending-review | approved | rejected>
reviewer: <string>
reviewed_at: <ISO-8601 timestamp or null>
artifacts:
  - name: <kebab-case target name>
    artifact_type: <pathway-package | alternate package label>
    input_artifacts:
      - <approved-l2-artifact-name>
    rationale: <string>
    required_sections:
      - pathways
      - actions
      - value_sets
    implementation_target: <true | false>
    reviewer_decision: <pending-review | approved | needs-revision | rejected>
    approval_notes: <string>
```

## Body Sections

The Markdown body must appear in this order:

1. `# Review Summary`
2. `# Proposed Artifacts`
3. `# Cross-Artifact Issues`
4. `# Implementation Readiness`

## Review Card Expectations

Under `Proposed Artifacts`, each candidate should include:
- target artifact name and type
- eligible structured inputs
- rationale for the converged package
- required computable sections
- unresolved overlap/modeling notes
- whether it is the single implementation target
- reviewer decision summary

## Approval Gate Semantics

- Plan-level `status` must be `approved` before implement can proceed.
- Exactly one artifact entry may set `implementation_target: true`.
- The implementation target must also have `reviewer_decision: approved`.
- Alternate candidates with `needs-revision`, `pending-review`, or `rejected`
  must not be implemented.

## Input Eligibility Rules

- Every `input_artifacts[]` entry must correspond to an approved and currently
  valid L2 artifact in `topics/<topic>/structured/`.
- Missing or invalid L2 inputs block implementation.

## Write Behavior

- `rh-inf-formalize plan` writes this file.
- `rh-inf-formalize implement` reads but does not rewrite reviewer decisions.
- Reviewer edits happen outside the CLI/agent write path.
