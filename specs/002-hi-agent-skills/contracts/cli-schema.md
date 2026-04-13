# CLI Contracts: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03

---

## New Command: `rh-skills ingest`

Follows the existing click command group pattern. All exit codes match the existing contract.

### `rh-skills ingest plan [--force]`

Generate an ingest plan template at `plans/ingest-plan.md` (root-level plans directory).

```
Usage: rh-skills ingest plan [--force]

Options:
  --force     Overwrite existing ingest-plan.md
  -h, --help  Print usage

Exit codes:
  0  Plan written to plans/ingest-plan.md
  0  Plan already exists (warns, suggests --force)
  2  Usage error

Output:
  plans/ingest-plan.md  (YAML front matter + Markdown prose)

Reads:
  topics/<name>/process/plans/discovery-plan.yaml  (if available, for context)
```

### `rh-skills ingest implement <file> [--force]`

Copy FILE to `sources/` and register in tracking.yaml. FILE is a path to any local file.

```
Usage: rh-skills ingest implement <file> [--force]

Arguments:
  file        Path to the local source file to ingest

Options:
  --force     Re-ingest source even if already registered
  -h, --help  Print usage

Exit codes:
  0  Source registered successfully
  0  Source already registered (updates checksum with warning)
  1  Source file not found on disk
  2  Usage error

Side effects:
  - Copies source file to sources/<filename>
  - Appends or updates sources[] entry in tracking.yaml (SHA-256 via hashlib)
  - Appends source_added or source_changed event to tracking.yaml
```

### `rh-skills ingest verify`

Verify all registered sources are still present and checksums match.

```
Usage: rh-skills ingest verify

Exit codes:
  0  All sources present and checksums match
  1  One or more sources changed, missing, or deleted
  2  Usage error

Output (stdout):
  ✓ ada-guidelines-2024            OK
  ✗ risk-factors-paper             CHANGED (was: abc123..., now: def456...)
  ✗ clinical-notes                 MISSING
```

---

## Extended Command: `rh-skills status`

### `rh-skills status <topic>`

```
Usage: rh-skills status <topic> [--json]

Exit codes:
  0  Summary printed
  2  Usage error / unknown topic

Output (human-readable):
  Topic:    diabetes-screening
  Title:    Diabetes Screening
  Author:   Clinical Informatics Team
  Created:  2026-04-03T19:00:00Z
  Stage:    l2-semi-structured

  Artifacts:
    L1 (discovery):        2
    L2 (semi-structured):  2
    L3 (computable):       0

  Last event: structured_derived (2026-04-03T19:05:00Z)
```

> **Note**: `rh-skills status progress`, `rh-skills status next-steps`, and `rh-skills status check-changes` are planned features (tasks T030–T032) and **not yet implemented**. The current `rh-skills status <topic>` provides basic lifecycle info.

---

## Plan Artifact Contract

All plan artifacts share this interface, consumed by `implement` mode scripts.

### File Location
`topics/<name>/process/plans/<plan-type>-plan.md`

### Front Matter Fields by Plan Type

#### discovery-plan.yaml

Pure YAML file (no frontmatter delimiters). Single machine-readable source of truth for `rh-inf-discovery` output. Consumed by `rh-skills validate --plan` and `rh-inf-ingest`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | ✅ | Topic name |
| `plan_type` | `"discovery"` | ✅ | Must be literal `"discovery"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `domain` | string | ✅ | Clinical domain |
| `sources[].type` | enum | ✅ | `guideline\|paper\|terminology\|dataset\|other` |
| `sources[].name` | string | ✅ | Human-readable source name |
| `sources[].priority` | enum | ✅ | `high\|medium\|low` |
| `sources[].url` | string | ❌ | URL if applicable |
| `sources[].rationale` | string | ❌ | Why this source |
| `sources[].access` | enum | ✅ | `open\|authenticated\|manual` |
| `sources[].auth_note` | string | ❌ | Required when `access: authenticated` or `access: manual` |

#### discovery-readout.md

Generated Markdown narrative derived from `discovery-plan.yaml`. Do not edit directly. Contains `## Domain Advice` and `## Research Expansion Suggestions` sections. For human/agent reading only; never machine-parsed.
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | ✅ | Topic name |
| `plan_type` | `"ingest"` | ✅ | Must be literal `"ingest"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `items[].name` | string | ✅ | Kebab-case artifact name |
| `items[].path` | string | ✅ | File path or URL |
| `items[].type` | enum | ✅ | `pdf\|docx\|xlsx\|txt\|md\|url` |
| `items[].extract_text` | bool | ❌ | Default `true` |
| `items[].target` | string | ❌ | Override destination in `sources/` |

#### extract-plan.md
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | ✅ | Topic name |
| `plan_type` | `"extract"` | ✅ | Must be literal `"extract"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `artifacts[].name` | string | ✅ | Kebab-case structured artifact name |
| `artifacts[].source_file` | string | ✅ | File in `sources/` (without extension) |
| `artifacts[].description` | string | ✅ | One-sentence description |

#### formalize-plan.md
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | ✅ | Topic name |
| `plan_type` | `"formalize"` | ✅ | Must be literal `"formalize"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `output_name` | string | ✅ | Kebab-case computable artifact name |
| `sources[]` | string[] | ✅ | Structured artifact names to combine |
| `sections[]` | string[] | ✅ | Computable sections to include |
| `outline` | string | ❌ | Human prose outline |

---

## Tracking.yaml Extension Contract

The `tracking.yaml` at the repo root uses the following structure. All fields are set by `rh-skills init` and extended by subsequent commands.

```yaml
# Current tracking.yaml structure
schema_version: "1.0"
sources: []           # list of registered raw source files (root level)
topics:
  - name: string
    title: string
    description: string
    author: string
    created_at: string
    structured: []    # L2 artifact entries
    computable: []    # L3 artifact entries
    events: []
events: []            # root-level events

# sources[] entry schema (added by rh-skills ingest implement):
sources:
  - name: string          # kebab-case, unique
    file: string          # path relative to repo root, in sources/
    type: string          # pdf|docx|xlsx|txt|md|url|document
    ingested_at: string   # ISO-8601
    checksum: string      # SHA-256 hex (64 chars)
    text_extracted: bool  # true if text extraction succeeded
```

---

## Framework Skill SKILL.md Contract

All 6 framework skills must satisfy:

```
Required frontmatter:
  name:           "hi-<skill>"
  description:    "<one-line summary>. Modes: <mode1> | <mode2> [| mode3]"
  compatibility:  "rh-skills >= 0.1.0"
  metadata:
    author:       string
    source:       "skills/.curated/hi-<skill>/SKILL.md"

Required body sections:
  ## User Input        ($ARGUMENTS block + MUST-consider directive)
  ## Mode: <mode>      (one section per supported mode)

Each mode section must document:
  - What it reads
  - What it writes (or "read-only")
  - Failure conditions
  - The rh-skills CLI commands it invokes
```

---

## Exit Code Contract (all new commands)

Unchanged from existing framework:

| Code | Meaning |
|------|---------|
| `0` | Success (including graceful no-ops with warnings) |
| `1` | Content/validation failure (wrong data, checksum mismatch, source not found) |
| `2` | Usage error (wrong args, missing skill, missing required plan) |
