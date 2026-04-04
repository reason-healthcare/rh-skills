---
topic: "diabetes-ccm"
date: "2026-04-15"
sources:
  - name: "ADA Standards of Medical Care in Diabetes 2024"
    type: "guideline"
    rationale: >
      Authoritative annual clinical practice guidelines from the American Diabetes
      Association covering screening, diagnosis, glycemic targets, and management.
      Essential baseline for any diabetes CCM initiative.
    search_terms:
      - "ADA standards of care diabetes 2024"
      - "diabetes clinical practice guidelines"
    evidence_level: "grade-a"
    access: "open"
    url: "https://diabetesjournals.org/care/issue/47/Supplement_1"

  - name: "SNOMED CT — Diabetes Mellitus Hierarchy"
    type: "terminology"
    rationale: >
      SNOMED CT provides the clinical concept hierarchy for diabetes mellitus
      subtypes (T1D, T2D, gestational, secondary) needed for CDS logic and
      value set construction.
    search_terms:
      - "SNOMED diabetes mellitus"
      - "73211009 diabetes mellitus"
    evidence_level: "reference-standard"
    access: "open"
    url: "https://browser.ihtsdotools.org/?perspective=full&conceptId1=73211009"

  - name: "CMS eCQM — Diabetes: HbA1c Poor Control (CMS122)"
    type: "measure-library"
    rationale: >
      CMS eCQM for patients with diabetes with HbA1c > 9%. Referenced by MIPS
      QPP and HEDIS. Provides FHIR measure bundle and value sets needed for
      CCM program alignment.
    search_terms:
      - "CMS122 diabetes HbA1c"
      - "eCQM diabetes poor control"
    evidence_level: "n/a"
    access: "open"
    url: "https://ecqi.healthit.gov/ecqm/ec/2024/cms0122fhir"

  - name: "USPSTF — Prediabetes and Type 2 Diabetes Screening"
    type: "guideline"
    rationale: >
      USPSTF Grade B recommendation for screening adults aged 35–70 who are
      overweight or obese. Directly relevant for preventive CCM program design.
    search_terms:
      - "USPSTF diabetes screening 2021"
      - "prediabetes prevention grade B"
    evidence_level: "uspstf-b"
    access: "open"
    url: "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/prediabetes-and-type-2-diabetes-screening"

  - name: "Gravity SDOH FHIR IG — Food Insecurity & Diabetes"
    type: "fhir-ig"
    rationale: >
      Food insecurity is a documented driver of poor glycemic control. The Gravity
      FHIR IG defines the interoperability standards for capturing and exchanging
      SDOH data including food security assessments.
    search_terms:
      - "Gravity Project SDOH FHIR IG"
      - "food insecurity diabetes FHIR"
    evidence_level: "reference-standard"
    access: "open"
    url: "https://hl7.org/fhir/us/sdoh-clinicalcare/"

  - name: "HCUP — National Inpatient Sample: Diabetes Hospitalizations"
    type: "health-economics"
    rationale: >
      HCUP NIS provides population-level hospitalization cost data for diabetes
      complications. Essential for building the health economics case for CCM
      investment (preventable admissions, cost offsets).
    search_terms:
      - "HCUP diabetes hospitalization costs"
      - "diabetes preventable admissions NIS"
    evidence_level: "n/a"
    access: "open"
    url: "https://www.hcup-us.ahrq.gov/nisoverview.jsp"

  - name: "Cochrane Review — Intensive Glycemic Control T2D"
    type: "systematic-review"
    rationale: >
      Systematic review of intensive vs. standard glycemic control trials.
      Informs evidence-based target setting for CCM protocols and shared
      decision-making components.
    search_terms:
      - "Cochrane intensive glycemic control type 2 diabetes"
      - "HbA1c target cardiovascular outcomes"
    evidence_level: "grade-a"
    access: "authenticated"
    url: "https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD008143.pub2/full"
    auth_note: >
      Cochrane Library requires institutional access or purchase. Access via
      hospital or university library proxy. Search: 'intensive glycemic control
      type 2 diabetes cardiovascular'. Many institutions have Cochrane access
      through Wiley Online Library.
    recommended: true

  - name: "LOINC — Glucose and HbA1c Lab Codes"
    type: "terminology"
    rationale: >
      LOINC codes for HbA1c (4548-4) and fasting glucose (1558-6) are required
      for lab result extraction in CDS logic. LOINC is the standard for
      interoperable lab observations under US Core.
    search_terms:
      - "LOINC HbA1c 4548-4"
      - "LOINC glucose 1558-6"
    evidence_level: "reference-standard"
    access: "open"
    url: "https://loinc.org/4548-4/"

  - name: "Diabetes Care (ADA Journal) — CCM Articles"
    type: "pubmed-article"
    rationale: >
      Primary specialty journal for diabetes research. PubMed search yielded
      multiple RCTs on chronic care model effectiveness in T2D management,
      including pharmacist-led and team-based models.
    search_terms:
      - "chronic care model diabetes management effectiveness"
      - "team-based diabetes care glycemic outcomes"
    evidence_level: "grade-b"
    access: "authenticated"
    url: "https://diabetesjournals.org/care"
    auth_note: >
      Full-text access via institutional subscription. Access via library proxy.
      Use PubMed (free) for abstracts: hi search pubmed --query 'chronic care
      model diabetes effectiveness'. PMC has some open-access articles.
    recommended: true

  - name: "ICD-10-CM — Diabetes Mellitus Codes (E08–E13)"
    type: "terminology"
    rationale: >
      ICD-10-CM chapter E08–E13 covers all diabetes mellitus subtypes. Required
      for value set construction, claims-based cohort identification, and
      quality measure denominator logic.
    search_terms:
      - "ICD-10-CM E11 type 2 diabetes"
      - "ICD-10 diabetes mellitus codes E08 E13"
    evidence_level: "reference-standard"
    access: "open"
    url: "https://www.icd10data.com/ICD10CM/Codes/E00-E89/E08-E13"
---

## Domain Advice

### CMS Program Alignment

Diabetes mellitus (T2D) has one of the largest footprints in CMS quality
programs. Key alignment points for a CCM initiative:

- **eCQMs**: CMS122 (HbA1c Poor Control), CMS125 (Breast Cancer Screening, if
  population overlap), CMS130 (Colorectal Cancer Screening) — all commonly
  co-tracked in diabetes management. CMS122 is a MIPS mandatory outcome measure.
- **MIPS/QPP**: Diabetes is a MIPS Improvement Activity focus area. QPP
  measure 001 (Diabetes: HbA1c Poor Control) and measure 119 (Diabetes:
  Medical Attention for Nephropathy) are widely used.
- **CMMI models**: Comprehensive Primary Care Plus (CPC+), ACO Realizing Equity,
  Access, and Community Health (REACH) Model, and Kidney Care Choices (KCC)
  all include diabetes management components.
- **Chronic Care Management (CCM) codes**: CPT 99490/99491 and complex CCM
  codes (99487/99489) are CMS-billable for eligible beneficiaries with T2D.

### SDOH Relevance

Food insecurity and housing instability are the most evidence-backed SDOH
drivers of poor glycemic control. Relevant Gravity Project domains:

- **Food Insecurity** — most directly linked to HbA1c variation
- **Transportation Access** — barrier to medication adherence and appointments
- **Financial Strain** — insulin affordability, meter/supplies access
- **Housing Instability** — associated with hypoglycemia risk

Use the [Gravity SDOH FHIR IG](https://hl7.org/fhir/us/sdoh-clinicalcare/) for
interoperable SDOH data capture. PRAPARE and AHC HRSN Tool both screen for
diabetes-relevant SDOH domains.

### Health Equity

Documented disparities in T2D management:
- Higher prevalence and worse glycemic control in Black, Hispanic/Latino, and
  American Indian/Alaska Native populations
- Lower rates of statin co-prescription and nephropathy screening in minority
  populations despite higher CKD risk
- HEDIS stratification now required for race/ethnicity in many measures

Include at least one equity-focused search: `hi search pubmed --query
"diabetes disparities race ethnicity HbA1c" --max 10`.

### Quality Measure Landscape

Active diabetes quality measures (2024):
- CMS eCQM: CMS122, CMS134, CMS136 (adolescent), CMS149
- HEDIS: CDC (Comprehensive Diabetes Care) — HbA1c testing, control, retinal
  exam, nephropathy monitoring, BP control
- NQF #0059 (HbA1c control), #0061 (BP control), #0062 (LDL-C control)

### Terminology Systems

Required for this topic:
- **SNOMED CT**: disease concepts, procedure hierarchy
- **LOINC**: HbA1c (4548-4), fasting glucose (1558-6), urinary albumin-creatinine ratio
- **ICD-10-CM**: E08–E13 diabetes spectrum
- **RxNorm**: metformin (860975), insulin analogs, GLP-1 agonists, SGLT-2 inhibitors
- **UCUM**: percent (%) for HbA1c, mg/dL for glucose

### Health Economics

T2D has a documented economic burden of ~$327 billion annually in the US (ADA
2022 cost estimates). Key economic considerations for a CCM initiative:
- Average per-patient annual cost for T2D: $16,752 (vs. $6,153 without diabetes)
- Preventable hospitalizations (DKA, hypoglycemia, foot complications) represent
  significant avoidable cost
- CCM billing revenue offsets program costs for eligible practices
- HCUP NIS and MEPS provide population-level cost data for business case modeling

---

## Research Expansion Suggestions

1. **Diabetic Kidney Disease (DKD) Prevention** — T2D is the leading cause of
   end-stage renal disease. A CCM initiative should address nephropathy
   surveillance and early CKD intervention. Relevant eCQM: CMS134.
   Start with: `hi search pubmed --query "diabetic kidney disease prevention SGLT2 CKD" --max 15`

2. **Healthcare Economics of Medication Adherence** — Insulin and GLP-1 agonist
   adherence gaps drive hospitalizations. Cost-effectiveness of pharmacist-led
   adherence programs in T2D is well-studied.
   Start with: `hi search pubmed --query "diabetes medication adherence cost effectiveness pharmacist" --max 10`

3. **Health Equity: Diabetes Disparities in Underserved Populations** — FQHC and
   safety-net populations have disproportionate T2D burden. HRSA Uniform Data
   System (UDS) provides FQHC-specific quality benchmarks.
   Start with: `hi search pubmed --query "diabetes disparities racial ethnic minority FQHC" --max 10`

4. **Continuous Glucose Monitoring (CGM) Integration** — CGM data interoperability
   via FHIR is an emerging area. DARIO, Dexcom, and Abbott have SMART on FHIR apps.
   Coverage policy (CMS LCD) is evolving.
   Start with: `hi search clinicaltrials --query "continuous glucose monitoring type 2 diabetes outcomes" --max 10`

5. **Implementation Science: CCM Adoption Barriers** — Known barriers include
   care coordination workflow burden and EHR template limitations. Implementation
   frameworks (CFIR, RE-AIM) applied to diabetes CCM are published.
   Start with: `hi search pubmed --query "chronic care model implementation barriers primary care diabetes" --max 10`
