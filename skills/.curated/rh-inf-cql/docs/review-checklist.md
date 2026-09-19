# Review Checklist

Use this checklist for pull requests, library reviews, and agent-generated change proposals.
Read the [CQL Style Guide](cql-style-guide.md) for Patient-context and typed
terminology examples before reviewing those patterns. Before writing findings,
also check the
[CMS QMD Pattern Index](https://build.fhir.org/ig/cqframework/cms-qmd/branches/main/pattern_index.html)
and flag nonconforming logic when a listed pattern covers the clinical/data
category; allow only documented, tested runtime adaptations.

## Environment and Packaging

- [ ] Is the target CQL version clear?
- [ ] Is the target model and FHIR version declared and pinned?
- [ ] Are included libraries versioned?
- [ ] Are translator options declared or otherwise reproducible?
- [ ] Is the packaging context clear (Library, Measure, PlanDefinition, etc.)?

## Semantics

- [ ] Do definition names match behavior?
- [ ] Are date and interval boundaries intentional and explicit?
- [ ] Is null behavior explicit? (not left to propagation defaults)
- [ ] Are types consistent across operator usage?
- [ ] Are quantity comparisons safe? (explicit unit on both sides)
- [ ] Are helper definitions used where they increase clarity?

## Retrieves and Terminology

- [ ] Are retrieves scoped appropriately? Use a ValueSet/code filter when a
      coded concept defines selection; document and test intentional
      context/relationship retrieves.
- [ ] Do terminology comparisons use declared CodeSystem/Code or ValueSet with
      typed CQL operators instead of split system/code string checks?
- [ ] Does a retrieve filter target the intended model code path, especially
      when it is not the resource's `primaryCodePath`?
- [ ] When using `context Patient`, does CQL rely on context scoping instead of
      duplicating it with `subject.reference = Patient.id` predicates?
- [ ] Are independent date, encounter-linkage, and provenance constraints
      preserved when redundant patient-scope predicates are removed?
- [ ] If the runtime fails a selected-patient context-isolation case, is that
      reported as a runtime blocker instead of worked around in CQL?
- [ ] Are value sets and codes declared explicitly?
- [ ] Are terminology versions pinned where reproducibility matters?
- [ ] Is value set membership assumed too loosely anywhere?

## Testing

- [ ] Is there at least one positive case?
- [ ] Is there at least one negative case?
- [ ] Is there at least one null/missing-data case?
- [ ] Is there at least one threshold/boundary case?
- [ ] Is a regression test added for any bug fix?

## Runtime Fit

- [ ] Would the intended engine and CLI evaluate this correctly?
- [ ] Are engine-specific assumptions documented?
- [ ] Is the fixture shape compatible with the model and context?
