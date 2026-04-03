# HI Skills Framework

A CLI-driven framework for building healthcare informatics skills that progress from raw discovery through structured criteria to computable artifacts.

## Artifact Levels

| Level | Format | Description |
|-------|--------|-------------|
| **L1** | Markdown | Raw discovery — guideline extracts, clinical notes, literature |
| **L2** | YAML | Semi-structured — discrete clinical criteria, coded concepts |
| **L3** | YAML | Computable — pathways, measures, value sets, FHIR-compatible |

The topology is many-to-many: one L1 can yield multiple L2 artifacts; multiple L2 artifacts can converge into a single L3.

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| `bash 3.2+` | Core runtime | Pre-installed on macOS/Linux |
| `yq` | YAML parsing | `brew install yq` / `snap install yq` |
| `jq` | JSON parsing | `brew install jq` / `apt install jq` |
| `curl` | LLM HTTP calls | `brew install curl` / `apt install curl` |

For testing:
```bash
npm install          # installs bats-core via npm
```

## Installation

```bash
git clone <repo-url> hi-skills
cd hi-skills
npm install
export PATH="$PATH:$(pwd)/bin"
```

## LLM Configuration

Copy `.env.example` and configure your LLM provider:

```bash
cp .env.example .env
```

```dotenv
# .env
LLM_PROVIDER=ollama           # ollama | anthropic | openai | stub
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```

`LLM_PROVIDER=stub` is available for testing without a live LLM.

## Quickstart

```bash
# 1. Scaffold a new skill
hi init diabetes-screening --title "Diabetes Screening" --author "My Team"

# 2. Add a raw L1 artifact (manual step)
cp my-guideline-extract.md skills/diabetes-screening/l1/ada-guidelines.md

# 3. Derive an L2 artifact from L1
hi promote derive diabetes-screening --source ada-guidelines --name screening-criteria

# 4. Derive another L2 from the same L1 source
hi promote derive diabetes-screening --source ada-guidelines --name risk-factors

# 5. Validate the L2 artifacts
hi validate diabetes-screening l2 screening-criteria
hi validate diabetes-screening l2 risk-factors

# 6. Converge two L2 artifacts into an L3
hi promote combine diabetes-screening \
  --sources screening-criteria,risk-factors \
  --name diabetes-screening-computable

# 7. Validate the L3 artifact
hi validate diabetes-screening l3 diabetes-screening-computable

# 8. Check skill status
hi status diabetes-screening

# 9. Run LLM fixture tests
hi test diabetes-screening
```

## Command Reference

### `hi init <skill-name> [options]`

Scaffold a new skill with directory structure and tracking.

```
Options:
  --title         Human-readable title
  --description   Brief description
  --author        Author or team name
```

### `hi promote <mode> <skill> [options]`

Promote artifacts to the next level using LLM reasoning.

**Derive mode** (L1 → L2):
```
  --source <l1-name>    Source L1 artifact name (required)
  --name   <l2-name>    Output L2 artifact name (required)
  --count  <n>          Number of L2 artifacts to generate (default: 1)
  --dry-run             Print LLM prompt only; do not invoke
```

**Combine mode** (L2 → L3):
```
  --sources <a,b,c>     Comma-separated L2 artifact names (required)
  --name    <l3-name>   Output L3 artifact name (required)
  --dry-run             Print LLM prompt only; do not invoke
```

### `hi validate <skill> <level> <artifact>`

Validate L2 or L3 artifacts against their schema.

- Required field violations → exit 1
- Optional field gaps → warnings (exit 0)

### `hi test <skill> [options]`

Run LLM-based fixture tests against a skill.

```
  --fixture <name>   Run a specific fixture only
  --mode    <mode>   Comparison: exact | normalized | case_insensitive | contains | keywords
```

Results written to `skills/<skill>/fixtures/results/<timestamp>-<runid>.json`.

### `hi status <skill> [--json]`

Show skill lifecycle stage and artifact counts.

### `hi list [--json] [--stage <stage>]`

List all skills. Filter by stage: `initialized`, `l1-discovery`, `l2-semi-structured`, `l3-computable`.

## Skill Structure

```
skills/
  <skill-name>/
    SKILL.md                    # Skill description + usage instructions
    tracking.yaml               # Append-only audit log
    l1/
      <source>.md               # Raw discovery artifacts
    l2/
      <artifact>.yaml           # Semi-structured criteria
    l3/
      <artifact>.yaml           # Computable artifact
    fixtures/
      <test>.yaml               # LLM test fixtures
      results/                  # Test run results
```

## L2 Schema

Required fields: `id`, `name`, `title`, `version`, `status`, `domain`, `description`, `derived_from`

See `schemas/l2-schema.yaml` for full schema.

## L3 Schema

Required: `artifact_schema_version`, `metadata` block (8 sub-fields), `converged_from`

Optional sections with FHIR equivalents:

| Section | FHIR R4/R5 Equivalent |
|---------|----------------------|
| `pathways` | `PlanDefinition` |
| `actions` | `RequestGroup` |
| `libraries` | `Library` |
| `measures` | `Measure` |
| `assessments` | `Questionnaire` |
| `value_sets` | `ValueSet` |
| `code_systems` | `CodeSystem` |

See `schemas/l3-schema.yaml` for full schema.

## Example Skill

See `skills/diabetes-screening/` for a complete reference implementation based on ADA 2024 guidelines, including:
- L1 guideline extract
- Two L2 artifacts (screening criteria, risk factors)
- One L3 computable artifact (pathways, measures, value sets)
- A fixture for LLM testing

## Running Tests

```bash
npm test                                    # all tests
npx bats tests/unit/                        # unit tests only
npx bats tests/integration/                 # integration tests only
npx bats tests/unit/init.bats               # single file
```

## Design Principles

- **Deterministic work to commands** — all file I/O, schema validation, tracking, and routing is handled by CLI commands
- **Reasoning to agents** — LLM is invoked only for L1→L2 and L2→L3 promotion
- **Portable** — scripts work on macOS (bash 3.2) and Linux; no GNU-isms
- **Lenient promotion** — optional fields produce warnings, not errors; strict mode only for required fields
- **Audit trail** — `tracking.yaml` is append-only; every action is recorded with timestamps

## For more

See [`specs/001-hi-skills-framework/`](specs/001-hi-skills-framework/) for full specification, data model, and quickstart guide.
