# Research: L2 Artifact Catalog Expansion

**Feature**: 010-l2-artifact-catalog  
**Date**: 2026-04-17

## Decision 1: Decision-Table Completeness Algorithm

**Decision**: Implement Shiffman augmented decision table completeness check with
wildcard (dash) expansion.

**Rationale**: The Shiffman 2001 model (PMC61256) defines completeness as: product
of condition moduli = sum of rule coverage counts. A dash (irrelevant condition) in
a rule with condition modulus N means that rule covers N combinations. This is the
standard model for clinical guideline decision tables and provides a verifiable
completeness metric.

**Algorithm**:
1. For each condition, compute modulus = len(values).
2. Total space = product of all moduli.
3. For each rule, compute coverage = product of moduli for each dashed condition.
4. Sum all rule coverages. If sum == total space, table is complete.
5. For contradiction check: expand dashes and verify no two rules map the same
   combination to different actions.

**Alternatives considered**:
- Simple rule count (ignores dashes, incorrect for real clinical tables)
- Full enumeration (correct but O(2^n) for large tables; warn when n > 10)

## Decision 2: Render Architecture — Dispatcher Pattern

**Decision**: Use a type→renderer dispatcher in `render.py`. Each artifact type maps
to a renderer function. Unknown types fall back to `_render_generic_summary`.

**Rationale**: Clean separation of concerns. Each renderer reads type-specific
sections from the YAML and writes view files. Adding a new renderer for a future
type requires only adding a function and a dispatcher entry.

**Pattern**:
```python
RENDERERS = {
    "decision-table": render_decision_table,
    "assessment": render_assessment,
    "policy": render_policy,
    "clinical-frame": render_clinical_frame,
}

def render(topic, artifact):
    yaml = load_artifact(topic, artifact)
    artifact_type = yaml.get("artifact_type", "")
    renderer = RENDERERS.get(artifact_type, render_generic_summary)
    renderer(yaml, views_dir)
```

**Alternatives considered**:
- Plugin-based renderers (over-engineered for 12 types)
- Single monolithic function with if/elif (harder to test)

## Decision 3: Section Shape Validation at Render Time

**Decision**: Render validates required type-specific sections before generating views.
Derive does NOT validate section shapes (LLM output is best-effort).

**Rationale**: Derive writes LLM output; enforcing schema at that point would require
post-processing that could corrupt output. Render is the first deterministic consumer
of the YAML — the right place to catch structural issues. Validation errors at render
time are clear and actionable: "decision-table missing required section: conditions".

**Alternatives considered**:
- Validate at derive time (rejected: LLM output can't be reliably schema-checked mid-generation)
- Validate at both points (rejected: duplicate validation, confusing error messages)

## Decision 4: Directory Restructure — No Backward Compatibility

**Decision**: All artifacts use `structured/<name>/<name>.yaml` exclusively. No
flat-path fallback. Existing flat-path artifacts must be re-derived.

**Rationale**: User confirmed no backward compatibility needed. This simplifies all
path resolution code (single code path) and avoids the complexity of dual-path
lookups. Existing topics with flat-path artifacts are expected to be re-derived as
part of normal workflow iteration.

**Impact**: ~30 path references across promote.py, validate.py, tracking-schema.yaml,
eval fixtures, tests. All updated in a single pass.

**Alternatives considered**:
- Flat-path fallback (rejected by user: unnecessary complexity)
- Migration command (rejected: re-derive is the natural workflow)

## Decision 5: Mermaid Output Format

**Decision**: Use Mermaid `.mmd` files for diagram views. Markdown files embed
mermaid code blocks for GitHub rendering.

**Rationale**: Mermaid is natively supported by GitHub markdown rendering and most
documentation tools. Writing standalone `.mmd` files allows tooling to render them
independently, while embedding in markdown provides immediate in-repo preview.

**Alternatives considered**:
- PlantUML (less GitHub integration)
- Graphviz DOT (requires external renderer)
- SVG (not easily diffable in git)

## Decision 6: Generic View for Existing 8 Types

**Decision**: The generic markdown summary view extracts metadata fields (id, title,
domain, description, artifact_type, clinical_question) and renders the `sections`
block as formatted markdown with headers per section key.

**Rationale**: All existing L2 artifacts share the same YAML shape (metadata +
`sections` dict). The generic renderer iterates section keys, formats each as a
markdown heading with content below, producing a readable summary without
type-specific logic.

**Alternatives considered**:
- YAML dump (not SME-friendly)
- No view for existing types (inconsistent experience)
