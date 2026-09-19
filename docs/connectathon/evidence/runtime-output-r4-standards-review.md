# Runtime output R4 standards review

**Scope:** read-only review of the run-001 runtime output against FHIR R4 and
the exact official FHIR Validator 6.10.2 build used by the rehearsal. This
records one narrow validator limitation and the normative RequestGroup action
boundary. It is not a claim that the current runtime output is error-free.

## Individual proportion MeasureReport with denominator zero

### R4 rule and recommended output

The R4 MeasureReport definition gives `MeasureReport.group.measureScore` a
cardinality of **0..1**, with the definition “What score this group achieved.”
It does not make the score mandatory for a Measure whose scoring is
`proportion`.

- FHIR R4 MeasureReport: <https://hl7.org/fhir/R4/measurereport.html>
- FHIR R4 Data Absent Reason: <https://hl7.org/fhir/R4/extension-data-absent-reason.html>

For the normal individual case whose denominator population is zero, omit
`group.measureScore`. The report can remain `status: complete`, `type:
individual`, with its actual population counts. A score of `0` would assert a
calculated result that division by zero did not produce. The UI must instead
show **Not applicable — denominator is zero**, derived from the counts.

For a nonzero denominator, emit only the numeric ratio in
`group.measureScore.value`; do not add Quantity unit, system, or code for a
proportion score. Validator 6.10.2 explicitly prohibits those three Quantity
fields for a proportion score.

`data-absent-reason:not-applicable` is semantically appropriate when a score
has no proper value: the R4 extension applies to any Element and the
`not-applicable` code means that there is no proper value. It is useful
interoperability metadata, but it does not make the following validator branch
accept an extension-only Quantity.

### Exact 6.10.2 limitation

The official command-line validator logged in
`/private/tmp/connectathon-live/evidence/run001-runtime-fhir-validation.log`
reports `MEASURE_MR_SCORE_REQUIRED` for each of the six generated individual
proportion reports when `group.measureScore` is absent.

A focused, non-production probe added only this R4 extension to the zero
Denominator report:

```json
"measureScore": {
  "extension": [{
    "url": "http://hl7.org/fhir/StructureDefinition/data-absent-reason",
    "valueCode": "not-applicable"
  }]
}
```

Input: `/private/tmp/connectathon-live/evidence/measure-score-absence-probe/input/MeasureReport-group-score-dar.json`
(SHA-256 `732b5e23ea79da2b062b03f8fcbf2fe39e4014d8e8e94ec67423c2ca2c857726`).

The same 6.10.2 validator returns
`MEASURE_MR_SCORE_VALUE_REQUIRED` at `MeasureReport.group[0].measureScore`.
The result is at
`/private/tmp/connectathon-live/evidence/measure-score-absence-probe/operationoutcome-group-dar.json`.

The JAR's `MeasureValidator` bytecode confirms the behavior without relying on
an inference from the error text:

1. for scoring in `proportion`, `ratio`, or `continuous-variable`, it requires
   a non-null score element (`MEASURE_MR_SCORE_REQUIRED`);
2. for `proportion`, it reads only the score's `value` child (or the Da Vinci
   alternate-score-type extension), then requires that child
   (`MEASURE_MR_SCORE_VALUE_REQUIRED`);
3. that branch does not inspect denominator population counts or Data Absent
   Reason.

The inspected disassembly is
`/private/tmp/connectathon-live/evidence/measure-score-absence-probe/MeasureValidator-6.10.2.javap.txt`,
method instructions 108-412 in the score-validation branch. This is a narrow
validator limitation relative to core R4's 0..1 cardinality, not authority to
fabricate a zero score. Record the single resulting validator error for the
expected zero-denominator fixture as a known limitation; do not claim a clean
strict-validator pass for it.

## Non-executable guidance in RequestGroup

The actual `eligible-unsteady-yes` protocol result contains an
`interpret-phase` leaf at Bundle entry 4, RequestGroup
`b9f7b8b2-7272-4b19-bb8b-a5bf9599ceb7`, action 0. It has a title,
description, documentation, and applicability condition but neither
`resource` nor child `action`. That violates core R4 invariant `rqg-1`:
`resource.exists() != action.exists()`.

- FHIR R4 RequestGroup: <https://hl7.org/fhir/R4/requestgroup.html>
- FHIR R4 PlanDefinition: <https://hl7.org/fhir/R4/plandefinition.html>
- FHIR R4 GuidanceResponse: <https://hl7.org/fhir/R4/guidanceresponse.html>

Do not create a ServiceRequest, CommunicationRequest, Task, or a placeholder
child simply to satisfy `rqg-1`. A RequestGroup action resource is a target
request and the R4 comment requires it to have `intent: option`; a
PlanDefinition is not such a request. R4 `RequestGroup.note` is 0..* Annotation
and is the valid bounded representation for a non-executable guidance message.

The runtime should omit the invalid leaf action and add a root-level note with
plain text identifying it as non-executable guidance. The root RequestGroup's
existing `instantiatesCanonical` remains the traceable source link. The
Workbench should render the note as **Guidance (non-executable)**, not a
proposed action or order, and resolve the detailed condition/documentation from
the instantiated PlanDefinition in the complete package. `GuidanceResponse`
and output `Parameters` are unnecessary for this limited correction.

The root RequestGroup returned by applying a plan may remain `intent:
proposal`. A nested RequestGroup or Task referenced through a parent
`RequestGroup.action.resource` must use `intent: option`. Existing nested
outputs use `proposal` and need runtime correction. CommunicationRequest R4
has no `intent`; do not invent one or claim it meets that specific action
resource comment.
