# RH Skills — Developer Guide

For contributors working on the `rh-skills` CLI, the curated skill library, or the framework specs.

> **End-user docs** → [README.md](README.md)

---

## Dev Setup

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/reason-healthcare/rh-skills
cd rh-skills
uv sync                  # install all dependencies into .venv
uv run rh-skills --help         # run the CLI from the local source
make install             # install rh-skills into ~/.local/bin (editable)
```

## Running Tests

```bash
make test                              # full suite
make test-unit                         # CLI unit tests only
make test-skills                       # skill schema, security, contract tests
make test-integration                  # integration tests
uv run pytest                        # full suite
uv run pytest tests/unit/            # CLI unit tests only
uv run pytest tests/skills/          # skill schema, security, contract tests
uv run pytest tests/build/           # build-system fixtures and bundle validation
uv run pytest tests/unit/test_init.py  # single file
```

The skill test suite (`tests/skills/`) is parametrized over curated skills in `skills/.curated/`. Tests skip gracefully when no skills are implemented yet and activate automatically as each skill is added.

## Building Distribution Bundles

Use the build entrypoint to turn canonical curated skills into deterministic
platform bundles under `dist/`:

```bash
scripts/build-skills.sh --platform copilot
scripts/build-skills.sh --all --dry-run
scripts/build-skills.sh --all --validate
```

Platform behavior lives in `skills/_profiles/*.yaml`, so new targets should
normally be onboarded by adding a profile and any referenced support content
rather than editing the core script. See
[docs/SKILL_DISTRIBUTION.md](docs/SKILL_DISTRIBUTION.md) for profile fields,
validation rules, and CI reproduction steps.

## Repository Layout

```
specs/                          ← feature specifications
  001-rh-skills-framework/      ← framework foundation (data model, CLI contract)
  002-rh-agent-skills/          ← agent skills framework (this dev repo)
  003-rh-inf-discovery/         ← individual skill specs (003–008)
  ...

src/rh_skills/                         ← rh-skills CLI source (Python, click)
  commands/
    init.py  list_cmd.py  status.py  ingest.py  promote.py  validate.py  test_cmd.py

tests/
  unit/                         ← pytest tests for CLI commands
  build/                        ← fixture-driven bundle generation + validation tests
  skills/                       ← skill schema, security, and contract tests
    conftest.py                 ← shared fixtures (curated_skill, parse_frontmatter)
    test_skill_schema.py        ← frontmatter validation, companion file presence
    test_skill_security.py      ← COMMAND_EXECUTION, PROMPT_INJECTION, PHI_EXPOSURE, etc.
    test_skill_audit.py         ← FR-016–FR-026 framework contract compliance

skills/
  _template/                    ← canonical SKILL.md template (copy to start a skill)
    SKILL.md
    reference.md
    examples/
      plan.md
      output.md
  .curated/                     ← stable, distributable skills (003–008 land here)
  _profiles/                    ← declarative bundle profiles + support content

scripts/
  build-skills.sh               ← deterministic bundle builder for agent-native platforms
  eval-skill.sh                 ← run a skill in an isolated workspace and capture transcript

eval/
  transcripts/                  ← captured agent session transcripts (per skill/scenario)
  reviews/                      ← human-filled review stubs (efficiency + quality scores)

docs/
  GETTING_STARTED.md
  WORKFLOW.md
  COMMANDS.md
  SKILL_AUTHORING.md            ← step-by-step skill authoring guide
  SKILL_DISTRIBUTION.md         ← build/profile/CI guide for generated bundles

schemas/
  l2-schema.yaml
  l3-schema.yaml
```

## Implementing a Skill

All six RH informatics skills follow the same SKILL.md pattern. To implement a new one:

1. **Copy the template**
   ```bash
   cp -r skills/_template skills/.curated/rh-inf-<capability>
   ```

2. **Fill in the SKILL.md** — replace every `<placeholder>` with skill-specific content. See `docs/SKILL_AUTHORING.md` for required sections and design rules.

3. **Update companion files** — `reference.md` (schemas, validation rules, clinical standards) and `examples/` (realistic plan + output examples).

4. **Run the skill test suite** — it must pass with zero failures:
   ```bash
   uv run pytest tests/skills/ -v
   ```

5. **Write a spec** — every skill has its own spec in `specs/00N-rh-inf-<capability>/`. Use the `speckit-specify`, `speckit-plan`, `speckit-tasks` skills to generate it.

### Skill Design Rules

- **Deterministic work to `rh-skills` CLI commands** — file I/O, schema validation, tracking writes, path resolution, all go in the CLI. Only reasoning belongs in SKILL.md.
- **`plan → implement → verify` modes** — every skill exposes all three. `verify` is strictly read-only (FR-022, FR-026).
- **Progressive disclosure** — SKILL.md body is Level 2; `reference.md` and `examples/` are Level 3 (loaded on demand). Keep the SKILL.md body lean.
- **Named events** — every `implement` mode must append a named event to `tracking.yaml` via `rh-skills ingest` / `rh-skills promote` (never raw YAML writes).

## Iterating on a Skill Locally

Before committing a new or revised skill, run it end-to-end in an isolated
workspace and capture the session for review. This surfaces two categories of
problems that static tests cannot catch:

1. **Efficiency** — ambiguity in the skill prompt, agent churn, and missing CLI
   commands (cases where the agent wrote a shell script for something that should
   be an `rh-skills` subcommand).
2. **Output quality** — clinical accuracy, schema compliance, evidence
   traceability, and absence of hallucinations. This requires a human reviewer.

### Running an eval session

```bash
# Claude CLI against rh-inf-discovery, "sources-identified" scenario
scripts/eval-skill.sh \
  --skill rh-inf-discovery \
  --scenario sources-identified \
  --agent claude

# Local model via Ollama
scripts/eval-skill.sh \
  --skill rh-inf-ingest \
  --scenario ingest-pdf \
  --agent ollama --model llama3

# No agent — dumps an opening prompt for manual copy-paste
scripts/eval-skill.sh \
  --skill rh-inf-extract \
  --scenario single-source \
  --agent generic
```

The script:

1. Creates a temp directory (`mktemp -d`) and bootstraps a minimal `rh-skills`
   project inside it so the agent sees a realistic workspace.
2. Calls `rh-skills skills init --platforms generic` to install the skill.
3. Launches the chosen agent, piping the opening prompt to it.
4. Tee-s stdout/stderr to a transcript file at
   `eval/transcripts/<skill>/<scenario>-<timestamp>.md`.
5. Writes a human-review stub to
   `eval/reviews/<skill>/<scenario>-<timestamp>-review.md`.
6. Deletes the temp directory on exit (pass `--keep-workdir` to preserve it for
   manual inspection of produced artifacts).

### Completing the review

Open the generated review stub and work through both checklists:

**Efficiency checklist** (objective — can be filled in by the skill author):

| Signal | What to look for |
|--------|-----------------|
| Ambiguity | Agent asked clarifying questions a clearer prompt would have answered |
| Churn | Agent retried a step, re-read the same file, or looped on the same sub-task |
| CLI gaps | Agent wrote an inline script for I/O, schema validation, or path ops that belong in `rh-skills` |
| Over-instruction | Skill body restates rules that are already in `reference.md`; trim and move |
| Token waste | Verbose preambles or repeated tool calls with identical arguments |

**Output quality checklist** (subjective — requires a clinical reviewer):

| Dimension | What to check |
|-----------|--------------|
| Completeness | All expected files/sections are present for the scenario |
| Clinical accuracy | Terminology, evidence levels, and cited guidelines are correct |
| Schema compliance | YAML/FHIR structure matches `schemas/l2-schema.yaml` or `l3-schema.yaml` |
| Traceability | Every claim in L2/L3 artifacts links back to an ingested source |
| No hallucinations | No fabricated citations, lab values, or guideline references |

Score each dimension 1–5 in the review file, add notes and recommended changes,
then commit both files:

```bash
git add eval/
git commit -m "eval(rh-inf-discovery/sources-identified): <one-line summary>"
```

### Scenario files

Each scenario is declared as a YAML file at
`eval/scenarios/<skill>/<scenario-name>.yaml`. When the script finds a matching
file it:

1. Seeds the workspace with the declared `tracking_yaml` and `files` entries
2. Uses the `prompt` field (with `{workdir}`, `{topic}`, `{skill}` placeholders) as the opening message
3. Pre-populates the review stub with the `expected_outputs`, `efficiency_focus`, and `quality_focus` checklists from the file

See `eval/scenarios/README.md` for the full schema.

**Current scenarios:**

| Skill | Scenario | What it tests |
|-------|----------|---------------|
| `rh-inf-discovery` | `fresh-start` | New topic, full session from blank slate |
| `rh-inf-discovery` | `resume-session` | Partial plan — add missing source types without duplicating existing ones |
| `rh-inf-ingest` | `open-access-sources` | Full ingest cycle, 3 open-access sources |
| `rh-inf-ingest` | `authenticated-source` | Correct advisory for gated source; no content fabrication |
| `rh-inf-extract` | `single-source` | Plan → implement → verify with one guideline source |
| `rh-inf-extract` | `conflicting-guidelines` | Explicit conflict record when two sources disagree |
| `rh-inf-formalize` | `converge-l2` | Converge two approved L2 artifacts into one L3 package |
| `rh-inf-status` | `empty-portfolio` | Empty portfolio — correct next-step guidance |
| `rh-inf-status` | `mid-workflow` | Two topics at different stages — distinct per-topic recommendations |
| `rh-inf-verify` | `post-ingest` | Missing normalized file detected; verify stays read-only |

### Naming scenarios

Use a short kebab-case label that describes the starting state or the
clinical question being tested, e.g.:

- `sources-identified` — discovery sources already found; test extract
- `ingest-pdf` — single PDF source; test normalize + classify
- `conflicting-guidelines` — two sources disagree; test conflict handling
- `no-sources` — nothing ingested yet; test graceful early exit

Scenarios accumulate in `eval/` and serve as a regression baseline when the
skill or the CLI commands it delegates to are updated.

## Skill Security Requirements

Before any skill is merged it must pass the security audit (`tests/skills/test_skill_security.py`):

| Check | Rule |
|-------|------|
| `COMMAND_EXECUTION` | Shell commands with user input must include explicit sanitization |
| `PROMPT_INJECTION` | Modes that read external content must declare an injection boundary |
| `CREDENTIAL_HANDLING` | Verbatim content copy must include a redaction rule |
| `PHI_EXPOSURE` | Patient data in outputs must include a de-identification rule |
| `TRACKING_WRITE` in verify | `verify` must not write `tracking.yaml` directly |

## Framework Contract Tests

`tests/skills/test_skill_audit.py` validates FR-016–FR-026 for every curated skill:

| FR | Contract |
|----|---------|
| FR-016 | `rh-skills ingest` CLI delegation pattern present |
| FR-017 | Plan artifact path follows `process/plans/<skill>-plan.md` |
| FR-018 | Plan-existence check before `implement` |
| FR-019 | `tracking.yaml` events mentioned |
| FR-020 | `--force` flag or overwrite protection documented |
| FR-021 | Named events appended on state change |
| FR-022 | `verify` is non-destructive (no create/modify/delete) |
| FR-025 | Security audit rules present (see above) |
| FR-026 | `verify` does not write `tracking.yaml` directly |

## Spec Structure

Each feature spec lives in `specs/00N-<name>/` and contains:

| File | Purpose |
|------|---------|
| `spec.md` | Requirements (FRs, NFRs, acceptance scenarios, edge cases) |
| `data-model.md` | Data structures, schemas, state machine |
| `plan.md` | Technical design, component breakdown |
| `tasks.md` | Ordered implementation tasks |
| `checklists/` | Requirements quality gate checklists |

Use the speckit skills (`.agents/skills/speckit-*/`) to generate and maintain these artifacts.

## Adding CLI Commands

CLI commands live in `src/rh_skills/commands/`. Each command:
- Is a `@click.command()` or `@click.group()` registered in `src/rh_skills/cli.py`
- Takes a `TOPIC` argument where applicable
- Updates `tracking.yaml` via `ruamel.yaml` (never raw string writes)
- Has unit tests in `tests/unit/test_<command>.py`
- Appends a named event on state-changing operations

### rh-skills search

Search biomedical databases and return structured results for use in discovery sessions.

```sh
rh-skills search pubmed --query "<terms>" --max 20 [--json]
rh-skills search pmc   --query "<terms>" --max 20 [--json]
rh-skills search clinicaltrials --query "<terms>" --max 20 [--json]
```

- `--json`: output a JSON object with query metadata plus `results[]`; each result includes shared keys (`id`, `title`, `url`, `year`, `journal`, `open_access`, `abstract_snippet`) plus PubMed-specific metadata (`pmid`, `authors`, `doi`, `pmcid`) or ClinicalTrials metadata (`nct_id`, `status`, `phase`, `conditions`, `interventions`)
- `--max`: maximum results to return (default 20)
- Set `NCBI_API_KEY` env var for higher PubMed rate limits (10 req/s vs 3 req/s)
- PubMed uses Entrez esearch→efetch two-step; ClinicalTrials uses REST API v2

### rh-skills ingest implement --url

Download a source file from a URL and register it in tracking.yaml.

```sh
rh-skills ingest implement --url <url> --name <slug> [--type <mime>] [--topic <topic>]
```

Exit codes: `0` success · `1` network/HTTP error · `2` file already exists · `3` auth redirect detected

### rh-skills ingest plan / verify

Topic-aware ingest orchestration stays read-only and is safe to call from the curated skill.

```sh
rh-skills ingest plan <topic>
rh-skills ingest verify <topic>
```

- `plan <topic>`: summarizes discovery-plan sources, authenticated/manual advisories, untracked files already present in `sources/`, and tool availability
- `verify <topic>`: reports file/checksum/normalized/classified/annotated readiness plus `concepts.yaml` validity without writing to `tracking.yaml`

### rh-skills promote derive

Derive an L2 structured artifact from one or more ingested sources.

```sh
rh-skills promote derive <topic> <artifact-name> \
  --source <source-name> \
  [--artifact-type <type>] \
  [--clinical-question "<question>"] \
  [--required-section <section>] \
  [--evidence-ref "claim_id|statement|source|locator"] \
  [--conflict "issue|source|statement|preferred_source|preferred_rationale"]
```

- multiple `--source` flags are supported for multi-source extraction
- stub/test mode now writes richer L2 artifact fields: `artifact_type`, `clinical_question`, `sections`, and `conflicts`
- `--evidence-ref` is repeatable and populates `sections.evidence_traceability`

### rh-skills promote plan

Write the 005 extract review packet from topic-normalized source inputs.

```sh
rh-skills promote plan <topic> [--force]
```

- writes `topics/<topic>/process/plans/extract-plan.md`
- groups normalized sources into candidate extract artifacts
- records `extract_planned` on success
- warns and exits without writing when no normalized topic sources are available
- refuses to overwrite an existing plan unless `--force` is passed

### rh-skills promote formalize-plan

Write the 006 formalize review packet from approved structured artifacts.

```sh
rh-skills promote formalize-plan <topic> [--force]
```

- writes `topics/<topic>/process/plans/formalize-plan.md`
- screens inputs to extract-approved structured artifacts that still pass validation
- proposes one primary pathway-oriented computable package and its required sections
- records `formalize_planned` on success
- refuses to overwrite an existing plan unless `--force` is passed

### rh-skills validate --plan

Validate a discovery plan YAML file for completeness and correctness.

```sh
rh-skills validate --plan topics/<topic>/process/plans/discovery-plan.yaml
```

Checks: YAML parseable · 5–25 sources · terminology source present · all rationale non-empty ·
all search_terms non-empty · valid evidence_level · known source type (warning) · health-economics source (warning).

### rh-skills validate `<topic> <artifact>`

Two-argument shorthand defaults to L2 validation:

```sh
rh-skills validate <topic> <artifact-name>
```

When `topics/<topic>/process/plans/extract-plan.md` exists and lists the artifact, validation also checks:
- `artifact_type` and `clinical_question`
- approved `source_files[]` vs `derived_from[]`
- required extract sections
- evidence traceability entries
- conflict records when the plan requires them

When `topics/<topic>/process/plans/formalize-plan.md` exists, is approved, and
marks the artifact as the implementation target, validation also checks:
- approved `input_artifacts[]` vs `converged_from[]`
- required computable sections from the approved plan
- minimum completeness for required sections such as pathways, actions, value sets, measures, libraries, and assessments

## Branches & Commits

- Feature branches: `00N-<spec-name>` (e.g., `003-rh-inf-discovery`)
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- All tests must pass before merging; skill tests must have zero FAIL-level findings

## Windows VM Parity Testing

See [Windows VM Contributing Guide](docs/WINDOWS_VM_CONTRIBUTING.md) for details on end user parity testing for a Windows VM.

## Further Reading

- [Usage Modes](docs/USAGE_MODES.md) — CLI-first vs agent-native, LLM configuration, platform support
- [Workflow](docs/WORKFLOW.md) — artifact lifecycle and many-to-many topology
- [Skill Authoring Guide](docs/SKILL_AUTHORING.md) — detailed per-step instructions
- [Command Reference](docs/COMMANDS.md) — full `rh-skills` CLI reference
- [002 Spec](specs/002-rh-agent-skills/spec.md) — framework requirements (FRs, NFRs)
- [002 Data Model](specs/002-rh-agent-skills/data-model.md) — tracking.yaml schema, event types, state machine
