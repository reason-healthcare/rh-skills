# HI Skills Framework

Agent skills for building clinical knowledge artifacts — from raw sources through structured criteria to computable, FHIR-aligned outputs.

## What it does

The HI framework guides clinical knowledge through three artifact levels:

| Level | Format | Description |
|-------|--------|-------------|
| **L1** | Markdown | Raw sources — guideline extracts, clinical notes, literature |
| **L2** | YAML | Structured — discrete clinical criteria, coded concepts |
| **L3** | YAML | Computable — pathways, measures, value sets (FHIR-compatible) |

The relationships are many-to-many: one L1 source can yield several L2 artifacts; multiple L2 artifacts can converge into a single L3.

## Usage Modes

The framework supports two modes — both use the `hi` CLI for deterministic work and an agent for reasoning:

| Mode | How it works | Best for |
|------|-------------|----------|
| **CLI-first** | You call `hi` commands directly; use any LLM provider (including local models) | Full control, CI/CD, bring-your-own-model |
| **Agent-native** | Your AI agent (Copilot, Claude, Gemini) reads the HI skills and calls `hi` on your behalf | Conversational UX, clinical teams |

→ See [docs/USAGE_MODES.md](docs/USAGE_MODES.md) for a full comparison, platform support, and LLM configuration.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- An LLM provider — local Ollama, Anthropic, OpenAI, or any OpenAI-compatible endpoint (CLI-first mode); or your existing agent platform (agent-native mode)

## Installation

```bash
uv tool install hi
hi --help
```

Configure your LLM provider:

```bash
cp .env.example .env   # set LLM_PROVIDER, model, and API key
```

## Quickstart

```bash
# 1. Initialize a clinical topic
hi init diabetes-screening --title "Diabetes Screening" --author "My Team"

# 2. Discover and ingest source materials (agent-guided)
#    hi-discovery and hi-ingest skills handle this step

# 3. Check where the topic stands
hi status show diabetes-screening

# 4. Extract structured L2 artifacts from ingested sources
hi promote derive diabetes-screening --source ada-guidelines --name screening-criteria
hi promote derive diabetes-screening --source ada-guidelines --name risk-factors

# 5. Validate the L2 artifacts
hi validate diabetes-screening l2 screening-criteria

# 6. Converge L2 artifacts into a computable L3
hi promote combine diabetes-screening \
  --sources screening-criteria,risk-factors \
  --name diabetes-screening-pathway

# 7. Validate the L3 artifact
hi validate diabetes-screening l3 diabetes-screening-pathway

# 8. See all topics and their stages
hi list
```

## Command Reference

### `hi init <name>`
Scaffold a new topic. Creates the directory structure and registers the topic in `tracking.yaml`.

```
Options:
  --title TEXT    Human-readable title
  --author TEXT   Author or team name
```

### `hi list`
List all topics and their lifecycle stages.

```
Options:
  --json          Output as JSON
  --stage STAGE   Filter: initialized | l1-discovery | l2-semi-structured | l3-computable
```

### `hi status <subcommand> <topic>`
Inspect a topic's current state.

| Subcommand | Description |
|------------|-------------|
| `show` | Summary table: stage, source count, artifact counts |
| `progress` | Completeness percentage toward L3 |
| `next-steps` | Recommended next action |
| `check-changes` | Detect files changed since last tracking event |

### `hi ingest <mode> <topic>`
Register source files (L1) with checksums in `tracking.yaml`.

```
Modes: plan | implement | verify
Options:
  --source PATH   Path to source file or URL
  --name TEXT     Artifact name
  --force         Overwrite existing output
```

### `hi promote <mode> <topic>`
Promote artifacts to the next level.

**`derive`** — L1 → L2 (one or more structured artifacts from a single source):
```
  --source TEXT     Source artifact name (required)
  --name TEXT       Output artifact name (required)
```

**`combine`** — L2 → L3 (one computable artifact from multiple structured inputs):
```
  --sources TEXT    Comma-separated artifact names (required)
  --name TEXT       Output artifact name (required)
```

Both modes support `--dry-run` (print prompt only) and `--force` (overwrite existing).

### `hi validate <topic> <level> <artifact>`
Validate an artifact against its schema. Required field violations exit 1; optional field gaps are warnings.

### `hi test <topic> <skill>`
Run a skill against test fixtures. Results written to `topics/<topic>/process/fixtures/results/`.

## Topic Structure

```
topics/
  <name>/
    structured/         ← L2 YAML artifacts
    computable/         ← L3 YAML artifacts
    process/
      plans/            ← skill plan artifacts
      contracts/        ← validation contracts
      checklists/       ← clinical review checklists
      fixtures/         ← test fixtures + results
      research.md
      conflicts.md

sources/
  <name>.<ext>          ← ingested L1 source files

tracking.yaml           ← append-only event log (repo root)
```

## L2 / L3 Schemas

| Schema | Required fields | Reference |
|--------|----------------|-----------|
| L2 | `id`, `name`, `title`, `version`, `status`, `domain`, `description`, `derived_from` | `schemas/l2-schema.yaml` |
| L3 | `artifact_schema_version`, `metadata.*`, `converged_from` | `schemas/l3-schema.yaml` |

L3 sections map to FHIR R4/R5 resources (`PlanDefinition`, `Measure`, `ValueSet`, etc.). See `schemas/l3-schema.yaml` for the full mapping.

## Example

See [`example-project/`](example-project/) for a complete diabetes-screening walkthrough with L1 source, two L2 artifacts, and a converged L3 artifact.

## Further reading

- [Usage Modes](docs/USAGE_MODES.md) — CLI-first vs agent-native, LLM configuration, platform support
- [Getting Started](docs/GETTING_STARTED.md) — step-by-step first topic walkthrough
- [Workflow](docs/WORKFLOW.md) — lifecycle diagram and many-to-many artifact topology
- [Command Reference](docs/COMMANDS.md) — full CLI reference with all flags
- [Developer Guide](DEVELOPER.md) — contributing skills and framework code
