# rh-inf-ingest Reference

Companion reference for `SKILL.md`. Loaded on demand during implement and verify modes.

---

## Concept Type Vocabulary

Use these types when calling `rh-skills ingest annotate --concept "<name>:<type>"`.

| Type | Description | Example |
|------|-------------|---------|
| `condition` | Clinical diagnosis or disease | `Hypertension`, `Type 2 Diabetes` |
| `finding` | Symptom, sign, or clinical finding | `Nasal congestion`, `Loss of sense of smell` |
| `medication` | Drug, drug class, or therapeutic agent | `Metoprolol`, `ACE Inhibitor` |
| `procedure` | Clinical procedure or intervention | `Functional endoscopic sinus surgery` |
| `measure` | Quality measure or clinical metric | `SNOT-22`, `HbA1c` |
| `lab` | Laboratory test result (concept with value and unit) | `Creatinine 0.8 mg/dL`, `Hemoglobin (Hgb) 15.0 g/dL` |
| `code` | Terminology code or value set reference | `ICD-10 I10`, `LOINC 8480-6` |
| `term` | General clinical or domain term (default) | `Shared decision-making` |
| `guideline-ref` | Reference to a clinical guideline | `JNC 8`, `ACC/AHA 2017` |
| `sdoh-factor` | Social determinant of health domain | `Food Insecurity`, `Housing Instability` |

### Mapping Guidance For Common Clinical Concept Shapes

Use the existing concept types consistently when annotating normalized clinical sources:

| Source concept shape | Preferred type | Notes |
|----------------------|----------------|-------|
| Disease, disorder, subtype | `condition` | Prefer the most specific clinically meaningful disorder name |
| Symptom, sign, or clinical finding | `finding` | Captures patient-reported or observed findings; do not omit |
| Drug ingredient or drug class | `medication` | Use explicit ingredient/class names when stated |
| Procedure, intervention, imaging, postop care action | `procedure` | Includes surgery, endoscopy, CT, irrigation, debridement |
| Named score, instrument, quality measure, outcome metric | `measure` | Includes `SNOT-22` and explicit QoL instruments |
| Adverse event or known complication | `condition` | Treat as a condition; capture even if secondary |
| Guideline, consensus statement, or named recommendation set | `guideline-ref` | Use the concise title without punctuation that conflicts with CLI delimiters |
| Terminology identifier | `code` | Add when the mapping is high confidence |
| General domain terminology without a more specific type | `term` | Last resort; prefer a specific type above whenever possible |

### Specificity Guidance

Keep the generic term and also add the specific form when the source supports it.
Capture subtypes and exclusions separately when they affect scope or eligibility.

| Generic (keep) | Also add when source supports it |
|----------------|----------------------------------|
| `Sinus surgery` | `Functional endoscopic sinus surgery`, `Revision endoscopic sinus surgery` |
| `Nasal endoscopy` | `Nasal sinus endoscopy` |
| `CT scan of the paranasal sinuses` | `Computed tomography of paranasal sinuses` |
| `Topical steroids` | `Intranasal steroid therapy` |
| `Oral steroids` | `Systemic corticosteroid therapy` |
| `Antibiotics` | `Antibacterial` (drug class) or the specific agent when named |
| `Nasal discharge` | `Purulent nasal discharge` when purulence is specified |
| `Smell impairment` | `Loss of sense of smell` or `Sense of smell impaired` per source phrasing |
| `Pain reliever` | `Acetaminophen`, `Ibuprofen` when the source names the agent |

### Terminology Code Naming Convention

`rh-skills ingest annotate` stores only `name` and `type`, so code-bearing concepts
must encode the coding system and identifier inside the `name` field.

Use this safe format for `code` concepts:

```text
<SYSTEM> <CODE> <DISPLAY>
```

Examples:
- `SNOMEDCT 897657000 Chronic rhinosinusitis`
- `SNOMEDCT 241526005 Computed tomography of paranasal sinuses`
- `RXNORM 161 Acetaminophen`

Do not use colons inside the concept name because `annotate` parses `name:type`.
For example, prefer `SNOMEDCT 897657000 Chronic rhinosinusitis:code` and avoid
`SNOMEDCT:897657000 Chronic rhinosinusitis:code`.

---

## Evidence Level Taxonomy

| Level | Description |
|-------|-------------|
| `ia` | Systematic review or meta-analysis of RCTs |
| `ib` | At least one RCT |
| `iia` | At least one controlled non-randomized study |
| `iib` | At least one other quasi-experimental study |
| `iii` | Non-experimental descriptive study (cohort, case-control, cross-sectional) |
| `iv` | Expert committee reports or clinical experience |
| `v` | Expert opinion / guidelines |
| `expert-consensus` | Formal expert consensus process |

---

## Source Type Taxonomy

| Type | Description |
|------|-------------|
| `clinical-guideline` | Clinical practice guideline from a professional society or government body |
| `systematic-review` | Systematic review or meta-analysis |
| `rct` | Randomized controlled trial |
| `cohort-study` | Prospective or retrospective cohort study |
| `case-control` | Case-control study |
| `cross-sectional` | Cross-sectional survey or study |
| `case-report` | Case report or case series |
| `expert-opinion` | Expert opinion, editorial, or commentary |
| `textbook` | Medical textbook or reference text |
| `government-program` | Government program document, coverage determination, or policy |
| `quality-measure` | Quality measure specification (eCQM, HEDIS, NQF) |
| `terminology` | Terminology system documentation (ICD, SNOMED, LOINC, RxNorm) |
| `fhir-ig` | FHIR Implementation Guide |
| `sdoh-assessment` | SDOH screening tool or assessment instrument |
| `health-economics` | Health economics study, cost-effectiveness analysis |
| `document` | General document (default when type is unspecified) |

---

## Tool Installation

`rh-skills ingest normalize` uses external tools for binary file formats. Install them
before running implement mode:

| Tool | Purpose | Install (macOS) | Install (Linux) |
|------|---------|-----------------|-----------------|
| `pdftotext` | Extract text from PDF files | `brew install poppler` | `apt-get install poppler-utils` |
| `pandoc` | Convert Word/Excel/HTML to Markdown | `brew install pandoc` | `apt-get install pandoc` |

If either tool is absent, `rh-skills ingest normalize` sets `text_extracted: false` in
the normalized.md frontmatter and continues (soft-fail). You can re-run
normalize after installing the missing tool.

Source naming note: `rh-skills ingest implement` and `rh-skills ingest normalize`
auto-derive `<name>` from the filename by sanitizing the stem and appending the
extension with an underscore suffix (`<stem>_<ext>`). Example:
`CPG_SurgCRS_FAQ_V6.pdf` -> `CPG_SurgCRS_FAQ_V6_pdf`.
Use this derived name for subsequent `classify` and `annotate` commands.

---

## Auth Note Advisory Format

For sources with `access: authenticated` in discovery-plan.yaml, the
`auth_note` field explains how to obtain the source manually:

```yaml
sources:
  - name: uptodate-hypertension
    access: authenticated
    url: https://www.uptodate.com/contents/hypertension-overview
    auth_note: >
      Requires institutional UpToDate subscription.
      Access via library portal or VPN. Download PDF and place at
      sources/uptodate-hypertension.pdf,
      then run: rh-skills ingest implement sources/uptodate-hypertension.pdf --topic <topic>
```

---

## concepts.yaml Schema

`topics/<topic>/process/concepts.yaml` is produced and updated by `rh-skills ingest annotate`.

```yaml
topic: "<topic-slug>"
generated: "<ISO-8601 timestamp>"
concepts:
  - name: "<canonical concept name>"
    type: "<concept type>"        # see Concept Type Vocabulary above
    sources:
      - "<source-name>"

  - name: "SNOMEDCT 897657000 Chronic rhinosinusitis"
    type: "code"
    sources:
      - "<source-name>"
```

Each call to `rh-skills ingest annotate` **appends** new concept entries to this file (one
entry per concept per source). Pass `--overwrite` to replace entries previously written for
that source. Downstream skills (`rh-inf-extract`, `rh-inf-formalize`) consume this file as
an accumulated vocabulary; any deduplication of concept names is their responsibility.

---

## normalized.md Frontmatter Schema

Every `sources/normalized/<name>.md` begins with a YAML frontmatter block:

```yaml
---
source: "<source-name>"
topic: "<topic-slug>"
normalized: "<ISO-8601 timestamp>"
original: "sources/<filename>"
text_extracted: true|false
concepts:                          # added by rh-skills ingest annotate
  - name: "<concept name>"
    type: "<concept type>"
---

<extracted markdown content>
```
