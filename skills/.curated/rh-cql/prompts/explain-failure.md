# Explain Failure

Use this prompt to explain a CQL translation or runtime failure.

## Prompt

Explain this CQL translation or runtime failure in plain language.

## Output Format

### Failure Category
Classify using the Failure Categories table in SKILL.md:
- e.g., `translation`, `null-propagation`, `terminology-resolution`, `fixture-or-data-shape`

### Minimal Failing Condition
Describe the smallest input or code state that reproduces the failure.
If a fixture is available, identify which case and which expression failed.

### Probable Root Cause
Explain in plain language what the evaluator or translator encountered.
Prefer precise technical explanation over vague summary.

### Evidence
Quote the relevant CQL, error message, or ELM excerpt that supports the diagnosis.

### Minimal Safe Fix
Describe the smallest change to the CQL or fixture that would resolve the failure.
Do not propose rewrites unless necessary.

### Regression Test to Add
Name the test case that should be added to prevent recurrence:
- Case name
- Case type
- Expected outcome
- What it isolates

See `prompts/propose-minimal-fix.md` for the next step.
