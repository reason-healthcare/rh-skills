# Feature Specification: rh-cql — First-Class CQL Authoring, Review, Debug, and Test-Generation Skill

**Feature Branch**: `014-rh-cql-skill`
**Created**: 2025-07-17
**Status**: Draft
**Input**: New first-class curated skill for Clinical Quality Language (CQL) authoring, review, debugging, and test-generation in the reason-skills-2 project.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Author a CQL Library from Structured Artifacts (Priority: P1)

A clinical informaticist has one or more L2 structured artifacts (measure definition, decision table, or policy) approved and ready for formalization. They invoke the `rh-cql` skill in `author` mode and receive a complete, standards-conformant CQL library file plus its FHIR Library wrapper JSON, ready for packaging.

**Why this priority**: CQL authoring is the core value proposition of this skill and the most frequently exercised path. Every downstream mode (review, debug, test-plan) presupposes a library exists. Delivering correct, rubric-compliant CQL from structured inputs is the minimum viable outcome.

**Independent Test**: Can be tested end-to-end by providing a single L2 structured artifact (e.g., a measure definition YAML) and verifying that a `.cql` file and a FHIR Library JSON are produced, that the CQL syntax is valid (translator reports zero errors), and that all rubric checklist items pass.

**Acceptance Scenarios**:

1. **Given** an approved L2 structured artifact for a measure or policy, **When** the agent operates in `author` mode with `rh-cql`, **Then** it produces a `.cql` file with a correct model declaration, library name/version, included libraries, terminology declarations, and fully documented `define` statements.
2. **Given** the authored `.cql` file, **When** the agent calls `rh-skills cql validate <topic> <library>`, **Then** the CQL translator reports zero syntax or semantic errors.
3. **Given** the authored `.cql` file, **When** the agent generates the FHIR Library wrapper, **Then** the JSON resource includes correct metadata, encoded CQL content, and dependency declarations consistent with the CQL library header.
4. **Given** a structured artifact that references one or more value sets, **When** the agent authors the CQL, **Then** all terminology declarations include explicit version pins and are sourced from resolved codes already present in the L2 artifact.
5. **Given** the authored library, **When** the rubric auto-check runs, **Then** zero blocking rubric violations are present (all ten rubric areas are addressed).

---

### User Story 2 — Review an Existing CQL Library Against Standards Rubrics (Priority: P2)

A clinical informaticist or measure developer has an existing CQL library (from any source: hand-authored, previously generated, vendor-supplied) and wants a structured quality review before it proceeds to packaging or publication.

**Why this priority**: Review mode is the second most common use case and the primary quality gate for CQL libraries that pre-exist or were not authored through this skill. It delivers standalone value without requiring authoring to have happened first.

**Independent Test**: Can be tested by providing any valid `.cql` file and verifying that a Markdown review report is produced containing findings categorized by severity (blocking / advisory / info) across authoring, packaging, and runtime rubric areas.

**Acceptance Scenarios**:

1. **Given** a `.cql` file at a known path, **When** the agent operates in `review` mode, **Then** it produces a structured Markdown review report with findings organized under the authoring rubric, packaging rubric, and runtime/high-risk-pattern categories.
2. **Given** a library that contains one or more high-risk patterns (unpinned terminology, ambiguous null handling, overly broad retrieves), **When** the review runs, **Then** each pattern is flagged with a `BLOCKING` or `ADVISORY` severity, a quoted evidence excerpt from the library, and a concrete recommended fix.
3. **Given** a library that passes all rubric checks, **When** the review runs, **Then** the report indicates "no blocking findings" and lists any informational observations.
4. **Given** a review report with blocking findings, **When** the findings are presented, **Then** every blocking finding identifies the specific line or expression causing the concern, not just the category.
5. **Given** the review report, **When** it is used as input to `rh-skills verify`, **Then** the verify command can accept the report as evidence of review completion and record it in the topic's tracking state.

---

### User Story 3 — Debug a CQL Library Given a Failing Test or Translator Error (Priority: P3)

A measure developer has a CQL library that fails to translate, produces unexpected results at runtime, or has a failing test case. They invoke `rh-cql` in `debug` mode with the library and the error message or failing test, and receive a diagnosis report with a minimal patch suggestion.

**Why this priority**: Debug mode closes the authoring feedback loop and reduces the time spent on iterative trial-and-error. It is lower priority than authoring and review because it applies to a subset of scenarios (libraries that already fail), but it is high-value when needed.

**Independent Test**: Can be tested by providing a CQL file with a known syntax or semantic error and a translator error message, then verifying that the diagnosis report correctly identifies the root cause and proposes a minimal corrective change.

**Acceptance Scenarios**:

1. **Given** a `.cql` file and the output of `rh-skills cql validate` containing one or more errors, **When** the agent operates in `debug` mode, **Then** it produces a diagnosis report that maps each error to the specific expression or declaration responsible.
2. **Given** a diagnosis report, **When** a patch is suggested, **Then** the suggestion is the minimal change that resolves the identified root cause — not a rewrite of unrelated logic.
3. **Given** a failing test case (input fixture + expected result + actual result), **When** the agent operates in `debug` mode, **Then** it identifies which `define` statement produces the unexpected result and explains the semantic mismatch (e.g., null propagation, interval boundary, date precision).
4. **Given** a runtime error attributed to a missing value set or unresolvable library dependency, **When** the agent debugs, **Then** it distinguishes between authoring errors (resolvable by editing CQL) and environment errors (resolvable by fixing the execution context or tooling setup).

---

### User Story 4 — Generate a Test Plan and Fixture Skeletons for a CQL Library (Priority: P3)

A measure developer wants to build a fixture-based test suite for a CQL library. They invoke `rh-cql` in `test-plan` mode and receive a test plan document and a skeleton directory of fixture files covering every `define` statement, including positive, negative, null, and boundary cases.

**Why this priority**: Test-plan mode is equal in priority to debug mode. It enables quality assurance that is currently absent from the CQL lifecycle within this project. It is lower than authoring and review because libraries must exist before tests can be generated.

**Independent Test**: Can be tested by providing a CQL file and verifying that a test plan Markdown document and at least one fixture skeleton directory are produced, with fixture files structured according to the standard test architecture.

**Acceptance Scenarios**:

1. **Given** a `.cql` file, **When** the agent operates in `test-plan` mode, **Then** it produces a test plan Markdown document listing the minimum required test cases for every `define` statement, grouped by test family (age boundary, timing, terminology match, value present/absent/null, conflicting events).
2. **Given** the test plan, **When** fixture skeletons are generated, **Then** the output follows the standard directory layout: `tests/cql/<library-name>/case-NNN-<description>/input/` and `tests/cql/<library-name>/case-NNN-<description>/expected/`.
3. **Given** a `define` statement that evaluates a timing interval, **When** fixtures are generated, **Then** at least three cases exist: event before the interval, event within the interval, and event after the interval.
4. **Given** a `define` statement that references a terminology value set, **When** fixtures are generated, **Then** at least three cases exist: code in the value set, code not in the value set, and code field absent/null.
5. **Given** the generated fixture skeletons, **When** they are placed in the test directory and `rh-skills cql test <topic> <library>` is run, **Then** the command executes without configuration errors (even if tests fail due to placeholder data).

---

### User Story 5 — Promote CQL Authoring from rh-inf-formalize to rh-cql (Priority: P2)

A system integrator updates the `rh-inf-formalize` skill to hand off CQL authoring to `rh-cql` rather than performing it inline. After the change, formalize continues to produce FHIR Library wrappers but delegates `.cql` content generation to `rh-cql author` mode.

**Why this priority**: This integration work is architecturally significant — it defines the boundary between two skills and prevents duplicated, inconsistent CQL generation. It must be designed before either skill's implementation is finalized.

**Independent Test**: Can be tested by running `rh-inf-formalize` on an artifact type that emits a CQL library (measure, decision-table, policy) and verifying that the `.cql` file was produced by the `rh-cql` skill path, that no duplicate CQL generation occurs in formalize, and that the FHIR Library wrapper produced by formalize correctly references the CQL authored by `rh-cql`.

**Acceptance Scenarios**:

1. **Given** a L2 artifact of type `measure`, `decision-table`, or `policy`, **When** `rh-inf-formalize` executes in implement mode, **Then** it invokes `rh-cql author` mode as a sub-step and does not generate its own CQL content independently.
2. **Given** the handoff from `rh-inf-formalize` to `rh-cql`, **When** `rh-cql` authors the library, **Then** formalize uses the `.cql` output to produce the FHIR Library JSON wrapper (via `rh-skills formalize`) without re-authoring the CQL.
3. **Given** a `rh-inf-formalize` run for an artifact type that does not require CQL (e.g., `terminology`, `assessment`), **When** formalize executes, **Then** `rh-cql` is not invoked and the behavior is identical to the pre-integration baseline.
4. **Given** `rh-cql review` output for a library, **When** the review is integrated with `rh-skills verify`, **Then** verify accepts the review report as evidence and updates topic tracking state accordingly.

---

### Edge Cases

- What happens when a `.cql` file references an included library not present in the local topic directory? The review and debug modes must distinguish missing-locally vs. unresolvable-globally and provide actionable guidance in both cases.
- What happens when the CQL translator binary is not installed or not on the PATH? `rh-skills cql validate` and `rh-skills cql translate` must emit a clear error message with installation instructions rather than a cryptic failure.
- What happens when a structured artifact provides no terminology codes? Author mode must still produce valid CQL with a comment block noting that terminology declarations are pending, rather than generating invalid or placeholder code.
- What happens when `test-plan` mode processes a library with no `define` statements other than `context Patient`? The output should be a minimal test plan acknowledging no testable expressions were found.
- What happens when a CQL library uses CQL version features not present in CQL 1.5.3? Review mode must flag the version incompatibility as a blocking finding.
- What happens when the same `define` expression name appears in both the library under review and an included library? Debug and review modes must resolve the namespace and report the correct origin.

## Requirements *(mandatory)*

### Functional Requirements

#### Skill Artifact Requirements

- **FR-001**: The project MUST contain a new curated skill at `skills/.curated/rh-cql/` comprising `SKILL.md`, `reference.md`, and an `examples/` directory.
- **FR-002**: `SKILL.md` MUST define four operating modes — `author`, `review`, `debug`, `test-plan` — each with distinct inputs, outputs, and behavioral instructions for the agent.
- **FR-003**: `SKILL.md` MUST include an authoring rubric covering all ten areas: model declaration and version; included libraries and versions; terminology declarations and version pinning; top-level documentation and intent; separation of retrieval logic from derived logic; reuse of helper functions; null/empty semantics; interval boundary behavior; date/time precision assumptions; and output shape and expected result types.
- **FR-004**: `SKILL.md` MUST include a high-risk pattern catalog with instructions to flag each pattern as blocking or advisory: unpinned terminology; hidden timezone/precision assumptions; quantity comparisons without unit normalization; overly broad retrieves filtered ad hoc; duplicate logic instead of helper definitions; ambiguous null handling; and dependence on implicit engine behavior.
- **FR-005**: `SKILL.md` MUST include a CQL style guide covering: library naming and versioning conventions; when to use helper functions; allowed retrieve patterns; terminology declaration rules; null and interval conventions; date/time precision rules; when to split logic into included libraries; and an anti-pattern catalog.
- **FR-006**: `SKILL.md` MUST declare which `rh-skills` CLI commands the agent invokes deterministically (writes/validates via CLI), which MCP tools the agent uses (reasonhub search and lookup tools), and which files it reads from and writes to.
- **FR-007**: `reference.md` MUST list all four layers of the standards corpus (Core CQL, FHIR-facing, Packaging/Lifecycle, Tooling) with URLs, version identifiers, and relevance notes describing when each source applies.
- **FR-008**: The `examples/` directory MUST contain at least two worked examples: one demonstrating `author` mode producing a complete CQL library, and one demonstrating `review` mode producing a structured review report with findings.

#### Author Mode Requirements

- **FR-009**: In `author` mode, the agent MUST read L2 structured artifacts from the topic's `structured/` directory and produce a `.cql` file that passes CQL translator validation with zero errors.
- **FR-010**: In `author` mode, the agent MUST use `rh-skills cql validate` (or equivalent CLI command) to confirm the authored library is syntactically and semantically valid before declaring the output complete.
- **FR-011**: In `author` mode, the agent MUST produce a FHIR Library JSON wrapper by calling `rh-skills formalize` with the `.cql` file as input.
- **FR-012**: Authored CQL libraries MUST follow the style guide in `SKILL.md`, including explicit model declarations, pinned library versions, pinned terminology versions, and a top-level documentation comment block.

#### Review Mode Requirements

- **FR-013**: In `review` mode, the agent MUST produce a Markdown review report that classifies each finding as `BLOCKING`, `ADVISORY`, or `INFO`.
- **FR-014**: Every `BLOCKING` or `ADVISORY` finding in the review report MUST include: the finding category (from the authoring rubric or high-risk pattern catalog), a quoted excerpt from the CQL identifying the specific line or expression, and a concrete recommended fix.
- **FR-015**: In `review` mode, the agent MUST check the library against all ten authoring rubric areas and all seven high-risk pattern categories.
- **FR-016**: In `review` mode, the agent MUST check packaging concerns: whether computable content (source CQL) is present, whether translator options are explicit and reproducible, and whether library metadata and dependencies are consistent.
- **FR-017**: A completed review report MUST be usable as evidence accepted by `rh-skills verify` to record review completion in topic tracking state.

#### Debug Mode Requirements

- **FR-018**: In `debug` mode, the agent MUST accept as input a `.cql` file plus at least one of: a translator error message from `rh-skills cql validate`, a failing test case (input fixture + expected result + actual result), or a runtime error description.
- **FR-019**: In `debug` mode, the agent MUST produce a diagnosis report that identifies the root cause of each provided error, maps it to the specific `define` statement or declaration responsible, and proposes a minimal corrective change.
- **FR-020**: The diagnosis report MUST distinguish between authoring errors (fixable by editing the CQL source) and environment/configuration errors (fixable by correcting tooling setup, missing dependencies, or execution context).

#### Test-Plan Mode Requirements

- **FR-021**: In `test-plan` mode, the agent MUST enumerate every non-context `define` statement in the library and produce at minimum: one positive case, one negative case, one null/absent case, and at least one boundary case per statement.
- **FR-022**: In `test-plan` mode, the agent MUST generate fixture skeleton files following the standard directory structure: `tests/cql/<library-name>/case-NNN-<description>/input/` (patient.json, bundle.json, parameters.json) and `tests/cql/<library-name>/case-NNN-<description>/expected/` (expression-results.json) with a `notes.md` per case.
- **FR-023**: The test plan Markdown document MUST summarize the test families applicable to each `define` statement: age below/at/above threshold; timing before/on/after; terminology match/non-match/missing; value present/absent/null; single/multiple/conflicting events.
- **FR-024**: Generated fixture skeletons MUST be structurally valid JSON (not empty files) with placeholder values annotated by inline comments or a companion `notes.md` explaining what data each placeholder represents.

#### CLI Command Requirements

- **FR-025**: The `rh-skills` CLI MUST be extended with a `cql` sub-command group containing at minimum: `validate <topic> <library>` (runs the CQL translator and reports errors), `translate <topic> <library>` (produces ELM JSON), and `test <topic> <library>` (runs fixture-based test cases).
- **FR-026**: `rh-skills cql validate` MUST exit with a non-zero status code when the CQL translator reports any errors and print a human-readable error summary to stdout.
- **FR-027**: `rh-skills cql translate` MUST write ELM JSON output to the topic's output directory and print the output file path to stdout on success.
- **FR-028**: `rh-skills cql test` MUST discover test fixtures automatically from the standard `tests/cql/<library-name>/` directory structure without requiring manual test registration.
- **FR-029**: All three `cql` sub-commands MUST emit a clear, actionable error message when the CQL translator binary is absent or not on the PATH, including instructions for obtaining it.

#### Integration Requirements

- **FR-030**: `rh-inf-formalize` MUST be updated so that for artifact types requiring CQL (`measure`, `decision-table`, `policy`), CQL authoring is delegated to `rh-cql author` mode rather than performed inline within formalize.
- **FR-031**: `rh-inf-formalize` MUST retain responsibility for producing the FHIR Library JSON wrapper via `rh-skills formalize`, using the `.cql` file output from `rh-cql` as input.
- **FR-032**: `rh-inf-formalize` MUST NOT invoke `rh-cql` for artifact types that do not produce CQL libraries (`terminology`, `assessment`).
- **FR-033**: The boundary between `rh-cql` and `rh-inf-formalize` MUST be documented in both skills' `SKILL.md` files so that an agent can determine from either skill's instructions which step owns CQL content generation.

### Key Entities

- **CQL Library**: The primary artifact produced by `rh-cql author` mode. Identified by library name and version. Contains model declarations, included library references, terminology declarations, and named `define` statements. Lives at `topics/<topic>/output/<library-name>.cql`.
- **Review Report**: A Markdown document produced by `rh-cql review` mode. Contains categorized findings (BLOCKING / ADVISORY / INFO) with evidence and recommended fixes. Lives at `topics/<topic>/process/reviews/<library-name>-review.md`.
- **Test Plan**: A Markdown document produced by `rh-cql test-plan` mode. Enumerates test cases per `define` statement with test family coverage. Lives at `topics/<topic>/process/test-plans/<library-name>-test-plan.md`.
- **Test Fixture**: A directory containing input patient/bundle JSON files and expected expression-results JSON. Lives at `tests/cql/<library-name>/case-NNN-<description>/`.
- **ELM JSON**: The compiled representation of a CQL library produced by `rh-skills cql translate`. Used for executable packaging. Lives at `topics/<topic>/output/<library-name>.json`.
- **FHIR Library Resource**: The FHIR R4 Library JSON wrapper produced by `rh-skills formalize`. References both the source CQL (computable content) and optionally the ELM JSON (executable content).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A CQL library authored by `rh-cql author` mode passes CQL translator validation with zero errors on the first invocation of `rh-skills cql validate` in 90% of authoring sessions.
- **SC-002**: A review report produced by `rh-cql review` mode covers all ten authoring rubric areas and all seven high-risk pattern categories with no category omitted, verifiable by inspection of the report's section headings.
- **SC-003**: A test plan produced by `rh-cql test-plan` mode for a library with N named `define` statements generates at minimum 4×N fixture skeleton cases (one positive, one negative, one null, one boundary per statement).
- **SC-004**: `rh-skills cql validate` completes and returns a translator result (pass or structured error list) within 30 seconds for a CQL library of up to 500 lines on a standard developer workstation.
- **SC-005**: After the `rh-inf-formalize` integration update, no `.cql` file content is generated by `rh-inf-formalize` directly — all CQL content originates from `rh-cql`, verifiable by code inspection showing no CQL string construction in the formalize skill.
- **SC-006**: An agent operating with only the `rh-cql` skill loaded (no other skills) can complete an `author`, `review`, `debug`, and `test-plan` session on the same library using only the information in `SKILL.md`, `reference.md`, and the examples — without requiring external documentation lookups for standard use cases.
- **SC-007**: The `rh-cql` skill's `reference.md` references all four layers of the standards corpus with at least one URL per source, confirmed by link validation at the time of skill creation.

## Assumptions

- CQL library authoring targets CQL version 1.5.3 and the FHIR R4 model. CQL 2.x or FHIR R5 targeting is out of scope for this feature.
- The CQFramework CQL translator (`cql-to-elm`) is the reference translator. Other translators (e.g., Smile CDR) are out of scope unless their error formats are identical to the CQFramework translator.
- L2 structured artifacts are assumed to already contain resolved terminology codes (from `rh-inf-formalize` or `rh-inf-extract`). The `rh-cql` skill does not perform terminology resolution from scratch.
- Test fixture execution depends on an external CQL testing framework (e.g., AHRQ CQL Testing Framework). The `rh-skills cql test` command wraps this framework but does not implement a CQL evaluation engine natively.
- The `rh-cql` skill operates within the existing topic/artifact lifecycle managed by `tracking.yaml`. It does not introduce a new lifecycle state; it adds steps within the existing L3-computable stage.
- `rh-inf-formalize` continues to own FHIR Library wrapper generation (`rh-skills formalize`). The scope of the `rh-inf-formalize` update is limited to redirecting CQL content generation, not refactoring the FHIR packaging logic.
- Worked examples in the `examples/` directory use a realistic but synthetic clinical scenario (not real patient data) that can be committed to the repository without privacy concerns.
- The initial version of `rh-cql` does not implement automated remediation — review and debug modes produce reports and suggestions that a human (or agent in a follow-up step) acts on, rather than auto-patching the CQL.
