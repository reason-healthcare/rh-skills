# Feature Specification: L2→L3 Formalization Strategies

**Feature Branch**: `011-formalize-strategies`  
**Created**: 2026-04-17  
**Status**: Draft  
**Depends On**: [006 — rh-inf-formalize](../006-rh-inf-formalize/), [010 — L2 artifact catalog](../010-l2-artifact-catalog/)  
**Input**: User description: "L2 to L3 formalization strategy business rules and type-specific FHIR conversion mappings for the rh-inf-formalize skill"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Type-specific formalize plan generation (Priority: P1)

A clinical informaticist runs `rh-inf-formalize plan <topic>` on a topic
whose approved L2 artifacts include various types (e.g., a `decision-table`
and a `terminology`). The plan mode reads each L2 artifact type, selects the
correct formalization strategy for that type, and proposes L3 FHIR target
resources with the right structure. The resulting `formalize-plan.md` names
the concrete FHIR resource types and required sections per strategy rather
than defaulting everything to a generic "pathway-package."

**Why this priority**: Without type-specific strategies, the formalize plan
proposes the same generic pathway-package structure regardless of input type,
producing incorrect or incomplete L3 artifacts.

**Independent Test**: Run `rh-inf-formalize plan <topic>` on a topic with an
approved `decision-table` artifact. Confirm the plan proposes a
PlanDefinition (ECA-rule) target with `condition[]` and `action[]` sections,
not a generic pathway with `steps[]`.

**Acceptance Scenarios**:

1. **Given** a topic with an approved `evidence-summary` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes Evidence and
   EvidenceVariable target resources with findings, populations, and certainty
   sections.
2. **Given** a topic with an approved `decision-table` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes a PlanDefinition
   (ECA-rule) target with condition-action mapping sections.
3. **Given** a topic with an approved `care-pathway` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes a PlanDefinition
   (clinical-protocol) target with ordered action and trigger sections.
4. **Given** a topic with an approved `terminology` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes ValueSet (and
   ConceptMap when mappings exist) targets.
5. **Given** a topic with an approved `measure` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes a Measure target
   with population groups and scoring type.
6. **Given** a topic with an approved `assessment` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes a Questionnaire
   target with item structure and scoring sections.
7. **Given** a topic with an approved `policy` artifact, **When**
   `rh-inf-formalize plan` runs, **Then** the plan proposes a PlanDefinition
   (ECA-rule) target with coverage criteria and decision action sections.

---

### User Story 2 — Type-specific implement execution (Priority: P1)

After a reviewer approves a type-specific formalize plan, a clinical
informaticist runs `rh-inf-formalize implement <topic>`. The implement mode
applies the correct conversion rules for each L2 input type: mapping L2
sections to the right FHIR resource structure, resolving terminology via MCP
where needed, and producing a computable artifact whose shape matches the
strategy's L3 target.

**Why this priority**: Implement is the stage that produces the actual L3
output. If conversion rules are wrong for a given L2 type, the computable
artifact will be structurally invalid or clinically incomplete.

**Independent Test**: Approve a formalize plan for a topic with a `measure`
artifact, run implement, and confirm the computable artifact contains
`group[].population[]` entries mapping to the L2 populations, a `scoring`
value, and Library expression references — not generic pathway steps.

**Acceptance Scenarios**:

1. **Given** an approved plan with a `terminology` input, **When** implement
   runs, **Then** the computable output contains `ValueSet-<id>.json` resource(s)
   with MCP-resolved codes in `compose.include[]` and (if mappings exist)
   `ConceptMap-<id>.json` resource(s) with source→target equivalences.
2. **Given** an approved plan with a `decision-table` input containing 3+
   levels of nesting, **When** implement runs, **Then** the computable artifact
   contains nested `action[].action[]` ECA structures that preserve the full
   decision depth.
3. **Given** an approved plan with a `care-pathway` input containing timed
   steps, **When** implement runs, **Then** the computable artifact contains
   ordered actions with timing constraints.

---

### User Story 3 — Type-specific verify validation (Priority: P2)

A clinical informaticist runs `rh-inf-formalize verify <topic>` after
implement. Verify checks that the computable artifact's structure matches the
expected L3 shape for the strategy that produced it — not just generic section
presence but type-appropriate completeness rules (e.g., a Measure must have
populations with numerator and denominator; a Questionnaire must have items
with linkIds).

**Why this priority**: Type-specific verification catches structural errors
that generic section-presence checks would miss.

**Independent Test**: Run verify on a computable artifact produced from a
`measure` input that is missing a denominator population. Confirm verify
reports the specific missing population rather than a generic "section
incomplete."

**Acceptance Scenarios**:

1. **Given** a completed `measure` formalization missing a denominator,
   **When** verify runs, **Then** it reports "Measure group missing
   denominator population" and exits non-zero.
2. **Given** a completed `terminology` formalization with an invalid SNOMED
   code, **When** verify runs, **Then** it calls
   `reasonhub-codesystem_verify_code` and reports the specific code failure.
3. **Given** a completed `assessment` formalization missing item linkIds,
   **When** verify runs, **Then** it reports the specific missing linkIds.

---

### User Story 4 — Multi-type convergence (Priority: P2)

A clinical informaticist runs formalize on a topic with multiple L2 artifact
types (e.g., a `decision-table` + `terminology` + `evidence-summary`). The
plan proposes a convergence strategy that applies each type's strategy
independently and merges the outputs into one computable package, with
explicit handling of overlap between inputs.

**Why this priority**: Real clinical guidelines produce multiple L2 artifact
types that must be combined into a coherent L3 package.

**Independent Test**: Run formalize plan on a topic with 3+ different L2
artifact types. Confirm the plan identifies the per-type strategy for each
input and documents merge precedence for overlapping FHIR resource types.

**Acceptance Scenarios**:

1. **Given** a topic with `decision-table` and `terminology` inputs, **When**
   plan runs, **Then** the plan proposes a PlanDefinition target with embedded
   ValueSet references, documenting how terminology codes bind to decision
   conditions.
2. **Given** a topic with two inputs that both produce PlanDefinition
   resources (e.g., `decision-table` and `care-pathway`), **When** plan runs,
   **Then** the plan flags the overlap and specifies merge precedence or
   requests reviewer resolution.

---

### Edge Cases

- What happens when an L2 artifact type is `custom` (not one of the 7 standard types)? The system should fall back to generic pathway-package strategy and warn.
- What happens when a `terminology` artifact has zero codes (only concept names without systems)? Implement must still attempt MCP resolution and report any codes it cannot resolve.
- What happens when a `decision-table` has 5+ levels of nesting? The strategy must preserve full depth without flattening; verify confirms nesting integrity.
- What happens when a `measure` has composite scoring (multiple measure groups)? Each group must produce its own population set.
- What happens when convergence selects inputs that produce conflicting resource structures? The plan must surface the conflict for reviewer resolution rather than silently merging.
- What happens when MCP terminology tools are unreachable during implement? The system must produce resources with `TODO:MCP-UNREACHABLE` placeholder codes, warn in output, and continue. Verify mode catches unresolved placeholders as errors.
- What happens when `rh-skills formalize` fails partway through generating resources? Keep partially written files, report which resources failed, exit non-zero. Verify catches incomplete resource sets.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The formalize skill MUST select a type-specific formalization strategy based on each L2 input artifact's `artifact_type` field. The strategy mapping is defined in `docs/FORMALIZE_STRATEGIES.md` and encoded in the formalize SKILL.md and reference.md.
- **FR-002**: Each strategy MUST define the L3 FHIR resource type(s) it produces, the required computable sections, and the L2→L3 section mapping rules.
- **FR-003**: Plan mode MUST propose strategy-appropriate L3 targets and required sections per input artifact type, written via `rh-skills promote formalize-plan`.
- **FR-004**: Implement mode MUST apply the type-specific conversion rules when generating FHIR JSON resources via `rh-skills formalize <topic> <artifact>`. All writes go through CLI commands.
- **FR-005**: Verify mode MUST check type-specific completeness rules (not just section presence) for the L3 target structure. Verify is non-destructive and safe to rerun.
- **FR-006**: When multiple L2 inputs converge, the plan MUST document per-input strategy selection, merge precedence for overlapping FHIR resource types, and surface conflicts for reviewer resolution.
- **FR-007**: The formalize SKILL.md and reference.md MUST document all 7 L2→L3 strategy mappings with L2 input shapes, L3 output shapes, conversion rules, and MCP tool usage.
- **FR-008**: Eval scenarios MUST exist for each of the 7 L2 types as formalize inputs, plus at least one multi-type convergence scenario.
- **FR-009**: Unknown or custom artifact types MUST fall back to the generic pathway-package strategy with a warning.
- **FR-010**: L3 output MUST be individual FHIR JSON resources (not YAML sections), written to `topics/<topic>/computable/` via `rh-skills formalize`. Each successful formalization appends a `computable_converged` event to tracking.yaml.
- **FR-011**: A separate `rh-skills package <topic>` command MUST bundle all computable resources into a FHIR package with `package.json` and `ImplementationGuide` following NPM conventions. Successful packaging appends a `package_created` event to tracking.yaml.
- **FR-012**: CQL Library generation MUST produce compilable CQL where the L2 definition is structured enough; pseudocode stubs with `// TODO` markers are used only when natural-language-only input prevents mechanical translation.

### Key Entities

- **Formalization Strategy**: A named set of conversion rules mapping one L2 artifact type to specific L3 FHIR resource types. Attributes: L2 type, L3 target resources, required sections, section mapping rules, MCP tool usage pattern.
- **L2 Artifact**: An approved structured artifact with `artifact_type` from the hybrid catalog. Input to formalization.
- **L3 Computable Artifact**: The FHIR-aligned output produced by applying a formalization strategy. Lives in `topics/<topic>/computable/`.
- **Convergence Plan**: A formalize-plan.md that selects multiple L2 inputs, assigns each a strategy, and documents merge rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 7 L2 artifact types have a documented formalization strategy in `docs/FORMALIZE_STRATEGIES.md` with concrete L2→L3 mapping rules (not placeholders).
- **SC-002**: The formalize skill (SKILL.md + reference.md) encodes all 7 strategies so that an agent can select and apply the correct conversion without external guidance.
- **SC-003**: Eval scenarios exist for each of the 7 L2 types as formalize inputs, and each scenario's expected output matches the strategy's L3 target shape.
- **SC-004**: A multi-type convergence scenario (3+ L2 types) produces a valid merged computable package with no unresolved resource conflicts.
- **SC-005**: Type-specific verify rules catch at least one structural error per strategy that generic section-presence checks would miss.

## Clarifications

### Session 2026-04-18

- Q: What tracking events should `rh-skills formalize` and `rh-skills package` append to tracking.yaml? → A: `rh-skills formalize` appends `computable_converged` per artifact; `rh-skills package` appends `package_created`.
- Q: How should `rh-skills formalize` behave when MCP terminology tools are unreachable? → A: Produce resource with `TODO:MCP-UNREACHABLE` placeholder codes; warn in output; verify catches them as errors.
- Q: What FHIR version should L3 output target? → A: FHIR R4 (4.0.1) + CQL 1.5, matching the US Core / QI-Core ecosystem.
- Q: What should happen when `rh-skills formalize` fails partway through? → A: Keep partial output (leave successfully written files), report which resources failed, exit non-zero. Verify catches incomplete sets.

## Assumptions

- The 7-type L2 hybrid catalog (evidence-summary, decision-table, care-pathway, terminology, measure, assessment, policy) is stable and will not change during this feature's implementation.
- L3 output targets FHIR R4 (4.0.1) and CQL 1.5, consistent with the US Core / QI-Core / CRMI ecosystem. All resource structures, profile conformance, and package dependencies assume R4.
- The existing `rh-skills promote combine` command will be replaced by two new commands: `rh-skills formalize <topic> <artifact>` (generates FHIR JSON + CQL) and `rh-skills package <topic>` (bundles into FHIR package). The `promote combine` command will be deprecated.
- MCP terminology resolution tools (reasonhub-search_*, codesystem_lookup, valueset_expand, codesystem_verify_code) are available in the formalize implement and verify modes.
- The `docs/FORMALIZE_STRATEGIES.md` document serves as the authoritative business-rules reference; SKILL.md and reference.md encode the operational subset needed by agents.
- CQL Library generation will produce compilable CQL where the L2 definition is structured enough; pseudocode stubs are a fallback for natural-language-only inputs.
- Case feature definitions (StructureDefinition profiles) are deferred to v2; v1 uses plain `Library.dataRequirement` entries without profile references.
- DTR Questionnaire CQL pre-population (initialExpression + companion Library) is deferred to v2; v1 generates Questionnaire structure without CQL pre-population.
