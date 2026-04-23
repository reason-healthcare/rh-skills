# Terminology Policy

Terminology assumptions must be reproducible whenever possible.

## General Rules

- Prefer explicit versions for value sets and code systems when reproducibility matters.
- Track expansion assumptions when using pre-expanded content.
- Keep terminology metadata close to the logic or in a manifest that is easy to inspect.
- Do not assume value set membership from display text or naming conventions alone.

## Declaration Pattern

Declare all value sets and code systems at the top of each CQL library:

```cql
codesystem "SNOMED-CT": 'http://snomed.info/sct'
  version 'http://snomed.info/sct/731000124108/version/20240301'

valueset "Hypertension": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113883.3.464.1003.104.12.1011'
  version '20230101'
```

## Classification

| Risk | When to pin |
|------|-------------|
| High | Guideline-based quality measures, regulatory reporting |
| Medium | Clinical decision support rules with known boundary dates |
| Low | Internal analytics, exploratory libraries |

When risk is High, always pin. When risk is Low, document the assumption.

## Test Expectations

Include terminology-focused tests for:
- in-value-set membership (positive)
- out-of-value-set membership (negative)
- missing or unresolved terminology (null behavior)
- version-sensitive behavior where applicable

Place these in `tests/cql/terminology/`.

## Manifesting

Record major terminology dependencies in:
- `src/manifests/terminology.yaml` — authoring-time declarations
- `context/terminology/version-manifest.yaml` — resolved runtime versions

## Offline Behavior

The `rh` evaluator resolves terminology offline by default. Value sets must be
pre-expanded or bundled into the fixture if a terminology service is not available.
