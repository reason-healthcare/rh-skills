# Template-Guided Formalize: Implementation Specification

## Overview

**Template-guided formalize** is a three-phase workflow that separates **architectural decisions** (builder responsibility) from **narrative content** (agent/LLM responsibility).

```
Phase 1 (Generate):  L2 → Builder template with {{TODO}} placeholders + .scaffold.md
Phase 2 (Fill):      {{TODO}} placeholders ← Agent OR LLM (based on mode)
Phase 3 (Merge):     Filled template → validate → Final FHIR JSON
```

### Comparison to Current Approaches

| Approach | Architecture | Content | Reproducibility | Narrative Richness |
|---|---|---|---|---|
| **Main (LLM-only)** | LLM decides (variable) | LLM generates | ❌ Non-deterministic | ✅ Rich |
| **Formalize branch (builder-only)** | Builder decides (fixed) | Builder uses L2 fields | ✅ Deterministic | ⚠️ Thin |
| **Template-guided (proposed)** | Builder decides (fixed) | Agent/LLM fills {{TODO}} | ✅ Deterministic structure | ✅ Rich content |

---

## Three Operational Modes

### Mode 1: Agent-Native (No LLM Provider)

**Configuration:** `LLM_PROVIDER` unset (or empty)

**Behavior:**
- Phase 1: Builder generates template + `.scaffold.md`
- Phase 2: **Agent fills scaffold.md** (required; no fallback)
  - Agent edits `.scaffold.md` with clinical reasoning
  - Agent updates corresponding `{{TODO}}` fields in PlanDefinition.json
  - Unfilled TODOs → validation fails at merge
- Phase 3: Validate + finalize

**Use case:** Agent (Copilot, Claude, Gemini) drives entire workflow with full control

**Example:**
```bash
# Generate template
rh-skills formalize topic artifact --mode template-guided

# Agent reads .scaffold.md, fills TODOs in both scaffold and JSON
# (Agent-native skill instructs agent to do this)

# Merge and finalize
rh-skills formalize topic artifact --mode template-guided --merge-template
```

**Validation:** If any `{{TODO:*}}` remains after merge, validation fails with error listing unfilled placeholders

---

### Mode 2: CLI-First with LLM (LLM Provider Set)

**Configuration:** `LLM_PROVIDER` set in `.rh-skills.toml` or environment

**Behavior:**
- Phase 1: Builder generates template + `.scaffold.md` (scaffolds are informational, not used)
- Phase 2: **CLI calls LLM to fill TODOs**
  - Formalize command detects `LLM_PROVIDER` is set
  - Builds prompt: template structure + TODO descriptions + L2 context
  - LLM generates content for each `{{TODO}}`
  - CLI replaces placeholders with LLM output
- Phase 3: Validate + finalize

**Use case:** CLI-driven workflow; no agent involved; LLM generates content

**Example:**
```bash
# Configure LLM
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Single command: generate + fill + merge + finalize
rh-skills formalize topic artifact --mode template-guided
# Internally:
# → Phase 1: Generate template
# → Phase 2: Call LLM for each TODO
# → Phase 3: Merge + validate
```

---

### Mode 3: Deterministic (Pure Builder)

**Configuration:** `--deterministic` flag (overrides LLM_PROVIDER)

**Behavior:**
- Phase 1: Builder generates template with {{TODO}} placeholders
- Phase 2: **All TODOs resolved via deterministic fallback functions** (no agent, no LLM)
- Phase 3: Validate + finalize (all TODOs replaced; no placeholders remain)

**Use case:** CI/CD, reproducibility tests, quick iteration during development

**Example:**
```bash
# Force deterministic, even if LLM_PROVIDER is set
rh-skills formalize topic artifact --mode template-guided --deterministic

# Output: Same FHIR every time (same L2 → same FHIR)
# No agent involvement, no LLM calls
```

---

## Phases in Detail

### Phase 1: Generate Template

**Input:** L2 artifact YAML

**Output:**
- `topics/<topic>/computable/<Artifact>-<ResourceType>.json` (template with `{{TODO:*}}` markers)
- `topics/<topic>/process/scaffolds/<Artifact>.scaffold.md` (agent-facing guide)

**Builder responsibility:**
1. Read L2 artifact
2. Build context dict with **architectural fields**:
   - `id`, `url`, `version`, `status`, `date` (metadata)
   - `action[]` structure with nesting/prerequisites (architecture)
   - `condition[]` hoisting strategy (architecture)
3. Mark **narrative fields** with `{{TODO:field_name}}`:
   - `description`, `title` (if enrichment needed)
   - `action[].description` (rule rationale/guidance)
   - `action[].documentation` (if applicable)
4. Render template → JSON with TODOs
5. Generate `.scaffold.md` with TODO descriptions and guidance for agent

**Template Context Example:**
```python
context = {
    "id": "crs-surgical-assessment",
    "url": "https://example.com/PlanDefinition/crs-surgical-assessment",
    "version": "1.0.0",
    "status": "active",
    "date": "2026-06-09",
    "name": "CrsSurgicalAssessment",
    "title": "CRS Surgical Assessment Recommendation",
    # Architectural fields (no TODOs)
    "action": [
        {
            "id": "rule-001",
            "type": "create",
            "trigger": {...},
            "condition": [...],  # Hoisted conditions (architectural)
            # Narrative field with TODO
            "title": rule.get('name', 'Unknown Rule'),
            "description": "{{TODO:rule_rationale}}",  # Will be filled or has fallback
        }
    ],
    # Deterministic fields (no TODOs)
    "relatedArtifact": [...]
}
```

**Jinja Template (unchanged):**
```jinja2
{
  "resourceType": "PlanDefinition",
  "id": "{{ id }}",
  "action": [
    {% for action in action %}
    {
      "id": "{{ action.id }}",
      "title": "{{ action.title }}",
      "description": {{ action.description | tojson }}  # Can be {{TODO:*}} or filled
    }
    {% endfor %}
  ]
}
```

**Rendered Output (Phase 1):**
```json
{
  "resourceType": "PlanDefinition",
  "id": "crs-surgical-assessment",
  "action": [
    {
      "id": "rule-001",
      "title": "Assess Surgical Candidacy",
      "description": "{{TODO:rule_rationale}}"
    }
  ]
}
```

---

### Phase 2: Fill TODOs

#### Agent-Native Mode

**Agent action:**
1. Read `.scaffold.md`
2. For each TODO entry:
   - Understand the clinical context
   - Write enriched content (evidence-based, guideline-aligned)
   - Update `.scaffold.md` with filled content
3. Apply changes to PlanDefinition.json:
   - Replace `"description": "{{TODO:rule_rationale}}"` with actual content
4. Trigger merge command

**Example `.scaffold.md`:**
```markdown
# PlanDefinition Scaffold: crs-surgical-assessment

## TODO: rule_rationale

**Field:** `action[0].description`
**Artifact:** Decision Table (crs-surgical-management)
**Rule ID:** rule-001

**L2 Context:**
- Rule name: "Assess Surgical Candidacy"
- Rule ID: rule-001
- Evidence: dt-002, dt-004
- L2 rationale: "Determine if patient meets surgical criteria"

**TODO: Write enriched rationale**
- What is the clinical reasoning for this recommendation?
- When should this assessment occur?
- Any contraindications or edge cases?

**Current (from L2):** "Determine if patient meets surgical criteria"

**Proposed (agent fills):** [AGENT EDITS HERE]
```

**Agent fills:**
```markdown
**Proposed (agent fills):** "Assess whether the patient is a surgical candidate based on tumor staging (AJCC), functional status (ECOG 0-2), and absence of distant metastases. This assessment informs staging laparoscopy or imaging-guided biopsy decisions."
```

**Agent updates JSON:**
```json
{
  "description": "Assess whether the patient is a surgical candidate based on tumor staging (AJCC), functional status (ECOG 0-2), and absence of distant metastases. This assessment informs staging laparoscopy or imaging-guided biopsy decisions."
}
```

#### CLI-First Mode

**CLI action:**
1. Detect `LLM_PROVIDER` is set
2. Build LLM prompt for each TODO:
   ```
   Artifact: crs-surgical-management (decision-table)
   Rule: Assess Surgical Candidacy (rule-001)
   
   Field: action[].description (clinical rationale/guidance)
   
   L2 context:
   - Rule name: Assess Surgical Candidacy
   - Evidence claim IDs: dt-002, dt-004
   - L2 description: Determine if patient meets surgical criteria
   
   Clinical context:
   [Include relevant L2 artifact sections]
   
   Task: Generate a clear, evidence-based clinical rationale for this recommendation. Explain the clinical reasoning, indications, and when this assessment applies.
   ```
3. Call LLM (via configured provider)
4. Parse response
5. Replace placeholder in JSON

---

### Phase 3: Merge and Finalize

**Input:**
- PlanDefinition.json (with filled content, no remaining `{{TODO:*}}` markers)
- `.scaffold.md` (informational; not used in this phase)

**Validation:**
1. Scan JSON for any remaining `{{TODO:*}}` markers
   - If found → ERROR with list of unfilled placeholders
   - Message: "Agent-native mode: all TODOs must be filled before merge. Unfilled: rule_rationale, action_guidance"
2. Validate FHIR structure (existing normalize + validate logic)
3. Write to computable/

**Output:**
- `topics/<topic>/computable/<Artifact>-PlanDefinition.json` (clean, no TODOs)
- `topics/<topic>/computable/<Artifact>-ActivityDefinition.json` (if applicable)
- Update tracking.yaml

**Command:**
```bash
rh-skills formalize topic artifact --mode template-guided --merge-template
```

Or automatically triggered if Phase 2 fills all TODOs in one pass (e.g., LLM mode).

---

## TODO Fields and Fallbacks

### Fallback Strategy

**Fallback function:** Deterministic value derived from L2 artifact or builder-computed fields.

**Goal:** Ensure no broken/incomplete FHIR if fallback is applied.

### Decision-Table PlanDefinition

| Field | TODO Name | Fallback |
|---|---|---|
| `description` | `description` | `event.description` or `"Recommendation for [event-name]"` |
| `action[].title` | *(no TODO)* | `rule.name` |
| `action[].description` | `rule_rationale` | `rule.rationale` or `rule.name` |
| `action[].documentation[].documentation` | `action_guidance` | `""` (empty) |

**Example with Jinja:**
```jinja2
"description": "{% if '{{TODO:description}}' in description_raw %}{{ description_raw }}{% else %}{{ fallback_description }}{% endif %}"
```

Or simpler — builder provides fallback in context:
```python
context = {
    "description": event.get('description') or f"Recommendation for {event_id}",
    # Not a TODO — always filled
}
```

Then for narrative TODOs (optional enrichment):
```python
context = {
    "action": [
        {
            "description": "{{TODO:rule_rationale}}" if TEMPLATE_MODE else (rule.get('rationale') or rule.get('name', 'Rule'))
        }
    ]
}
```

### Care-Pathway PlanDefinition

| Field | TODO Name | Fallback |
|---|---|---|
| `description` | `description` | `pathway.description` or `"Clinical pathway"` |
| `action[].title` | *(no TODO)* | Step name or action label |
| `action[].description` | `step_rationale` | Step description from L2 |
| `action[].documentation` | `step_guidance` | `""` (empty) |

---

## CLI Syntax

### Generate Template

```bash
rh-skills formalize <topic> <artifact> --mode template-guided [--dry-run]
```

**Options:**
- `--mode template-guided` — Enable template-guided mode (generate phase)
- `--dry-run` — Show what would be generated without writing

**Output:**
- PlanDefinition.json with `{{TODO:*}}` placeholders
- .scaffold.md guide for agent

### Merge Template

```bash
rh-skills formalize <topic> <artifact> --mode template-guided --merge-template
```

**Options:**
- `--merge-template` — Enter merge phase (Phase 3)

**Behavior:**
- Scan JSON for unfilled TODOs
- If Agent-native and TODOs remain → ERROR
- If CLI-first → call LLM for unfilled TODOs (if not already done)
- Validate + finalize

### Force Deterministic

```bash
rh-skills formalize <topic> <artifact> --mode template-guided --deterministic
```

**Options:**
- `--deterministic` — Use deterministic fallback for all TODOs (skip Phase 2 agent/LLM)

**Behavior:**
- Phase 1: Generate template
- Phase 2 (skipped): All TODOs replaced with fallback values immediately
- Phase 3: Validate + finalize

**Equivalent:** Single-pass execution (no explicit merge needed)

---

## Operational Workflows

### Workflow 1: Agent-Native (Full Agent Control)

```bash
# Terminal (Agent-Native Copilot/Claude):

# Step 1: Generate template
$ rh-skills formalize crs surgical-management --mode template-guided
✓ Generated: topics/crs/computable/SurgicalManagement-PlanDefinition.json
✓ Generated: topics/crs/process/scaffolds/surgical-management.scaffold.md

# Agent reads .scaffold.md, fills TODOs (via rh-inf-formalize skill instructions)
# Agent also updates PlanDefinition.json with filled content

# Step 2: Merge template (Agent triggers)
$ rh-skills formalize crs surgical-management --mode template-guided --merge-template
✓ No unfilled TODOs found
✓ Validated 1 PlanDefinition, 2 ActivityDefinitions
✓ Written: topics/crs/computable/SurgicalManagement-PlanDefinition.json
✓ Updated: tracking.yaml
```

**Agent skill instruction (rh-inf-formalize SKILL.md):**
```markdown
### Phase 2: Fill TODOs (Agent-Native Mode)

1. Read `topics/<topic>/process/scaffolds/<artifact>.scaffold.md`
2. For each TODO entry:
   - Understand the clinical context and L2 artifact
   - Write evidence-based, clinically sound content
   - Update the JSON file: replace `{{TODO:field_name}}` with your content
3. Trigger merge:
   $ rh-skills formalize <topic> <artifact> --mode template-guided --merge-template

Do NOT skip any TODOs — merge will fail if any remain.
```

---

### Workflow 2: CLI-First with LLM

```bash
# Terminal (No Agent):

# Configure LLM
$ export LLM_PROVIDER=anthropic
$ export ANTHROPIC_API_KEY=sk-ant-...

# Single command: generate + fill (via LLM) + merge
$ rh-skills formalize crs surgical-management --mode template-guided
ℹ Generating template...
✓ Generated: topics/crs/computable/SurgicalManagement-PlanDefinition.json

ℹ LLM_PROVIDER detected; filling TODOs via LLM...
  → Calling LLM for rule_rationale (rule-001)...
  → Calling LLM for action_guidance (action-001)...
✓ Filled 2 TODOs

ℹ Merging and validating...
✓ No unfilled TODOs
✓ Validated 1 PlanDefinition, 2 ActivityDefinitions
✓ Written: topics/crs/computable/SurgicalManagement-PlanDefinition.json
✓ Updated: tracking.yaml
```

---

### Workflow 3: Deterministic (No Agent, No LLM)

```bash
# Terminal:

# Force deterministic (even if LLM_PROVIDER is set)
$ rh-skills formalize crs surgical-management --mode template-guided --deterministic
ℹ --deterministic flag: using builder fallbacks (ignoring LLM_PROVIDER)

ℹ Generating template and applying fallbacks...
✓ Generated and filled: topics/crs/computable/SurgicalManagement-PlanDefinition.json

ℹ Validating...
✓ No TODOs remaining
✓ Validated 1 PlanDefinition, 2 ActivityDefinitions
✓ Written: topics/crs/computable/SurgicalManagement-PlanDefinition.json
✓ Updated: tracking.yaml

# Output is identical every run (same L2 → same FHIR)
```

---

## Implementation Checklist

### Phase 1: Generate Template (with TODOs)

- [ ] Identify narrative fields per artifact type (decision-table, care-pathway, etc.)
- [ ] Extend builder to accept `template_mode=True` parameter
- [ ] Builder outputs `{{TODO:field_name}}` instead of computed value for narrative fields
- [ ] Fallback functions defined for each TODO (deterministic values)
- [ ] Generate `.scaffold.md` from template structure + TODO descriptions
- [ ] Store template JSON in computable/ (overwrite existing on re-run)

### Phase 2: Fill TODOs

**Agent-Native:**
- [ ] rh-inf-formalize skill reads .scaffold.md
- [ ] Skill instructs agent to fill TODOs (with clinical reasoning)
- [ ] Agent updates JSON fields directly
- [ ] Trigger merge command when done

**CLI-First:**
- [ ] Detect `LLM_PROVIDER` in formalize command
- [ ] Build prompt for each TODO (context + L2 + guidance)
- [ ] Call LLM for each unfilled placeholder
- [ ] Replace placeholders in JSON

**Deterministic:**
- [ ] Detect `--deterministic` flag
- [ ] Apply fallback functions to all TODOs
- [ ] No LLM calls; no agent involvement

### Phase 3: Merge and Finalize

- [ ] Scan JSON for remaining `{{TODO:*}}` markers
- [ ] If found (agent-native) → ERROR with unfilled list
- [ ] Validate FHIR structure (existing normalize + validate)
- [ ] Write to computable/
- [ ] Update tracking.yaml

### Testing

- [ ] Test agent-native workflow (manual or scripted)
- [ ] Test CLI-first workflow (with mock LLM)
- [ ] Test deterministic workflow (compare to expected output)
- [ ] Verify fallbacks produce valid FHIR
- [ ] Verify templates render correctly with and without TODOs
- [ ] Test error cases (unfilled TODOs in agent-native)

### Documentation

- [ ] Update docs/FORMALIZE.md with template-guided section
- [ ] Update rh-inf-formalize SKILL.md with Phase 2 instructions
- [ ] Document TODO fields and fallbacks per artifact type
- [ ] Add example workflows to docs/WORKFLOW.md

---

## Design Decisions

1. **No hybrid mode for formalize** — Either agent fills (agent-native) or LLM fills (CLI-first) or fallback (deterministic). No in-between.

2. **Agent-native has no fallback** — Aligns with CQL pattern; agent owns completeness.

3. **{{TODO:field_name}} syntax** — Distinguishes placeholders from regular Jinja variables; easy to scan for unfilled.

4. **Deterministic fallback for all modes** — Ensures no broken artifacts even if agent/LLM skip fields.

5. **Separate .scaffold.md** — Agent-facing guide; not needed for LLM or deterministic modes, but generated anyway for consistency.

6. **Single template layer** — Extend existing Jinja templates; no new template system.

---

## Future Enhancements

- Add `--interactive` flag for agent-native to prompt user per TODO
- Add `--scaffold-only` to generate .scaffold.md without JSON
- Support markdown-based scaffold editing (with merge back to JSON)
- Integrate template validation layer (enforce no extra fields)
- Add `--compare-mode` to show diff between fallback and agent-filled versions
