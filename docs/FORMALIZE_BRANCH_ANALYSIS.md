# Formalize Branch Analysis

**Branch:** `formalize`  
**Base:** 73 commits ahead of `main`  
**Scope:** ~18K lines added (+581 deleted)  
**Files Changed:** 83 files

---

## 1. HIGH-LEVEL SUMMARY

The **formalize branch** is a **major architectural refactor** of the L2→L3 formalization pipeline:

### Core Changes
- **New FHIR builder pattern** — Replaces generic LLM-stub generation with dedicated type-specific builders:
  - `DecisionTableBuilder` for event-condition-action logic (Recommendation PlanDefinitions)
  - `CarePathwayBuilder` for clinical workflows (clinical-protocol PlanDefinitions)
  - Support for prerequisite hoisting (condition deduplication) via `ConditionHoister`

- **Evidence traceability enforcement** — Evidence linkage is now **mandatory** (validation error):
  - Decision-table rules must have `evidence_traceability_ids[]`
  - Care-pathway recommendation-like steps must have `evidence_traceability_ids[]`
  - Inferred recommendations require `provenance.rationale`

- **L2 validation framework** — New validators for structural correctness:
  - `validators/decision_table.py` — Comprehensive decision-table validation
  - `validators/care_pathway.py` — Comprehensive care-pathway validation

- **New extraction workflow** — `promote derive` command for L1→L2 artifact generation with body-file support

- **Comprehensive documentation & testing** — AI iteration guide, CRS iteration log, ~1400 new test lines

---

## 2. DETAILED BREAKDOWN

### 2.1 Architecture: FHIR Builders

#### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/rh_skills/fhir/builders/decision_table_builder.py` | 618 | Builds Recommendation PlanDefinitions (eca-rule) from decision-table rules. Maps events→PlanDefinitions, groups rules by event, applies evidence/strength metadata. |
| `src/rh_skills/fhir/builders/care_pathway_builder.py` | 930 | Builds clinical-protocol PlanDefinitions from care-pathway steps. Supports rule-linkage, strategy generation, and phase decomposition. |
| `src/rh_skills/fhir/builders/condition_hoister.py` | 412 | Analyzes decision tables to identify shared preconditions across sibling actions; deduplicates via prerequisite hoisting to reduce CQL complexity. |
| `src/rh_skills/fhir/builders/action_tree.py` | 515 | Builds state-based action trees with unmet/met branches from L2 rules. Supports nested conditions and default fallback actions. |
| `src/rh_skills/fhir/builders/condition_merger.py` | 270 | Topic-level condition registry for deduplicating conditions across multiple decision-table artifacts (for CQL Library generation). |

#### Modified Files

| File | Changes | Impact |
|------|---------|--------|
| `src/rh_skills/fhir/builders/base.py` | +110 lines | Added shared evidence/strength helper methods: `build_evidence_claim_index()`, `build_evidence_related_artifacts()`, `build_strength_of_recommendation_extension()`. |

### 2.2 Validators: L2 Artifact Validation

#### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/rh_skills/validators/decision_table.py` | 519 | **Mandatory validation for decision-table artifacts.** Checks: rule references valid events/conditions/actions, actions/rules have `evidence_traceability_ids[]` (rules: ERROR, actions: WARN), evidence traceability entries reference valid claim IDs, inferred provenance includes rationale, pathway phase assignments. |
| `src/rh_skills/validators/care_pathway.py` | 314 | **Mandatory validation for care-pathway artifacts.** Checks: recommendation-like steps have `evidence_traceability_ids[]` (ERROR), proper parent-child nesting, rule-linkage consistency, semantic alignment between step label and action labels. |

### 2.3 Commands: Extract & Formalize

#### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/rh_skills/commands/derive.py` | 212 | Helper module for `promote derive` — L1→L2 artifact generation (moved from inline in `promote.py`). |

#### Modified Files

| File | Lines Changed | Key Changes |
|------|----------------|------------|
| `src/rh_skills/commands/formalize.py` | +2000 | **Complete rewrite (~3000 total lines).** Now uses builder classes instead of LLM stubs. Implements: builder selection by artifact type, evidence linkage validation (error on missing), strategy-specific resource generation, condition hoisting for CQL. |
| `src/rh_skills/commands/promote.py` | +730 | **Evidence linkage guidance updated.** Changed wording from "should include" to "must include" for `evidence_traceability_ids[]`. New `derive` command for L1→L2 promotion. Added body-file support for structured deriving. |

### 2.4 Schemas & Configuration

#### Modified

| File | Changes | Detail |
|------|---------|--------|
| `src/rh_skills/schemas/l2-schema.yaml` | +125 lines | Updated decision-table and care-pathway section definitions to mark `evidence_traceability_ids[]` as required in comments. Updated guidance text. |

#### New

- `schemas/extract-plan-schema.yaml` — Schema for extract-plan.yaml artifacts
- `schemas/concepts-plan-schema.yaml` — Schema for concepts-plan.yaml terminology artifacts

### 2.5 Skills & Documentation

#### New Documentation

| File | Lines | Purpose |
|------|-------|---------|
| `docs/AI_ITERATION_GUIDE.md` | 674 | **Complete guide for extract→formalize→package iteration workflow.** Step-by-step instructions, environment setup, troubleshooting, and examples using AAO CRS case study. |
| `docs/CRS_ITERATION_LOG.md` | 452 | **Real iteration log from AAO CRS surgical management project.** Documents evidence linkage fixes, builder integration, packaging workflow. |
| `skills/.curated/rh-inf-extract/decision-table-guide.md` | 1273 | **Comprehensive extraction guidance for decision tables.** Sections on event extraction, condition modeling, rule construction, evidence traceability, with multiple worked examples. |

#### Updated Skills

- `skills/.curated/rh-inf-formalize/SKILL.md` — Updated with builder-based formalization workflow
- `skills/.curated/rh-inf-extract/SKILL.md` — Updated with evidence linkage requirements
- `skills/.curated/rh-inf-extract/reference.md` — Enhanced with extraction patterns and edge cases

### 2.6 Tests

#### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `tests/unit/test_fhir_builder_evidence.py` | 119 | Tests for evidence traceability in builder output (decision-table citations, care-pathway no-strength). |
| `tests/unit/test_formalize_evidence.py` | 144 | Tests for evidence linkage helpers: `_build_evidence_claim_index()`, `_build_related_artifacts()`, `_build_strength_extension()`. |
| `tests/fhir/test_condition_hoister.py` | 213 | Low-level tests for condition hoisting analysis and classification. |
| `tests/fhir/test_cql_generator.py` | 80 | Tests for CQL stub generation from decision-table conditions. |
| `tests/fhir/test_crs_formalize.py` | 100 | Integration test for AAO CRS artifact formalization end-to-end. |
| `tests/fhir/validate_builders.py` | 310 | Validation helpers for builder resource output (structure, metadata, action nesting). |
| `tests/fhir/validate_hoister.py` | 81 | Validators for hoister classification output. |

#### Modified Files

| File | Additions | Detail |
|------|-----------|--------|
| `tests/test_formalize_command.py` | +1229 lines | Massive expansion covering: builder selection, evidence linkage validation, rule-level plan generation, strategy selection, care-pathway decomposition, assessment questionnaire linking. |
| `tests/unit/test_validate.py` | +1272 lines | New comprehensive test suite for decision-table and care-pathway validation, including mandatory evidence-link enforcement test cases. |
| `tests/unit/test_promote.py` | +378 lines | Updated tests for new `derive` command and evidence linkage guidance. |

---

## 3. REGRESSIONS & GAPS

### 3.1 Potential Regressions

#### 1. **Evidence Linkage Now Mandatory** ⚠️ BREAKING
- **Issue:** Any L2 artifact with recommendation rules/steps **must** carry `evidence_traceability_ids[]` or validation fails.
- **Impact:** Existing projects with L2 artifacts lacking evidence links will fail validation at promote/formalize time.
- **Mitigation:** 
  - Validation errors are clear and actionable
  - Extraction guidance enforces linkage upfront
  - Consider migration path for existing external repos
- **Status:** Intentional design; enforcement is feature, not regression

#### 2. **Builder Structure Assumptions**
- **Issue:** New builders assume well-formed L2 (events, conditions, actions, rules sections). Malformed L2 produces cryptic errors.
- **Impact:** Users with non-standard L2 may see unclear builder failures instead of graceful stubs.
- **Mitigation:** L2 validators run before builders and catch structural issues early.
- **Status:** Expected; validators are defense layer.

#### 3. **Care-Pathway Rule Linkage Ambiguity**
- **Issue:** Care-pathway steps without explicit `rule_id` are linked to decision-table rules via semantic matching of action labels. Ambiguous matches could produce unexpected cross-links.
- **Status:** Current behavior is conservative (high-confidence matches only); low risk of false positives.

#### 4. **CQL Logic Not Applicable to Care-Pathway**
- **Issue:** Care-pathway artifacts generate orchestration (protocols), not decision logic. No CQL Library for care-pathways.
- **Status:** Expected design; care-pathway is sequencing, not conditions. Decision-table is the logic layer.

---

### 3.2 Known Gaps & Open Items

#### 1. **CQL Authoring Not Automated** 📌
- **Issue:** Framework does not auto-generate `.cql` files. Must be hand-authored via `rh-inf-cql` skill.
- **Status:** Intentional — CQL is complex; human review required.
- **Flag:** formalize emits info message if `.cql` not found; formalize continues anyway (non-blocking).
- **Action:** Users must author CQL separately or run `rh-skills cql ...` to generate stubs.

#### 2. **Assessment Artifact Linkage Fragile** 🔧
- **Issue:** Decision-table actions with `assessment_artifact: questionnaire-name` link to L3 Questionnaire resources by name convention. Naming drift can break linkage.
- **Status:** Linkage happens at formalize time via canonical URL matching; medium risk of breakage if names change.
- **Action:** Document naming conventions; consider stronger reference validation.

#### 3. **Provenance.rationale Inference Incomplete** 🔧
- **Issue:** Care-pathway steps with `provenance.source: inferred` require `provenance.rationale`, but extraction guidance does not always auto-populate this field.
- **Status:** Validator catches the gap and errors, requiring manual L2 fix.
- **Action Needed:** Either auto-populate rationale during derive or document rationale as extraction requirement.

#### 4. **Strength-of-Recommendation Not Inferred** 🔧
- **Issue:** If L2 evidence claims lack `strength` field, formalize does not infer it from guideline grading or other metadata.
- **Status:** Validator warns (soft requirement); formalize continues without strength extension.
- **Action Needed:** Consider inference from guideline strength levels or add strength-scoring guidance.

#### 5. **Package Workspace Stale File Pollution** 🧹
- **Issue:** After formalize, old computable files may linger in `topics/{topic}/computable/`. Package only includes current outputs; stale files are ignored but pollute the directory.
- **Status:** User must manually clean or run `--force --pack` to rebuild workspace.
- **Mitigation:** Add `--clean` flag to formalize to auto-remove stale outputs, or document cleanup steps in AI_ITERATION_GUIDE.

---

### 3.3 Code Health: Unused & Potential Refactors

#### Unused/Dead Code Found

1. **`src/rh_skills/fhir/builders/cql_generator.py`** — Multiple TODO markers
   - **Status:** Stub CQL with TODO comments throughout (15 instances)
   - **Lines:** 95, 109, 150-156, 187, 194, 222, 231, 238
   - **Action Needed:** Implement LLM-based CQL expansion or document as future work

#### Potential Refactoring Opportunities

1. **`formalize.py` is too large (3000+ lines)** 🔴 HIGH PRIORITY
   - **Issue:** Single 3000-line command file mixing CLI orchestration, LLM invocation, builder dispatch, strategy selection, error handling
   - **Recommend:**
     - Extract builder dispatch to `_formalize_strategies.py`
     - Extract LLM prompting to `_formalize_llm.py`
     - Extract strategy-specific logic to `_formalize_[strategy]_strategies.py`
     - Keep CLI entry point light (~200 lines)
   - **Benefit:** Improves testability, maintainability, and code reuse

2. **Builder duplication in `decision_table_builder.py` and `care_pathway_builder.py`**
   - **Issue:** Both builders have similar evidence linking logic, action tree building, metadata application
   - **Recommend:**
     - Extract common builder patterns to `base.py` (mixin or abstract methods)
     - `_apply_recommendation_metadata()` — common to both
     - `_build_action_definitions()` — common logic
     - `_build_related_artifacts_from_evidence()` — evidence linkage
   - **Benefit:** ~200 lines of deduplication

3. **Validators `decision_table.py` and `care_pathway.py` share logic**
   - **Issue:** Both call `_validate_traceability_links()` and `_validate_provenance()` with similar implementation
   - **Recommend:**
     - Extract to `validators/base_validator.py`
     - Reuse `_validate_traceability_links()` and `_validate_provenance()` helpers
     - Keep artifact-specific logic in submodules
   - **Benefit:** ~100 lines of deduplication

4. **CQL stub generation needs refactor** 🔴 HIGH PRIORITY
   - **Issue:** `cql_generator.py` is all stubs with TODO markers; not ready for production
   - **Recommend:**
     - Define clear interface: `generate_cql_from_decision_table(L2_data) -> CQL_string`
     - Implement either:
       - LLM-based expansion (call Claude/Ollama to expand stubs to full CQL)
       - Rule-based code generation (map L2 conditions/actions to CQL patterns)
     - Add comprehensive test cases
   - **Timeline:** Post-MVP; document as known limitation

5. **Builder test organization** 
   - **Issue:** Tests spread across `tests/fhir/`, `tests/unit/`, `tests/test_formalize_command.py`
   - **Recommend:**
     - Consolidate builder tests to `tests/fhir/test_builders/`
     - `test_decision_table_builder.py`, `test_care_pathway_builder.py`, `test_hoister.py`
     - Keep integration tests in `test_formalize_command.py`
   - **Benefit:** Clearer test structure, easier navigation

6. **CLI command aliases & dispatch**
   - **Issue:** `formalize`, `derive`, `promote`, etc. are separate commands; some overlap in L2 artifact handling
   - **Recommend:**
     - Consider unified `promote` command with subcommands (`promote derive`, `promote verify`, etc.)
     - Or keep separate but document interaction clearly
   - **Timeline:** Post-MVP refactor

7. **Tracking.yaml reconciliation**
   - **Issue:** No automatic sync between tracked artifacts and actual L2 files; can drift over time
   - **Recommend:**
     - Add `rh-skills status --reconcile` mode to auto-sync tracking
     - Or add `rh-skills promote verify-tracking` command
   - **Timeline:** Future; currently manual verification required

---

## 4. SUMMARY TABLE: Risk vs. Impact

| Item | Risk Level | Impact | Mitigation | Action |
|------|-----------|--------|-----------|--------|
| Evidence linkage now mandatory | 🔴 HIGH | Breaks existing L2 artifacts | Clear error messages, migration guide | Document backward-compat path |
| CQL generation incomplete | 🔴 HIGH | CQL is only stubs with TODOs | Document limitation, block deploy if CQL required | Implement LLM-based CQL expansion |
| formalize.py size (3000 lines) | 🟡 MEDIUM | Hard to test & maintain | Modular design exists; refactor | Extract builder dispatch, LLM logic |
| ActivityDefinition.code missing | 🟡 MEDIUM | Invalid FHIR output | Emit warning, document workaround | Require concept-coding for auto-population |
| Builder assumptions on L2 structure | 🟡 MEDIUM | Cryptic errors on malformed L2 | Validators run first | Add builder-level assertions |
| Unused warning function in formalize | 🟢 LOW | Code bloat, confusion | Already deprecated | Remove `_warn_missing_decision_table_evidence_links()` |
| CQL TODO markers | 🟢 LOW | Code clutter | Document as known limitation | Address in future CQL expansion work |
| Package stale file pollution | 🟢 LOW | Directory clutter, potential confusion | Document cleanup steps | Consider `--clean` flag |

---

## 5. DEPLOYMENT RECOMMENDATIONS

### Ready for Deploy (MVP)
✅ FHIR builders (decision-table, care-pathway)  
✅ L2 validators (decision-table, care-pathway)  
✅ Evidence traceability enforcement  
✅ Documentation & guides  
✅ Test coverage for core workflows  

### Post-MVP (Stabilization)
⏳ CQL generation (replace TODO stubs with real logic)  
⏳ formalize.py refactoring (split into modules)  
⏳ Builder deduplication & optimization  
⏳ Tracking.yaml reconciliation commands  
⏳ Backward-compatibility migration path  

### External Repo Readiness
⚠️ **ACTION REQUIRED:** Audit AAO and other external repos for L2 artifacts missing evidence linkage before deploying this branch to production.

---

## 6. FILES SUMMARY

### New in Formalize Branch (83 files changed)

**Builders (New):**
- `src/rh_skills/fhir/builders/decision_table_builder.py`
- `src/rh_skills/fhir/builders/care_pathway_builder.py`
- `src/rh_skills/fhir/builders/condition_hoister.py` (also on formalize, significant for decision-table support)
- `src/rh_skills/fhir/builders/action_tree.py`
- `src/rh_skills/fhir/builders/condition_merger.py`

**Validators (New):**
- `src/rh_skills/validators/decision_table.py`
- `src/rh_skills/validators/care_pathway.py`

**Commands (New/Modified):**
- `src/rh_skills/commands/derive.py` (NEW)
- `src/rh_skills/commands/formalize.py` (MAJOR REWRITE)
- `src/rh_skills/commands/promote.py` (UPDATED)

**Tests (New):**
- `tests/unit/test_fhir_builder_evidence.py`
- `tests/unit/test_formalize_evidence.py`
- `tests/fhir/test_condition_hoister.py`
- `tests/fhir/test_cql_generator.py`
- `tests/fhir/test_crs_formalize.py`
- `tests/fhir/validate_builders.py`
- `tests/fhir/validate_hoister.py`

**Documentation (New):**
- `docs/AI_ITERATION_GUIDE.md`
- `docs/CRS_ITERATION_LOG.md`
- `skills/.curated/rh-inf-extract/decision-table-guide.md`

---

**Last Updated:** 2026-06-09  
**Branch:** formalize  
**Status:** Pre-merge analysis
