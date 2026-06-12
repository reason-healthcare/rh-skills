# Next Steps Plan

Modify the rh-skills framework so recommendation-to-care-pathway linkage
coverage is enforced only when a topic contains both an approved
`decision-table` and an approved `care-pathway` artifact for the same clinical
workflow.

## Goal

When both artifacts are present, all recommendation-scoped decision-table rules
must be represented in the care-pathway linkage model. A care-pathway branch or
leaf may legitimately correspond to multiple recommendations; the requirement is
not "one rule per branch," it is "do not drop recommendation coverage." The
framework should ensure that all applicable recommendation rules are linked
somewhere appropriate in the care-pathway, whether singly or in grouped form.

## What To Change

### 1. Extract / Validation Behavior

Add a paired-artifact consistency rule:

- Only activate it when both a `decision-table` and `care-pathway` exist for
  the same topic/artifact pair.
- Treat recommendation-scoped decision-table rules as rules that should map to
  care-pathway leaf nodes or grouped recommendation leaf nodes.
- A care-pathway leaf may link:
  - one rule via `rule_id`
  - multiple related rules via `rule_ids[]`
- Parent steps with children must not carry `rule_id` or `rule_ids[]`.
- The requirement is complete recommendation coverage, not forced 1:1
  decomposition.
- If a recommendation rule is not linked from any care-pathway leaf, surface
  that clearly.
- Prefer a blocking validation error when the framework can determine a rule is
  orphaned.
- If there is genuine ambiguity that cannot be resolved deterministically, emit
  a strong warning listing the unlinked rule IDs.

### 2. Care-Pathway Enrichment / Derive Behavior

- When both artifacts are present, improve rule-link assignment so all distinct
  recommendation rules are considered for pathway coverage.
- Do not collapse multiple distinct recommendations into one broad branch in a
  way that loses explicit linkage coverage.
- It is valid for one pathway branch or leaf to represent multiple
  recommendations when they truly belong together clinically.
- Use grouped `rule_ids[]` when multiple recommendation rules share the same
  pathway node meaning, actor, and timing, and when grouping them preserves
  explicit coverage rather than hiding distinctions.
- The framework should optimize for correct coverage and clinically coherent
  grouping, not forced over-splitting.
- If a step label and linked rule set appear semantically mismatched, surface
  that mismatch instead of silently attaching the wrong rule set.
- Normalize generated linkage IDs to be simple and numbered rather than highly
  detailed or source-literal. Follow the same style already used for
  `claim_id` values: stable, compact identifiers such as `rule-001`,
  `step-001`, or similar, rather than verbose sentence-derived IDs.

### 3. Formalize / L3 Behavior

- Do not invent missing recommendation-to-pathway links.
- Consume the L2 linkage as the source of truth.
- If both artifacts are present and orphaned recommendation rules still reach
  formalize, emit a clear warning that L2 linkage coverage is incomplete.
- Preserve grouped recommendation linkage when `rule_ids[]` is used
  appropriately; do not collapse multi-rule linkage to a single recommendation
  reference.

## Constraints

- This rule applies only when both `decision-table` and `care-pathway` are
  present.
- Do not break topics that have only a decision-table or only a care-pathway.
- Do not hard-code CRS-specific artifact names, rule IDs, or pathway steps.
- Keep the behavior generalizable for other narrative guidelines.
- Keep generated IDs simple, stable, and numbered where appropriate rather than
  overly detailed. Favor compact machine IDs over verbose source-literal IDs.
- Update the full framework surface consistently:
  - CLI/framework code
  - curated extract skill/reference/examples
  - docs
  - tests/regressions

## Implementation Expectations

- Inspect the current pairing/linkage logic and validators first.
- Add tests for:
  - both artifacts present with full linkage coverage -> passes
  - both artifacts present with one orphaned rule -> fails or strongly warns,
    per chosen rule
  - decision-table only -> no paired-linkage requirement
  - care-pathway only -> no paired-linkage requirement
  - grouped `rule_ids[]` coverage -> passes when appropriate
  - grouped branches that still omit one recommendation rule -> fails or warns
    because coverage is incomplete
- After implementation, rerun the external AAO CRS repo through extract
  implement to formalize/package and verify whether all recommendation rules are
  represented in care-pathway leaf linkage.

## Iteration Workflow

Use the AI iteration guide workflow:

- refresh install surfaces
- use curated skills
- use stub mode by default
- do not hand-edit generated artifacts
- commit each meaningful framework step separately
- summarize whether the fix is truly generalizable
