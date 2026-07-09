# ReasonHub Healthcare Informatics Pipeline — Demo Summary

> **Topic:** Hypertension CMS Quality Measure (`hypertension-cms-measure`)
> **Date completed:** 2026-05-18
> **Stack:** `rh-skills` CLI · ReasonHub MCP · pi coding agent

---

## What This Demo Shows

This project demonstrates a fully automated, **reviewer-gated evidence-to-computable pipeline** — starting from a plain-English clinical topic and ending with a publish-ready FHIR R4 package. The topic is **CMS165 — Controlling High Blood Pressure (NQF 0018)**, the flagship CMS electronic clinical quality measure tracking the proportion of patients aged 18–85 with essential hypertension whose most recent blood pressure reading is `< 140/90 mmHg`.

Every step is traceable: sources have checksums, structured artifacts record which sources they were derived from, computable resources record which structured artifacts they were converged from, and the event log in `tracking.yaml` timestamps every transition.

---

## The Three-Level Lifecycle

```
RAW SOURCES  ─── ingest ──►  L1 NORMALIZED  ─── extract ──►  L2 STRUCTURED  ─── formalize ──►  L3 COMPUTABLE
 (HTML/PDF)                  (Markdown +                      (YAML artifacts)                  (FHIR R4 JSON
                              front-matter)                                                       + CQL)
```

| Level | What it is | Files in this project |
|---|---|---|
| **L1** | Downloaded + normalized sources | `sources/normalized/*.md` (13 files) |
| **L2** | Human-reviewed YAML artifacts | `structured/{measure,terminology,assessment,decision-table,evidence-summary}/*.yaml` |
| **L3** | Computable FHIR resources + CQL | `computable/*.json`, `*.cql` |
| **📦 Package** | Deployable npm/FHIR bundle | `package/` — `@reason/hypertension-cms-measure v1.0.0` |

---

## Stage 1 — Discovery (L1)

**Tool used: `rh-skills` CLI**

The agent ran `rh-skills` discovery commands to produce `discovery-plan.yaml`, a curated list of 18 sources across six categories. It also wrote `discovery-readout.md` — a human-readable domain brief covering CMS program alignment, SDOH relevance, health equity context, and a terminology map.

**Sources ultimately ingested (13 of 18):**

| Source | Type | Evidence Level |
|---|---|---|
| USPSTF Hypertension Screening (2021) | Guideline | USPSTF-B |
| CDC NCHS Hypertension Surveillance | Government data | N/A |
| GBD 2023 — Global Burden of Disease | Health economics | Ia |
| VSAC NQF 0018 Value Sets | Value set | Reference standard |
| QI-Core FHIR IG | FHIR IG | Reference standard |
| Gravity SDOH FHIR IG | FHIR IG | Reference standard |
| PMID 41439541 — Medicare HTN QI | PubMed article | Grade B |
| PMID 41186866 — Patient Activation RCT | PubMed article | Ib |
| NCT07556783 — Telephone HBPM Trial | Clinical trial registry | N/A |
| ICD-10-CM (NLM) | Terminology | Reference standard |
| SNOMED CT | Terminology | Reference standard |
| LOINC | Terminology | Reference standard |
| RxNorm (NLM) | Terminology | Reference standard |

> **5 planned sources were unavailable** (HTTP 404/403): CMS165 eCQM page, ACC/AHA 2017 guideline, HCUP statistical brief. The pipeline logged these failures and continued without them — evidence traceability was preserved.

Each source was: ① downloaded, ② normalized to Markdown, ③ classified (type + evidence level + domain tags), ④ annotated with concept metadata (75 unique concepts extracted across all 13 sources).

---

## Stage 2 — Extract (L2)

**Tool used: `rh-skills` CLI + ReasonHub MCP (terminology lookup)**

The agent produced `extract-plan.yaml` proposing **6 structured artifacts**. The human reviewer (Brian Kaney) reviewed and approved 5, rejecting 1 with a note explaining why.

### Concept Review — powered by ReasonHub MCP

Before structured artifacts were generated, every concept extracted from the 13 sources was presented for human review. **ReasonHub MCP** was called to look up standardized terminology codes:

- `reasonhub__search_snomed` — to find SNOMED CT codes for clinical findings (e.g., *Essential hypertension* → `59621000`, *Housing instability* → `1156191002`)
- `reasonhub__search_loinc` — for blood pressure observation codes (*Systolic BP* → `8480-6`, *Diastolic BP* → `8462-4`, *BP panel* → `85354-9`)
- `reasonhub__search_rxnorm` — for antihypertensive drug classes (*Thiazide diuretic* → `3571`, *ACE inhibitor* → `1430745`)
- `reasonhub__search_icd10` — for diagnosis and SDOH codes (*Essential hypertension* → `I10`, *Food insecurity* → `Z59.41`, *Housing instability* → `Z59.81`)
- `reasonhub__codesystem_lookup` / `reasonhub__codesystem_verify_code` — to confirm LOINC UCUM units (e.g., `mm[Hg]` for blood pressure values)

**Result:** 75 concepts reviewed → **43 approved with standardized codes** across SNOMED, ICD-10-CM, LOINC, and RxNorm. These feed directly into L2 `concepts.yaml` and from there into L3 ValueSet resources.

### Approved L2 Artifacts

| Artifact | Sources | Key content |
|---|---|---|
| **measure** | All 13 sources | CMS165 initial population (age 18–85, I10/SNOMED 59621000), denominator, exclusions (ESRD N18.6, hospice, frailty), numerator (BP < 140/90 mmHg). Stratifications: race/ethnicity, age group, payer type. |
| **terminology** | VSAC, LOINC, SNOMED, ICD-10-CM, RxNorm | 7 value sets: essential hypertension (ICD-10 + SNOMED), BP observations (LOINC), antihypertensives (RxNorm), CKD exclusions, SDOH codes, BP screening procedures |
| **decision-table** | USPSTF, QI-Core, VSAC, Gravity, CDC, NCT trial | 10 ECA rules across 5 event domains: HTN-SCREEN, HTN-MONITOR, BP-READING, SDOH-SCREEN, QI-OUTREACH. 11 clinical actions. |
| **evidence-summary** | CDC, GBD 2023, Gravity, PMID 41439541, NCT trial | 8 graded findings: 49.1% US prevalence, 56.8M office visits/year, 42,343 deaths, global SBP burden (Ia), HBPM efficacy (Grade B), SDOH drivers |
| **assessment** | Gravity SDOH IG, USPSTF | 9-item instrument: 5 SDOH boolean items (AHC HRSN domains), 4 numeric BP items (office + OOO confirmation) with LOINC codes and UCUM units |
| ~~policy~~ | NCT trial only | ❌ **Rejected** — clinical trial registry is not a policy source; trial content folded into evidence-summary |

---

## Stage 3 — Formalize (L3)

**Tool used: `rh-skills` CLI + ReasonHub MCP (code verification)**

The agent produced `formalize-plan.yaml` mapping each L2 artifact to one or more FHIR R4 resource types via named **strategies**. The reviewer approved all 5 strategies, designating `measure` as the **primary implementation target**.

During formalization, **ReasonHub MCP** was called again to:
- `reasonhub__valueset_expand` — verify ValueSet compositions before writing JSON
- `reasonhub__codesystem_verify_code` — confirm all 43 concept codes were valid in their respective code systems
- `reasonhub__codesystem_subsumes` — verify SNOMED hierarchy relationships (e.g., that `38341003` Hypertensive disorder subsumes `59621000` Essential hypertension)

### Computable Artifacts Produced

| Strategy | L2 Input | FHIR Resources Generated |
|---|---|---|
| `terminology` | terminology.yaml | `ValueSet-vs-htn-dx-icd10.json`, `ValueSet-vs-htn-dx-snomed.json`, `ValueSet-vs-bp-obs-loinc.json`, `ValueSet-vs-antihtn-rxnorm.json`, `ValueSet-vs-ckd-comorbidity.json`, `ValueSet-vs-sdoh-icd10.json`, `ValueSet-vs-bp-screening-snomed.json`, `ConceptMap-terminology-conceptmap.json` |
| `assessment` | assessment.yaml | `Questionnaire-assessment.json` (9 items with LOINC/SNOMED/ICD-10 codes + UCUM units) |
| `evidence-summary` | evidence-summary.yaml | `Evidence-evidence-summary.json`, `EvidenceVariable-evidence-summary-evidencevariable.json` |
| `decision-table` | decision-table.yaml | `PlanDefinition-decision-table.json` (10 ECA rules), `Library-decision-table-library.json` + `DecisionTableLibrary.cql` |
| `measure` ⭐ | measure.yaml | `Measure-measure.json` (proportional, 4 populations, 3 stratifications), `Library-measure-library.json` + `MeasureLibrary.cql` |

### The `rh` CQL Toolchain

CQL authoring in this pipeline uses two CLI layers. `rh` is a **Rust binary** that owns all deterministic CQL operations — validation, compilation to ELM, and expression evaluation. `rh-skills cql` is a **project-aware wrapper** that resolves topic paths and invokes `rh` with the correct arguments.

```
# Install the rh binary
cargo install rh

# Or configure an existing path
export RH_CLI_PATH=/usr/local/bin/rh
# alternatively: .rh-skills.toml  →  [cql] rh_cli_path = "..."
```

The formalize phase runs three CQL operations for each library — validate, translate to ELM, then a spot-check eval pass for key expressions:

**Step 1 — Validate syntax and semantics**

```bash
# rh-skills wrapper (project-aware path resolution)
rh-skills cql validate hypertension-cms-measure MeasureLibrary
rh-skills cql validate hypertension-cms-measure DecisionTableLibrary

# Underlying rh command
rh cql validate topics/hypertension-cms-measure/computable/MeasureLibrary.cql
```

Exits 0 on success. On failure it prints the offending line, column, and a category (`syntax`, `translation`, `type-mismatch`, etc.). The agent retries once with a targeted fix; if it fails a second time it reports the error verbatim and waits for human guidance.

**Step 2 — Compile to ELM JSON**

```bash
# rh-skills wrapper — writes ELM under computable/elm/
rh-skills cql translate hypertension-cms-measure MeasureLibrary
# output → topics/hypertension-cms-measure/computable/elm/MeasureLibrary.json

# Underlying rh command with flags
rh cql compile topics/hypertension-cms-measure/computable/MeasureLibrary.cql \
  --output topics/hypertension-cms-measure/computable/elm/MeasureLibrary.json

# With debug annotations (adds source locators and result types to ELM nodes)
rh cql compile topics/hypertension-cms-measure/computable/MeasureLibrary.cql \
  --output topics/hypertension-cms-measure/computable/elm/MeasureLibrary.json \
  --debug

# Strict mode — disables implicit conversions
rh cql compile ... --strict
```

ELM JSON is what the FHIR Library resource embeds as
`content[type=application/elm+json]`. It must be regenerated every time the
`.cql` source changes, then `rh-skills formalize <topic> <artifact> --force`
must be re-run so the FHIR Library embeds the current CQL and ELM content.
Stale ELM causes silent behavior differences at runtime.

**Step 3 — Evaluate expressions against fixture data (spot-check / debug)**

```bash
# Evaluate a single named define against a FHIR Bundle
rh cql eval \
  topics/hypertension-cms-measure/computable/MeasureLibrary.cql \
  "Numerator" \
  --data tests/cql/MeasureLibrary/case-001-controlled-bp/input/bundle.json

# Evaluate with step-by-step trace (useful for debugging null propagation)
rh cql eval \
  topics/hypertension-cms-measure/computable/MeasureLibrary.cql \
  "Most Recent Systolic Value" \
  --data tests/cql/MeasureLibrary/case-002-uncontrolled/input/bundle.json \
  --trace

# Additional library include path (e.g. for FHIRHelpers)
rh cql eval ... \
  --lib-path topics/hypertension-cms-measure/computable/ \
  --data bundle.json

# Interactive REPL — load a library, evaluate expressions interactively
rh cql repl

# Parse tree inspection
rh cql explain parse  topics/hypertension-cms-measure/computable/MeasureLibrary.cql

# Semantic analysis details
rh cql explain compile topics/hypertension-cms-measure/computable/MeasureLibrary.cql
```

**FHIRHelpers dependency**

The `rh` evaluator is **FHIRHelpers-agnostic** — unlike the Java reference translator, it does not auto-inject `FHIRHelpers.ToConcept()` wrapping. Every library that uses FHIR coded, quantity, or date types must explicitly include it:

```cql
include fhir.cqf.common.FHIRHelpers version '4.0.1' called FHIRHelpers
```

To install the package locally for validation:

```bash
rh download package fhir.cqf.common 4.0.1
```

This is a local validation dependency only — the runtime resolves FHIRHelpers independently and it is not committed into the topic's `computable/` directory.

**Full `rh cql` command reference**

| Command | What it does | Key flags |
|---|---|---|
| `rh cql validate <file.cql>` | Syntax + semantic check; exits non-zero on errors | — |
| `rh cql compile <file.cql>` | Compile to ELM JSON | `-o / --output <path>`, `--debug`, `--strict` |
| `rh cql eval <file.cql> <name>` | Evaluate one named expression | `--data <bundle.json>`, `--lib-path <dir>`, `--trace` |
| `rh cql explain parse <file.cql>` | Print parse tree | — |
| `rh cql explain compile <file.cql>` | Print semantic analysis | — |
| `rh cql repl` | Interactive expression REPL | — |
| `rh download package <id> <version>` | Fetch a FHIR package (e.g. FHIRHelpers) | — |

**Output paths**

| Artifact | Path |
|---|---|
| CQL source | `topics/<topic>/computable/<LibraryName>.cql` |
| ELM JSON | `topics/<topic>/computable/elm/<LibraryName>.json` |
| Test fixtures | `tests/cql/<LibraryName>/case-NNN-<desc>/` |
| Validation report | stdout / stderr |

---

### The CQL (Clinical Quality Language) Libraries

Two CQL libraries were generated and compiled to ELM (JSON):

**`MeasureLibrary.cql`** — CMS165 population logic:
```cql
define "Initial Population":
  "Age 18 to 85"
    and exists "Qualifying Outpatient Encounters"
    and "Has Active Hypertension Diagnosed Before October"

define "Numerator":
  "Denominator"
    and "Most Recent Systolic Value" is not null
    and "Most Recent Diastolic Value" is not null
    and "Most Recent Systolic Value" < 140
    and "Most Recent Diastolic Value" < 90
```

The library handles both panel observations (`LOINC 85354-9`) and standalone component codes (`8480-6` / `8462-4`), extracts values from `FHIR.Quantity`, and correctly resolves the `< 140/90 mmHg` threshold.

**`DecisionTableLibrary.cql`** — CDS rule condition evaluation logic for the 10 ECA rules in the PlanDefinition.

---

## Final Package

**Tool used: `rh-skills` CLI**

All computable resources were bundled into a deployable package:

```
@reason/hypertension-cms-measure  v1.0.0
├── 22 FHIR R4 resources
├── FHIR R4 4.0.1
├── Dependencies: us-core 6.1.0, crmi 1.0.0, cql 2.0.0
└── ImplementationGuide-hypertension-cms-measure.json
```

---

## How `rh-skills` CLI and ReasonHub Work Together

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HUMAN REVIEWER                               │
│   Reviews plans, approves/rejects artifacts, provides decisions     │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ approve / reject
          ┌───────────▼──────────────┐
          │    rh-skills CLI (rh)    │
          │  Orchestrates pipeline   │
          │  Reads/writes YAML,      │
          │  JSON, CQL, tracking.yaml│
          └───────────┬──────────────┘
                      │ terminology lookups
          ┌───────────▼──────────────┐
          │    ReasonHub MCP         │
          │  SNOMED · LOINC          │
          │  RxNorm · ICD-10-CM      │
          │  UCUM · ValueSet expand  │
          │  Code verify · Subsumes  │
          └──────────────────────────┘
```

| What we need to do | Tool |
|---|---|
| Scaffold a topic, download sources, normalize to Markdown | `rh-skills` CLI |
| Generate and review discovery/extract/formalize plans | `rh-skills` CLI |
| Approve or reject proposed artifacts | Human reviewer via `rh-skills promote` |
| Look up clinical codes (SNOMED, LOINC, RxNorm, ICD-10-CM) | **ReasonHub MCP** |
| Verify codes exist and are active | **ReasonHub MCP** |
| Expand and compose FHIR ValueSets | **ReasonHub MCP** |
| Generate CQL source (`.cql`) from L2 structured artifacts | `rh-skills` CLI (with agent) |
| Validate CQL syntax and semantics | `rh` Rust binary (`rh cql validate`) |
| Compile CQL to ELM JSON | `rh` Rust binary (`rh cql compile`) |
| Evaluate CQL expressions against fixture data | `rh` Rust binary (`rh cql eval`) |
| Package final FHIR IG bundle | `rh-skills` CLI |

---

## Key Numbers

| Metric | Value |
|---|---|
| Sources ingested | 13 |
| Concepts extracted | 75 |
| Concepts approved with codes | 43 |
| L2 artifacts approved | 5 of 6 proposed |
| L3 FHIR resources generated | 22 |
| CQL libraries | 2 (compiled to ELM JSON) |
| ValueSets | 8 (7 condition/obs/med + 1 SDOH) |
| Terminology systems covered | SNOMED CT, ICD-10-CM, LOINC, RxNorm |
| Pipeline duration (wall clock) | ~2 hours (2026-05-18, 19:41 → 21:32 UTC) |
| Human review touchpoints | 3 (extract plan, concept review, formalize plan) |

---

## Traceability Example

Every claim in every FHIR resource traces back to a source. Here's one end-to-end chain:

```
USPSTF 2021 Guideline (HTML)
  └── normalized → sources/normalized/uspstf-hypertension-screening-2021.md
        └── annotated → 9 concepts (hypertension screening, office BP measurement...)
              └── extracted → structured/measure/measure.yaml  (et-m-01: BP < 140/90 threshold)
                    └── formalized → computable/Measure-measure.json
                          └── CQL: MeasureLibrary.cql  ("Most Recent Systolic Value" < 140)
                                └── packaged → @reason/hypertension-cms-measure v1.0.0
```

---

*Generated by pi coding agent · rh-skills v0.1.0 · ReasonHub MCP*
