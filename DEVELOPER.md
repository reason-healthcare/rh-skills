# RH Skills — Developer Guide

For contributors working on the `rh-skills` CLI, the curated skill library, or the framework specs.

> **End-user docs** → [README.md](README.md)

---

## Dev Setup

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url> reason-skills-2
cd reason-skills-2
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
uv run pytest tests/unit/test_init.py  # single file
```

The skill test suite (`tests/skills/`) is parametrized over curated skills in `skills/.curated/`. Tests skip gracefully when no skills are implemented yet and activate automatically as each skill is added.

## Repository Layout

```
specs/                          ← feature specifications
  001-rh-skills-framework/      ← framework foundation (data model, CLI contract)
  002-rh-agent-skills/          ← agent skills framework (this dev repo)
  003-rh-inf-discovery/         ← individual skill specs (003–008)
  ...

src/hi/                         ← rh-skills CLI source (Python, click)
  commands/
    init.py  list_cmd.py  status.py  ingest.py  promote.py  validate.py  test_cmd.py

tests/
  unit/                         ← pytest tests for CLI commands
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

docs/
  GETTING_STARTED.md
  WORKFLOW.md
  COMMANDS.md
  SKILL_AUTHORING.md            ← step-by-step skill authoring guide

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

CLI commands live in `src/hi/commands/`. Each command:
- Is a `@click.command()` or `@click.group()` registered in `src/hi/cli.py`
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
rh-skills ingest implement --url <url> --name <slug> [--type <mime>]
```

Exit codes: `0` success · `1` network/HTTP error · `2` file already exists · `3` auth redirect detected

### rh-skills validate --plan

Validate a discovery plan YAML file for completeness and correctness.

```sh
rh-skills validate --plan topics/<topic>/process/plans/discovery-plan.yaml
```

Checks: YAML parseable · 5–25 sources · terminology source present · all rationale non-empty ·
all search_terms non-empty · valid evidence_level · known source type (warning) · health-economics source (warning).

## Branches & Commits

- Feature branches: `00N-<spec-name>` (e.g., `003-rh-inf-discovery`)
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- All tests must pass before merging; skill tests must have zero FAIL-level findings

## Further Reading

- [Usage Modes](docs/USAGE_MODES.md) — CLI-first vs agent-native, LLM configuration, platform support
- [Workflow](docs/WORKFLOW.md) — artifact lifecycle and many-to-many topology
- [Skill Authoring Guide](docs/SKILL_AUTHORING.md) — detailed per-step instructions
- [Command Reference](docs/COMMANDS.md) — full `rh-skills` CLI reference
- [002 Spec](specs/002-rh-agent-skills/spec.md) — framework requirements (FRs, NFRs)
- [002 Data Model](specs/002-rh-agent-skills/data-model.md) — tracking.yaml schema, event types, state machine
