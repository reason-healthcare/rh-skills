# Next Steps Plan

## Goal

Move `rh-skills` to a cleaner workflow that:

1. converts structured YAML into FHIR JSON cleanly,
2. supports iterative CQL/FHIRPath authoring and testing,
3. packages through the real `rh package` flow,
4. aligns extract/formalize behavior to the target output shape, and
5. proves the workflow with repo-owned examples and repeatable iteration.

## Target Shape Reference

The current target-shape references for this work are the repo-owned examples:

- `topics/chronic-rhinosinusitis/`

These targets currently express the desired direction for:

- L2 structure and decomposition
- L2 readout shape
- L3 FHIR resource boundaries and linkage
- event/trigger/applicability separation
- assessment decomposition and questionnaire linkage
- follow-up coordination vs postoperative follow-up branching

For this slice, the target-shape alignment scope is limited to:

- `terminology`
- `care-pathway`
- `decision-table`
- `assessment`
- `CQL` and the companion FHIR logic linkage

It does **not** include broad alignment work for other L2 artifact types.
Those may be revisited later, but they are out of scope for this target-model
iteration.

The plan and the iteration guide should be read together, but this plan should
be explicit about one rule:

- new framework work should reduce drift between actual CLI/skill behavior and
  these target shapes
- prioritize semantic and structural alignment to the target shapes over low-value
  syntax differences
- treat differences such as `type` vs `kind` or `true/false` vs `Yes/No` as
  secondary unless they block validation, formalization, or packaging
- if the target shapes are materially wrong, update the target shapes deliberately
- do not allow the framework and target examples to evolve as separate,
  conflicting models

## Current Status

Completed:

- `rh-skills package` wraps `rh package`
- deterministic `packager.toml` workspace generation exists
- `formalize-plan.yaml` validation alignment exists
- formalize implementation-target gating exists
- computable tracking deduplication on rerun exists for `formalize`
- `rh-skills cql test` executes
- `rh-skills fhirpath` wrapper exists
- terminology formalization to `ValueSet` output is proven
- activity definitions now carry codings in the recent target work
- assessment recommendations can point to questionnaire-backed assessment actions

Still open:

- end-to-end terminology proof in a repo-owned topic
- template-driven YAML -> FHIR JSON conversion
- explicit event/trigger contract in L2
- stronger action output modeling
- trigger/applicability ownership rules in L3 formalize
- renderer/readout support for hierarchy
- tighter CQL stubs with concrete criteria and status filtering

## Working Rules

- Do not base committed CLI/skill examples on external CRS content.
- Use external CRS only as an iteration probe.
- Regenerate external comparison content through the CLI workflow. Do not
  manually patch external structured or computable artifacts as the normal
  iteration path.
- Use the repo-owned target-shape topics as the working reference for desired
  L2 schema usage, readout structure, and L3 FHIR output shape for:
  - terminology
  - care-pathway
  - decision-table
  - assessment
  - CQL-linked logic artifacts
- After framework changes, run relevant local tests, then rerun content using [docs/AI_ITERATION_GUIDE.md](/Users/taylorkingston/projects/rh-skills/docs/AI_ITERATION_GUIDE.md:1).
- Make a commit between each meaningful iteration step in both:
  - this repo for framework changes
  - the external comparison repo for regenerated comparison content
- Breaking changes are acceptable. Do not preserve legacy schema or compatibility-only behavior unless there is a strong reason.
- When updating skills, use direct instructions. Do not describe desired behavior by contrasting it with prior behavior.
- Do not treat manual target artifacts as the solution. Use them to define the target shape, then move that shape into framework behavior.
- Do not let the plan, iteration guide, target artifacts, and framework
  behavior drift apart. If one changes, assess whether the others must change
  too.
- When comparing external output to the repo-owned target, evaluate semantic and
  structural alignment first:
  - staged events and orchestration
  - parent/child task decomposition
  - condition/data-element separation
  - readout hierarchy
  - recommendation and follow-up structure
  Treat syntax-only differences as lower priority unless they break the toolchain.
- Do not keep adding builder-specific L3 shaping to the current `formalize`
  path if that work is expected to be replaced by template-driven generation.
  Prefer:
  - L2/schema/skill/readout changes that clarify the target model
  - template-refactor work in `formalize`
  - then L3/output-shape work on top of the template layer

## Actionable To-Do List

### 1. Packaging and terminology

- [ ] Prove terminology wiring in a repo-owned end-to-end topic so `ValueSet` resources are generated alongside the artifacts that reference them.
- [ ] Validate the generated package workspace against the real `rh package` runtime end to end, without mocks.
- [ ] Decide whether package build outputs under `process/` should be retained or cleaned automatically after successful packaging.

### 2. Formalize architecture

- [ ] Refactor `formalize` to use template-driven YAML -> FHIR JSON conversion.
  - This is not just adding templates alongside the current code.
  - It will require replacing parts of the current Python builder path in `formalize` and related FHIR builder code.
  - The target state is:
    - reusable FHIR resource templates for core artifact families
    - scripts/helpers that bind structured YAML data into those templates
    - less direct field-by-field JSON construction embedded in command logic
- [ ] Establish the initial template boundary before more L3 alignment work:
  - identify the current builder entry points to replace
  - choose the first artifact families to template
  - introduce template-loading/render helpers into `formalize`
  - migrate one concrete resource family end to end before expanding scope
- [ ] Define and validate a formal L2 `event.trigger` contract:
  - optional presence
  - FHIR-compatible trigger types
  - resource criteria
  - timing-window support
- [ ] Define stronger conventions for action outputs beyond `produces_conditions[]`, especially assessment-result outputs that later logic consumes.
- [ ] After the template layer is in place, add an explicit formalize rule for trigger/applicability ownership so branch logic is not duplicated across L3 levels.
- [ ] After the template layer is in place, add explicit cross-artifact alignment support between care-pathway nodes and decision-table workflow contexts where that alignment matters to formalize.
- [ ] After the template layer is in place, align formalize output progressively to the repo-owned target L3 shapes so
  pathway, strategy, recommendation, assessment, questionnaire, and follow-up
  branches can be produced by the framework rather than by hand-authored target
  artifacts.
  - Scope this work to terminology, care-pathway, decision-table, assessment,
    and CQL-linked logic outputs only.

### 3. Extract and skill behavior

- [ ] Improve extract/skill guidance so event-only workflow contexts, optional triggers, and parent/child assessment decomposition are produced reliably without hand editing.
- [ ] Align extract behavior and L2 schema usage progressively to the repo-owned
  target L2 shapes so event decomposition, assessment hierarchy, and branching
  structure come from the framework rather than manual target authoring.
  - Scope this work to terminology, care-pathway, decision-table, assessment,
    and CQL-linked logic outputs only.
- [ ] Run target-vs-external semantic alignment checks as a recurring loop item:
  - compare current external CRS `care-pathway` and `decision-table` against the
    repo-owned target shape
  - identify the top 1-2 structural drifts
  - fix framework behavior for those drifts before addressing cosmetic syntax
    differences
- [ ] Tighten CQL-authoring guidance so mocked/generated logic uses:
  - concrete result criteria
  - explicit thresholds or TODOs
  - appropriate status filtering
- [ ] Remove lingering comparison-style skill wording and keep only direct behavioral instructions.

### 4. Renderer and readouts

- [ ] Upgrade the renderer/readout layer so hierarchy is supported directly.
- [ ] Support care-pathway trees from `steps[].parent_id`.
- [ ] Support decision-table event/rule/action trees from `events[]`, `rules[]`, and `actions[].parent_action_id`.
- [ ] Surface cross-artifact links between pathway nodes and downstream decision-table/recommendation artifacts.
- [ ] Align rendered readouts to the repo-owned target readout shapes so the
  built-in renderer can produce the same kind of hierarchy and cross-link
  visibility now shown in the manual target reports.
  - Scope this work to terminology, care-pathway, decision-table, assessment,
    and CQL-linked logic outputs only.

### 5. Tracking and cleanup

- [ ] If tracking consistency work expands beyond `formalize`, align `derive` and deprecated `combine` with the append-only-events and single-latest-artifact-row policy.
- [ ] Refresh docs/specs once implementation behavior settles.

## Recommended Order

1. Finish packaging and terminology proof in a repo-owned topic.
2. Implement the initial template-driven `formalize` boundary and migrate the
   first resource family off the current builder path.
3. Continue L2/schema/skill work needed to clarify the target model.
4. Resume L3/output-shape alignment on top of the template layer.
5. Move hierarchical target readouts into the real renderer.
6. Refresh docs/specs after behavior stabilizes.

## Explicit Non-Goals

- Do not use the e2e statin topic as the primary proof point for the next slice.
- Do not preserve old schema just because it existed.
- Do not treat external CRS output as a committed example set.
