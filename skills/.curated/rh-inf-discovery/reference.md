# rh-inf-discovery Reference

Companion reference for `SKILL.md`. Loaded on demand during session mode.

---

## Domain Advice Checklist

Apply the relevant sections below when generating domain advice in Step 1 of
session mode. Address each applicable item in the **Domain Advice** section of
`discovery-plan.md` (the narrative file).

### CMS Program Alignment
- Does an existing CMS eCQM (electronic clinical quality measure) cover this
  condition? Check [eCQM Library](https://ecqi.healthit.gov/ecqms) and
  [CMIT](https://cmit.cms.gov/).
- Is there a MIPS/QPP performance measure? Check
  [QPP Measures](https://qpp.cms.gov/mips/explore-measures).
- Is there a Medicaid or CMMI model that incentivizes this intervention?
- Are there CMS national or local coverage determinations (NCD/LCD) affecting
  clinical decision support?

### SDOH Relevance
- Does this condition have known SDOH drivers? Map to Gravity Project domains:
  Food Insecurity · Housing Instability / Homelessness · Transportation Access ·
  Utility Difficulties · Interpersonal Safety · Financial Strain · Social
  Isolation · Education / Employment · Health Behaviors.
- Is there a standardized SDOH screening tool in use? (PRAPARE, AHC HRSN, etc.)
- Is the [Gravity SDOH FHIR IG](https://hl7.org/fhir/us/sdoh-clinicalcare/)
  relevant for interoperability planning?

### Health Equity
- Are there documented disparities (race, ethnicity, language, geography,
  disability) in screening, treatment, or outcomes for this condition?
- Are there CMS health equity goals or HEDIS equity stratification requirements?
- Does the USPSTF or specialty society address disparate populations explicitly?

### Quality Measure Landscape
- What HEDIS measures apply? (Check NCQA measure list)
- What NQF-endorsed measures exist? (Check NQF Quality Positioning System)
- Are there Joint Commission quality standards?
- Is there a FHIR-based measure using QI-Core / US Core profiles?

### Terminology Systems
Identify which coding systems are likely needed (include at least one in `sources[]`):
- **Diagnoses**: ICD-10-CM ([NLM](https://www.nlm.nih.gov/research/umls/sourcereleasedocs/current/ICD10CM/))
- **Clinical findings / procedures**: SNOMED CT ([SNOMED International](https://www.snomed.org/))
- **Lab / observations**: LOINC ([Regenstrief](https://loinc.org/))
- **Medications**: RxNorm ([NLM](https://www.nlm.nih.gov/research/umls/rxnorm/))
- **Units**: UCUM ([Unitsofmeasure.org](https://ucum.org/))
- **Social determinants**: Gravity Project SDOH value sets ([VSAC](https://vsac.nlm.nih.gov/))

### Health Economics Angle
Required when the topic involves a **chronic condition**, **preventive intervention**,
or **CMS quality program**. Address in domain advice and include at least one
`health-economics` source in `sources[]`:
- Total cost of care / disease burden (HCUP, MEPS, GBD)
- Cost per QALY or cost-effectiveness analysis (CEA Registry, ICER, NICE HTA)
- CMS National Health Expenditure Data for population-level spend
- Employer or payer burden if applicable

---

## US Government Healthcare Coverage

For any topic with a US clinical or population health angle, include sources from:

| Source | URL | What to find |
|--------|-----|--------------|
| CMS eCQM Library | https://ecqi.healthit.gov/ecqms | Existing quality measures |
| CMS CMIT | https://cmit.cms.gov/ | Model tests and initiatives |
| QPP / MIPS Measures | https://qpp.cms.gov/mips/explore-measures | Clinician performance measures |
| USPSTF | https://www.uspreventiveservicestaskforce.org/uspstf/recommendation-topics | Preventive service grades |
| Gravity Project | https://thegravityproject.net/ | SDOH domains, FHIR IG |
| AHRQ | https://www.ahrq.gov/research/findings/evidence-based-reports/ | Evidence-based practice reports |
| CDC / MMWR | https://www.cdc.gov/mmwr/ | Epidemiological data |
| HCUP | https://www.hcup-us.ahrq.gov/ | Hospital utilization + costs |
| MEPS | https://meps.ahrq.gov/ | Medical expenditure panel survey |
| GBD (IHME) | https://vizhub.healthdata.org/gbd-results | Global burden of disease |
| NLM VSAC | https://vsac.nlm.nih.gov/ | Value sets for eCQMs |
| CMS NCD/LCD | https://www.cms.gov/medicare-coverage-database | Coverage policies |
| HRSA | https://www.hrsa.gov/ | Underserved populations, safety net |

### Accessing CMS Data Without Authentication
- eCQM measure packages: downloadable as FHIR JSON bundles from eCQI
- HCUP: most summary statistics are publicly available; microdata requires DUA
- MEPS: public use files downloadable at no cost from AHRQ

---

## Medical Journals

Use these when identifying high-value publication sources. Most require
institutional access; include as `access: authenticated` with `auth_note`.

For a comprehensive list see: https://en.wikipedia.org/wiki/List_of_medical_journals

### High-Impact General Medicine
| Journal | Publisher | Access |
|---------|-----------|--------|
| NEJM | Massachusetts Medical Society | Institutional |
| JAMA (+ JAMA Network) | AMA | Institutional / open abstracts |
| The Lancet (+ family) | Elsevier | Institutional |
| BMJ | BMJ Publishing | Free registration for abstracts |
| Annals of Internal Medicine | ACP | Institutional |

### Healthcare Informatics / Health IT
| Journal | Publisher | Access |
|---------|-----------|--------|
| JAMIA | Oxford / AMIA | Institutional |
| J Biomed Informatics | Elsevier | Institutional |
| npj Digital Medicine | Nature | Open access |
| Applied Clinical Informatics | Thieme | Institutional |

### Quality, Safety, and Policy
| Journal | Publisher | Access |
|---------|-----------|--------|
| Health Affairs | Project HOPE | Institutional |
| JAMA Health Forum | AMA | Open access |
| Milbank Quarterly | Wiley | Open access |
| BMJ Quality & Safety | BMJ | Institutional |

### Specialty (examples — expand based on topic)
| Specialty | Key Journal | Access |
|-----------|-------------|--------|
| Cardiology | JACC, Circulation | Institutional |
| Endocrinology / Diabetes | Diabetes Care, Diabetologia | Institutional |
| Oncology | JCO, JNCI | Institutional |
| Nephrology | JASN, CJASN | Institutional |
| Pulmonology | AJRCCM | Institutional |
| Psychiatry / Behavioral | Lancet Psychiatry | Institutional |

---

## Source Type Taxonomy

| `type` value | Examples |
|---|---|
| `guideline` | ADA Standards, ACC/AHA guidelines, USPSTF recommendations, NICE guidance |
| `clinical-guideline` | Alias for `guideline` |
| `systematic-review` | Cochrane reviews, AHRQ evidence reports |
| `rct` | Randomized controlled trials |
| `cohort-study` | Prospective or retrospective cohort studies |
| `case-control` | Case-control studies |
| `cross-sectional` | Cross-sectional surveys and prevalence studies |
| `case-report` | Case reports and case series |
| `expert-opinion` | Expert opinion, editorial, or commentary |
| `terminology` | SNOMED CT, LOINC, ICD-10-CM, RxNorm, UCUM |
| `value-set` | VSAC (NLM), FHIR value sets, PHIN VADS |
| `measure-library` | CMS eCQMs, HEDIS, MIPS/QPP measures, NQF-endorsed measures |
| `quality-measure` | Alias for `measure-library` |
| `fhir-ig` | US Core, QI-Core, CARIN BB, Gravity SDOH FHIR IG |
| `cds-library` | CDS Hooks registry, OpenCDS |
| `sdoh-assessment` | PRAPARE, AHC HRSN Tool, CDC SVI, CDC PLACES |
| `health-economics` | HCUP, MEPS, GBD, CEA Registry, ICER, NICE HTA |
| `government-program` | CMS CMMI models, Medicaid state plans, CMS LCD/NCD, HRSA |
| `registry` | ClinicalTrials.gov, disease registries |
| `pubmed-article` | PubMed / PMC research articles |
| `textbook` | Textbooks and reference manuals |
| `document` | General documents not covered above |
| `other` | Anything not covered above |

**At least one `terminology` entry is required** for any plan that passes `verify`.

---

## Evidence Level Taxonomy

| Value | Meaning |
|-------|---------|
| `grade-a` | GRADE high-certainty evidence |
| `grade-b` | GRADE moderate-certainty evidence |
| `grade-c` | GRADE low-certainty evidence |
| `grade-d` | GRADE very low-certainty evidence |
| `uspstf-a` | USPSTF Grade A (high certainty of substantial net benefit) |
| `uspstf-b` | USPSTF Grade B (high certainty of moderate net benefit) |
| `uspstf-c` | USPSTF Grade C (moderate certainty of small net benefit) |
| `uspstf-d` | USPSTF Grade D (moderate/high certainty of no net benefit or harm) |
| `uspstf-i` | USPSTF Grade I (insufficient evidence) |
| `ia` | Oxford Level 1a — systematic review of RCTs |
| `ib` | Oxford Level 1b — individual RCT |
| `iia` | Oxford Level 2a — systematic review of cohort studies |
| `iib` | Oxford Level 2b — individual cohort study |
| `iii` | Oxford Level 3 — case-control study |
| `iv` | Oxford Level 4 — case series |
| `v` | Oxford Level 5 — expert opinion |
| `expert-consensus` | No formal systematic review; expert opinion or consensus statement |
| `reference-standard` | Authoritative reference (terminology, value set, coding system) |
| `n/a` | Not applicable (e.g., clinical trials, registries, government data sets) |

---

## rh-skills search Command Reference

```sh
# Search PubMed articles
rh-skills search pubmed --query "<terms>" --max 20 [--json]

# Search PubMed Central (open-access full text)
rh-skills search pmc --query "<terms>" --max 20 [--json]

# Search ClinicalTrials.gov
rh-skills search clinicaltrials --query "<terms>" --max 20 [--json]
```

The `--json` flag outputs a structured array for programmatic parsing:
```json
[
  {
    "id": "...",
    "title": "...",
    "authors": ["..."],
    "year": "2024",
    "journal": "...",
    "abstract": "...",
    "url": "https://pubmed.ncbi.nlm.nih.gov/...",
    "open_access": false
  }
]
```

Set `NCBI_API_KEY` environment variable to increase PubMed rate limits from
3 req/s to 10 req/s (register free at https://www.ncbi.nlm.nih.gov/account/).

---

## rh-skills ingest implement --url Reference

```sh
rh-skills ingest implement --url <url> --name <slug> [--type <mime>]
```

Exit codes:
- `0`: success — file downloaded to `sources/`, registered in `tracking.yaml`
- `1`: network or HTTP error
- `2`: file already exists (idempotent — treat as already downloaded)
- `3`: auth redirect detected — reclassify source as `access: authenticated`
