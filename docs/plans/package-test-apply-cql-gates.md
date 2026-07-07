# Package Test, Apply, and CQL Gate Plan

## Summary

`rh-skills` should treat CQL fixtures, package smoke tests, and fixture
packaging as first-class L3 concerns. These should be visible in package generation and
validation gates instead of living as manual patches around generated packages.

This plan covers:

- First-class package apply smoke verification.
- CQL fixture drift as a validation/package gate.
- Optional package-level promotion of test fixture input resources to examples.

## Goals

- A generated package can be smoke-tested by posting a bundle and invoking
  `$r5.apply` before it is considered shippable.
- CQL test fixtures cannot silently drift from the CQL they are meant to cover.
- rh-skills can prepare package input from both `computable/` and selected test
  fixture input resources, then delegate build/pack to `rh package`.

## Non-Goals

- Replacing `rh cql eval` or the RH runtime.
- Encoding temporary RH runtime workarounds in generated CQL. FHIR choice-type
  behavior should be fixed in RH and validated through fixture execution.
- Reimplementing package build, tarball assembly, FHIR server posting, `$apply`,
  or CQL evaluation inside rh-skills.
- Building a full authoring UI for fixture maintenance.
- Making generated resource ids stable enough to compare apply outputs by id.
  Apply verification should compare by canonical URL and resource type.

## Ownership Boundary

Use this boundary to avoid putting generic runtime or packaging work in
rh-skills.

| Concern | Owner | Rationale |
|---|---|---|
| Topic layout, tracking, L2/L3 artifact discovery | rh-skills | This is specific to the skills repository workflow. |
| Selecting topic computable files for a package workspace | rh-skills | This is repository-layout orchestration before invoking `rh package`. |
| Selecting fixture input resources to promote into package examples | rh-skills | Fixture source selection is workflow-specific; promoted examples become normal package examples. |
| Building and packaging example resources | rh | Once examples are under the package source directory, package build behavior is generic. |
| FHIR package build/check/pack behavior, including preserving package input folders in the final tarball | rh | This is package-tool behavior and should not be patched by rh-skills after build. |
| CQL parsing, ELM translation, expression evaluation, model choice-type semantics | rh | This is runtime/toolchain behavior. rh-skills should invoke it and report results. |
| Fixture discovery, topic-scoped drift reporting, validation gating | rh-skills | This ties runtime results back to topic workflow state. |
| Generic fixture execution format, if it becomes useful outside rh-skills | rh first, rh-skills wrapper | Avoid locking a reusable test runner into the skills repo. |
| FHIR server interaction for posting bundles and invoking `$r5.apply` | rh preferred | This is generic runtime smoke testing; rh-skills should call it once exposed. |
| Choosing which topic package, canonical, and fixture case to apply-smoke | rh-skills | This is workflow orchestration and user ergonomics. |
Design rule: rh-skills may stage files, call `rh`, parse machine-readable
results, and fail workflow gates. It should not compensate for missing generic
`rh` behavior by duplicating runtime/package internals.

## Phase 1: Optional Test Fixture Example Promotion

Add an opt-in path option to `rh-skills package <topic>` that copies selected
CQL fixture input resources into the package workspace's normal
`input/examples/` directory. rh-skills is responsible for preparing the package
source workspace from `topics/<topic>/computable/` and the explicitly supplied
fixture source directory; `rh package` remains responsible for normal
check/build/pack behavior.

Proposed command:

```bash
rh-skills package <topic> --include-test-fixtures tests/cql [--fixture-library LIBRARY] [--fixture-case CASE]
```

rh-skills behavior:

- Keep default behavior as fixture exclusion.
- Rebuild package workspace from `topics/<topic>/computable/` as today.
- Require `--include-test-fixtures DIR` to explicitly identify the fixture
  source directory.
- When `--include-test-fixtures DIR` is supplied, copy only supported fixture
  input resources from that directory into `package-workspace/input/examples/`.
- Include only:
  - `input/bundle.json`
  - `input/patient.json`, if present
  - `input/parameters.json`, if present
- Do not include:
  - `expected/expression-results.json`
  - `notes.md`
  - generated test reports
  - arbitrary fixture helper files
- Give copied examples normal FHIR package example file names derived from
  `resourceType` and `id`, such as `Bundle-case-a.json`.
- Include copied fixture examples in `ImplementationGuide.definition.resource[]`
  because they are promoted to normal IG examples.
- Invoke `rh package build <workspace>` without fixture-specific options.
- Report fixture library/case counts and copied example resource counts.

RH behavior used:

- `rh package build` should build and package normal IG examples from
  `input/examples/`.

Acceptance:

- `rh-skills package <topic>` without the flag does not package fixture data.
- `rh-skills package <topic> --include-test-fixtures tests/cql` copies supported
  fixture input resources into package examples and calls `rh package build`
  without fixture-specific options.
- Package output/tarball contains promoted fixture examples but not expected
  assertion files or notes.
- Promoted fixture examples are added to `ImplementationGuide.definition.resource[]`
  through the normal example resource path.

## Phase 2: No Dedicated Case Sync Command

Do not add a separate `case sync` command for package fixture inclusion. CQL
fixture cases are durable authored test inputs under `tests/cql/**`. When a
fixture changes, rerun:

```bash
rh-skills package <topic> --include-test-fixtures tests/cql
```

That rebuilds package workspace from `computable/`, promotes supported fixture
input resources from `tests/cql/**` to package examples, regenerates package IG
inputs, and delegates build/pack to `rh package`.

If a fixture case is renamed, the author should rename the fixture directory and
update `input/bundle.json` as part of normal fixture authoring. The subsequent
package run picks up the new path and drops the old path because package
workspace is recreated.

Acceptance:

- Package workspace and package output contain no stale promoted fixture
  examples after rerunning `rh-skills package <topic> --include-test-fixtures tests/cql`.
- rh-skills does not maintain a second identity-rewrite workflow for fixture
  cases.

## Phase 3: Apply Smoke Verification

Add a first-class apply smoke workflow that exercises the generated package
against a configured server/runtime without reimplementing generic apply
behavior in rh-skills.

Preferred shape once `rh` exposes a package/apply smoke primitive:

```bash
rh-skills package apply-smoke <topic> --server <FHIR_BASE_URL> [--case CASE] [--canonical CANONICAL]
```

rh-skills responsibilities:

- Run package preparation and package build.
- Select the package workspace/output, fixture case, and target canonical.
- Invoke the `rh` apply-smoke command with those paths and options.
- Parse machine-readable `rh` output, write a topic review report, and fail the
  rh-skills workflow gate when `rh` reports errors.
- Compare outputs, if requested, by:
   - `resourceType`
   - canonical URL
   - code/system where relevant
   - not generated ids

rh responsibilities:

- Build any transaction bundle needed from package resources and selected test
  input Bundles.
- POST package/test resources to the configured FHIR server.
- Invoke `$r5.apply`.
- Interpret OperationOutcome severities and diagnostics.
- Return a stable JSON result for rh-skills to report.

Temporary fallback:

- Until `rh` exposes this primitive, rh-skills should document the manual `rh`
  command sequence or mark apply smoke as unavailable. It should not grow a
  parallel HTTP/FHIR apply implementation.

Configuration:

- Read default server URL from `.rh-skills.toml`, e.g.:

```toml
[apply]
server = "http://localhost:8080/fhir"
```

- Allow CLI override with `--server`.
- Keep the command opt-in until local HAPI/RH server setup is stable.

Regression tests:

- Unit-test rh-skills command construction and parsing of mocked `rh` JSON
  output.
- Fail when mocked `rh` output reports OperationOutcome error diagnostics.
- Compare expected outputs by canonical when generated ids differ.

Acceptance:

- A topic can run a deterministic package/apply smoke test before release when
  the installed `rh` provides the apply-smoke primitive.

## Phase 4: CQL Test Drift Reporting and Gates

Make CQL fixture execution part of validation and packaging gates.

Implementation:

- Add a reusable CQL fixture orchestration service under `src/rh_skills/cql/`
  so `rh-skills cql test`, `rh-skills validate`, and `rh-skills package` share
  discovery, expected-result loading, and report writing.
- Delegate CQL evaluation to `rh cql eval` or a future `rh cql test`
  primitive. Do not parse or evaluate CQL in rh-skills.
- Add validation checks:
  - every fixture expected expression exists as a CQL define
  - every fixture has `input/bundle.json`
  - every fixture has non-empty `expected/expression-results.json`
  - every CQL library with fixtures can be evaluated successfully
- Add package gating:
  - package fails if matching fixtures exist and delegated CQL fixture
    execution fails
  - dry-run reports whether CQL tests would be run
  - allow temporary opt-out with `--skip-cql-tests`, but print a clear warning
- Add a report artifact:
  - `topics/<topic>/process/reviews/cql-test-report.json`
  - include case, expression, expected, actual, status, and delegated `rh`
    command/result metadata

Regression tests:

- Stale expected define fails validation before packaging.
- Failed runtime evaluation prevents package success.
- Missing fixture files fail with actionable messages.
- `--skip-cql-tests` bypasses runtime execution but records a warning.

Acceptance:

- CQL fixture failures cannot silently ship in a package unless explicitly
  skipped by the user.
- Any generic fixture execution enhancements discovered here should be proposed
  for `rh`; rh-skills keeps only topic-specific orchestration and gating.

## Phase 5: Runtime Conformance Notes

Do not add rh-skills lint rules or generation prompts that encode temporary RH
runtime limitations for FHIR choice types. The framework should keep CQL
authoring aligned to the intended CQL/FHIR model and use fixture execution to
catch runtime mismatches.

Implementation:

- Document known runtime compatibility issues in CQL test reports when they are
  observed.
- Prefer fixing RH runtime behavior over adding rh-skills CQL authoring
  workarounds.
- Keep any future choice-type linting standards-based rather than RH-bug-based.
- If a validation rule depends on RH runtime behavior rather than the CQL/FHIR
  model, keep it out of rh-skills and track it as an RH issue.

Acceptance:

- CQL choice-type behavior is validated through `rh-skills cql test`, but
  rh-skills does not prescribe temporary RH-specific access patterns.

## Suggested Implementation Order

1. Add CQL test runner service and drift reporting.
2. Wire CQL tests into `validate` and package gates.
3. Add opt-in fixture example promotion to `rh-skills package`.
4. Add runtime conformance reporting for fixture failures.
5. Add apply smoke wrapper after the corresponding `rh` primitive exists.

This order makes stale fixtures visible before packaging starts promoting them
to examples, then adds the heavier apply smoke workflow once the package
contents and CQL fixtures are reliable.

## Open Questions

- Should fixture inclusion support all libraries by default, or require
  `--fixture-library` to avoid accidentally packaging unrelated test data?
- Should apply smoke live under `rh-skills package apply-smoke` or
  `rh-skills verify apply` once the verify workflow is expanded?
- Should generic CQL fixture execution move fully into `rh cql test`, leaving
  rh-skills with discovery, topic gating, and report aggregation only?
- What minimum `rh` version should rh-skills require before enabling apply
  smoke gates?
