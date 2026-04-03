# CLI Contracts: HI Agent Skills Suite (002)

**Branch**: `002-hi-agent-skills` | **Date**: 2026-04-03

---

## New Command: `hi ingest`

Follows the existing `bin/hi-{command}` dispatcher pattern. All exit codes match the existing contract.

### `hi ingest plan <skill> [--force]`

Register a list of sources to ingest into a reviewable plan.

```
Usage: hi ingest plan <skill> [--force]

Arguments:
  skill       Skill name (kebab-case)

Options:
  --force     Overwrite existing ingest-plan.md
  -h, --help  Print usage

Exit codes:
  0  Plan written to skills/<skill>/plans/ingest-plan.md
  0  Plan already exists (warns, suggests --force)
  1  Source file listed in discovery-plan.md does not exist on disk
  2  Usage error (missing args, unknown skill)

Output:
  skills/<skill>/plans/ingest-plan.md  (YAML front matter + Markdown prose)
```

### `hi ingest implement <skill> [--force]`

Register each source from the ingest plan: copy to `l1/`, compute SHA-256 checksum, record in tracking.yaml.

```
Usage: hi ingest implement <skill> [--force]

Arguments:
  skill       Skill name (kebab-case)

Options:
  --force     Re-ingest sources even if already registered
  -h, --help  Print usage

Exit codes:
  0  All sources registered successfully
  0  Source skipped (already registered and --force not set)
  1  Source file not found on disk
  1  Checksum computation failed
  2  No ingest plan found (plans/ingest-plan.md missing)
  2  Usage error

Side effects:
  - Copies source files to skills/<skill>/l1/
  - Appends sources[] entries to skills/<skill>/tracking.yaml
  - Appends l1_added events to tracking.yaml
  - Extracts text (optional: requires pdftotext/pandoc; warns if absent)
```

### `hi ingest verify <skill>`

Verify all registered sources are still present and checksums match.

```
Usage: hi ingest verify <skill>

Arguments:
  skill       Skill name (kebab-case)

Exit codes:
  0  All sources present and checksums match
  1  One or more sources changed, missing, or deleted
  2  Usage error

Output (stdout):
  ✓ ada-guidelines-2024  OK
  ✗ risk-factors-paper   CHANGED (stored: abc123..., current: def456...)
  ! clinical-notes       MISSING (was: skills/diabetes-screening/l1/clinical-notes.md)
```

---

## Extended Command: `hi status`

Existing `hi-status` gains three modes dispatched by subcommand argument.

### `hi status progress <skill>`

```
Usage: hi status progress <skill>

Exit codes:
  0  Summary printed
  2  Usage error / unknown skill

Output (human-readable):
  ── diabetes-screening ──────────────────────────────
  Stage:       l2-semi-structured
  Sources:     2 registered (2 checksums OK)
  L1 artifacts: 1
  L2 artifacts: 2 (1 validated, 1 unvalidated)
  L3 artifacts: 0
  Last event:  2026-04-03T19:05:00Z  l2_derived
  Completeness: 60%
```

### `hi status next-steps <skill>`

```
Usage: hi status next-steps <skill>

Exit codes:
  0  Recommendation printed
  2  Usage error / unknown skill

Output (human-readable):
  Next recommended action:
  ▶ Validate unvalidated L2 artifact:
      hi validate diabetes-screening l2 risk-factors

  Or run hi-extract verify for a full L2 validation pass.
```

### `hi status check-changes <skill>`

```
Usage: hi status check-changes <skill>

Exit codes:
  0  No changes detected
  1  One or more sources have changed, are missing, or are new
  2  Usage error / unknown skill

Output (human-readable, exit 1 example):
  ✗ CHANGED: ada-guidelines-2024
    Path:     skills/diabetes-screening/l1/ada-guidelines-2024.md
    Stored:   e3b0c442...
    Current:  9f86d081...
    ⚠ Potentially stale L2 artifacts: screening-criteria, risk-factors

  ! MISSING: clinical-notes
    Was: skills/diabetes-screening/l1/clinical-notes.md
```

---

## Plan Artifact Contract

All plan artifacts share this interface, consumed by `implement` mode scripts.

### File Location
`skills/<name>/plans/<plan-type>-plan.md`

### Front Matter Fields by Plan Type

#### discovery-plan.md
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skill` | string | ✅ | Skill name |
| `plan_type` | `"discovery"` | ✅ | Must be literal `"discovery"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `domain` | string | ✅ | Clinical domain |
| `sources[].type` | enum | ✅ | `guideline\|paper\|terminology\|dataset\|other` |
| `sources[].name` | string | ✅ | Human-readable source name |
| `sources[].priority` | enum | ✅ | `high\|medium\|low` |
| `sources[].url` | string | ❌ | URL if applicable |
| `sources[].rationale` | string | ❌ | Why this source |

#### ingest-plan.md
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skill` | string | ✅ | Skill name |
| `plan_type` | `"ingest"` | ✅ | Must be literal `"ingest"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `items[].name` | string | ✅ | Kebab-case artifact name |
| `items[].path` | string | ✅ | File path or URL |
| `items[].type` | enum | ✅ | `pdf\|docx\|xlsx\|txt\|md\|url` |
| `items[].extract_text` | bool | ❌ | Default `true` |
| `items[].target` | string | ❌ | Override destination path |

#### extract-plan.md
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skill` | string | ✅ | Skill name |
| `plan_type` | `"extract"` | ✅ | Must be literal `"extract"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `artifacts[].name` | string | ✅ | Kebab-case L2 artifact name |
| `artifacts[].source` | string | ✅ | L1 artifact name |
| `artifacts[].description` | string | ✅ | One-sentence description |

#### formalize-plan.md
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skill` | string | ✅ | Skill name |
| `plan_type` | `"formalize"` | ✅ | Must be literal `"formalize"` |
| `version` | string | ✅ | `"1.0"` |
| `created` | ISO-8601 | ✅ | Creation timestamp |
| `output_name` | string | ✅ | Kebab-case L3 artifact name |
| `sources[]` | string[] | ✅ | L2 artifact names to combine |
| `sections[]` | string[] | ✅ | L3 sections to include |
| `outline` | string | ❌ | Human prose outline |

---

## Tracking.yaml Extension Contract

The existing `tracking.yaml` gains a `sources[]` array. Existing fields are unchanged.

```yaml
# Existing fields (unchanged)
schema_version: "1.0"
skill: { name, title, ... }
artifacts: { l1: [], l2: [], l3: [] }
events: []

# New field
sources:
  - name: string          # kebab-case, unique within skill
    path: string          # path relative to repo root
    original_path: string # source path before copy (may be absolute)
    type: string          # pdf|docx|xlsx|txt|md|url
    ingested_at: string   # ISO-8601
    checksum: string      # SHA-256 hex (64 chars)
    text_extracted: bool  # true if text extraction succeeded
    url: string|null      # populated for url-type sources
```

---

## Framework Skill SKILL.md Contract

All 6 framework skills must satisfy:

```
Required frontmatter:
  name:           "hi-<skill>"
  description:    "<one-line summary>. Modes: <mode1> | <mode2> [| mode3]"
  compatibility:  "hi-skills-framework >= 0.1.0"
  metadata:
    author:       string
    source:       "skills/_framework/hi-<skill>/SKILL.md"

Required body sections:
  ## User Input        ($ARGUMENTS block + MUST-consider directive)
  ## Mode: <mode>      (one section per supported mode)

Each mode section must document:
  - What it reads
  - What it writes (or "read-only")
  - Failure conditions
  - The hi CLI commands it invokes
```

---

## Exit Code Contract (all new commands)

Unchanged from existing framework:

| Code | Meaning |
|------|---------|
| `0` | Success (including graceful no-ops with warnings) |
| `1` | Content/validation failure (wrong data, checksum mismatch, source not found) |
| `2` | Usage error (wrong args, missing skill, missing required plan) |
