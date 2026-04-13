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

Basic lifecycle summary.

```
rh-skills status show <topic> [--json]
```

### `rh-skills status progress <topic>`

Detailed progress report with completeness percentage and stage pipeline.

```
rh-skills status progress <topic>
```

### `rh-skills status next-steps <topic>`

Recommend the single most important next action with the exact command to run.

```
rh-skills status next-steps <topic>
```

**Example output:**
```
Topic: diabetes-screening

Recommended next step:
  Extract structured (L2) artifacts from ingested sources

Run:
  rh-inf-extract plan
```

### `rh-skills status check-changes <topic>`

Re-checksum all registered sources and report drift. Lists downstream structured artifacts that may be stale.

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

---

## `rh-skills validate`

Schema-validate any named artifact.

```
rh-skills validate <topic> <artifact>
```

**Output:** Required-field errors (blocking, exit 1) and optional-field warnings (advisory, exit 0).

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
