# Feature Specification: L2 Artifact Catalog Expansion

**Feature Branch**: `010-l2-artifact-catalog`  
**Created**: 2026-04-17  
**Status**: Implemented  
**Input**: Expand L2 Hybrid Artifact Catalog with 4 new artifact types (clinical-frame, decision-table, assessment, policy), restructure structured/ directory to per-artifact subdirectories with generated views, and add a render command for SME-reviewable representations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract Agent Proposes New Artifact Types (Priority: P1)

A knowledge engineer running the extract skill against clinical guidelines receives
plan proposals that include clinical-frame, decision-table, assessment, and policy
artifact types when the source material warrants them. The planner keyword-matches
source content to the expanded catalog and proposes the correct type with an
appropriate key question.

**Why this priority**: Without the new artifact profiles in the planner, no downstream
functionality (derive, render, formalize) can operate on these types.

**Independent Test**: Can be tested by creating normalized source files containing
keywords for each new type and verifying `rh-skills promote plan` proposes the
correct artifact_type.

**Acceptance Scenarios**:

1. **Given** a normalized source containing "decision table", "condition", and "action" keywords, **When** the planner runs, **Then** it proposes an artifact with `artifact_type: decision-table` and key question about condition-action rules.
2. **Given** a normalized source containing "PHQ-9", "screening", and "assessment" keywords, **When** the planner runs, **Then** it proposes an artifact with `artifact_type: assessment`.
3. **Given** a normalized source containing "prior authorization", "coverage", or "documentation requirement" keywords, **When** the planner runs, **Then** it proposes an artifact with `artifact_type: policy`.
4. **Given** a normalized source with multiple clinical questions, **When** the planner runs, **Then** it proposes a `clinical-frame` artifact as the first artifact in the plan, containing PICOTS decomposition of each question.
5. **Given** a source with no keywords matching the new types, **When** the planner runs, **Then** it falls back to the existing 8 types as before (no regression).

---

### User Story 2 - Derive Writes to Subdirectory Structure (Priority: P1)

A knowledge engineer derives an L2 artifact and it is written into a per-artifact
subdirectory (`structured/<name>/<name>.yaml`) instead of the previous flat layout.
Validation, formalize, and status commands all resolve artifacts at the new path.

**Why this priority**: The subdirectory structure is the prerequisite for generated
views (render) and affects every downstream command.

**Independent Test**: Run `rh-skills promote derive` and verify the file is created
at `topics/<topic>/structured/<name>/<name>.yaml`, that tracking.yaml records the
new path, and that `rh-skills validate` finds the artifact.

**Acceptance Scenarios**:

1. **Given** an approved extract plan, **When** `rh-skills promote derive <topic> <name>` runs, **Then** the L2 YAML is written to `topics/<topic>/structured/<name>/<name>.yaml`.
2. **Given** a derived artifact at the new path, **When** `rh-skills validate <topic> l2 <name>` runs, **Then** it locates and validates the artifact without error.
3. **Given** a derived artifact at the new path, **When** tracking.yaml is inspected, **Then** the `file` field reads `topics/<topic>/structured/<name>/<name>.yaml`.
4. **Given** artifacts derived at new paths, **When** `rh-skills promote combine` reads L2 inputs for formalize, **Then** it resolves them from the subdirectory structure.

---

### User Story 3 - Render Generates SME-Reviewable Views (Priority: P2)

A knowledge engineer or SME runs `rh-skills render <topic> <artifact>` and receives
human-readable generated views (mermaid diagrams, markdown tables) in a
`views/` subdirectory alongside the control YAML. The YAML remains the single source
of truth; views are strictly derived.

**Why this priority**: The render command delivers the core SME review experience,
but depends on the new directory structure being in place.

**Independent Test**: Derive a decision-table artifact, run `rh-skills render`, and
verify that `views/` contains the expected mermaid and markdown files.

**Acceptance Scenarios**:

1. **Given** a `decision-table` artifact, **When** `rh-skills render <topic> <name>` runs, **Then** `structured/<name>/views/` contains a mermaid decision tree (`.mmd`), a markdown rules table, and a completeness check report.
2. **Given** an `assessment` artifact, **When** `rh-skills render` runs, **Then** `views/` contains a rendered questionnaire (markdown) and scoring summary table.
3. **Given** a `policy` artifact, **When** `rh-skills render` runs, **Then** `views/` contains a mermaid criteria flowchart and requirements checklist.
4. **Given** a `clinical-frame` artifact, **When** `rh-skills render` runs, **Then** `views/` contains a PICOTS summary table in markdown.
5. **Given** any existing artifact type (e.g., `eligibility-criteria`), **When** `rh-skills render` runs, **Then** it generates appropriate views for that type (at minimum a markdown summary).
6. **Given** an artifact YAML is updated manually, **When** `rh-skills render` is re-run, **Then** views are regenerated from the current YAML content (overwriting previous views).

---

### User Story 4 - Decision Table Verifiability (Priority: P2)

An SME reviewing a decision-table artifact can verify its completeness and
consistency. The rendered completeness report shows the product of condition moduli
versus the rule count, identifies missing rule combinations, and flags contradictory
rules.

**Why this priority**: Formal verification is the key differentiator of the
Shiffman augmented decision table model — without it, the type is just a generic
table.

**Independent Test**: Create a decision-table YAML with a known missing rule and
verify the completeness report identifies it.

**Acceptance Scenarios**:

1. **Given** a decision-table with 3 binary conditions and 8 rules, **When** rendered, **Then** the completeness report shows "8/8 rules — complete".
2. **Given** a decision-table with a missing rule combination, **When** rendered, **Then** the report lists the missing combination(s) and marks the table incomplete.
3. **Given** a decision-table with two rules sharing identical conditions but different actions, **When** rendered, **Then** the report flags a contradiction.
4. **Given** a decision-table with irrelevant conditions (dash entries), **When** rendered, **Then** column counts correctly account for wildcard expansion (a dash in a condition of modulus N counts as N covered combinations).

---

### User Story 5 - Formalize Maps New Types to L3 Sections (Priority: P3)

When the formalize skill processes approved L2 artifacts of the new types, it
correctly maps them to the appropriate L3 target sections.

**Why this priority**: Formalize is downstream of extract and render. The mapping
ensures new types participate in the full lifecycle.

**Independent Test**: Mock approved L2 artifacts of each new type and verify
`_formalize_required_sections()` returns the expected L3 sections.

**Acceptance Scenarios**:

1. **Given** an approved `decision-table` artifact, **When** formalize required sections are computed, **Then** `actions` is included in the required L3 sections.
2. **Given** an approved `assessment` artifact, **When** formalize required sections are computed, **Then** `assessments` is included.
3. **Given** an approved `policy` artifact, **When** formalize required sections are computed, **Then** `actions` is included.
4. **Given** a `clinical-frame` artifact, **When** formalize runs, **Then** it is treated as scoping metadata (no direct L3 section mapping required).

---

### User Story 6 - Type-Specific L2 Section Shapes (Priority: P2)

Each new artifact type has documented section shapes in the extract reference so
that the extract agent and `derive` command produce correctly structured YAML.

**Why this priority**: Without defined shapes, derived artifacts for new types would
have inconsistent or missing structure.

**Independent Test**: Derive each new type and validate the YAML contains the
expected type-specific sections.

**Acceptance Scenarios**:

1. **Given** artifact_type `decision-table`, **When** derived, **Then** YAML contains `conditions[]`, `actions[]`, and `rules[]` sections with the documented substructure (id, label, values for conditions; id, label for actions; when/then for rules).
2. **Given** artifact_type `assessment`, **When** derived, **Then** YAML contains `instrument`, `items[]`, and `scoring` sections.
3. **Given** artifact_type `policy`, **When** derived, **Then** YAML contains `applicability`, `criteria[]`, and `actions` sections.
4. **Given** artifact_type `clinical-frame`, **When** derived, **Then** YAML contains `frames[]` with PICOTS fields (population, intervention, comparison, outcomes, timing, setting).

---

### Edge Cases

- What happens when `rh-skills render` is called on an artifact type with no specific view generator? Falls back to a generic markdown summary view.
- What happens when a decision-table has conditions with modulus > 10? The exhaustive completeness check should warn about combinatorial explosion and show only a summary.
- What happens when an existing topic has flat-path artifacts from before the restructure? They must be re-derived; no flat-path fallback is provided.
- What happens when `rh-skills render` is run before `derive`? Fails with a clear error: "Artifact not found."
- What happens when a policy artifact has no criteria defined? Validation warns; render shows an empty requirements checklist.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add `clinical-frame`, `decision-table`, `assessment`, and `policy` to `EXTRACT_ARTIFACT_PROFILES` with appropriate keywords, section names, and key questions.
- **FR-002**: System MUST update `_formalize_required_sections()` to map `decision-table` → `actions`, `assessment` → `assessments`, `policy` → `actions`. `clinical-frame` has no L3 section mapping.
- **FR-003**: System MUST write derived L2 artifacts to `topics/<topic>/structured/<name>/<name>.yaml` (subdirectory structure).
- **FR-004**: System MUST update tracking.yaml `file` entries to reflect the new subdirectory path format.
- **FR-005**: `rh-skills validate` MUST resolve L2 artifacts at `structured/<name>/<name>.yaml`.
- **FR-006**: System MUST provide a new CLI command `rh-skills render <topic> <artifact>` that reads an L2 YAML control file, validates that required type-specific sections exist for the artifact type, and generates human-readable views into `structured/<name>/views/`.
- **FR-007**: The render command MUST generate type-specific views: decision-table → mermaid decision tree + markdown rules table + completeness report; assessment → rendered questionnaire + scoring table; policy → mermaid criteria flowchart + requirements checklist; clinical-frame → PICOTS summary table.
- **FR-008**: The render command MUST generate at least a generic markdown summary view for any artifact type not listed in FR-007 (including the original 8 types).
- **FR-009**: The decision-table completeness report MUST calculate the product of condition moduli, compare to rule count, identify missing combinations, and flag contradictions. A dash (irrelevant condition) in a rule acts as a wildcard: one rule with a dash in a condition of modulus N covers N combinations (standard Shiffman counting).
- **FR-010**: The Hybrid Artifact Catalog in `reference.md` MUST document all 12 artifact types with descriptions and type-specific L2 section shapes.
- **FR-011**: SKILL.md plan step 4 catalog list MUST include all 12 artifact types.
- **FR-012**: The `clinical-frame` section shape MUST include PICOTS fields: population, intervention, comparison, outcomes (list), timing, setting.
- **FR-013**: The `decision-table` section shape MUST include conditions (id, label, values), actions (id, label), and rules (id, when map, then list) following the Shiffman augmented decision table model.
- **FR-014**: The `assessment` section shape MUST include instrument metadata, items (id, text, type, options), and scoring (method, ranges with interpretations).
- **FR-015**: The `policy` section shape MUST include applicability, criteria (id, description, requirement_type, rule), and actions (approve/deny/pend with conditions).
- **FR-016**: Generated views MUST be overwritten on re-render (idempotent).
- **FR-017**: The render command MUST fail with a clear error if the artifact does not exist.
- **FR-018**: All path resolution MUST use the subdirectory structure exclusively (`structured/<name>/<name>.yaml`). No flat-path fallback is provided.

### Key Entities

- **Artifact Profile**: Defines keyword matching, section name, and key question for the planner. One per artifact type in `EXTRACT_ARTIFACT_PROFILES`.
- **L2 Artifact (control file)**: YAML source of truth at `structured/<name>/<name>.yaml`. Contains type-specific sections per the documented shapes.
- **Generated View**: Derived human-readable file (`.mmd`, `.md`) written to `structured/<name>/views/`. Regenerated from control file on each render invocation.
- **Hybrid Artifact Catalog**: The 12-type reference table mapping artifact types to their purpose, section shapes, and L3 targets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 12 artifact types are recognized by the planner — keyword-driven proposals produce the correct `artifact_type` for each.
- **SC-002**: `rh-skills render` produces at least one generated view file for every artifact type in the catalog.
- **SC-003**: Decision-table completeness reports correctly identify missing rules in 100% of test cases (complete tables, incomplete tables, tables with contradictions).
- **SC-004**: Full test suite passes with no regressions after the directory restructure.
- **SC-005**: A derived artifact can be validated and rendered in a single workflow without manual path adjustments.
- **SC-006**: SME-facing generated views (mermaid, tables) are syntactically valid and render correctly in standard markdown viewers.

## Clarifications

### Session 2026-04-17

- Q: Should existing flat-path artifacts be migrated or supported via fallback? → A: No backward compatibility needed. All artifacts use the new subdirectory structure exclusively.
- Q: How should dash/irrelevant conditions count in decision-table completeness? → A: Dash = wildcard; one rule covers N combinations (standard Shiffman counting).
- Q: Where should type-specific section shapes be enforced? → A: At render time — render validates required sections before generating views.
- Q: Should render support batch mode (--all) or single artifact only? → A: Single artifact only.

## Assumptions

- The existing 8 artifact types continue to work unchanged; this is additive.
- The L2 schema (`l2-schema.yaml`) does not constrain artifact types — it only validates required metadata fields. No schema file changes are needed for new types.
- The `clinical-frame` type is a scoping/framing artifact with no direct L3 computable target. It informs but does not participate in `combine`.
- Mermaid diagram generation is deterministic from the YAML structure (no LLM required for render).
- The render command is a pure CLI command (no LLM invocation) — it reads YAML and writes derived files.
- No backward compatibility for flat-path artifacts. All artifacts use the subdirectory structure exclusively; existing flat-path artifacts must be re-derived.
- The L3 schema and formalize skill will eventually target FHIR/CQL/FHIRPath directly, but that is out of scope for this feature (documented as future direction).
