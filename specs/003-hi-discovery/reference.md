# `hi-discovery` Reference: Medical Sources Taxonomy

This document is the Level 3 companion to the `hi-discovery` SKILL.md. It defines the source landscape the agent draws from when producing a discovery plan.

---

## Core Access Strategy

Virtually all peer-reviewed medical journals are indexed in **PubMed/MEDLINE** (the NLM database). The agent does not need to know individual journal URLs — it searches PubMed and lets MEDLINE's indexing surface the right journals by specialty, publication type, and evidence level.

Access falls into three tiers:

| Tier | What it means | `hi` action |
|------|--------------|-------------|
| **Open access** | Full text freely available (PMC, BioMed Central, PLoS, many society journals) | `hi ingest implement --url <pdf-url>` |
| **Authenticated** | Requires login but is freely accessible with registration or institutional access — the agent MUST recommend these with specific access instructions | Mark `access: authenticated` + `auth_note`; agent prints advisory |
| **Subscription** | Requires institutional/paid subscription; abstract via PubMed only | Mark `access: authenticated`; advisory notes institutional proxy |
| **Society portal** | PDF available from the society website (often free after free registration) | `hi ingest implement --url <pdf-url>` if direct link; else `access: authenticated` |

---

## PubMed Search Strategy

### Publication type filters (PubMed `[pt]` field)

Use these to focus on high-value source types:

| Goal | PubMed filter |
|------|--------------|
| Clinical practice guidelines | `"guideline"[pt]` or `"practice guideline"[pt]` |
| Systematic reviews | `"systematic review"[pt]` |
| Meta-analyses | `"meta-analysis"[pt]` |
| Randomized controlled trials | `"randomized controlled trial"[pt]` |
| Review articles | `"review"[pt]` |
| Clinical trials | `"clinical trial"[pt]` |

### Open-access filter

`"open access"[Filter]` or use PMC search (`hi search pmc`) for full-text downloadable articles.

### Date recency

Add `("last 5 years"[PDat])` or `("last 10 years"[PDat])` to prioritize current evidence.

### Example composite query

```
diabetes screening guidelines 2019:2024[pdat] AND ("guideline"[pt] OR "systematic review"[pt] OR "meta-analysis"[pt])
```

---

## High-Priority Source Categories for HI

### Tier 1 — Authoritative guidelines (always search for these)

| Source | Publisher | Access | Notes |
|--------|-----------|--------|-------|
| USPSTF Recommendations | US Preventive Services Task Force | Open | Search PubMed: `"United States Preventive Services Task Force"[Corporate Author]` |
| NICE Guidelines | National Institute for Health and Care Excellence | Open | Download from nice.org.uk |
| WHO Guidelines | World Health Organization | Open | who.int/publications |
| CDC MMWR | Centers for Disease Control | Open | cdc.gov/mmwr |
| Agency for Healthcare Research and Quality (AHRQ) | HHS | Open | ahrq.gov |

### Tier 2 — Major medical society guidelines

| Society | Key journals | PubMed filter |
|---------|-------------|---------------|
| American Diabetes Association (ADA) | *Diabetes Care*, *Diabetes* | `"American Diabetes Association"[Corporate Author]` |
| ACC / AHA | *JACC*, *Circulation* | `"American College of Cardiology"[Corporate Author]` |
| American College of Physicians | *Annals of Internal Medicine* | `"American College of Physicians"[Corporate Author]` |
| American Academy of Family Physicians | *American Family Physician* | `"American Academy of Family Physicians"[Corporate Author]` |
| American Thoracic Society | *AJRCCM* | `"American Thoracic Society"[Corporate Author]` |
| American Society of Hematology | *Blood* | `"American Society of Hematology"[Corporate Author]` |
| Infectious Disease Society of America | *CID*, *Open Forum ID* | `"Infectious Diseases Society of America"[Corporate Author]` |
| American College of Obstetricians | *Obstetrics & Gynecology* | `"American College of Obstetricians and Gynecologists"[Corporate Author]` |
| American Academy of Pediatrics | *Pediatrics* | `"American Academy of Pediatrics"[Corporate Author]` |

### Tier 3 — High-impact general medical journals (all in PubMed)

These are searched naturally via PubMed queries; no special filter needed.

| Journal | Publisher | Open access |
|---------|-----------|-------------|
| *New England Journal of Medicine* (NEJM) | NEJM Group | Subscription (some open) |
| *The Lancet* | Elsevier | Subscription (some open) |
| *JAMA* | AMA | Subscription (some open) |
| *BMJ* | BMJ Group | Mixed (many open) |
| *Annals of Internal Medicine* | ACP | Subscription |
| *PLOS Medicine* | PLoS | ✅ Fully open |
| *BMC Medicine* | BioMed Central | ✅ Fully open |

### Tier 4 — Health informatics-specific journals

Especially relevant for informatics framing, FHIR alignment, and CDS:

| Journal | Focus | Open access |
|---------|-------|-------------|
| *JAMIA* (J American Medical Informatics Assoc) | Clinical informatics | Mixed |
| *Journal of Biomedical Informatics* | Biomedical informatics | Subscription |
| *Applied Clinical Informatics* | Clinical informatics | Subscription |
| *npj Digital Medicine* | Digital health | ✅ Open |
| *AMIA Annual Symposium Proceedings* | Informatics | PMC |

---

## Terminology & Computable Sources

These are always required for L3 artifacts. The agent MUST include at least one.

| Source | What it provides | Access |
|--------|-----------------|--------|
| SNOMED CT | Clinical concept hierarchy, procedure/finding codes | Licensed (free via NLM UMLS) |
| LOINC | Lab and clinical observation codes | Free at loinc.org |
| ICD-10-CM | Diagnosis codes (US billing) | Free at cms.gov |
| ICD-11 | WHO international disease classification | Free at who.int |
| RxNorm | Drug naming standards | Free via NLM API |
| UCUM | Units of measure | Free at unitsofmeasure.org |
| VSAC (NLM) | Value set repository | Free with UMLS license |

---

## Measure Libraries

Search these when the topic has an existing quality measure:

| Library | What it contains | URL |
|---------|-----------------|-----|
| CMS eCQM Library | CMS electronic clinical quality measures | ecqi.healthit.gov |
| HEDIS | NCQA health plan quality measures | ncqa.org (subscription) |
| CMS Physician Quality Reporting | MIPS / QPP measures | qpp.cms.gov |
| Joint Commission | Hospital accreditation measures | jointcommission.org |

---

## FHIR Implementation Guides

When the topic targets FHIR-computable output:

| IG | Purpose | URL |
|----|---------|-----|
| US Core | Baseline US FHIR profiles | hl7.org/fhir/us/core |
| QI-Core | Quality improvement profiles (extends US Core) | hl7.org/fhir/us/qicore |
| CARIN Blue Button | Consumer claims data | hl7.org/fhir/us/carin-bb |
| Da Vinci | Payer-provider interoperability | hl7.org/fhir/us/davinci-* |
| SMART on FHIR | App authorization | hl7.org/fhir/smart-app-launch |

---

## ClinicalTrials.gov Search Strategy

Use `hi search clinicaltrials` for:
- Identifying active/completed trials that inform evidence gaps
- Finding intervention arms that map to L2 clinical criteria
- Understanding population characteristics (inclusion/exclusion criteria)

Key filters:
- `--status recruiting|completed|active` — focus on completed for evidence
- Use condition MeSH terms as query terms for precision

---

## Authenticated Source Advisories

When a source requires authentication, the agent MUST recommend it if it is authoritative for the topic and produce an advisory with these fields. Access difficulty never reduces a source's recommendation priority.

### Advisory format

```
📚 Recommended authenticated source: <Name>
   Why relevant: <one sentence specific to the topic>
   URL: <direct URL>
   Access: <method>
   Search terms to use: <topic-specific terms>
```

### Key authenticated sources by category

| Source | URL | Access method | Best for |
|--------|-----|--------------|----------|
| **Cochrane Library** | cochranelibrary.com | Free personal registration OR institutional login | Systematic reviews, meta-analyses |
| **NEJM** | nejm.org | Institutional login (some free with registration) | High-impact RCTs, landmark trials |
| **JAMA Network** | jamanetwork.com | Free personal account for some content; institutional for full | Clinical guidelines, major trials |
| **The Lancet** | thelancet.com | Institutional login; some open-access articles | Global health, major trials |
| **Annals of Internal Medicine** | annals.org | ACP membership or institutional | US internal medicine guidelines |
| **NICE Guidance** | nice.org.uk/guidance | Free, no login required (UK focus) | Clinical guidelines, technology appraisals |
| **UpToDate** | uptodate.com | Institutional subscription | Clinical decision support summaries |
| **EMBASE** | embase.com | Institutional subscription | European literature, pharmacology |
| **CINAHL** | ebscohost.com/nursing/products/cinahl | Institutional subscription | Nursing, allied health |
| **PsycINFO** | apa.org/pyscinfo | Institutional subscription | Mental health, behavioral medicine |
| **HEDIS Measures** | ncqa.org | NCQA membership / purchase | Quality measures by plan type |

### Authentication methods — standard language for advisories

Use these exact phrases in `auth_note` fields for consistency:

| Method | `auth_note` value |
|--------|------------------|
| Free personal registration | `"Free account at <url> — register with email, no institutional affiliation required"` |
| Institutional login | `"Requires institutional access — use your organization's library proxy or VPN"` |
| Society membership | `"Requires <Society> membership — check if your institution has a group subscription"` |
| Library proxy | `"Access via your institution's library database portal (e.g., EZproxy)"` |
| Open with UMLS license | `"Free with NLM UMLS license — register at uts.nlm.nih.gov (approved in ~1 business day)"` |

---

## Domain Advice Checklist (for SKILL.md reasoning)

When the agent produces a discovery plan, it MUST advise on:

1. **Diagnostic criteria** — what defines the condition? (ICD codes, clinical thresholds, lab values)
2. **Population scope** — age, sex, comorbidity, risk stratification
3. **Intervention landscape** — screening intervals, treatment thresholds, first-line vs. second-line
4. **Contraindications and exceptions** — when NOT to apply the guideline
5. **Evidence gaps** — areas where guidelines differ or evidence is sparse
6. **Existing measures** — are there eCQMs or HEDIS measures already? How does this topic relate?
7. **Coding landscape** — which terminology systems are authoritative for this domain?
8. **FHIR alignment** — are there existing implementation guides or profiles?
9. **Regulatory context** — CMS coverage, FDA approvals, USPSTF grade
10. **Recency** — when were the current guidelines last updated? Are updates pending?
