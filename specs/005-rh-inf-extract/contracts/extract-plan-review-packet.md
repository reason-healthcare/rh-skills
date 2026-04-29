# Contract: `extract-plan.md` Review Packet

**Phase 1 Design Artifact** | **Branch**: `005-rh-inf-extract`

---

## File

`topics/<topic>/process/plans/extract-plan.md`

## Frontmatter Schema

```yaml
topic: <topic-slug>
plan_type: extract
status: <pending-review | approved | rejected>
reviewer: <string>
reviewed_at: <ISO-8601 timestamp or null>
artifacts:
  - name: <kebab-case artifact name>
    artifact_type: <catalog type>
    custom_artifact_type: <optional custom label or null>
    source_files:
      - sources/normalized/<source>.md
    purpose: <string — what this artifact does downstream>
    rationale: <string — why these sources were selected>
    key_questions:
      - <question>
    required_sections:
      - summary
      - evidence_traceability
    concerns:
      - concern: <description of tension or ambiguity>
        resolution: <resolution text or empty string if open>
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

Under `Proposed Artifacts`, each artifact should have a review card containing:
- artifact name and type
- source coverage summary
- purpose and clinical rationale
- required sections to derive
- open concerns
- reviewer decision summary

## Approval Gate Semantics

- Plan-level `status` must be `approved` before implement can proceed.
- Every artifact intended for implementation must have `reviewer_decision: approved`.
- Any artifact with `needs-revision`, `pending-review`, or `rejected` must block or be excluded from implementation.

## Write Behavior

- `rh-inf-extract plan` writes this file.
- `rh-inf-extract implement` reads but does not rewrite reviewer decisions.
- Reviewer edits happen outside the CLI/agent write path.
