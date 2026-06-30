# CPG-Aligned Case Feature Resolution Readout

## Summary

Decision-table readouts should follow the CPG pattern:

```text
action/task -> produced data element(s) -> resolved case feature/condition -> rule or pathway gate
```

Tasks and actions produce data, not conditions. Conditions are the resolved case
features consumed by rule logic. The readout should show how each case feature is
resolved from supporting data elements without tying L2 to FHIR resource shapes.

CPG distinguishes two paths for resolving a case feature:

- **Assertion**: the feature is directly asserted in available patient data or
  documentation.
- **Inference**: the feature is calculated from other resolved data elements or
  clinical concepts.

The current L2 shape keeps a single `conditions[].resolution` field for now.
Use its `summary` and `inputs` to describe the relevant assertion/inference
logic in human-readable terms, but do not introduce separate
`assertionExpression`/`inferenceExpression` fields until the framework has a
first-class design for them.

## L2 Modeling

Use `conditions[]` for case features. A condition is not classified as observed
or inferred. Instead, its value is resolved from supporting `data_elements[]`.

Use `data_elements[].role` to describe how data supports feature resolution:

- `direct_evidence`
- `inference_input`
- `assessment_output`
- `context`
- `calculation_input`
- `derived_value`

Use `data_elements[].value_type` for neutral value shape:

- `presence`
- `quantity`
- `codeable_concept`
- `date_time`
- `interval`
- `ordinal`
- `text`

Use `data_elements[].produced_by[]` to reference action IDs that produce the data
element. Prefer this over `actions[].produces_conditions[]`; action output should
be modeled as produced data elements, and conditions should resolve from those
data elements.

Use `conditions[].resolution` when a case feature is resolved from multiple data
elements or requires interpretation:

```yaml
conditions:
  - id: advanced-sinus-disease-feature-present
    label: Advanced sinus disease feature present
    values: [Yes, No]
    resolution:
      operator: any_of
      inputs:
        - de-bony-erosion
        - de-osteitis
      summary: >
        Yes when any supporting advanced disease feature is documented in the
        current surgical evaluation context.
      unknown_policy: unknown_if_no_evaluable_evidence
```

## Readout Requirements

Render a `Case Feature Definitions` section before the rule matrix. The default
readout should mirror the CPG case-study decision-flow shape:

```text
data elements -> case feature definitions -> decisions -> interventions
```

Use one short block per case feature:

- case feature
- feature values
- brief description
- supporting data element names as a bullet list

Keep default readouts clinically readable and high level. Do not show
`data_elements[].role`, `data_elements[].value_type`, source, timing/scope,
produced-by actions, resolution operator, raw resolution inputs, or unknown
policy in the default report. Those fields are retained in L2 for validation,
downstream derivation, and future detailed rendering modes, but they add noise
for informaticist/clinical review unless the reader is specifically auditing
derivation mechanics.

Keep the rule matrix condition-based. Rules should consume resolved case
features, not task outputs or data elements directly.

## Example

```yaml
data_elements:
  - id: de-bony-erosion
    condition_id: advanced-sinus-disease-feature-present
    label: Bony erosion
    role: assessment_output
    data_type: imaging_finding
    value_type: presence
    produced_by:
      - review-sinus-ct
    evidence_source:
      - imaging
      - operative_note
    temporal_scope: current_surgical_evaluation

actions:
  - id: review-sinus-ct
    label: Review sinus CT
    kind: assessment
    produces_data_elements:
      - de-bony-erosion
```

The readout should present this as supporting data for the resolved case feature,
while the rules table gates on `advanced-sinus-disease-feature-present`.
