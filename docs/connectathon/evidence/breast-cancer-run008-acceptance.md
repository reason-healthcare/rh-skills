# Breast cancer run008: coded diagnostic Questionnaire

Date: 2026-09-20. Local implementation and synthetic-data validation; not clinical approval or a production deployment.

## Contract

- Every approved assessment produces a Questionnaire, including clinician-entered diagnostic results and review of existing results. Missing terminology blocks extraction readiness, not creation of the assessment.
- The generated breast-cancer Questionnaire has six required coded-choice items: ER, PR, HER2, clinical T, N and M. Question codes are reviewed LOINC 2.81. Answer codes are verified LOINC LA codes; no unverified answer version is invented.
- The supported SDC observation-extraction subset maps item codes to `Observation.code` and coded answers to `Observation.valueCodeableConcept`. Item clinical category overrides the form category: laboratory for receptors, exam for staging.
- Completed/all-required-answer gating preserves unknown for incomplete data. Clinical CQL consumes Observations, not QuestionnaireResponse identifiers.
- Subject, encounter, authored time, author/performer and QuestionnaireResponse derivation are preserved. Explicit host-supplied cancer focus is separate from standard SDC answer mapping; Workbench validates the selected Condition belongs to the patient. It does not infer a tumor from unrelated bundle content.
- Run007 is unchanged. Run008 is generated from its source workspace through the updated formalizer/package workflow.

## Implementation checks

- rh-skills generator/schema/command/skill checks: 527 passed, 18 skipped as reported by the implementation agent. Independent rerun of `PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_questionnaire.py`: 15 passed.
- All 24 skill distribution bundles validated in dry-run mode: zero warnings/errors.
- rh runtime: 12 extraction tests and 8 Node wrapper tests passed; clippy, formatting and documentation synchronization passed. Node WASM and TypeScript package rebuilt.
- Workbench: 25 focused tests, TypeScript checking and production build passed. Local production server on port 9090 restarted with that build.
- Broad checks are qualified: rh `just check` exits 0 but reports 23 R5 conformance failures, 99 unimplemented cases and registry timeout diagnostics from audit. Workbench full lint retains 39 pre-existing formatting errors; unrelated files were not reformatted.
- Whitespace checks passed in all three changed repositories. No commits or pushes were made.

## Terminology and FHIR validation

- Current-run requests and responses are retained in `breast-cancer-run008-terminology.json`, including exact ReasonHub question-code lookups and official LOINC answer-list references.
- Final Questionnaire SHA-256: `04f1450a23db40ff5a328d8ecaaa900e3759152c385db750a30dd8c8d0f1c4fc`.
- HL7 validator 6.10.2, FHIR R4 4.0.1, SDC 4.0.0: Questionnaire has zero errors, 30 warnings. Terminology server was disabled (`-tx n/a`), so this does not claim online terminology validation. Warnings cover unavailable terminology validation and missing narrative.
- Full validation logs and OperationOutcome are under `dist/connectathon-20260920/workspaces/breast-cancer-run008-20260920/evidence/questionnaire-fhir-validation/`.
- The actual reconciled `qr-tnbc-t1c-n0` clinical Bundle also has zero errors, with 52 warnings and two informational issues. These include unavailable terminology, absent narrative, the legacy tumor-size Observation's missing performer, the unloaded Questionnaire canonical, and relative-reference resolution warnings when transaction `urn:uuid` entries are reused in a collection Bundle. This is not a clean FHIR server round-trip claim; the reference-resolution warnings remain an existing reconciliation limitation.

## Reproduction and runtime evidence

- Builder: `docs/connectathon/tools/build-breast-cancer-run008.py`.
- Workspace: `dist/connectathon-20260920/workspaces/breast-cancer-run008-20260920/`.
- Native CQL and public Node SDC extraction evidence: workspace `evidence/runtime-run008/`.
- The original 13 Observation-based cases remain alongside 13 QuestionnaireResponse-based cases. The latter remove matching receptor/staging Observations, so pre-existing diagnostic values cannot mask an extraction failure. Synthetic Encounter and Practitioner resources explicitly support the new response provenance.

## Browser acceptance

- Verified the L2 assessment's Computable tab links to its directly-derived Questionnaire.
- In the rebuilt Workbench, selected `qr-tnbc-t2-n0`, clicked Populate, and rendered all six coded selectors. Unanswered required questions initially disabled completion.
- Explicitly entered Negative ER/PR/HER2, T2, N0 and M0. Validation displayed: "SDC Observation extraction produced 6 final Observations for this staged response." The validated response was staged for CPG/Measure preview.
- Repeated that workflow after the final production rebuild. Screenshot inspection at a 592-pixel viewport confirmed six readable selectors and wrapped coded-answer JSON without the earlier horizontal overflow. The completed Questionnaire tab was left open.
- The exact provisional snapshot `snap_connectathon-breast-cancer_run008-04f1450a23` was retained and relabeled `008 draft · Superseded validation build`; no snapshot artifacts were deleted. The accepted snapshot is `snap_connectathon-breast-cancer_run008-1053af6366`.
- Runtime verifier: `docs/connectathon/tools/verify-breast-cancer-run008.mjs`. All 26 scenarios, 208 native CQL assertions, and 26 public CPG guidance checks passed. Incomplete required responses produce zero Observations; complete valid responses produce six. No automatic medication regimen is executed by the guidance pathway.
- Matrix report: workspace `evidence/runtime-run008/acceptance.json` (SHA-256 `c5638fb17e6ce1d741c0dd5c34db1fb2dee3b424db2b6bb0b39edcf3d8075210`). The actual positive extraction, transaction, combined Bundle, QR-free clinical input, and CPG output are the `qr-tnbc-t2-n0-*` files in that directory.
- Final imported snapshot: `snap_connectathon-breast-cancer_run008-1053af6366`, 44 artifacts, six source documents, 34 executable resources and 26 fixtures. Its label is `008 · Coded diagnostic questionnaire`. The suffix hashes all source, L2, L3, package and fixture inputs, with the full inventory in workspace `evidence/snapshot-location.json`.
- Final ZIP SHA-256: `a56605d70f57be64ce24efb0979f0e5861d6901c77a0a5d6530358361e409f10`; manifest SHA-256: `e13dea133592293c44f33158bc7a65cc8c892564074c40777b5c2656ec0c5387`.
- Detailed artifact/version decisions, exact reproduction commands, fixture semantics and final paths are in [the snapshot report](breast-cancer-run008-snapshot.md).
