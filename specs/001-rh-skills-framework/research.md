# Research: Healthcare Informatics Skills Framework

**Phase**: 0 — Pre-Design Research  
**Branch**: `001-rh-skills-framework`  
**Date**: 2026-04-03

---

## 1. Anthropic Skills-Developer Conventions

**Finding**: Each skill in `.agents/skills/{skill-name}/` contains a single `SKILL.md` file with a YAML frontmatter header followed by Markdown instruction content.

**Frontmatter structure**:
```yaml
---
name: "skill-name"
description: "One-line capability description"
compatibility: "Runtime requirements or constraints"
metadata:
  author: "author-name"
  source: "reference source"
---
```

**Body structure**: Free-form Markdown with headings for:
- `## User Input` — how `$ARGUMENTS` is consumed
- `## Pre-Execution Checks` — prerequisite gates
- `## Outline` — numbered step-by-step instruction for the agent

**Implication for RH skills framework**: Each HI skill lives at `skills/{skill-name}/SKILL.md` following this exact convention. The SKILL.md prompt is the authoritative agent instruction that references L3 YAML artifact content at runtime.

---

## 2. LLM Invocation from Bash

**Finding**: Three provider strategies are fully implementable in pure Bash + `curl` + `jq`.

### Provider Abstraction
```bash
export LLM_PROVIDER="ollama"   # ollama | anthropic | openai
```
A single `invoke_llm()` dispatcher routes to the appropriate provider. Response is parsed by a paired `parse_llm_response()` function.

| Provider | Endpoint Config | Response Parsing |
|----------|----------------|-----------------|
| Ollama (local) | `OLLAMA_ENDPOINT=http://localhost:11434` | `jq -r '.response'` |
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | `jq -r '.content[0].text'` |
| OpenAI-compatible | `OPENAI_ENDPOINT`, `OPENAI_API_KEY`, `OPENAI_MODEL` | `jq -r '.choices[0].message.content'` |

### Fixture Comparison Modes
Five modes for comparing actual vs. expected LLM output:

| Mode | Use Case |
|------|----------|
| `exact` | Deterministic outputs, specific codes |
| `normalized` | General text (whitespace collapsed) — **default** |
| `case_insensitive` | Clinical terms with variable capitalization |
| `contains` | Required finding must appear in response |
| `keywords` | Multiple concepts must all be present |

### Outcome States
- **PASSED** (exit 0): LLM call succeeded AND output matched expected
- **FAILED** (exit 1): LLM call succeeded BUT output did not match
- **ERRORED** (exit 2): LLM call failed (API error, timeout, connection refused)

### Test Result Artifact (JSON)
```json
{
  "test_run_id": "test-20260403-141500",
  "timestamp": "2026-04-03T14:15:00Z",
  "skill_name": "diabetes-screening",
  "llm_config": { "provider": "ollama", "model": "mistral" },
  "summary": { "total": 3, "passed": 2, "failed": 1, "errored": 0 },
  "fixtures": [
    { "fixture_id": "f-001", "status": "PASSED", "comparison_mode": "normalized" },
    { "fixture_id": "f-002", "status": "FAILED", "expected": "...", "actual": "..." },
    { "fixture_id": "f-003", "status": "ERRORED", "error_type": "TIMEOUT" }
  ]
}
```

**Recommendation**: Default to Ollama for development (free, fully offline), OpenAI-compatible for CI, Anthropic for production validation. All switch via `LLM_PROVIDER` env var.

---

## 3. L3 Artifact Schema — FHIR-Compatible Custom YAML

**Finding**: A 7-section custom YAML schema provides full clinical knowledge representation while remaining FHIR-mappable. Sections map directly to core FHIR resource types. No FHIR tooling required to author or validate.

### Schema Sections → FHIR Resource Mapping

| Schema Section | FHIR Resource | CPG-on-FHIR Role |
|---------------|---------------|-----------------|
| `pathways` | PlanDefinition | Clinical protocol / ECA rule / workflow definition |
| `actions` | ActivityDefinition | Medication/service/task recommendations |
| `libraries` | Library | CQL logic container |
| `measures` | Measure | Quality measurement populations |
| `assessments` | Questionnaire (SDC) | Clinical data capture / screening tools |
| `value_sets` | ValueSet | Terminology groupings |
| `code_systems` | CodeSystem | Local/custom terminology |

### L3 Schema Top-Level Structure
```yaml
artifact_schema_version: "1.0"

metadata:
  id: {kebab-case}
  name: {PascalCase}
  title: {Human-Readable String}
  version: {semver}
  status: draft | active | retired
  domain: {e.g., "Hypertension Management"}
  created_date: YYYY-MM-DD
  description: |
    Multi-line clinical description.

# Include only relevant sections:
pathways: [...]
actions: [...]
libraries: [...]
measures: [...]
assessments: [...]
value_sets: [...]
code_systems: [...]
```

### Key Naming Conventions (Enforced by rh-skills validate)
- `id` / `identifier` fields: kebab-case (e.g., `htn-mgmt`)
- `name` fields: PascalCase (e.g., `HypertensionManagement`)
- `title` fields: Natural language (e.g., "Hypertension Management Pathway")
- `canonical` fields: Fully-qualified URL (e.g., `http://example.org/fhir/PlanDefinition/htn-mgmt`)
- `expression` fields in actions: Must exactly match CQL `defines` names (case-sensitive)

### Standard Code Systems (Preferred)
| Content Type | System |
|-------------|--------|
| Observations / Questionnaire items | LOINC (`http://loinc.org`) |
| Conditions / Procedures | SNOMED CT (`http://snomed.info/sct`) |
| Diagnoses | ICD-10-CM (`http://hl7.org/fhir/sid/icd-10-cm`) |
| Medications | RxNorm (`http://www.nlm.nih.gov/research/umls/rxnorm`) |

### CQL/FHIRPath Extensions (Optional)
L3 artifacts support optional `extensions.cql` and `extensions.fhirpath` blocks for teams that need executable logic. These are not required for L3 promotion.

---

## 4. YAML Validation in Bash

**Finding**: `yq` is the clear recommendation across all four decision criteria.

| Criterion | Winner | Reason |
|-----------|--------|--------|
| Fewest dependencies | `yq` | Single native Go binary (~13 MB), zero runtime deps |
| Required + optional field distinction | `yq` | `yq eval ".field"` returns `"null"` for missing fields; clean bash loop logic |
| macOS + Linux portability | `yq` | `brew install yq` / `apt-get install yq` / Docker `apk add yq` — all architectures |
| No language runtime | `yq` | Self-contained binary; Python (`yamale`), Node (`ajv`), all excluded |

**Alternatives rejected**:
- `grep`/`awk`: Cannot validate nested structures or distinguish missing vs. empty
- `jq` + `yq` (YAML→JSON pipeline): Adds `oniguruma` library dependency; overkill for config validation
- `yamale`: Requires Python runtime — violates zero-dependency constraint
- `ajv`: Requires Node.js runtime — violates zero-dependency constraint

### Validation Pattern (rh-skills validate implementation)

```bash
validate_yaml_artifact() {
    local file="$1"
    local -a required_fields=("$2")   # Passed as array
    local -a optional_fields=("$3")
    local errors=() warnings=()

    # 1. Syntax check
    yq eval '.' "$file" >/dev/null 2>&1 || {
        echo "ERROR: Invalid YAML syntax in $file" >&2; return 1
    }

    # 2. Required fields — block promotion on failure
    for field in "${required_fields[@]}"; do
        value=$(yq eval ".$field" "$file" 2>/dev/null)
        [[ "$value" == "null" || -z "$value" ]] && errors+=("$field")
    done

    # 3. Optional fields — warn but do not block
    for field in "${optional_fields[@]}"; do
        value=$(yq eval ".$field" "$file" 2>/dev/null)
        [[ "$value" == "null" || -z "$value" ]] && warnings+=("$field")
    done

    # 4. Emit warnings (non-blocking)
    [[ ${#warnings[@]} -gt 0 ]] && \
        printf '[WARN] Missing optional fields: %s\n' "${warnings[*]}" >&2

    # 5. Block on errors
    if [[ ${#errors[@]} -gt 0 ]]; then
        printf '[FAIL] Missing required fields: %s\n' "${errors[*]}" >&2
        return 1
    fi

    echo "[PASS] Validation passed"
    return 0
}
```

### Validation Output (JSON mode for tracking artifact)
```json
{
  "status": "warnings",
  "file": "l2/screening-criteria.yaml",
  "timestamp": "2026-04-03T14:15:00Z",
  "errors": [],
  "warnings": ["references", "tags"]
}
```

**Decision**: `yq` is a required dependency alongside `jq` and `curl`. All three are installable via `brew`/`apt` with no language runtime.

---

## 5. Bash Testing with bats-core

**Finding**: `bats-core` is the right tool. Installable via `brew install bats-core`, `npm install --save-dev bats`, or `apt-get install bats`. No language runtime required.

### Test Structure
```bash
#!/usr/bin/env bats

setup() {
  # Runs before each test — creates isolated temp dir
  export TEST_DIR="${BATS_TMPDIR}/test-$$"
  mkdir -p "$TEST_DIR"
  cd "$TEST_DIR"
}

teardown() {
  rm -rf "$TEST_DIR"
}

@test "rh-skills init creates skill directory structure" {
  run rh-skills init diabetes-screening --description "A screening skill"
  [ "$status" -eq 0 ]
  [ -d "skills/diabetes-screening/l1" ]
  [ -d "skills/diabetes-screening/l2" ]
  [ -d "skills/diabetes-screening/l3" ]
  [ -f "skills/diabetes-screening/SKILL.md" ]
  [ -f "skills/diabetes-screening/tracking.yaml" ]
}
```

### Key Patterns
- `run <command>` captures status + output; `$status`, `$output`, `${lines[@]}` available
- `$BATS_TMPDIR` auto-isolated per test run
- `--separate-stderr` flag separates stdout from stderr in assertions
- `bats-mock` (via npm or git subtree) stubs external commands: `stub curl`, `stub git`

### Mocking LLM Calls in Tests
```bash
setup() {
  # Stub curl to return fixture response without network
  stub curl "echo '{\"content\":[{\"text\":\"mocked response\"}]}'"
}
```

### Test Organization
```
tests/
├── unit/
│   ├── rh-skills init.bats        # Scaffold command
│   ├── rh-skills promote.bats     # Promotion + validation
│   ├── rh-skills validate.bats    # Schema validation
│   ├── rh-inf-status.bats      # Tracking artifact read
│   └── rh-skills list.bats        # Repository listing
└── integration/
    └── skill-lifecycle.bats  # Full L1→L2→L3 workflow
```
