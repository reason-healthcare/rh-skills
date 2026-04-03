# CLI Contracts: Healthcare Informatics Skills Framework

**Phase**: 1 — Design  
**Branch**: `001-hi-skills-framework`  
**Date**: 2026-04-03

---

## CLI Dispatcher

**Entry point**: `bin/hi`

Routes subcommands to dedicated scripts in `bin/`:

```
hi <command> [arguments] [flags]
```

Global flags:
- `--help` / `-h`: Print usage for any command
- `--json`: Machine-readable JSON output (where applicable)
- `--version`: Print framework version

---

## Commands

### `hi init`

Scaffolds a new skill directory with L1 stubs, SKILL.md, and an initial tracking artifact.

```
hi init <skill-name> [--description "..."] [--author "..."]
```

**Arguments**:
- `<skill-name>` (required): Kebab-case skill identifier; must be unique in `skills/`

**Flags**:
- `--description`: Short description of the skill (written into tracking.yaml)
- `--author`: Author name (defaults to `$USER`)

**Outputs** (stdout):
```
✓ Created skills/diabetes-screening/
✓ Created l1/, l2/, l3/, fixtures/ directories
✓ Created SKILL.md
✓ Created tracking.yaml (status: initialized, level: L1)
```

**Exit codes**:
- `0`: Success
- `1`: Skill name already exists
- `2`: Invalid skill name (not kebab-case)

**Side effects**:
- Creates `skills/{skill-name}/` directory tree
- Creates `skills/{skill-name}/SKILL.md` from template
- Creates `skills/{skill-name}/l1/discovery.md` stub
- Creates `skills/{skill-name}/tracking.yaml` with creation event

---

### `hi promote`

Promotes one or more artifacts to the next level. Supports two modes:

#### Derive mode (L1 → L2)

Derives one or more L2 artifacts from a single L1 artifact.

```
hi promote <skill-name> <l1-artifact-name> --to l2 [--count N]
```

**Flags**:
- `--count N`: Number of L2 artifacts to scaffold (default: 1)

**Outputs**:
```
✓ Scaffolded l2/concept-x.yaml (derived from l1/ada-guidelines-excerpt.md)
✓ Scaffolded l2/concept-y.yaml (derived from l1/ada-guidelines-excerpt.md)
! [WARN] Missing optional fields in l2/concept-x.yaml: references, tags
✓ Tracking artifact updated (2 derivation events recorded)
```

**Exit codes**:
- `0`: Success (may include warnings)
- `1`: L1 artifact not found
- `2`: Required field validation failed (blocks promotion)

#### Combine mode (L2 → L3)

Combines two or more L2 artifacts into a single L3 artifact.

```
hi promote <skill-name> --combine <l2-artifact-1> <l2-artifact-2> [<l2-artifact-N>...] --output <l3-artifact-name>
```

**Outputs**:
```
✓ Scaffolded l3/screening-guideline.yaml
    (converged from: screening-criteria.yaml, risk-factors.yaml)
✓ L3 schema validation: PASSED
✓ Tracking artifact updated (convergence event recorded)
```

**Exit codes**:
- `0`: Success
- `1`: One or more L2 artifacts not found
- `2`: L2 required field validation failed
- `3`: L3 schema validation failed

---

### `hi validate`

Validates a specific artifact against its level schema without promoting.

```
hi validate <skill-name> <artifact-path> [--json]
```

**Arguments**:
- `<artifact-path>`: Relative path from skill root (e.g., `l2/screening-criteria.yaml`)

**Outputs**:
```
Validating: skills/diabetes-screening/l2/screening-criteria.yaml
[PASS] Syntax: valid YAML
[PASS] Required fields: all present
[WARN] Optional fields missing: references, tags
Status: WARNINGS (promotable with warnings)
```

**JSON output** (`--json`):
```json
{
  "file": "l2/screening-criteria.yaml",
  "status": "warnings",
  "errors": [],
  "warnings": ["references", "tags"],
  "promotable": true
}
```

**Exit codes**:
- `0`: Valid (or valid with warnings)
- `1`: Invalid (missing required fields or syntax error)

---

### `hi test`

Runs LLM-based tests for a skill against defined fixtures.

```
hi test <skill-name> [--fixture <fixture-name>] [--provider ollama|anthropic|openai]
```

**Flags**:
- `--fixture`: Run a single named fixture (default: run all)
- `--provider`: Override `$LLM_PROVIDER` env var for this run

**Environment variables**:
```bash
LLM_PROVIDER=ollama          # ollama | anthropic | openai
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=mistral
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
OPENAI_API_KEY=sk-...
OPENAI_ENDPOINT=https://api.openai.com/v1/chat/completions
OPENAI_MODEL=gpt-4o-mini
```

**Outputs**:
```
Running tests for: diabetes-screening
Provider: ollama (mistral)

  ✓ basic-case          PASSED  (normalized, 1.2s)
  ✗ high-risk-case      FAILED
      Expected: "A1C and fasting glucose recommended"
      Actual:   "Fasting glucose test only"
  ⚠ timeout-scenario    ERRORED (TIMEOUT after 30s)

Results: 1 passed, 1 failed, 1 errored (3 total)
Test result artifact written: fixtures/results/2026-04-03-abc123.json
Tracking artifact updated.
```

**Exit codes**:
- `0`: All fixtures passed
- `1`: One or more fixtures failed or errored
- `2`: No fixtures defined
- `3`: LLM provider not configured or unreachable

---

### `hi status`

Reads a skill's tracking artifact and renders its full workflow state.

```
hi status <skill-name> [--json]
```

**Outputs**:
```
Skill: diabetes-screening
Title: Diabetes Screening
Created: 2026-04-03 by bkaney

Artifact Inventory:
  L1  2 artifacts   discovery-a.md, ada-guidelines-excerpt.md
  L2  2 artifacts   screening-criteria.yaml, risk-factors.yaml
  L3  1 artifact    screening-guideline.yaml

Latest Test Run: 2026-04-03  2 passed / 1 failed / 0 errored

Event History:
  2026-04-03T14:00Z  created
  2026-04-03T14:10Z  l2_derived  (discovery-a.md → screening-criteria.yaml)
  2026-04-03T14:11Z  l2_derived  (ada-guidelines-excerpt.md → risk-factors.yaml)
  2026-04-03T14:20Z  l3_converged (screening-criteria.yaml + risk-factors.yaml → screening-guideline.yaml)
  2026-04-03T14:30Z  test_run (2 passed, 1 failed, 0 errored)
```

**Exit codes**:
- `0`: Success
- `1`: Skill not found
- `2`: Tracking artifact missing or corrupt (with repair guidance)

---

### `hi list`

Lists all skills in the repository with a summary table.

```
hi list [--level l1|l2|l3] [--json]
```

**Flags**:
- `--level`: Filter to skills that have artifacts at a specific level

**Outputs**:
```
Healthcare Informatics Skills Repository
3 skills

SKILL                   L1    L2    L3    LAST TEST
───────────────────────────────────────────────────────
diabetes-screening       2     2     1     2026-04-03 ✓
htn-management           3     1     0     —
sepsis-screening         1     0     0     —
```

**Exit codes**:
- `0`: Success (even if no skills exist)
- `1`: Skills directory not found (not an HI skills repository)
