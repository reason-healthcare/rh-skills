# CQL Style Guide

Use this guide when authoring or reviewing FHIR CQL. Examples target FHIR R4
4.0.1; use the CQL version accepted by the configured translator (the current
`rh` authoring setup targets CQL 1.5.3) and pin/test that translator. The
published CQL 2.0.0 guide is cited for context and retrieve rules that also
apply here. FHIR model metadata defines which coded path a retrieve filter
uses. The rules below describe CQL semantics where stated; retrieve factoring
and helper layout are house-style preferences, not language restrictions.

## Patient context is part of the query

Declare `context Patient` for patient-specific decision support and measure
expressions. A Patient-context retrieve is scoped to the current patient when
the selected FHIR ModelInfo defines that context relationship and the engine
honors it. Do not repeat that intended scope by comparing
`Encounter.subject.reference` or `Observation.subject.reference` with
`Patient.id`.

```cql
library EncounterClassFilter version '1.0.0'
using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1' called FHIRHelpers

codesystem "ActCode":
  'http://terminology.hl7.org/CodeSystem/v3-ActCode'

code "Ambulatory":
  'AMB' from "ActCode" display 'Ambulatory'

parameter "Measurement Period" Interval<DateTime>

context Patient

define "Ambulatory Encounters":
  [Encounter: class ~ "Ambulatory"] E
    where FHIRHelpers.ToDateTime(E.period.start) in "Measurement Period"
```

The retrieve above relies on the Patient context contract for patient scope
and specifies the intended encounter class. Add explicit encounter-date
filters when the clinical rule requires them. Clinical decision CQL consumes
the extracted clinical resources: retrieve the intended Observation code set
and retain required final status, effective date, and selected-Encounter
linkage. Extraction may retain QuestionnaireResponse provenance such as
`derivedFrom`, but ordinary clinical reasoning must not retrieve or depend on
Questionnaire/QuestionnaireResponse resources or their identifiers. These
clinical relationships define meaning; Patient context does not replace them.

There is no blanket ban on `subject.reference` comparisons. They may be needed
for `context Unfiltered`, a deliberate cross-context query, or an explicit
source relationship. Use them only when the selected context does not already
provide that patient scope, and state why. If a runtime leaks other patients'
resources from a Patient-context retrieve, report a runtime conformance defect
and block that engine path. Do not make the CQL pass by adding subject guards.

The normative CQL specification describes [Patient context](https://cql.hl7.org/02-authorsguide.html#context)
and [retrieve context](https://cql.hl7.org/02-authorsguide.html#retrieve-context).
Check the pinned model's context relationship and test isolation with another
patient's data in the same input. If another patient's resource leaks through,
the engine/model contract is broken; do not hide it with an author-side filter.

### Join through a FHIR reference

When the source rule links an Observation to a selected Encounter, preserve
that relationship with a reference join. The HL7 Using CQL with FHIR STU2
`FHIRCommon` library provides a fluent `references()` function for this
pattern. Pin the included library and carry its matching Library/ELM dependency
through normal package closure:

```cql
library ScreeningReferenceJoin version '1.0.0'

using FHIR version '4.0.1'

include FHIRHelpers version '4.0.1' called FHIRHelpers
include FHIRCommon version '2.0.0'

codesystem "ActCode":
  'http://terminology.hl7.org/CodeSystem/v3-ActCode'

code "Ambulatory":
  'AMB' from "ActCode" display 'Ambulatory'

valueset "Unsteadiness Question":
  'https://example.org/fhir/ValueSet/unsteadiness-question' version '0.2.0'

parameter "Measurement Period" Interval<DateTime>

context Patient

define "Screening Encounters":
  [Encounter: class ~ "Ambulatory"] E
    where FHIRHelpers.ToDateTime(E.period.start) in "Measurement Period"

define "Unsteadiness Observations":
  [Observation: "Unsteadiness Question"] O
    with "Screening Encounters" E
      such that O.encounter.references(E)
```

The `references(Reference, Resource)` overload compares the reference's final
slash-delimited component with `resource.id`; it assumes both resources come
from the same source server. It does not check reference type, base URL,
canonical identity, or history/version semantics. Use it only when that
identity model matches the input contract. It preserves the resource-to-
resource relationship without manually constructing a reference string, and
does not replace Patient-context scoping. Keep required date, status, period,
and encounter relationships in the logic. Keep producer lineage such as
`Observation.derivedFrom` as extraction provenance; do not make it a clinical
selection predicate unless an explicitly source-defined audit rule requires
that lineage.

This specific function is provided by the pinned
[FHIRCommon 2.0.0 library](https://hl7.org/fhir/uv/cql/Library-FHIRCommon.html)
at canonical `http://hl7.org/fhir/uv/cql/Library/FHIRCommon|2.0.0`. Its
source and ELM must be available to the translator/runtime as a versioned
dependency; declaring only the include does not package the dependency. When a
local closure compiles the published source against a pinned FHIRHelpers
version, retain that exact helper source, ELM, model version, compiler options,
and resulting Library identity together.

For the Connectathon's pinned closure, the imported source is the HL7 CQL IG
2.0.0 package. The local FHIRCommon ELM was compiled from its published CQL
with CQFramework `cql-to-elm-cli` 3.26.0 (`--signatures Overloads`), FHIR R4
4.0.1 ModelInfo, and the pinned FHIRHelpers 4.0.1 CQL/ELM. The derivative ELM
SHA-256 is
`5b735bf1807df3518d365206797b7c1693cacc996d9e022eab5bd6ca11264817`; the
published package ELM is retained separately because its bundled helper bytes
differ. Import and link the derivative through `rh-skills cql import-library`
using its checksum manifest, rather than substituting same-version bytes.

## Consume a calculated assessment score

When the authored assessment defines a scored SDC item, downstream CQL reads
the resulting coded `Observation`; it does not repeat questionnaire scoring.
Use the score's declared ValueSet or CodeSystem/Code with typed terminology
operators, then apply the authored Observation status, integer type/range,
effective-time, and Encounter rules. With Patient context, rely on the pinned
ModelInfo/runtime scope and keep the explicit Encounter and time relationship.

For this score contract, exactly one valid score Observation across the
qualifying screening Encounters in the measurement period is required. No
match, a code outside the declared terminology, wrong status or value type, an
out-of-range value, wrong Encounter/time, or multiple valid scores leaves the
result unknown. Standard CQL Code equivalence and ValueSet membership select
by system and code; they do not filter input `Coding.version` or display text.
Preserve the authored version in the CodeSystem, generated Observation, and
evidence, but do not claim that a typed retrieve rejects a different input
version. If a source-defined rule requires version-based selection and the
configured translator/runtime cannot express it with a tested typed operation,
record that as a capability gap rather than splitting system/code strings. A
score value of `0` is a valid present score; do not treat it as missing or
false. The interpretation threshold comes from the authored L2 classification
and its cited source, not from the Observation's mere existence.

Keep this boundary independent of the score producer. CQL must not retrieve
`Questionnaire` or `QuestionnaireResponse`, recompute from answer items, or
require response identifiers or `Observation.derivedFrom` links. A separately
produced Observation with the same reviewed immutable score system/code, a
final status, an integral value that satisfies the declared range and validity
rules, and the required encounter/time context must be eligible for the same
downstream logic even if its input `Coding.version` is absent or different.
Preserve any supplied version as provenance; it is not a membership filter.
Test alternate Observation-only inputs with omitted and differing
`Coding.version` explicitly.

For unscored or item-level assessments, evaluate the extracted, item-coded
Observations directly; do not read QuestionnaireResponse answers in clinical
CQL. Do not add a calculated score just to make a downstream retrieve easier,
and do not describe a local numeric encoding as a validated instrument unless
its source establishes that claim. A source-defined audit use of response
resources is a separate, explicit rule and not the default clinical pathway.

## Use typed terminology operators

Declare the clinical code or value set, then use CQL terminology operators.
This keeps system/code identity together and lets the model's typed code paths
and terminology service resolve membership or equivalence.

```cql
[Encounter: class ~ "Ambulatory"] E
```

This filter uses the CodeSystem and Code declarations from the complete library
above.

FHIR R4 models `Encounter.class` as a `Coding`, while the Encounter retrieve's
primary code path is `Encounter.type`. The explicit `class ~ "Ambulatory"`
filter targets the class code. A bare `[Encounter: "Ambulatory"]` targets the
primary `type` path instead. Confirm the relevant `primaryCodePath` and element
type in the pinned model information before authoring a retrieve filter.

For coded resources, prefer:

- `[Observation: "Question ValueSet"] O` when the resource's primary code
  should be in a declared, versioned ValueSet.
- `code in "Question ValueSet"` for membership of a typed code in a ValueSet.
- `class ~ "Ambulatory"` for code equivalence on an explicitly named
  non-primary `Coding` path.
- `=` only when exact equality, including the model's version/display semantics,
  is the actual rule.
- Primitive status fields such as `Observation.status` may use their defined
  status code (for example, `'final'`); they are not Coding/CodeableConcept
  terminology comparisons.

Do not replace a typed comparison with separate string checks such as
`E.class.system.value = '...' and E.class.code.value = '...'`. Do not filter a
non-primary code path by writing a bare ValueSet in the retrieve. Pin ValueSet
canonical/version and provide a complete matching expansion when the runtime
requires it. FHIR terminology `Coding.version` may matter to provenance or
validation even when standard CQL membership is defined by the ValueSet.

See the [CQL retrieve guide](https://cql.hl7.org/02-authorsguide.html#retrieve)
and the FHIR R4 [Encounter.class definition](https://hl7.org/fhir/R4/encounter-definitions.html#Encounter.class).

## Convert FHIR values only when the type requires it

Keep FHIR model types explicit. Include the pinned FHIRHelpers dependency when
the expression needs an explicit primitive/date conversion or a portable
choice-type conversion; do not add helper calls to fields already compared in
their native model type.

```cql
include FHIRHelpers version '4.0.1' called FHIRHelpers

// FHIR dateTime to CQL DateTime
FHIRHelpers.ToDateTime(E.period.start)

// FHIR choice value[x] to a logical FHIR Boolean
(A.value as FHIR.boolean).value
```

Use `Interval<Date>` for date-only rules and `Interval<DateTime>` for timestamp
rules. Document precision, timezone, open/closed boundaries, and the clock used
for age or other time-sensitive logic. Keep the FHIRHelpers source, ELM, and
FHIR Library canonical/version pinned through the normal import and package
flow.

## Keep unknown distinct from false

Decide the meaning of missing or incomplete evidence before writing a
conditional. Preserve `null` when the clinical result is unknown; return
`false` only when the source rule defines a negative result. A process measure
may separately define completion as false for a missing/incomplete response.
Do not let that completion rule coerce an unknown clinical risk result to
false.

Given separately defined Boolean expressions `"Has Required Evidence"` and
`"Evidence Is Positive"`, keep unknown distinct from negative:

```cql
define "Clinical Result":
  if not "Has Required Evidence" then null
  else "Evidence Is Positive"
```

## Readability and reuse (house-style)

Prefer descriptive retrieve/helper definitions for repeated terminology,
encounter, time, and provenance logic. Keep final definitions aligned with the
consuming PlanDefinition or Measure names, and test intermediate definitions
when they represent separate semantic decisions. These are readability
preferences, not requirements for one `define` per resource type or a ban on
retrieves in functions; use the structure that best expresses the rule and
validate it with the configured translator.

## Validation contract

Before claiming a library is ready:

1. Confirm the CQL context and the model path used by every terminology filter.
2. Pin the FHIR model, library includes, ValueSet canonical/version, and
   complete terminology expansions required by the runtime.
3. Run `rh-skills cql validate`, `rh-skills cql translate`, and fixture-based
   `rh-skills cql test` with the selected patient, evaluation date, full
   Measurement Period, and parameters supplied explicitly.
4. Include positive, negative, null/incomplete, wrong-code/system, and
   encounter/date/provenance cases appropriate to the decision. For runtime
   context validation, include another patient's resources in the Bundle and
   verify they do not change a Patient-context result.
5. If an engine fails Patient-context isolation or typed terminology behavior,
   record the engine/runtime blocker; do not add CQL workarounds that obscure
   the defect.

Validation is technical evidence. It does not constitute clinical approval.
