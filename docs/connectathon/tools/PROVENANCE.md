# Durable acceptance tools

The current score-based candidate uses the run005 tools described below.
The older commands are retained to reproduce their frozen baselines.

## Historical run003/run004 Observation workflow

The run003/run004 workflow is QuestionnaireResponse → actual SDC
extraction → Observations → versioned ValueSet CQL. The run003 package is a
frozen accepted baseline. Run004 is the declared idiomatic-CQL revision, with
Patient-context isolation and pinned FHIRCommon reference relationships; its
final acceptance is recorded in the journal and readiness manifest.

`run-run003-observation-acceptance.py` is the historical local entrypoint for this
Observation contract. Its historical filename is retained; supply the exact
candidate workspace/content paths and a new output directory for every replay.
The command verifies:

- 48 unchanged decision assertions and 18 Measure population assertions through
  normal source-based `rh-skills cql test`.
- Actual public Node/WASM SDC extraction against the frozen generated-Questionnaire
  capture, separate from expected-output fixtures.
- Observation/terminology adverse cases, including wrong patient/encounter,
  partial or duplicate results, and unresolved or wrong-version ValueSets.
- Public Node/WASM PlanDefinition and individual Measure results using QR-free
  clinical data prepared from actual extraction output.

The generated Questionnaire must match the extraction capture's input hash
before reusing that capture. A changed Questionnaire needs a new native
extraction capture and derived clinical-data manifest; never silently relabel
an older capture as output of a new input. Package, native runtime, public
module and WASM binary identities must accompany the results.

Example (use the final accepted candidate paths from the readiness manifest):

```sh
python3 docs/connectathon/tools/run-run003-observation-acceptance.py \
  --run-id run004 \
  --oracle-root dist/connectathon-20260919/workspaces/run-004/oracle/test-bundles \
  --workspace dist/connectathon-20260919/workspaces/run-004 \
  --content dist/connectathon-20260919/workspaces/run-004/topics/steadi-live-replay/process/package-workspace/executable/executable-bundle.json \
  --runtime-root /Users/bkaney/projects/reason-healthcare/rh \
  --runtime /Users/bkaney/projects/reason-healthcare/rh/packages/cpg/dist/node.js \
  --terminology-root dist/connectathon-20260919/terminology-cql-replay \
  --prepared-root dist/connectathon-20260919/terminology-cql-replay/evidence/actual-generated-v2-qr-free-data \
  --extraction-capture dist/connectathon-20260919/verification/root-sdc-generated-native-v2 \
  --rh-skills-bin "$PWD/.venv/bin/rh-skills" \
  --output dist/connectathon-20260919/verification/operator-run004
```

## Run005 score Observation acceptance

Run005 is a declared revision of the frozen run004 workspace. Its raw response
fixtures are adapted to the new Questionnaire version; the original 66 clinical
expectations remain unchanged. The following tools are authored in this branch
and do not modify source fixtures or the protected Connectathon repository:

- `verify-run005-score-contract.mjs` performs actual public Node/WASM extraction,
  writes QR-free prepared data, and checks 22 explicitly expected alternate-source
  score cases through both native CQL libraries and public Node Measure/CPG.
  It binds every alternate input by SHA-256. Input Coding.version remains
  provenance; immutable system/code identifies the algorithm.
- `verify-run005-observation-node.mjs` checks the original 60 PlanDefinition
  applications and six MeasureReports using that hash-bound prepared data.
- `verify-run005-score-apps.mjs` replays the same 22 score-only inputs through
  Workbench Measure, Workbench CPG, and standalone CPG. It requires the accepted
  core report, package hash, snapshot manifest and artifact identity/checksums.
  A separate coordinator check compares all snapshot L3 resources with the
  candidate Bundle before import evidence is accepted.
- `verify-run003-workbench-api.mjs` and
  `verify-run003-standalone-raw-qr.mjs` remain usable with explicit run005 paths
  and versioned canonicals. They exercise the actual raw-response preparation
  path. The older generic vendor Workbench verifier does not prepare SDC
  Observations and must not be used for these revised packages.
- `run-run005-fhir-validation.py` invokes the pinned official validator for
  knowledge resources, actual extraction transactions/clinical Bundles, or
  actual runtime outputs. It records raw diagnostics and does not suppress or
  automatically accept the known zero-denominator MeasureReport diagnostic.

Reference CQFramework translation, application builds, fresh skill installation,
and browser interaction are separate evidence. Translation is not claimed as
execution by an independent CQL engine. Run001–004 evidence remains frozen.

Service checks are separate: `verify-run003-workbench-api.mjs` sends raw
QuestionnaireResponse inputs to every imported preview endpoint; configure the
exact project/snapshot/artifact identities after importing the final package.
`verify-run003-standalone-raw-qr.mjs` exercises standalone extraction and CPG
application. Set the Workbench cookie only in the environment, never in a
committed config or report. Both require the final running service and runtime.

Use the raw-response Workbench verifier for run003/run004. The older generic
`vendor/verify-workbench-api-matrix.mjs` does not prepare extracted Observations for its
direct comparison and is only appropriate to its historical QR-reading
contract; using it for run004 produced a rejected 53/72 comparison. Do not
replace extraction output with the expected fixture oracle to make it pass.

```sh
REPO_ROOT=/Users/bkaney/projects/reason-healthcare \
WORKBENCH_BASE_URL=http://127.0.0.1:9090 \
node docs/connectathon/tools/verify-run003-workbench-api.mjs \
  --config docs/connectathon/tools/runs/run004-observation-workbench.json \
  --output dist/connectathon-20260919/verification/operator-run004-workbench

node docs/connectathon/tools/verify-run003-standalone-raw-qr.mjs \
  --run-id run004 \
  --content dist/connectathon-20260919/workspaces/run-004/topics/steadi-live-replay/process/package-workspace/executable/executable-bundle.json \
  --runtime /Users/bkaney/projects/reason-healthcare/rh/packages/cpg/dist/node.js \
  --fixtures dist/connectathon-20260919/workspaces/run-004/topics/steadi-live-replay/process/package-workspace/executable/fixtures/index.json \
  --assertion-root dist/connectathon-20260919/workspaces/run-004/oracle/test-bundles/cases \
  --standalone http://127.0.0.1:9091 \
  --output dist/connectathon-20260919/verification/operator-run004-standalone
```

`verify-patient-context-fhircommon-node.mjs` independently tests the official
reference-translated helper through the public WASM module. It includes
wrong-patient-only and wrong-encounter-only data; a positive Measure membership
count by itself cannot prove that a result list excluded unrelated resources.

Official FHIR validation, reference CQL translation, browser assessment staging
and restore, source visibility, narrow layouts, and source-repository integrity
have separate evidence. API parity uses the same RH engine and is not a second
independent CQL implementation. None of these additional gates is inferred from
local acceptance success.

## Historical QuestionnaireResponse-reading replays

`run-durable-acceptance.py` is the entrypoint for the frozen run001/run002 contracts. It invokes
the configured `rh-skills cql test` matrices and the current public Node/WASM
package verifier. The native tool is pinned to `--runtime-root/target/debug/rh`;
it does not silently use a PATH binary. Its report binds the durable executable bundle, fixture index, runtime
module, commands, and exit statuses by SHA-256.

The `runs/` configurations keep the two demonstration contracts distinct. Use a
fresh local skill installation such as `"$PWD/.venv/bin/rh-skills"`; do not use
the historical `/private/tmp` virtual environment in a replay.


- `run001.json` expects a coded `CommunicationRequest` guidance output.
- `run002.json` expects informational `RequestGroup.note[]` guidance. It is
  never inferred from package text.

The native matrices are 30 decision assertions plus 18 Measure assertions. The
public Node/WASM verifier reads the immutable six-case oracle supplied by
`--oracle-root`, executes every emitted PlanDefinition and the Measure, and
requires 53 run-001 or 71 run-002 semantic checks: populations, score/period,
individual report shape, action XOR/link closure, intent, subject/encounter,
Questionnaire validity, and the explicit guidance contract. The native 48-case
oracle stays in each durable workspace under `tests/cql/`.

`vendor/` contains copies of the existing service/evidence verifiers from
`/private/tmp/connectathon-live/evidence/`, copied on 2026-09-18. The
standalone verifier has one documented durable adaptation: an explicit
`informational-guidance-notes` contract that checks configured positive action
IDs in `RequestGroup.note[]`, while allowing other informational notes; it
never derives expectations from package text. They
remain separate because authenticated Workbench and standalone calls require
running services and, for Workbench, an ephemeral cookie. `runs/run001-workbench.json`
and `runs/run002-workbench.json` contain only durable project/snapshot/artifact
identities; the entrypoint supplies all filesystem paths and the service URL. Browser, manual,
official FHIR-validator, SDC, and second-engine evidence must retain their own
attachments and are reported as `not_run` or `unsupported`, never as a pass.

Example required-core replay:

```sh
python3 docs/connectathon/tools/run-durable-acceptance.py \
  --config docs/connectathon/tools/runs/run002.json \
  --repo-root "$PWD" \
  --runtime-root /path/to/rh \
  --rh-skills-bin "$PWD/.venv/bin/rh-skills" \
  --oracle-root /path/to/test-bundles \
  --output /path/to/evidence/run002
```

Optional service replays use the same entrypoint. This example does not write the
cookie to config or output; it reads the named environment variable only for the
child verifier:

```sh
WORKBENCH_COOKIE='session=…' python3 docs/connectathon/tools/run-durable-acceptance.py \
  --config docs/connectathon/tools/runs/run002.json \
  --repo-root "$PWD" --runtime-root /path/to/rh \
  --rh-skills-bin "$PWD/.venv/bin/rh-skills" \
  --oracle-root /path/to/test-bundles \
  --with-standalone http://127.0.0.1:9091 \
  --with-workbench http://127.0.0.1:9090 \
  --workbench-config docs/connectathon/tools/runs/run002-workbench.json \
  --output /path/to/evidence/run002
```
