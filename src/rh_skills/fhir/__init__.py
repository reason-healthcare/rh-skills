"""FHIR output validation, normalization, and packaging.

Hybrid LLM + Validation Architecture
-------------------------------------
The LLM generates FHIR R4 JSON content guided by type-specific strategy
instructions in SKILL.md and reference.md.  Python code in this module
validates and normalizes the LLM output post-generation:

- **normalize** — mechanical fixes (ids, urls, dates, required fields)
- **validate**  — structural completeness checks per resource type
- **packaging** — FHIR NPM package bundling (package.json, IG resource)

Clinical content is never rewritten — that is the LLM's responsibility.
"""
