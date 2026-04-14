# Research: `rh-inf-extract` Skill — Phase 0

**Branch**: `005-rh-inf-extract` | **Date**: 2026-04-14

---

## Decision 1: `extract-plan.md` is a durable review packet, not a transient run sheet

**Decision**: `rh-inf-extract plan <topic>` should write `topics/<topic>/process/plans/extract-plan.md` as a durable reviewer-facing artifact.

**Rationale**:
- 005 centers on a human approval gate; that gate needs a stable, editable artifact.
- The plan must capture reviewer decisions, approval notes, and unresolved conflicts over time.
- Unlike 004 ingest, there is no upstream machine-readable artifact that already serves this role.

**Alternatives considered**:
- Transient stdout-only plan summary — rejected because it cannot serve as an approval record.
- YAML-only machine file — rejected because the primary audience is a human reviewer, not an automation step.

---

## Decision 2: Use a hybrid clinical reasoning catalog for artifact proposals

**Decision**: Artifact proposals should start from a standard catalog but allow topic-specific custom types.

**Rationale**:
- The standard catalog gives consistency across topics and helps reviewers scan the plan quickly.
- Some topics need custom artifact shapes that do not fit a strict closed taxonomy.

**Standard catalog minimums**:
- eligibility / criteria
- exclusions
- risk factors
- decision points
- workflow steps
- terminology / value sets
- measure logic
- evidence summary

**Alternatives considered**:
- Closed fixed catalog — rejected because some topics need custom artifacts.
- Fully free-form artifact typing — rejected because review quality would drift across topics.

---

## Decision 3: Support many-to-many source/artifact relationships

**Decision**: A proposed L2 artifact may synthesize multiple normalized sources, and any normalized source may contribute to multiple artifacts.

**Rationale**:
- Clinical criteria, workflow logic, and evidence summaries routinely span multiple sources.
- A many-to-many model better matches the actual reasoning process and improves reuse of ingested evidence.

**Alternatives considered**:
- One source per artifact — rejected because it fragments reasoning and produces redundant artifacts.
- One artifact per source — rejected because it makes downstream formalization harder and less clinically meaningful.

---

## Decision 4: Claim-level traceability is required in both plan and artifact design

**Decision**: Every extracted claim, rule, criterion, or interpretation should be traceable back to one or more specific source references.

**Rationale**:
- Extract is the first durable reasoning layer; traceability is essential before formalization.
- Reviewer approval is stronger when the plan states how claims will be evidenced, not just which files were consulted.

**Alternatives considered**:
- Source-level traceability only — rejected because it is too coarse for contested rules and multi-source synthesis.
- No explicit traceability requirement until formalize — rejected because evidence quality would already be lost at L2.

---

## Decision 5: Conflicts must be preserved explicitly, not normalized away

**Decision**: Material source disagreements should be carried into both the plan and the derived artifact schema as explicit conflict records.

**Rationale**:
- Conflicting guidance is common in clinical evidence and should be reviewer-visible.
- Silent collapse of disagreement would overstate certainty and make later review harder.

**Recommended representation**:
- conflicting positions
- preferred interpretation (optional)
- rationale for preference
- unresolved reviewer follow-up

**Alternatives considered**:
- Pick a single best interpretation silently — rejected because it hides disagreement.
- Block extraction entirely on any conflict — rejected because many artifacts are still valuable with explicit caveats.

---

## Decision 6: Reuse `promote derive`, but extend its contract instead of adding a separate writer

**Decision**: Keep deterministic L2 writes in `rh-skills promote derive`, extending its input/output contract for 005 instead of creating a new parallel write path.

**Rationale**:
- The framework principle is that deterministic writes happen in CLI primitives, not in the agent.
- The existing promote command already owns L2 file creation and tracking events.
- Extending one primitive is safer than splitting L2 persistence across multiple commands.

**Expected extensions**:
- richer prompt/schema for L2 artifacts
- multiple `--source` inputs already supported, but schema and tracking need richer semantics
- traceability/conflict fields in output

**Alternatives considered**:
- Create a new `extract derive` write command — rejected because it duplicates promote behavior and increases maintenance cost.

---

## Decision 7: Validation must go beyond required fields

**Decision**: 005 verification should combine existing `rh-skills validate` checks with extract-specific assertions for traceability and conflict handling.

**Rationale**:
- Current L2 validation is likely schema-centric; 005 needs semantic checks tied to the review packet requirements.
- Reviewers need actionable field-level errors if traceability or conflict sections are missing.

**Validate should check**:
- required top-level metadata fields
- derived-from source set present
- evidence/claim references present where required
- conflict sections present when the plan declared unresolved conflicts
- artifact file names and tracking metadata align with approved plan entries

**Alternatives considered**:
- Keep verify as a thin wrapper over existing validation only — rejected because it would miss 005-specific guarantees.
