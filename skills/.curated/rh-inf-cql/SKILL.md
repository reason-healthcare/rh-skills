---
name: "rh-inf-cql"
description: "First-class CQL (Clinical Quality Language) authoring, review, debugging, and test-plan skill for the rh-skills informatics workflow."
compatibility: "Requires rh-skills project with topics/<topic>/computable/ structure and `rh` CLI on PATH"
applyTo: "**/*.cql, **/*.xml, **/Library-*.json, **/Measure-*.json, **/PlanDefinition-*.json, **/ActivityDefinition-*.json, **/tests/cql/**/*.json, **/tests/cql/**/*.yaml, **/skills/.curated/rh-inf-cql/**"
metadata:
  author: "rh-skills"
  version: "1.1.0"
---

## User Input

```text
$ARGUMENTS
```

Read the user input and determine the operating mode (`author`, `review`, `debug`,
or `test-plan`). If no mode is stated, infer from context:
- Structured artifact YAML provided → `author`
- Existing `.cql` file + "review" / "check" / "audit" → `review`
- Error message or failing test provided → `debug`
- "test plan" / "fixtures" / "cases" requested → `test-plan`

If mode is still ambiguous, ask the user to confirm before proceeding.

**CONFLICTS**: Any decision that could produce incorrect or ambiguous output MUST
be confirmed by the human before proceeding. Do not resolve conflicts silently.

---

## Pre-Execution Checks

Before producing any output:

1. Confirm the `rh` CLI binary is reachable (via `RH_CLI_PATH`, `.rh-skills.toml [cql] rh_cli_path`, or `rh` on PATH). If absent, halt and show `cargo install rh` hint.
2. Confirm the topic directory `topics/<topic>/` exists. If it does not, halt and prompt the user to run `rh-skills init <topic>` or correct the topic name.
3. For **author** mode: confirm the structured artifact YAML exists at `topics/<topic>/structured/<artifact>.yaml`.
4. For **review**/**debug**/**test-plan** modes: confirm the `.cql` source file exists at `topics/<topic>/computable/<LibraryName>.cql`.
5. For any CQL expression involving **intervals, date/time, null semantics, or operators whose behavior is uncertain**: **first check the Critical Authoring Patterns table** (search this file for `## Critical Authoring Patterns`). Only call `reasonhub-search_spec_content` (source: `cql`) if the specific pattern is not already covered there.

**Author mode — prohibited diagnostic commands**: Do **not** run `ls`, `git status`, `git diff`, or `rg --files` as part of the authoring workflow. The directory structure is confirmed by steps 1–4 above. Any exec call not in the author workflow steps below is wasted work.

If any check fails, report the missing resource and halt. Do NOT proceed with a partial context.

---

## Guiding Principles

- **Deterministic work via CLI**: validation (`rh-skills cql validate`), compilation (`rh-skills cql translate`), and test execution (`rh-skills cql test`) are always delegated to the `rh-skills` CLI. The agent reasons about CQL but does not replace the CLI for deterministic operations.
- **Ownership boundary**: `rh-inf-cql` owns `.cql` source files and fixture cases. FHIR JSON packaging is outside scope.
- **Human confirmation for conflicts**: any ambiguity, inconsistency, or multi-option decision MUST be surfaced to the human before the agent proceeds. Silent resolution is not permitted.
- **Portable FHIR CQL**: declare `using FHIR version '4.0.1'`, include the versioned `FHIRHelpers` library for FHIR primitive/choice conversions, and use FHIR logical-model types that translate in both `rh` and the reference translator. Do not claim interoperability from one engine alone.

---

## Tool Boundaries

> **NEVER read the `rh` Rust source or the `rh-skills` Python source.**

`rh` and `rh-skills` are black-box CLIs. The agent must not read, search, or
inspect their implementation source files under any circumstances — not to
understand behavior, not to debug errors, not to confirm flag syntax.

Prohibited actions (hard stop — do not proceed):
- Reading any file under `~/projects/rh/` (Rust crates, `apps/rh-cli/src/`, etc.)
- Reading any file under the `rh-skills` install path (Python `.py` source)
- Using `find`, `rg`, `grep`, or `cat` against `*.rs` files
- Using `python -c "import rh_skills; ..."` to locate and then read the source

Allowed alternatives:
- `rh cql --help` / `rh cql eval --help` for flag reference
- `rh-skills cql --help` for wrapper command reference  
- Docs in `.agents/skills/rh-inf-cql/` for runtime behavior
- If behavior is unclear after reading help and skill docs: **ask the user**

---

## Critical Authoring Patterns (read before writing any CQL)

**Runtime defaults** (assume these unless the user specifies otherwise):
- CQL version: `1.5.3` | FHIR model: `4.0.1` | Record non-default translator options and validate against a reference translator when portability matters.
- Engine: `rh`; fixtures run through `rh-skills cql test` / `rh cql eval`. Include pinned libraries explicitly and pass the complete evaluation context.

Parameter-only decision-table libraries are scaffold artifacts and are not acceptable finished authoring outputs.

**Anti-patterns that cause silent failures or runtime errors:**

| ❌ Wrong | ✓ Correct | Why |
|----------|-----------|-----|
| `M.authoredOn during Interval<DateTime>` | `FHIRHelpers.ToDateTime(M.authoredOn) during Interval<DateTime>` | Convert the FHIR primitive explicitly using the pinned helper |
| `date from M.authoredOn` | `FHIRHelpers.ToDateTime(M.authoredOn)` | Convert the FHIR primitive explicitly; use a matching interval type |
| `ToDateTime(E.period.start)` | `FHIRHelpers.ToDateTime(E.period.start)` | FHIR primitive conversion must use the declared helper |
| `A.valueBoolean = true` | `(A.value as FHIR.boolean).value = true` | QuestionnaireResponse answer is a choice; use its FHIR logical type for portable translation |
| `V.expansion.contains E where E.code = 'X'` | `C.code in "ValueSetName"` | Use typed membership; separately supply the complete pinned expansion through the runtime's terminology input or packaged knowledge Bundle |
| `[Encounter: "Ambulatory"]` | `[Encounter: class ~ "Ambulatory"]` | The FHIR R4 Encounter retrieve's primary code path is `type`; name the non-primary `class` path explicitly |
| `C.clinicalStatus.value = 'active'` | `exists (C.clinicalStatus.coding S where S ~ "Active")` | Compare the typed Coding with a declared Code and CodeSystem; do not split terminology identity into string predicates |
| `define function "F"(p Interval<DateTime>): ... p ...` | `define "F": Interval[ToDate(start of ...), ToDate(end of ...)]` | Typed function parameters with complex types (`Interval<>`, `FHIR.*`) fail to resolve in the `rh` translator; use named `define` expressions instead |
| `[Condition] C where C.recordedDate is not null` | `[Condition: "BellsPalsyValueSet"] C` when the coded concept defines selection | Broad retrieves can include unrelated resources. A terminology filter is appropriate when code membership defines the concept; a narrow context/relationship retrieve may be intentional if its scope is explicit and tested |
| `[Condition] C where exists(C.code.coding S where S ~ "BellsPalsy")` | `[Condition: "BellsPalsyValueSet"] C` | Prefer a complete, reviewed ValueSet when the clinical concept includes synonyms or multiple codes; for one named code, declare its CodeSystem and use a typed terminology comparison |

Before writing CQL, read the required [CQL Style Guide](docs/cql-style-guide.md).
Other secondary docs (`authoring-guidelines.md`, `engine-notes/README.md`,
`translator-options/README.md`, `cli/usage.md`, and similar files) are
on-demand: consult them when a specific runtime or workflow question arises.
The critical authoring patterns and anti-pattern catalog below still apply.

---

## Purpose

This skill turns the agent into a disciplined reviewer and test-oriented author
for CQL artifacts. Use it for:

- writing or revising CQL libraries from structured clinical artifacts
- reviewing CQL for correctness and maintainability
- debugging translation or runtime failures
- generating test scenarios and minimal fixture bundles
- validating behavior using the `rh` CLI evaluator
- checking alignment with FHIR Clinical Reasoning packaging conventions

The skill should prefer deterministic reasoning over stylistic improvisation.
For detailed conventions, see:
- `skills/.curated/rh-inf-cql/docs/authoring-guidelines.md`
- `skills/.curated/rh-inf-cql/docs/review-checklist.md`
- `skills/.curated/rh-inf-cql/docs/testing-strategy.md`
- `skills/.curated/rh-inf-cql/docs/terminology-policy.md`
- `skills/.curated/rh-inf-cql/docs/runtime-assumptions.md`

---

## What the Agent Should Optimize For

- **Semantic correctness** — logic that evaluates correctly across the full case space
- **Reproducible execution** — pinned versions, explicit options, no silent defaults
- **Clarity of intent** — names match behavior; structure makes logic reviewable
- **Explicit assumptions** — model, terminology, runtime all stated
- **Compact but sufficient tests** — four minimum cases per define (positive, negative, null, boundary)
- **Minimal safe changes** — prefer the smallest edit that solves the problem
- **Consistency with local conventions** — follow `docs/authoring-guidelines.md`

Do **not** optimize for: cleverness, compressing logic into dense one-liners, or
vague positive review language such as "looks good."

---

## Required Context to Gather First

Before making any recommendation, gather as much of the following as available.
State clearly which items are missing and the likely impact of each gap.

- Target CQL version (default: 1.5.3)
- Target FHIR version (default: 4.0.1)
- Model declaration and model version
- Included libraries and their versions
- Translator options (defaults: signatureLevel none, enableAnnotations false — see `context/runtime/translator-options/README.md` only if non-default options are in use)
- Terminology dependencies and version pins
- Runtime engine and evaluator details (default: `rh` engine — see `context/runtime/engine-notes/README.md` only if a non-default engine is in use)
- Expected input data shape (patient bundle structure)
- Expected output expressions or artifact behavior
- Packaging context: Library, Measure, PlanDefinition, or ActivityDefinition

---

## Standard Operating Sequence

For any non-trivial request, follow this order. Do **not** skip to code edits
unless the user explicitly asks for a narrow syntax-only change.

1. **Identify the effective execution environment** — model, FHIR version, translator options, runtime engine.
2. **Summarize library intent** — purpose, key defines, major dependencies.
3. **Inspect dependencies, terminology, and model assumptions** — flag missing or unpinned items.
4. **Consult CQL specification when syntax or semantics are uncertain** — use `reasonhub-search_spec_content` (source: `cql`) before writing any expression whose behavior is ambiguous. Prefer spec evidence over recall.
5. **Review semantics and maintainability** — apply the authoring rubric and review checklist.
6. **Inspect translation behavior or ELM if relevant** — run `rh-skills cql validate` and `rh-skills cql translate`.
7. **Run or reason about test scenarios** — run `rh-skills cql test` against existing fixtures; identify gaps.
8. **Propose minimal changes** — prefer one-line fixes over restructuring.
9. **Define regression tests** — specify the new or updated cases required.

---

## Primary Tasks

### Task 1 — Summarize a Library

For a given CQL library:

- identify the purpose of the library
- list important expressions and their dependencies
- summarize retrieves, terminology, and helper usage
- identify runtime assumptions (model, engine, translator options)
- explain expected outputs and result types
- call out unclear or risky assumptions

Output format: use the structured template from `prompts/summarize-library.md`.

---

### Task 2 — Review a Library

When reviewing CQL, check all items in the Review Checklist below. For each
deficiency, produce a finding classified as `BLOCKING`, `ADVISORY`, or `INFO`
with:
- the specific area from the checklist or high-risk pattern catalog
- a quoted CQL excerpt as evidence
- a concrete recommended fix

Output format: use the report template from `prompts/review-library.md`.

---

### Task 3 — Debug Failures

When a translation or runtime error occurs:

- isolate whether the issue is syntax, translation, model mismatch, terminology,
  fixture shape, packaging, or engine behavior (use the Failure Categories section)
- reduce to the smallest failing expression or data condition
- explain the probable root cause in plain language
- propose the smallest safe fix
- recommend a regression test to add
- note whether the failure is deterministic or environment-dependent

Output format: use the template from `prompts/explain-failure.md` and then
`prompts/propose-minimal-fix.md`.

---

### Task 4 — Generate Tests

For each important definition, generate at minimum:

| Case type | What it proves |
|-----------|----------------|
| Positive | Nominal true / expected-result path |
| Negative | Nominal false / contrasting result |
| Null / missing-data | Absent resource, missing date, incomplete evidence |
| Boundary | Just below / exactly at / just above a threshold |
| Conflicting evidence | Multiple facts that might cause ambiguity |
| Terminology | In-valueset / out-of-valueset / version-drift behavior |
| Multi-event | Earliest, latest, first, or any-match semantics |

Prefer compact fixture sets that isolate one semantic point at a time.
Output format: use `prompts/generate-test-scenarios.md`.

---

### Task 5 — Review Packaging and Surrounding Artifacts

When CQL is embedded or referenced from FHIR artifacts:

- confirm the intended expression context (Library, Measure, PlanDefinition, etc.)
- identify whether the content is computable, executable, publishable, or shareable
- verify references to Library resources and their version declarations
- verify parameter and data expectations
- confirm terminology and model assumptions are compatible with the surrounding artifact
- flag any packaging that obscures executable dependencies

---

## Review Checklist

Apply every time unless the user asks for something narrower. See
`docs/review-checklist.md` for the full structured rubric.

### Environment and Packaging
- [ ] Is the target CQL version clear?
- [ ] Is the target model and FHIR version declared and pinned?
- [ ] Are included libraries versioned?
- [ ] Are translator options declared or otherwise reproducible?
- [ ] Is packaging context clear (Library, Measure, PlanDefinition, etc.)?

### Semantics
- [ ] Do definition names match behavior?
- [ ] Are date and interval boundaries intentional and explicit?
- [ ] Is null behavior explicit? (not left to propagation defaults)
- [ ] Are types consistent across operator usage?
- [ ] Are quantity comparisons safe? (explicit unit on both sides)
- [ ] Are helper definitions used where they increase clarity?

### Retrieves and Terminology
- [ ] Are retrieves scoped appropriately? Use a ValueSet/code filter when a coded concept defines the selection; document and test intentional context or relationship retrieves.
- [ ] Are value sets and codes declared explicitly?
- [ ] Is each declared ValueSet used by the evaluated resource path, or is its non-use justified (for example, QR linkIds before SDC extraction)?
- [ ] Are terminology versions pinned where reproducibility matters?
- [ ] Is value set membership assumed too loosely anywhere?
- [ ] If SDC extraction is required, are CQL and tests using produced Observations rather than only a normalized expected Bundle?

### Testing
- [ ] Is there at least one positive case?
- [ ] Is there at least one negative case?
- [ ] Is there at least one null/missing-data case?
- [ ] Is there at least one threshold/boundary case?
- [ ] Is a regression test added for any bug fix?

### Runtime Fit
- [ ] Would the intended engine and CLI evaluate this correctly?
- [ ] Are engine-specific assumptions documented?
- [ ] Is the fixture shape compatible with the model and context?

---

## Testing Workflow

When the `rh` CLI is available, use this loop:

1. Translate the CQL to ELM: `rh-skills cql translate <topic> <library>`
2. Capture translator warnings and errors.
3. Run evaluator against focused fixture bundles: `rh-skills cql test <topic> <library>`
4. Record outputs for key expressions, not only final population results.
5. Compare actual vs expected outputs (the test command does this automatically).
6. Classify failures using the Failure Categories below.
7. Recommend the minimal code or fixture change.
8. Add or update regression test cases at `tests/cql/<LibraryName>/`.

If per-expression output is needed for debugging, run the evaluator directly:
```bash
rh cql eval topics/<topic>/computable/<LibraryName>.cql "<DefineName>" \
  --data tests/cql/<LibraryName>/<case>/input/bundle.json
```

See `context/runtime/cli/usage.md` for full CLI reference.

---

## Failure Categories

Use these categories when classifying issues in reviews or debug reports:

| Category | Description | Fix domain |
|----------|-------------|------------|
| `syntax` | Parse error, invalid token, grammar violation | Authoring |
| `translation` | ELM generation failure, type inference error | Authoring |
| `type-mismatch` | Operator applied to incompatible types | Authoring |
| `null-propagation` | Unexpected null from missing optional element | Authoring |
| `interval-boundary` | Inclusive/exclusive boundary produces wrong result | Authoring |
| `temporal-precision` | Date/time comparison with mismatched precision | Authoring |
| `terminology-resolution` | Code not in valueset, wrong system URL | Authoring |
| `retrieve-scope` | Retrieve too broad; filtered too late downstream | Authoring |
| `unit-conversion` | Quantity comparison without unit normalization | Authoring |
| `version-drift` | Library, model, or valueset version changed | Authoring |
| `fixture-or-data-shape` | Input bundle does not match model expectations | Fixture |
| `packaging` | Library resource references, compiler options mismatch | Packaging |
| `model-mismatch` | Wrong FHIR version, QI-Core vs base FHIR | Environment |
| `engine-behavior` | Evaluator-specific handling of edge cases | Environment |
| `missing-binary` | `rh` not on PATH or `RH_CLI_PATH` unset | Environment |

---

## Output Format

For all non-trivial responses, prefer this structure:

### Context
State the effective environment and assumptions (model, FHIR version, translator
options, runtime, terminology versions). Be explicit about what is missing.

### Findings
List the most important correctness or maintainability findings first. Classify
each as `BLOCKING`, `ADVISORY`, or `INFO`.

### Proposed Changes
Suggest the smallest changes that address each finding. Show before/after for
any CQL edit. Explain the **semantic** impact, not just textual change.

### Test Scenarios
List the new or updated test cases required. Include case name, case type,
expected outcome, and what semantic point the case isolates.

### Remaining Uncertainty
State explicitly what cannot be confirmed from current context — missing runtime
details, unknown terminology expansions, unverified fixture assumptions.

---

## Mode: author

**Goal**: Produce a valid, well-formed CQL library from L2 structured artifacts.

### Inputs
- L2 structured artifact YAML from `topics/<topic>/structured/<artifact>.yaml`
- The topic name and library name (infer from artifact if not stated)
- Optionally: existing CQL libraries to include (pinned versions required)

### Workflow

1. **Read the structured artifact** — extract:
   - Measure/concept name → becomes the `library` identifier
   - FHIR R4 model version
   - Valuesets (name, OID/URL, version) — all must be pinned
   - Logic statements → map to CQL `define` names
   - Population criteria (if measure) → Initial Population, Denominator, Numerator
   - Condition rows (if decision-table) → one `define` per condition (PascalCase, no spaces)

   **Valueset sourcing rule**: Every valueset referenced in the CQL library must
   be backed by a `ValueSet` FHIR resource in `topics/<topic>/computable/`.
   The terminology L2 artifacts (`topics/<topic>/structured/*.yaml` with
   `artifact_type: terminology`) are the authoritative control files that drive
   this — each one formalizes into a `ValueSet-<id>.json` via
   `rh-skills formalize <topic> <terminology-artifact>`.

   **Valuesets must be built before the CQL phase.** The required concepts are
   known at extract time from the terminology L2 artifacts — do not wait until
   CQL authoring to discover missing valuesets.

   Before authoring CQL:
   1. List the topic's terminology L2 artifacts: check `structured/` for any
      `artifact_type: terminology` files.
   2. Confirm each required valueset has already been formalized into
      `computable/ValueSet-<id>.json`. If not, run
      `rh-skills formalize <topic> <terminology-artifact>` first.
   3. When building a valueset, **always use ReasonHub MCP tools**
      (`reasonhub-search_snomed`, `reasonhub-search_icd10`, `reasonhub-search_rxnorm`,
      `reasonhub-search_loinc`) to find semantically similar codes across systems.
      Real-world data uses multiple coding systems and synonymous codes — a
      valueset with only one code will produce false negatives in production.
   4. If a concept needed in CQL has no corresponding terminology L2 artifact,
      that is a gap at the extract stage — raise it rather than inventing a
      ValueSet resource directly.

   > 🔖 **Future**: Revisit reusability — well-known public valuesets (e.g., from
   > VSAC, HL7, or FHIR community IGs) should eventually be referenced by their
   > canonical URL rather than duplicated locally. For now, local-first via the
   > terminology L2 pipeline is the required path.

   **Choose the terminology boundary that matches the input resource.** In
   FHIR R4, a `QuestionnaireResponse.item` carries `linkId` and answers; it does
   not carry the Questionnaire item's LOINC `Coding`. If logic evaluates a
   response before extraction, bind the exact versioned Questionnaire canonical
   and expected `linkId` values. Do not invent a ValueSet lookup against a QR
   answer. When the workflow requires SDC extraction, retain the source
   Questionnaire's SDC extraction profile and metadata, evaluate the generated
   `Observation` resources, and scope each retrieve with its terminology L2
   ValueSet, for example `[Observation: "UnsteadinessQuestion"]`. In that
   path, verify each Observation's code, system, version, subject, encounter,
   status, `derivedFrom` response, and provenance before treating the CQL result
   as an extraction result. A normalized extracted fixture is an oracle; it
   does not prove that `$extract` produced those Observations.

   Fixture-driven native runs may supply a pre-expanded ValueSet or Bundle of
   ValueSets at `tests/cql/<Library>/case-*/input/terminology.json`. The CQL
   test runner forwards this file to `rh cql eval --terminology`; include only
   complete, versioned expansions for declared canonical dependencies. Test
   positive membership, wrong code, wrong system, and unresolved or wrong
   ValueSet canonical version. Do not expect `Coding.version` or display text
   alone to change standard CQL code membership; assert those fields separately
   when they are part of the extraction contract.

2. **Read the [CQL Style Guide](docs/cql-style-guide.md)** and apply the
   **authoring rubric** (see Authoring Rubric below) before writing or reviewing
   code. The guide is the source of truth for Patient-context retrieval,
   terminology operators, FHIR primitive handling, and provenance joins.

3. **Draft the CQL library** using the template for the artifact type:

   **Measure** (`artifact_type: measure`):

   ```cql
   /**
    * Library: <LibraryName>
    * Version: 1.0.0
    * Description: <one-line description from artifact>
    * Author: rh-inf-cql (generated from structured artifact)
    * Date: <today>
    */
   library <LibraryName> version '1.0.0'

   using FHIR version '4.0.1'

   include FHIRHelpers version '4.0.1' called FHIRHelpers

   codesystem "<SystemName>": '<system-url>'

   valueset "<ValuesetName>": '<valueset-url>'  // version '<pinned-version>'

   parameter "Measurement Period" Interval<DateTime>
     default Interval[@2024-01-01, @2024-12-31]

   context Patient

   define "Initial Population":
     <expression>

   define "Denominator":
     "Initial Population"

   define "Numerator":
     <expression>
   ```

   **Decision table** (`artifact_type: decision-table`):

   One `define` per condition row from `sections.conditions`. The define name is the
   condition `label` converted to PascalCase (e.g., `"Facial weakness present"` →
   `"FacialWeaknessPresent"`). The PlanDefinition stub generated by `rh-skills formalize`
   references these exact names in its `action[].condition[].expression` fields.

   **Do not use Boolean placeholder parameters as stand-ins for unresolved clinical
   evidence.** Parameters such as `parameter "QualityOfLifeBurdenDocumented" Boolean default false`
   are acceptable only for true runtime inputs like `"Measurement Period"` or an
   externally supplied execution flag. They are not acceptable substitutes for
   patient findings, observations, diagnoses, procedures, questionnaire scores,
   or therapy history drawn from the guideline.

   Instead:
   - create retrieve-level helper defines for the clinical evidence itself
   - scope retrieves with the appropriate valueset at the retrieve
   - add explicit status filters where best practice requires them
   - model thresholds as named expressions or comments/TODOs on the retrieve-based
     define, not as Boolean input parameters

   For example:
   - use `[Condition: "ChronicRhinosinusitis"] C` with active-status logic, not
     `parameter "HasCrsDiagnosis" Boolean`
   - use `[Observation: "QualityOfLife"] O` plus score threshold TODOs, not
     `parameter "QualityOfLifeBurdenDocumented" Boolean`
   - use retrieves or derived history expressions for prior-therapy evidence, not
     `parameter "PriorTherapyInsufficient" Boolean`

   ```cql
   /**
    * Library: <LibraryName>
    * Version: 1.0.0
    * Description: <one-line description from artifact>
    * Author: rh-inf-cql (generated from structured artifact)
    * Date: <today>
    */
   library <LibraryName> version '1.0.0'

   using FHIR version '4.0.1'

   include FHIRHelpers version '4.0.1' called FHIRHelpers

   codesystem "<SystemName>": '<system-url>'

   valueset "<ValuesetName>": '<valueset-url>'  // version '<pinned-version>'

   context Patient

   // One define per condition row — names must match PlanDefinition action expressions
   define "<ConditionOneLabelPascalCase>":
     /* TODO: implement condition logic */

   define "<ConditionTwoLabelPascalCase>":
     /* TODO: implement condition logic */
   ```

4. **Check the library against the authoring rubric** (all 10 areas) — see
   Authoring Rubric section.

5. **Validate** by calling the deterministic CLI command:
   ```
   rh-skills cql validate <topic> <LibraryName>
   ```
   Do not declare the library complete until `rh-skills cql validate` exits 0.
   If it exits non-zero, read the error output and fix issues before retrying.

   **Validate failure protocol:**
   - **Attempt 1 fails** — read errors, apply a targeted fix, retry.
   - **Attempt 2 fails** — use `rh-skills cql translate` as a proxy to confirm
     the CQL is structurally sound (translate succeeds ⇒ logic is likely correct,
     validate error may be a tool bug). Record the discrepancy and proceed with
     the translate result. Do **not** make further speculative edits.
   - **After 2 failed attempts** — report the error verbatim to the user and ask
     for guidance. Do **not** iterate further without explicit direction.
   - **Do not use web search** to diagnose CQL errors. Consult the local context
     corpus (`skills/.curated/rh-inf-cql/context/`) or ReasonHub MCP spec tools
     (`reasonhub-search_spec_content` with `source_id: "cql"`).

   **Pinned FHIRHelpers dependency:**
   When a CQL library includes FHIRHelpers, provide a local manifest that pins
   the helper's source URL/tag/license, CQL and ELM hashes, canonical, version,
   and translator options. Import it with
   `rh-skills cql import-library <topic> <manifest.json>`. The command copies
   the exact helper CQL, ELM, and FHIR Library into computable/, links each
   including Library through `relatedArtifact[type=depends-on]`, and records
   an external dependency in tracking. No runtime network lookup is assumed.

   The manifest pins identity and local, relative inputs:

   ```json
   {
     "resource": {
       "id": "fhir-helpers-4-0-1",
       "name": "FHIRHelpers",
       "version": "4.0.1",
       "url": "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers"
     },
     "source": {
       "url": "https://example.invalid/pinned-source",
       "tag": "vX.Y.Z",
       "license": "Apache-2.0",
       "compile_tool": {
         "name": "cql-to-elm-cli",
         "version": "X.Y.Z",
         "options": [],
         "inputs": []
       }
     },
     "cql": { "path": "FHIRHelpers-4.0.1.cql", "sha256": "<64 lowercase hex characters>" },
     "elm": { "path": "FHIRHelpers-4.0.1.json", "sha256": "<64 lowercase hex characters>" }
   }
   ```

   Replace every example value with verified metadata and digests. The
   importer rejects hash, identity, version, or path mismatches and never
   downloads dependencies.

6. The `.cql` file is now ready. FHIR packaging (Library JSON wrapper, Measure
   JSON) is outside `rh-inf-cql`'s scope — hand off to whatever packaging step
   is appropriate for the context.

### Output contract
- `.cql` file at `topics/<topic>/computable/<LibraryName>.cql`
- Passes `rh-skills cql validate` with zero errors, with explicit versioned
  includes present locally
- Follows all style guide and rubric requirements

---

## Mode: review

**Goal**: Produce a structured Markdown review report classifying findings as
`BLOCKING`, `ADVISORY`, or `INFO`.

### Inputs
- Path to an existing `.cql` file
- Optionally: context about the intended use (measure, CDS rule, etc.)

### Workflow

1. Read the CQL source fully before writing any finding.
2. Apply the **authoring rubric** (10 areas) — flag deficiencies.
3. Apply the **high-risk pattern catalog** (7 categories) — flag matches.
4. Apply the **packaging rubric** (4 concerns) — flag issues.
5. Write the review report.

### Report format

```markdown
# CQL Review Report: <LibraryName>
**Reviewed**: <date>
**File**: `topics/<topic>/computable/<LibraryName>.cql`
**Reviewer**: rh-inf-cql (automated review)

## Summary
- BLOCKING: N
- ADVISORY: N
- INFO: N

## Findings

### BLOCKING: <Finding Category>
**Area**: <rubric area or high-risk pattern>
**Evidence**:
```cql
<quoted excerpt>
```
**Issue**: <description>
**Recommended fix**: <concrete fix>

### ADVISORY: ...
### INFO: ...

## Rubric Coverage
| Area | Status | Notes |
|------|--------|-------|
| Model declaration and version | ✓ PASS / ✗ FAIL | ... |
| ... (all 10 areas) |

## High-Risk Pattern Scan
| Pattern | Status | Notes |
|---------|--------|-------|
| Unpinned terminology | ✓ PASS / ✗ FOUND | ... |
| ... (all 7 patterns) |

## Packaging
| Concern | Status | Notes |
|---------|--------|-------|
| CQL source present | ✓ / ✗ | ... |
| ... |
```

### Output contract
- Review report at `topics/<topic>/process/reviews/<LibraryName>-review.md`
- All 10 rubric areas covered (no category omitted)
- All 7 high-risk patterns scanned
- Accepted by `rh-skills verify` as review evidence

---

## Mode: debug

**Goal**: Identify the root cause of a CQL error and propose a minimal corrective
change.

### Inputs (provide at least one)
- A `.cql` file path
- Translator error from `rh-skills cql validate`
- Failing fixture: `case-NNN/input/bundle.json` + `expected/expression-results.json`
  \+ actual output from `rh cql eval`
- Runtime error description

### Workflow

1. **Classify the error type** using the taxonomy below.
2. **Locate the responsible `define`** — trace from the error message or failing
   expression back to the source statement.
3. **Propose the minimal corrective change** — prefer one-line fixes over
   restructuring.

### Error taxonomy

| Category | Description | Fix domain |
|----------|-------------|------------|
| Temporal precision | Date/time comparison with mismatched precision | Authoring |
| Null propagation | Unexpected null from missing optional element | Authoring |
| Terminology mismatch | Code not in valueset, wrong system URL | Authoring |
| Retrieve scope | Too broad a retrieve, filtered after the fact | Authoring |
| Unit conversion | Quantity comparison without normalization | Authoring |
| Version drift | Library or valueset version changed | Authoring |
| Context misuse | `Patient` context used where wrong | Authoring |
| Missing binary | `rh` not on PATH or CQL_TRANSLATOR_PATH unset | Environment |
| Model mismatch | Wrong FHIR version, QI-Core vs base FHIR | Environment |
| Translator option mismatch | Options differ between compile and evaluate | Environment |

### Diagnosis report format

```markdown
# CQL Debug Report: <LibraryName>
**Error input**: <translator / test / runtime>

## Root Cause
**Category**: <from taxonomy>
**Responsible define**: `<define-name>` at line N
**Evidence**: <error message or diff>

## Explanation
<one paragraph>

## Minimal Corrective Change
```cql
// Replace the current expression with:
<replacement expression>
```

## Distinguishing authoring vs environment
<if authoring: fix by editing .cql>
<if environment: fix by correcting tooling setup / config>
```

---

## Mode: test-plan

**Goal**: Enumerate all `define` statements and produce a test plan Markdown plus
structurally valid fixture skeletons.

### Inputs
- Path to an existing `.cql` file
- Topic and library name

### Workflow

1. Parse all non-context `define` statements from the CQL source.
2. For each `define`, determine applicable test families from the matrix below.
3. Write the test plan Markdown.
4. Write fixture skeleton files for each case.

### Test family matrix

| Dimension | Case variants |
|-----------|--------------|
| Age | below threshold / at threshold / above threshold |
| Timing | before boundary / on boundary / after boundary |
| Terminology | code matches valueset / code not in valueset / code absent |
| Value | value present / value absent / value null |
| Events | single event / multiple events / conflicting events |

**Minimum cases per define**: 4×N rule — for N `define` statements, generate at
minimum 4N fixture cases: one positive, one negative, one null/absent, one boundary.

### Fixture directory structure

```
tests/cql/<LibraryName>/
├── case-001-<description>/
│   ├── input/
│   │   ├── patient.json        # FHIR R4 Patient resource
│   │   ├── bundle.json         # FHIR R4 Bundle (transaction or collection)
│   │   └── parameters.json     # (optional) FHIR Parameters for overrides
│   ├── expected/
│   │   └── expression-results.json   # { "<define>": <value>, ... }
│   └── notes.md                # What this case proves, placeholder explanations
├── case-002-<description>/
│   └── ...
```

`expression-results.json` format:
```json
{
  "Initial Population": true,
  "Denominator": true,
  "Numerator": false,
  "Patient Age": 45
}
```

### Test plan Markdown format

```markdown
# Test Plan: <LibraryName>

## Define Inventory
| Define | Purpose | Test families |
|--------|---------|--------------|
| <name> | <intent> | age, timing, terminology |
| ...    |          |              |

## Case Summary
| Case | Define(s) | Family | Expected outcome |
|------|-----------|--------|-----------------|
| case-001-... | ... | positive | IsAdult = true |
| ...           |     |          |                |

## Fixture Notes
<any special data requirements>
```

### Output contract
- Test plan at `topics/<topic>/process/test-plans/<LibraryName>-test-plan.md`
- Fixture directories at `tests/cql/<LibraryName>/case-NNN-<description>/`
- Every fixture has structurally valid JSON (not empty files)
- All `notes.md` files explain placeholder values

---

## Anti-Patterns to Flag

The following patterns indicate high risk regardless of mode. Flag them with the
category and classification shown. See `docs/authoring-guidelines.md` for
guidance on preferred alternatives.

| Pattern | Category | Classification |
|---------|----------|----------------|
| Unpinned valueset or code system version | `terminology-resolution` | BLOCKING |
| Hidden timezone or precision assumption (`Today()`, `Now()` without explicit context) | `temporal-precision` | ADVISORY |
| Quantity comparison without unit normalization on both sides | `unit-conversion` | BLOCKING |
| Broad retrieve without explained clinical scope | `retrieve-scope` | HOUSE POLICY: BLOCKING unless documented exception |
| Code/ValueSet filter that defines the concept is applied only downstream | `retrieve-scope` | ADVISORY |
| Duplicate logic instead of a named helper definition | Style | ADVISORY |
| Ambiguous null handling — assuming null is false without explicit `is null` check | `null-propagation` | ADVISORY |
| Dependence on implicit engine behavior not documented in `context/runtime/` | `engine-behavior` | ADVISORY |
| Mixed FHIR version assumptions in included libraries | `model-mismatch` | BLOCKING |
| Library version not declared or declared as `0.0.0` | `version-drift` | ADVISORY |
| ELM not re-generated after CQL change | `packaging` | ADVISORY |

---

## Working Style

- Always state your assumptions explicitly before producing any output.
- When multiple approaches are viable, present the top two with their tradeoffs
  and ask the user to choose. Never silently pick one.
- When a finding is ambiguous, classify it conservatively (BLOCKING if unsure).
- Prefer table and structured formats over paragraphs for findings.
- For proposed code changes, show the minimal replacement needed to correct the issue.
- Do not rewrite libraries wholesale unless explicitly asked. Prefer targeted edits.
- When the `rh` CLI is available, run it before claiming a library is correct.
- Do not claim "this looks good" without completing the full Review Checklist.
- If the required context is missing (model, runtime, terminology), state that
  explicitly before proceeding, rather than assuming defaults.
- Always propose a regression test for any bug fix. Do not close a debug session
  without identifying the minimum fixture that reproduces the issue.

---

## Authoring Rubric (10 Areas)

Check every authored library against all 10 areas. Flag deficiencies in the
review report.

| # | Area | What to check |
|---|------|--------------|
| 1 | Model declaration and version | `using FHIR version '4.0.1'` present and pinned |
| 2 | Included libraries and versions | All `include` statements have explicit version strings |
| 3 | Terminology declarations and version pinning | All `valueset` and `codesystem` declarations have pinned versions or OIDs |
| 4 | Top-level documentation and intent | Library has a doc comment block with name, version, description, date |
| 5 | Separation of retrieval logic from derived logic | Retrieve (`[Condition]`, `[Observation]`, etc.) kept in dedicated `define`; derivations reference those defines |
| 6 | Reuse of helper functions | Repeated logic extracted into named helpers; no copy-paste expressions |
| 7 | Null/empty semantics | Null propagation is explicit; lists checked with `exists` before access |
| 8 | Interval boundary behavior | Interval operators (`during`, `starts`, `ends`, `overlaps`) include correct boundary (open/closed) |
| 9 | Date/time precision assumptions | Date truncation (`ToDate()`, `date from`) is explicit; no silent precision coercion |
| 10 | Output shape and expected result types | Each `define` has a clear expected type (Boolean, List, Interval, etc.) documented in a comment |

---

## High-Risk Pattern Catalog

Flag each pattern as BLOCKING (must fix before use) or ADVISORY (should fix).

| # | Pattern | Classification | What to look for |
|---|---------|---------------|-----------------|
| 1 | Unpinned terminology | BLOCKING | `valueset "X": 'urn:oid:...'` without version pinning where reproducibility matters |
| 2 | Hidden timezone/precision assumptions | ADVISORY | `Today()` or `Now()` without explicit context clock; date arithmetic without `ToDate()` |
| 3 | Quantity comparison without unit normalization | BLOCKING | `obs.value > 5 'mg'` where source unit may differ |
| 4 | Broad retrieve without an explained clinical scope | HOUSE POLICY: BLOCKING unless documented exception | Prefer a retrieve-level ValueSet/code filter when terminology defines the selection. A context or relationship retrieve may be appropriate without one when its intended scope and joins are explicit and tested. |
| 5 | Duplicate logic instead of helper definitions | ADVISORY | Same expression repeated in 3+ defines without extraction |
| 6 | Ambiguous null handling | BLOCKING | `if X then Y` without `else null` where null branch matters; comparing null to a value without `~` |
| 7 | Dependence on implicit engine behavior | ADVISORY | Logic that relies on FHIRHelpers auto-injection, implicit conversions, or unspecified operator overloads |

---

## CQL Style Guide

Read the [CQL Style Guide](docs/cql-style-guide.md) before authoring or
reviewing CQL. The key constraints are repeated below because violations can
change patient scope or coded clinical meaning.

### Library naming and versioning
- Library identifiers use PascalCase: `LipidManagementLogic`, `PHQ9AssessmentLogic`
- Version follows semantic versioning: `version '1.0.0'`
- Match the library filename: `LipidManagementLogic.cql` → `library LipidManagementLogic`

### Terminology declaration rules
- Always pin valueset versions in production libraries
- Prefer canonical VSAC/FHIR URLs over raw OIDs for new libraries
- One `codesystem` declaration per system; reuse across the library
- Every valueset declared in the library **must have a local `ValueSet` resource**
  in `topics/<topic>/computable/ValueSet-<id>.json` — verify it exists before
  finalizing the library. See the valueset sourcing rule in the author workflow.

### Retrieve patterns
- Prefer named retrieve definitions when they clarify or reuse resource filters;
  name them for the resource and meaningful filter.
- Prefer keeping status filters with their retrieve when that makes the result
  easier to review.
- Keep a retrieve in a helper function only when the function improves reuse
  and the configured translator supports it.
- With `context Patient`, rely on Patient context to scope each retrieve when
  the pinned FHIR ModelInfo declares the relevant context relationship and the
  engine honors it; do not
  repeat it with `subject.reference = Patient.id`. If the runtime leaks another
  patient's resource, block that engine path rather than adding a CQL workaround.
- Declare a `valueset`, `codesystem`, or `code` and use typed terminology
  operators (`in`, `~`, or exact `=`). Do not decompose a `Coding` or
  `CodeableConcept` comparison into separate system/code string checks.
- Name non-primary coded paths in the retrieve filter. FHIR R4 Encounter's
  primary code path is `type`; `class` is a separate `Coding`, so
  `[Encounter: "Ambulatory"]` does not filter `class`.
- Preserve independent status, date, encounter-linkage, and `derivedFrom`
  provenance conditions. Patient context does not replace these joins.
- For an Observation-to-Encounter reference join, prefer the pinned
  `FHIRCommon.references()` fluent function when its same-source-server,
  resource-id semantics match the input contract. Include and package the
  versioned Library/ELM dependency; do not replace the relationship with a
  manually assembled reference string.
- Explicit patient-reference checks may be valid in `context Unfiltered` or a
  deliberate cross-patient query; state that context and purpose. See the
  [CQL context guidance](https://cql.hl7.org/02-authorsguide.html#context) and
  [retrieve scoping](https://cql.hl7.org/02-authorsguide.html#retrieve-context).

### Null and interval conventions
- Use `~` (equivalent) for concept comparisons, `=` for exact equality
- Use `exists ( ... )` before accessing list elements
- Prefer `Interval[start, end]` with explicit closed brackets over implicit

### Date/time precision rules
- Use `ToDate()` when comparing dates; use `ToDateTime()` for datetime comparisons
- Never rely on implicit precision coercion between `Date` and `DateTime`
- Use `FixedClock` / `"Measurement Period"` parameter for deterministic evaluation

### When to split into included libraries
- Extract reusable helpers (age, encounter, status) into a separate shared library
- A library over 200 lines with repeated patterns should be refactored

### Anti-pattern catalog
- ❌ `[Observation] O where O.status = 'final'` (literal string; use code)
- ❌ Nested function calls beyond 3 levels deep without intermediate defines
- ❌ `if X is not null then X else default` — prefer `Coalesce(X, default)`
- ❌ `First([Condition])` without an ordering expression
- ❌ Comparing dates with `=` instead of `same day as` or interval operators
- ❌ Compare FHIR primitive date/time fields directly to CQL system values — convert with the pinned FHIRHelpers function matching the field and interval type
- ❌ Reconstruct a CodeableConcept/Coding terminology comparison with separate system/code string predicates — declare the CodeSystem and Code and compare with `~`, or use a reviewed ValueSet
- ❌ Manual ValueSet expansion matching (`V.expansion.contains E where E.system = ... and E.code = ...`) — use `code in "ValueSetName"` instead
- ❌ Match only a code or display while ignoring its coding system — use a verified ValueSet for a concept set, or a declared CodeSystem/Code with a typed terminology operator for one named code
- ❌ `define function "F"(p Interval<DateTime>): ...` — typed function parameters with `Interval<>` or `FHIR.*` types fail to compile; use a named `define` expression with inline logic instead

---

## CLI Commands (Deterministic Boundary)

Use the CLI for deterministic validation, compilation, test execution, and
pinned external-library import. Do not manually edit generated ELM or FHIR
Library resources.

| Action | Command | Status |
|--------|---------|--------|
| Validate CQL syntax and semantics | `rh-skills cql validate <topic> <library>` | ✓ active (`rh cql validate`) |
| Compile CQL to ELM JSON | `rh-skills cql translate <topic> <library>` | ✓ active (`rh cql compile`) |
| Run fixture-based test cases | `rh-skills cql test <topic> <library>` | ✓ active (`rh cql eval` per expected expression) |
| Import pinned external CQL/ELM/FHIR Library | `rh-skills cql import-library <topic> <manifest.json>` | ✓ verifies hashes and identity; updates tracking |

`rh-skills cql test` discovers fixture cases under `tests/cql/<Library>/case-*/`,
passes the topic `computable/` directory as the include path, forwards each
fixture's subject, evaluation date, measurement period, and parameters, then
compares actual vs expected values and exits non-zero if any assertion fails.

---

## MCP Tools

### Terminology lookup

| Tool | When to use |
|------|------------|
| `reasonhub-search_loinc` | Look up LOINC codes for observation concepts in the library |
| `reasonhub-search_snomed` | Look up SNOMED codes for condition/procedure concepts |
| `reasonhub-search_rxnorm` | Look up RxNorm codes for medication concepts |
| `reasonhub-codesystem_lookup` | Get UCUM units for a LOINC code; verify code display name |
| `reasonhub-search_valuesets` | Find existing ValueSets to reference |

### CQL and FHIR specification lookup

Use these tools **before** writing any expression whose syntax, semantics, or
operator behavior is uncertain. Do not rely on recall alone for CQL grammar or
FHIR Clinical Reasoning rules.

| Tool | When to use |
|------|------------|
| `reasonhub-search_spec_content` with `source_id: "cql"` | Interval semantics, null propagation, operator precedence, date/time arithmetic, retrieve syntax, query clauses (`where`, `let`, `return`, `sort`), type coercion rules |
| `reasonhub-search_spec_content` with `source_id: "fhir-r4"` | FHIR resource field definitions, data type semantics, search parameter behavior |
| `reasonhub-search_spec_content` with `source_id: "fhirpath"` | FHIRPath expression semantics when used in Library criteria |
| `reasonhub-list_spec_sources` | Discover available spec source IDs and versions |
| `reasonhub-get_spec_context` | Retrieve a specific section by heading (e.g., `source_id: "cql"`, `heading: "Interval"`) |

**Trigger conditions — call `reasonhub-search_spec_content` when the pattern is NOT already covered in the Critical Authoring Patterns table above, and when:**
- Writing or reviewing an interval expression (`overlaps`, `during`, `before`, `after`, closed/open boundaries)
- Writing date/time arithmetic (`+ N days`, `start of`, `end of`, precision qualifiers)
- Reasoning about null propagation through boolean expressions
- Unsure whether an operator accepts List vs singleton operands
- Verifying the semantics of `exists`, `in`, `contains`, `~`, `!~`, or `is`
- Reviewing a `where` clause on a retrieve — especially multi-property conditions
- Writing a `define` that uses `if`/`then`/`else` with possible null branches
- Any question about CQL 1.5.x vs 2.0 differences

---

## Human-in-the-Loop Rules

- **All conflicts must be confirmed by the human** before resolution. Never silently
  resolve ambiguity in clinical logic.
- If two valuesets could satisfy a concept, present both and ask the user to choose.
- If the rubric reveals a BLOCKING issue, halt and report — do not auto-fix.
- If `rh-skills cql validate` fails after two correction attempts, use
  `rh-skills cql translate` as a proxy (see Validate failure protocol above),
  then report the discrepancy and ask the user for guidance. Do **not** attempt
  further speculative fixes or copy unverified helper files into the topic.
- Before writing more than one fixture case with placeholder data, confirm the
  fixture schema is acceptable.

---

## File Read/Write Table

| Operation | Path | Command |
|-----------|------|---------|
| Read structured artifact | `topics/<topic>/structured/<artifact>.yaml` | direct read |
| Write CQL source | `topics/<topic>/computable/<Library>.cql` | direct write |
| Write ELM JSON | `topics/<topic>/computable/<Library>.json` | via `rh-skills cql translate` |
| Write review report | `topics/<topic>/process/reviews/<Library>-review.md` | direct write |
| Write test plan | `topics/<topic>/process/test-plans/<Library>-test-plan.md` | direct write |
| Write fixture cases | `tests/cql/<LibraryName>/case-NNN-<desc>/` | direct write |

---

## Ownership boundary

`rh-inf-cql` owns **CQL content** — the `.cql` source text, its logical
correctness, and its fixture cases. FHIR JSON packaging (Library wrapper,
Measure, PlanDefinition) is outside scope and must not be written by this skill.
