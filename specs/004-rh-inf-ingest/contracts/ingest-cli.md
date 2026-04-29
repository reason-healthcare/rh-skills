# CLI Contract: `rh-skills ingest`

**Phase 1 Design Artifact** | **Branch**: `004-rh-inf-ingest`

---

## Command Group

`rh-skills ingest` owns deterministic source registration and enrichment.

Subcommands in scope for 004:
- `plan`
- `list-manual`
- `implement`
- `normalize`
- `classify`
- `annotate`
- `verify`

---

## `rh-skills ingest plan [<topic>]` (skill-level summary)

**Purpose**: Render a transient pre-flight summary for ingest readiness.

**Behavior**:
- Scans `sources/` via `rh-skills ingest list-manual [<topic>]`
- Reports:
  - untracked files requiring registration
  - already-registered sources
  - tool availability (`pdftotext`, `pandoc`)
- Makes no file or tracking writes

---

## `rh-skills ingest list-manual [<topic>]`

**Purpose**: List files in `sources/` that are not yet registered in `tracking.yaml`.

```bash
rh-skills ingest list-manual [<topic>]
```

**Behavior**:
- Scans `sources/` directory
- Compares against `tracking.yaml` registered sources
- If `<topic>` is provided, filters to sources belonging to that topic
- Emits per-file `rh-skills ingest implement sources/<file>` commands for each untracked file
- If all sources are already registered, outputs: `✓ No untracked files in sources/`

**Exit codes**:
- `0` success (whether or not untracked files exist)
- non-zero for invalid topic or tracking.yaml errors

---

## `rh-skills ingest implement FILE`

```bash
rh-skills ingest implement <file>
```

**Behavior**:
- Copies the file into `sources/`
- Computes SHA-256
- Registers the source in `tracking.yaml`

**Exit codes**:
- `0` success
- non-zero for invalid or missing file

---

## Registration Step Requirement

Registration is explicit and must happen before normalization.

Recommended sequence:
1. Run `rh-skills ingest list-manual [<topic>]` to identify untracked files.
2. Run `rh-skills ingest implement sources/<file> [--topic <topic>]` for each file reported.
3. Proceed to `rh-skills ingest normalize ...` only after required files are registered.

---

## `rh-skills ingest normalize FILE --topic TOPIC [--name NAME]`

```bash
rh-skills ingest normalize <file> --topic <topic> [--name <source-name>]
```

**Behavior**:
- Writes `sources/normalized/<name>.md`
- Chooses normalization strategy by file extension:
  - `.pdf` → `pdftotext` when available
  - `.doc`, `.docx`, `.xlsx` → `pandoc` when available
  - `.html`, `.htm` → `markdownify`
  - text/markdown → direct read
- Writes YAML frontmatter with provenance/extraction metadata
- Updates `tracking.yaml` with `normalized` and `text_extracted`

**Exit codes**:
- `0` success or soft-success with `text_extracted: false`
- non-zero for invalid input path

---

## `rh-skills ingest classify NAME --topic TOPIC --type TYPE --evidence-level LEVEL [--tags CSV]`

```bash
rh-skills ingest classify <name> --topic <topic> --type <type> --evidence-level <level> [--tags <csv>]
```

**Behavior**:
- Writes classification metadata to the matching `tracking.yaml` source record
- Adds `source_classified` event

**Validation**:
- `TYPE` must be in the source taxonomy
- `LEVEL` must be in the evidence-level taxonomy

---

## `rh-skills ingest annotate NAME --topic TOPIC --concept NAME:TYPE [--concept NAME:TYPE ...]`

```bash
rh-skills ingest annotate <name> --topic <topic> --concept <concept[:type]>...
```

**Behavior**:
- Requires `sources/normalized/<name>.md` to exist
- Writes `concepts[]` into normalized frontmatter
- Creates or updates `topics/<topic>/process/concepts.yaml`
- De-dupes concept entries by canonical name and appends source backlinks
- Adds `source_annotated` event and updates `concept_count`

---

## `rh-skills ingest verify`

```bash
rh-skills ingest verify
```

**Behavior**:
- Re-checks all registered source files against stored checksums
- Reports `OK`, `CHANGED`, or `MISSING`
- Makes no file or tracking writes

**Exit codes**:
- `0` all sources unchanged
- `1` at least one source changed or missing
