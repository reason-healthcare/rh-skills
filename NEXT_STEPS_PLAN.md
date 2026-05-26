# Next Steps Plan

## Goal

Move the project from a mostly in-repo packaging prototype to a workflow that:

1. formalizes structured YAML into FHIR JSON,
2. supports iterative CQL/FHIRPath authoring with `rh`,
3. wraps the real `rh package` flow with a generated `packager.toml`,
4. validates package build/check/preview behavior, and
5. proves the workflow with one fresh end-to-end topic.

This plan is based on the current repository state as of 2026-05-21 and the follow-up decisions for this slice:

- Use the local `rh` CLI package tooling rather than inventing a parallel packager.
- Proceed with implementation work, but do not spend this slice on docs/contracts cleanup.
- Do not add real LLM provider support yet.
- Do not take on broad "fix failing tests" cleanup unrelated to the touched work.

## Current State

### What now exists

- `rh-skills formalize <topic> <artifact>` exists in [src/rh_skills/commands/formalize.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/formalize.py:392) and now respects an approved `formalize-plan.yaml` target when one exists.
- `rh-skills cql validate`, `translate`, and executable fixture-driven `test` exist in [src/rh_skills/commands/cql.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/cql.py:60).
- `rh-skills fhirpath parse` and `eval` now exist in [src/rh_skills/commands/fhirpath.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/fhirpath.py:28).
- `rh-skills package <topic>` now stages a package workspace from `computable/` and wraps `rh package check/build/pack` via [src/rh_skills/commands/package.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/package.py:48).
- The repo tracks packaging and computable lifecycle events in `tracking.yaml`.
- A fresh end-to-end statin topic orchestration flow now exists as [tests/integration/test_statin_primary_prevention_flow.py](/Users/taylorkingston/projects/rh-skills/tests/integration/test_statin_primary_prevention_flow.py:1).

### What `rh` supports right now

The local `rh` CLI exposes:

- `rh package init`
- `rh package build`
- `rh package check`
- `rh package pack`
- `rh cql ...`
- `rh fhirpath ...`

Most importantly:

- `rh package build <DIR>` expects a source directory containing `packager.toml` and FHIR resources.
- `rh package check <DIR>` validates source before build.
- `rh package pack <DIR>` produces a `.tgz` from an expanded package output.

### Remaining gaps and mismatches

- `formalize` still relies on stub LLM behavior only; that is acceptable for this slice, but it limits realistic automation.
- The current design has treated `package/` as a durable artifact directory, but the cleaner model is for `computable/` to remain the only canonical home for L3 artifacts.
- `rh package` still needs a source directory and build output directory, but those should be treated as packaging internals rather than a second persistent L3 store.
- The repo still has stale docs and specs that refer to `formalize-plan.md`, `package/`, and `cql test` as eval-pending; those are intentionally deferred for now.
- Real `rh package check/build` behavior still needs live validation against the actual `rh` runtime, not only subprocess-mocked tests.
- ReasonHub spec-context access failed in this session due an MCP transport/session issue, so spec verification had to stay local for this pass.

## Tracking Consistency Policy

- `tracking.yaml.events[]` and `topic.events[]` are append-only run history.
- `--force` may overwrite files or regenerate plan/config artifacts, but it must not delete or rewrite historical tracking events.
- Artifact index arrays such as `topic.structured[]` and `topic.computable[]` are current-state registries, not run-history logs.
- For current-state registries, the preferred policy is one row per artifact `name`, replaced on rerun rather than duplicated.
- New work should align toward:
  - appending a fresh event for each successful run
  - keeping a single latest artifact row per artifact name
- Older commands that still append duplicate artifact rows should be treated as legacy inconsistency to clean up deliberately, not as the standard to copy forward.

### Current pattern in this repo

- `promote plan` and `promote formalize-plan` already overwrite plan files with `--force` while still appending new events.
- `formalize` already follows the desired model:
  - file overwrite is allowed with `--force`
  - a new `computable_converged` event is appended per run
  - the latest `computable[]` row replaces the prior row for the same artifact name
- `derive` and deprecated `combine` still append duplicate artifact rows and should be treated as inconsistent legacy behavior, not precedent.

## Scope For This Slice

### In scope

- Replace or wrap the current package builder with a real `rh package` workflow.
- Generate a `packager.toml` control file.
- Support package preview/check/build/pack behaviors from `rh-skills`.
- Finish the practical CQL iteration loop by making `rh-skills cql test` actually execute tests through `rh`.
- Align formalize/validate behavior enough to support the package workflow cleanly.
- Add one new end-to-end topic fixture that exercises the intended path.
- Add a lightweight FHIRPath wrapper to complete the iterative logic-authoring loop.

### Out of scope

- Docs refresh across `README.md`, `docs/`, and `specs/`.
- Broad cleanup of pre-existing failing tests unrelated to touched code.
- Real LLM provider integrations.

## Completion Summary

- Completed: packaging wrapper around `rh package`
- Completed: deterministic `packager.toml` workspace generation
- Completed: `formalize-plan.yaml` validation alignment
- Completed: formalize implementation-target gating
- Completed: computable tracking deduplication on rerun as an implementation of the single-latest artifact-row policy
- Completed: executable `rh-skills cql test`
- Completed: lightweight `rh-skills fhirpath` wrapper
- Completed: fresh end-to-end statin topic integration flow for the decision-table/CQL/package path
- Completed: terminology formalization proven through `ValueSet` outputs (including multi-`value_sets[]` → multiple `ValueSet-*.json` behavior)
- Not yet completed: terminology included in the fresh end-to-end topic path

## Remaining Work

- [x] Formalize at least one approved `terminology` artifact into concrete `ValueSet` JSON output and verify the output shape.
- [ ] Build template-driven scripts to convert YAML to FHIR JSON.
- [ ] Prove terminology wiring in an end-to-end topic so `ValueSet` resources are generated alongside the other computable artifacts that reference them.
- [ ] Validate the generated package workspace against the real `rh package` runtime end to end, without mocks.
- [ ] Decide whether to preserve package build outputs under `process/` or clean them up automatically after successful packaging.
- [ ] If tracking consistency work expands beyond `formalize`, align `derive` and deprecated `combine` with the append-only-events and single-latest-artifact-row policy.
- [ ] Refresh docs/specs once implementation behavior settles.

## Proposed Implementation Plan

## Phase 1: Rework Packaging Around `rh package`

Status: Complete

### Objective

Turn `rh-skills package` into a thin orchestration layer over the real `rh package` subcommands.

### Deliverables

- Keep `topics/<topic>/computable/` as the single canonical directory for L3 artifacts.
- Generate a packaging source directory only as an implementation detail, likely under `topics/<topic>/process/` or a temp workspace.
- Generate `packager.toml` into that packaging source directory.
- Stage or copy FHIR JSON and CQL inputs from `topics/<topic>/computable/` into that packaging source directory.
- Replace direct package assembly in `src/rh_skills/fhir/packaging.py` with wrapper logic that shells out to:
  - `rh package check <source-dir>`
  - `rh package build <source-dir> --out <build-dir>`
  - optionally `rh package pack <build-dir>`

### Command direction

Keep `rh-skills package <topic>` as the user-facing command, but evolve it to:

- `--dry-run`: show what source dir, output dir, and `rh` commands would be used
- `--check-only`: run `rh package check`
- `--pack`: run `rh package pack` after build
- `--output-dir`: override expanded build output
- optionally `--source-dir`: override package source directory for debugging

### Design notes

- `formalize-config.yaml` should remain the source for canonical, version, status, package name defaults, and related metadata.
- The generated `packager.toml` should be deterministic and rewritten safely on each packaging run.
- We should avoid introducing a second long-lived L3 output tree beside `computable/`; packaging outputs should be ephemeral or clearly scoped as distribution artifacts, not canonical computable sources.
- `package_created` should still be recorded only after a successful build.
- If `rh` is missing, the error path should mirror the actionable install guidance already used in `cql.py`.

## Phase 2: Align Formalize and Validation With The New Packaging Path

Status: Complete for this slice

### Objective

Make sure the computable outputs and validation flow are compatible with the package wrapper.

### Deliverables

- Update `validate` to read the current `formalize-plan.yaml` workflow instead of the stale `.md` assumption.
- Confirm `validate` can still check implementation-target gating and `converged_from` consistency.
- Tighten `formalize` behavior where needed so packaging works against one coherent set of computable outputs.

### Specific follow-ups

- Decide whether `formalize` itself should refuse to run unless the approved YAML formalize plan names the artifact as the implementation target.
- Keep `formalize` aligned with the tracking policy: append run-history events, but keep a single latest `topic["computable"]` row per artifact name.
- If tracking consistency cleanup broadens later, apply the same policy deliberately to `derive` and deprecated `combine` rather than treating duplicate rows as acceptable precedent.
- Preserve the current "no real LLM provider yet" constraint and continue using stub-based generation where necessary.

## Phase 3: Finish The CQL Iteration Loop

Status: Complete for this slice

### Objective

Make `rh-skills cql` genuinely useful for repeated author-review-test cycles.

### Deliverables

- Replace the placeholder `rh-skills cql test` implementation with real execution through `rh cql eval` or the closest supported `rh` command surface.
- Support fixture-driven case evaluation from `tests/cql/<Library>/case-*/`.
- Report pass/fail per case and exit non-zero when any case fails.
- Emit concise summaries that agents can use for iterative repair.

### Notes

- `validate` and `translate` already exist and should remain the backbone of the loop.
- The lightweight `rh-skills fhirpath` wrapper is now in place, so FHIRPath no longer needs to stay as a direct-only `rh` escape hatch for this slice.

## Phase 4: Formalize Terminology To ValueSets

Status: Partially complete

### Objective

Close the missing terminology gap by proving that L2 `terminology` artifacts are actually carried through to L3 `ValueSet` resources, not just planned in strategy docs.

### Deliverables

- Formalize at least one approved `terminology` artifact into `ValueSet-*.json` output under `topics/<topic>/computable/`.
- Preserve the companion `ConceptMap` output where the artifact defines mappings, but treat `ValueSet` generation as the non-optional proof point.
- Verify that downstream artifacts can reference the produced `ValueSet` canonicals rather than leaving terminology implicit in narrative or structured YAML only.
- Add or update focused tests so the terminology path is covered by repo automation, not just by documentation and eval scenarios.

### Extract-side design

- Keep `concepts[]` as the authoritative reviewed terminology catalog.
- Add stable `concepts[].id` values so terminology references are durable.
- Emit a thin `sections.value_sets[]` manifest from extract where each entry:
  - names the future `ValueSet`
  - points to one or more reviewed concepts via `concept_refs[]`
- For the first pass, create one `value_sets[]` entry per concept.
- Only emit `concepts[]` and `value_sets[]` entries for approved concepts with approved codes and/or approved expansions.
- Do not duplicate approved `codes[]` and `expansions[]` into `value_sets[]`; formalize should resolve them by following `concept_refs[]`.

### Notes

- The terminology path is now explicitly wired through extract (`concepts[]` + `sections.value_sets[].concept_refs[]`) and formalize emits multiple `ValueSet` resources when multiple value set manifest rows are present.
- Remaining work is topic-level end-to-end proof that includes terminology in the fresh fixture flow.

## Phase 5: Add A Fresh End-to-End Fixture Topic

### Objective

Prove the intended workflow with one new topic built in this repo from scratch.

### Proposed topic

Use a new topic such as `statin-primary-prevention`.

This topic is a good fit because it can naturally exercise:

- terminology/value sets,
- a decision-table or policy-style artifact,
- a measure with companion CQL,
- package generation.

Current status:

- The statin topic already proves the decision-table/CQL/package path.
- It does not yet prove terminology formalization to `ValueSet`, so this phase should now be treated as partially complete until terminology is included.

### Fixture expectations

Create a minimal but realistic topic that includes:

- `structured/` inputs authored specifically for this repo
- at least one approved `terminology` artifact that becomes `ValueSet-*.json`
- at least one CQL-backed artifact
- `computable/` outputs generated through the repo workflow
- packaging inputs/outputs only as wrapper internals around `rh package`
- tracking events showing the full path from structured to packaged

### Success criteria

The new topic should support the following sequence:

1. `rh-skills formalize-config <topic>`
2. `rh-skills promote formalize-plan <topic>` and approval steps
3. `rh-skills formalize <topic> <artifact>`
4. confirm `ValueSet-*.json` exists for the terminology artifact
5. `rh-skills cql validate <topic> <library>`
6. `rh-skills cql translate <topic> <library>`
7. `rh-skills cql test <topic> <library>`
8. `rh-skills package <topic> --check-only`
9. `rh-skills package <topic>`
10. optional `rh-skills package <topic> --pack`

## Phase 6: Focused Test Coverage For New Work

### Objective

Add or update targeted tests only for the code we touch in this slice.

### Test targets

- package wrapper command behavior
- `packager.toml` generation
- `rh` subprocess invocation arguments
- `check/build/pack` flows
- `cql test` real fixture execution behavior
- terminology `ValueSet` formalization behavior
- YAML formalize-plan validation path
- tracking policy conformance where touched: append-only events plus single-latest artifact rows

### Constraints

- Do not stop this slice to chase unrelated pre-existing failures.
- Do not do a repo-wide test repair project here.
- If test environment tooling is flaky, keep unit tests subprocess-mocked where needed and limit new integration coverage to deterministic cases.

## Suggested File-Level Work Breakdown

### Likely code changes

- [src/rh_skills/commands/package.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/package.py:20)
- [src/rh_skills/fhir/packaging.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/fhir/packaging.py:15)
- [src/rh_skills/commands/cql.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/cql.py:35)
- [src/rh_skills/commands/validate.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/validate.py:309)
- possibly [src/rh_skills/commands/formalize.py](/Users/taylorkingston/projects/rh-skills/src/rh_skills/commands/formalize.py:369)

### Likely new tests

- `tests/test_package_command.py`
- `tests/test_fhir_packaging.py`
- `tests/unit/test_cql.py`
- `tests/unit/test_validate.py`
- possibly a new focused integration test for the new topic fixture

## Order Of Execution

1. ✅ Formalize at least one terminology artifact to `ValueSet` output.
2. Extend the fresh end-to-end topic fixture so it includes terminology, not only decision logic and packaging.
3. Validate the generated package workspace against the real `rh package` runtime.
4. Decide packaging-output retention behavior.
5. Refresh docs/specs once implementation behavior is stable.

This order reduces rework because the missing terminology proof point should be closed before the end-to-end fixture is treated as fully complete.

## Risks To Watch

- `rh package` source layout may impose metadata requirements beyond what `formalize-config.yaml` currently captures.
- Existing packaging tests assume self-generated `package.json` and IG behavior; they will need to be rewritten around subprocess orchestration.
- The repo currently has mixed assumptions about `.md` vs `.yaml` formalize plans; code changes here should be localized and deliberate to avoid accidental contract churn.
- The repo still has mixed tracking-row behavior across commands, so future work needs to enforce the append-only-events / single-latest-artifact-row policy consistently instead of copying legacy duplicate-row behavior.
- `uv` execution in this environment has already shown instability, so verification should not rely entirely on one local runner path.
- The current statin integration test can give a false sense of completeness because it does not yet exercise terminology formalization or `ValueSet` references.

## Done Criteria For This Slice

- `rh-skills package` wraps `rh package` rather than building packages itself.
- A generated `packager.toml` exists in a deterministic packaging workspace while `computable/` remains the sole canonical L3 artifact directory.
- `rh-skills cql test` performs actual executable case testing.
- `validate` no longer depends on the stale `formalize-plan.md` path.
- At least one approved terminology artifact is formalized to `ValueSet` JSON and covered by tests.
- One newly created end-to-end topic proves the workflow from structured input through terminology/value-set generation and package build.
- New targeted tests exist for the touched code paths, without expanding scope into repo-wide test cleanup.
