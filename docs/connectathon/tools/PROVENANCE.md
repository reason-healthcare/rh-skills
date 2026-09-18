# Durable acceptance tools

`run-durable-acceptance.py` is the only required-core entrypoint. It invokes
the configured `rh-skills cql test` matrices and the current public Node/WASM
package verifier. The native tool is pinned to `--runtime-root/target/debug/rh`;
it does not silently use a PATH binary. Its report binds the durable executable bundle, fixture index, runtime
module, commands, and exit statuses by SHA-256.

The `runs/` configurations keep the two demonstration contracts distinct:

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
  --rh-skills-bin /path/to/rh-skills \
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
  --rh-skills-bin /path/to/rh-skills \
  --oracle-root /path/to/test-bundles \
  --with-standalone http://127.0.0.1:9091 \
  --with-workbench http://127.0.0.1:9090 \
  --workbench-config docs/connectathon/tools/runs/run002-workbench.json \
  --output /path/to/evidence/run002
```
