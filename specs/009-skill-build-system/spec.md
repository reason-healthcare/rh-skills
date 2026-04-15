# Feature Specification: RH Skills Build System

**Feature Branch**: `009-skill-build-system`  
**Created**: 2026-04-14  
**Status**: ✅ Complete  
**Input**: User description: "Specify what needs to be done on branch 009 for a build system that turns the canonical RH skill library into installable platform-specific skill bundles from one source of truth."

## Clarifications

### Session 2026-04-14

- Q: Should 009 cover only build/distribution, or also include CI evaluation? → A: Include CI validation of generated bundles and installability checks in 009; defer scenario-based model evaluation to a later extension.

## User Scenarios & Testing *(mandatory)*

The RH Skills supports two usage modes:

1. **CLI-first** — users call `rh-skills` commands directly
2. **Agent-native** — users interact with an AI agent (Copilot, Claude, Gemini, etc.) which reads RH skills and calls `rh-skills` commands on their behalf

In both modes, the guiding principle is identical: **all deterministic work via `rh-skills` CLI, all reasoning by the agent.** The SKILL.md content does not change between modes — only the *installation format* differs per agent platform.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build skill bundles for supported platforms (Priority: P1)

A contributor wants to package the canonical RH skill library for one or more
supported agent platforms so teams can install the same skills consistently
without manually rewriting them for each platform.

**Why this priority**: This is the core value of the feature. Without reliable
multi-platform packaging from one source of truth, the build system does not
solve the distribution problem it exists to address.

**Independent Test**: A contributor can run the build workflow for one supported
platform or all supported platforms and receive installable platform-specific
skill bundles plus a clear build summary.

**Acceptance Scenarios**:

1. **Given** canonical RH skills are available in the curated skill library,
   **When** a contributor builds for one supported platform, **Then** the system
   produces installable skill bundles for that platform from the same canonical
   source content.
2. **Given** canonical RH skills are available in the curated skill library,
   **When** a contributor builds for all supported platforms, **Then** the
   system builds each configured platform in one workflow and reports the
   outcome for each platform.
3. **Given** the canonical skill content contains unresolved placeholder text,
   **When** a contributor starts a build, **Then** the system stops before
   distributing output and identifies the affected skill clearly.
4. **Given** generated bundles are ready for distribution, **When** repository CI
   runs, **Then** the system validates the generated bundles and installability
   checks before distribution is considered ready.

---

### User Story 2 - Add or adjust a platform profile declaratively (Priority: P2)

A maintainer wants to support a new agent platform, or refine an existing one,
by updating a platform profile rather than rewriting the build workflow itself.

**Why this priority**: The build system must stay extensible. Adding platform
support should be routine configuration work rather than a bespoke engineering
project each time.

**Independent Test**: A maintainer can add a new platform profile and build for
that platform without changing the core build workflow.

**Acceptance Scenarios**:

1. **Given** a maintainer defines a new platform profile, **When** the build
   workflow is run for that platform, **Then** the system uses the profile to
   generate platform-specific bundles without requiring core build logic changes.
2. **Given** a platform profile changes how metadata or preamble content should
   appear, **When** the build workflow runs, **Then** the output reflects the
   profile-defined formatting rules consistently across all generated bundles.
3. **Given** a profile contains an unsupported or conflicting configuration,
   **When** the build workflow starts, **Then** the system reports the issue
   clearly before producing ambiguous or conflicting output.

---

### User Story 3 - Validate or preview build output before distribution (Priority: P2)

A contributor wants confidence that generated skill bundles are well-formed
before sharing them, and sometimes wants to preview the impact of a build
without writing any files.

**Why this priority**: Distribution safety matters because broken skill bundles
would create installation problems across platforms and erode trust in the
canonical skill library.

**Independent Test**: A contributor can run validation and preview workflows and
receive a clear per-platform, per-skill outcome without needing to inspect the
generated files manually.

**Acceptance Scenarios**:

1. **Given** generated bundles are ready for review, **When** a contributor runs
   the validation workflow, **Then** the system reports pass/fail results for
   each bundle with enough detail to diagnose failures.
2. **Given** a generated bundle is missing required platform content, **When**
   validation runs, **Then** the system fails the validation workflow with a
   clear diagnostic tied to the affected platform and skill.
3. **Given** a contributor wants a non-destructive preview, **When** the preview
   workflow runs, **Then** the system shows what would be generated without
   writing files while still surfacing blocking errors.
4. **Given** a generated bundle cannot be installed or loaded in its target
   platform validation flow, **When** CI validation runs, **Then** the system
   fails with a clear platform-specific diagnostic.

---

### Edge Cases

- What happens when the curated skill library contains zero buildable skills?
- What happens when a platform profile is requested but does not exist?
- What happens when two platform profiles would generate output to the same
  destination?
- What happens when a platform profile references required supporting content
  that cannot be found?
- What happens when a curated skill is incomplete and cannot be distributed?
- What happens when a platform profile includes fields the current build system
  does not yet understand?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate installable skill bundles for one selected
  supported platform from the canonical curated RH skill library.
- **FR-002**: The system MUST generate installable skill bundles for all
  supported platforms in a single build workflow when requested.
- **FR-003**: The system MUST preserve one canonical source of truth for skill
  content and MUST NOT require contributors to manually rewrite the same skill
  for each supported platform.
- **FR-004**: The system MUST support a non-destructive preview mode that shows
  what would be generated without writing distributable output.
- **FR-005**: The system MUST support a validation mode that checks generated
  bundles against platform-specific expectations and reports failures clearly.
- **FR-005a**: The system MUST support automated CI validation of generated
  bundles and installability checks for bundled platforms before distribution is
  considered ready.
- **FR-006**: The system MUST stop a build before distribution when canonical
  skill content is incomplete or contains unresolved placeholder text, and it
  MUST identify the affected skill clearly.
- **FR-007**: The system MUST provide a clear build summary showing which skills
  and platforms succeeded, failed, or produced warnings.
- **FR-008**: The system MUST use declarative platform profiles so that adding or
  refining a supported platform does not require changing the core build
  workflow in the normal case.
- **FR-009**: A platform profile MUST define the output shape needed for that
  platform, including bundle location, metadata handling, and any required
  preamble or formatting rules.
- **FR-010**: The system MUST detect conflicting platform profile outputs before
  writing bundles so contributors do not receive ambiguous or overlapping build
  artifacts.
- **FR-011**: The system MUST warn clearly about unsupported or unrecognized
  optional profile fields without silently changing the canonical skill content.
- **FR-012**: The system MUST include bundled support for GitHub Copilot, Claude
  Code, and Gemini CLI as initial distribution targets.
- **FR-013**: The system MAY include an additional distribution target that
  produces an aggregate agent-guidance document derived from the same canonical
  skill library.
- **FR-014**: Generated build artifacts MUST be kept separate from the canonical
  curated skill sources so contributors can distinguish source content from
  distributable output.
- **FR-015**: Re-running the same build with unchanged inputs MUST produce the
  same output so contributors can trust the build workflow to be repeatable.

### Key Entities *(include if feature involves data)*

- **Canonical Skill**: A curated RH skill that serves as the single source of
  truth for skill content before distribution.
- **Platform Profile**: A declarative description of how canonical skill content
  should be shaped for one supported platform.
- **Generated Skill Bundle**: A platform-specific distribution artifact derived
  from a canonical skill and a platform profile.
- **Validation Finding**: A pass, warning, or failure result associated with a
  generated bundle during validation.
- **Installability Check**: A platform-specific automated check confirming that a
  generated bundle can be loaded or consumed in the expected distribution flow.
- **Build Summary**: A contributor-facing report of which skills and platforms
  were built, skipped, warned, or failed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A contributor can generate distributable skill bundles for any
  bundled platform from a clean clone in under 10 minutes after following the
  documented setup steps.
- **SC-002**: A maintainer can add support for a new platform by defining one
  platform profile without changing the core build workflow for at least 90% of
  new platform onboarding cases.
- **SC-003**: 100% of generated bundles for bundled platforms pass the build
  system's platform-specific validation checks before distribution.
- **SC-003a**: 100% of bundled-platform distributions pass automated CI
  installability checks before contributors treat them as releasable output.
- **SC-004**: Preview mode produces zero file writes while still surfacing 100%
  of blocking errors that would fail a normal build.
- **SC-005**: A new contributor can successfully build and distribute RH skills
  for a supported platform without reading the build workflow source code.

## Assumptions

- `yq` (Go binary, v4+) and bash 3.2+ are available in all contributor environments — consistent with existing framework tooling.
- The canonical SKILL.md format is stable (defined in 002); the build system transforms it, never modifies the source.
- `dist/` is gitignored by default; teams that want to version-control generated outputs can remove it from `.gitignore`.
- Gemini CLI skill format will be derived from Gemini CLI documentation at implementation time; profile fields are sufficient to accommodate any discovered nuances.
- Claude Code reads skill context from plain Markdown files in `.claude/commands/`; frontmatter stripping plus a slash-command preamble is sufficient for compatibility.
- The build script is a developer tool only — it is never invoked by `rh-skills` CLI or called by end users.
- Platform profiles for 003–008 skills (once implemented) will be validated as part of the build; the build system does not need to know skill semantics.
- The curated RH skill library remains the single source of truth for skill
  content and distribution starts from that library rather than from
  platform-specific copies.
- Supported target platforms continue to accept file-based skill bundles or
  equivalent distributable documents.
- Contributors need both selective builds for one platform and full builds for
  all bundled platforms.
- Generated output is treated as derived distribution material rather than the
  authoritative editing surface for RH skills.
- The first release of this feature should cover GitHub Copilot, Claude Code,
  and Gemini CLI, with room for additional platforms later.
- Scenario-based model evaluation and transcript ranking are explicitly out of
  scope for 009 and may be proposed as a later extension once the CI validation
  baseline exists.
