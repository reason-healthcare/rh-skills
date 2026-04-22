# Summarize Library

Use this prompt to produce an implementation-facing summary of a CQL library.

## Prompt

Summarize this CQL library for an implementation or review audience.

## Output Sections

### Purpose
One or two sentences describing the clinical or computational intent.

### Key Definitions
List important expressions with their expected result type and a one-line
description:

| Definition | Type | Description |
|------------|------|-------------|
| Initial Population | Boolean | Patients with at least one qualifying condition |
| ... | ... | ... |

### Model and Dependencies
- Target CQL version
- FHIR version
- Included libraries and versions
- Known translator options

### Terminology Usage
List declared value sets and code systems. Note which have pinned versions and
which are unpinned.

### Runtime Assumptions
Note any assumptions about the evaluator, CLI flags, or execution context.
If unknown, state that explicitly.

### Likely Review or Testing Risks
Flag any patterns that deserve close review or additional test coverage:
- ambiguous null handling
- interval boundary behavior
- unpinned terminology
- complex retrieve filters
- missing documentation
