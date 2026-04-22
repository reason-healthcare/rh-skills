# Review Checklist

Use this checklist for pull requests, library reviews, and agent-generated change proposals.

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

- [ ] Are retrieves scoped appropriately? (valueset or code filter at the retrieve)
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
