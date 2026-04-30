# Extract Workflow Report

## Overview

The **rh-inf-extract** skill is the **L2 structured artifact extraction** stage of the lifecycle. It transforms normalized L1 source material (Markdown files from ingest) into proposed structured (L2) artifacts through a three-stage workflow:

1. **PLAN**: Analyze sources and generate a reviewer-gated extraction plan
2. **IMPLEMENT**: Execute approved derivations via CLI commands (deterministic writes only)
3. **VERIFY**: Validate all L2 artifacts and confirm required sections

**Guiding principle:** All clinical reasoning happens in the skill; all durable writes go through `rh-skills` CLI commands. The plan→implement gate prevents low-quality artifacts by requiring explicit reviewer approval before any files are written.

---

## CLI Commands

| Command | Purpose | Writes To |
|---------|---------|-----------|
| `rh-skills promote plan <topic> [--force]` | Generate extract review packet | `extract-plan.yaml`, `extract-plan-readout.md`, tracking event |
| `rh-skills promote approve <topic> --artifact <name> --decision <approved\|rejected\|needs-revision> [--add-concern TEXT] [--finalize]` | Record reviewer approval decisions | `extract-plan.yaml` (updated), `extract-plan-readout.md` (regenerated) |
| `rh-skills promote derive <topic> <name> --source <source> [--artifact-type TYPE] [--clinical-question TEXT] [--required-section S] [--evidence-ref REF] [--concern C]` | Create single L2 artifact via LLM | `structured/<name>/<name>.yaml`, tracking event |
| `rh-skills validate <topic> structured <artifact>` | Schema-validate L2 artifact | (read-only) |
| `rh-skills render <topic> structured <artifact>` | Generate human-readable Markdown report with Mermaid diagrams | `structured/<name>/<name>-report.md` |

---

## L2 Artifact Types (7 Standard)

| Type | SME Question | L3 FHIR Target | Key Sections |
|------|-------------|-----------------|--------------|
| **evidence-summary** | What does the evidence say? | Evidence, EvidenceVariable, Citation | summary_points, risk_factors, evidence_traceability |
| **decision-table** | What decisions must be made? | PlanDefinition (eca-rule), Library (CQL) | events, conditions, actions, rules, exceptions |
| **care-pathway** | In what order do things happen? | PlanDefinition (clinical-protocol), ActivityDefinition | triggers, steps (ordered with actor + next-step) |
| **terminology** | What codes define the concepts? | ValueSet, ConceptMap | value_sets, concept_maps |
| **measure** | How do we know it's working? | Measure, Library (CQL) | populations, scoring, improvement_notation |
| **assessment** | What do we ask the patient? | Questionnaire | instrument, items (questions), scoring |
| **policy** | What's required for coverage? | PlanDefinition (eca-rule), Questionnaire (DTR), Library | applicability, criteria, actions |

Custom types allowed when no standard type preserves the clinical purpose (must be justified in plan).

---

## Workflow

```
1. PLAN: rh-skills promote plan <topic>
   ├─ Read tracking.yaml + sources/normalized/*.md + concepts.yaml
   ├─ Pre-execution checks:
   │   ├─ Verify topic exists
   │   ├─ Identify normalized vs un-normalized sources
   │   └─ Check if discovery was run (note if skipped)
   ├─ Analyze sources:
   │   ├─ Infer artifact profiles from source type/count
   │   ├─ Group sources by clinical domain/question
   │   ├─ Propose L2 artifacts using 7-type catalog
   │   └─ Detect cross-source concerns
   ├─ For terminology: use reasonhub MCP (optional)
   │   ├─ Search SNOMED/LOINC/ICD-10/RxNorm
   │   └─ Populate candidate_codes[] in review packet
   ├─ Write extract-plan.yaml (control file)
   ├─ Write extract-plan-readout.md (narrative)
   └─ Event: extract_planned

2. REVIEW GATE: rh-skills promote approve <topic> --artifact <name> --decision approved --finalize
   ├─ Reviewer reads extract-plan-readout.md
   ├─ Per-artifact decisions: approved | rejected | needs-revision
   ├─ Optional: --add-concern, --add-source for refinements
   ├─ Regenerates readout with final decisions
   └─ Plan status → approved

3. IMPLEMENT: rh-skills promote derive <topic> <name> --source <source> ...
   ├─ For each approved artifact:
   │   ├─ Map plan entry → CLI arguments
   │   ├─ LLM generates L2 YAML from L1 source(s)
   │   ├─ Write structured/<name>/<name>.yaml
   │   ├─ Event: structured_derived
   │   ├─ Validate: rh-skills validate <topic> structured <name>
   │   │   ├─ Schema: required fields, type-specific sections
   │   │   ├─ Evidence traceability: claims have evidence entries
   │   │   └─ Conflict records: present when plan listed concerns
   │   ├─ Render: rh-skills render <topic> structured <name>
   │   │   └─ Generate report.md + Mermaid diagrams (`decision-table` requires `events`, `conditions`, `actions`, and `rules`)
   │   └─ Report ✓ or ✗ per artifact
   └─ Stop on first blocking failure

4. VERIFY: rh-skills validate <topic> structured <artifact> (for each)
   ├─ Re-validate schema, sections, evidence traceability
   ├─ Confirm render reports present
   ├─ Check concern records (when plan had concerns)
   ├─ Non-destructive, safe to rerun
   └─ Report pass/fail per artifact

5. HANDOFF → rh-inf-formalize
   ├─ rh-skills promote formalize-plan <topic>
   │   ├─ Scans approved L2 artifacts
   │   ├─ Groups by artifact_type
   │   ├─ Detects FHIR resource type overlaps
   │   └─ Creates formalize-plan.md
   └─ Ready for L3 conversion
```

---

## Key Files

| File | Role |
|------|------|
| `src/rh_skills/commands/promote.py` | Plan generation, approve, derive commands (~1400 lines) |
| `skills/.curated/rh-inf-extract/SKILL.md` | Skill definition; plan/implement/verify modes |
| `skills/.curated/rh-inf-extract/reference.md` | L2 type catalog, validation rules, concern handling |
| `topics/<topic>/process/plans/extract-plan.yaml` | **Control file**: proposed/approved artifacts, sources, concerns |
| `topics/<topic>/process/plans/extract-plan-readout.md` | **Derived**: human-friendly narrative (do not edit directly) |
| `topics/<topic>/structured/<name>/<name>.yaml` | **L2 artifact**: semi-structured clinical content |
| `topics/<topic>/structured/<name>/<name>-report.md` | **Rendered report**: Mermaid diagrams for SME review |
| `topics/<topic>/process/concepts.yaml` | Pre-defined clinical concepts from ingest (input) |
| `tracking.yaml` | Records extract_planned, structured_derived events |

---

## Design Details

### Plan Generation (Deterministic Grouping)

`_group_sources_for_extract_plan()` groups L1 sources by:
1. Source type (guideline, measure, policy, etc.)
2. Count (single source → single artifact proposal)
3. Inferred profiles (e.g., PDF with eligibility rules → decision-table)

**Limitation:** Deterministic planner groups by type, not clinical concerns. If conflicting sources end up in separate artifacts, the reviewer must consolidate using `--add-source` at approval time.

### LLM Usage (Artifact Generation)

`rh-skills promote derive` invokes the LLM backend (`LLM_PROVIDER` env var):
- **System prompt**: Healthcare informatics specialist role
- **User prompt**: Source content + artifact type + clinical question + required sections + evidence/conflict metadata
- **Output**: YAML scaffold with type-specific sections populated
- **Testing**: `LLM_PROVIDER=stub` + `RH_STUB_RESPONSE="<yaml>"` for deterministic tests

### Validation Rules

Post-derive validation checks:
1. Required top-level fields: id, name, title, version, status, domain, description, derived_from[], artifact_type, clinical_question
2. Type-specific required sections (e.g., decision-table MUST have events, conditions, actions, rules)
3. Evidence traceability: claims have evidence[] entries
4. Conflict records present when extract-plan listed unresolved concerns

### Extract → Formalize Linkage

Extract produces approved L2 artifacts → Formalize consumes them:
- `formalize-plan` reads extract-plan.yaml (status: approved)
- Groups eligible inputs by `artifact_type`
- Maps each type to FHIR conversion strategy via `_L3_TARGET_MAP`
- Detects overlapping FHIR resource types across artifacts
