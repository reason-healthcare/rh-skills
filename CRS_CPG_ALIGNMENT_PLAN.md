# CRS CPG Alignment Plan

## Purpose

Realign the CRS `decision-table` and `care-pathway` artifacts to the CPG-on-FHIR distinction between:

- recommendation plans: event-condition-action recommendation definitions
- pathway plans: longitudinal clinical protocol definitions that orchestrate recommendations over time

This plan assumes:

- `strategy` is out of scope for now
- recommendations must remain independently usable outside the pathway
- the pathway should compose recommendations, not absorb their logic

## Current Problems

### Decision table owns pathway information

The current CRS `decision-table` contains broad workflow-stage markers such as:

- evaluation
- planning
- education
- follow-up

These are pathway phases, not recommendation-scoped ECA triggers.

### Care pathway owns recommendation logic

The current CRS `care-pathway` contains step text that embeds recommendation logic directly, especially conditional recommendations such as advanced-subtype surgical approach decisions.

### Resulting mismatch

- the `decision-table` is too workflow-oriented
- the `care-pathway` is too recommendation-oriented
- the boundary between recommendation definition and pathway definition is blurred

## Target Model

### L2 ownership

#### Care pathway should own

- major phases of care
- sequencing over time
- transitions between phases or steps
- references to recommendation units relevant at each step

#### Decision table should own

- recommendation-scoped triggering moments
- applicability conditions
- recommended actions
- rule branches
- recommendation-level evidence and rationale

## Phase 1: Improve The Single Decision Table Plan

Phase 1 keeps a single CRS `decision-table` artifact, but makes it behave more like a true ECA recommendation bundle.

### Phase 1 goals

- keep one decision-table artifact
- narrow events to recommendation-scoped triggers
- remove inherited pathway-stage prerequisites from downstream rules
- enrich recommendation actions so they can formalize cleanly to `ActivityDefinition`
- preserve recommendation standalone usability

### Phase 1 decision-table changes

#### 1. Replace broad workflow events with recommendation-scoped triggers

Replace broad pathway-stage events such as:

- `event-eval`
- `event-plan`
- `event-educate`
- `event-followup`

With recommendation-scoped triggers such as:

- `diagnosis-and-candidacy-assessment-completed`
- `purulent-discharge-assessment-completed`
- `preoperative-planning-initiated`
- `advanced-subtype-identified-during-planning`
- `preoperative-counseling-encounter-started`
- `postoperative-followup-encounter-started`

#### 2. Remove inherited pathway progression from downstream rules

Recommendation rules should not restate upstream pathway-stage prerequisites unless they are clinically required by the recommendation itself.

Examples:

- the CT recommendation should not carry the entire earlier evaluation stack
- the counseling recommendation should not restate all preoperative candidacy conditions
- the follow-up documentation recommendation should focus on postoperative timing and context

Rule simplification principle:

- if a condition is only present because the patient has arrived at a phase of care, it belongs to the pathway in Phase 2
- if a condition is clinically required for the recommendation itself, it stays in the decision-table

#### 3. Enrich actions while keeping one artifact

Decision-table `actions[]` should be rich enough to become `ActivityDefinition` resources.

Recommended fields:

- `id`
- `label`
- `description`
- `kind`
- `code`
- `valueset`
- `do_not_perform`
- `participants`
- `documentation`
- `intent`

#### 4. Keep one artifact, but group recommendations conceptually

The artifact may remain one file, but its recommendations should be organized conceptually into:

- candidacy recommendations
- preoperative planning recommendations
- counseling recommendations
- operative approach recommendations
- postoperative follow-up recommendations

This can be expressed with optional grouping metadata such as `group`.

#### 5. Preserve standalone recommendation use

Each rule should remain independently meaningful outside the pathway by keeping:

- its own trigger
- its own applicability conditions
- its own recommendation outputs
- its own supporting documentation

## Phase 2: Full Pathway/Recommendation Ownership Split

Phase 2 introduces the cleaner CPG-on-FHIR ownership split:

- pathway owns longitudinal care phases and orchestration
- decision-table owns recommendation-scoped decision logic

## Proposed L2 Changes

### 1. Refactor care-pathway into pathway-owned phases and steps

Keep `care-pathway` as the longitudinal orchestration artifact.

Update `steps[]` so each step represents a care phase or pathway node, not embedded recommendation content.

Suggested pathway steps:

1. diagnosis confirmation
2. candidacy assessment
3. benefit-risk decision
4. preoperative planning
5. preoperative counseling
6. operative approach selection
7. postoperative follow-up
8. postoperative outcome documentation

Add explicit identifiers and recommendation references:

```yaml
steps:
  - id: diagnosis-confirmation
    label: Confirm CRS diagnosis
    description: Confirm the patient meets established CRS diagnostic criteria.
    recommendation_ids:
      - rec-confirm-diagnosis
    next:
      - candidacy-assessment
```

Recommended new fields for `care-pathway.steps[]`:

- `id`
- `label`
- `description`
- `recommendation_ids`
- `next`
- `actor`
- `applicability_condition` optional

### 2. Narrow decision-table events to recommendation-scoped triggers

Remove broad pathway-stage events such as:

- `event-eval`
- `event-plan`
- `event-educate`
- `event-followup`

Replace them with recommendation-scoped triggers such as:

- `diagnosis-confirmed-and-surgery-being-considered`
- `candidacy-assessment-completed`
- `preoperative-planning-initiated`
- `advanced-subtype-identified-during-planning`
- `preoperative-counseling-encounter-started`
- `postoperative-followup-encounter-started`
- `purulent-discharge-assessment-completed`

Rule of thumb:

- broad phase of care -> pathway
- recommendation evaluation moment -> decision-table event
- patient-state fact -> decision-table condition

### 3. Keep recommendations standalone

Each decision-table recommendation should remain independently usable by keeping:

- its own trigger
- its own conditions
- its own action payload
- its own evidence/rationale

The pathway should reference recommendations, but recommendations must not depend on pathway-step state such as `step = 4`.

### 4. Enrich decision-table actions

Decision-table `actions[]` should become robust recommendation outputs that can formalize to `ActivityDefinition`.

Recommended fields:

- `id`
- `label`
- `description`
- `kind`
- `code`
- `valueset`
- `do_not_perform`
- `participants`
- `documentation`
- `intent`

Example:

```yaml
actions:
  - id: obtain-fine-cut-ct
    label: Obtain fine-cut computed tomography for surgical planning
    description: Order fine-cut CT when surgical planning is underway and imaging is not already available.
    kind: ServiceRequest
    valueset: computed-tomography-of-paranasal-sinuses
```

### 5. Optionally split the monolithic decision table

If the CRS artifact remains too dense, split one large `decision-table` into multiple recommendation-group artifacts, for example:

- diagnosis-and-candidacy-recommendations
- preoperative-planning-recommendations
- counseling-recommendations
- postoperative-followup-recommendations

This is optional, but it may improve clarity and recommendation portability.

## Proposed L3 Changes

## Decision-table L3 template changes

Decision-table should formalize to:

- one `PlanDefinition` for recommendation logic
- one `ActivityDefinition` per `actions[]`
- one `Library` for reusable condition logic

### PlanDefinition template changes

Current problem:

- top-level actions are derived from conditions rather than rules

Target:

- each L2 `rule` becomes a `PlanDefinition.action`
- each rule action carries:
  - `id`
  - `title`
  - `description`
  - `trigger`
  - `condition[]`
  - nested `action[]` referencing `ActivityDefinition` resources via `definitionCanonical`

Template expectation:

```json
{
  "id": "rule-001",
  "title": "Offer surgery when candidacy and benefit criteria are met",
  "trigger": [{ "type": "named-event", "name": "candidacy-assessment-completed" }],
  "condition": [
    {
      "kind": "applicability",
      "expression": {
        "language": "text/cql-identifier",
        "expression": "EstablishedChronicRhinosinusitisDiagnosticCriteriaAreMet"
      }
    }
  ],
  "action": [
    {
      "definitionCanonical": "https://example.org/fhir/ActivityDefinition/offer-surgery"
    }
  ]
}
```

### ActivityDefinition template changes

Each recommendation action should become its own `ActivityDefinition`.

Template should support:

- `kind`
- `intent`
- `code`
- `doNotPerform`
- `participant`
- `relatedArtifact`
- `description`

This gives the recommendation layer a concrete reusable payload independent of pathway composition.

### Library template changes

The `Library` should support only rule applicability logic:

- one boolean define per condition or derived condition
- no substitution for recommendation payload

The library should not be treated as the recommendation artifact itself.

## Care-pathway L3 template changes

Care-pathway should formalize to one pathway-style `PlanDefinition`.

### Pathway PlanDefinition target

The pathway `PlanDefinition` should:

- represent ordered care over time
- use `action.relatedAction[]` for sequencing
- reference recommendation units through `definitionCanonical`
- avoid embedding recommendation logic directly in step prose

Preferred target:

- pathway steps reference recommendation `PlanDefinition` resources when those are available

Interim acceptable target:

- pathway steps reference decision-table-generated `ActivityDefinition` resources while recommendation `PlanDefinition` decomposition is still evolving

### Pathway step template changes

Each L2 step should map to:

- `action.id`
- `action.title`
- `action.description`
- `action.relatedAction[]`
- `action.definitionCanonical`

Example:

```json
{
  "id": "preoperative-planning",
  "title": "Preoperative planning",
  "description": "Conduct surgical planning and imaging review.",
  "definitionCanonical": "https://example.org/fhir/PlanDefinition/rec-preoperative-planning",
  "relatedAction": [
    {
      "actionId": "preoperative-counseling",
      "relationship": "before-start"
    }
  ]
}
```

## Connection Model

### Immediate connection model

In the near term:

- decision-table emits `ActivityDefinition` outputs
- care-pathway references those outputs or recommendation-level wrappers

### Preferred future connection model

Preferred end state:

- recommendation artifacts are their own `PlanDefinition` recommendation definitions
- care-pathway references those recommendation `PlanDefinition`s
- `ActivityDefinition` remains the concrete action payload under the recommendation layer

This gives:

- standalone recommendations
- reusable recommendation logic
- pathway composition without duplication

## Implementation Phases

### Phase 1. Single decision-table cleanup

- keep one `decision-table`
- replace broad workflow events with recommendation-scoped triggers
- remove inherited upstream conditions where they are not recommendation-local
- enrich `actions[]` for `ActivityDefinition` generation
- leave `care-pathway` structurally unchanged

### Phase 2. L2 ownership split

- move broad phase ownership into `care-pathway`
- add recommendation references to pathway steps
- narrow decision-table further to recommendation-local logic

### Phase 3. L3 recommendation/action template alignment

- ensure decision-table emits rule-based `PlanDefinition`
- emit one `ActivityDefinition` per action
- keep `Library` scoped to applicability logic

### Phase 4. Pathway template alignment

- make pathway a sequencing/orchestration artifact
- reference recommendation outputs from steps
- remove recommendation logic from pathway prose

### Phase 5. Topic regeneration and review

- regenerate CRS computable artifacts
- verify recommendation standalone use
- verify pathway composition
- review for CPG-on-FHIR semantic alignment

## Acceptance Criteria

The CRS topic is aligned when:

- no broad care phases remain as decision-table event triggers
- pathway steps no longer contain embedded recommendation logic
- each decision-table recommendation can stand alone outside the pathway
- decision-table L3 outputs include actionable `ActivityDefinition`s
- pathway L3 output references recommendation outputs rather than a single generic activity
- sequencing is explicit in the pathway and recommendation logic is explicit in the recommendation layer
