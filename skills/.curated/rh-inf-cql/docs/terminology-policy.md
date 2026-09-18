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
- no matching clinical code (false/empty retrieve, with null only when the authored clinical rule says evidence is incomplete)
- unavailable, incomplete, or wrong-version ValueSet dependency (execution failure, not clinical null)
- version-sensitive behavior where applicable

Keep the terminology boundary aligned with the resource being evaluated.
FHIR R4 `QuestionnaireResponse.item` has a `linkId` and answer, not the
Questionnaire item's LOINC Coding. Logic that evaluates a response before
extraction should bind the exact Questionnaire canonical/version and expected
linkIds; it should not pretend QR answers are coded observations. For an SDC
Questionnaire-to-Observation workflow, test `Observation.code` against the
declared ValueSet and separately assert the extracted Coding's system, version,
code, display, subject, encounter, status, and provenance. ValueSet membership
tests should vary code and system and should test missing or wrong
canonical/version resolution. Do not expect changing only `Coding.version` or
display to change standard CQL membership semantics.

The `rh-skills cql test` runner accepts an optional `input/terminology.json`
sidecar per case. It may contain one pre-expanded ValueSet or a Bundle of
pre-expanded ValueSets and is passed to the runtime via `--terminology`. A
normalized extracted-resource Bundle is an oracle fixture; it does not establish
that an extraction implementation produced those resources.

Place these in `tests/cql/terminology/`.

## Manifesting

Record major terminology dependencies in:
- `src/manifests/terminology.yaml` — authoring-time declarations
- `context/terminology/version-manifest.yaml` — resolved runtime versions

## Offline Behavior

The `rh` evaluator resolves terminology offline by default. Value sets must be
pre-expanded or bundled into the fixture if a terminology service is not available.
