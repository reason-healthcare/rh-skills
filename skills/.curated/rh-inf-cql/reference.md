# Reference: rh-inf-cql Standards Corpus

This document lists the four layers of the CQL standards corpus that ground
`rh-inf-cql` authoring, review, debugging, and test-plan decisions.

---

## Layer 1 — Core CQL Language

The non-negotiable base set. Read these to understand syntax, semantics, typing,
null handling, intervals, dates, retrieves, and the canonical ELM representation.

| Source | URL | Version | When to use |
|--------|-----|---------|-------------|
| CQL Specification | https://cql.hl7.org/ | 1.5.3 (stable) | All CQL authoring and review |
| CQL Author's Guide | https://cql.hl7.org/02-authorsguide.html | 1.5.3 | Writing CQL expressions |
| CQL Developer's Guide | https://cql.hl7.org/03-developersguide.html | 1.5.3 | Compiler/tooling behavior |
| ELM Specification | https://cql.hl7.org/elm.html | 1.5.3 | Debugging translation issues, reviewing ELM output |
| CQL Grammar | https://cql.hl7.org/grammar.html | 1.5.3 | Syntax edge cases, parser behavior |

---

## Layer 2 — FHIR-Facing CQL

Required when CQL is used with FHIR data models, Library resources, or inside
Clinical Reasoning artifacts (Measure, PlanDefinition). Defines how CQL types
interact with FHIR types and how translator options are expressed.

| Source | URL | Version | When to use |
|--------|-----|---------|-------------|
| Using CQL with FHIR IG | https://hl7.org/fhir/uv/cql/ | current | Any CQL that uses FHIR data model |
| FHIR Clinical Reasoning Module | https://hl7.org/fhir/R4/clinicalreasoning-module.html | R4 | Understanding Library/Measure resource structure |
| FHIRHelpers | https://hl7.org/fhir/uv/cql/Library-FHIRHelpers.html | 4.0.1 | FHIR↔CQL type conversion library; pin CQL, ELM, and Library identity |
| FHIR ModelInfo | https://build.fhir.org/ig/HL7/cql-ig/ | current | Understanding model declarations and type resolution |
| CQL Translator Options | https://build.fhir.org/ig/HL7/cql-ig/using-elm.html | current | Declaring reproducible translator options in Library |
| CMS QMD Pattern Index | https://build.fhir.org/ig/cqframework/cms-qmd/branches/main/pattern_index.html | current | **Preferred first-choice FHIR CQL patterns** |

> **CMS QMD pattern precedence**: When authoring or revising FHIR CQL, first
> consult the CMS QMD Pattern Index and use a
> listed pattern when it covers the requested clinical/data category. Apply the
> pinned FHIR/CQL versions, terminology policy, FHIRHelpers conversions, and
> runtime tests from this repository. If a pattern is not portable as written,
> preserve its intent in the smallest tested adaptation and record the reason.
> Use the local Critical Authoring Patterns table only for cases the pattern
> index does not cover or for environment-specific behavior.

> **rh-inf-cql note**: The runtime does not automatically inject FHIRHelpers.
> When source includes a helper, import its pinned CQL/ELM/FHIR Library through
> `rh-skills cql import-library`; reference the helper canonical and version in
> the primary Library's `relatedArtifact`. For FHIR choices and primitives,
> use logical FHIR types and verify the same ELM with a reference translator.

---

## Layer 3 — Packaging and Lifecycle

Required when authoring CQL that will be packaged in FHIR artifacts, published
as computable/executable Libraries, or used in quality measure workflows.

| Source | URL | Version | When to use |
|--------|-----|---------|-------------|
| CRMI IG — Canonical Resource Management | https://build.fhir.org/ig/HL7/crmi-ig/ | current | Library computable vs executable packaging decisions |
| Quality Measure IG — Using CQL | https://build.fhir.org/ig/HL7/cqf-measures/using-cql.html | 5.0.0 | CQL in eCQM measures, data model declarations |
| Quality Measure IG — Conformance | https://build.fhir.org/ig/HL7/cqf-measures/conformance.html | 5.0.0 | Library metadata, dependency declarations |

---

## Layer 4 — Tooling and Runtime

Required for understanding compilation behavior, error messages, and test
execution patterns. The `rh` CLI (in-house Rust implementation) is the primary
toolchain for this project.

| Source | URL / Path | When to use |
|--------|-----------|-------------|
| rh-inf-cql Rust crate | `rh/crates/rh-inf-cql/README.md` | Understanding compiler behavior, ELM output differences from Java reference |
| rh-cli CQL commands | `rh/apps/rh-cli/src/cql.rs` | `rh cql validate/compile/eval/explain/repl` flags and output format |
| CQFramework clinical_quality_language | https://github.com/cqframework/clinical_quality_language | Java reference translator — compare behavior against rh-inf-cql when debugging |
| AHRQ CQL Testing Framework | https://github.com/AHRQ-CDS/CQL-Testing-Framework | Test case patterns and fixture format reference |

### rh cql command quick reference

```bash
rh cql validate <file.cql>                      # Validate; non-zero exit on errors
rh cql compile  <file.cql> --output <dir>       # Produce ELM JSON
rh cql eval     <file.cql> <name> \
                            --data <bundle.json> # Evaluate one expression
rh cql eval     ... --trace                     # With step-by-step trace
rh cql explain  parse   <file.cql>              # Parse tree
rh cql explain  compile <file.cql>              # Semantic analysis details
rh cql repl                                     # Interactive REPL
```
