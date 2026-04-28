# Data Model: `rh-inf-ingest` Skill

**Phase 1 Design Artifact** | **Branch**: `004-rh-inf-ingest`

---

## Entity 1: Tracked Source Record (`tracking.yaml` → `sources[]`)

```yaml
sources:
  - name: "ada-2024-guideline"          # kebab-case identifier
    file: "sources/ada-2024-guideline.pdf"
    type: "guideline"
    url: "https://example.org/guideline.pdf"      # optional, when downloaded
    checksum: "sha256-hex"
    ingested_at: "ISO-8601"
    downloaded: true
    normalized: "sources/normalized/ada-2024-guideline.md"   # optional
    text_extracted: true
    evidence_level: "ia"               # optional until classified
    domain_tags: ["diabetes", "screening"]
    classified_at: "ISO-8601"          # optional
    annotated_at: "ISO-8601"           # optional
    concept_count: 12                  # optional
```

**Validation / behavior rules**:
- `name`, `file`, `checksum`, and `ingested_at` are required once a source is registered.
- `downloaded: true` indicates remote acquisition via `--url`; manually copied files may omit it.
- `normalized` is populated after normalize succeeds or soft-succeeds.
- `text_extracted: false` is valid and indicates a warning condition, not a hard failure.
- `type`, `evidence_level`, and `domain_tags` are required for a source to be considered classified.

---

## Entity 2: `sources/normalized/<name>.md`

Normalized Markdown is the canonical per-source text artifact used by downstream extraction.

```markdown
---
source: ada-2024-guideline
topic: diabetes-ccm
normalized: 2026-04-13T12:00:00Z
original: sources/ada-2024-guideline.pdf
text_extracted: true
html_meta:
  title: "ADA Standards of Care 2024"
  author: "American Diabetes Association"
concepts:
  - name: "HbA1c"
    type: "measure"
---

# ADA Standards of Care

Normalized markdown content...
```

**Rules**:
- Frontmatter is YAML and must parse cleanly.
- `source`, `topic`, `original`, and `text_extracted` are required.
- `html_meta` is optional and present for HTML-derived sources.
- `concepts[]` is optional until annotation runs.

---

## Entity 3: `topics/<topic>/process/concepts.yaml`

Topic-level, de-duped concept vocabulary built from annotated normalized sources.

```yaml
topic: diabetes-ccm
generated: 2026-04-13T12:30:00Z
concepts:
  - name: HbA1c
    type: measure
    sources:
      - ada-2024-guideline
      - cms122-hba1c-poor-control
  - name: SNOMED CT
    type: terminology
    sources:
      - snomed-diabetes-hierarchy
```

**Rules**:
- `topic`, `generated`, and `concepts[]` are required.
- Concepts are de-duped by canonical `name` (case-insensitive comparison).
- `sources[]` records every source name that references the concept.
- This file is append/update-only from ingest annotation; downstream stages read but do not own it.

---

## Entity 4: Pre-flight Summary (`rh-inf-ingest plan <topic>`)

This is a transient summary rendered to stdout, not a durable plan file.

**Sections**:
1. Downloadable open-access sources from `discovery-plan.yaml`
2. Authenticated/manual sources requiring user placement
3. Manually placed files already present in `sources/`
4. Tool availability (`pdftotext`, `pandoc`)
5. Re-run/idempotency notes

**Purpose**:
- operational readiness check before `implement`
- no file writes

---

## Entity 5: Ingest Verification Report

Read-only, rendered to stdout by skill-level verify.

Per source:
- raw file present ✓/✗
- checksum OK / CHANGED / MISSING
- normalized markdown present ✓/✗
- classified ✓/✗
- annotated ✓/✗
- `text_extracted: false` warning where applicable

Topic-wide:
- `concepts.yaml` schema valid ✓/✗
- duplicate concept collisions surfaced

---

## State Transitions

```text
registered
  ├── normalize → normalized
  │       └── text_extracted: false → normalized-with-warning
  ├── classify → classified
  ├── annotate → annotated
  └── verify → status report only (read-only)
```

- A source can be normalized before classification.
- Annotation depends on the normalized artifact existing.
- Verify never changes state.

---

## Tracking Events

```yaml
events:
  - type: source_added
    description: "Downloaded source: ada-2024-guideline"
  - type: source_normalized
    description: "Normalized: ada-2024-guideline"
  - type: source_classified
    description: "Classified: ada-2024-guideline"
  - type: source_annotated
    description: "Annotated: ada-2024-guideline (12 concepts)"
```

These events provide the audit trail for ingest progress and downstream readiness.
