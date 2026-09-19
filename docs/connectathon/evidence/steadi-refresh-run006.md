# STEADI refresh run 006 evidence

Run date: 2026-09-19 UTC

## Scope and isolation

- rh-skills worktree: `/Users/bkaney/projects/reason-healthcare/rh-skills-steadi-refresh`
- branch: `codex/steadi-refresh-20260919`
- framework revision: `8e11422b10b2c533fc0ea89ab00648118a81bd12`
- latest fetched `origin/main`: `78d8a8c` (ancestor of the framework revision; zero commits behind)
- run workspace: `/Users/bkaney/projects/reason-healthcare/rh-skills-steadi-refresh/dist/connectathon-20260919/live-workspaces/run-006-steadi-refresh-20260919T181031Z`
- protected source repository: `/Users/bkaney/projects/reason-healthcare/hl7-agentic-knowledge-connectathon`
- protected source revision: `5034ccd6bc5971aa7e366b6b0df0b23caffe4f46` on `codex/breast-cancer-neoadjuvant-case`
- protected repository status before and after the run: clean

The accepted run-005 score authoring workspace was copied into the unique run-006 directory. The six clinical source snapshots and patient fixtures were refreshed from the current read-only `use-cases/steadi` tree. The six clinical source bytes are unchanged. The reorganized use-case README changed, so it was re-registered and normalized through `rh-skills ingest implement` and `rh-skills ingest normalize`. All eight registered sources passed `rh-skills ingest verify`.

The source fixtures still reference Questionnaire version `0.2.0`; the accepted score artifacts are version `0.3.0`. Only the isolated run copy was adapted: its fixture manifest and five QuestionnaireResponses now reference `0.3.0`. `evidence/input-provenance.json` records every adaptation. No prior run or protected source file was changed.

## Framework commands

The environment used Python 3.13.12 and the offline locked dependencies. The run-local curated skills were freshly installed and `rh-skills skills check` passed.

```sh
rh-skills ingest implement sources/connectathon-track-readme.md --topic steadi-live-replay
rh-skills ingest normalize sources/connectathon-track-readme.md --topic steadi-live-replay
rh-skills ingest verify steadi-live-replay

rh-skills validate steadi-live-replay l2 <each-of-seven-L2-artifacts>
rh-skills validate steadi-live-replay l3 <each-of-seven-authored-L3-groups>

rh-skills package steadi-live-replay --pack \
  --include-test-fixtures "$WS/tests/cql" \
  --fixture-library FallRiskScreeningRecommendationLogic \
  --workspace-dir "$WS/topics/steadi-live-replay/process/package-build-$RUN_ID"

rh-skills compose-executable steadi-live-replay \
  --root-canonical 'https://reason-healthcare.github.io/hl7-agentic-knowledge-connectathon/fhir/PlanDefinition/steadi-fall-risk-screening-protocol|0.3.0' \
  --fixture-manifest "$WS/test-bundles/manifest.json" \
  --fixture-dir "$WS/test-bundles/cases" \
  --evaluation-date '2026-06-15T09:20:00Z'
```

The package contains 25 FHIR resources, four CQL files, and six fixture examples. The executable closure contains 25 knowledge resources plus a six-case fixture index. All six generated patient Bundles have `Bundle.type = collection`, `HTEST`, the Workbench `test-case` tag, a deterministic `steadi-live-replay/<fixture-id>` identifier, and exactly one Patient matching the indexed subject.

The generic L3 validator has one retained tooling defect: validating either tracked external dependency record attempts to parse its `.cql` and ELM JSON files as FHIR resources. The seven authored L3 groups pass. Both external Library FHIR resources are included in the 25-resource official validation, which passes with zero errors. The diagnostic is retained in `evidence/validation.log`; it was not suppressed.

## Validation

- Seven of seven L2 artifact validations passed. Optional guidance warnings were retained.
- Seven of seven authored L3 group validations passed.
- Official HL7 validator 6.10.2 checked all 25 knowledge resources with FHIR R4 4.0.1, SDC 4.0.0, CPG 2.0.0, and offline terminology. Result: zero errors, 71 warnings, 18 informational messages.
- Score contract: six source fixtures and 22 alternate Observation-producer cases passed against native CQL and the public Node/WASM runtime.
- Runtime matrix: 60 PlanDefinition `$apply` calls and six Measure evaluations passed.
- Deterministic composition: executable Bundle, fixture index, and all six generated fixture Bundles were byte-identical across two output directories.
- Current fixture-composer unit suite: 23 passed.
- Current Workbench importer validation passed for both the snapshot directory and ZIP.
- Workbench database import passed: one published snapshot, 36 artifact versions, and six tagged executable fixtures.

## Deliverables and hashes

- snapshot directory: `/Users/bkaney/projects/reason-healthcare/rh-skills-steadi-refresh/dist/connectathon-20260919/snapshots/connectathon-steadi-scores-run006-e05c9760c1c9-snapshot`
- snapshot ZIP: `/Users/bkaney/projects/reason-healthcare/rh-skills-steadi-refresh/dist/connectathon-20260919/snapshots/connectathon-steadi-scores-run006-e05c9760c1c9-snapshot.zip`
- Workbench snapshot ID: `snap_connectathon-steadi-scores_run006-e05c9760c1c9`
- snapshot manifest SHA-256: `a78fd9f8246d16ee2fd6deb6440fba3b71a9ef0657a0e58443212c861985a3f0`
- snapshot ZIP SHA-256: `cd7062364c19200acd0867b51bf23dd98d193217627cfa2efc82b7b198c523a5`
- executable Bundle SHA-256: `e05c9760c1c900c672ad9345699004ac8ba52f14c362f6095429a196ad502e60`
- fixture index SHA-256: `c3239ac23c98f9ae9f555b82e4d8a40d9fd5f7d1b4bf7f458d8b3d8a831b1edc`
- FHIR package SHA-256: `1cd9cfd04bbd81d03efdac76155713d9bba0ea725d6755e72ab34b47926297e4`
- runtime Node wrapper SHA-256: `478033b2ddbcab71dd648a59ccd25c07484113c2ccca381ef200fd3e8027f00b`
- runtime WASM SHA-256: `4e15b12fb3dacf0ebab7965a370866cabd26db2d0959286c6a91d4ab337dde5c`
- native RH CLI SHA-256: `937a0948187f0df83d73a1afd17674409aa10a6461b4123d835bed49b7a2bc82`

Run-local machine-readable evidence is under the workspace `evidence/` directory, including source integrity, input adaptations, official FHIR results, score/runtime matrices, deterministic composition, Workbench importer validation, and database import verification.
