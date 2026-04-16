# rh-skills CLI — Command Reference

All commands are invoked as `rh-skills <command> [options] [args]`.

---

## `rh-skills init`

Initialize a new clinical topic.

```
rh-skills init <name> [--title TITLE] [--author AUTHOR]
```

**Arguments:**
- `name` — Topic identifier (kebab-case, e.g., `diabetes-screening`)

**Options:**
- `--title` — Human-readable title (default: name)
- `--author` — Author name

**Creates:**
```
topics/<name>/
  structured/
  computable/
  process/
    plans/tasks.md
    notes.md
    contracts/  checklists/  fixtures/fixtures/results/
```

Updates `tracking.yaml` with the new topic entry.

---

## `rh-skills list`

List all topics in the repository.

```
rh-skills list [--json] [--stage STAGE]
```

**Options:**
- `--json` — Output as JSON array
- `--stage` — Filter by lifecycle stage: `initialized`, `l1-discovery`, `l2-semi-structured`, `l3-computable`

**Example:**
```bash
rh-skills list
rh-skills list --stage l2-semi-structured
rh-skills list --json
```

---

## `rh-skills status`

Show workflow state of a topic. Subcommands: `show`, `progress`, `next-steps`, `check-changes`.

### `rh-skills status show <topic>`

Basic lifecycle summary with deterministic next-step bullets.

```
rh-skills status show <topic> [--json]
```

### `rh-skills status progress <topic>`

Detailed progress report with completeness percentage, stage pipeline, and deterministic next-step bullets.

```
rh-skills status progress <topic>
```

### `rh-skills status next-steps <topic>`

Recommend deterministic next-step bullets for the topic.

```
rh-skills status next-steps <topic>
```

**Example output:**
```
Topic: diabetes-screening

Next steps:
  - Extract structured (L2) artifacts from ingested sources: rh-inf-extract plan diabetes-screening
  - Check whether any source files have changed since ingest: rh-skills status check-changes diabetes-screening
```

### `rh-skills status check-changes <topic>`

Re-checksum all registered sources and report drift. Lists downstream structured and computable artifacts that may be stale, then emits deterministic remediation bullets.

```
rh-skills status check-changes <topic>
```

**Exit codes:** 0 = all sources unchanged, 1 = one or more sources changed or missing.

---

## `rh-skills ingest`

Register and track raw L1 source artifacts.

### `rh-skills ingest plan`

Generate an ingest plan template at `plans/ingest-plan.md`.

```
rh-skills ingest plan
```

Creates `plans/ingest-plan.md` with YAML front matter listing sources to register. Edit the file before running `implement`.

### `rh-skills ingest implement <file>`

Copy a file to `sources/` and register it in `tracking.yaml`.

```
rh-skills ingest implement <file>
```

**Records:** file path, detected type, SHA-256 checksum, ISO 8601 timestamp.

**Supported types:** PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), URLs.

**Optional tools:** `pdftotext` (poppler) for PDF text extraction; `pandoc` for Word/Excel. If absent, metadata and checksum are registered but text extraction is skipped (warning emitted).

### `rh-skills ingest verify`

Confirm all registered sources are unchanged.

```
rh-skills ingest verify
```

Re-checksums all sources in `tracking.yaml` and reports `✓ OK` or `✗ CHANGED / MISSING`.

**Exit codes:** 0 = all OK, 1 = any mismatch.

---

## `rh-skills promote`

Derive and combine artifacts.

### `rh-skills promote derive <topic> <name>`

Create a structured (L2) artifact scaffold.

```
rh-skills promote derive <topic> <name>
```

Creates `topics/<topic>/structured/<name>.yaml` with schema-valid YAML scaffold.

### `rh-skills promote combine <topic> <sources…> <target>`

Merge structured (L2) artifacts into a computable (L3) artifact.

```
rh-skills promote combine <topic> screening-criteria risk-factors <target-name>
```

Creates `topics/<topic>/computable/<target-name>.yaml`.

### `rh-skills promote formalize-plan <topic> [--force]`

Write the 006 formalize review packet from approved, valid structured inputs.

```
rh-skills promote formalize-plan <topic> [--force]
```

- writes `topics/<topic>/process/plans/formalize-plan.md`
- selects only extract-approved structured artifacts that still pass validation
- proposes one primary pathway-oriented computable package
- records `formalize_planned` on success
- warns and exits without writing when no eligible structured inputs are available
- refuses to overwrite an existing plan unless `--force` is passed

---

## `rh-skills validate`

Two modes: discovery-plan validation (L1) and artifact schema validation (L2/L3).

### Discovery plan validation (`--plan`)

Validate a `discovery-plan.yaml` before handing off to `rh-inf-ingest`:

```
rh-skills validate --plan <path>
rh-skills validate --plan -                          # read from stdin
cat discovery-plan.yaml | rh-skills validate --plan -
```

Checks: YAML structure, required fields per source entry, evidence level vocabulary,
source type taxonomy, source count (5–25), presence of a `terminology` source.

Add `--check-urls` to HTTP-verify every source URL (requires network):

```
rh-skills validate --plan discovery-plan.yaml --check-urls
```

**Output:** Errors (blocking, exit 1) and warnings (advisory, exit 0).

See valid field values with `rh-skills schema show discovery-plan`.

### Artifact schema validation

Schema-validate a named L2 or L3 artifact:

```
rh-skills validate <topic> <level> <artifact>
```

**Output:** Required-field errors (blocking, exit 1) and optional-field warnings (advisory, exit 0).

When `topics/<topic>/process/plans/formalize-plan.md` exists, is approved, and
lists the artifact as the implementation target, validation also checks:
- approved `input_artifacts[]` vs `converged_from[]`
- required computable sections from the approved plan
- minimum completeness for section types such as pathways, actions, value sets, measures, libraries, and assessments

---

## `rh-skills schema`

Show schemas and valid vocabularies for RH Skills artifacts.

```
rh-skills schema show <type>
rh-skills schema show <type> --json
```

Types:

| Type | Description |
|---|---|
| `discovery-plan` | Fields, valid source types, evidence levels, and validation rules for `discovery-plan.yaml` |
| `l2` / `structured` | Required and optional fields for L2 structured artifacts |
| `l3` / `computable` | Required and optional fields for L3 computable artifacts |

Use during discovery to understand required source fields before writing a plan:

```
rh-skills schema show discovery-plan
```

---

## Curated skill entry points

These reviewer-facing skill invocations sit above the deterministic `rh-skills`
CLI commands.

### `rh-inf-verify <topic>`

Run unified, read-only topic verification across the lifecycle.

```bash
rh-inf-verify verify <topic>
```

- determines which lifecycle stages are applicable for the topic
- launches the applicable stage-specific verify workflows
- preserves stage-attributed failures, warnings, and invocation problems
- reports later stages explicitly as `not-yet-ready` or `not-applicable`
- does not create files or update `tracking.yaml`

---

## `rh-skills tasks`

Per-topic task tracking via `tasks.md`.

### `rh-skills tasks list [<topic>]`

```
rh-skills tasks list                    # root plans/tasks.md
rh-skills tasks list diabetes-screening # topics/<name>/process/plans/tasks.md
```

### `rh-skills tasks add <topic> <task>`

```
rh-skills tasks add diabetes-screening "Review screening criteria with cardiologist"
```

### `rh-skills tasks complete <topic> <task-id>`

```
rh-skills tasks complete diabetes-screening 1
```

---

## `rh-skills test`

Run a skill against topic fixtures.

```
rh-skills test <topic> <skill>
```

Runs the named skill against fixture inputs in `topics/<topic>/process/fixtures/` and writes results to `topics/<topic>/process/fixtures/results/`.

**Example:**
```bash
rh-skills test diabetes-screening rh-inf-extract
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | User error (missing file, validation failure, checksum mismatch) |
| `2` | Usage error (bad arguments, unknown topic) |
