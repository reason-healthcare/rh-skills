# Breast cancer run007 correction evidence

Date: 2026-09-19

## Finding

The prior run006 did not use ReasonHub MCP for terminology discovery. Its generation session made zero `mcp__reasonhub` calls and promoted source-supplied local and LOINC codes. An earlier source-authoring session used exact CodeSystem lookup for eight already-selected LOINC codes, but it did not discover SNOMED CT or RxNorm concepts for invasive breast cancer, triple-negative breast cancer, staging, or the named regimen medications. Run006 also did not contain a chemotherapy order-set PlanDefinition or medication ActivityDefinitions.

The exact session paths, findings, ReasonHub MCP requests, and full responses are preserved in [breast-cancer-run007-reasonhub.json](breast-cancer-run007-reasonhub.json). Its repository-formatted SHA-256 is `1b6d64f6ca11bd6c1af7831d47688bce9d8ebf25656228ac38b7af21b1f7d9df`; the semantically identical run-workspace copy has SHA-256 `9c60dac39fdb7ca609e33cf75c2f400d9653a18f29ea861d51b8510b6f1c3cca`.

## Current-run terminology evidence

Run007 called ReasonHub MCP for version discovery, text search, exact code lookup, and reusable knowledge-artifact search. The selected standardized concepts are:

| Purpose | System and version | Code | Display |
| --- | --- | --- | --- |
| Invasive breast cancer | SNOMED CT US `20250901` | `713609000` | Invasive carcinoma of breast |
| Triple-negative breast cancer | SNOMED CT US `20250901` | `706970001` | Triple-negative breast cancer |
| Estrogen receptor status | LOINC `2.81` | `85337-4` | Estrogen receptor Ag [Presence] in Breast cancer specimen by Immune stain |
| Progesterone receptor status | LOINC `2.81` | `85339-0` | Progesterone receptor Ag [Presence] in Breast cancer specimen by Immune stain |
| HER2 status | LOINC `2.81` | `48676-1` | HER2 [Interpretation] in Tissue |
| Tumor size | LOINC `2.81` | `21889-1` | Size Tumor |
| Pembrolizumab | RxNorm `01052026` | `1547545` | Product containing pembrolizumab (medicinal product) |
| Paclitaxel | RxNorm `01052026` | `56946` | Paclitaxel |
| Carboplatin | RxNorm `01052026` | `40048` | Carboplatin |
| Doxorubicin | RxNorm `01052026` | `3639` | Doxorubicin |
| Cyclophosphamide | RxNorm `01052026` | `3002` | Cyclophosphamide |

ReasonHub knowledge searches returned no reusable KEYNOTE-522 PlanDefinition or ActivityDefinition. Run007 therefore authors a local draft rather than claiming reuse of an existing canonical artifact. Fixture-only staging codes remain clearly labeled as local test data.

## Regimen order set

The isolated run007 workspace is `/Users/bkaney/projects/reason-healthcare/rh-skills-breast-cancer-run007/dist/connectathon-20260919/workspaces/breast-cancer-run007-20260919T201338Z`.

It adds the L2 `KEYNOTE-522 evidence regimen review` decision table and these L3 resources:

- one draft, experimental order-set PlanDefinition: `PlanDefinition-keynote-522-regimen-review-order-set.json`
- six proposal-only MedicationRequest ActivityDefinitions for paclitaxel, carboplatin, doxorubicin, cyclophosphamide, neoadjuvant pembrolizumab, and adjuvant pembrolizumab
- standardized SNOMED CT ValueSets for invasive breast cancer and triple-negative breast cancer

The order set preserves the source-supported sequence: paclitaxel plus carboplatin, then doxorubicin plus cyclophosphamide, with neoadjuvant and post-surgery pembrolizumab. The source does not establish exact dose, route, frequency, cycle count, supportive medications, or a complete treatment-specific eligibility contract, so run007 does not invent them. It remains a clinician-initiated proposal and is not automatically executed by the broad guidance pathway.

## Verification

- Skill hardening commit: `8a5c97c6bd987d0f9cbd0d10ccde6511bd05b6dd`.
- Skill tests: 302 passed, 18 skipped.
- Distribution dry run: 24 bundles built with zero warnings or errors.
- Static regimen acceptance: one order set, six proposal activities, and the source boundary passed.
- Official FHIR validation: all 33 authored FHIR resources passed with zero issues.
- Direct order-set `$apply`: HTTP 200; one RequestGroup and six RxNorm-coded MedicationRequests; no dosage instructions.
- Baseline guidance `$apply`: zero MedicationRequests, confirming that the order set is not auto-executed.
- Workbench import: `snap_connectathon-breast-cancer_run007-5034ccd-d734874`, with 7 L2 artifacts, 36 L3 artifacts, 6 source documents, and 13 patient test cases.
- Live Workbench acceptance with `tnbc-t2-n0`: HTTP 200; 7 generated resources, including all 6 MedicationRequests; the readable RequestGroup and complete response JSON modal both rendered without browser errors or warnings.
- The superseded breast-cancer run006 snapshot was removed after acceptance. The database now contains exactly STEADI run006 and breast-cancer run007.
- The protected `hl7-agentic-knowledge-connectathon` checkout remains clean at `5034ccd6bc5971aa7e366b6b0df0b23caffe4f46`; it was not modified.

The Workbench snapshot is live at [Breast cancer run007](http://localhost:9090/projects/connectathon-breast-cancer/snapshots/snap_connectathon-breast-cancer_run007-5034ccd-d734874). The chemotherapy order set opens at [KEYNOTE-522 order set preview](http://localhost:9090/projects/connectathon-breast-cancer/snapshots/snap_connectathon-breast-cancer_run007-5034ccd-d734874/artifacts/connectathon-breast-cancer--plandefinition-keynote-522-regimen-review-order-set/preview/cpg?fixture=tnbc-t2-n0).
