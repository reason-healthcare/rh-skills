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
Clinical decision CQL consumes extracted clinical resources, including
Observations from both scored and unscored assessments; it does not evaluate
QuestionnaireResponse answers. FHIR R4 `QuestionnaireResponse.item` has a
`linkId` and answer, not the Questionnaire item's LOINC Coding. An SDC
Questionnaire-to-Observation workflow carries that Coding onto the extracted
Observation. Test
`Observation.code` against the declared ValueSet and separately assert the
extracted Coding's system, version, code, display, subject, encounter, status,
and provenance. Preserve source linkage in the extraction output, but do not
require QuestionnaireResponse or `derivedFrom` to select clinical evidence.
ValueSet membership tests should vary code and system and should test missing
or wrong canonical/version resolution. Do not expect changing only
`Coding.version` or display to change standard CQL membership semantics.

The `rh-skills cql test` runner accepts an optional `input/terminology.json`
sidecar per case. It may contain one pre-expanded ValueSet or a Bundle of
pre-expanded ValueSets and is passed to the runtime via `--terminology`. A
normalized extracted-resource Bundle is an oracle fixture; it does not establish
that an extraction implementation produced those resources.

Place these in `tests/cql/terminology/`.

## Categorical classifier inventory

Before authoring CQL, inventory every Boolean or enum classifier over a FHIR
`Coding` or `CodeableConcept`. The inventory includes positive/negative,
normal/abnormal, detected/not-detected, stage, grade, status, interpretation,
and local categories. It must cover the whole library; converting one category
does not satisfy the authoring inventory. A category whose reviewed ValueSet
currently contains one code is still part of the inventory.

Each inventory row records the source path, output category, reviewed ValueSet
canonical/version, current-run terminology evidence, the one named Concept
conversion helper, named membership Booleans, and null/neither/both policy.
When one or many codes or coding systems express an authored category, define
that category with a reviewed, versioned ValueSet rather than direct-reference
Code comparisons. For each classified FHIR element, call the pinned
`FHIRHelpers.ToConcept()` exactly once in one named helper, then reuse the
resulting CQL `Concept` in every named membership Boolean.

Direct comparison with a declared `Code` is limited to a true exact
single-concept predicate that is not functioning as a Boolean or enum category.
Document why it is exact. Positive or negative meaning is categorical even
when represented by one code, so it requires a ValueSet.

Use `if`/`else if`/`case` only to preserve cardinality, null, type, conflict,
or three-valued semantics. Category branches reference named membership
Booleans; they do not compare raw Codes or repeat `FHIRHelpers.ToConcept()`.

Concept membership succeeds when any code in the Concept belongs to the
ValueSet. It does not infer order, severity, stage hierarchy, or subsumption
from the ValueSet's name. Each classification ValueSet must explicitly select
the intended system/code identities through its reviewed definition and
complete runtime expansion.

For true/false classifications represented by two ValueSets:

- require a source-backed clinical contract that defines both categories; do
  not invent the false/contrasting ValueSet from absence or non-membership;
- require the sets to be mutually exclusive by definition;
- return `null` for an absent or non-`CodeableConcept` value;
- return `null`, or otherwise raise a separately authored data-quality result,
  when a multi-coded Concept matches both sets;
- return `null` when the Concept matches neither set; and
- treat an unresolved, incomplete, or wrong-version ValueSet as an execution
  failure rather than clinical uncertainty.

Test at least one member from each intended coding system, one member of the
contrasting category, an out-of-set code, an absent/wrong-type value, a
multi-coded input whose codings agree, and a conflicting multi-coded input.
For intentionally one-code positive/negative interpretation ValueSets, test the
single current member and an out-of-set code, and retain the same ValueSet
contract when later terminology review adds synonyms. For a cross-system
category, test at least one member from every included system and prove that
the named membership Boolean produces the same category for each.

## Manifesting

Record major terminology dependencies in:
- `src/manifests/terminology.yaml` — authoring-time declarations
- `context/terminology/version-manifest.yaml` — resolved runtime versions

## Offline Behavior

The `rh` evaluator resolves terminology offline by default. Value sets must be
pre-expanded or bundled into the fixture if a terminology service is not available.
