# Data Model: rh-cql — First-Class CQL Authoring Skill

**Branch**: `014-rh-cql-skill` | **Phase**: 1

---

## 1. New skill artifact: `skills/.curated/rh-cql/`

### `SKILL.md` structure

```
Frontmatter (name, description, compatibility)
## User Input
## Mode: author
  - Inputs: L2 structured artifact YAML from structured/
  - Authoring rubric (10 areas)
  - Style guide
  - CQL structure template (library header, valueset declarations, context Patient, defines)
  - CLI boundary: rh-skills formalize for file write
  - Output contract: .cql file + FHIR Library JSON
## Mode: review
  - Inputs: existing .cql file path
  - Authoring rubric check (all 10)
  - High-risk pattern catalog (all 7)
  - Packaging rubric check
  - Output contract: review report Markdown
## Mode: debug
  - Inputs: .cql file + error (translator output OR failing test OR runtime description)
  - Error taxonomy: authoring vs environment
  - Output contract: diagnosis report + minimal patch suggestion
## Mode: test-plan
  - Inputs: .cql file
  - Test family matrix per define statement
  - Fixture skeleton structure
  - Output contract: test plan Markdown + fixture skeletons
## Standards corpus summary (inline quick-reference)
## CLI commands (deterministic boundary)
## MCP tools used (reasonhub search/lookup)
## Human-in-the-loop rules
```

### `reference.md` structure

Organized by corpus layer:

| Layer | Sources | URLs |
|-------|---------|------|
| 1 — Core CQL | CQL 1.5.3 Spec, Author's Guide, Developer's Guide, ELM, Grammar | https://cql.hl7.org/ |
| 2 — FHIR-facing | FHIR Clinical Reasoning, Using CQL with FHIR IG, FHIRHelpers, ModelInfo | https://build.fhir.org/ |
| 3 — Packaging | CRMI, Quality Measure IG using-CQL | https://build.fhir.org/ig/HL7/ |
| 4 — Tooling | CQFramework clinical_quality_language, AHRQ CQL Testing Framework | https://github.com/ |

### `examples/` layout

```
examples/
├── author-example/
│   ├── plan.md     # Input: L2 measure artifact excerpt, task description
│   └── output.md   # Output: full CQL library + rubric check results
└── review-example/
    ├── plan.md     # Input: a CQL library with 2-3 known issues
    └── output.md   # Output: review report with BLOCKING/ADVISORY/INFO findings
```

---

## 2. New CLI command group: `src/rh_skills/commands/cql.py`

### Command group structure

```python
@click.group("cql")
def cql_group(): ...

@cql_group.command("validate")
@click.argument("topic")
@click.argument("library")
def validate(topic, library):
    """Validate a .cql file using rh cql validate."""
    # 1. Resolve .cql path: topics/<topic>/computable/<library>.cql
    # 2. Resolve rh binary from RH_CLI_PATH / config / PATH
    # 3. subprocess.run(["rh", "cql", "validate", cql_path])
    # 4. Echo stdout/stderr; exit non-zero on errors

@cql_group.command("translate")
@click.argument("topic")
@click.argument("library")
def translate(topic, library):
    """Compile a .cql file to ELM JSON using rh cql compile."""
    # 1. Resolve .cql path
    # 2. Resolve rh binary
    # 3. subprocess.run(["rh", "cql", "compile", cql_path, "--output", computable_dir])
    # 4. Echo output path

@cql_group.command("test")
@click.argument("topic")
@click.argument("library")
def test(topic, library):
    """Run fixture-based test cases using rh cql eval."""
    # 1. Discover tests/cql/<library>/case-*/ directories
    # 2. Resolve rh binary
    # 3. For each case: load expected/expression-results.json
    # 4. For each expression key: run rh cql eval <lib.cql> --expr <name> --data input/bundle.json
    # 5. Diff actual stdout vs expected value
    # 6. Report PASS/FAIL per case; exit non-zero on any failure
```

### Config keys to add to `common.py`

```python
_CONFIG_KEYS additions:
    "RH_CLI_PATH",   # path to `rh` binary (default: "rh" on $PATH)
```

### TOML mapping to add to `_load_config_file()`

```toml
[cql]
rh_cli_path = "/Users/me/.cargo/bin/rh"  # optional; defaults to `rh` on PATH
```

---

## 3. CLI entry point registration

In `src/rh_skills/cli.py` (or equivalent), add:

```python
from rh_skills.commands.cql import cql_group
cli.add_command(cql_group)
```

---

## 4. `formalize.py` changes

**Remove** (lines ~355–376):
```python
# Generate CQL stub if strategy involves Library
if strategy.get("supporting") and "Library" in strategy["supporting"]:
    cql_name = "".join(...) + "Logic"
    cql_fname = f"{cql_name}.cql"
    cql_path = computable_dir / cql_fname
    if not cql_path.exists() or force:
        cql_content = (f'library {cql_name} version \'1.0.0\'\n' ...)
        cql_path.write_text(cql_content)
        ...
```

**Replace with**:
```python
# CQL content is authored by the rh-cql skill (author mode).
# See skills/.curated/rh-cql/SKILL.md for the authoring workflow.
# rh-skills formalize writes the FHIR Library wrapper once CQL is present.
```

---

## 5. `rh-inf-formalize/SKILL.md` boundary documentation

Add to the Implement section, before the `rh-skills formalize` step:

```markdown
> **CQL boundary**: For artifact types that produce a CQL Library (`measure`,
> `decision-table`, `policy`), author the `.cql` file first using the `rh-cql`
> skill in `author` mode. Then run `rh-skills formalize` which wraps the CQL
> in the FHIR Library JSON. Do NOT generate CQL inline within formalize.
```

---

## 6. File path reference table

| Artifact | Path |
|----------|------|
| CQL source | `topics/<topic>/computable/<library-name>.cql` |
| ELM JSON | `topics/<topic>/computable/<library-name>.json` |
| FHIR Library wrapper | `topics/<topic>/computable/Library-<artifact>.json` |
| Review report | `topics/<topic>/process/reviews/<library-name>-review.md` |
| Test plan | `topics/<topic>/process/test-plans/<library-name>-test-plan.md` |
| Test fixture cases | `tests/cql/<library-name>/case-NNN-<description>/` |

---

## 7. Test coverage plan

| Area | Test file | Key assertions |
|------|-----------|----------------|
| `cql validate` — `rh` present, no errors | `tests/unit/test_cql.py` | exit 0, "0 errors" in output |
| `cql validate` — `rh` present, errors | `tests/unit/test_cql.py` | exit non-zero, error summary in stdout |
| `cql validate` — `rh` binary absent | `tests/unit/test_cql.py` | exit non-zero, install hint in output |
| `cql translate` — success | `tests/unit/test_cql.py` | ELM file created, path echoed |
| `cql test` — all cases pass | `tests/unit/test_cql.py` | PASS per case, exit 0 |
| `cql test` — one case fails | `tests/unit/test_cql.py` | FAIL summary, exit non-zero |
| `rh-cql` skill schema | `tests/skills/test_skill_schema.py` | auto-discovered via parametrize |
| `rh-cql` audit — four modes defined | `tests/skills/test_skill_audit.py` | new `TestRhCqlSkillContract` class |
| `rh-cql` audit — reference.md has all 4 corpus layers | `tests/skills/test_skill_audit.py` | URL presence check |
| formalize — no CQL stub generation | `tests/unit/test_formalize.py` (new) | `.cql` not created by formalize alone |

---

## 8. CLI entry point discovery

```bash
# Verify entry point (once registered):
rh-skills cql --help
rh-skills cql validate --help
rh-skills cql translate --help
rh-skills cql test --help
```
