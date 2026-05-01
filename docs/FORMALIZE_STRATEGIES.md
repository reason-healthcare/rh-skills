# L2 → L3 Formalization Strategies

This document captures the business rules for converting each L2 structured
artifact type into its L3 FHIR computable representation. Each strategy
describes **what goes in** (L2 shape), **what comes out** (L3 FHIR resources),
and **how the conversion works** (mapping rules, decisions, MCP usage).

---

## Strategy Overview

| L2 Type | L3 FHIR Target | Primary Resource | Supporting Resources |
|---------|----------------|------------------|---------------------|
| `evidence-summary` | Evidence package | Evidence | EvidenceVariable, Citation |
| `decision-table` | ECA rule set | PlanDefinition (type: eca-rule) | Library (CQL expressions) |
| `care-pathway` | Clinical protocol | PlanDefinition (type: clinical-protocol) | ActivityDefinition |
| `terminology` | Value set bundle | ValueSet | ConceptMap |
| `measure` | Quality measure | Measure | Library (CQL population logic) |
| `assessment` | Questionnaire | Questionnaire | QuestionnaireResponse (example) |
| `policy` | Payer policy | PlanDefinition (type: eca-rule) | Questionnaire (DTR), Library (CQL pre-population) |

---

## 1. evidence-summary → Evidence Package

### L2 Input Shape

```yaml
artifact_type: evidence-summary
sections:
  findings: [...]          # graded clinical claims
  populations: [...]       # PICOTS populations
  interventions: [...]     # studied interventions
  outcomes: [...]          # measured outcomes
  evidence_quality: ...    # overall GRADE or equivalent
```

### L3 Output

- **Evidence**: One per major finding/claim. Contains `description`,
  `certainty[]` (maps from evidence_quality), and `variableDefinition[]`
  referencing EvidenceVariable resources.
- **EvidenceVariable**: One per population, intervention, comparator, or
  outcome concept. Contains `characteristic[]` with coded criteria.
- **Citation** (optional): Bibliographic reference for the source guideline.

### Conversion Rules

1. **Findings → Evidence resources.** Each entry in `sections.findings[]` produces
   one Evidence resource. The finding's statement becomes `Evidence.description`.
   If the finding carries a per-claim quality grade, map it to
   `Evidence.certainty[0].rating` (see grading table below). When no per-claim
   grade exists, apply the artifact-level `evidence_quality` to every Evidence
   resource as a default certainty.

2. **PICOTS → EvidenceVariable resources.** Each distinct population,
   intervention, comparator, and outcome in `sections.populations[]`,
   `sections.interventions[]`, and `sections.outcomes[]` becomes one
   EvidenceVariable. Use `EvidenceVariable.characteristic[]` to encode coded
   criteria (resolved via MCP). Link each EvidenceVariable back to its Evidence
   resources through `Evidence.variableDefinition[].observed` (for outcomes) or
   `.intended` (for populations/interventions).

3. **Evidence grading map.** Map the source grading system to FHIR
   `certainty.rating`:
   - GRADE high / Oxford 1a → `high`
   - GRADE moderate / Oxford 2a-2b → `moderate`
   - GRADE low / Oxford 3a-4 → `low`
   - GRADE very-low / Oxford 5 → `very-low`
   - If the source uses an unrecognized scale, record the raw grade in
     `certainty.note` and set rating to `no-concern` with a reviewer comment.

4. **Citation resources.** Generate one Citation per unique entry in
   `references[]` or `derived_from[]`. Link each Evidence resource to its
   Citation via `Evidence.relatedArtifact[]` with type `cite`. Omit Citation
   when the only reference is an inline guideline name with no bibliographic
   detail.

5. **L3 output files.** Each Evidence resource is written as an individual
   FHIR JSON file (`Evidence-<id>.json`). Each EvidenceVariable is a
   separate file (`EvidenceVariable-<id>.json`). Citations produce
   `Citation-<id>.json` files. All are placed in the topic's computable
   directory and referenced by the ImplementationGuide resource during
   packaging.

### MCP Usage

- `reasonhub-search_snomed` — resolve clinical finding and procedure concepts
  in populations, interventions, outcomes
- `reasonhub-codesystem_lookup` — confirm canonical displays

### Resolved Decisions

- **Non-GRADE/Oxford scales**: Map USPSTF and other scales to FHIR certainty ratings
  using the closest semantic match (e.g., USPSTF A → `high`, B → `moderate`,
  C → `low`, D/I → `very-low`). Document the mapping in a `_review_note` extension.
- **Finding-to-resource ratio**: 1:1 for v1 — each finding gets its own Evidence
  resource. Group related findings under a common `EvidenceVariable` for PICO framing.
- **Multi-source conflicts**: Separate Evidence resources, one per source. Flag
  conflicts via `Evidence.note` with cross-references to the conflicting resource.

---

## 2. decision-table → PlanDefinition (ECA Rules)

### L2 Input Shape

```yaml
artifact_type: decision-table
sections:
  events: [...]       # trigger definitions for when the table applies
  conditions: [...]   # decision conditions with thresholds
  actions: [...]      # resulting actions per condition branch
  rules: [...]        # event → condition → action mappings
  exceptions: [...]   # override / exclusion rules
```

### L3 Output

- **PlanDefinition** (type: `eca-rule`): One resource with `action[]` entries.
  Each action has `condition[]` (applicability) and nested `action[]` for
  branching logic.
- **Library** (optional): CQL expressions for complex condition evaluation
  (e.g., calculated scores, compound boolean logic).
- **ActivityDefinition**: Reusable clinical activities referenced
  by `action.definitionCanonical`. This is one-to-one with the Action in ECA.

### Conversion Rules

1. **Conditions → action.condition (applicability).** Each entry in
   `sections.conditions[]` becomes a `PlanDefinition.action.condition` with
   `kind: applicability`. Simple threshold conditions (e.g., "A1C ≥ 6.5%")
   are expressed as inline FHIRPath in `condition.expression`. Compound
   boolean conditions (AND/OR with 3+ clauses) are extracted to a Library
   CQL expression and referenced in `PlanDefinition.library[]` using it's
   canonical URL (`{Library.url}|{Library.version}`). The CQL
   definition should then be used in `condition.expression`, with `language`
   as `text/cql-identifier`, `condition.expression.reference` should also
   refer to the canonical URL of the Libaray.

2. **Rules → nested action structure.** Each `sections.rules[]` entry
   (condition→action mapping) becomes one top-level `PlanDefinition.action`.
   The rule's condition set maps to `action.condition[]` and the resulting
   actions map to `action.action[]` (nested children). Multi-branch rules
   (if/else-if/else) produce sibling actions at the same nesting level, each
   with mutually exclusive applicability conditions.

3. **Inline vs. Library expressions.** Use inline FHIRPath when:
   - The condition is a single comparison or simple boolean (≤ 2 clauses)
   - No calculated intermediate value is needed

   Extract to a separate Library (CQL) when:
   - The condition involves a calculated score, aggregation, or date arithmetic
   - The same logic is reused across 2+ actions
   - Nesting depth exceeds 3 levels

4. **Exception / override rules.** Map `sections.exceptions[]` to
   `PlanDefinition.action` entries with `condition.kind: applicability` that
   negate the parent rule's condition. Place exception actions *before* the
   standard rule actions in the action list so they short-circuit evaluation.
   Use `action.priority: routine | urgent | stat` to signal override severity.

5. **Deep nesting (5+ levels).** Flatten to a maximum of 4 action nesting
   levels. Any condition chain deeper than 4 gets refactored: extract the
   inner conditions into a Library CQL `define` statement and reference it
   from a single action.condition at the appropriate level.

6. **Dynamic Values** If the logic is intended to modify a property of the
   resulting request resource, use `action.dynamicValue` with either a
   FHIRPath expression or CQL expression. The parameters to the $apply 
   operation are available within dynamicValue CQL and FHIRPath expressions 
   as context variables, accessible by the name of the parameter prefixed with 
   a percent (%) symbol. For example, to access the subject given to the apply, 
   use the expression %subject. The value of the %subject context variable in 
   a dynamicValue expression is determined using the current subject, as 
   specified by the subject element on the PlanDefinition, current 
   PlanDefinition.action, or ActivityDefinition.

   In addition to the $apply operation parameters, the context variable %action can be used within the path element of a dynamicValue to specify the current action target. For example, to specify the path to the description element of the current action, use %action.description.

### MCP Usage

- `reasonhub-search_loinc` — resolve observable/lab conditions
- `reasonhub-search_snomed` — resolve clinical finding conditions
- `reasonhub-search_rxnorm` — resolve medication actions

### Resolved Decisions

- **Nesting depth / CQL flattening**: 4 levels is the hard limit. Complex trees
  (e.g., sepsis management) should break nested logic into named Library CQL
  `define` statements at depth 3, then reference from the PlanDefinition action.
- **Override rules**: Use `action.priority = routine|urgent|asap|stat` plus
  `action.condition` with `kind = stop` for overrides. Do not use a separate
  `action.type` — keep overrides as high-priority conditions within the same tree.
- **Large decision tables (>20 rules)**: Stay as actions within one PlanDefinition
  for v1. Group related rules under `action.action` sub-groups. Splitting into
  separate PlanDefinitions deferred to v2 when clinical consensus on grouping exists.

---

## 3. care-pathway → PlanDefinition (Clinical Protocol)

### L2 Input Shape

```yaml
artifact_type: care-pathway
sections:
  steps: [...]         # ordered clinical steps
  triggers: [...]      # initiation criteria
  milestones: [...]    # checkpoint / gate criteria
  branches: [...]      # conditional forks in the pathway
```

### L3 Output

- **PlanDefinition** (type: `clinical-protocol`): Primary resource with
  ordered `action[]` representing the care sequence. Each action may have
  `relatedAction[]` for ordering constraints and `condition[]` for branching.
  The leaf-nodes of `PlanDefinition.action` should be `definitionCanonical`
  references to ECA rules (see above).

### Conversion Rules

1. **Steps → ordered PlanDefinition.action[].** Each `sections.steps[]` entry
   becomes one `PlanDefinition.action`. Ordering is expressed via
   `action.relatedAction[]` with `relationship: before-start` linking each
   step to its successor. The step's `id` becomes `action.id`; the step's
   title and description map to `action.title` and `action.description`.

2. **Triggers → action.trigger.** Each `sections.triggers[]` entry becomes a
   `PlanDefinition.action.trigger` on the first action in the pathway.
   Use `trigger.type: named-event` for clinical events (e.g., "patient
   admitted") and `trigger.type: periodic` for time-based initiations.
   Encode the trigger condition as a FHIRPath `trigger.condition.expression`.

3. **Milestones → gate conditions.** Each `sections.milestones[]` entry
   becomes an action with `action.condition[].kind: applicability` that gates
   progression to the next step. The milestone action produces no clinical
   output but must evaluate to true before downstream actions fire. Represent
   milestones as `action.type: create` with a documentation output that names
   the gate criterion.

4. **Conditional branches.** Each `sections.branches[]` fork produces a
   group action containing child actions with mutually exclusive
   `condition.kind: applicability` expressions. The group action has
   `groupingBehavior: logical-group` and `selectionBehavior: exactly-one`
   (if/else) or `selectionBehavior: any` (parallel branches).

5. **ActivityDefinition extraction.** Promote a step to its own
   ActivityDefinition (referenced via `action.definitionCanonical`) when:
   - The step is reused in 2+ pathways within the same topic
   - The step carries standalone order semantics (lab order, medication order)
   - The step's detail exceeds what fits cleanly in an inline action

   Otherwise keep the step as an inline `PlanDefinition.action`.

6. **Timed constraints.** Map time-bound steps ("within 1 hour") to
   `action.relatedAction[].offsetDuration` using UCUM time units
   (e.g., `{value: 1, unit: "h", system: "http://unitsofmeasure.org"}`).
   When the timing is a range ("1–3 hours"), use `offsetRange` instead.

### MCP Usage

- `reasonhub-search_snomed` — resolve procedure and assessment codes
- `reasonhub-search_loinc` — resolve lab order codes in pathway steps

### Resolved Decisions

- **Parallel branches**: Use `selectionBehavior: all` on a group action. This
  is semantically clearer than sibling actions with no ordering and aligns with
  CPG-on-FHIR patterns for concurrent interventions.
- **Timed constraints**: Use `relatedAction.offsetDuration` for step-to-step
  delays. For recurring activities (e.g., "every 4 hours"), use `timingTiming`
  on the action with `repeat.period` / `repeat.periodUnit`.
- **External protocol references**: Use `definitionCanonical` pointing to the
  external PlanDefinition URL. If the URL is not yet published, create a
  placeholder action with `description` and a `_review_note` flagging the
  external dependency.

---

## 4. terminology → ValueSet + ConceptMap

### L2 Input Shape

```yaml
artifact_type: terminology
sections:
  value_sets:
    - name: ...
      system: ...
      codes: [...]        # concept codes with displays
  concept_maps:
    - source_system: ...
      target_system: ...
      mappings: [...]     # source→target equivalences
```

### L3 Output

- **ValueSet**: One per `value_sets[]` entry. Contains `compose.include[]`
  with system and concept entries. Hierarchical sets use filter expressions
  (e.g., `is-a` for SNOMED descendants).
- **ConceptMap**: One per `concept_maps[]` entry. Contains `group[].element[]`
  with source/target mappings and equivalence annotations.

### Conversion Rules

1. **Candidate code carry-forward.** If the approved extract plan contains
   `candidate_codes[]` for the corresponding `terminology-value-sets` artifact,
   those codes are the authoritative starting set. Each entry's `code`,
   `system`, and `display` map directly to `ValueSet.compose.include[].concept[]`.
   Invoke MCP search only to fill gaps where the extract set is incomplete
   (missing codes for known concepts or codes flagged `needs-review`).

2. **Intensional vs. extensional ValueSets.** Use intensional (filter-based)
   when:
   - The value set is defined as "all descendants of concept X" (e.g., all
     SNOMED children of Diabetes mellitus 73211009)
   - The concept hierarchy has >20 leaf codes
   - The source definition uses language like "including subtypes"

   Express as `compose.include[].filter[]` with `op: is-a` and the parent
   concept.  Call `reasonhub-valueset_expand` to inline-expand and verify
   the hierarchy during implement.

   Use extensional (enumerated) when:
   - The value set is a curated list of specific codes (<20 codes or
     cherry-picked from different branches)
   - Codes span multiple systems in one value set

3. **ConceptMap equivalence.** For each `sections.concept_maps[].mappings[]`
   entry, determine the FHIR equivalence level:
   - Source and target mean exactly the same thing → `equivalent`
   - Target is broader than source → `wider`
   - Target is narrower than source → `narrower`
   - Concepts overlap but neither subsumes the other → `inexact`
   - No reasonable target exists → `unmatched`

   When the source data does not specify equivalence, default to `equivalent`
   for same-hierarchy mappings (confirmed via `reasonhub-codesystem_lookup`)
   and `inexact` for cross-system mappings, flagging both for reviewer
   verification.

4. **Unresolved / ambiguous codes.** When MCP search returns multiple
   candidates for a single concept:
   - If one candidate has an exact display-name match, select it
   - If multiple candidates are equally plausible, include all in the value
     set and add a `_review_note` comment listing the ambiguity
   - Never silently drop an ambiguous code; surface it for reviewer resolution

5. **L3 output files.** Each L2 terminology artifact produces individual
   FHIR JSON files: `ValueSet-<id>.json` for each value set and
   `ConceptMap-<id>.json` for each concept map. All are placed in the
   topic's computable directory and referenced by the ImplementationGuide
   resource during packaging.

### MCP Usage

- `reasonhub-search_*` — resolve all code references
- `reasonhub-codesystem_lookup` — confirm canonical display for each code
- `reasonhub-valueset_expand` — expand hierarchical sets (e.g., SNOMED descendants)
- `reasonhub-codesystem_verify_code` — validate every code in verify mode

### Resolved Decisions

- **Minimum code count**: ≥2 codes from the same system. Single-code references
  are inlined as direct `Coding` in the consuming resource (no standalone ValueSet).
- **Ambiguous MCP matches**: Always surface for reviewer resolution when no exact
  display-name match exists. Never auto-pick. Include top 3 candidates in a
  `_review_note` for the reviewer to select from.
- **Cross-system value sets**: One ValueSet with multiple `compose.include[]`
  entries for v1 (simplest for consumers). Each `include` has its own `system`
  and `version`. Splitting deferred unless a consuming resource requires
  system-specific filtering.

---

## 5. measure → Measure

### L2 Input Shape

```yaml
artifact_type: measure
sections:
  populations:
    initial_population: ...
    denominator: ...
    numerator: ...
    denominator_exclusions: ...
    denominator_exceptions: ...
  scoring: ...            # proportion | ratio | continuous-variable
  improvement_notation: ... # increase | decrease
  stratifiers: [...]      # optional sub-group dimensions
```

### L3 Output

- **Measure**: One resource with `group[].population[]` entries mapping to
  initial population, denominator, numerator, exclusions, exceptions.
  `scoring` maps to `Measure.scoring`. Each population references a Library
  expression.
- **Library**: CQL expressions defining each population criterion.

### Conversion Rules

1. **Populations → Measure.group[].population[].** Map each population key to
   a FHIR population entry:
   - `initial_population` → population with `code: initial-population`
   - `denominator` → population with `code: denominator`
   - `numerator` → population with `code: numerator`
   - `denominator_exclusions` → population with `code: denominator-exclusion`
   - `denominator_exceptions` → population with `code: denominator-exception`

   Each population entry references a Library CQL expression via
   `criteria.expression` (e.g., `"InitialPopulation"`).

2. **Scoring type.** Map `sections.scoring` directly to `Measure.scoring`:
   - `proportion` → `Measure.scoring.code = proportion`
   - `ratio` → `Measure.scoring.code = ratio`
   - `continuous-variable` → `Measure.scoring.code = continuous-variable`

   Map `sections.improvement_notation` to
   `Measure.improvementNotation.code` (`increase` or `decrease`).

3. **Stratifiers.** Each `sections.stratifiers[]` entry becomes a
   `Measure.group[].stratifier` with a CQL expression defining the
   stratification dimension (e.g., age band, ethnicity). The stratifier
   `criteria.expression` references a Library `define` statement.

4. **Minimum viable Library CQL.** For each population, generate a CQL
   `define` statement that captures the population logic as a boolean
   expression. Minimum structure:
   ```cql
   library <TopicSlug>Measure version '1.0.0'
   using FHIR version '4.0.1'
   define "InitialPopulation": <boolean expression>
   define "Denominator": <boolean expression>
   define "Numerator": <boolean expression>
   ```
   If the L2 population definitions are natural-language-only and cannot be
   mechanically translated, generate pseudocode stubs with `// TODO: refine`
   comments and flag for reviewer completion.

5. **Composite measures.** When the L2 artifact defines multiple measure
   groups (e.g., separate quality domains), each group becomes a separate
   `Measure.group[]` entry with its own population set. All groups share
   the same Library resource but reference different `define` statements.

6. **L3 output files.** The Measure resource is written as
   `Measure-<id>.json`. The companion Library containing CQL population
   definitions is written as `Library-<id>.json` with the CQL source
   attached as a `content[]` attachment (base64 or inline). Both are placed
   in the topic's computable directory.

### MCP Usage

- `reasonhub-search_snomed` / `reasonhub-search_loinc` — resolve diagnosis
  and observation criteria in population definitions
- `reasonhub-search_icd10` — resolve billing/diagnosis codes for denominator criteria

### Resolved Decisions

- **CQL generation**: Generate compilable CQL when the L2 definition has
  structured criteria (conditions with explicit values). Leave as pseudocode
  stubs with `// TODO: refine` only when the L2 is purely narrative.
- **Composite measures / mixed scoring**: Split into separate Measure resources.
  FHIR `Measure.scoring` is singular; mixing scoring types in one resource
  violates the spec. Link related Measures via `relatedArtifact`.
- **Supplemental data**: Use `Measure.supplementalData[]` entries that reference
  Library `define` statements. This keeps the Measure self-documenting while
  the Library holds the actual retrieval logic.

---

## 6. assessment → Questionnaire

### L2 Input Shape

```yaml
artifact_type: assessment
sections:
  items:
    - text: ...
      type: ...          # choice | boolean | integer | string | group
      required: ...
      options: [...]     # answer choices with scores
      enable_when: ...   # conditional display logic
  scoring:
    method: ...          # sum | weighted | algorithm
    ranges: [...]        # interpretation bands
```

### L3 Output

- **Questionnaire**: One resource with `item[]` entries. Each item has
  `type`, `answerOption[]` (from options), `enableWhen[]` (conditional logic),
  and `extension[]` for scoring weights.
- **QuestionnaireResponse** (optional): Example completed response for
  validation/testing.

### Conversion Rules

1. **Items → Questionnaire.item[] with linkId.** Each `sections.items[]`
   entry becomes one `Questionnaire.item`. Generate `linkId` as a stable,
   sequential identifier: `q1`, `q2`, … for top-level items; `q1.1`, `q1.2`
   for nested sub-items. Map `text` → `item.text`, `type` → `item.type`
   (FHIR types: `choice`, `boolean`, `integer`, `string`, `group`),
   `required` → `item.required`.

2. **Answer options with scores.** Each `options[]` entry becomes an
   `item.answerOption` with `valueCoding.display` set to the option text.
   Attach scoring weights using the SDC `ordinalValue` extension:
   ```json
   {
     "url": "http://hl7.org/fhir/StructureDefinition/ordinalValue",
     "valueDecimal": <score>
   }
   ```
   If options have no score, omit the extension.

3. **enableWhen conditional logic.** Map each `enable_when` entry to
   `item.enableWhen[]` with:
   - `question` → the `linkId` of the referenced item
   - `operator` → FHIR operator (`=`, `!=`, `>`, `<`, `>=`, `<=`, `exists`)
   - `answer[x]` → the triggering value

   When multiple enable_when conditions exist on one item, set
   `item.enableBehavior` to `all` (AND) or `any` (OR) based on the L2 logic.

4. **Group / nested items.** Items with `type: group` become container
   `Questionnaire.item` entries with their own `item[]` children. Nesting
   depth follows the L2 structure. If nesting exceeds 4 levels, flatten
   inner groups to the 4th level with prefixed text labels.

5. **Scoring method.** Capture the `sections.scoring.method` using the SDC
   `questionnaire-scoring` extension on the root Questionnaire:
   - `sum` → `scoring.code = sum` (add all ordinalValues)
   - `weighted` → `scoring.code = weighted` (multiply by item weight)
   - `algorithm` → `scoring.code = algorithm` with a reference to a
     Library expression containing the custom logic

   Map `sections.scoring.ranges[]` to an extension array encoding
   interpretation bands (e.g., 0–4 = minimal, 5–9 = mild).

6. **QuestionnaireResponse example.** Generate an example response when:
   - The assessment has ≤ 20 items (manageable example size)
   - Scoring ranges are defined (example demonstrates score calculation)

   The example populates each item with a representative answer and includes
   a calculated total score. Mark as `status: completed`.

7. **L3 output files.** The Questionnaire is written as
   `Questionnaire-<id>.json`. If a custom scoring Library is generated,
   it is written as `Library-<id>.json`. An optional example
   `QuestionnaireResponse-<id>-example.json` may be included for
   validated instruments. All are placed in the topic's computable
   directory.

### MCP Usage

- `reasonhub-search_loinc` — resolve LOINC panel and question codes (e.g., PHQ-9)
- `reasonhub-codesystem_lookup` — confirm item-level LOINC codes

### Resolved Decisions

- **Scoring ranges**: Descriptive metadata on Questionnaire extensions for v1.
  Use `ordinalValue` on answer options and a `_scoring_interpretation` extension
  with min/max/label triples. Library CQL scoring deferred to v2 for validated
  instruments (e.g., PHQ-9).
- **Adaptive assessments**: Flag as "requires SDC Adaptive Questionnaire profile"
  in the `_review_note`. Generate a standard Questionnaire with all items; adaptive
  item-selection logic is out of scope for v1.
- **Branching scoring paths**: Generate one scoring range interpretation covering
  the maximum possible score. Add `_review_note` documenting skip-pattern impact
  on scoring. Per-path scoring deferred to v2.

---

## 7. policy → PlanDefinition (Payer)

### L2 Input Shape

```yaml
artifact_type: policy
sections:
  criteria: [...]       # coverage/eligibility conditions
  actions: [...]        # approve | deny | pend | request-info
  documentation: [...]  # required supporting documentation
  exceptions: [...]     # override conditions
  appeal_process: ...   # escalation pathway
```

### L3 Output

- **PlanDefinition** (type: `eca-rule`): Primary resource with `action[]`
  for each coverage decision pathway. Each action has `condition[]`
  (applicability criteria) and `output[]` or nested actions for the decision
  (approve/deny/pend).
- **Questionnaire** (optional): One per documentation requirement group that
  collects structured information from the provider. Follows the
  [Da Vinci DTR](https://hl7.org/fhir/us/davinci-dtr/) pattern with
  CQL-backed `initialExpression` extensions for EHR pre-population, per the
  [CQL Questionnaire Support](https://confluence.hl7.org/spaces/DVP/pages/248713571/CQL+Questionnaire+Support)
  project and the
  [Common CQL Artifacts for FHIR (US)](https://build.fhir.org/ig/HL7/us-cql-ig/en/)
  IG.
- **Library** (optional): CQL expressions that supply `initialExpression`
  values for Questionnaire items by querying US Core profiles (Patient,
  Condition, Observation, MedicationRequest, ServiceRequest, Coverage, etc.).


### Conversion Rules

1. **Criteria → action.condition (applicability).** Each
   `sections.criteria[]` entry becomes a `PlanDefinition.action` with
   `condition[].kind: applicability`. Express eligibility criteria as
   FHIRPath expressions in `condition.expression`. Group related criteria
   (e.g., diagnosis + procedure + timeframe) under a single action with
   multiple conditions joined by implicit AND.

2. **Decision outcomes as action types.** Map `sections.actions[]` to
   nested `PlanDefinition.action` children under each criterion action:
   - `approve` → action with `type.code = create` (authorize the service)
   - `deny` → action with `type.code = remove` and `action.documentation`
      linking to the denial reason
   - `pend` → action with `type.code = update` and
     `action.relatedAction[]` pointing to a "request additional info" step
   - `request-info` → action with `type.code = collect-information` and
      `action.input[]` listing required documentation items

3. **Required documentation.** Map `sections.documentation[]` to
   `action.input[]` entries on the relevant criterion action. Each input
   has `type` (e.g., DocumentReference, DiagnosticReport), a
   `profile` reference if available, and human-readable `requirement` text.
   This makes documentation requirements machine-queryable for prior-auth
   automation.

4. **Documentation Questionnaires (DTR pattern).** When
   `sections.documentation[]` entries describe information that must be
   collected from the provider or attested (rather than simply attached),
   generate one or more **Questionnaire** resources following the Da Vinci
   Documentation Templates and Rules (DTR) pattern:

   a. **Item generation.** Each documentation requirement that asks for a
      discrete data element (diagnosis date, lab result, clinical
      justification, etc.) becomes a `Questionnaire.item` with appropriate
      `type` (`choice`, `string`, `date`, `boolean`, `attachment`, `group`).
      Use `linkId` generation rules from §6.1 (sequential `q1`, `q2`, …).

   b. **CQL pre-population via `initialExpression` (v2 scope).** For v1,
      generate Questionnaire items **without** `initialExpression`
      extensions — all items require manual completion. In v2, for each
      item where the answer can be sourced from the EHR, attach an SDC
      [`initialExpression`](http://hl7.org/fhir/uv/sdc/StructureDefinition-sdc-questionnaire-initialExpression.html)
      extension whose `valueExpression.language` is `text/cql-identifier`
      and whose `valueExpression.expression` references a `define` statement
      in a companion Library. Use the
      [US CQL Common](https://build.fhir.org/ig/HL7/us-cql-ig/en/Library-USCoreCommon.html)
      and
      [US Core Elements](https://build.fhir.org/ig/HL7/us-cql-ig/en/Library-USCoreElements.html)
      authoring patterns where applicable:
      - Patient demographics → `USCoreElements` Patient patterns
      - Active conditions/diagnoses → `USCoreElements` Condition patterns
      - Lab results → `USCoreElements` Observation Lab patterns
      - Current medications → `USCoreElements` Medication patterns
      - Coverage details → `USCoreElements` Coverage patterns
      - Requesting provider → `USCoreElements` Practitioner/ServiceRequest patterns

   c. **Companion Library (v2 scope).** In v2, generate a Library resource containing CQL
      `define` statements for each pre-populatable item. Minimum structure:
      ```cql
      library <TopicSlug>DocQuestions version '1.0.0'
      using FHIR version '4.0.1'
      include USCoreCommon version '2.0.0' called UC
      include USCoreElements version '2.0.0' called UCE

      define "PatientName": UCE."Patient Name"
      define "ActiveDiagnoses": UCE."Active Conditions"
      // ... one define per pre-populated item
      ```

   d. **Non-pre-populatable items.** Documentation items that require
      provider attestation, free-text clinical justification, or attached
      documents (e.g., operative notes, pathology reports) become
      Questionnaire items **without** an `initialExpression`. These items
      remain blank for manual completion.

   e. **Linking to PlanDefinition.** Reference each Questionnaire from the
      `request-info` or `pend` action via
      `action.definitionCanonical` pointing to the Questionnaire's canonical
      URL. This connects the coverage decision logic to the documentation
      collection workflow.

   f. **When to generate.** Generate documentation Questionnaires when:
      - `sections.documentation[]` has ≥2 discrete data collection items
      - The policy explicitly requires structured data capture (not just
        document attachment)
      - The documentation maps to EHR-queryable US Core profiles

      Skip Questionnaire generation when documentation is purely
      attachment-based (e.g., "attach operative notes") — use plain
      `action.input[]` with `type: DocumentReference` instead.

5. **Exception / override rules.** Map `sections.exceptions[]` using the
   same pattern as decision-table (§2.4): exception actions precede the
   standard criterion actions, with negated applicability conditions that
   short-circuit the deny/pend pathway. Add `action.priority: stat` for
   medical-necessity overrides.

6. **Appeal process.** When `sections.appeal_process` is present, model it
   as a related `PlanDefinition.action` chain appended after the primary
   decision actions:
   - Step 1: "Submit Appeal" (collect-information)
   - Step 2: "Peer Review" (action with condition gating on appeal status)
   - Step 3: "Final Determination" (approve or deny)

   Link appeal steps to the denial action via
   `relatedAction[].relationship: after` so the appeal pathway only
   activates after a deny outcome. If the appeal process is a multi-step
   flow with external review, flag it for a separate PlanDefinition
   and reference it via `action.definitionCanonical`.

### MCP Usage

- `reasonhub-search_snomed` — resolve clinical criteria (diagnosis, procedure)
- `reasonhub-search_icd10` — resolve coverage diagnosis codes
- `reasonhub-search_loinc` — resolve required lab/test documentation and
  Questionnaire item codes for pre-population mappings

### Resolved Decisions

- **Prior-auth decision outcomes**: Use X12 278 response codes where available
  (A1=certified, A2=modified, A3=not certified, A4=pended, A6=cancelled). Fall
  back to descriptive text with a `_review_note` for non-standard workflows.
- **Multi-step prior auth**: Separate PlanDefinitions when the appeal flow has
  ≥3 steps. Link via `relatedArtifact` with `type = depends-on`. Single-step
  appeals stay inline as a final action.
- **Time-limited authorizations**: Use `action.timingDuration` for the authorized
  period. Add a reauthorization action triggered by `relatedAction` with
  `relationship = after` and `offsetDuration` matching the authorization period.
- **Missing US CQL Common patterns**: Author a custom CQL `define` in the
  project-level shared library with a `// CANDIDATE: propose to <IG>` comment.
  Leave `initialExpression` empty with a `// TODO` only when the concept itself
  is undefined (not just the pattern).
- **Documentation Questionnaire versioning**: Version independently from the
  parent PlanDefinition. Use `relatedArtifact` with `type = composed-of` and
  explicit version references to maintain bundle coherence.

---

## Cross-Cutting Concerns

### Terminology Resolution Pattern (all strategies)

Every strategy that produces coded FHIR resources follows the same resolution flow:

1. Carry forward `candidate_codes[]` from extract plan (authoritative starting set)
2. Use `reasonhub-search_*` to fill gaps where extract codes are incomplete
3. Confirm every code with `reasonhub-codesystem_lookup` (canonical display)
4. In verify mode, validate every code with `reasonhub-codesystem_verify_code`

### L3 Output Model

The L3 output is a **FHIR Package** following NPM conventions:

```
topics/<topic>/computable/
  <resource-type>-<id>.json   # individual FHIR JSON resources
  <library-name>.cql          # CQL source files
```

After individual resources are generated, `rh-skills package <topic>` bundles
them into a distributable FHIR package:

```
topics/<topic>/package/
  package.json                 # FHIR package manifest (NPM conventions)
  ImplementationGuide-<id>.json
  PlanDefinition-<id>.json
  ValueSet-<id>.json
  Library-<id>.json
  ...
```

**CLI commands:**

| Command | Purpose |
|---------|---------|
| `rh-skills formalize <topic> <artifact>` | Generate individual FHIR JSON + CQL from an approved L2 artifact |
| `rh-skills package <topic>` | Bundle all computable resources into a FHIR package |

### Convergence (multi-input formalize)

When a formalize plan selects **multiple** L2 artifacts as inputs:

- Each L2 input maps to its strategy independently via
  `rh-skills formalize <topic> <artifact>`
- The `rh-skills package <topic>` command bundles all generated resources
  into one FHIR package with an ImplementationGuide
- Overlap detection rules: if two inputs produce the same FHIR resource type,
  the plan must specify merge precedence or flag for reviewer resolution

### Resource Identity

All generated FHIR resources use:
- `id`: derived from topic slug + artifact name
- `url`: canonical URL pattern `urn:rh-skills:<topic>/<resource-type>/<name>`
- `version`: matches the formalize plan version
- `status`: `draft` until verified

### Case Feature Definitions (v2 Scope)

> **v1 approach:** Use plain `Library.dataRequirement` entries without
> profile references. Case feature StructureDefinitions are deferred to v2.

Every clinical concept that appears in CQL logic — whether as a retrieve,
a condition test, or a population criterion — SHOULD have a corresponding
**case feature definition**. A case feature definition is a FHIR
StructureDefinition (profile) that describes the shape of the data the
logic expects.

**Why:** Case features make data requirements explicit and testable. They
also enable `Library.dataRequirement` entries that tell implementers
exactly what data a Library needs, what profiles it expects, and what
value set filters it applies — without reading the CQL source.

#### Profile Selection

Most case features are **Observation profiles**, but the base resource
depends on the clinical concept:

| Concept Kind | Base Resource | Example |
|-------------|---------------|---------|
| Lab result, vital sign, screen score | Observation | HbA1c, BMI, PHQ-9 total score |
| Patient-reported / clinician-assessed risk | Observation | Fall risk, Braden score |
| Diagnosis or problem | Condition | Active diabetes, CKD stage |
| Treatment target | Goal | HbA1c target < 7%, BP target < 130/80 |
| Medication exposure | MedicationStatement / MedicationRequest | Statin use, insulin regimen |
| Procedure history | Procedure | Colonoscopy, joint replacement |

#### Reuse Existing Profiles First

Before authoring a new profile, check for an existing published profile
that already constrains the concept:

| Domain | IG / Package | Example Profiles |
|--------|-------------|-----------------|
| General vitals & labs | [US Core](http://hl7.org/fhir/us/core) | US Core Vital Signs, US Core Laboratory Result Observation |
| Quality improvement | [QI-Core](http://hl7.org/fhir/us/qicore) | QICore Observation, QICore Condition, QICore Procedure |
| Oncology | [mCODE](http://hl7.org/fhir/us/mcode) | Tumor Size, Cancer Stage Group, TNM categories |
| Cardiovascular | [CIMI / CardX](http://hl7.org/fhir/us/cardx-htn) | Average Blood Pressure |
| Behavioral health | [US Behavioral Health Profiles](http://hl7.org/fhir/us/behavioral-health) | PHQ-9, AUDIT-C |

When an existing profile fits, the case feature definition is simply a
reference to that profile's canonical URL — no new StructureDefinition is
needed.

#### Authoring New Profiles

When no published profile covers the concept, author a minimal
StructureDefinition that:

1. Derives from the appropriate base (`Observation`, `Condition`, `Goal`, etc.)
2. Constrains `code` to a single concept or a value set binding
3. Constrains `value[x]` type and units where applicable
4. Sets `status` to `draft`

```yaml
# L3 case feature definition — new profile
case_features:
  - id: hba1c-observation
    base: Observation
    title: "HbA1c Observation"
    code:
      system: http://loinc.org
      code: "4548-4"
      display: "Hemoglobin A1c/Hemoglobin.total in Blood"
    value_type: Quantity
    value_units: "%"
    profile_url: "urn:rh-skills:<topic>/StructureDefinition/hba1c-observation"
    source_profile: null   # no existing profile — new

  - id: us-core-bmi
    base: Observation
    title: "BMI (US Core)"
    profile_url: "http://hl7.org/fhir/us/core/StructureDefinition/us-core-bmi"
    source_profile: "http://hl7.org/fhir/us/core/StructureDefinition/us-core-bmi"  # reuse
```

#### Linking to Library.dataRequirement

Every CQL `define` that retrieves patient data generates a
`Library.dataRequirement` entry. The case feature definition governs what
appears there:

```yaml
libraries:
  - id: diabetes-screening-logic
    # ...
    data_requirements:
      - type: Observation
        profile: "urn:rh-skills:diabetes-screening/StructureDefinition/hba1c-observation"
        code_filter:
          path: code
          value_set: "http://example.org/fhir/ValueSet/hba1c-codes"
      - type: Condition
        profile: "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition-problems-health-concerns"
        code_filter:
          path: code
          value_set: "http://example.org/fhir/ValueSet/diabetes-dx"
```

**Rules:**

1. Every retrieve (`[Resource: "ValueSet"]`) in CQL produces exactly one
   `dataRequirement` entry.
2. If a case feature definition exists for the concept, use its
   `profile_url` in `dataRequirement.profile[]`.
3. If the retrieve filters by value set, include a `codeFilter` with the
   value set canonical URL.
4. During verify mode, confirm that every `dataRequirement.profile` either
   resolves to a published IG or exists in the topic's `case_features[]`.

### FHIR Package Dependencies

Every L3 computable package has FHIR IG dependencies that must be
declared explicitly. Dependencies fall into two categories:

#### Modeling Dependencies (data profiles)

These IGs define the StructureDefinitions, value sets, and code systems
that the computable artifact's case features and CQL logic reference:

| Package | Canonical | When to Include |
|---------|----------|-----------------|
| **US Core** | `hl7.fhir.us.core` | Almost always — base US patient data profiles |
| **QI-Core** | `hl7.fhir.us.qicore` | When generating Measures (§5) or when using QI-Core negation profiles |
| **mCODE** | `hl7.fhir.us.mcode` | Oncology topics — tumor staging, cancer conditions, genomics |
| **C-CDA on FHIR** | `hl7.fhir.us.ccda` | When ingesting/referencing C-CDA documents |
| Domain-specific IGs | varies | e.g., CardX for hypertension, Gravity for SDOH, Dental for oral health |

#### Specification Dependencies (conformance rules)

These IGs define the patterns, extensions, and conformance expectations
the generated artifacts follow:

| Package | Canonical | When to Include |
|---------|----------|-----------------|
| **Using CQL With FHIR** | `hl7.fhir.uv.cql` | Any artifact with CQL Library resources (§2, §5, §7) |
| **CRMI** | `hl7.fhir.uv.crmi` | All artifacts — canonical resource management, versioning, packaging |
| **CPG** | `hl7.fhir.uv.cpg` | Care pathways (§3), decision-tables (§2) — clinical guidelines patterns |
| **CQM** | `hl7.fhir.us.cqfmeasures` | Quality measures (§5) — measure conformance and reporting |
| **SDC** | `hl7.fhir.uv.sdc` | Assessments (§6) and DTR questionnaires (§7) — advanced form extensions |
| **CRD** | `hl7.fhir.us.davinci-crd` | Prior auth / coverage policies (§7) — coverage requirements discovery |
| **DTR** | `hl7.fhir.us.davinci-dtr` | Prior auth / coverage policies (§7) — documentation templates & rules |
| **PAS** | `hl7.fhir.us.davinci-pas` | Prior auth (§7) — prior authorization support exchange |

#### Declaring Dependencies

Record dependencies in the L3 computable artifact metadata so that
downstream tooling (FHIR IG Publisher, SUSHI, validators) can resolve them:

```yaml
metadata:
  id: diabetes-screening-computable
  # ... other metadata ...
  fhir_version: "4.0.1"
  dependencies:
    # Modeling
    - package: hl7.fhir.us.core
      version: "7.0.0"
      purpose: modeling    # data profiles for patient data retrieval
    # Specification
    - package: hl7.fhir.uv.cql
      version: "2.0.0"
      purpose: specification  # CQL authoring conformance
    - package: hl7.fhir.uv.cpg
      version: "2.0.0"
      purpose: specification  # clinical guidelines patterns
    # Domain-specific
    - package: hl7.fhir.us.mcode
      version: "4.0.0"
      purpose: modeling    # only when topic is oncology
```

**Rules:**

1. Every L3 package SHALL declare at least one modeling dependency (US Core
   at minimum) and one specification dependency (CRMI at minimum).
2. Add the Using CQL With FHIR (`hl7.fhir.uv.cql`) dependency whenever the
   package contains ≥1 Library with CQL content.
3. Add CPG (`hl7.fhir.uv.cpg`) whenever the package contains PlanDefinition
   or ActivityDefinition resources.
4. Add CQM (`hl7.fhir.us.cqfmeasures`) whenever the package contains
   Measure resources.
5. Add SDC (`hl7.fhir.uv.sdc`) whenever the package contains Questionnaire
   resources with advanced extensions (`initialExpression`, `calculatedExpression`,
   `enableWhenExpression`, scoring).
6. Add DTR + CRD + PAS when the topic is a payer policy with prior auth
   requirements (§7).
7. Domain-specific modeling IGs (mCODE, CardX, etc.) are added only when
   the topic's case features reference profiles from those IGs.
8. Pin dependency versions explicitly — never use `current` or `latest`.
   Prefer the most recent published (non-ballot) version.

---

## CQL Authoring Guidance

> Reference: [Using CQL With FHIR IG](https://build.fhir.org/ig/HL7/cql-ig/en/index.html)
> (hl7.fhir.uv.cql v2.1.0)

Strategies §2 (decision-table), §5 (measure), and §7 (policy) all produce
Library resources containing CQL. This section establishes authoring
conventions that apply across all three. The guiding principle is
**simple CQL with composability**: keep individual expressions small and
single-purpose, then compose complex logic from those building blocks
via library includes.

### Library Structure

Every generated CQL library follows this skeleton:

```cql
library <TopicSlug><Purpose> version '1.0.0'

using FHIR version '4.0.1'

include FHIRHelpers version '4.0.1'
include FHIRCommon called FC

// ── Terminology ──────────────────────────────
codesystem "SNOMED CT": 'http://snomed.info/sct'
codesystem "LOINC":     'http://loinc.org'

valueset "Diabetes Diagnoses": 'http://example.org/fhir/ValueSet/diabetes-dx'

code "HbA1c": '4548-4' from "LOINC" display 'Hemoglobin A1c/Hemoglobin.total in Blood'

// ── Definitions ──────────────────────────────
define "Active Diabetes":
  [Condition: "Diabetes Diagnoses"] C
    where C.clinicalStatus ~ FC."active"
```

Conformance rules (derived from the Using CQL With FHIR IG):

| Element | Convention | Reference |
|---------|-----------|-----------|
| Library name | PascalCase, alphanumeric only — no underscores | CR 2.1 |
| Library version | Semantic Versioning (`major.minor.patch`) | CR 2.2 |
| `include` aliases | Use a `called` clause; alias SHOULD be consistent across libraries | CR 2.3 |
| Data model | `using FHIR version '4.0.1'` — always include version | CR 2.5 |
| Code system URIs | Canonical URLs from HL7 Terminology (THO) | CR 2.6 |
| Value set URIs | Canonical URLs; local identifier SHOULD match the value set title | CR 2.7 |
| Direct-reference codes | Logical identifier is the code value, not a URI; local identifier is the display | CR 2.11 |
| Expression names | Initial Case with spaces (e.g., `"Blood Pressure Observations Within 30 Days"`) | CR 2.13 |
| Aliases | PascalCase, descriptive — no abbreviations | CR 2.16 |
| UCUM units | Use `Quantity` literals (`90 'mm[Hg]'`), not code declarations | §2.6 |

### Composability via Includes

Complex logic SHOULD be decomposed into **layered libraries** with narrow
responsibilities, then composed via `include`. This keeps each library
auditable and reusable across topics.

**Layer pattern:**

```text
┌─────────────────────────────┐
│  Topic-specific Library     │  ← one per L2 artifact
│  (e.g., DiabetesScreening)  │
├─────────────────────────────┤
│  Shared domain library      │  ← reusable across topics
│  (e.g., LabCommon)          │
├─────────────────────────────┤
│  FHIRCommon / FHIRHelpers   │  ← IG-standard foundations
└─────────────────────────────┘
```

Rules:

1. **One primary Library per FHIR artifact.** All CQL expression references
   from a given PlanDefinition, Measure, or Questionnaire SHOULD resolve to
   a single library (CR 2.3). If an artifact references expressions from
   multiple libraries, all expression references SHALL be qualified
   (`LibraryAlias."Expression Name"`).

2. **FHIRHelpers is always included.** Required for implicit FHIR primitive
   conversions. Include with the FHIR version: `include FHIRHelpers version '4.0.1'`.

3. **FHIRCommon for utilities.** Use `include FHIRCommon called FC` for
   common status checks, interval conversions, and extension access.
   Prefer `FC."active"`, `FC."completed"`, etc. over inline code literals.

4. **US Core Elements for EHR data access (§7 DTR).** When CQL pre-populates
   Questionnaire items from the EHR, include:
   ```cql
   include USCoreCommon version '2.0.0' called UC
   include USCoreElements version '2.0.0' called UCE
   ```
   Reference UCE patterns (`UCE."Active Conditions"`, `UCE."Patient Name"`)
   rather than writing retrieve logic from scratch.

5. **Extract shared expressions into domain libraries.** When ≥2 topic
   libraries share the same retrieval or filtering logic (e.g., "Latest
   HbA1c"), extract it to a shared domain library and include it:
   ```cql
   include LabCommon called Lab
   define "Needs Screening": Lab."Latest HbA1c".value > 5.7 '%'
   ```

6. **Max include depth: 3.** Topic → domain → foundation. Deeper nesting
   makes dependency tracking and debugging disproportionately harder.

### Expression Granularity

Each `define` statement SHOULD express a single clinical concept that can
be tested and understood in isolation.

**Preferred — small composable definitions:**

```cql
define "Has Diabetes Diagnosis":
  exists [Condition: "Diabetes Diagnoses"] C
    where C.clinicalStatus ~ FC."active"

define "Latest HbA1c":
  First(
    [Observation: "HbA1c"] O
      where O.status in { 'final', 'amended', 'corrected' }
      sort by effective.toInterval() desc
  )

define "HbA1c Above Threshold":
  "Latest HbA1c".value > 6.5 '%'

define "Needs Diabetes Management":
  "Has Diabetes Diagnosis" and "HbA1c Above Threshold"
```

**Avoid — monolithic expressions:**

```cql
// Anti-pattern: combining retrieval, filtering, and decision in one define
define "Needs Diabetes Management":
  exists [Condition: "Diabetes Diagnoses"] C
    where C.clinicalStatus ~ FC."active"
  and First([Observation: "HbA1c"] O
    where O.status in { 'final', 'amended', 'corrected' }
    sort by effective.toInterval() desc).value > 6.5 '%'
```

### Terminology Patterns in CQL

Follow the Using CQL With FHIR IG patterns for terminology comparisons:

- **Value set membership** — use `in`:
  `where Condition.code in "Diabetes Diagnoses"`
- **Direct-reference code comparison** — use `~` (equivalent):
  `where Observation.code ~ "HbA1c"`
- **Required-binding code elements** — use `=` (equal):
  `where Encounter.status = 'finished'`
- **Avoid string-based membership testing** (CR 2.10) — never test bare
  strings against value sets when a coded comparison is possible.
- **Avoid `concept` as a value set surrogate** (CR 2.12) — use proper
  value set definitions instead.

### Missing Information

CQL `null` propagation can cause silent false negatives. Follow the IG
patterns:

- **Boolean elements** — use `is true` / `is not true` rather than `= true`:
  ```cql
  where MedicationRequest.doNotPerform is not true
  ```
- **Choice-type temporals** — use the FHIRCommon `toInterval()` fluent
  function to normalize `dateTime | Period` choices:
  ```cql
  where Observation.effective.toInterval() starts 30 days or less before Today()
  ```

### Strategy-Specific CQL Notes

| Strategy | CQL Role | Key Guidance |
|----------|----------|-------------|
| §2 decision-table | Applicability conditions in PlanDefinition ECA rules | Keep each `condition.expression` as a single boolean `define`; reference via `<Library>."Expression Name"` in `action.condition[].expression` |
| §5 measure | Population criteria (initial population, denominator, numerator, exclusions) | One `define` per population segment; scoring-driven — never share a `define` across two population types |
| §7 policy (DTR) | Pre-population of Questionnaire items via `initialExpression` | One `define` per pre-populated item; compose from UCE patterns; non-pre-populatable items have no CQL |

### Resolved Decisions

- **Missing domain functions**: Place in a project-level shared library with
  `// CANDIDATE: propose to <IG>` annotations. Do not inline domain-level
  helpers in topic-specific libraries.
- **`context Patient` explicit**: Yes, always include `context Patient` in
  generated CQL. Explicit context aids readability and avoids ambiguity when
  mixing patient-context and unfiltered retrieves.
- **Minimum CQL validation in `rh-skills validate`**: Syntactic well-formedness
  only for v1 (valid CQL parse tree). In verify mode: also check that all
  `include` references resolve and terminology references match ValueSets in
  the topic's computable/ directory.
