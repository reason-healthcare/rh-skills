# CQL Style Guide

Use this guide when authoring or reviewing FHIR CQL. Examples target FHIR R4
4.0.1; use the CQL version accepted by the configured translator (the current
`rh` authoring setup targets CQL 1.5.3) and pin/test that translator. The
published CQL 2.0.0 guide is cited for context and retrieve rules that also
apply here. FHIR model metadata defines which coded path a retrieve filter
uses. The rules below describe CQL semantics where stated; retrieve factoring
and helper layout are house-style preferences, not language restrictions.

For FHIR CQL, the CMS QMD Pattern Index is the first-choice
pattern source:

[https://build.fhir.org/ig/cqframework/cms-qmd/branches/main/pattern_index.html](https://build.fhir.org/ig/cqframework/cms-qmd/branches/main/pattern_index.html)

Before drafting logic, locate the closest clinical/data category and use the
corresponding CMS QMD pattern when available. Deviate only when the pattern is
not covered, the pinned FHIR/CQL version cannot express it, or the runtime
conformance requires an adaptation; preserve the CMS QMD pattern's intent,
and state the reason in the review or output.

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
include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers

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
pattern. It is not the `FHIRCommon` published in `fhir.cqf.common@4.0.1`, which
does not define `references`. Pin the package that actually publishes the
function, use its namespace in the include, and compile its CQL source locally:

```cql
library ScreeningReferenceJoin version '1.0.0'

using FHIR version '4.0.1'

include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers
include hl7.fhir.uv.cql.FHIRCommon version '2.0.0' called FHIRCommon

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

`references` is declared as a `fluent function`. Invoke it with dot syntax:
the receiver is the function's first argument and the values inside
`references(...)` supply the remaining arguments. Therefore
`O.encounter.references(E)` binds the published `(Reference, Resource)`
overload; `FHIRCommon.references(O.encounter, E)` does not. Including
`FHIRCommon` makes the fluent declaration available, but does not turn it into
a namespace-style function call. When the receiver is a cast or another
compound expression, parenthesize it:

```cql
// Correct
(First(O.focus) as FHIR.Reference).references(C)

// Wrong: a fluent function is not invoked through the library namespace
FHIRCommon.references(First(O.focus) as FHIR.Reference, C)
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
at canonical `http://hl7.org/fhir/uv/cql/Library/FHIRCommon|2.0.0` in package
namespace `hl7.fhir.uv.cql`. Do not create a local `FHIRCommon` that merges
functions from different releases. Resolve the exact package CQL source and
FHIR Library metadata from the immutable package/cache without copying it into
first-party computable content, ignore the package's generated ELM, and run the
project translator. Record package/source checksums, FHIR ModelInfo, translator
version and options, and the locally generated ELM checksum as one provenance
record.

For ordinary FHIR conversion helpers and common functions that are actually
present there, prefer `fhir.cqf.common@4.0.1` and qualify both includes:

```cql
include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers
include fhir.cqf.common.FHIRCommon version '4.0.1' called FHIRCommon
```

The namespace is the FHIR package ID. Do not accept package-supplied
`application/elm+json` or `application/elm+xml` as execution input; always
translate the packaged `text/cql` with the pinned project translator.

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

## Inventory and classify every coded category with reviewed ValueSets

Before authoring, inventory every Boolean or enum classifier whose input is a
FHIR `Coding` or `CodeableConcept`. Include every positive/negative,
normal/abnormal, detected/not-detected, stage, grade, status, interpretation,
and local category. A category is not exempt because its reviewed definition
currently contains only one code, and applying the ValueSet pattern to one
prominent classifier does not complete the inventory.
Treat this categorical classifier inventory as a required authoring artifact,
not an informal scan.

For each inventory row, record the FHIR source path, output category, reviewed
ValueSet canonical and version, terminology evidence, null/neither/both policy,
and the named conversion and membership definitions. For each classified
source element, define exactly one named helper that calls
`FHIRHelpers.ToConcept()`; all category memberships reuse that Concept. Keep
the mappings in reviewed, versioned ValueSets and do not repeat conversion or
direct-reference code comparisons in decision logic.

A direct declared `Code` comparison is allowed only when the expression is a
true exact single-concept predicate and is not functioning as a Boolean or enum
category. Document that distinction. A positive, negative, or other category
with one code remains a category and therefore still uses a ValueSet.

Control flow does not establish terminology meaning. Use `if`/`else if`/`case`
only for cardinality, null, wrong-type, conflict, or other three-valued
semantics. Category branches must reference named membership Booleans, never
raw codes. Convert a FHIR `CodeableConcept` result to a CQL `Concept` with the
pinned `FHIRHelpers.ToConcept()` function, then use ValueSet membership:

The example assumes `"Clinical T Result"` is a separately defined, single
selected `Observation`, not a list of Observations. Its selection logic still
owns the required observation code, status, date, encounter, and ambiguity
rules.

```cql
valueset "Clinical T1c Or Higher":
  'https://example.org/fhir/ValueSet/clinical-t1c-or-higher'
    version '1.0.0'

valueset "Clinical T Below T1c":
  'https://example.org/fhir/ValueSet/clinical-t-below-t1c'
    version '1.0.0'

define "Clinical T Concept":
  if "Clinical T Result" is null then null
  else FHIRHelpers.ToConcept(
    "Clinical T Result".value as FHIR.CodeableConcept
  )

define "Clinical T Is T1c Or Higher":
  "Clinical T Concept" in "Clinical T1c Or Higher"

define "Clinical T Is Below T1c":
  "Clinical T Concept" in "Clinical T Below T1c"

define "Has Clinical T1c Or Higher":
  if "Clinical T Concept" is null then null
  else if "Clinical T Is T1c Or Higher"
      and not "Clinical T Is Below T1c" then true
  else if "Clinical T Is Below T1c"
      and not "Clinical T Is T1c Or Higher" then false
  else null
```

`FHIRHelpers.ToConcept()` carries every `Coding` in the FHIR
`CodeableConcept` into the CQL `Concept`. Concept-in-ValueSet membership is
true when any code in that Concept is a member. This removes local-code versus
standard-code `or` branches while preserving each code's system identity.
If `Observation.value[x]` is not a FHIR `CodeableConcept`, the `as` expression
returns `null`, and `ToConcept(null)` remains `null`. The final definition's
Concept-null guard is therefore required to preserve wrong-type or absent
evidence as unknown; raw ValueSet membership on a null code argument is false.

The two classification ValueSets must use verified system/code identities and
must be reviewed as mutually exclusive. The conflict-safe form above returns
`null` when the value is in neither set or when a multi-coded concept matches
both sets; it does not silently make branch order clinically meaningful. A
shorter `if higher then true else if below then false` form is acceptable only
when both terminology membership and the input profile enforce that the two
matches cannot coexist.

Do not invent the contrasting ValueSet merely to obtain a Boolean result. Use
the two-ValueSet pattern only when the source-backed clinical contract defines
both categories. Missing, wrong-type, out-of-both, or unavailable terminology
is not evidence for the false category.

ValueSet membership does not infer numeric order, stage order, hierarchy, or
subsumption from a ValueSet name such as `Or Higher`. The ValueSet definition
must explicitly select every intended code through reviewed compose or
expansion semantics. Use actual canonical system and code values; labels such
as `LOINC cT1c` are not terminology identities. An unresolved or wrong-version
ValueSet is an execution error, not a clinical `null` result.

### Non-staging examples: one-code interpretations and cross-system categories

One-code positive and negative interpretation categories are reusable
terminology assets, not permission to branch on declared Codes. The following
illustrative ValueSets are assumed to have reviewed terminology L2 artifacts;
the example canonicals do not establish their content:

```cql
valueset "Positive Interpretation":
  'https://example.org/fhir/ValueSet/positive-interpretation'
    version '1.0.0'

valueset "Negative Interpretation":
  'https://example.org/fhir/ValueSet/negative-interpretation'
    version '1.0.0'

define "Selected Result Interpretation Concept":
  if "Selected Result" is null
      or Count("Selected Result".interpretation) != 1 then null
  else FHIRHelpers.ToConcept(First("Selected Result".interpretation))

define "Interpretation Is Positive":
  "Selected Result Interpretation Concept" in "Positive Interpretation"

define "Interpretation Is Negative":
  "Selected Result Interpretation Concept" in "Negative Interpretation"

define "Interpretation Category":
  if "Selected Result Interpretation Concept" is null then null
  else if "Interpretation Is Positive" and "Interpretation Is Negative" then null
  else if "Interpretation Is Positive" then 'positive'
  else if "Interpretation Is Negative" then 'negative'
  else null
```

The cardinality guard and final control flow preserve unknown/conflicting
semantics. The category branches use named membership Booleans; they do not
compare interpretation codes. This rule still applies when each ValueSet
contains exactly one code today.

A category whose accepted representations span systems also remains one
reviewed ValueSet. For example, a qualitative result contract may accept
reviewed representations from both a standard interpretation system and a
source-specific result CodeSystem:

```cql
valueset "Qualitative Result Detected":
  'https://example.org/fhir/ValueSet/qualitative-result-detected'
    version '2.1.0'

define "Qualitative Result Concept":
  if "Selected Result" is null then null
  else FHIRHelpers.ToConcept(
    "Selected Result".value as FHIR.CodeableConcept
  )

define "Qualitative Result Is Detected":
  "Qualitative Result Concept" in "Qualitative Result Detected"
```

The reviewed `Qualitative Result Detected` ValueSet, not the CQL branches,
owns that cross-system mapping. If the surrounding clinical output requires a
false or contrasting category, define and review its ValueSet too; do not turn
non-membership into clinical false.

## Convert FHIR values only when the type requires it

Keep FHIR model types explicit. Include the pinned FHIRHelpers dependency when
the expression needs an explicit primitive/date conversion or a portable
choice-type conversion; do not add helper calls to fields already compared in
their native model type.

```cql
include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers

// FHIR dateTime to CQL DateTime
FHIRHelpers.ToDateTime(E.period.start)

// FHIR choice value[x] to a logical FHIR Boolean
(A.value as FHIR.boolean).value
```

Use `Interval<Date>` for date-only rules and `Interval<DateTime>` for timestamp
rules. Document precision, timezone, open/closed boundaries, and the clock used
for age or other time-sensitive logic. Keep the package identity, FHIRHelpers
CQL source, FHIR Library canonical/version, translator provenance, and locally
generated ELM checksum pinned through the normal import and package flow; never
substitute package-supplied ELM.

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
