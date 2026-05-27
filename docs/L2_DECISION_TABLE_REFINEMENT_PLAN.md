# L2 Decision-Table Refinement Plan

## Purpose

Use the CRS surgical management example as a forcing function to improve the
`rh-skills` CLI and curated skills so L2 `decision-table` artifacts are more
consistently recommendation-scoped, less duplicative, and easier to formalize
into clean FHIR CPG resources.

This is a framework plan, not a topic-specific remediation note.

## What The CRS Example Exposed

### 1. The framework documents the right boundary, but does not enforce it

Current docs and skills already say:

- `decision-table` should model recommendation-scoped ECA logic
- `care-pathway` should model longitudinal sequencing

But the CLI mostly validates presence and shape, not modeling quality. A topic
can still pass validation while:

- using pathway phases as decision-table events
- repeating upstream prerequisites across downstream rules
- duplicating near-identical actions across ECA branches
- mixing pathway orchestration with recommendation logic

### 2. Formalization is a mapper, not a model-quality gate

`src/rh_skills/commands/formalize.py` faithfully converts L2 rows into FHIR:

- `sections.actions[]` -> `ActivityDefinition`
- `sections.rules[]` -> `PlanDefinition.action`

It does not currently detect:

- duplicate `then[]` branches with only minor wording differences
- broad event patterns like `event-plan` that should be pathway-owned
- rules whose condition sets include inherited workflow state instead of local
  recommendation applicability
- repeated action bundles that should be factored into shared actions or grouped
  recommendations

### 3. Current validation is structural, not semantic

`src/rh_skills/commands/validate.py` currently checks:

- required extract fields
- evidence traceability presence
- formalize plan consistency
- FHIR JSON structural validity

It does not perform decision-table-specific linting for:

- unused events, conditions, or actions
- duplicated rule signatures
- contradictory or subsumed branches
- phase leakage from care-pathway into decision-table
- recommendation grouping quality

### 4. Rendering exposes completeness, but not duplication or leakage

`src/rh_skills/commands/render.py` computes combination coverage and
contradictions, which is useful, but it does not report:

- duplicate action bundles across rules
- duplicate action definitions with overlapping descriptions
- rules that differ only by pathway phase naming
- opportunities to collapse broad event families into recommendation-scoped
  trigger moments

## Framework Goals

1. Make the authoring boundary between `decision-table` and `care-pathway`
   executable, not just documented.
2. Detect branch duplication before formalization.
3. Encourage recommendation-scoped event design.
4. Preserve simple authoring for small tables while adding stronger linting for
   complex guideline topics.
5. Keep FHIR formalization deterministic by improving L2 quality upstream.

## Proposed Changes

### A. Add decision-table quality linting to `validate`

Add a type-specific validation pass for `artifact_type: decision-table`.

New checks:

- `unused-events`: event defined but never referenced by any rule
- `unused-conditions`: condition defined but never used in any `when`
- `unused-actions`: action defined but never referenced by any `then`
- `duplicate-rule-signature`: same event plus same normalized `when` map appears
  in multiple rules
- `duplicate-action-bundle`: multiple rules resolve to the same normalized
  `then[]` set
- `broad-phase-event-warning`: event ids or labels that look like pathway phases
  such as `eval`, `plan`, `followup`, `education`
- `phase-leakage-warning`: downstream rules that restate broad prerequisite
  workflow state instead of local recommendation applicability
- `single-branch-action-warning`: action defined only once and semantically
  overlaps another action strongly enough that reuse is more likely than a new
  action

Suggested implementation point:

- add `_validate_decision_table_semantics()` in
  `src/rh_skills/commands/validate.py`
- invoke it from `_validate_extract_artifact()` when `artifact_type` is
  `decision-table`

Severity:

- unused definitions and duplicate rule signatures -> error
- broad phase events and likely phase leakage -> warning
- duplicate action bundles -> warning in v1, promote to error later if stable

### B. Expand render output with an audit section

Extend the decision-table report to include an automatically generated audit
summary.

New report sections:

- `Event Audit`
- `Rule Redundancy`
- `Shared Action Bundles`
- `Unused Definitions`
- `Boundary Warnings`

Suggested implementation point:

- extend `src/rh_skills/commands/render.py`
- augment `src/rh_skills/templates/render/decision-table/report.md.j2`

This gives reviewers quick feedback before L3 formalization and makes the
quality signals visible without requiring a separate command.

### C. Tighten the L2 schema guidance for reusable branch structure

The current schema guidance is directionally correct but too permissive.

Add recommended fields for `decision-table`:

- `group`: conceptual recommendation family such as `candidacy`,
  `preoperative-planning`, `counseling`, `followup`
- `recommendation_id`: stable identifier shared by rules that express one
  recommendation with multiple branches
- `branch`: branch name such as `eligible`, `ineligible`, `exception`
- `branch_priority`: optional explicit ordering for exception-first evaluation
- `rationale`: short rule-level explanation when the branch is clinically
  meaningful

Why this helps:

- makes duplication easier to detect
- supports grouping related rules without forcing multiple artifacts
- creates a better bridge to FHIR `PlanDefinition.action` grouping later

Suggested implementation points:

- update `src/rh_skills/schemas/l2-schema.yaml`
- update `docs/FORMALIZE_STRATEGIES.md`
- update curated skill examples

### D. Improve `promote` stubs so authors start from better defaults

Current decision-table stubs are structurally valid, but they do not nudge the
author toward recommendation-scoped modeling strongly enough.

Improve the generated stub copy to:

- name triggers as recommendation evaluation moments
- discourage broad phase ids
- suggest `group` and `recommendation_id`
- include a comment showing one recommendation with multiple branch rows

Suggested implementation point:

- update decision-table starter content in `src/rh_skills/commands/promote.py`

### E. Strengthen curated skill instructions

The skill guidance should explicitly require a branch-dedup pass during extract
and formalize planning.

For `rh-inf-extract`:

- require checking whether multiple rules share the same action outcome
- require moving broad temporal sequencing into `care-pathway`
- require recommendation-scoped event naming

For `rh-inf-formalize`:

- require reviewing rule families for action duplication before approving the
  formalize plan
- require flagging when `decision-table` and `care-pathway` overlap because the
  decision table is carrying orchestration logic rather than only PlanDefinition
  resource overlap

Suggested implementation points:

- `skills/.curated/rh-inf-extract/SKILL.md`
- `skills/.curated/rh-inf-formalize/SKILL.md`

### F. Prepare formalize for recommendation grouping, but do not block on it

The formalizer should remain deterministic, but it can preserve higher-quality
L2 grouping metadata once present.

Near-term changes:

- carry `group` and `recommendation_id` into `PlanDefinition.action.title` or
  extension metadata
- optionally sort rules by `group`, then `branch_priority`, then source order

Do not yet:

- auto-merge semantically similar actions
- auto-split one decision table into multiple PlanDefinitions

Those are reviewer-level modeling choices and should stay upstream for now.

## Suggested Delivery Sequence

### Phase 1: Low-risk linting and review visibility

1. Add decision-table semantic linting in `validate.py`
2. Add redundancy and boundary audit output in `render.py`
3. Add regression fixtures based on the CRS example pattern

### Phase 2: Authoring guidance and stub improvements

1. Update `l2-schema.yaml` guidance
2. Improve `promote.py` decision-table starter content
3. Update `rh-inf-extract` and `rh-inf-formalize` skill instructions

### Phase 3: Metadata-aware formalization

1. Preserve `group` and `recommendation_id` during formalization
2. Add stable ordering for grouped recommendations
3. Revisit whether grouped recommendations should become nested FHIR actions

## Test Plan

Add tests that cover:

- duplicate rule signature detection
- duplicate `then[]` bundle warnings
- broad phase event warnings
- unused event/condition/action detection
- render audit output for shared action bundles
- acceptance of clean recommendation-scoped tables

Suggested files:

- `tests/unit/test_validate.py`
- `tests/unit/test_render.py`
- `tests/unit/test_promote.py`

## Recommended First Slice

If we want the highest signal for the least code, start here:

1. implement `decision-table` semantic linting in `validate.py`
2. expose the lint results in the rendered decision-table report
3. update skill instructions so new artifacts stop reproducing the CRS pattern

That would address the biggest framework gap without changing the formalization
contract yet.
