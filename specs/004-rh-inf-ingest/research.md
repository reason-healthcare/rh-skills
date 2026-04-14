# Research: `rh-inf-ingest` Skill — Phase 0

**Branch**: `004-rh-inf-ingest` | **Date**: 2026-04-13

---

## Decision 1: Keep `plan` mode as a transient pre-flight summary

**Decision**: `rh-inf-ingest plan <topic>` should remain a transient, read-only pre-flight summary rather than creating a durable `topics/<topic>/process/plans/ingest-plan.md` artifact.

**Rationale**:
- `rh-inf-discovery` already produces `topics/<topic>/process/plans/discovery-plan.yaml`, which is the approved machine-readable source inventory and access queue.
- A second durable ingest plan would duplicate source lists, access notes, and readiness state, creating drift and review confusion.
- The value of ingest planning is operational: what will be downloaded, what must be placed manually, and which tools are available.

**Alternatives considered**:
- Create a durable `ingest-plan.md` per topic — rejected because it duplicates `discovery-plan.yaml`.
- Create a repo-level `plans/ingest-plan.md` — rejected because topic-level `discovery-plan.yaml` already captures the actual work queue.

---

## Decision 2: Four-stage pipeline boundaries should stay strict

**Decision**: Keep ingest separated into four deterministic stages with non-overlapping responsibilities:
1. **Download/Register** — source file placement, provenance, checksum, and tracking
2. **Normalize** — source file to normalized Markdown plus extraction metadata
3. **Classify** — `type`, `evidence_level`, and `domain_tags` in `tracking.yaml`
4. **Annotate** — source-local concept metadata in normalized frontmatter plus topic-level `concepts.yaml`

**Rationale**:
- The current code and tests already separate tracking-only writes from markdown and concepts writes cleanly.
- Narrow stage boundaries make re-runs and debugging simpler.
- Downstream extract needs stable normalized text and a de-duped concept vocabulary, not blended stage behavior.

**Alternatives considered**:
- Merge classify and annotate into a single semantic-enrichment step — rejected because classification and concept extraction have different user confirmation and failure semantics.
- Fold normalize into implement/register — rejected because normalization depends on external tools and should remain independently retryable.

---

## Decision 3: Normalized output should be frontmatter-first Markdown

**Decision**: `rh-skills ingest normalize` should write `sources/normalized/<name>.md` with YAML frontmatter followed by Markdown body text.

**Rationale**:
- Frontmatter keeps source-local provenance and extraction metadata adjacent to the normalized content.
- The current tests already validate this shape.
- Downstream extract can parse frontmatter deterministically while still reading the body as plain Markdown.

**Recommended frontmatter fields**:
- `source`
- `topic`
- `normalized`
- `original`
- `text_extracted`
- optional `html_meta`
- optional future semantic fields such as `classification` and `concepts`

**Alternatives considered**:
- Store metadata only in `tracking.yaml` — rejected because extract would need two reads for every source.
- Store metadata in a separate sidecar YAML file — rejected because it complicates per-source portability.

---

## Decision 4: Classification precedence comes from discovery when available

**Decision**: If a source appears in `discovery-plan.yaml`, ingest should treat discovery classification as authoritative and copy it into `tracking.yaml`. Only manually placed or ad hoc sources should require user-confirmed classification.

**Rationale**:
- Discovery is already the evidence-curation stage and should not be second-guessed by ingest.
- This minimizes repetitive human work.
- The manual-source path remains available when users skip discovery or add sources later.

**Alternatives considered**:
- Always re-prompt for classification — rejected because it duplicates discovery decisions.
- Never prompt and always infer automatically — rejected because manual sources need user oversight.

---

## Decision 5: `concepts.yaml` should be a de-duped topic vocabulary

**Decision**: `topics/<topic>/process/concepts.yaml` should store a topic-level, de-duped concept list keyed by canonical concept name with source backlinks.

**Rationale**:
- Extract needs a topic-wide vocabulary for identifying candidate L2 artifacts and shared clinical terms across sources.
- The current annotate tests already validate de-duplication by canonical name and multi-source backlinks.

**Recommended schema**:
- `topic`
- `generated`
- `concepts[]`
  - `name`
  - `type`
  - `sources[]`

**Alternatives considered**:
- Keep concepts only inside each normalized file — rejected because extract would need to rebuild the topic vocabulary every run.
- Use one concepts file per source — rejected because it makes topic-wide joins harder.

---

## Decision 6: Verify should guarantee ingest readiness, not just checksum integrity

**Decision**: Skill-level `rh-inf-ingest verify` should be broader than the current CLI checksum check and should report ingest readiness across the full pipeline.

**Rationale**:
- Downstream extract cares about more than raw file drift; it needs normalized text, classification, and annotation state.
- The current CLI `rh-skills ingest verify` is useful but narrow; the skill can combine it with additional read-only checks.

**Verify should check**:
- raw source file present
- checksum unchanged or explicitly flagged `CHANGED`
- normalized file exists and is parseable
- classification present where expected
- annotation present where expected
- `concepts.yaml` valid and de-duped
- `text_extracted: false` as a warning, not an automatic failure

**Alternatives considered**:
- Keep verify checksum-only — rejected because it does not tell the user whether extract can proceed.

---

## Decision 7: JavaScript-rendered HTML should remain a future optional path

**Decision**: Keep static HTML normalization as the default and document optional Playwright-backed `--js-render` support as future work.

**Rationale**:
- Most guideline and government pages are static enough for `markdownify`.
- Browser automation adds a heavy optional dependency and should not block the normal path.
- The current code already documents the future hook in comments.

**Alternatives considered**:
- Require Playwright for all HTML normalization — rejected because it would burden all users.
- Ignore dynamic HTML entirely — rejected because some payer and registry portals may require it later.
