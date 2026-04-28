# Feature Specification: CQL Eval Scenarios — Full Measure Pipeline

**Feature Branch**: `013-cql-eval-scenarios`  
**Created**: 2025-07-17  
**Status**: Draft  

## Overview

Add four eval scenario YAML files that together cover the complete clinical quality measure authoring pipeline — ingest → extract → formalize — with a focus on CQL library authoring. The scenarios use a shared `lipid-management` topic (ACC/AHA cholesterol and NCQA HEDIS statin-therapy source material) and are ordered so that each stage's workspace fixtures are exactly what the prior stage produces.

The goal is to expose gaps in agent behavior that existing scenarios (diabetes CCM, PHQ-9) do not test: specifically, the two new formalize scenarios exercise CQL `define` statement authoring, FHIR data requirements with valueset references resolved via the ReasonHub MCP, correct population-criteria naming conventions, and the correct linking of Library → Measure → PlanDefinition.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ingest a Quality Measure Guideline Source (Priority: P1)

A developer adding coverage for a new clinical quality measure topic needs an ingest scenario that starts from a validated discovery plan and exercises the full download → normalize → classify → annotate cycle for lipid-management source material. This scenario is the entry point of the pipeline and must exist for the downstream scenarios (US-2 through US-4) to have realistic workspace fixtures.

**Why this priority**: All three downstream scenarios depend on the normalized source content established here. Without a credible, self-contained ingest fixture for `lipid-management`, the extract and formalize scenarios cannot represent realistic workspace state.

**Independent Test**: The scenario file at `eval/scenarios/rh-inf-ingest/quality-measure-source.yaml` can be run independently with `scripts/eval-skill.sh --scenario quality-measure-source` against the `rh-inf-ingest` skill. Success is measured by the presence of the normalized source file and a valid `concepts.yaml`.

**Acceptance Scenarios**:

1. **Given** a discovery plan exists for `lipid-management` with one open-access source (ACC/AHA cholesterol guideline), **When** the agent runs the ingest cycle (plan → implement → verify), **Then** `sources/normalized/acc-aha-cholesterol-2023.md` exists, `concepts.yaml` contains measure-relevant concepts (LDL-C, statin, ASCVD risk), and `tracking.yaml` records an `ingest_complete` event.
2. **Given** the scenario YAML is loaded, **When** a reviewer inspects the quality_focus items, **Then** each item refers to a concrete, checkable property of the produced artifacts (not vague goals like "good quality").
3. **Given** the scenario YAML is loaded, **When** a reviewer inspects the efficiency_focus items, **Then** each item identifies a specific redundant action the agent must avoid (e.g., reading the discovery plan more than once, using manual Markdown conversion instead of `rh-skills ingest normalize`).

---

### User Story 2 — Extract Quality Measure Logic from Ingested Source (Priority: P1)

A developer needs an extract scenario that starts with `ingest_complete` workspace state for `lipid-management` and exercises measure-specific L2 artifact extraction: initial population, denominator, numerator eligibility criteria, and a denominator exclusion. This scenario must verify that the agent proposes the correct artifact types (`measure-logic`, `decision-table`, or `evidence-summary`) for quality measure source material — not generic care-pathway or policy types.

**Why this priority**: The extract stage produces the L2 artifacts that the CQL authoring formalize scenarios depend on. If the extract scenario is missing or produces artifacts without proper population criteria structure, the formalize CQL scenarios cannot be meaningfully tested.

**Independent Test**: The scenario file at `eval/scenarios/rh-inf-extract/measure-logic-extraction.yaml` can be run independently — the workspace already contains a fully ingested normalized source. The agent only needs to plan and implement the extraction.

**Acceptance Scenarios**:

1. **Given** the `lipid-management` topic is in `ingest_complete` state with a normalized ACC/AHA source, **When** the agent runs extract (plan → approve → implement → verify), **Then** at least one L2 artifact with `artifact_type: measure` or `artifact_type: decision-table` is produced, containing `populations.initial_population`, `populations.denominator`, and `populations.numerator` sections.
2. **Given** the extract plan is produced, **When** the reviewer checks it, **Then** the plan explicitly lists eligibility criteria (age range, diagnosis code domain, encounter requirements) and numerator criterion (statin prescription in measurement period).
3. **Given** the implemented artifact, **When** `rh-skills validate` is run, **Then** zero errors are reported.

---

### User Story 3 — Formalize CQL Library for Population Criteria (Priority: P1)

A developer needs a formalize scenario that starts with `extract_complete` state for `lipid-management` and exercises CQL Library authoring in depth. The scenario must verify that the agent: (a) authors CQL `define` statements for each population criterion, (b) references valueset URIs resolved via the ReasonHub MCP rather than constructing them inline, (c) uses correct `context Patient` declaration and date-interval arithmetic, and (d) wraps the CQL in a FHIR `Library` resource linked to a stub `Measure`.

**Why this priority**: CQL Library authoring is the highest-value, hardest-to-test behavior in the formalize stage. No existing scenario exercises CQL correctness at this level of detail. This scenario is the primary deliverable of the feature request.

**Independent Test**: The scenario file at `eval/scenarios/rh-inf-formalize/cql-library-authoring.yaml` can be run independently — the workspace provides fully structured L2 measure artifacts. The quality_focus items are specific enough to be evaluated by inspecting the generated CQL content.

**Acceptance Scenarios**:

1. **Given** approved L2 population-criteria artifacts for `lipid-management`, **When** the agent runs formalize (plan → approve → implement → verify), **Then** a CQL file is produced that contains `context Patient`, at least three `define` statements (InitialPopulation, Denominator, Numerator), and at least one `valueset` declaration.
2. **Given** the produced CQL, **When** efficiency_focus items are checked, **Then** the agent did not re-query the ReasonHub MCP for valuesets already declared in the L2 artifact, and did not read the normalized source file during the formalize phase.
3. **Given** the produced FHIR Library resource, **When** its content is inspected, **Then** it contains a `content` attachment with `contentType: text/cql`, and a `dataRequirement` section listing at least one FHIR resource type (e.g., `Condition`, `MedicationRequest`).
4. **Given** the produced CQL, **When** quality_focus CQL-correctness items are checked, **Then** date arithmetic uses `Interval` or `during` correctly (no hard-coded year strings), and population `define` statements reference each other correctly (Denominator filters InitialPopulation).

---

### User Story 4 — Formalize Complete Measure Bundle (Priority: P2)

A developer needs an end-to-end formalize scenario that starts with `extract_complete` state for `lipid-management` (multiple L2 artifacts including a measure and a decision-table) and produces a complete, linked FHIR measure bundle: `Library` (containing CQL), `Measure` resource, and `PlanDefinition` all cross-linked by canonical URL. This scenario tests that the agent correctly links resources together — not just that each resource is individually valid.

**Why this priority**: While US-3 checks CQL authoring in isolation, this scenario verifies the integration: the Measure's `library[]` references the Library URL, and the PlanDefinition's `action[].definition` references the Measure. This is a critical correctness property that requires a separate, broader scenario.

**Independent Test**: The scenario file at `eval/scenarios/rh-inf-formalize/measure-bundle-complete.yaml` can be run independently with richer L2 workspace fixtures. It tests a superset of what US-3 tests, so it can run without US-3 having been executed.

**Acceptance Scenarios**:

1. **Given** approved L2 artifacts (measure + decision-table) for `lipid-management`, **When** the agent runs formalize, **Then** `Measure-lipid-statin-therapy.json`, `Library-lipid-statin-therapy.json`, and `PlanDefinition-lipid-statin-therapy.json` are all produced in `topics/lipid-management/computable/`.
2. **Given** the three produced FHIR JSON files, **When** cross-linking is checked, **Then** the Measure's `library[]` array contains the canonical URL of the Library, and the PlanDefinition's `action[0].definitionCanonical` contains the canonical URL of the Measure.
3. **Given** all three resources, **When** `rh-skills verify` is run, **Then** zero structural errors and zero cross-link errors are reported.
4. **Given** the scenario's efficiency_focus items, **When** the agent transcript is reviewed, **Then** the agent did not separately derive valueset references that were already present in the L2 artifacts' `value_sets[]` sections.

---

### Edge Cases

- **Scenario file references a non-existent skill directory**: The `rh-inf-formalize` skill directory already exists; if a scenario uses a skill slug that doesn't map to an existing directory under `eval/scenarios/`, the eval harness must surface a clear error rather than silently creating a new directory.
- **Workspace fixture YAML contains inline CQL with special characters**: The scenario YAML must correctly quote or block-scalar CQL strings that contain `"`, `|`, and `>` characters so the YAML parser does not misinterpret them.
- **Multiple L2 artifacts for the same topic**: The measure-bundle-complete scenario has two L2 artifacts (measure + decision-table). The agent must formalize both into the same computable output directory without overwriting the Library produced for one artifact with a different Library for the other.
- **Valueset URLs not yet resolved in L2 artifacts**: The CQL-library-authoring scenario should include at least one `value_sets[]` entry with a placeholder URL to verify the agent consults the ReasonHub MCP to resolve it — rather than propagating the placeholder into the CQL verbatim.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each scenario file MUST conform to the eval scenario schema defined in `eval/scenarios/README.md` — fields `name`, `skill`, `description`, `topic`, `workspace`, `prompt`, `expected_outputs`, `efficiency_focus`, and `quality_focus` are all present and non-empty.

- **FR-002**: The four scenario files MUST be placed in the correct skill subdirectories:
  - `eval/scenarios/rh-inf-ingest/quality-measure-source.yaml`
  - `eval/scenarios/rh-inf-extract/measure-logic-extraction.yaml`
  - `eval/scenarios/rh-inf-formalize/cql-library-authoring.yaml`
  - `eval/scenarios/rh-inf-formalize/measure-bundle-complete.yaml`

- **FR-003**: All four scenarios MUST use the topic slug `lipid-management` and share a logically consistent normalized source file (`acc-aha-cholesterol-2023.md`) whose inline content covers: LDL-C thresholds for statin initiation, age eligibility (40–75), denominator exclusions (pregnancy, active liver disease, ESRD), and a numerator criterion (statin prescription during measurement period).

- **FR-004**: Workspace fixtures MUST be self-contained — each scenario MUST include all required workspace files inline (no `fixture:` file references) so the scenario can be run without external file dependencies.

- **FR-005**: The `expected_outputs` section of each scenario MUST include at least one `contains:` check that is specific to the clinical content (e.g., `contains: "LDL-C"` or `contains: "statin"`), not just structural checks like `exists`.

- **FR-006**: The `efficiency_focus` items in the two formalize scenarios (cql-library-authoring and measure-bundle-complete) MUST include at least one item explicitly targeting CQL-specific anti-patterns: re-querying the ReasonHub MCP for valuesets that were already resolved in the L2 artifact, or re-reading the normalized source file during the formalize phase.

- **FR-007**: The `quality_focus` items in the two formalize scenarios MUST include at least three CQL correctness checks covering: (a) presence of `context Patient` declaration, (b) correct use of date-interval arithmetic (no hard-coded year strings), and (c) correct population define-statement chaining (Denominator references InitialPopulation, Numerator references Denominator or applies an additional filter).

- **FR-008**: The measure-bundle-complete scenario's `expected_outputs` MUST include cross-linking checks verifying that the `Measure` JSON references the `Library` URL, and the `PlanDefinition` JSON references the `Measure` URL — using `contains:` checks on the canonical URL strings.

- **FR-009**: The `tracking_yaml` in each scenario's workspace MUST accurately reflect the lifecycle state that the skill under test expects to start from:
  - ingest scenario: topic state `discovery_planned`, no `ingest_complete` event
  - extract scenario: topic state `ingest_complete`, sources listed as normalized
  - formalize scenarios: topic state `extract_complete`, structured artifacts listed as approved

- **FR-010**: The `prompt` field in each scenario MUST follow the existing prompt convention: state the skill and topic, list what is present in the workspace, and enumerate the sub-commands (plan → approve → implement → verify) the agent should execute.

### Key Entities

- **Scenario File**: A YAML document at `eval/scenarios/<skill>/<name>.yaml` that fully specifies a single eval run — workspace state, opening prompt, expected outputs, and evaluation guidance. One scenario per file; name must match the YAML `name` field.

- **Workspace Fixture**: Inline file content embedded in the scenario's `workspace.files[]` list. Fixtures represent the deterministic starting state of the temp workspace. The `lipid-management` topic will use a shared normalized source document (`acc-aha-cholesterol-2023.md`) whose content appears in the extract and formalize scenarios' fixtures.

- **CQL Library Artifact**: The primary output of the two formalize scenarios. Consists of: (1) a `.cql` text file with `context Patient`, `valueset` declarations, and population `define` statements; (2) a FHIR `Library` JSON resource with `content[].contentType: "text/cql"`, `dataRequirement[]`, and `relatedArtifact[]` cross-references.

- **Measure Bundle**: The complete output of the measure-bundle-complete scenario. Consists of three linked FHIR resources: `Library` (CQL), `Measure` (with `group[].population[]` and `library[]`), and `PlanDefinition` (with `action[].definitionCanonical` pointing to the Measure).

- **Lipid Management Topic**: The shared clinical subject for all four scenarios. Source material is drawn from the ACC/AHA Guideline on Blood Cholesterol Management (2023 Update) — already present as `acc-aha-lipid-2023.md` in the `cvd-risk-management` extract scenario — adapted here as `acc-aha-cholesterol-2023.md` under the `lipid-management` topic slug.

- **Quality/Efficiency Focus Items**: String-valued evaluation prompts embedded in the scenario YAML. Quality items are checked against artifact content. Efficiency items are checked against the agent's action transcript. Both are distinct from `expected_outputs` checks (which are machine-verifiable) — focus items are intended for human reviewers or an LLM judge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four scenario YAML files are present at their specified paths and parse without YAML errors (zero parse failures when loaded by the eval harness).

- **SC-002**: Each scenario YAML passes schema validation against the eval scenario schema (all required fields present, all `checks:` values use known check types: `exists`, `contains`, `contains_any_file_with`, `event`).

- **SC-003**: The inline workspace fixture content for `acc-aha-cholesterol-2023.md` contains at least 8 distinct clinical facts used across `expected_outputs` checks in scenarios 2, 3, and 4 — ensuring the fixture is realistic enough to drive meaningful evaluation.

- **SC-004**: The two formalize scenarios together contain at least 6 CQL-specific quality_focus items (3 per scenario) covering the three correctness dimensions defined in FR-007, so that a single-pass LLM judge can evaluate CQL correctness without ambiguity.

- **SC-005**: The cross-pipeline dependency is traceable: the workspace `tracking_yaml` and `files[]` in the extract scenario match the expected output structure of the ingest scenario, and the formalize scenarios' workspace fixtures match the expected output structure of the extract scenario.

- **SC-006**: All efficiency_focus items are specific and falsifiable — each item names a concrete agent action that can be observed in a tool-use transcript (e.g., "calls `reasonhub-search_loinc` more than once for the same concept") rather than vague performance goals (e.g., "efficient").

## Scenario Content Specification

This section defines the required content for each scenario file in enough detail for an implementer to write the YAML without ambiguity.

### Scenario 1 — `quality-measure-source.yaml` (rh-inf-ingest)

**Clinical topic**: `lipid-management`

**Starting state**: `discovery_planned` — a discovery plan is present, no sources yet ingested.

**Discovery plan source entry**:
```yaml
- id: acc-aha-cholesterol-2023
  title: "ACC/AHA Guideline on Blood Cholesterol Management (2023 Update)"
  url: https://www.ahajournals.org/doi/10.1161/CIR.0000000000001166
  type: clinical-guideline
  evidence_level: ia
  rationale: >
    Primary guideline for LDL-C management and statin therapy eligibility
    in primary and secondary prevention.
  open_access: true
```

**Normalized source content** (to be embedded inline in the scenario — `acc-aha-cholesterol-2023.md`): The file must include:
- Age eligibility for statin therapy: adults 40–75 years
- LDL-C thresholds: ≥70 mg/dL for high-risk patients, ≥190 mg/dL for high-intensity statin without risk calculation
- 10-year ASCVD risk thresholds: ≥7.5% for statin consideration, ≥20% for high-intensity
- Denominator exclusions: pregnancy, active liver disease, ESRD, known hypersensitivity to statin
- Numerator criterion: statin prescription (any intensity) during measurement period
- Evidence grades: CTT meta-analysis data (RCT, high quality), effect sizes for LDL reduction

**Expected outputs**:
- `sources/normalized/acc-aha-cholesterol-2023.md` — exists
- `topics/lipid-management/process/concepts.yaml` — exists, contains `"LDL-C"` and `"statin"`
- `tracking.yaml` — event `ingest_complete`

**Efficiency focus** (3 items):
- Agent uses `rh-skills source download --url` for the source, not a manual curl/download loop
- Agent does not re-read the discovery plan more than once during the implement sub-command
- Agent uses `rh-skills ingest classify` (not an inline classification table) for the source type

**Quality focus** (4 items):
- Normalized Markdown is clean — no garbled HTML artifacts from the download
- `concepts.yaml` contains at least: LDL-C, statin therapy, ASCVD, 10-year risk score, measurement period
- Classification tags for `acc-aha-cholesterol-2023` are appropriate (`type: clinical-guideline`, `evidence_level: ia`)
- `rh-skills ingest verify` reports zero errors

---

### Scenario 2 — `measure-logic-extraction.yaml` (rh-inf-extract)

**Clinical topic**: `lipid-management`

**Starting state**: `ingest_complete` — `acc-aha-cholesterol-2023.md` present and normalized.

**Required L2 artifact structure** (output of this scenario, used as fixture for scenarios 3 & 4):

```yaml
artifact_type: measure
sections:
  populations:
    initial_population:
      description: "Patients aged 40–75 with a diagnosis of hyperlipidemia or dyslipidemia"
      age_range: "40-75"
      diagnosis_value_set: "hyperlipidemia-disorders"
    denominator:
      description: "Equals initial population"
    numerator:
      description: "Patients with at least one statin prescription during the measurement period"
      medication_value_set: "statin-medications"
    denominator_exclusion:
      description: >
        Patients with active liver disease, pregnancy, ESRD, or documented statin allergy
  scoring:
    type: proportion
    improvement_notation: increase
  value_sets:
    - id: hyperlipidemia-disorders
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.9"
      description: "ICD-10 codes for hyperlipidemia and dyslipidemia"
    - id: statin-medications
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1047.97"
      description: "RxNorm codes for statin medications"
```

**Expected outputs**:
- `topics/lipid-management/process/plans/extract-plan.yaml` — exists, contains `"measure"`, contains `"populations"`
- `topics/lipid-management/structured/` — any file with `artifact_type: measure`
- `topics/lipid-management/structured/` — any file with `populations:`
- `topics/lipid-management/structured/` — any file with `value_sets:`
- `tracking.yaml` — events `extract_planned` and `structured_derived`

**Efficiency focus** (4 items):
- Agent does not re-read the normalized source file more than once during implement
- Agent uses `rh-skills promote derive` with `--artifact-type measure` (not inline YAML construction)
- Agent uses `rh-skills validate` after producing the artifact, not a manual schema review
- Agent does not call the ReasonHub MCP to look up valueset URLs that are already in concepts.yaml

**Quality focus** (5 items):
- Extract plan proposes `artifact_type: measure` (not `care-pathway` or `policy`)
- L2 artifact contains all four population sections: initial_population, denominator, numerator, denominator_exclusion
- Numerator criterion explicitly references a medication value set (statin prescriptions)
- Denominator exclusion includes all four exclusion categories from the source (liver disease, pregnancy, ESRD, allergy)
- `rh-skills validate` reports zero errors

---

### Scenario 3 — `cql-library-authoring.yaml` (rh-inf-formalize)

**Clinical topic**: `lipid-management`

**Starting state**: `extract_complete` — one approved L2 `measure` artifact present.

**Workspace L2 fixture** (the artifact from scenario 2, with `status: approved`): Embed the full artifact YAML described in Scenario 2 above, with `status: approved` and `reviewer_decision: approved` in the extract plan.

**Expected outputs**:
- `topics/lipid-management/process/plans/formalize-plan.md` — exists, contains `"Library"`, contains `"CQL"`
- `topics/lipid-management/computable/Library-lipid-statin-therapy.json` — exists, contains `"resourceType": "Library"`, contains `"text/cql"`
- `topics/lipid-management/computable/Measure-lipid-statin-therapy.json` — exists, contains `"resourceType": "Measure"`, contains `"group"`
- CQL content — contains `"context Patient"`, contains `"define \"InitialPopulation\""`, contains `"define \"Numerator\""`, contains `"valueset"`

**CQL structure the agent must produce** (quality_focus targets):

```cql
library LipidStatinTherapy version '1.0.0'

using FHIR version '4.0.1'

include FHIRHelpers version '4.0.1' called FHIRHelpers

valueset "Hyperlipidemia Disorders": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.9'
valueset "Statin Medications": 'http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1047.97'

parameter "Measurement Period" Interval<DateTime>
  default Interval[@2024-01-01, @2024-12-31]

context Patient

define "Initial Population":
  AgeInYearsAt(start of "Measurement Period") >= 40
    and AgeInYearsAt(start of "Measurement Period") <= 75
    and exists (
      [Condition: "Hyperlipidemia Disorders"] C
        where C.clinicalStatus ~ 'active'
    )

define "Denominator":
  "Initial Population"

define "Numerator":
  exists (
    [MedicationRequest: "Statin Medications"] M
      where M.authoredOn during "Measurement Period"
        and M.status = 'active'
  )

define "Denominator Exclusion":
  /* active liver disease, pregnancy, ESRD, or statin allergy — see exclusion value sets */
  false
```

**Efficiency focus** (4 items):
- Agent does not re-read `acc-aha-cholesterol-2023.md` during the formalize phase (source content is already in the L2 artifact)
- Agent uses the valueset URLs from the L2 artifact's `value_sets[]` directly — does not re-query ReasonHub MCP for valueset codes already resolved
- Agent does not call `rh-skills promote derive` during formalize (it is a formalize, not extract, operation)
- Agent produces the CQL content in a single `rh-skills formalize implement` invocation, not by patching the file in multiple steps

**Quality focus** (6 items):
- CQL file contains `context Patient` declaration (not `context Encounter` or absent)
- Date-interval arithmetic uses `"Measurement Period"` parameter or `Interval<DateTime>` — not hard-coded year strings like `@2024-01-01` directly in define statements
- Denominator `define` statement references `"Initial Population"` by name (correct chaining)
- Numerator `define` uses `during "Measurement Period"` interval check (not a manual date comparison)
- FHIR Library `content[]` attachment has `contentType: "text/cql"` and non-empty `data` (base64 CQL)
- FHIR Library `dataRequirement[]` lists at least `Condition` and `MedicationRequest` resource types

---

### Scenario 4 — `measure-bundle-complete.yaml` (rh-inf-formalize)

**Clinical topic**: `lipid-management`

**Starting state**: `extract_complete` — two approved L2 artifacts: a `measure` artifact (populations) and a `decision-table` artifact (exclusion criteria with clinical thresholds).

**Additional decision-table L2 fixture** (exclusion logic):

```yaml
artifact_type: decision-table
sections:
  conditions:
    - id: exc-liver
      condition: "Active liver disease (ALT > 3x ULN)"
      action: "Exclude from denominator"
    - id: exc-pregnancy
      condition: "Pregnancy or planned pregnancy"
      action: "Exclude from denominator"
    - id: exc-esrd
      condition: "End-stage renal disease (eGFR < 15 or dialysis)"
      action: "Exclude from denominator"
    - id: exc-allergy
      condition: "Documented allergy or intolerance to statin class"
      action: "Exclude from denominator"
  value_sets:
    - id: liver-disease-disorders
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.14"
    - id: pregnancy-disorders
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.80"
    - id: esrd-disorders
      url: "http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1116.65"
```

**Expected outputs**:
- `topics/lipid-management/computable/Library-lipid-statin-therapy.json` — exists, contains `"resourceType": "Library"`, contains `"text/cql"`
- `topics/lipid-management/computable/Measure-lipid-statin-therapy.json` — exists, contains `"resourceType": "Measure"`, contains `"library"`, contains `"lipid-statin-therapy"`
- `topics/lipid-management/computable/PlanDefinition-lipid-statin-therapy.json` — exists, contains `"resourceType": "PlanDefinition"`, contains `"definitionCanonical"`
- Cross-link: Measure JSON contains `"Library-lipid-statin-therapy"` (Library URL in `library[]`)
- Cross-link: PlanDefinition JSON contains `"Measure-lipid-statin-therapy"` (Measure URL in `action[].definitionCanonical`)
- `tracking.yaml` — events `formalize_planned` and `computable_converged`

**Efficiency focus** (4 items):
- Agent does not separately look up each of the four exclusion valuesets via ReasonHub MCP — they are already resolved in the `decision-table` artifact's `value_sets[]`
- Agent produces all three FHIR resources in a single `rh-skills formalize implement` invocation rather than one resource at a time
- Agent does not re-read the normalized source file (`acc-aha-cholesterol-2023.md`) during the formalize phase
- The CQL `Denominator Exclusion` define statement incorporates exclusion logic from the `decision-table` artifact without requiring the agent to re-derive it from source prose

**Quality focus** (5 items):
- Measure JSON `library[]` array contains the canonical URL of the produced Library resource (confirmed cross-link, not a placeholder)
- PlanDefinition `action[0].definitionCanonical` contains the canonical URL of the produced Measure (confirmed cross-link)
- CQL `Denominator Exclusion` define includes at least two of the four exclusion conditions from the decision-table artifact (liver disease, pregnancy, ESRD, allergy)
- All four valueset declarations from both L2 artifacts appear in the CQL file (6 valuesets total: 2 from measure + 4 from decision-table, minus any shared)
- `rh-skills verify` reports zero structural errors and zero cross-link errors across all three FHIR resources

## Assumptions

- The `lipid-management` topic slug is new — no existing `eval/scenarios/rh-inf-ingest/quality-measure-source.yaml` or extract/formalize counterparts exist. The ACC/AHA source content in the `cvd-risk-management` extract scenario (`acc-aha-lipid-2023.md`) provides a credible basis for the normalized source fixture but is adapted here as `acc-aha-cholesterol-2023.md` under the new topic.

- The eval harness (`scripts/eval-skill.sh`) reads scenario YAML files directly from `eval/scenarios/<skill>/` and does not require registration in a manifest file. New scenario files are automatically discovered by the harness.

- Inline CQL code samples embedded in scenario YAML `workspace.files[].content` fields use YAML literal block scalars (`|`) to preserve line breaks and special characters. The YAML does not need to base64-encode the CQL — the harness writes the content directly to disk.

- The formalize scenarios do not require the agent to produce syntactically valid, translator-compilable CQL. The quality_focus checks verify structural correctness (correct keywords, correct define chaining, correct interval syntax) but do not invoke a CQL translator. Translator-level validation is out of scope for this feature.

- The `value_sets[]` entries in the L2 artifact fixtures use real NLM VSAC canonical URLs (from the existing `cvd-risk-management` scenario's source material) as representative examples. These URLs do not need to resolve at test time — they serve as realistic fixtures for the agent to reference.

- The PlanDefinition produced by the measure-bundle-complete scenario uses `action[].definitionCanonical` to link to the Measure. This follows the FHIR CQF-Measures IG pattern. The spec does not prescribe a specific PlanDefinition `type` code beyond ensuring the cross-link is present.

- Cross-scenario dependency (ingest before extract before formalize) is a logical dependency for content coherence, not a runtime dependency. The eval harness runs each scenario independently; the dependency is expressed through workspace fixture content alignment, not through scenario chaining.
