# Feature Specification: Healthcare Informatics Skills Framework

**Feature Branch**: `001-hi-skills-framework`  
**Created**: 2026-04-03  
**Status**: Clarified  
**Input**: User description: "I want to build a skills repo for a set of healthcare informatics skills. I want to model it after spec-kit with similar style. The concept is to progress from discovery of L1 artifacts (unstructured / raw), progressing to L2 (semi-structured) and then ultimately L3 (computable) artifacts. Each step of the workflow, I want to produce tracking artifacts, so this system will require a CLI. Model the actual skills source development following anthropic skills-developer. We want to allow for local testing of the skills. A guiding principal is to offload all deterministic work to commands, and only leave reasoning to the agent."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scaffold a New Healthcare Informatics Skill (Priority: P1)

A healthcare informatics developer (skill author) uses the CLI to initialize a new skill in the repository. The CLI scaffolds the standard directory structure and creates starter L1 artifacts (raw/unstructured discovery documents such as plain-text notes, interview transcripts, reference materials) along with an initial tracking artifact recording the skill's creation and current lifecycle state.

**Why this priority**: This is the entry point for all other workflows. Without the ability to create a new skill with a well-defined structure, no further progression or testing is possible. A single successfully scaffolded skill with tracking artifacts is already a functional deliverable.

**Independent Test**: Can be fully tested by running the CLI `init` command for a new skill, verifying the expected directory structure, L1 artifact stubs, and a tracking artifact are created — independent of any progression or testing commands.

**Acceptance Scenarios**:

1. **Given** an empty or existing skills repository, **When** a developer runs the CLI skill-init command with a skill name and brief description, **Then** a new skill directory is created with the spec-kit-style structure, L1 artifact stubs, and a tracking artifact capturing the initial state (skill name, author, creation date, current level: L1).
2. **Given** a skill name that already exists, **When** a developer attempts to init the same skill again, **Then** the CLI reports a conflict and does not overwrite existing artifacts.
3. **Given** a newly scaffolded skill, **When** the developer lists skills via the CLI, **Then** the new skill appears in the listing with its current level (L1) and tracking status.

---

### User Story 2 - Progress Skill Artifacts Through Levels (Priority: P2)

A skill author refines a skill by progressing individual artifacts across three levels. The artifact topology is many-to-many: a single L1 artifact (raw discovery) may yield several L2 artifacts (semi-structured), and several L2 artifacts may be combined to produce a single L3 artifact (computable YAML). Each level holds a collection of independent artifacts, not a single document. At each promotion, the CLI validates readiness of the specific artifact(s) being promoted, performs deterministic scaffolding and tracking work, and leaves domain reasoning and content authoring to the human or agent.

**Why this priority**: The many-to-many, multi-artifact progression is the core value of the framework. Once a skill can be scaffolded and individual artifacts can be promoted, authors have a complete knowledge refinement pipeline.

**Independent Test**: Can be tested by promoting a single L1 artifact to produce two L2 artifacts, then combining those two L2 artifacts into one L3 artifact, verifying that each step produces the expected artifact structure, tracking entries, and that partial/optional fields produce warnings rather than blocking errors.

**Acceptance Scenarios**:

1. **Given** a skill with one or more L1 artifacts, **When** a developer runs the CLI promote command on a specific L1 artifact targeting L2, **Then** the CLI scaffolds one or more L2 artifact templates (the author specifies how many to derive), pre-populates deterministic fields from L1 content, records the derivation relationship in the tracking artifact (which L1 produced which L2s), and reports which fields require reasoning to complete.
2. **Given** a skill with two or more L2 artifacts, **When** a developer runs the CLI promote command selecting multiple L2 artifacts to combine into one L3 artifact, **Then** the CLI scaffolds one L3 YAML artifact template, records the convergence relationship (which L2s contributed), updates the tracking artifact, and validates the result against the L3 YAML schema.
3. **Given** a specific artifact with all required fields complete and some optional fields empty, **When** a developer promotes that artifact, **Then** the CLI allows promotion and emits warnings listing the incomplete optional fields — it does not block.
4. **Given** a specific artifact with one or more required fields missing or empty, **When** a developer attempts to promote that artifact, **Then** the CLI blocks promotion and reports exactly which required fields are missing.
5. **Given** a skill at any level, **When** the developer inspects the tracking artifact, **Then** it contains a complete, timestamped history of all artifact-level events including derivation (L1→L2) and convergence (L2→L3) relationships.

---

### User Story 3 - Locally Test a Skill (Priority: P3)

A skill author runs a local test of an L3 skill to verify it behaves correctly before contributing it to the shared repository. Skills are LLM-invocable prompts — the CLI submits the skill's prompt plus a test fixture's input to a configured LLM, captures the response, and compares it against the fixture's expected output. Each test run produces a structured test result artifact capturing pass/fail per fixture, actual vs. expected outputs, and a summary.

**Why this priority**: Local testing closes the development loop and ensures skills produce correct LLM responses before publication. It models the anthropic skills-developer approach of enabling offline/local validation against a live or local LLM.

**Independent Test**: Can be tested by running the CLI test command against a skill with pre-defined fixtures, verifying it invokes the LLM, produces a structured test result artifact, and prints a human-readable pass/fail summary.

**Acceptance Scenarios**:

1. **Given** a skill at L3 with test fixtures defined (each fixture: input conversation context + expected LLM response), **When** a developer runs the CLI test command, **Then** the CLI submits each fixture's input to the configured LLM using the skill's prompt, captures the response, evaluates pass/fail against expected output, produces a structured test result artifact, and prints a human-readable summary.
2. **Given** a skill with no test fixtures defined, **When** a developer runs the CLI test command, **Then** the CLI reports that no fixtures are available and provides guidance on how to add them.
3. **Given** a skill where one or more fixture tests fail, **When** the developer reviews the test result artifact, **Then** the artifact clearly identifies which fixtures failed, the expected output, and the actual LLM response received.
4. **Given** a fixture test where the LLM call returns an error or times out (execution crash), **When** the developer reviews the test result, **Then** the fixture is marked as errored (not pass/fail) with the error detail captured in the test result artifact.
5. **Given** a skill at L1 or L2, **When** a developer attempts to run the test command, **Then** the CLI warns that full LLM invocation testing requires L3 artifacts but allows structural validation tests (schema conformance) on the current level's artifacts.

---

### User Story 4 - Track and Inspect Workflow State (Priority: P4)

A skill author or repository maintainer uses the CLI to inspect the current workflow state of any skill — seeing its current artifact level, history of transitions, validation outcomes, and test results — all from a central tracking artifact without navigating file structures manually.

**Why this priority**: Tracking is the operational backbone of the system. Transparent state visibility enables quality governance and collaboration across authors.

**Independent Test**: Can be tested by running the CLI status command for any skill and verifying the tracking artifact is read and rendered accurately.

**Acceptance Scenarios**:

1. **Given** any skill in the repository, **When** a developer runs the CLI status command for that skill, **Then** the CLI reads the tracking artifact and displays: current level, last transition date, validation status, and latest test result summary.
2. **Given** a repository with multiple skills, **When** a developer runs the CLI list command, **Then** all skills are shown with their current level and tracking status in a concise table.
3. **Given** a skill with a full history of transitions, **When** the developer views the skill's tracking artifact, **Then** the complete ordered history of all events (creation, promotions, test runs) is present with timestamps.

---

### Edge Cases

- When a skill author promotes an L1 artifact to L2, how many L2 artifacts to derive is a reasoning decision left to the author — the CLI scaffolds as many as requested.
- When combining multiple L2 artifacts into one L3, the CLI requires the author to explicitly select which L2 artifacts participate; combining across skills is out of scope for v1.
- When promoting an artifact with incomplete optional fields, the CLI emits warnings but does not block; required fields always block promotion.
- How does the system handle a corrupt or missing tracking artifact for a skill that otherwise has artifacts present? (CLI must detect and report, offering a repair command.)
- When a test run produces an LLM error or timeout rather than a response, the fixture is recorded as "errored" (distinct from "failed") with error detail captured.
- How are breaking schema changes to the L3 YAML format handled for previously promoted artifacts? (Schema versioning strategy to be defined during planning.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a CLI implemented as Shell/Bash scripts as the primary interface for all skill lifecycle operations (init, promote, test, status, list), with zero runtime dependencies beyond a POSIX shell.
- **FR-002**: The CLI MUST scaffold new skills with a spec-kit-style directory structure containing L1 artifact stubs and an initial tracking artifact.
- **FR-003**: The system MUST define three distinct artifact levels: L1 (unstructured/raw discovery), L2 (semi-structured YAML with defined fields), and L3 (computable YAML conforming to a custom domain schema). Each level holds a collection of independent artifacts, not a single document.
- **FR-004**: The artifact topology MUST support many-to-many relationships: one L1 artifact may yield multiple L2 artifacts (derivation), and multiple L2 artifacts may converge into one L3 artifact (convergence). The CLI MUST record these derivation and convergence relationships in the tracking artifact.
- **FR-005**: The CLI MUST validate artifact readiness before allowing promotion. Required fields being empty or missing MUST block promotion with a specific report. Incomplete optional fields MUST emit warnings but MUST NOT block promotion.
- **FR-006**: The CLI MUST perform all deterministic work (directory scaffolding, template generation, tracking artifact updates, relationship recording, schema validation) as commands, leaving domain-specific content authoring and reasoning to the human or agent.
- **FR-007**: The system MUST produce a tracking artifact for each skill that records all lifecycle events (creation, artifact derivations, artifact convergences, promotion outcomes, test runs) with timestamps and artifact-level relationship maps.
- **FR-008**: The CLI MUST support local testing of skills by submitting L3 skill prompts plus fixture inputs to a configured LLM, capturing responses, evaluating pass/fail against expected outputs, and producing a structured test result artifact.
- **FR-009**: Test result artifacts MUST distinguish three fixture outcomes: pass, fail, and errored (LLM call failed or timed out), with full detail captured for each.
- **FR-010**: Skill source structure and conventions MUST follow the anthropic skills-developer pattern, enabling skills to be loaded and invoked by AI agents.
- **FR-011**: The system MUST allow skills to be developed, promoted, and structurally validated entirely offline. LLM-invocation testing (US3) requires a configured LLM endpoint but no other remote service.
- **FR-012**: The CLI MUST provide a status command that reads a skill's tracking artifact and renders current artifact inventory by level, derivation/convergence relationships, promotion history, and latest test result summary.
- **FR-013**: The CLI MUST provide a list command that summarizes all skills in the repository with their artifact counts per level and tracking status.
- **FR-014**: The system MUST define and enforce a custom YAML schema for L3 artifacts — usable without any FHIR tooling — that is designed to be structurally compatible with FHIR (HL7 FHIR R4/R5), navigable via FHIRPath, and expressible in CQL. Teams that do not use FHIR MUST be able to work with L3 artifacts natively using only the custom schema. Translation of L3 artifacts to FHIR resources, FHIRPath expressions, or CQL MAY be provided as an additional CLI command or skill and is not required for core promotion validation.
- **FR-015**: The system MUST explicitly exclude PHI/PII from all artifacts, fixtures, and tracking records. Clinical knowledge/logic is the only permitted content — no patient-specific data.

### Key Entities

- **Skill**: A discrete healthcare informatics capability authored in the repository; identified by a unique name; owns a collection of artifacts across one or more levels (L1, L2, L3).
- **Artifact**: A document or structured record associated with a skill at a specific level. L1 artifacts are raw/unstructured (notes, transcripts, reference materials). L2 artifacts are semi-structured YAML with defined fields. L3 artifacts are computable YAML documents conforming to a custom domain schema that is designed for FHIR compatibility (mappable to FHIR R4/R5 resource structures, navigable via FHIRPath, expressible in CQL) while remaining fully usable without FHIR tooling. Each level holds multiple independent artifacts; the relationship between levels is many-to-many.
- **Derivation**: The relationship from one L1 artifact to one or more L2 artifacts produced from it; recorded in the tracking artifact.
- **Convergence**: The relationship from two or more L2 artifacts combined into one L3 artifact; recorded in the tracking artifact.
- **Tracking Artifact**: A structured record per skill capturing all lifecycle events (creation, derivations, convergences, validation outcomes, test runs) with timestamps and relationship maps; the authoritative source of skill workflow state.
- **Test Fixture**: An author-defined pair of (input conversation context, expected LLM response) used to validate a skill's behavior during local testing.
- **Test Result Artifact**: A structured record produced by a test run, capturing per-fixture outcomes (pass/fail/errored), actual vs. expected LLM responses, and a summary.
- **CQL Artifact**: An optional downstream artifact representing clinical logic extracted from L3 artifacts and expressed in Clinical Quality Language (CQL); produced by a dedicated CLI command or a separate skill; not required for L3 promotion.
- **Skill Repository**: The top-level collection of skills, their multi-level artifact collections, tracking artifacts, and test fixtures, organized in a spec-kit-style directory structure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A skill author can scaffold, populate, and fully promote a new skill from L1 to L3 without reading internal source code — relying solely on CLI commands and generated artifact templates.
- **SC-002**: All deterministic workflow steps (scaffolding, promotion, schema validation, tracking updates) complete without requiring the author to manually edit configuration or structural files.
- **SC-003**: A skill author can run local tests against a completed L3 skill and receive a structured pass/fail report within a time comparable to running a local unit test suite.
- **SC-004**: 100% of level transitions are recorded in the tracking artifact with a timestamp and validation outcome, ensuring complete and auditable workflow history.
- **SC-005**: A new contributor can understand the artifact level of any skill and its workflow history by running a single CLI command, without navigating the file system manually.
- **SC-006**: Skills developed in this framework are directly loadable and invocable by AI agents following the anthropic skills-developer conventions, with no additional manual configuration.

## Assumptions

- Primary users are healthcare informatics professionals who may not be software engineers; the CLI must be operable without deep technical knowledge of the underlying file formats.
- Skills are authored individually and the repository supports multiple independent skills developed in parallel by different authors.
- The anthropic skills-developer conventions are adopted as the source structure pattern for skills; any divergence from those conventions is explicitly documented in the framework.
- L3 artifacts use a custom YAML schema (spec-kit-style) that is fully usable without any FHIR tooling. The schema is designed to be structurally compatible with FHIR R4/R5, navigable via FHIRPath, and expressible in CQL — enabling translation to those standards for teams that require it. The specific schema fields and compatibility mapping will be defined during planning. L2 artifacts also use YAML with defined fields; exact L2 schema to be defined during planning.
- Local testing executes skills in the same environment where they are developed; network isolation or sandboxing is out of scope for v1.
- The CLI is a command-line tool invocable from a terminal; no graphical or web interface is in scope for v1.
- The repository structure follows spec-kit conventions for discoverability and tooling compatibility, but spec-kit itself is not a runtime dependency of the healthcare informatics skills framework.
