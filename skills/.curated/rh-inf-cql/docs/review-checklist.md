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
- [ ] Are external includes package-qualified (for example,
      `fhir.cqf.common.FHIRHelpers`) and resolved from a pinned package ID and
      version rather than a locally shadowed `FHIRHelpers`/`FHIRCommon`?
- [ ] Is external package CQL translated locally with the pinned translator,
      model, and options, with package-supplied ELM excluded from execution?
- [ ] Does dependency provenance record package/source checksums, translator
      identity/options/model, and the locally generated ELM checksum?
- [ ] Are translator options declared or otherwise reproducible?
- [ ] Is the packaging context clear (Library, Measure, PlanDefinition, etc.)?
- [ ] Does the FHIR Library satisfy [CQL IG Requirement 4.2](https://build.fhir.org/ig/HL7/cql-ig/en/conformance.html#conformance-requirement-4-2): exact CQL `name`/`version`, `<IG canonicalBase>/Library/<CQL name>` URL, `cql-namespace = IG.packageId`, `cql-namespaceUri = IG.canonicalBase`, no underscore, 64-character maximum, preferred 30-character maximum and versioned filename, and subject matching the single CQL context?

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
- [ ] Are helpers declared as `fluent function` invoked with dot syntax, such
      as `O.encounter.references(E)`, rather than as a namespace-style call
      such as `FHIRCommon.references(O.encounter, E)`?
- [ ] If `references` is used, does the selected package/version actually
      publish it? `fhir.cqf.common@4.0.1` does not; do not patch a local
      `FHIRCommon` to add it.
- [ ] If the runtime fails a selected-patient context-isolation case, is that
      reported as a runtime blocker instead of worked around in CQL?
- [ ] Are value sets and codes declared explicitly?
- [ ] Are terminology versions pinned where reproducibility matters?
- [ ] Is value set membership assumed too loosely anywhere?
- [ ] Are multi-code or cross-system result categories expressed as reviewed,
      versioned ValueSets rather than repeated direct-code `or` chains?
- [ ] Does the review include a complete categorical classifier inventory for
      every Boolean or enum decision over a FHIR `Coding` or
      `CodeableConcept`, including positive/negative categories whose reviewed
      ValueSet currently contains one code?
- [ ] Does each classified source element use exactly one named
      `FHIRHelpers.ToConcept()` helper, reused by named membership Booleans?
- [ ] Are direct declared-Code comparisons limited to documented exact
      single-concept predicates that are not functioning as categories?
- [ ] Does `if`/`else if`/`case` handle only cardinality, null, type, conflict,
      or three-valued semantics, with category branches using named membership
      Booleans rather than raw codes?
- [ ] For a FHIR `CodeableConcept` result, does logic use
      `FHIRHelpers.ToConcept()` before membership, keep category ValueSets
      mutually exclusive, and handle neither/both-match outcomes explicitly?

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
