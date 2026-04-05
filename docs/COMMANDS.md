# HI CLI — Command Reference

All commands are invoked as `hi <command> [options] [args]`.

---

## `hi init`

Initialize a new clinical topic.

```
hi init <name> [--title TITLE] [--author AUTHOR]
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

## `hi list`

List all topics in the repository.

```
hi list [--json] [--stage STAGE]
```

**Options:**
- `--json` — Output as JSON array
- `--stage` — Filter by lifecycle stage: `initialized`, `l1-discovery`, `l2-semi-structured`, `l3-computable`

**Example:**
```bash
hi list
hi list --stage l2-semi-structured
hi list --json
```

---

## `hi status`

Show workflow state of a topic. Subcommands: `show`, `progress`, `next-steps`, `check-changes`.

### `hi status show <topic>`

Basic lifecycle summary.

```
hi status show <topic> [--json]
```

### `hi status progress <topic>`

Detailed progress report with completeness percentage and stage pipeline.

```
hi status progress <topic>
```

### `hi status next-steps <topic>`

Recommend the single most important next action with the exact command to run.

```
hi status next-steps <topic>
```

**Example output:**
```
Topic: diabetes-screening

Recommended next step:
  Extract structured (L2) artifacts from ingested sources

Run:
  hi-extract plan
```

### `hi status check-changes <topic>`

Re-checksum all registered sources and report drift. Lists downstream structured artifacts that may be stale.

```
hi status check-changes <topic>
```

**Exit codes:** 0 = all sources unchanged, 1 = one or more sources changed or missing.

---

## `hi ingest`

Register and track raw L1 source artifacts.

### `hi ingest plan`

Generate an ingest plan template at `plans/ingest-plan.md`.

```
hi ingest plan
```

Creates `plans/ingest-plan.md` with YAML front matter listing sources to register. Edit the file before running `implement`.

### `hi ingest implement <file>`

Copy a file to `sources/` and register it in `tracking.yaml`.

```
hi ingest implement <file>
```

**Records:** file path, detected type, SHA-256 checksum, ISO 8601 timestamp.

**Supported types:** PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), URLs.

**Optional tools:** `pdftotext` (poppler) for PDF text extraction; `pandoc` for Word/Excel. If absent, metadata and checksum are registered but text extraction is skipped (warning emitted).

### `hi ingest verify`

Confirm all registered sources are unchanged.

```
hi ingest verify
```

Re-checksums all sources in `tracking.yaml` and reports `✓ OK` or `✗ CHANGED / MISSING`.

**Exit codes:** 0 = all OK, 1 = any mismatch.

---

## `hi promote`

Derive and combine artifacts.

### `hi promote derive <topic> <name>`

Create a structured (L2) artifact scaffold.

```
hi promote derive <topic> <name>
```

Creates `topics/<topic>/structured/<name>.yaml` with schema-valid YAML scaffold.

### `hi promote combine <topic> <sources…> <target>`

Merge structured (L2) artifacts into a computable (L3) artifact.

```
hi promote combine <topic> screening-criteria risk-factors <target-name>
```

Creates `topics/<topic>/computable/<target-name>.yaml`.

---

## `hi validate`

Schema-validate any named artifact.

```
hi validate <topic> <artifact>
```

**Output:** Required-field errors (blocking, exit 1) and optional-field warnings (advisory, exit 0).

---

## `hi tasks`

Per-topic task tracking via `tasks.md`.

### `hi tasks list [<topic>]`

```
hi tasks list                    # root plans/tasks.md
hi tasks list diabetes-screening # topics/<name>/process/plans/tasks.md
```

### `hi tasks add <topic> <task>`

```
hi tasks add diabetes-screening "Review screening criteria with cardiologist"
```

### `hi tasks complete <topic> <task-id>`

```
hi tasks complete diabetes-screening 1
```

---

## `hi test`

Run a skill against topic fixtures.

```
hi test <topic> <skill>
```

Runs the named skill against fixture inputs in `topics/<topic>/process/fixtures/` and writes results to `topics/<topic>/process/fixtures/results/`.

**Example:**
```bash
hi test diabetes-screening hi-extract
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | User error (missing file, validation failure, checksum mismatch) |
| `2` | Usage error (bad arguments, unknown topic) |
