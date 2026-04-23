# Review Library

Use this prompt to produce a structured review report for a CQL library.

## Prompt

Review the CQL library using the full review checklist in `docs/review-checklist.md`
and the high-risk pattern catalog in `SKILL.md`.

## Output Sections

### Context
State the effective environment and assumptions:
- CQL version
- FHIR version and model
- Included libraries and versions
- Translator options
- Runtime engine
- Terminology dependencies and version pins

Note clearly what is missing and the likely impact of each gap.

### Findings
For each finding:
- **Classification**: `BLOCKING`, `ADVISORY`, or `INFO`
- **Checklist area**: Which area triggered this finding
- **Evidence**: Quoted CQL excerpt or file location
- **Recommendation**: Smallest safe change to address it

List BLOCKING findings first.

### Proposed Changes
Show before/after for any CQL edit proposed. Explain the semantic impact,
not just the textual change.

### Test Scenarios
List new or updated test cases required. For each:
- Case name (e.g., `case-003-null-measurement`)
- Case type (positive/negative/null/boundary/terminology)
- Expected outcome
- What semantic point the case isolates

### Remaining Uncertainty
State explicitly what cannot be confirmed from current context.
