# Research: L2→L3 Formalization Strategies

**Feature**: 011-formalize-strategies | **Date**: 2026-04-17

## Decision 1: L3 Output Format — FHIR JSON replacing YAML

**Decision**: Replace the current YAML-based L3 output (`artifact_schema_version: "1.0"`, monolithic sections) with individual FHIR R4 JSON resource files.

**Rationale**: The current `promote combine` produces a custom YAML schema that doesn't align with any FHIR tooling, validation infrastructure, or IG publishing pipeline. FHIR JSON is the canonical wire format for R4, directly consumable by FHIR validators (HL7 FHIR Validator), IG Publisher, CQF Tooling, and terminology servers.

**Alternatives considered**:
- FHIR XML: Valid but JSON is the dominant format in the US CQL/CDS ecosystem.
- FHIR Bundle as single file: Rejected because individual resources enable per-artifact formalization and selective re-generation without touching the whole bundle.
- Keep YAML with FHIR-aligned schema: Rejected because it creates a translation step that adds no value and risks schema drift.

## Decision 2: Command Architecture — Separate formalize and package

**Decision**: Two new commands: `rh-skills formalize <topic> <artifact>` (per-artifact FHIR JSON generation) and `rh-skills package <topic>` (FHIR NPM bundle creation).

**Rationale**: Formalization and packaging are distinct concerns. Formalization converts one L2 artifact to one-or-more FHIR JSON resources; packaging collects all formalized resources into a distributable FHIR package. Separating them enables:
- Re-running formalize on a single artifact without re-packaging
- Packaging only after all artifacts pass verify
- Clear tracking events per concern (`computable_converged` vs `package_created`)

**Alternatives considered**:
- Single command (`promote combine` with new output): Rejected because it conflates generation and bundling, making partial re-runs impossible.
- Three commands (formalize + verify + package): Verify already exists as a mode, not a separate command. No change needed.

## Decision 3: Hybrid LLM + Validation Architecture

**Decision**: The LLM generates FHIR JSON content guided by type-specific strategy instructions in SKILL.md/reference.md. Python code in `src/rh_skills/fhir/` validates and normalizes the LLM output post-generation.

**Rationale**: This follows the existing `promote combine` pattern (LLM-driven content generation with CLI as write boundary) while adding structural guarantees. The LLM has the flexibility to handle the diverse L2→L3 mappings across 7 artifact types, while Python normalization ensures consistent ids, urls, dates, and required FHIR fields. This avoids building 7 separate mechanical transformers (which would be brittle and expensive to maintain) while preventing the LLM from producing structurally invalid FHIR JSON.

**Alternatives considered**:
- Pure deterministic Python builders: Over-engineered — would require mechanical transformation code for 7 strategies with deep FHIR knowledge embedded in Python. Expensive to build and maintain.
- Pure LLM without validation: Risky — LLM output may have inconsistent ids, missing required fields, or incorrect canonical URLs.
- Plugin/strategy class hierarchy: Unnecessary complexity for 7 static strategies.

## Decision 4: FHIR Output Normalization Scope

**Decision**: Python normalization handles: resource id format (kebab-case), canonical URL pattern, version string, status field, date format, resourceType correctness, and required field presence. It does NOT rewrite clinical content — that's the LLM's responsibility.

**Rationale**: Normalization fixes the mechanical/structural aspects that LLMs frequently get wrong (URL patterns, date formats, id conventions) without second-guessing clinical mappings. This is a thin validation layer, not a transformation engine.

## Decision 5: CQL Generation Approach

**Decision**: Generate compilable CQL source files (`.cql`) alongside FHIR Library resources. CQL is generated mechanically where L2 structure is sufficient; pseudocode stubs (`// TODO`) where natural-language-only input prevents translation.

**Rationale**: CQL is required by Using CQL With FHIR IG for computable measures, decision support, and order sets. Generating compilable CQL (not just pseudocode) enables downstream validation with CQL-to-ELM translation and integration with CQF Tooling.

**Alternatives considered**:
- No CQL (defer entirely to v2): Rejected because measures and decision tables without CQL are not truly computable.
- Full CQL with semantic validation: Deferred — v1 generates syntactically valid CQL; semantic validation (terminology bindings resolve, types check) is a v2 concern.
- ELM-only (skip CQL source): Rejected because CQL source is the authoritative human-readable form.

## Decision 6: MCP Failure Handling

**Decision**: When MCP tools are unreachable during implement, produce resources with `TODO:MCP-UNREACHABLE` placeholder codes, warn in CLI output, and continue. Verify mode catches these as errors.

**Rationale**: Partial output with explicit markers is more useful than complete failure. It preserves progress, lets reviewers see which codes need resolution, and aligns with the CQL `// TODO` stub pattern. The verify command provides a separate validation pass that will surface all unresolved items.

**Alternatives considered**:
- Fail entirely: Rejected because a single MCP timeout shouldn't discard all formalization work.
- Use L2 candidate_codes without validation: Risky — unvalidated codes could propagate silently.

## Decision 7: Partial Failure Behavior

**Decision**: When `rh-skills formalize` fails partway through generating resources, keep successfully written files, report which resources failed, and exit non-zero.

**Rationale**: Consistent with MCP-UNREACHABLE handling — preserve partial progress, make failures explicit. The verify command will catch incomplete resource sets as part of its type-specific completeness checks.

## Decision 8: FHIR Package Structure

**Decision**: `rh-skills package <topic>` produces a FHIR NPM package in `topics/<topic>/package/` containing `package.json`, `ImplementationGuide-<id>.json`, and all FHIR JSON + CQL files from `computable/`.

**Rationale**: FHIR packages follow NPM conventions per the [FHIR Package Specification](https://registry.fhir.org/learn). This enables publishing to FHIR registries and consumption by IG Publisher, CQF Tooling, and FHIR validators. The `package.json` declares dependencies on US Core, CRMI, and domain-specific IGs.

**Alternatives considered**:
- FHIR Bundle resource as package: A Bundle is a transport format, not a distribution format. It doesn't support `package.json` metadata or dependency declarations.
- Zip/tar archive only: Loses the NPM convention benefits (dependency resolution, registry publishing).

## Decision 9: Deprecation Path for promote combine

**Decision**: `promote combine` will be deprecated with a warning message pointing users to `rh-skills formalize` + `rh-skills package`. It will remain functional during the transition period but will not receive new features.

**Rationale**: Breaking existing workflows immediately would block in-progress topics. A deprecation warning gives users time to migrate.

**Alternatives considered**:
- Remove immediately: Too disruptive for active topics.
- Keep both indefinitely: Violates Principle V (minimal surface area) — two write paths for the same concern.
