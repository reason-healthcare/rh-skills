# HI Skills Framework — Developer Guide

For contributors working on the `hi` CLI, the curated skill library, or the framework specs.

> **End-user docs** → [README.md](README.md)

---

## Dev Setup

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url> reason-skills-2
cd reason-skills-2
uv sync                  # install all dependencies into .venv
uv run hi --help         # run hi from the local source
```

## Running Tests

```bash
uv run pytest                        # full suite
uv run pytest tests/unit/            # CLI unit tests only
uv run pytest tests/skills/          # skill schema, security, contract tests
uv run pytest tests/unit/test_init.py  # single file
```

The skill test suite (`tests/skills/`) is parametrized over curated skills in `skills/.curated/`. Tests skip gracefully when no skills are implemented yet and activate automatically as each skill is added.

## Repository Layout

```
specs/                          ← feature specifications
  001-hi-skills-framework/      ← framework foundation (data model, CLI contract)
  002-hi-agent-skills/          ← agent skills framework (this dev repo)
  003-hi-discovery/             ← individual skill specs (003–008)
  ...

src/hi/                         ← hi CLI source (Python, click)
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

All six HI skills follow the same SKILL.md pattern. To implement a new one:

1. **Copy the template**
   ```bash
   cp -r skills/_template skills/.curated/hi-<name>
   ```

2. **Fill in the SKILL.md** — replace every `<placeholder>` with skill-specific content. See `docs/SKILL_AUTHORING.md` for required sections and design rules.

3. **Update companion files** — `reference.md` (schemas, validation rules, clinical standards) and `examples/` (realistic plan + output examples).

4. **Run the skill test suite** — it must pass with zero failures:
   ```bash
   uv run pytest tests/skills/ -v
   ```

5. **Write a spec** — every skill has its own spec in `specs/00N-hi-<name>/`. Use the `speckit-specify`, `speckit-plan`, `speckit-tasks` skills to generate it.

### Skill Design Rules

- **Deterministic work to `hi` CLI commands** — file I/O, schema validation, tracking writes, path resolution, all go in the CLI. Only reasoning belongs in SKILL.md.
- **`plan → implement → verify` modes** — every skill exposes all three. `verify` is strictly read-only (FR-022, FR-026).
- **Progressive disclosure** — SKILL.md body is Level 2; `reference.md` and `examples/` are Level 3 (loaded on demand). Keep the SKILL.md body lean.
- **Named events** — every `implement` mode must append a named event to `tracking.yaml` via `hi ingest` / `hi promote` (never raw YAML writes).

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
| FR-016 | `hi ingest` CLI delegation pattern present |
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

## Branches & Commits

- Feature branches: `00N-<spec-name>` (e.g., `003-hi-discovery`)
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- All tests must pass before merging; skill tests must have zero FAIL-level findings

## Further Reading

- [Workflow](docs/WORKFLOW.md) — artifact lifecycle and many-to-many topology
- [Skill Authoring Guide](docs/SKILL_AUTHORING.md) — detailed per-step instructions
- [Command Reference](docs/COMMANDS.md) — full `hi` CLI reference
- [002 Spec](specs/002-hi-agent-skills/spec.md) — framework requirements (FRs, NFRs)
- [002 Data Model](specs/002-hi-agent-skills/data-model.md) — tracking.yaml schema, event types, state machine
