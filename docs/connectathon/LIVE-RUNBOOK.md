# Saturday live authoring runbook

This runbook is for a fresh STEADI source-to-preview session on September 19,
2026. The Saturday authoring procedure starts from shared source snapshots and
synthetic fixtures; run-004 below is a targeted technical revision used to
validate the Observation/CQL contract, not an input to fresh L2 authoring or an
independent timing sample. Check the [24-hour plan](../CONNECTATHON-24H-PLAN.md),
[journal](../CONNECTATHON-JOURNAL.md), and
[status ledger](../connectathon-24h-status.json) before starting. Those files
are the current source of truth for open gates and exact application commands.

The output is for a technical Connectathon demonstration. The seven L2
artifacts have automated technical review only; clinical review remains
pending. The measure is a track-authored screening-completion process measure,
not an implementation or equivalent of CMS139FHIR. The rehearsed mode used
agent-authored L2/CQL with `LLM_PROVIDER=stub` for deterministic L3 templates;
it does not establish provider-backed L3 generation. Record any different
provider/model used live and keep it distinct from these rehearsal results.

Run-003 first demonstrated the supported Boolean SDC extraction subset.
Run-004 is a targeted revision of that workspace and the run-002 authoring
replay, not an independent authoring or timing sample. It demonstrates the
same bounded workflow with the current Patient-context and encounter-join
contracts: the generated Questionnaire declares the SDC extraction profile
and explicit version algorithm, the native RH extractor produces coded
Observations from completed responses, and generated CQL retrieves those
Observations through pinned question ValueSets. This does not establish full
SDC extraction interoperability or two-server conformance; keep those broader
track gates separate.

Post-run review found that run-003's frozen CQL compares each retrieved
resource's subject reference to `Patient.id`, masking an engine Patient-context
scoping defect. Keep the accepted run-003 package and evidence unchanged. The
isolated run-004 candidate is a targeted revision, not new independent
authoring or timing: it removes those redundant subject predicates, uses the
typed `[Encounter: class ~ "Ambulatory"]` filter instead of splitting the
Coding system/code into strings, and joins Observations to the selected
Encounter with the pinned `FHIRCommon.references()` function. It retains the
encounter date, status, selected-encounter and QuestionnaireResponse
provenance rules and all 66 expected assertions. Normal RH CLI validation,
translation, and 48 decision plus 18 Measure assertions pass against QR-free
inputs derived from a fresh native extraction capture. The frozen executable
knowledge Bundle contains 23 resources, with six separate fixture Bundles in
its fixture sidecar; official FHIR validation reports zero errors and zero
unresolved references, plus 66 warnings and 14 information messages under
offline terminology validation. Runtime-output validation has one narrowly
documented zero-denominator `MEASURE_MR_SCORE_REQUIRED` validator error
(`strictValidatorPassed: false`); it is accepted only under the exact
exception described in section 6. Final Workbench API validation passes 72/72
checks and standalone raw-QR parity/semantics passes 6/6. Both actual browser
flows pass: Workbench extracts/stages Observations and updates Measure/CPG;
standalone loads a separate raw patient Bundle and returns positive or unknown
guidance. Workbench also decodes Library CQL/ELM for inspection. These are local
technical rehearsal results, not clinical approval or full Connectathon
interoperability completion.

## What the scenario means

The scenario is a community-dwelling adult age 65 or older in ambulatory care.
Community dwelling is supplied as a scenario precondition, not inferred from
FHIR encounter data. Age is evaluated on the qualifying encounter date. The
fixed encounter/evaluation clock used by the synthetic fixture contract is
`2026-06-15T09:20:00Z`; its measurement period is January 1 through December
31, 2026, inclusive.

The response is complete only when its status is `completed`, it references
the exact versioned three-question Questionnaire, and all three expected
linkIds have usable Boolean answers. The SDC extraction step applies that
contract and emits one final Boolean Observation per coded item; Observation
CQL then checks exact ValueSet membership, the Patient-context-selected
qualifying encounter, and common QuestionnaireResponse provenance. Patient
context filtering depends on the pinned FHIR ModelInfo and evaluator. Do not
add manual subject-reference predicates to mask a runtime context leak; test
with a mixed-patient Bundle and treat leakage as an execution blocker. It does
not read `QuestionnaireResponse.item` to discover terminology because FHIR R4 has no
item-level code there. A completed screen is increased risk when any extracted
answer is true and not increased risk when all are false. Missing, incomplete,
wrong-version, or unusable responses do not produce usable extraction results;
risk remains unknown, completion is false, and the measure numerator is false.
Completion is not gated by age, so the younger complete fixture can still
demonstrate assessment completion while remaining outside the screening
population. Retain the shared fixture's exact measurement-period JSON,
including both inclusive boundaries.

## 1. Pin the workspace and tools

Use a unique workspace for this run. Never point the CLI at the protected
Connectathon repository or at another rehearsal's topic. The source repository
is read-only, including its Git state.

```sh
set -euo pipefail

export SKILLS_REPO=/Users/bkaney/projects/reason-healthcare/rh-skills
export RH_REPO=/Users/bkaney/projects/reason-healthcare/rh
export CORPUS=/Users/bkaney/projects/reason-healthcare/hl7-agentic-knowledge-connectathon
export RUN_ID="live-$(date -u +%Y%m%dT%H%M%SZ)"
export TOPIC=steadi-live-replay
export LIVE_ROOT="${LIVE_ROOT:-$SKILLS_REPO/dist/connectathon-20260919/live-workspaces}"
export WS="$LIVE_ROOT/$RUN_ID"
export UV_CACHE_DIR="$SKILLS_REPO/dist/connectathon-20260919/uv-cache"
export UV_PROJECT_ENVIRONMENT="$LIVE_ROOT/venv-$RUN_ID"
export RH_CLI_PATH="$RH_REPO/target/debug/rh"
export PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"
export LLM_PROVIDER=stub

mkdir -p "$WS"
uv sync --offline --locked --project "$SKILLS_REPO"
```

The original run-001/run-002 replays used Python 3.13+ through `uv`,
`rh-skills` commit `9f48a46f91bf2407d46394a0e235908baf9fd11b`, and RH CLI
`0.2.8`. The run-003 runtime hashes are historical. The frozen run-004
technical candidate uses RH commit `26716c9319f50ee71aa8456cc8a0ccefe100d7f5`,
native SHA-256
`7b11131a9c748daaedd88a830d1aa39328d2c6ff81908e5176a70fce83d945e6`, and
WASM SHA-256
`d936e08fed0ae47bcc30ad75274ec3d1336ec079a7bf97054de4fa80f1081726`; the
Node wrapper SHA-256 is
`478033b2ddbcab71dd648a59ccd25c07484113c2ccca381ef200fd3e8027f00b`.
Recheck revisions and checksums at session start and record them with the
results; the final readiness ledger remains authoritative for which services
and preview build were exercised. The RH evaluator must expose
`--subject`, `--evaluation-date`, `--measurement-period-start`,
`--measurement-period-end`, `--parameter`, and `--lib-path`:

```sh
"$RH_CLI_PATH" --version
shasum -a 256 "$RH_CLI_PATH"
"$RH_CLI_PATH" cql eval --help | rg -- '--subject|--evaluation-date|--measurement-period|--parameter|--lib-path'
"$UV_PROJECT_ENVIRONMENT/bin/python" -c 'import importlib.metadata as m; print(m.version("rh-skills"))'
git -C "$SKILLS_REPO" rev-parse HEAD
git --no-optional-locks -C "$RH_REPO" rev-parse HEAD
shasum -a 256 "$RH_CLI_PATH"
git --no-optional-locks -C "$CORPUS" rev-parse HEAD
git --no-optional-locks -C "$CORPUS" status --short
test "$(command -v rh-skills)" = "$UV_PROJECT_ENVIRONMENT/bin/rh-skills"
rh-skills --help >/dev/null
```

Set the per-workspace config **before any `rh-skills` command**. A copied
`.rh-skills.toml` can silently keep the old workspace root, so verify the root
before `init`, `formalize`, or composition and confirm that command output
paths remain below `$WS`.

```sh
cat > "$WS/.rh-skills.toml" <<EOF
[paths]
repo_root = "$WS"

[cql]
rh_cli_path = "$RH_CLI_PATH"
EOF
cd "$WS"
python - <<'PY'
import os, tomllib
from pathlib import Path
cfg = tomllib.loads(Path('.rh-skills.toml').read_text())
assert Path(cfg['paths']['repo_root']).resolve() == Path(os.environ['WS']).resolve()
assert Path(cfg['cql']['rh_cli_path']).resolve() == Path(os.environ['RH_CLI_PATH']).resolve()
print('workspace and RH binary pinned')
PY
```

Install the agent-native skills into this run workspace before beginning the
authoring workflow. Choose the generic `.agents/skills/` format with the
non-interactive menu answer `1`; this keeps the installed files and drift
lockfile under `$WS`, never in the `rh-skills` source checkout. `skills check`
compares the installation to that lockfile. The run-004 isolated install check
passed in a fresh offline-locked environment, and the installed CQL style
guide hash matches the curated source exactly. See the
[run-004 install evidence](../../dist/connectathon-20260919/live-workspaces/agent-skills-preflight-20260918/run004-final/fresh-install-evidence.json),
its [lockfile](../../dist/connectathon-20260919/live-workspaces/agent-skills-preflight-20260918/run004-final/fresh-workspace/.rh-skills-lock.yaml),
the [run-local skill check](../../dist/connectathon-20260919/workspaces/run-004/evidence/fresh-install/skills-check.txt),
and [content hash comparison](../../dist/connectathon-20260919/workspaces/run-004/evidence/fresh-install/content-hashes.txt).
The earlier wheel-install check is retained at
[agent-skill install evidence](evidence/agent-skills-install-preflight.json).
After installation, start or restart the live authoring agent with
`$WS` as its working directory so that session loads the installed
`.agents/skills/` instructions. Installing files does not hot-reload the
current agent session; use the generic platform contract unless a different
agent platform is explicitly selected and validated.

```sh
mkdir -p "$WS/evidence"
printf '1\n' | rh-skills skills init --from "$SKILLS_REPO/skills/.curated"
rh-skills skills check
shasum -a 256 "$WS/.rh-skills-lock.yaml" > "$WS/evidence/agent-skills-lock.sha256"
python - <<'PY'
import hashlib, json, os
from pathlib import Path
from ruamel.yaml import YAML

ws = Path(os.environ['WS'])
curated = Path(os.environ['SKILLS_REPO']) / 'skills/.curated'
installed = ws / '.agents/skills'
lock_path = ws / '.rh-skills-lock.yaml'
lock = YAML(typ='safe').load(lock_path.read_text())
assert lock['platforms'] == ['generic']
checks = {}
for name in ('rh-inf-extract', 'rh-inf-formalize', 'rh-inf-cql'):
    source = curated / name
    target = installed / name
    expected = (source / 'SKILL.md').read_text()
    actual = (target / 'SKILL.md').read_text()
    actual = actual.replace(f'.agents/skills/{name}/reference.md', 'reference.md')
    actual = actual.replace(f'.agents/skills/{name}/examples/', 'examples/')
    assert actual == expected, f'SKILL.md drift: {name}'
    source_files = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    target_files = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    assert source_files == target_files, f'file inventory drift: {name}'
    for rel in source_files - {'SKILL.md'}:
        assert (source / rel).read_bytes() == (target / rel).read_bytes(), f'support-file drift: {name}/{rel}'
    checks[name] = hashlib.sha256((target / 'SKILL.md').read_bytes()).hexdigest()
record = {
    'lockfile': str(lock_path),
    'lockfileSha256': hashlib.sha256(lock_path.read_bytes()).hexdigest(),
    'installedSkillCount': len(lock['skills']),
    'selectedInstalledSkillMdSha256': checks,
}
(ws / 'evidence/agent-skills-install-check.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
```

Do not use a globally installed `rh-skills`/`rh` from `PATH` without confirming
the selected executable. `RH_CLI_PATH` and the local config prevent the stale
binary failure observed during rehearsal. Do not remove context flags to
accommodate an old runtime.

## 2. Copy and register only the supplied inputs

Copy input files into the new workspace, leaving the protected repository
unchanged. Use the corpus manifest to check all six snapshot hashes and bytes;
keep `manifest.yaml` as evidence rather than registering it as a clinical
source. Copy the track overview and fixture contract as additional operational
sources. Preserve restricted normalized text locally and do not redistribute
it without a separate rights review.

```sh
rh-skills init "$TOPIC" --title 'STEADI live rehearsal' \
  --description 'Source-driven fall-risk screening rehearsal'
mkdir -p "$WS/sources" "$WS/evidence" "$WS/test-bundles"
cp "$CORPUS/sources/manifest.yaml" "$WS/evidence/source-manifest.yaml"
cp "$CORPUS/sources/raw/"{cdc-steadi-algorithm.pdf,cdc-steadi-pocket-guide.pdf,uspstf-falls-recommendation-2024.html,uspstf-falls-evidence-update-2024.html,pillay-falls-systematic-review-2024.html,cdc-injury-economics.html} "$WS/sources/"
cp "$CORPUS/README.md" "$WS/sources/connectathon-track-readme.md"
cp "$CORPUS/test-bundles/README.md" "$WS/sources/fixture-contract-readme.md"
cp "$CORPUS/test-bundles/manifest.json" "$WS/test-bundles/manifest.json"
cp "$CORPUS/test-bundles/questionnaire.json" "$WS/test-bundles/questionnaire.json"
ditto "$CORPUS/test-bundles/cases" "$WS/test-bundles/cases"
```

Before ingest, check every source in the six-entry source manifest against the
original revision, hash, and byte length. This read-only command prints each
verified file and fails on drift:

```sh
python - <<'PY'
import hashlib, os
from pathlib import Path
from ruamel.yaml import YAML
root = Path(os.environ['CORPUS'])
manifest = YAML(typ='safe').load((root / 'sources/manifest.yaml').read_text())
for item in manifest['included_sources']:
    path = root / item['local_path']
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert len(content) == item['bytes'], f"byte-count mismatch: {path}"
    assert digest == item['sha256'], f"SHA-256 mismatch: {path}"
    print(digest, len(content), path)
PY
```

Then follow the installed
`rh-inf-discovery` and `rh-inf-ingest` skills in plan/implement/verify order.
The real CLI steps are `rh-skills init`, `rh-skills source scan`,
`rh-skills ingest plan`, `rh-skills ingest list-manual`,
`rh-skills ingest implement sources/<file> --topic <topic>`,
`rh-skills ingest normalize sources/<file> --topic <topic>`, and
`rh-skills ingest verify <topic>`. Classify and annotate through the skill
workflow; keep source text as untrusted data. Do not create tracking rows or
normalized source files by hand. Record the reviewer's actual role and any
classification decisions. Confirm the topic and source count with
`rh-skills status show <topic> --json` before extraction.

The rehearsal registered eight source documents: the six manifest snapshots
plus the track README and fixture-contract README. The bounded terminology
scope was the three questions “feel unsteady when standing or walking,”
“worried about falling,” and “falls in the past year.” CMS139FHIR remains
comparison-only and link-only.

## 3. Extract, review, and validate L2

Use the `rh-inf-extract` skill from its plan stage through derive, validate,
and technical review. The planner can omit necessary use-case artifact types;
add only the bounded eligibility and pathway types, with the explicitly
reviewed source set. Example used in the rehearsal:

```sh
rh-skills promote plan "$TOPIC" --force \
  --include-artifact-type eligibility-criteria \
  --include-artifact-type care-pathway \
  --include-source cdc-steadi-algorithm_pdf \
  --include-source cdc-steadi-pocket-guide_pdf \
  --include-source uspstf-falls-recommendation-2024_html \
  --include-source connectathon-track-readme_md \
  --include-source fixture-contract-readme_md
```

`--include-artifact-type` adds a type only when plan inference omitted it;
`--include-source` is the shared provenance set for forced rows. Review the
resulting plan and every L2 body. Derive and validate the seven artifacts by
the documented `rh-skills promote body-init` / `rh-skills promote derive`
workflow: evidence summary, eligibility criteria, assessment, decision table,
care pathway, measure, and concepts/terminology. Use the normal approve and
finalize commands after the actual review; do not mark automated technical
review as human clinical approval.

For the supported SDC Boolean extraction path, the assessment L2 must preserve
the source Questionnaire identity/version, each exact question text and
linkId, and one reviewed Coding per Boolean item with system, version, code,
and display. Explicitly author `sections.instrument.version_algorithm` when
`observation_extraction.enabled` is true; the versioned SDC profile requires
Questionnaire version-algorithm metadata. Also author the supported profile,
enable flag, and survey category. The L2 validator/formalizer preserves these
typed fields; it does not run extraction. Ordinary assessments without enabled
SDC extraction do not inherit the item-Coding or extraction-metadata
requirements.

The final care-pathway contract in rh-skills `9f48a46` resolves only explicit
`rule_id`/`rule_ids` bindings; it no longer guesses a recommendation by fuzzy
title matching. It supports `applicability_conditions[]`, an AND of explicit
decision-condition IDs alongside any existing singular condition. The “await
complete response” step requires both unresolved response and screening
population. Keep text-only guideline actions as guidance; do not invent an
ActivityDefinition, referral code, or order from a similar catalog term.
Unknown/incomplete questionnaire data remains unknown for risk. Preserve the
supported Boolean type in L2 instead of encoding a Boolean as presence,
ordinal, or free text. Keep recommendation grade, evidence certainty, and
source type distinct; omit certainty when a source does not report it.

For LOINC, preserve the fixture-pinned version `2.81` on both the composed
codes and their verified expansion. The three shared codes are `100257-5`,
`97878-3`, and `52552-7`. Their active status and exact expansion were checked
through ReasonHub MCP at build time. Record provider, requested composition,
version, response timestamp, and response SHA-256 in the terminology L2. Write
the approved packet through `rh-skills promote concept write <topic>
--expansions <verified-expansion-yaml>` and then formalize the registered L2
artifact id `concepts`. A search result is not an expansion. The local Full
image has LOINC 2.82 and cannot answer an exact 2.81 expansion request; do not
silently upgrade, omit the version, invent codes, or leave an unreachable
placeholder. No terminology lookup is needed at preview runtime.

Validate every L2 artifact and check the status/event trail before proceeding:

```sh
rh-skills validate "$TOPIC" l2 evidence-summary
rh-skills validate "$TOPIC" l2 eligibility-criteria
rh-skills validate "$TOPIC" l2 assessment
rh-skills validate "$TOPIC" l2 decision-table
rh-skills validate "$TOPIC" l2 care-pathway
rh-skills validate "$TOPIC" l2 measure
rh-skills validate "$TOPIC" l2 concepts
rh-skills status check-changes "$TOPIC"
```

An automated technical review may establish schema/provenance consistency for
the rehearsal. It does not authorize clinical content. Mark the latter
pending until a qualified clinical reviewer actually reviews and signs off.

## 4. Author CQL, pin helpers, and translate

Before CQL authoring, set the L3 canonical/version and generate and review the
formalization plan. Initial formalization creates the resource and Library
skeletons that CQL authoring fills. Approve only after the required review;
the automated technical reviewer label does not imply clinical approval.

```sh
rh-skills formalize-config "$TOPIC" --non-interactive --force \
  --name SteadiLiveReplay --id steadi-live-replay \
  --canonical https://reason-healthcare.github.io/hl7-agentic-knowledge-connectathon/fhir \
  --status draft --version 0.2.0
rh-skills promote formalize-plan "$TOPIC" --force
# Review and approve the formalize plan using the rh-inf-formalize skill.
rh-skills formalize "$TOPIC" assessment --force
rh-skills formalize "$TOPIC" eligibility-criteria --force
rh-skills formalize "$TOPIC" evidence-summary --force
rh-skills formalize "$TOPIC" concepts --force
rh-skills formalize "$TOPIC" decision-table --force
rh-skills formalize "$TOPIC" measure --force
rh-skills formalize "$TOPIC" care-pathway --force --generate-strategies
```

Author CQL from the reviewed L2 and source oracle, following the
`rh-inf-cql` skill. For this SDC workflow, derive each observation retrieve
from an exact, pinned ValueSet alias; never treat QR linkIds as code-system
membership. The required patient logic has eight named expressions:
`In Screening Population`, `Completed Three Question Screen`, `At Increased
Fall Risk`, `Exercise Intervention Applicable`, `Consider Multifactorial
Intervention`, `Initial Population`, `Denominator`, and `Numerator`. Preserve
null as a distinct result from false. Bind evaluation to the selected patient
context, qualifying encounter, fixed evaluation clock, and the full
measurement-period parameter, not just the period start/end CLI bounds. The
Patient-context retrieves must be scoped by the pinned FHIR ModelInfo and
evaluator context; never add a manual `subject.reference = Patient.id` guard
as a workaround. Verify isolation with a mixed-patient Bundle.

The portable CQL uses `FHIRHelpers version '4.0.1'`, helper-based FHIR date
conversion, and a logical-model cast for FHIR choice elements. The Observation
retrieves use the three ValueSet aliases backed by the fixture-pinned LOINC
2.81 expansions. Qualification checks final status, Boolean value, the
qualifying ambulatory encounter selected through the Patient context, and a shared
`QuestionnaireResponse/<id>` `derivedFrom` reference. Completion requires
exactly one usable Observation for each of the three aliases; incomplete or
absent extraction remains unknown for increased risk. For Coding or
CodeableConcept terminology, declare a CodeSystem/Code or a reviewed ValueSet
and use typed equivalence (`~`) or membership (`in`), as shown in the CQL style
guide. Do not split terminology into raw system/code string predicates.
Primitive status fields such as `Observation.status = 'final'` remain direct
status-code comparisons. Do not use RH-only JSON member shortcuts such as `A.valueBoolean` or
`CodeableConcept.value` as portable CQL. The QR-only baseline remains useful
for comparison, but it is not the primary SDC execution path.

Copy the pinned local helper packets and import them only after CQL includes
them.
The workspace copy is under the ignored rehearsal area
`$SKILLS_REPO/dist/connectathon-20260919/dependencies/FHIRHelpers-4.0.1/`;
the RH-skills CLI does not fetch dependencies implicitly. The packet contains
the CQL, translated ELM, R4 4.0.1 model-info, and import manifest. Check the
manifest hashes before copying. Its provenance is CQFramework
`clinical_quality_language` tag `v3.26.0`, Apache-2.0; official Library
canonical is `http://hl7.org/fhir/uv/cql/Library/FHIRHelpers|4.0.1`.
Run-004 also uses official FHIRCommon `hl7.fhir.uv.cql#2.0.0`, compiled to
derivative ELM against the same pinned helper and FHIR R4 ModelInfo. Its
`references(Reference, Resource)` function compares only the final reference
path segment with `Resource.id` and assumes a shared source server; it does not
validate reference type, base URL, canonical, or history semantics.

```sh
mkdir -p "$WS/process/dependencies/FHIRHelpers-4.0.1"
cp "$SKILLS_REPO/dist/connectathon-20260919/dependencies/FHIRHelpers-4.0.1/"* \
   "$WS/process/dependencies/FHIRHelpers-4.0.1/"
cd "$WS"
rh-skills cql import-library "$TOPIC" \
  process/dependencies/FHIRHelpers-4.0.1/import-manifest.json
mkdir -p "$WS/process/dependencies/FHIRCommon-2.0.0"
cp "$SKILLS_REPO/dist/connectathon-20260919/dependencies/FHIRCommon-2.0.0/"* \
   "$WS/process/dependencies/FHIRCommon-2.0.0/"
rh-skills cql import-library "$TOPIC" \
  process/dependencies/FHIRCommon-2.0.0/import-manifest.json
# Re-import so FHIRCommon's transitive FHIRHelpers dependency is linked.
rh-skills cql import-library "$TOPIC" \
  process/dependencies/FHIRHelpers-4.0.1/import-manifest.json
```

Each import is tracked as an external dependency with source/ELM hashes and a
versioned FHIR Library. The native RH CQL commands resolve these includes from
the imported, version-checked ELM sidecar and its provenance record; they do
not need to parse the full external helper source as ordinary CQL. The
reference translator separately compiles the authored libraries against the
pinned source closure, so keep both dependency sources in its input directory.

Expected helper hashes:

| File | SHA-256 |
| --- | --- |
| `FHIRHelpers-4.0.1.cql` | `6748661c16fe66dd07a68f07f77f7fea44e8b933d265dcc3c575964ba8329591` |
| `FHIRHelpers-4.0.1.json` | `4f8b5da2c1205afc62a1c3f4d412c87ccaeb9eb4d1196883704060d0863c9554` |
| `fhir-modelinfo-4.0.1.xml` | `16fa8119e074ebfb6a301b58af72417c2360dca899e89f6e3bd1d9a0e4789722` |

The FHIRCommon import packet is under
`$SKILLS_REPO/dist/connectathon-20260919/dependencies/FHIRCommon-2.0.0/`.
Its important pinned hashes are:

| File | SHA-256 |
| --- | --- |
| `FHIRCommon-2.0.0.cql` | `40ed15194eb5f436c9fdeec9267a74f1ef5f93b3755f431b3bf687d4cf4da28c` |
| `FHIRCommon-2.0.0.json` (ELM) | `5b735bf1807df3518d365206797b7c1693cacc996d9e022eab5bd6ca11264817` |
| Published package `hl7.fhir.uv.cql#2.0.0` | `a7c201465e98a7a528bf0ce1fff55e3d6f974efc8e19f99f476d88b3a063c35a` |

Its canonical is `http://hl7.org/fhir/uv/cql/Library/FHIRCommon|2.0.0`.

Before CQL tests, use the extraction capture tool against the immutable source
Bundles. It invokes the native extractor only for completed responses, using
the generated Questionnaire and the Patient/Encounter references from each
case; incomplete and absent responses are recorded as not invoked. It captures
the native transaction output and never reads `extracted-bundle.json` as runtime
output. Then compare the captured output with the source extraction oracle.

```sh
python "$SKILLS_REPO/docs/connectathon/tools/run-sdc-source-extraction.py" \
  --rh "$RH_CLI_PATH" \
  --oracle-root "$WS/test-bundles" \
  --questionnaire "$WS/topics/$TOPIC/computable/Questionnaire-steadi-three-question-screen.json" \
  --output-dir "$WS/process/observation-extraction"
python "$SKILLS_REPO/docs/connectathon/tools/verify-sdc-extraction.py" \
  --oracle-root "$WS/test-bundles" \
  --manifest "$WS/process/observation-extraction/manifest.json" \
  --output "$WS/evidence/sdc-extraction-verification.json"
```

Run the actual CLI sequence for both libraries. The CQL test adapter uses
QR-free Bundle views made from actual captured extractor outputs: retain the
captured Patient, Encounter, and generated Observations unchanged, and remove
only the QuestionnaireResponse entry so the test proves CQL reads Observations.
Record this adapter transformation and the source capture manifest. Each test
case has `input/bundle.json`, `input/terminology.json`,
`input/evaluation-context.json`, and `expected/expression-results.json`. The
terminology sidecar is a Bundle of complete, version-pinned ValueSet resources;
`rh-skills cql test` passes it to RH as `--terminology`. The decision library
has 48 assertions (eight expressions times six cases); the Measure library
tests the three population expressions for 18 assertions. Preserve the
original 48-expression source oracle unchanged. Pass the explicit
`Patient/<id>`, evaluation date, both period bounds, and full `Measurement
Period` JSON including inclusivity. Do not key logic off fixture ids or
silently treat a missing response as false.

```sh
rh-skills cql validate "$TOPIC" FallRiskScreeningRecommendationLogic
rh-skills cql translate "$TOPIC" FallRiskScreeningRecommendationLogic
rh-skills cql test "$TOPIC" FallRiskScreeningRecommendationLogic
rh-skills cql validate "$TOPIC" MeasureMeasure
rh-skills cql translate "$TOPIC" MeasureMeasure
rh-skills cql test "$TOPIC" MeasureMeasure
```

The run-004 authoring and packaging commands have been executed. Their exact
command list, tool/runtime pins, CQL/ELM/package hashes, fixture hashes, and
supporting evidence links are recorded in the
[run-004 authoring manifest](../../dist/connectathon-20260919/workspaces/run-004/evidence/authoring-manifest.json).
The four RH CLI validation/test logs are saved beside that manifest. The
fresh native extraction capture uses the final generated Questionnaire; four
completed responses were extracted and the incomplete/absent response cases
were not invoked. The six CQL test Bundles retain the captured Patient,
Encounter, and any extracted Observation resources, while omitting only the
QuestionnaireResponse resource so the expressions must read the Observations.
Those inputs are evaluation-only derivatives, not extraction outputs or new
clinical fixtures. The test oracle remains byte-identical to the inherited
48 decision and 18 Measure assertions.

Also translate through the pinned CQFramework 3.26.0 reference translator with
the FHIR R4 4.0.1 model-info and overload signatures. A zero-error reference
translation plus RH execution is required for portable-source evidence, but it
is not two independent execution engines. Record translator options and
diagnostics. Include pinned FHIRCommon 2.0.0 and FHIRHelpers 4.0.1 sources in
the reference translator input closure. Re-formalize the CQL-dependent
decision-table and measure artifacts after successful translation so their
generated Libraries contain the actual CQL/ELM and both dependency links; only
re-formalize the care pathway if its own L2 content changed. Then rerun
validation and all fixture tests. Reference translation of the corrected
run-004 Libraries is recorded in the
[reference translation manifest](../../dist/connectathon-20260919/workspaces/run-004/evidence/reference-cqf-run004-20260918T143000Z/manifest.json).
Normal RH CLI validation, translation, and evaluation also pass with the
imported FHIRCommon/FHIRHelpers dependency closure; the composer includes the
matching versioned Library resources and `depends-on` references in the
23-resource Bundle.

The six source cases are younger-than-65, eligible-all-no,
eligible-unsteady-yes, eligible-prior-fall-yes,
eligible-incomplete-response, and eligible-no-response. The original oracle is
48 typed expression assertions; run-002 passed all 48 against its final
authored CQL and 96 total reference-ELM checks (48 original plus 48
variations). The four foreign/out-of-period encounter intervention
expectations were reviewed as `null` under the authored unknown-precedence
contract; they are not false. Other variations tested wrong patient, wrong
Questionnaire version, duplicate answers, changed patient/resource IDs, and
Boolean/null typing. Never edit the shared source assertions to make a failed
implementation pass.

After successful translation, re-formalize only the CQL-dependent artifacts
so the generated Libraries contain the actual CQL/ELM and `FHIRHelpers` plus
`FHIRCommon` dependency links. Use the actual provider explicitly; this
rehearsal used `stub` for deterministic templates:

```sh
LLM_PROVIDER=stub rh-skills formalize "$TOPIC" decision-table --force
LLM_PROVIDER=stub rh-skills formalize "$TOPIC" measure --force
```

## 5. Formalize, package, and compose the executable Bundle

Validate L3 with `rh-skills validate <topic> l3 <artifact>` and check that
generated titles preserve the L2 clinical title, all CQL identifiers exist,
canonical/version pairs agree with the embedded ELM, and no stale untracked
resources or `TODO` placeholders remain. The generated FHIR R4 resources must
preserve authored question code versions and link collection to the emitted
Questionnaire. `concepts` is the formalizer's L2 artifact id for the
terminology catalog; the literal id `terminology` is not registered in this
topic. Re-run the affected formalizations after every relevant source, L2,
CQL, ELM, or helper change.

Build the normal NPM package and executable Bundle from this same topic
revision. Use a disposable package build directory: `rh-skills package`
recreates its `--workspace-dir`, so pointing it at the standard
`process/package-workspace` would remove the composer's `executable/` output.
Keep the six synthetic fixture Bundles in fixture examples and the executable
fixture index; do not merge patient Bundles into the knowledge Bundle.

```sh
PACKAGE_BUILD="$WS/topics/$TOPIC/process/package-build-$RUN_ID"
rh-skills package "$TOPIC" --pack \
  --include-test-fixtures "$WS/tests/cql" \
  --fixture-library FallRiskScreeningRecommendationLogic \
  --workspace-dir "$PACKAGE_BUILD"
mkdir -p "$WS/topics/$TOPIC/process/package-workspace/output"
cp "$PACKAGE_BUILD/output/"*.tgz \
   "$WS/topics/$TOPIC/process/package-workspace/output/"

rh-skills compose-executable "$TOPIC" \
  --root-canonical 'https://reason-healthcare.github.io/hl7-agentic-knowledge-connectathon/fhir/PlanDefinition/steadi-fall-risk-screening-protocol|0.2.0' \
  --fixture-manifest "$WS/test-bundles/manifest.json" \
  --fixture-dir "$WS/test-bundles/cases" \
  --evaluation-date '2026-06-15T09:20:00Z'
```

Before accepting composition, assert that reported output paths begin with
`$WS`; the root canonical/version selects the expected PlanDefinition; the
Bundle closes all referenced Library/ELM/helper dependencies; ValueSet
expansions are complete and versioned; and all six fixture bundles remain in
the sidecar. Record Bundle, manifest, package, fixture-index, source, L2,
CQL/ELM, tool, and dependency hashes. Re-run the composer into a separate clone
and compare normalized resource hashes to prove regeneration is deterministic.

## 6. Validate and exercise both previews

Run the official HL7 validator 6.10.2 over the composed resource inventory
with FHIR R4 4.0.1, SDC 4.0.0, and CPG 2.0.0 packages loaded from the pinned
local cache. Use `-tx n/a` only when recording that terminology validation is
offline; the separately verified LOINC expansion is still required. The
acceptance result requires zero FHIR errors. Triage every warning; resolve
references from the actual Bundle closure, and do not treat validator
canonical-resolution messages as proof of closure. The previous run-001
Bundle had zero errors and no unresolved reference warnings; run-002's
validator result remains whatever the current ledger says, not a carry-forward
from run-001.

Validate runtime outputs separately from the knowledge Bundle: capture all
PlanDefinition `$apply` Bundles and individual MeasureReports for all six
fixtures, then run the same official validator against each result together
with its knowledge dependencies. A clean package validation does not establish
valid operation outputs. Check that non-coded guidance is conveyed as a valid
RequestGroup note, not an invalid leaf order; measure counts remain complete
for a zero denominator and an undefined score is omitted. Classify any
validator diagnostic about zero-denominator `measureScore` against the
FHIR R4 rule and the saved raw OperationOutcome; do not suppress errors or
convert an undefined score to zero.

Import the Workbench snapshot built from the NPM output and executable Bundle
from this same revision. Confirm the package inventory, L2/L3 source links,
Questionnaire response handoff, selected subject/encounter, measure period,
and named fixture selector. Exercise guideline, measure, and Questionnaire
previews in the browser. Repeat through the standalone CPG preview only after
its separate raw patient-Bundle upload flow is available. Capture their
API/browser evidence and compare results to the six source assertions. A
successful CLI run, package build, or snapshot import alone is not a preview
pass. For the durable
required-core and optional service command, see
[the tools provenance and invocation](tools/PROVENANCE.md).

The runtime represents non-coded text guidance in the RequestGroup notes; it
does not create a coded order or referral. With a zero measure denominator,
retain complete counts and omit the mathematically undefined score. In
run-004, runtime-output validation is `strictValidatorPassed: false`: among
the 12 validated outputs, the only accepted error is one
`MEASURE_MR_SCORE_REQUIRED` at `MeasureReport.group[0]` in
`younger-than-65--MeasureReport-measure.json`. That fixture has a zero
denominator, so the FHIR R4 score is undefined and omitted; validator 6.10.2
still reports it as required. The run-004 summary has those exact values; see
[knowledge Bundle validation](evidence/run004-knowledge-fhir-validation.json)
and [runtime-output validation](evidence/run004-runtime-fhir-validation.json).
Accept this exception only when the run-specific validation record identifies
that exact input and error, preserves the raw OperationOutcome, and has
`unacceptedErrors: []` plus `acceptedForCoreRehearsal: true`. Any additional or
different error fails the gate; do not fabricate a score or suppress the
validator result. Record standards-server round trips and engine identity
separately from Workbench/standalone smoke tests.

## 7. Timing, gates, and limits

Observed wall-clock from workspace creation to first executable Bundle was
3h 26m 31s for run-001 and 2h 28m 59s for run-002. These include framework
debugging, validation, waits, and repair/rebuild cycles; they are not hands-on
authoring durations or a clean 60–90 minute target. Run-002's author had prior
integration context and the independent fresh-session spawn was unavailable,
so it is not reported as a fully fresh-context replay. Capture live authoring,
human review, framework repair, and service/queue waits as separate durations.

The measured intervals were run-001 workspace creation at 19:39:51 EDT to its
first Bundle at 23:06:22 EDT, and run-002 creation at 20:37:29 EDT to its first
Bundle at 23:06:28 EDT. Journal milestones put run-001 L1 verification around
20:05, L2 review around 20:09, and its first 48-expression native CQL run at
20:32; these tasks overlapped with framework/runtime work and must not be
summed as exclusive authoring time. Run-002 recorded L1/L2 at 00:53:24Z,
scoped terminology completion at 01:45:42Z, portable CQL replay later in the
same session, and first Bundle at 03:06:28Z. Its first manual plan edit was
preserved as a failed intervention and excluded from the successful skill
path; the planner fix and later clean replan were counted as framework
intervention, not agent authoring. No credible hands-on-only total was
measured.

The source-authored runs also differ in two substantive ways. Run-001 retained
both a separate `terminology` artifact and a `concepts` catalog, while
run-002 scoped the three verified LOINC 2.81 concepts into the registered
`concepts` artifact. Run-001 used a phase-oriented pathway and coded positive
communication action; run-002 authored text-only exercise/multifactorial
guidance and an explicit unresolved-response AND screening-population gate.
Treat these as distinct authoring choices requiring review, not byte-identical
independent outputs. Clinical review remains pending for both.

The historical run-003 replay verified the local native extractor for the
bounded Boolean SDC profile. Run-004 repeated native extraction and
Observation-driven CQL over six cases: four completed responses were
extracted, while incomplete and absent responses were not invoked. The final
generated Questionnaire and actual extracted resources were validated, and
the package passed knowledge Bundle validation with zero errors and zero
unresolved references. Workbench API validation passed 72/72 checks, and the
captured browser staging flow passed on the reported Workbench build. Standalone
raw-QR API parity passed 6/6, and the separate patient-file browser Apply flow
passes on standalone `6227080`. Decoded Measure/FHIRCommon CQL and ELM are
browser-verified in Workbench `f79a632`; shared Source keyboard handling passes
its existing Measure dialog regression. See the
[run-004 browser report](evidence/run004-browser-verification.json) and
[runtime/API report](evidence/run004-final-runtime-app-verification.json).
These results do not establish full standard SDC `$extract`
interoperability. The track still requires two independent CQL
implementations and round-trips through two independent FHIR servers; native
and WASM builds of the same RH engine do not satisfy the two-engine
requirement. Keep any still-open gate in the status ledger. Do not equate
technical schema/ELM/FHIR validation with clinical approval.

The two formalization-replay comparisons are recorded in
[`run001-9f48a46-deterministic-rebuild.json`](evidence/run001-9f48a46-deterministic-rebuild.json)
and [`run002-9f48a46-deterministic-rebuild.json`](evidence/run002-9f48a46-deterministic-rebuild.json).
The run-002 record includes the clone-root isolation correction and identifies
the only workspace-dependent difference as absolute `sourcePath` values in
the executable manifest.

## Preview service launch and recovery

The frozen run-004 technical candidate uses RH runtime
`26716c9319f50ee71aa8456cc8a0ccefe100d7f5`, native SHA-256
`7b11131a9c748daaedd88a830d1aa39328d2c6ff81908e5176a70fce83d945e6`, and
WASM SHA-256
`d936e08fed0ae47bcc30ad75274ec3d1336ec079a7bf97054de4fa80f1081726`.
These pins identify the code used for current local checks; they do not
substitute for the final readiness ledger or an application/browser acceptance
result.
Use the durable archived workspaces, never an ephemeral `/private/tmp` run:

```sh
export SKILLS_REPO=/Users/bkaney/projects/reason-healthcare/rh-skills
export RH_REPO=/Users/bkaney/projects/reason-healthcare/rh
export STANDALONE_ROOT="$SKILLS_REPO/dist/connectathon-20260919/standalone"
export STANDALONE_APP="$STANDALONE_ROOT/packages/cpg-review"
export WORKBENCH_REPO=/Users/bkaney/projects/reason-healthcare/workbench
export WORKBENCH_DATABASE_URL='postgres://workbench:workbench@127.0.0.1:55432/workbench'

git --no-optional-locks -C "$RH_REPO" rev-parse HEAD
shasum -a 256 "$RH_REPO/packages/cpg/wasm-node/rh_cpg_bg.wasm"
```

Before starting either application, compare these values with the current
readiness ledger and record any later runtime rebuild. Stop if the application
does not use the intended native/WASM hash; a local candidate pin is not a
release or full-track conformance claim.

Build each production application from its checked-out final revision. The
Workbench build needs the task database at port `55432` only when it starts;
do not substitute a default local PostgreSQL port. Stop an existing local
listener only after identifying it, then start one instance of each service:

```sh
cd "$WORKBENCH_REPO"
npm run build --workspace @reasonhealth/workbench
DATABASE_URL="$WORKBENCH_DATABASE_URL" PORT=9090 HOSTNAME=127.0.0.1 \
  npm run start --workspace @reasonhealth/workbench

cd "$STANDALONE_APP"
npm run build
RH_CPG_WASM_NODE_MODULE="$RH_REPO/packages/cpg/wasm-node/rh_cpg.js" \
  PORT=9091 HOSTNAME=127.0.0.1 \
  node .next/standalone/packages/cpg-review/server.js
```

Run these two server commands in separate terminals; each remains in the
foreground. If Docker was restarted, start the existing task database with
`docker start connectathon-workbench-postgres-20260917`. Do not recreate or
reset it. Workbench's local demo login is `admin@vermonster.com` / `password`.

The services are intentionally local-only. In separate shells, verify the
actual routes before opening a browser: the unauthenticated Workbench root may
return its normal sign-in redirect, while standalone must render its upload
page directly.

```sh
curl -fsS -o /dev/null -w 'standalone %{http_code}\n' http://127.0.0.1:9091/
curl -fsS -o /dev/null -w 'workbench %{http_code}\n' http://127.0.0.1:9090/
```

Then load the actual browser interfaces. An HTTP 200 alone is insufficient:
the final standalone build's `postbuild` copies both `.next/static` and
`public` into its generated server tree. The final root-document probe checked
12 Workbench sign-in assets and 29 standalone assets with zero failures. This
is an initial-page asset check; actual preview navigation was also tested. A
permanent Loading screen or missing logo means the asset check failed; run
the production build again before using the preview.

Workbench browser verification passed against snapshot
`snap_connectathon-steadi-observations_run004-d412006a1f1a`; the report records
the extraction staging flow, positive guidance, and restored unknown-response
path. Earlier snapshot links remain historical rehearsals:
[run-001](http://localhost:9090/projects/connectathon-steadi/snapshots/snap_connectathon-steadi_run001-08a666000842)
and [run-002](http://localhost:9090/projects/connectathon-steadi-replay/snapshots/snap_connectathon-steadi-replay_run002-3e6a1fde4db9).

To inspect decoded Libraries in Workbench, open **Inspect package contents**,
expand a **Library**, then **Inspect Library content**. CQL is readable by
default; expand `application/elm+json` for formatted ELM, or **Original FHIR
Library JSON** for the encoded source. The **Authored artifacts** Library list
uses the same viewer. Canonical, version and content type remain visible.
Malformed/unsupported attachments show an explicit status; URL-only
attachments are not fetched automatically.

The [standalone preview](http://localhost:9091) runs the knowledge-only run-004
package with a separate raw patient fixture:

1. Upload `dist/connectathon-20260919/workspaces/run-004/topics/steadi-live-replay/process/package-workspace/output/reason.steadi-live-replay-0.2.0.tgz`.
2. Select **STEADI fall-risk screening care pathway**, **View Content**, then **Add Context**.
3. Expand **FHIR Endpoints Configuration** and choose **Local pinned RH CPG runtime**. Set evaluation date `2026-06-15T09:20:00Z` and period `2026-01-01T00:00:00Z` through `2026-12-31T23:59:59Z`.
4. Choose **Local file** and **Choose local FHIR Bundle file**. Upload `dist/connectathon-20260919/workspaces/run-004/topics/steadi-live-replay/process/package-workspace/executable/fixtures/eligible-unsteady-yes.json`; set encounter `Encounter/encounter-eligible-unsteady-yes`. The selected Patient is read from the file.
5. Click **Apply**. Verify exercise and individualized multifactorial guidance. **Edit Context**, load `eligible-no-response.json` from the same directory, and set `Encounter/encounter-eligible-no-response`; Apply must show the unknown-response stop note without positive guidance.

The file must be a FHIR Bundle containing exactly one Patient with a valid id.
An invalid file produces an inline error; loading a valid file clears it.
Patient data stays separate from the knowledge package, and external endpoint
search is disabled in local mode. Use these raw fixtures, never the expected
`extracted-bundle.json` oracle: completed responses invoke actual extraction;
absent/incomplete responses do not create Observations. The standalone
Task-based pathway does not expose an interactive Questionnaire editor; use
Workbench for the live assessment completion demonstration.

If Workbench returns a database aggregate error, check that the process was
started with `WORKBENCH_DATABASE_URL` above and that the task database at
`127.0.0.1:55432` is available; preserve the database and restart the process
with the same URL. If standalone reports a missing local runtime module, check
`RH_CPG_WASM_NODE_MODULE`, its exact WASM hash, and rebuild the standalone
application. Do not fall back to an external engine, HAPI server, or an
unversioned package. Rerun the API parity entrypoint after either restart and
record the new build/runtime/content hashes alongside its result.

## Recovery checks

- **CLI uses the wrong binary or rejects subject/period flags:** inspect
  `RH_CLI_PATH`, the `[cql]` entry in `.rh-skills.toml`, the binary checksum,
  and `rh cql eval --help`. Rebuild/select the pinned binary, then rerun the
  real fixture command with all context flags intact.
- **Output path escapes the run directory:** stop. Read `.rh-skills.toml`,
  confirm its `repo_root` equals `$WS`, and rerun only in that isolated run.
  A prior comparison clone retained the original `repo_root`; formalize only
  rewrote the original `tracking.yaml` convergence entries and timestamps. The
  original tracking file was restored byte-for-byte from the pre-run copy,
  while resource, Bundle, package, and fixture hashes remained unchanged. The
  clone was retargeted before the successful replay. See the run-002 evidence
  link above. Do not repair an accepted output by copying from a rehearsal
  after the fact.
- **Versioned helper does not resolve:** compare all three local helper hashes,
  confirm the import manifest path is under `$WS/process/dependencies`, and
  rerun `cql import-library`, translate, then formalize the affected Libraries.
  Do not remove the CQL include or rely on unversioned fallback behavior.
- **Exact terminology release is unavailable:** stop with a terminology
  blocker. Search is not expansion, and LOINC 2.82 is not an acceptable
  replacement for fixture-pinned 2.81.
- **Package build would replace the executable folder:** cancel and select a
  unique `process/package-build-$RUN_ID` workspace, then copy the built
  archive into the existing output folder.
- **Any L2, CQL, source, or helper hash changes:** regenerate every dependent
  FHIR Library/PlanDefinition/Measure, translate, rerun both six-case CQL
  suites, official FHIR validation, execution matrix, package, snapshot, and
  browser checks. Keep prior failed evidence; never edit the shared oracle.

At handoff, update the central status ledger and journal with exact repository
SHAs, elapsed stages, outputs/hashes, review roles, failure recovery,
unresolved warnings, and remaining interoperability gaps. Verify the protected
source repository still has its original revision and clean Git status.
