<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Modified principles:
  - Template Principle 1 -> I. Deterministic CLI Boundary
  - Template Principle 2 -> II. Reviewable Lifecycle Artifacts
  - Template Principle 3 -> III. Spec-Linked Validation
  - Template Principle 4 -> IV. Safety and Evidence Integrity
  - Template Principle 5 -> V. Minimal Surface Area
- Added sections:
  - Delivery Constraints
  - Development Workflow
- Removed sections:
  - Placeholder template principle titles and section names
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md
  - ✅ .specify/templates/spec-template.md
  - ✅ .specify/templates/tasks-template.md
  - ✅ docs/SKILL_AUTHORING.md
  - ✅ specs/005-rh-inf-extract/spec.md
  - ✅ specs/005-rh-inf-extract/plan.md
- Follow-up TODOs:
  - None
-->

# RH Skills Constitution

## Core Principles

### I. Deterministic CLI Boundary
All state-changing operations, filesystem writes, schema validation, and
tracking updates MUST be implemented in `rh-skills` CLI commands. SKILL.md files,
specifications, and plans MAY describe reasoning and orchestration, but they
MUST NOT become alternate persistence paths. Every feature that writes durable
artifacts MUST identify the canonical CLI command that owns those writes and the
named tracking events it appends.

Rationale: keeping durable behavior in the CLI preserves auditability,
repeatability, and testability across agent and CLI-first workflows.

### II. Reviewable Lifecycle Artifacts
Features that advance lifecycle state MUST use an explicit `plan -> implement ->
verify` flow unless the feature is intentionally read-only or status-only. Plan
artifacts MUST be durable, human-reviewable files under
`topics/<topic>/process/plans/`. Implement flows MUST fail when the required
plan or approval gate is absent. Verify flows MUST be non-destructive and safe
to rerun.

Rationale: reviewable artifacts and enforced gates are the core safety mechanism
for clinical knowledge work.

### III. Spec-Linked Validation
Every feature spec MUST define independently testable user stories, explicit
functional requirements, and measurable success criteria when buildable work is
required. Every implementation plan MUST record applicable constitution checks,
technical constraints, and the concrete file/command boundaries used to satisfy
the spec. Every tasks file MUST show requirement or story coverage and MUST
include validation tasks for changed CLI contracts, schemas, events, or
safety-sensitive behavior.

Rationale: implementation quality depends on traceable alignment between the
problem statement, design, and executable work.

### IV. Safety and Evidence Integrity
Features that read clinical or source content MUST treat that content as
untrusted data, declare an injection boundary before analysis, and preserve
evidence traceability when structured clinical claims are produced. Material
source conflicts MUST be surfaced explicitly rather than silently collapsed.
Validation and reporting flows MUST distinguish blocking errors from advisory
warnings.

Rationale: safety depends on preserving provenance, exposing uncertainty, and
preventing source content from being mistaken for instructions.

### V. Minimal Surface Area
The project MUST prefer extending existing `rh-skills` primitives, schemas, and
artifact locations over creating parallel commands, duplicate schemas, or
alternate write paths. A new command, abstraction, or artifact name is allowed
only when the spec and plan explain why existing surfaces are insufficient.
Documentation and examples MUST reflect the canonical command shapes and
artifact names actually implemented.

Rationale: minimizing surface area reduces maintenance cost and prevents
contract drift across specs, skills, CLI commands, and docs.

## Delivery Constraints

- Python CLI work MUST stay within the repository's established stack
  (`click`, `ruamel.yaml`, `pytest`) unless a feature plan explicitly justifies
  expansion.
- Tracking updates MUST be append-only named events written through shared CLI
  helpers; raw string writes to `tracking.yaml` are forbidden.
- Curated skills MUST live under `skills/.curated/<name>/` and include
  `SKILL.md`, `reference.md`, and worked examples.
- Features that can create durable clinical artifacts MUST document review and
  approval gates explicitly in their specs, plans, and skills.

## Development Workflow

- `spec.md`, `plan.md`, and `tasks.md` are the required governance artifacts for
  implementation work.
- The Constitution Check in `plan.md` MUST identify the applicable principles,
  note any justified complexity, and fail closed on unresolved conflicts with
  this constitution.
- Tasks MUST be organized by user story, include exact file paths, and capture
  validation work for changed CLI contracts, schemas, events, and review gates.
- Before merge, the repository tests relevant to the change MUST pass. Skill
  changes MUST also pass the skill schema, security, and contract suites.
- When a constitution amendment changes project workflow expectations, dependent
  templates and guidance docs MUST be updated in the same change.

## Governance

This constitution supersedes ad hoc workflow conventions for RH Skills. Every
spec, plan, task list, review, and implementation change MUST verify compliance
with these principles.

Amendments MUST:
1. explain the principle or section being changed;
2. classify the version bump as MAJOR, MINOR, or PATCH;
3. update dependent templates and guidance docs in the same change, or record
   why no updates were needed;
4. preserve an auditable history in git.

If a feature must violate a principle, the violation MUST be documented in the
feature plan's Constitution Check and explicitly approved before implementation;
implementation convenience alone is not sufficient justification.

**Version**: 1.0.0 | **Ratified**: 2026-04-14 | **Last Amended**: 2026-04-14
