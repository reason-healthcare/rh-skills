# Live Connectathon readiness: 24-hour implementation plan

Prepared 2026-09-17. Status: execution started 2026-09-17 at 23:35 UTC / 19:35 EDT; target handoff 2026-09-18 at 23:35 UTC / 19:35 EDT. Follow [the progress journal](CONNECTATHON-JOURNAL.md) and [task ledger](connectathon-24h-status.json) for actual results.

**User constraint:** do not modify `hl7-agentic-knowledge-connectathon`, including its source files, fixtures and Git state. Treat it as a read-only source/oracle. All generated work, fixture adapters, logs and iteration artifacts belong in separate rehearsal workspaces or implementation repositories. Verify its source inventory remains unchanged at handoff.

## Required follow-up from user review — September 18

SDC Observation-based extraction is now part of the required primary workflow: **completed QuestionnaireResponse → actual SDC extraction → Observations → versioned ValueSet CQL → Measure and CPG results**. The earlier QR-reading run001/run002 packages remain frozen compatibility baselines. Their successful execution is not evidence for this new requirement. The generated Questionnaire must preserve the source SDC profile and extraction/category extensions through typed L2 metadata. Measure preview must expose the population definitions and their supporting logic, not only expression names.

ITER-026 owns the remaining sequence: (1) repair generic L2/formalization metadata and source inspection; (2) implement a shared, explicitly scoped Observation-based extractor and resolve actual terminology retrieval; (3) generate a separate run003 package through the framework; (4) prove extraction outputs and all48 source CQL assertions, plus adverse context/completeness/terminology cases, on native and WASM; (5) replay actual Workbench assessment/staging and standalone CPG; (6) update the live runbook, evidence and cold-start instructions. Keep unsupported extraction modes explicit. Only generated resources derived from the exact staged response may be reconciled. Expected fixture extraction files are comparison oracles, never substituted execution output.

ITER-028 adds the user's idiomatic CQL requirements to final acceptance. Create and link a reusable CQL style guide; rely on Patient-context retrieve scoping; use declared typed codes and the explicit FHIR R4 Encounter `class` path; preserve Observation-to-Encounter relationships with pinned `FHIRCommon.references()` and `with ... such that`. Fix runtime conformance defects instead of adding authored subject or string-code workarounds. A separate run004 revision must preserve all 66 clinical assertions and pass mixed-patient, wrong-code/system, wrong-encounter, incomplete and provenance cases through native and public WASM execution. Reference translation, final package validation, Workbench and standalone API/browser replay, and fresh skill installation remain separate gates. Keep run003 and earlier packages/evidence frozen.

## Outcome and scope

Prepare the skill framework and tools to be used **live at the Connectathon on Saturday, September 19, 2026**. The product of this sprint is a reliable authoring process and toolchain: an operator starts from clinical source material, follows the actual skills to create L2/L3, validates what was just generated, and opens those fresh outputs in Workbench and standalone CPG preview.

The STEADI package is a rehearsal output and regression reference. A polished prebuilt package alone does not satisfy this plan. The live run must succeed without copying generated L2/L3, CQL/ELM, or snapshot mappings from the rehearsal.

The seed is the community-dwelling ambulatory adult age 65+ workflow in `/Users/bkaney/projects/reason-healthcare/hl7-agentic-knowledge-connectathon`, revision `57f9e1a822108f7f2a13e9033a0ed5103f369b71`. Its six cases, eight named expressions, shared Questionnaire, and expected extraction resources are the acceptance oracle. AAO CRS remains a regression case; it is not this sprint's primary authoring target.

Required deliverables for Saturday:

- Repaired, version-pinned skills and tools, with a clean-workspace launch path, a live-session runbook, visible stage progress, and tested recovery commands.
- Two timed clean-source rehearsals that produce traceable L1, schema-valid L2, FHIR R4 L3, CQL/ELM, exact dependency versions, and authoring/review evidence by following the framework.
- A FHIR NPM package, a dependency-complete executable content Bundle, and a Workbench snapshot generated from that same revision. Patient fixtures are separate from executable knowledge content.
- Working Workbench guideline/CPG, measure, and assessment/Questionnaire previews, with a shared package inspector and connected L2/L3 navigation.
- The same package working in standalone CPG preview, with patient selection and real `$apply` execution independent of Workbench's database/session.
- A repeatable acceptance command, machine-readable results, screenshots, and a capability/limitation report suitable for deciding what to attempt live.

This is readiness to run the core authoring challenge live, not clinical approval or complete Connectathon certification. Actual SDC Observation-based extraction is required by the follow-up above. The track additionally requires two independent CQL implementations and round trips through two independent FHIR implementations. Keep those requirements visible and unpassed until demonstrated. Native and WASM builds of the same engine do not count as independent implementations. Broader interoperability and new engine features cannot displace a reliable live skills loop in this 24-hour window.

## Verified starting point

| Area | Evidence gathered during planning | Implication |
| --- | --- | --- |
| rh-skills | Local `main` is 22 commits behind freshly fetched `origin/main` (`eb28096`). | Execute from a clean branch/worktree based on current `origin/main`; do not assess the old installed CLI as current. |
| Workbench | Clean `cpg-phase-6` at `968c565`; CPG, Measure, Questionnaire routes, source actions, and L2/L3 chips exist. | Build on the implementation containing all Phase 6 work. |
| Other Workbench branch | Fresh `origin/cpg-preview-45` at `be756c1` is divergent; selecting it alone removes Phase 6 package persistence/navigation. | Reconcile required commits deliberately; do not choose a branch merely because its name or timestamp looks newer. |
| Snapshot generation | `scripts/build-aao-snapshot.mjs:59` copies package `output`, but not `executable`; artifact records at line 84 omit `derivedFrom`. | Generated snapshots lose runnable content and review-to-preview relationships. |
| Snapshot loading | `scripts/load-aao-snapshot.mjs:371` expects `topics/<topic>/process/package-workspace/executable/executable-bundle.json`. Import validation does not currently require a complete executable package. | Align producer, importer, persistence, and readiness checks. |
| Execution fallback | Workbench `$apply` route at line 83 falls back to a one-resource Bundle when the topic bundle is absent; other preview paths need the same audit. | Rendering a root resource cannot establish package readiness. |
| Packaging | Current rh-skills `origin/main` runs `rh package check/build/pack`; no `link` stage. Audited `rh-ws3` has no `rh package link`. | Recover or add a bounded, reusable execution-bundle builder; never document a nonexistent command as working. |
| Rust | Actual checkout is `/Users/bkaney/projects/reason-healthcare/rh-ws3`, `cpg-phase-4`, `fc96943a`; the configured sibling `/rh` does not exist. Workbench uses a local `@reasonhealth/cpg` dependency. | Pin/rebuild the real runtime; remove machine-specific assumptions from the demo handoff. |
| Standalone | `/Users/bkaney/projects/reason-healthcare/reason-framework/packages/cpg-review` loads packages and uses an external engine for `$apply`; it is not wired to Workbench's Rust runtime. | A successful Workbench run does not prove standalone works. |
| Authoring inputs | Connectathon repository contains sources and fixtures but no rh-skills topic, tracking, generated L2/L3, or executable package. | Start a clean authoring run, rather than re-labeling the existing AAO fixture. |
| CQL tests | Current rh-skills `origin/main` actually invokes `rh cql eval`; docs still contain obsolete “eval pending” text. Existing test adapter does not visibly forward patient/period context. | Reuse and harden actual execution; synchronize docs and prove context handling. |
| Measure capability | `rh-ws3/crates/rh-cpg/src/measure.rs` emits individual MeasureReports with a hardcoded single-day 2026-01-01 period; current wrapper does not expose a measurement-period option. | Correct context/period propagation for this case. A new aggregate MeasureReport engine is outside guaranteed scope. |
| Extraction capability | Rust Questionnaire support includes assembly, population and lightweight checks, but no `$extract` implementation. | Mark SDC extraction as a known challenge gap; timebox the narrow implementation only after the core is passing. |
| Design | Workbench has project-local Impeccable v3.8.0, `apps/workbench/PRODUCT.md`, `DESIGN.md`, and `.impeccable/design.json`. | Use the existing calm clinical review system and real design skill. |
| Live services | No Workbench database or terminology container was running at audit time. | Runtime/browser acceptance remains pending. |

Read current files again at T0 and record full SHAs. Branch names and these observations are a planning snapshot, not a substitute for final verification.

## Package completeness contract

“Complete package” has three independently tested meanings:

1. **Content is present:** every authored resource in the distribution inventory is visible, including Evidence, EvidenceVariable, Library, ValueSet, ActivityDefinition, ImplementationGuide, and resources without a specialized preview. Provide counts by type, canonical/version, title, source, and a source/download action. Account for package dependencies explicitly.
2. **Content is connected:** guideline, measure, and assessment roots resolve their transitive execution dependencies by canonical and exact version. Each generated preview root links to its actual L2 artifact IDs; each relevant L2 artifact exposes all its generated L3 roots. Related evidence and terminology are accessible from those roots.
3. **Content executes:** Workbench and standalone use the same checked executable knowledge inventory. Required ELM, included Libraries, FHIRHelpers when used, and complete unfiltered ValueSet expansions are available. All references used during execution resolve without an external terminology/FHIR fetch.

Generate a package inventory/lock with package ID/version, FHIR version, source revision, resource identities/checksums, dependency versions, and execution-bundle checksum. Resolve ambiguous duplicate canonicals as errors. Make authored roots and imported dependencies distinguishable. Do not merge patient records into the shared knowledge inventory.

Reject invalid mappings or unresolved execution dependencies at build time. Workbench may still import an incomplete snapshot for review, but it must label it “Preview unavailable — package incomplete,” name the missing dependency, and disable execution. The Connectathon acceptance command must fail such a snapshot. Eliminate the silent single-resource fallback for package-backed execution.

Regenerating/importing a snapshot must not leave stale executable content behind if its source bundle disappears. Preserve project/snapshot authorization for package inspection and downloads. Changes must not overwrite unrelated review decisions or demo data.

## Execution schedule and ownership

Use one coordinating frontier agent plus at most three workers. Default workers: `gpt-5.6-terra` with high reasoning for code/runtime work, `gpt-5.6-luna` with high reasoning for authoring/replay/evidence. Announce actual model/effort on each spawn. Owners have separate files/worktrees; shared package contracts are agreed before parallel implementation.

| Window | Owner/workstream | Concrete work | Exit gate |
| --- | --- | --- | --- |
| T+0–2h | Lead + runtime worker | Refresh refs; isolate clean working branches; inventory engines, package builder, validator, and local services. Run one real CQL expression with patient + fixed period and one full-package `$apply`. Freeze manifest/bundle contracts and design brief. | G0: exact baselines and feasibility report; executable path chosen; no assumed `link` command. |
| T+2–7h | Skills worker | Follow current skills in a new STEADI workspace from pinned source corpus; generate L2, formalize L3, translate CQL; capture prompts/decisions and fix generic skill/schema defects. | G1: valid L2/L3, complete inventory, no placeholder logic/terminology. |
| T+2–7h | Runtime/package worker | Implement/recover bounded executable bundling, fixture adapter with patient/date parameters, and dependency checks. Probe standalone Rust integration early. | G2: complete content Bundle and actual execution results for all six cases. |
| T+2–7h | Workbench worker | Repair generic snapshot export/import and `derivedFrom`; add package-readiness state and shared inventory UI following Impeccable. Start local app early enough to inspect actual behavior. | G3a: generated snapshot imports with complete, inspectable content. |
| T+7–12h | Workbench + runtime | Wire all three previews to the package; named fixture selector; actual CPG results, individual measure reports, and assessment completion. Fix period/context propagation. Use failures to repair upstream generators. | G3b: six fixtures agree with expression/applicability oracle through Workbench APIs; negative package cases fail visibly. |
| T+7–12h | Skills worker + lead | Finish provenance/conformance checks; verify clinical assertions against sources; repair skill instructions, examples, and documentation; begin an independent clean skill replay. | G4a: authored source-to-result trace and replay differences recorded. |
| T+12–16h | Runtime worker | Finish the bounded standalone adapter (2–3h budget) and compare normalized results. Implement and verify metadata-driven Observation extraction for the declared Boolean subset as required by the follow-up scope. | G4b: standalone runs independently; actual extraction is demonstrated before primary-path acceptance. |
| T+12–16h | Workbench worker | Impeccable critique/audit and focused fixes to the shared preview surface; keyboard/responsive checks; clear loading/error/unknown states. | G5: coherent flow, no blocking design/accessibility defects. |
| T+16–20h | Lead + workers | Timed live-authoring rehearsal from empty workspace, independent repeat and small input variation; package/snapshot rebuild; integration tests and relevant final-revision builds. Repair only demonstrated blockers. | G6: repeatable skill process, measured stage durations, and passing acceptance report. |
| T+20–24h | Lead | Freeze scope. Saturday-style cold-start/recovery rehearsal, authenticated preview walkthrough, external terminology outage check, screenshots and final runbook. | G7: live-readiness decision with exact tools/revisions, observed time, and declared limitations. |

Target about 18–20 hours to working acceptance plus 4 hours of contingency/rehearsal. Parallel work provides roughly 35–45 focused worker-hours; these estimates assume one narrow STEADI slice and reuse of existing runtimes. The protected core is live authoring/replay, package completeness, existing preview capabilities, and a bounded standalone adapter. New cohort execution, broad SDC work, and decorative redesign are excluded from that estimate. A large newly discovered engine defect may still prevent a ready result; the gates must expose that rather than hide it.

## Workstream A: prove the skills, not just a hand-fixed package

Use current source skills under `skills/.curated/`: discovery, ingest, extract, formalize, CQL, verify, status, and resolve when relevant. Install the generated skill bundle into the isolated authoring workspace and record its checksum. Preserve the implementation-neutral upstream corpus and fixtures.

1. Verify source-manifest checksums; ingest the supplied PDF/HTML snapshots. Preserve source locators and redistribution notes. Keep comparison-only material such as CMS139FHIR link-only. Follow the corpus NOTICE: retain restricted sources unchanged; keep normalized working copies private and use source links in a shared snapshot where redistribution of transformed content is not established. The core demo can use the CDC/USPSTF/AHRQ sources without adding a source-rights decision to its critical path.
2. Register a `steadi-fall-screening` topic with evidence/population, assessment, decision-table/guideline logic, screening-completion measure, and terminology L2 artifacts. Start with one guideline execution root; converge overlapping decision-table/care-pathway representations rather than creating duplicate competing PlanDefinitions. Distinguish source statements from track-authored operational decisions.
3. Validate L2 semantics and schema before formalizing: eligibility, completion, null behavior, measurement period, evidence links, and the eight named expressions must be explicit.
4. Formalize FHIR R4 4.0.1 resources: Evidence/EvidenceVariable, Questionnaire, PlanDefinition/ActivityDefinition, Measure, Libraries, ValueSets, and ImplementationGuide. Preserve question linkIds and LOINC codes, plus canonical/version identity or a documented mapping to the shared Questionnaire. Do not emit R5 Citation into R4.
5. Translate actual CQL to ELM JSON and embed/reference it correctly in Libraries; re-formalize after translation when required by the generator to refresh Library content. Execute expressions using real patient data. Ban constant/stub replacements that merely satisfy fixtures.
6. Validate resources with the HL7 validator using exact dependency versions, including SDC 4.0.0 for the supplied extraction contract. Treat warnings individually; do not mark a run “validated” when terminology checks were skipped without recording that limitation.
7. Generate ordinary package, executable bundle, and Workbench snapshot from one source revision. Derive mappings and inventory mechanically. Use the disposable workspace even for packaging `--dry-run`: the current command stages files before reaching its dry-run branch.
8. Repeat from a second empty workspace using the repaired skills. The second authoring run must not copy generated L2/L3 from the first. Record prompts/model/version, authoring time, intervention time, revision count, defects, and semantic differences.

Fix defects in the smallest reusable owner: skill instructions, CLI/schema/generator, packaging, runtime, or UI. Regenerate downstream output after each repair. A manual artifact edit is an experiment until its generalizable cause is fixed and clean replay succeeds. Do not edit the shared acceptance assertions to match the implementation.

Deterministic rebuild from identical accepted L2/CQL must produce equivalent locked content (normalize only documented timestamp/order noise). Independent AI authoring is tested for semantic equivalence and traceability, not identical prose or byte-for-byte output.

## Workstream B: execution and test matrix

Use `test-bundles/manifest.json`, each `assertions.json`, and each `extracted-bundle.json` as input. Adapt them into rh-skills' `tests/cql/<library>/case-*/input/bundle.json` and `expected/expression-results.json` layout without changing the oracle. Preserve exact Boolean versus null types, patient context, encounter, measurement period, and a fixed evaluation clock. Missing parameters, evaluation errors, and unsupported operations are failures, not null results.

| Shared case | In population | Screen complete | Increased risk / exercise / multifactorial | Numerator | Extracted final Observations |
| --- | --- | --- | --- | --- | --- |
| younger-than-65 | false | true | false / false / false | false | 3 |
| eligible-all-no | true | true | false / false / false | true | 3 |
| eligible-unsteady-yes | true | true | true / true / true | true | 3 |
| eligible-prior-fall-yes | true | true | true / true / true | true | 3 |
| eligible-incomplete-response | true | false | null / null / null | false | 0; no extraction invocation |
| eligible-no-response | true | false | null / null / null | false | 0; no extraction invocation |

Initial Population and Denominator follow the population column. The oracle implies totals 5/5/3 and proportion 0.6 across these fixtures. The required 24-hour implementation produces actual **individual** MeasureReports for the six patients and checks their period/populations. A test-harness summary may show the oracle totals if clearly labeled; do not present it as an engine-generated aggregate MeasureReport. A true cohort evaluator is a separate extension.

Required execution checks:

- All 48 named expression assertions, independently from CPG applicability and measure presentation.
- CPG `$apply`: applicable actions and evidence links for positive cases; no affirmative guidance for incomplete/absent/out-of-scope cases; explicit explanation of unknown versus inapplicable.
- Assessment: Boolean answers can remain unanswered; no default false. Three required usable answers plus `completed` status are required. Editing an answer invalidates stale results. Validate before marking complete.
- SDC extraction capability check: report whether completed responses actually yield three final Observations with code/value, patient, encounter, author, authored time, and `derivedFrom`. Incomplete/absent responses must never produce final observations. If extraction is unsupported, mark the positive extraction assertions unsupported and retain them as an explicit unmet track requirement. A displayed precomputed expected Bundle is not an extraction implementation.
- Measure: individual reports for all six patients, explicit correct period, actual population membership/counts, and the distinction between a missing screen and a negative completed screen.
- Mutation cases: exactly age 65; period boundary/outside period; completed status with a missing answer; partial affirmative response; wrong answer type; mismatched Questionnaire canonical/version; missing Library/ELM/ValueSet; duplicate canonical; wrong patient context. Derive expected behavior from the frozen contract and record any genuinely unspecified policy separately.
- Packaging: remove a dependency and ensure build/readiness fail; exercise multiple L3s per L2, non-previewable resources, versioned references, and stale bundle replacement.
- Runtime parity: compare same inputs/content across native CLI, Workbench runtime, and standalone. This is regression evidence, not independent-engine interoperability evidence.

If core readiness is already green, allow up to two hours for the standard Observation-based extraction mechanism needed by this Questionnaire, with metadata-driven handling and tests. Otherwise preserve it as a declared challenge gap. Do not hardcode the three expected output resources, remove extraction expectations, or attempt broad SDC support during this sprint.

Existing command families to use after T0 verifies installed versions:

```text
rh-skills init steadi-fall-risk
rh-skills validate <topic> l2 <artifact>
rh-skills validate <topic> l3 <artifact>
rh-skills formalize <topic> <artifact>
rh-skills cql validate <topic> <library>
rh-skills cql translate <topic> <library>
rh-skills cql test <topic> <library>
rh-skills package <topic> --pack --include-test-fixtures <fixture-dir>
uv run pytest
npm run check
npm run build
cargo test -p rh-cpg
```

These are component gates, not a working end-to-end recipe today. `--include-test-fixtures` is present in the inspected `origin/main`; it is absent from the stale local checkout. Add and document a single acceptance entrypoint during implementation that builds the fixture adapter, validates/links content, exports/imports the snapshot, executes the matrix, and emits nonzero on required failures. Its report must distinguish pass, fail, unsupported, and not run; full-track acceptance fails while extraction/interoperability remains unpassed. Confirm CLI flags with `--help`; do not assume historical `rh package link` exists. Run focused packager/CQL/WASM tests when those modules change.

## Workstream C: shared Workbench preview experience

Design skill: [`impeccable`](/Users/bkaney/projects/reason-healthcare/workbench/.agents/skills/impeccable/SKILL.md), using the Workbench product register and committed design system. Its context command has been run for `apps/workbench` during planning; it found PRODUCT.md and DESIGN.md. Use v3.8.0 for this sprint unless the optional update is explicitly selected.

Design brief:

- **Audience and scene:** a clinical reviewer and presenter inspecting a case on a laptop/projector in a bright conference room; prioritize clear labels, readable results, and predictable navigation.
- **Primary action:** start at the L2 artifact, choose “Try guideline,” “Try measure,” or “Try assessment,” select a named patient scenario, run it, and understand the result and supporting evidence.
- **Visual direction:** preserve ReasonHealth deep teal, action green, Roobert, quiet surfaces, and the existing Asana-inspired hierarchy. Workbench's current review surface is the primary reference. Clinical terminology stays precise.
- **Scope:** production-quality behavior for this three-preview flow and a reusable package inspector, within the 24-hour sprint. No app-wide redesign or new component framework.
- **Layout:** persistent artifact/package identity and return-to-review link; compact scenario/run controls; main result area; progressive “Package contents,” “Evidence,” and “Source” details. On smaller screens, collapse supporting panels before reducing text size.
- **Package inspector:** searchable resource table/grouped list with type counts, version, dependency relationship, and source access. Show every authored resource even if its renderer is generic. Root selection must not silently hide the rest of the package.
- **CPG:** show nested actions and resolved ActivityDefinitions; distinguish the authored pathway from actions applicable to the selected patient.
- **Measure:** show purpose, period, eligibility, populations and counts, then MeasureReport/source details. No unexplained raw JSON as the primary result.
- **Assessment:** three labeled Boolean questions with explicit unanswered state, completion validation and risk outcome. Show extracted resources/provenance only if extraction actually runs; otherwise label the capability as unavailable.
- **States:** loading, ready, incomplete package, missing patient data, unanswered assessment, true/false/unknown, unsupported feature, execution error, and stale result. Use actionable text and preserve current input during errors.

Apply Impeccable's product/interaction guidance during implementation, then run `critique`, `audit`, targeted `harden`/`polish`, and re-check. Keep the shared component rules, DESIGN.md/design.json where changed, and UI behavior synchronized. New raster mockups are unnecessary for refinement of this established interface.

Visual acceptance: authenticated screenshots at 1440×900 and 1024×768, narrow-screen overflow check, keyboard-only run and source inspection, visible focus, contrast checks, color-independent statuses, and reduced motion. No console/hydration errors, clipped controls, nested interactive links, stale results, or unexplained blank/error screens. Use browser interaction, not HTML/source inspection alone, as evidence.

## Workstream D: standalone CPG preview

Target the existing `reason-framework/packages/cpg-review` application. Preserve its package upload, graph, and patient-selection affordances. Prefer a bounded adapter to the same pinned `@reasonhealth/cpg` Rust/WASM runtime already used by Workbench, passing the complete knowledge Bundle plus separate patient context. Preserve R4 RequestGroup semantics; do not silently substitute an R5 operation.

Run the feasibility spike by T+2h. If browser/WASM wiring is impractical but the same runtime can be exposed through a small local adapter, that is an acceptable declared demo mode: it must run without Workbench authentication/database and must use the same package and engine. Do not introduce HAPI as a new required execution dependency or maintain a second clinical logic implementation just to meet the clock.

If neither path works within the allocated window, retain the passing Workbench demo and report standalone as an unmet P0. A graph-only package rendering is not completion of the standalone execution goal.

## Terminology decision and integration

The new local hub-distribution API is a suitable contract for build-time terminology work, conditional on a complete installed release with the needed versions. Live planning evidence:

- Started the existing image `rh-terminology-lite:2026.1.6-3204e340` briefly in a read-only temporary container on loopback port 18080, then stopped/removed that container.
- Health and metadata returned 200. Releases identified the content as `fixture`, `complete=false`, with only three LOINC concepts at `dev-lite-2026-08-20`.
- An actual STEADI search returned unrelated fixture lab codes. Expanding the three required question codes at LOINC 2.81 returned 404: requested CodeSystem release unavailable.
- Connected ReasonHub MCP successfully looked up all three LOINC 2.81 concepts as active and expanded the exact three-code ValueSet with total 3. No password file was needed.

Execution update (2026-09-17 19:53 EDT): an existing Full image was found and tested on isolated port 18085. STEADI search and exact three-code expansion pass at its installed LOINC 2.82; fixture-pinned 2.81 is unavailable. Continue using ReasonHub for 2.81 membership while retaining the local API as a verified 2.82 discovery/expansion option. See [the probe evidence](connectathon/evidence/local-full-terminology.json).

At execution, spend at most 60–90 minutes locating/starting an already-qualified Full image containing the required versions. Do not begin a production terminology rebuild/release project. If unavailable or version-incompatible, use the verified ReasonHub MCP fallback and record the provider explicitly.

Build-time adapter requirements:

1. Discover exact `(system_uri, source_version)` through `/v1/releases` and verify content/retrieval readiness.
2. Use `/v1/search` only for candidate discovery. Resolve and verify chosen codes; do not infer membership from semantic rank.
3. Expand governed, version-pinned ValueSets through `/fhir/R4/ValueSet/$expand`, with no semantic `filter` when materializing the complete executable membership. Page until complete and compare returned membership with `expansion.total`.
4. Honor documented API bounds: at most 100 results/page and `offset + count <= 1000`. Reject truncation, unsupported nested composition, unavailable versions, and unsupported filters rather than silently weakening the ValueSet. The three-code STEADI set fits these bounds.
5. Persist provider, exact versions, definition/expansion hashes and expansion evidence with the package. Do not silently switch terminology versions between providers.
6. Pre-expand at build time; preview execution consumes the pinned local content. Verify the demo still runs when external terminology access is unavailable.

The local API's `Authorization` value is a stable gateway-owned scope, not the ReasonHub bearer key. Keep authentication server-side. If fallback credentials are ever needed, retrieve only the necessary ReasonHub entry from `~/passwords`, never print or commit it, and send it only to the intended ReasonHub endpoint.

## Unattended iteration and resumption

After execution is requested, continue through routine coding, local builds, tests, design fixes, and demo preparation without phase-by-phase permission prompts. This plan does not schedule an automation or claim that implementation is already running.

Maintain `docs/connectathon-24h-status.json` as the manual orchestration/resumption record and a run-specific evidence directory outside committed secrets/protected content. Also capture actual framework state with `rh-skills status show <topic> --json`; the manual ledger is not proof of skill lifecycle completion. At each checkpoint record: current branch/SHA per repo; task/owner; start/end; exact command; exit code; artifact hashes; evidence paths; defect severity; next action. Only mark a gate passed after inspecting the evidence.

Iteration loop:

1. Select the highest-priority failing gate and give one owner a bounded task with an acceptance condition.
2. Reproduce the failure and classify it: source interpretation, L2 schema, formalization, terminology, package closure, runtime, snapshot, or UI.
3. Repair its reusable cause, regenerate affected artifacts, and run focused checks.
4. Independently inspect the change and rerun the affected end-to-end case. Do not accept a worker's summary as the only proof.
5. Record progress and move to the next failing gate. Batch full-suite execution at integration checkpoints; repeat it after final code changes.

Use checkpoint commits on task branches after verified units of work; preserve unrelated dirty work and existing stacks. One owner handles cross-repo integration. Do not merge, publish packages, deploy publicly, send messages, or replace existing demo data as an inferred extension of this local readiness sprint. Execution authorization covers routine technical iteration within this plan. Record automated technical reviews as automated; never fabricate a human clinical approval to satisfy a skill lifecycle gate. Keep clinical approval pending while continuing independent demo work.

If stuck for 45–60 minutes, re-scope the fix, use an already-defined fallback, or record the blocker and work on an independent gate. A dependency unavailable for two hours triggers the timebox decision below. Ask only for decisions that cannot be inferred: changed clinical meaning, access that is genuinely unavailable, destructive actions, or a new external publication scope. Silence is never clinical approval.

## Timebox decisions and cut line

| Checkpoint | Decision |
| --- | --- |
| T+2h | If a broad linker is absent, implement a bounded reusable composer from staged resources + exact cached dependencies + verified expansions, with strict closure validation. Do not start a universal package resolver rewrite. |
| T+2h | If Full terminology is unavailable, proceed with verified ReasonHub MCP and pinned expansions. The lack of Full does not block the local demo. |
| T+7h | If STEADI execution is not passing, devote runtime/skills workers to it; freeze decorative work. Preserve all six original cases and unknown semantics. |
| T+12h | If standalone remains blocked, choose the bounded same-runtime local adapter or explicitly record unmet P0. Do not hide the failure behind a screenshot. |
| T+16h | Stop new features. Finish whole-package visibility, three previews, standalone, and clean replay. Defer additional cases/artifact renderers beyond the required contract. |
| T+20h | Freeze scope and run final revision checks/rehearsal. A failing P0 produces a partial-readiness report, not a demo-ready label. |

Deferred from the guaranteed 24-hour core: new cohort MeasureReport evaluation, SDC extraction beyond a successful bounded spike, universal terminology compatibility, unrelated AAO refactors, full application redesign, public deployment, package publication, clinical sign-off, and independent-engine/server interoperability. Extraction remains required by the full track even when deferred from preparation; the final capability report must say so.

## Saturday live-session rehearsal and runbook

The decisive test is whether an operator can use the standard installed skills, following the runbook, without the preparing agent supplying undocumented knowledge or patching generated output. A fresh worker performs the second rehearsal using only the pinned framework, source inputs, public scenario requirements and runbook. Keep generated rehearsal artifacts out of that worker's input.

Preflight the actual laptop/environment: tested CLI/model versions, installed skill bundle, validator and exact standards dependencies, local app/runtime builds, credentials, model access, sufficient disk, and occupied ports. Pre-download tools and standards packages, and verify the source corpus hashes; these caches do not contain generated clinical artifacts. Freeze the tested toolchain Friday and avoid untested updates on Saturday.

The live sequence is:

1. Create a new workspace/run ID; show empty generated-content directories and register the supplied sources.
2. Invoke discovery/ingest and extraction through the actual skills. Show source locators, proposed L2 structure, and the human decisions the framework requests.
3. Produce/review L2, then formalize and author CQL/ELM. Show progress and framework status rather than a long silent model call.
4. Run schema/FHIR validation and the six-case execution checks. Explain actual diagnostics, fix through the framework, and regenerate when needed.
5. Build/link/package and import the snapshot emitted by this run. Open guideline, measure and assessment previews and inspect package contents/source.
6. Load this run's package into standalone CPG preview and perform `$apply`. Show unresolved capabilities explicitly.

Measure first-use setup separately from source-to-preview duration, along with model latency, human-review time, revision cycles, and undocumented interventions. Use a **provisional 60-minute rehearsal target after prepared-tool preflight**, to be adjusted to the actual Saturday slot. It is an observed target, not a guarantee or a reason to skip required validation.

Run one small input variation in the second rehearsal: change a nonclinical source title/identifier and a synthetic patient's identifying/reference data; add the already-defined complete “worries about falling = yes” scenario. Generated provenance/references and evaluation must follow the inputs. Do not change clinical thresholds ad hoc. Keep the original shared cases unchanged and classify added cases separately. This probes accidental hardcoding without creating a second guideline project.

Exercise recovery from one interrupted authoring stage, one intentional validation failure, and loss of terminology network access. Resume from an explicit checkpoint; never silently load a prepared answer. If the authoring model itself is unavailable and no tested alternate exists, say the live generation is blocked. A labeled prior rehearsal can illustrate outputs, but it does not count as successful live authoring.

The final runbook contains exact tested commands/prompts and expected visible stages, operator decision points, fresh-workspace reset, links/ports, safe restart/resume steps, and the observed timing. Record which steps still require human judgment on Saturday; unattended preparation must not invent those approvals.

## Final acceptance and demo

P0 means mandatory; P1 is desirable only after all P0 gates pass.

| ID | Priority | Pass evidence |
| --- | --- | --- |
| G0 | P0 | Exact source/tool/runtime revisions; one real context-aware execution; chosen standalone and package paths. |
| G1 | P0 | Clean-source skill run, valid L2/FHIR R4 L3/CQL/ELM, no placeholders, traceability and exact terminology. |
| G2 | P0 | Complete locked package + executable Bundle + snapshot; 48 expression assertions and six individual MeasureReports with correct context/period pass; extraction capability is reported honestly. |
| G3 | P0 | Workbench imports the generated snapshot; all content is inspectable; all three previews use the complete bundle; L2/L3 links and negative readiness tests pass. |
| G4 | P0 | Standalone loads the same package and performs actual `$apply` for positive, negative, and unknown cases with parity across all six cases. |
| G5 | P0 | Impeccable-guided browser review, keyboard/contrast/responsive checks, and actionable states; no blocking UI defects. |
| G6 | P0 | Two timed clean-source skill runs, independent replay/input variation, and deterministic rebuild evidence; relevant final-revision tests/build pass. |
| G7 | P0 | Saturday live-session runbook and recovery exercised; measured source-to-preview duration and final capability/evidence manifest. |
| X1 | P0 for the declared Boolean extraction subset; broader interoperability remains separate | Actual SDC extraction passes all completed and incomplete/absent cases with provenance. |
| M1 | P1 | A genuine cohort MeasureReport evaluator emits the verified aggregate; not a mislabeled harness summary. |
| I1 | P1 for this sprint; required by full track | Two independent CQL engines agree and two FHIR implementations round-trip the artifacts; report separately. |

The short output walkthrough follows the live generation: open the new STEADI L2/source → inspect its package → try a positive assessment and applicable guideline actions → switch to incomplete response and show unknown/no final Observations → run an individual MeasureReport with the correct period → open this same package in standalone CPG preview. Include actual extraction or aggregate reports only after their separate gates pass.

Handoff includes the tested skill/tool versions, launch and stage commands/prompts, observed live-authoring timing, recovery steps, framework status, named fixture selector, package/snapshot checksums, screenshots of all three previews and package contents, final test report, and explicitly outstanding requirements. No need for a presenter to paste JSON during the normal preview walkthrough. The readiness decision is “ready to attempt the live core” only when G0–G7 pass; it is not “full track complete” while X1/I1 remain open.

## References for execution

- Connectathon source contract: `/Users/bkaney/projects/reason-healthcare/hl7-agentic-knowledge-connectathon/README.md`, `sources/manifest.yaml`, `test-bundles/README.md`, and `test-bundles/manifest.json`.
- Workbench implementation: `scripts/build-aao-snapshot.mjs`, `scripts/load-aao-snapshot.mjs`, `packages/rh-skills-importer/src/index.ts`, snapshot preview routes, and `packages/workbench-core/src/db/review-read-repository.ts`.
- Workbench design: `/Users/bkaney/projects/reason-healthcare/workbench/.agents/skills/impeccable/SKILL.md`, `apps/workbench/PRODUCT.md`, `apps/workbench/DESIGN.md`, and `apps/workbench/.impeccable/design.json`.
- Terminology API: `/Users/bkaney/projects/reason-healthcare/hub-distribution/terminology-api/docs/FHIR-R4.md`, `AUTHORIZATION.md`, and `contracts/v1.openapi.json`.
- HL7's [artifact packaging guidance](https://hl7.org/fhir/uv/cpg/packaging.html) distinguishes knowledge artifacts, dependencies and test content, including target-environment packaging. Resolve exact IG package versions before validation; do not use an unversioned web page as the dependency lock.
- The supplied extraction fixtures target the [SDC Observation extraction profile](https://hl7.org/fhir/uv/sdc/STU4/en/StructureDefinition-sdc-questionnaire-extr-obsn.html); preserve their normalized comparison contract and pin `hl7.fhir.uv.sdc#4.0.0`.

## Execution handoff — September 18

**Final acceptance reopened after user review.** Run001/run002 remain historical QR-based rehearsals. Run003 verifies the actual SDC Observation pipeline and all three complete-package Workbench previews, with the documented zero-denominator MeasureReport validator exception. Run004 is the pending context-correct, idiomatic CQL revision; it must pass the current runtime, package and application gates before becoming the primary demo candidate.

Use the [live runbook](connectathon/LIVE-RUNBOOK.md), [journal](CONNECTATHON-JOURNAL.md), [acceptance tools](connectathon/tools/PROVENANCE.md), and [evidence manifest](connectathon/evidence/final-readiness.json) for current status. The two source authoring rehearsals retain their recorded timing and context-reuse limits; run003/run004 are revisions, not additional independent authoring samples. Clinical approval, cohort Measure execution and independent engine/server interoperability remain open. The protected Connectathon repository is unchanged. Changes remain on local task branches; no publication, deployment or merge was performed.
