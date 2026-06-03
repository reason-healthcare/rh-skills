# AI Iteration Guide for Extract/Formalize

This guide is for iterating on the `rh-skills` extract/formalize framework using
a concrete comparison case without overfitting the system to that one case.

Current example inputs:

- Target example in this repo: `topics/chronic-rhinosinusitis/`
- External test project: `/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs/`
- External test topic: `topics/crs-surgical-management/`

The important constraint is that `chronic-rhinosinusitis` is an evaluation
reference, not a template to copy. Improvements must come from better CLI and
skill behavior, not from manually shaping outputs to match one target topic.

Do not use the external CRS project as a committed example source. It is an
iteration probe only and is not owned as committed content in this repo.

When updating the external comparison repo, use the CLI workflow to regenerate
content. Do not hand-edit external structured or computable artifacts except
when diagnosing a transient failure and discarding that change afterward.
External comparison commits should come from:

- `rh-skills promote body-init`
- agent-authored draft completion
- `rh-skills promote derive`
- `rh-skills render`
- `rh-skills formalize`
- `rh-skills validate`
- `rh-skills package --pack`

If the framework change requires the external content to change, rerun the
appropriate CLI steps and commit those regenerated outputs. Do not patch the
comparison artifacts directly as the normal iteration path.

## Default Execution Mode

Use `LLM_PROVIDER=stub` as the default mode for framework iteration.

Rationale:

- it removes network, quota, and model-availability noise from the loop
- it keeps attention on CLI boundaries, prompt contracts, validation, and
  deterministic framework behavior
- it is safer for repeated reruns against the external test project

Only switch to a real model after a change is stable enough that you want to
evaluate actual content quality rather than framework mechanics.

## True Agent Stub Mode

For this iteration workflow, "stub mode" should normally mean:

- `LLM_PROVIDER=stub`
- the agent reads the relevant source content
- the agent uses the curated extract/formalize skills for behavioral guidance
- the agent authors the artifact content itself
- for `derive`, the agent fills the `body-init` scaffold or artifact body itself
- for `formalize`, the agent provides the FHIR JSON artifact content through
  `RH_STUB_RESPONSE`
- `rh-skills` owns the deterministic write, validation, and formalize steps

This is different from plain placeholder stub mode.

Plain placeholder stub mode:

- uses the built-in scaffold content only
- is useful for schema/mechanics checks
- does not meaningfully test content production quality

True agent stub mode:

- uses stubbed CLI execution with agent-authored content
- exercises the curated skill instructions and prompt contracts
- lets the iteration loop test both CLI behavior and skill behavior without
  calling a live model

Default expectation for extract/formalize iteration:

1. run `body-init` when needed to create a scaffold
2. have the agent complete the draft using source evidence and the curated
   skills as guidance
3. run `promote derive --body-file ...`
4. when testing `formalize` in stub mode, have the agent author the intended
   JSON resource array and pass it through `RH_STUB_RESPONSE`
5. validate and package through the CLI

Do not treat plain placeholder scaffolds as the main iteration path when the
goal is to assess or improve output shape relative to the target.

## Agent-Authored Stub Content

For this project, default stub-mode testing should use agent-authored artifact
content, not built-in placeholder scaffolds.

For `derive`:

- use `LLM_PROVIDER=stub`
- let the agent read the sources and curated extract skill
- let the agent complete the L2 draft body
- run `promote derive --body-file ...`

For `formalize`:

- use `LLM_PROVIDER=stub`
- let the agent read the structured L2 artifact and curated formalize skill
- let the agent author the intended FHIR JSON resource array
- pass that JSON through `RH_STUB_RESPONSE`
- run `rh-skills formalize ...`

Use plain placeholder stub output only when you are deliberately testing CLI
mechanics or scaffold topology. Do not use it as the default content-quality
iteration path.

## Required Refresh Steps

Before regenerating artifacts in the external test project, refresh both the
local CLI install and the installed skills.

1. From the root of this repo, run:

```bash
make install
```

This must be run from the root of the framework repo:

- `/Users/taylorkingston/projects/rh-skills`

2. From the root of the external test repo, run:

```bash
rh-skills skills init --from /Users/taylorkingston/projects/rh-skills/skills/.curated --force
```

This must be run from the root of the test repo:

- `/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs`

Why this matters:

- `make install` refreshes the locally installed `rh-skills` CLI from the
  current framework source
- `rh-skills skills init --from ... --force` refreshes the test repo's
  installed skill files from the current curated skill set
- running regeneration without these steps can mix old installed CLI/skill
  behavior with new source changes and invalidate the iteration results

## Structured Drafts

`rh-skills promote body-init` should be treated as a draft-scaffold helper.

It currently writes to:

- `topics/<topic>/process/tmp/<artifact>.yaml`

Why this matters:

- the scaffold is not yet a validated structured artifact
- `promote derive --body-file ...` is the step that should turn the scaffold
  into completed structured content
- iteration should not confuse tmp scaffolds with the canonical
  `structured/<artifact>/<artifact>.yaml` output

## Alignment Scope

When iterating, the agent must keep the whole framework aligned. A valid change
is rarely "just update the CLI" or "just tweak the skill prompt."

At minimum, assess whether the iteration requires updates in each of these
surfaces:

- CLI implementation under `src/rh_skills/commands/`
- FHIR helpers under `src/rh_skills/fhir/`
- bundled/curated skill instructions and references
- end-user docs under `docs/`
- tests under `tests/`
- eval scenarios under `eval/scenarios/`
- example or tracked topic artifacts used as reference points

If behavior changes in one layer, the agent should explicitly decide whether the
other layers need matching updates. Silent drift between these layers is a
framework bug.

## Skill Usage In Iteration

The curated skills are part of the framework being iterated on, not just
operator convenience text.

During iteration the agent should explicitly use:

- `skills/.curated/rh-inf-extract/`
- `skills/.curated/rh-inf-formalize/`

Why this matters:

- these skills define the intended agent-side behavior when working with the
  CLI in true agent stub mode
- if the skills drift from actual CLI behavior, that is a framework defect
- output regressions may come from stale skill guidance even when the Python
  code is unchanged

So each iteration should consider both:

- did the CLI/framework need to change?
- did the curated skill guidance need to change?

## Formalize Plan Semantics

Treat `formalize-plan.yaml` as a prioritization and review artifact, not an
exclusive execution lock.

- `implementation_target: true` identifies the plan's primary artifact for
  review focus and packaging emphasis
- it should not block `formalize` or `validate` for other artifacts that are
  individually approved
- if non-target artifacts are blocked only because they are not the target,
  that is a workflow bug to fix in the framework

## Goal

Use an agent to repeatedly:

1. Assess what framework changes would make `extract` and `formalize` produce
   better L2/L3 outputs for the external test topic.
2. Implement those changes in `rh-skills` itself.
3. Re-run the lifecycle in the external test project.
4. Compare the new outputs against the target example at the level of
   structure, semantics, and clinical decomposition.
5. Repeat until the framework is producing materially better results.

## What "Better Alignment" Means

Alignment does not mean file-for-file matching.

Use the target topic to evaluate:

- whether the framework chooses the right artifact types
- whether one narrative guideline is decomposed into the right set of L2
  artifacts
- whether decisions are kept recommendation-scoped instead of becoming one
  monolithic rule set
- whether care sequencing becomes pathway structure rather than leaking into
  decision logic
- whether L3 outputs reflect clean FHIR resource boundaries
- whether naming, granularity, and action decomposition are clinically coherent

Do not require:

- the same artifact count
- the same artifact names
- the same exact FHIR resource ids
- the same ordering of files
- the same shape for unrelated future guidelines

## Current Example Signal

Today the target example under
`topics/chronic-rhinosinusitis/structured/` contains a narrow L2 shape:

- `care-pathway`
- `decision-table`

The external test topic under
`/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs/topics/crs-surgical-management/structured/`
currently contains a broader set:

- `assessment`
- `care-pathway`
- `concepts`
- `decision-table`
- `evidence-summary`
- `measure`

That difference is useful, but it should not be interpreted as "the framework
must collapse everything to exactly two artifacts." The right question is
whether the broader decomposition is justified by the source material and the
framework rules, or whether extract/formalize is currently producing avoidable
sprawl for this class of narrative guideline.

## Non-Negotiable Rules

1. Change the framework, not the outputs by hand.
   All durable output changes must come from `rh-skills` commands and skill
   behavior. Do not manually edit generated L2/L3 artifacts in the test repo as
   a way to "prove" alignment.

2. Optimize for generalizable rules.
   Every change should be explainable as a reusable improvement for narrative
   guideline processing, not as a CRS-only exception.

3. Default to stub-mode testing first.
   First prove the framework behaves correctly with `LLM_PROVIDER=stub`. Use
   live model runs only as a later validation pass.

4. Compare semantics, not filenames.
   The agent should compare artifact purpose, decomposition, and computable
   boundaries before it compares names or counts.

5. Preserve CLI boundaries.
   Reasoning belongs in skills/prompts. Deterministic writes, path resolution,
   and validation belong in `rh-skills` commands.

6. Keep all framework artifacts consistent.
   If extract/formalize behavior changes, update the skill guidance, docs,
   tests, and eval fixtures that define or verify that behavior.

7. Do not copy target content.
   The target can justify a rule like "prefer recommendation-scoped
   decision-table events," but not "emit this exact list of steps/actions."

8. Keep the target as a probe, not a golden schema.
   A future hypertension guideline or prior auth policy should still be able to
   pass through the same improved framework even if its output shape differs.

9. Breaking changes are acceptable.
   Do not preserve legacy schema or compatibility-only behavior if it blocks a
   cleaner framework contract. This is a new tool.

10. Use direct skill language.
    When updating skills, state the behavior the agent should follow. Do not
    describe desired behavior by contrasting it with previous behavior.

11. Commit between iteration steps.
    Each meaningful framework iteration step should end with a commit before
    moving on to the next step. Apply this to both:
    - the `rh-skills` repo when framework behavior changes
    - the external comparison repo when regenerated content changes
    Use separate commits for distinct framework moves, reruns, or corrections
    so the iteration history stays inspectable.

## Change Surface Checklist

Before closing an iteration, the agent should review this full checklist.

### 1. CLI and framework logic

Potential files:

- `src/rh_skills/commands/promote.py`
- `src/rh_skills/commands/formalize.py`
- `src/rh_skills/commands/validate.py`
- `src/rh_skills/fhir/normalize.py`
- `src/rh_skills/fhir/validate.py`
- strategy builders under `src/rh_skills/fhir/builders/`

Questions:

- Did planner heuristics change?
- Did derive/formalize behavior change?
- Did validation expectations change?
- Did naming or normalization rules change?

### 2. Skill instructions

Potential files:

- curated skill `SKILL.md` files for extract/formalize
- curated `reference.md` files
- installed skill templates if they mirror the same guidance

Questions:

- Does the skill still instruct the agent to use the updated behavior?
- Are prompt examples now stale?
- Did a rule move from prompt-only guidance into CLI logic, or vice versa?

### 3. Documentation

Potential files:

- `docs/EXTRACT.md`
- `docs/FORMALIZE.md`
- `docs/FORMALIZE_STRATEGIES.md`
- `docs/WORKFLOW.md`
- `docs/COMMANDS.md`
- this guide

Questions:

- Do the workflow docs still describe the real lifecycle?
- Did command behavior or expected outputs change?
- Is new guidance needed so future agents do not regress?

### 4. Tests

Potential files:

- unit tests under `tests/unit/`
- command tests such as `tests/test_formalize_command.py`
- topic-specific regression tests such as `tests/fhir/test_crs_formalize.py`
- integration tests under `tests/integration/`

Questions:

- Is there a test proving the new rule?
- Did an existing test encode the old behavior and now need revision?
- Is there a missing regression test for the exact failure that motivated the
  change?

### 5. Eval scenarios and fixtures

Potential files:

- `eval/scenarios/rh-inf-extract/*.yaml`
- `eval/scenarios/rh-inf-formalize/*.yaml`
- fixture files under `tests/` or `example-project/`

Questions:

- Does the evaluation scenario still exercise the right behavior?
- Should a new scenario be added for the new decomposition rule?
- Are fixture expectations outdated?

### 6. Reference topics and examples

Potential files:

- `tracking.yaml`
- `topics/chronic-rhinosinusitis/`
- `example-project/`

Questions:

- Is the reference example still the right comparison case?
- Did a framework change make the tracked example misleading or stale?
- Does the example need regeneration or a note explaining version drift?

## Recommended Iteration Loop

### 1. Baseline the comparison

Review both topics before changing code:

- target L2/L3 in `topics/chronic-rhinosinusitis/`
- actual L2/L3 in
  `/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs/topics/crs-surgical-management/`
- relevant framework docs:
  - `docs/EXTRACT.md`
  - `docs/FORMALIZE.md`
  - `docs/FORMALIZE_STRATEGIES.md`

Capture differences as framework hypotheses, for example:

- extract is over-producing auxiliary artifact types for single-source narrative
  guidelines
- decision-table event selection is too broad
- care-pathway derivation is not canonical enough
- formalize is generating overly fragmented PlanDefinitions
- activity/action naming is too literal or too source-sentence-driven

Each hypothesis should point to a framework lever:

- extract planning heuristics
- derive prompt instructions
- render/validate expectations
- formalize strategy logic
- normalization rules

### 2. Make a small framework change

Prefer narrow, testable changes in:

- `src/rh_skills/commands/promote.py`
- `src/rh_skills/commands/formalize.py`
- validation or normalization helpers under `src/rh_skills/fhir/`
- skill/reference docs when the issue is prompt behavior rather than CLI logic
- tests and eval scenarios whenever behavior expectations change
- workflow docs whenever the user-facing contract changes

Avoid batch edits that change multiple extract and formalize behaviors at once.
You want each rerun to explain which rule moved the output.

### 3. Re-run against the external project

Before rerunning extract/formalize, refresh the install surfaces:

```bash
cd /Users/taylorkingston/projects/rh-skills
make install

cd /Users/taylorkingston/rh-skills-projects/aao_vermonster_crs
rh-skills skills init --from /Users/taylorkingston/projects/rh-skills/skills/.curated --force
```

Run the CLI from this repo while pointing it at the external project root:

```bash
LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills promote plan crs-surgical-management
```

Then continue the relevant lifecycle steps, for example:

```bash
LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills promote formalize-plan crs-surgical-management

LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills validate crs-surgical-management structured decision-table

LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills validate crs-surgical-management l3 decision-table
```

If a full cycle is needed, re-run only the specific artifacts affected by the
change whenever possible rather than regenerating everything blindly.

After code or skill changes:

1. run the relevant local tests for the touched code paths
2. refresh the CLI and curated skills
3. rerun the comparison content using this guide

Do not treat code changes as complete until both tests and the iteration rerun
have been done.

Do not parallelize dependent lifecycle steps against the same artifact. In
particular:

- do not run `promote derive` and `validate` for the same artifact at the same
  time
- do not run `formalize` and `validate` for the same artifact at the same time

Run them sequentially so validation always reflects the artifact that was just
written.

For extract and formalize implement steps, also keep stub mode on unless you
are explicitly doing a live-model content check:

```bash
LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills promote derive crs-surgical-management decision-table --force \
  --source CPG_SurgCRS_FAQ_V6_pdf \
  --source GLIA_Summary_Report-CPGSurgCRS-Final_pdf \
  --source Otolaryngol_head_neck_surg_2025_Shin_Clinical_Practice_Guideline_Surgical_Management_of_Chronic_Rhinosinusitis_pdf \
  --source crs_scope_pdf \
  --source crs_stage_1_search_narrative_pdf \
  --artifact-type decision-table \
  --clinical-question "What recommendation-scoped triggers, local conditions, and actions form the decision logic?" \
  --required-section summary \
  --required-section events \
  --required-section conditions \
  --required-section actions \
  --required-section rules \
  --required-section evidence_traceability

LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills formalize crs-surgical-management decision-table --force
```

### 4. Assess the rerun

After each rerun, answer:

- Did the framework choose a more appropriate artifact decomposition?
- Did the L2 outputs become more clinically coherent?
- Did L3 become closer to clean strategy/resource boundaries?
- Did the result improve without introducing CRS-specific assumptions?
- Would the rule still make sense for a different narrative guideline?

If the answer to the last question is no, revert the direction and redesign the
change.

### 5. Repeat

Continue until changes stop producing meaningful quality gains.

## What the Agent Should Produce Each Cycle

For each iteration, the agent should leave a short markdown note containing:

- hypothesis
- whether the rerun used stub mode or a live model
- framework files changed
- skills/docs/tests/eval files changed
- commands rerun in the external project
- observed differences in L2
- observed differences in L3
- whether the improvement seems generalizable
- whether all affected framework surfaces were updated
- next change to try

Store these notes in a dedicated working document, for example:

- `docs/CRS_ITERATION_LOG.md`

That file is optional, but keeping the loop explicit will prevent drifting into
unexplained prompt tweaking.

## Comparison Checklist

Use this checklist when comparing actual output to the target example.

### Extract / L2

- Are artifact types justified by the source, or are they artifacts of prompt
  verbosity?
- Is the decision-table focused on recommendation-level decisions?
- Is sequencing captured in the care-pathway rather than duplicated in rules?
- Are evidence and measure artifacts only produced when they add distinct value?
- Are action names normalized to reusable clinical activities?
- Are artifacts internally coherent and reviewable by a human SME?

### Formalize / L3

- Does each L2 artifact map cleanly to the intended FHIR strategy?
- Are PlanDefinitions separated by actual workflow/decision boundaries?
- Are ActivityDefinitions reusable and not sentence-fragment copies?
- Are Library/CQL boundaries sensible for the logic present?
- Are generated resource ids and names stable, normalized, and not overly
  source-literal?

### Generalization

- Would this same rule help another narrative guideline?
- Is the change based on artifact semantics rather than CRS content?
- Did the change avoid assuming a fixed target artifact inventory?

## Anti-Patterns

Do not let the agent:

- manually edit generated YAML or JSON in the external test repo to "finish"
  the result
- hard-code CRS artifact names into planner or formalize logic
- update CLI behavior without updating the corresponding skill guidance
- update skill guidance without adding or revising tests when behavior changed
- update prompts/examples while leaving workflow docs inaccurate
- optimize for matching file counts
- collapse all narrative guidelines into the exact target CRS shape
- introduce hidden topic-specific exceptions without naming them explicitly
- treat the target repo as training data to replicate verbatim

## Good Prompting Frame for the Agent

When assigning the loop to an agent, frame it like this:

> Compare the external test topic against the chronic-rhinosinusitis example to
> identify generalizable extract/formalize weaknesses. Make the smallest
> framework change that improves decomposition or computable structure, rerun
> the affected lifecycle steps in the external project, assess the delta, and
> repeat. Use `LLM_PROVIDER=stub` by default, do not hand-edit generated
> artifacts, and do not optimize for exact file matching.

## Suggested Success Criteria

This iteration effort is succeeding when:

- the external test topic can be re-derived through the CLI with less noisy L2
  decomposition
- L3 outputs have clearer strategy/resource boundaries
- improvements are explainable as framework rules
- stub-mode reruns are stable and useful before any live-model pass
- skill instructions, docs, tests, and eval scenarios stay aligned with the
  implemented behavior
- the target example remains a useful comparison point without becoming a rigid
  template
- a different guideline topic could plausibly benefit from the same changes
