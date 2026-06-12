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
    fixtures/  fixtures/results/
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

Print the canonical read-only ingest pre-flight summary.

```
rh-skills ingest plan [<topic>]
```

Reports untracked files in `sources/`, prints the exact `rh-skills ingest implement ...`
commands needed to register them, and checks normalization tool availability.

### `rh-skills ingest implement <file>`

Copy a file to `sources/` and register it in `tracking.yaml`.

```
rh-skills ingest implement <file>
```

**Records:** file path, inferred registration type, SHA-256 checksum, ISO 8601 timestamp.

**Supported types:** PDF (`.pdf`), Word (`.docx`), Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), HTML/XML and other local file types.

`rh-skills ingest implement` does not accept `--type`. Local-file registration
infers an initial type hint from the file extension; `rh-skills ingest classify`
remains the authoritative place to set final source type and evidence metadata.

Use `rh-skills ingest plan [<topic>]` as the primary pre-flight summary.
Use `rh-skills ingest list-manual [<topic>]` when you want only the raw
untracked-file inventory and registration commands.

### `rh-skills ingest list-manual [<topic>]`

List files in `sources/` that are not yet registered in `tracking.yaml`.

```
rh-skills ingest list-manual [<topic>]
```

Outputs each untracked file and a corresponding `rh-skills ingest implement sources/<file> [--topic <topic>]` command.

### `rh-skills source download --url <url> --name <name>`

Download a URL to `sources/` and register it in `tracking.yaml`.

```
rh-skills source download --url <url> --name <name> [--type <source-type>] [--topic <topic>]
```

Use this command (not `ingest implement`) for URL-based acquisition.
`--type` persists an initial source-type hint at registration time; later
`rh-skills ingest classify` remains the authoritative classification step.

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

### `rh-skills promote derive artifact <topic> <name>`

Create a structured (L2) artifact scaffold.

```sh
rh-skills promote derive artifact <topic> <name> [--force]
```

Creates `topics/<topic>/structured/<name>.yaml` with schema-valid YAML scaffold.
When `--body-file` is provided, the YAML body is written verbatim and must
already contain all required L2 fields. In that mode, repeated content flags
such as `--clinical-question`, `--required-section`, `--evidence-ref`, and
`--concern` are treated as consistency checks rather than merge inputs.

Use `--force` to re-derive only a non-terminology artifact in place. This
overwrites the existing `structured/<name>/<name>.yaml` file and refreshes its
tracking entry without re-running terminology review/write. The explicit
terminology package `concepts` is not re-derived with this command; use
`rh-skills promote concept write <topic>` instead. When terminology has not
changed, leave `concept review` / `concept write` as-is and validate only the
artifact you re-ran.

### `rh-skills promote derive pathway --from-decision-table <artifact>`

Generate a fallback `care-pathway` scaffold from a `decision-table` that already
has `sections.pathway_phases[]`.

```sh
rh-skills promote derive pathway --from-decision-table <decision-table-id> [--pathway-id <id>] [--force]
```

Use this only when direct care-pathway authoring is having trouble keeping
recommendation linkage aligned with the paired decision-table. It is a repair
and fallback tool, not the primary authoring path.

The generated artifact:

- uses the flat `steps[]` + `parent_id` care-pathway model
- mirrors the decision-table phase model
- copies phase-aligned `rule_id` / `rule_ids[]`, `action_labels`, and
  `evidence_traceability_ids[]` when available
- still requires human review before use

### `rh-skills promote combine <topic> <sources…> <target>`

> **Deprecated** — Use `rh-skills formalize` for individual FHIR JSON generation
> and `rh-skills package` for FHIR NPM packaging.

Merge structured (L2) artifacts into a computable (L3) artifact.

```
rh-skills promote combine <topic> screening-criteria risk-factors <target-name>
```

Creates `topics/<topic>/computable/<target-name>.yaml`.

### `rh-skills promote plan <topic> [--force]`

Write the extract review packet from normalized sources.

```
rh-skills promote plan <topic> [--force]
```

- writes `topics/<topic>/process/plans/extract-plan.yaml` and `extract-plan-readout.md`
- groups normalized sources by inferred artifact type
- optionally writes `concepts-plan.yaml` and `concepts-plan-readout.md` when frontmatter concepts are found
- records `extract_planned` event in `tracking.yaml`
- refuses to overwrite an existing plan unless `--force` is passed

### `rh-skills promote approve <topic>`

Record reviewer decisions on `extract-plan.yaml` artifacts.

```
rh-skills promote approve <topic> [OPTIONS]
```

**Options:**
- `--artifact NAME` — Artifact name to set decision on (non-interactive)
- `--decision approved|rejected|needs-revision` — Decision for `--artifact`
- `--notes TEXT` — Approval notes (used with `--artifact`)
- `--add-concern TEXT` — Append a concern to the artifact's concerns list (repeatable)
- `--add-source SLUG` — Add a missing source slug to the artifact's source_files list (repeatable)
- `--reviewer NAME` — Reviewer name written to plan header
- `--review-summary TEXT` — Plan-level review summary written to `extract-plan.yaml`
- `--finalize` — Set plan status to `approved` and record reviewer/timestamp

**Behavior:**
- Reads `extract-plan.yaml` for the topic
- Sets `reviewer_decision` on the named artifact (or enters interactive mode if `--artifact` is omitted)
- `--finalize` seals the plan (`status: approved`) — required before `rh-inf-extract implement` can run

### `rh-skills promote concept <subcommand>`

Manage concept coding review for a topic.

| Subcommand | Purpose |
|---|---|
| `add` | Add a custom concept placeholder not extracted from source documents |
| `enrich` | Record RH MCP code candidates for a concept |
| `review` | Set approved/excluded decisions per concept or per code; finalize |
| `write` | Write `concepts.yaml` from the finalized review CSV |

#### `rh-skills promote concept enrich <topic>`

Record RH MCP code candidates for a concept in the review CSV.

```
rh-skills promote concept enrich <topic> [OPTIONS]
```

**Arguments:**
- `CONCEPT` *(required)* — Concept name to enrich
- `--type TYPE` — Concept type to disambiguate when the name is ambiguous
- `--candidate system|code|display[|distance[|confidence]]` — Candidate code to record; repeatable; pass once per candidate
- `--lookup-query TEXT` — Search query used (defaults to concept name)
- `--lookup-notes TEXT` — Notes when MCP returned no results
- `--reset` — Clear existing candidate rows for the concept and restore placeholder

**Behavior:**
- Appends candidate rows to `concepts-review.csv` for the named concept
- Omit `--candidate` (without `--reset`) to record lookup metadata with no results
- Call once per candidate; pass multiple `--candidate` flags in a single call to add several at once

#### `rh-skills promote concept review <topic>`

Set `approved (y/n)` on code rows and optionally finalize the review.

```
rh-skills promote concept review <topic> [OPTIONS]
```

**Arguments:**
- `CONCEPT` *(optional)* — Concept name to update
- `--approve-all` — Set `include/exclude = include` on all **candidate** rows for the concept (does not affect related or expansion rows)
- `--exclude-all` — Set `include/exclude = exclude` on all **candidate** rows for the concept
- `--approve-code CODE` — Set `include/exclude = include` on the **candidate** row matching this code; repeatable
- `--exclude-code CODE` — Set `include/exclude = exclude` on the **candidate** row matching this code; repeatable
- `--approve-related PARENT|RELATED` — Set `include/exclude = include` on the related row identified by the parent code and related code pair; repeatable
- `--exclude-related PARENT|RELATED` — Set `include/exclude = exclude` on the matching related row; repeatable
- `--approve-expansion SYSTEM|EXPRESSION` — Set `include/exclude = include` on the expansion row identified by system + expression; repeatable
- `--exclude-expansion SYSTEM|EXPRESSION` — Set `include/exclude = exclude` on the matching expansion row; repeatable
- `--note TEXT` — Set comment on the first **candidate** row for the concept
- `--finalize` — Seal the review (`status: approved`). **Does NOT write `concepts.yaml`** — run `concept write` during implement for that. Can be used alone or with a `CONCEPT` argument
- `--reviewer NAME` — Reviewer name. Required for `--finalize`
- `--force` — Bypass the checksum unchanged warning during `--finalize`

**Behavior:**
- Updates `include/exclude` on code rows in the per-concept CSVs under `topics/<topic>/process/plans/concepts/`
- `--finalize` seals the packet (`status: approved`) but does **not** write `concepts.yaml`; run `rh-skills promote concept write <topic>` separately during implement
- Finalize gate: every **candidate** row must have `include/exclude` set to `include` or `exclude` before finalize succeeds; related and expansion rows may remain blank

**Examples:**
```bash
# Approve all candidate rows for a concept:
rh-skills promote concept review diabetes-screening \
  "Hypertension" --approve-all

# Exclude all candidate rows for a concept:
rh-skills promote concept review diabetes-screening \
  "Hypertension" --exclude-all

# Approve one specific candidate code, exclude another:
rh-skills promote concept review diabetes-screening \
  "Hypertension" --approve-code 38341003 --exclude-code I10

# Approve a specific related row (PARENT_CODE|RELATED_CODE):
rh-skills promote concept review diabetes-screening \
  "Hypertension" --approve-related "38341003|59621000"

# Approve a specific expansion row (SYSTEM|EXPRESSION):
rh-skills promote concept review diabetes-screening \
  "Hypertension" --approve-expansion "http://snomed.info/sct|<<38341003"

# Approve with a note, then finalize:
rh-skills promote concept review diabetes-screening \
  "Last concept" --approve-all --note "FSN confirmed" \
  --finalize --reviewer "taylor" --force

# Standalone finalize after manual CSV edits:
rh-skills promote concept review diabetes-screening \
  --finalize --reviewer "taylor"
```

#### `rh-skills promote concept write <topic>`

Write `topics/<topic>/structured/concepts.yaml` from the finalized concept review CSV.

```
rh-skills promote concept write <topic>
```

**Behavior:**
- Requires concept review to be finalized (`status: approved` in `concepts-review-meta.yaml`)
- All concepts appear in `concepts.yaml`; only those with at least one `approved (y/n) = y` row get a `codes` list
- Registers the artifact in `tracking.yaml`
- Call this during **implement mode** after the extract plan is approved; it is a **separate step** from `concept review --finalize`

### `rh-skills promote concerns <topic>`

List open (unresolved) concerns across extract and formalize plans.

```
rh-skills promote concerns <topic>
```

**Behavior:**
- Scans both `extract-plan.yaml` and `formalize-plan.yaml` (whichever exist)
- Reports every concern/conflict entry whose resolution field is empty or absent
- Exit code 0 in all cases; use the output to decide whether to proceed
- Use `resolve-concern` to record a resolution

### `rh-skills promote resolve-concern <topic>`

Record the resolution for a specific concern entry.

```
rh-skills promote resolve-concern <topic> [OPTIONS]
```

**Options:**
- `--artifact NAME` *(required)* — Name of the artifact containing the concern
- `--index N` *(required)* — 0-based index of the concern entry within the artifact's concerns list
- `--resolution TEXT` *(required)* — Resolution text to record
- `--plan extract|formalize` *(required)* — Which plan file to update

**Example:**
```bash
# List open concerns first:
rh-skills promote concerns diabetes-ccm

# Then resolve by plan/artifact/index:
rh-skills promote resolve-concern diabetes-ccm \
  --plan extract --artifact screening-decisions --index 0 \
  --resolution "ADA 2024 is the primary guideline; USPSTF framing is supplementary."
```

### `rh-skills promote formalize-plan <topic> [--force]`

Write the 006 formalize review packet from approved, valid structured inputs.

```
rh-skills promote formalize-plan <topic> [--force]
```

- writes `topics/<topic>/process/plans/formalize-plan.yaml`
- selects only extract-approved structured artifacts that still pass validation
- creates per-type artifacts using the appropriate L2→L3 strategy
- detects overlapping FHIR resource types across artifacts and flags for review
- records `formalize_planned` on success
- warns and exits without writing when no eligible structured inputs are available
- refuses to overwrite an existing plan unless `--force` is passed

---

## `rh-skills formalize`

Generate FHIR R4 JSON and CQL from an approved L2 structured artifact.

```
rh-skills formalize <topic> <artifact> [--strategy TYPE] [--dry-run]
```

**Arguments:**
- `topic` — Topic name
- `artifact` — Name of the structured artifact to formalize

**Options:**
- `--strategy` — Override the auto-detected L2 type strategy (one of: `evidence-summary`, `decision-table`, `care-pathway`, `terminology`, `measure`, `assessment`, `policy`)
- `--dry-run` — Show what would be generated without writing files

**Behavior:**
- Reads the approved formalize-plan for the artifact's strategy and l3_targets
- Matches `<artifact>` to the approved plan entry's `source_artifact` field
- Applies the type-specific conversion strategy from SKILL.md/reference.md
- Writes FHIR JSON resources to `topics/<topic>/computable/`
- Writes CQL libraries as `.cql` files alongside the JSON
- Records `computable_converged` event in tracking.yaml

**Strategy → Output:**

| L2 Type | Primary Output | Supporting Output |
|---------|---------------|-------------------|
| evidence-summary | Evidence.json | EvidenceVariable.json, Citation.json |
| decision-table | PlanDefinition.json | ActivityDefinition.json, Library.json, .cql |
| care-pathway | PlanDefinition.json | ActivityDefinition.json |
| terminology | ValueSet.json | ConceptMap.json |
| measure | Measure.json | Library.json, .cql |
| assessment | Questionnaire.json | Library.json (scoring) |
| policy | PlanDefinition.json | Questionnaire.json (DTR) |

**Example:**
```bash
rh-skills formalize diabetes-screening screening-criteria
rh-skills formalize diabetes-screening lab-values --strategy terminology
```

---

## `rh-skills formalize-config`

Configure FHIR/CQL artifact metadata for a topic.

```
rh-skills formalize-config <topic> [OPTIONS]
```

**Arguments:**
- `topic` — Topic name

**Options:**
- `--non-interactive` — Accept all suggested defaults without prompting
- `--name NAME` — PascalCase IG name override (default: derived from topic slug)
- `--id ID` — Kebab-case ID override (default: topic slug)
- `--canonical URL` — Base canonical URL (default: `http://example.org/fhir`)
- `--status STATUS` — FHIR publication status: `draft`, `active`, `retired`, `unknown` (default: `draft`)
- `--version VERSION` — SemVer version (default: `0.1.0`)
- `--force` — Overwrite existing config without prompting

**Behavior:**
- Creates (or updates) `topics/<topic>/process/formalize-config.yaml`
- Values drive all FHIR and CQL artifact generation:
  - `resource.url` = `{canonical}/{ResourceType}/{id}`
  - `resource.version` = `version`
  - `resource.status` = `status`
  - ImplementationGuide: `name`, `id`, `packageId`, `url`, `status`, `version`
  - CQL library header: `library <Name> version "{version}"`
- `rh-skills formalize` and `rh-skills package` require this file to exist

**File location:**
```
topics/<topic>/process/formalize-config.yaml
```

**Example config:**
```yaml
name: DiabetesScreening
id: diabetes-screening
canonical: https://example.org/fhir
status: draft
version: 0.1.0
```

**Examples:**
```bash
rh-skills formalize-config diabetes-screening
rh-skills formalize-config diabetes-screening --non-interactive
rh-skills formalize-config diabetes-screening --canonical https://my-org.example.com/fhir
rh-skills formalize-config diabetes-screening --force --version 1.0.0
```

---

## `rh-skills package`

Stage computable resources into a package workspace and run `rh package`.

```
rh-skills package <topic> [--dry-run] [--check-only] [--pack] [--output-dir PATH] [--workspace-dir PATH]
```

**Arguments:**
- `topic` — Topic name

**Options:**
- `--dry-run` — Show effective workspace/output paths and commands without executing `rh`
- `--check-only` — Run `rh package check <workspace>` only
- `--pack` — Run `rh package pack <build-output>` after successful build
- `--workspace-dir PATH` — Override workspace location (default: `topics/<topic>/process/package-workspace`)
- `--output-dir PATH` — Override build output location (default: `<workspace>/output`)

**Prerequisites:**
- `formalize-config.yaml` should exist (`rh-skills formalize-config <topic>`); if missing, defaults are used with a warning.

**Behavior:**
- Stages FHIR JSON and CQL from `topics/<topic>/computable/` into the workspace
- Writes packaging control files in the workspace
- Executes:
  - `rh package check <workspace>`
  - `rh package build <workspace>` (uses `--out <PATH>` only when `--output-dir` is provided)
  - optional `rh package pack <effective-build-output>` when `--pack` is used

**Default Paths:**
- Workspace: `topics/<topic>/process/package-workspace`
- Build output: `topics/<topic>/process/package-workspace/output`

**Example:**
```bash
rh-skills package diabetes-screening
rh-skills package diabetes-screening --dry-run
rh-skills package diabetes-screening --output-dir /tmp/pkg-out
```

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

## `rh-skills cql`

Author, validate, compile, and test CQL libraries for a topic.

### `rh-skills cql validate <topic> <library>`

Validate CQL syntax and semantics.

```
rh-skills cql validate <topic> <library>
```

**Arguments:**
- `topic` — Topic identifier (e.g., `statin-eligibility`)
- `library` — CQL library name without extension (e.g., `StatinEligibility`)

**Behavior:** Runs `rh cql validate` against `topics/<topic>/computable/<library>.cql`. Reports syntax errors and semantic issues. Exit 0 on success.

**Example:**
```bash
rh-skills cql validate statin-eligibility StatinEligibility
```

---

### `rh-skills cql translate <topic> <library>`

Compile CQL to ELM JSON.

```
rh-skills cql translate <topic> <library>
```

**Arguments:**
- `topic` — Topic identifier
- `library` — CQL library name without extension

**Behavior:** Runs `rh cql compile` against the library. Writes ELM JSON output alongside the source `.cql` file. Exit 0 on success.

**Example:**
```bash
rh-skills cql translate statin-eligibility StatinEligibility
```

---

### `rh-skills cql test <topic> <library>`

List fixture test cases for a CQL library.

```
rh-skills cql test <topic> <library>
```

**Arguments:**
- `topic` — Topic identifier
- `library` — CQL library name without extension

**Behavior:** Lists fixture cases under `tests/cql/<library>/` (each case has `input/bundle.json` and `expected/expression-results.json`). **Expression evaluation is pending** — reports `[eval pending]` and exits 0 without executing expressions.

**Fixture layout:**
```
tests/cql/<Library>/
  case-001-<name>/
    input/bundle.json           ← FHIR Bundle with Patient + clinical resources
    expected/expression-results.json  ← { "ExprName": true/false/null, ... }
  case-002-<name>/
    ...
```

**Example:**
```bash
rh-skills cql test statin-eligibility StatinEligibility
```

---

### CQL file path convention

CQL libraries live at:
```
topics/<topic>/computable/<Library>.cql
```

The `rh-inf-cql` skill owns `.cql` source files. FHIR JSON wrappers (Library, Measure JSON) are generated and owned by `rh-inf-formalize`.

---

## `rh-skills cql` — Status summary

| Command | Invokes | Status |
|---------|---------|--------|
| `rh-skills cql validate <topic> <lib>` | `rh cql validate` | ✓ active |
| `rh-skills cql translate <topic> <lib>` | `rh cql compile` | ✓ active |
| `rh-skills cql test <topic> <lib>` | — | ⏳ eval pending (lists cases only) |

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
