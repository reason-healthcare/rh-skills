# Ingest Workflow Report

## Overview

The **rh-inf-ingest** skill is the **L1 source acquisition and preparation** stage of the evidence processing pipeline. It orchestrates a four-stage workflow to acquire clinical source documents (PDFs, HTML, Word, etc.), normalize them to Markdown with structured metadata, classify them according to evidence hierarchy, and extract key clinical concepts for downstream artifact generation.

**Core Purpose:** Transform raw clinical sources into normalized, classified, and concept-annotated Markdown documents that feed into extraction (L2) and formalization (L3) stages.

---

## CLI Commands

| Command | Purpose | Writes To |
|---------|---------|-----------|
| `rh-skills ingest plan [<topic>]` | Print pre-flight summary or create ingest-plan.md template | `plans/ingest-plan.md` |
| `rh-skills ingest list-manual [<topic>]` | List untracked files in `sources/` with registration commands | (stdout only) |
| `rh-skills ingest implement <file>` | Register a local file into tracking.yaml | `sources/<file>`, `tracking.yaml` |
| `rh-skills ingest implement --url <url> --name <name> [--topic <topic>]` | Download source from URL, auto-detect MIME, register | `sources/<name>.<ext>`, `tracking.yaml` |
| `rh-skills ingest normalize <file> --topic <topic> [--name <name>]` | Extract text from binary formats; write normalized Markdown | `sources/normalized/<name>.md`, `tracking.yaml` |
| `rh-skills ingest classify <name> --topic <topic> --type <type> --evidence-level <level>` | Assign classification metadata | `tracking.yaml` |
| `rh-skills ingest annotate <name> --topic <topic> --concept "name:type" [...]` | Extract clinical concepts from normalized source | `normalized/<name>.md`, `concepts.yaml`, `tracking.yaml` |
| `rh-skills ingest verify [<topic>]` | Audit topic ingest readiness (checksums, completeness) | (read-only) |

---

## Input Types Supported

| Format | Extension | Extraction Tool | Notes |
|--------|-----------|-----------------|-------|
| PDF | `.pdf` | `pdftotext` (poppler) | Soft-fail if missing |
| Word | `.docx`, `.doc` | `pandoc` | Soft-fail if missing |
| Excel | `.xlsx` | `pandoc` | Soft-fail if missing |
| HTML | `.html`, `.htm` | `markdownify` (Python) | + HTML meta extraction |
| Plain Text | `.txt` | direct read | — |
| Markdown | `.md` | direct read | — |
| XML | `.xml` | direct read | — |
| URL | HTTP/HTTPS | Content-Type dependent | MIME auto-detection; auth-redirect detection (exit 3) |

**Soft-fail behavior:** If `pdftotext` or `pandoc` is missing, normalize succeeds but sets `text_extracted: false` in frontmatter.

---

## Workflow

```
1. PLAN: rh-skills ingest plan <topic>
   ├─ Read discovery-plan.yaml (if exists)
   ├─ Check tool availability (pdftotext, pandoc)
   ├─ Categorize sources: open | authenticated | manual
   └─ Print pre-flight summary → await user confirmation

2. DOWNLOAD: rh-skills ingest implement --url <url> --name <name>
   ├─ For each "open" source (parallel):
   │   ├─ HTTP GET with auth-redirect detection (exit 3 on login URLs)
   │   ├─ MIME-type detection
   │   ├─ SHA-256 checksum
   │   ├─ Write sources/<name>.<ext>
   │   └─ Register in tracking.yaml
   └─ For authenticated/manual: skip (user places manually)

3. NORMALIZE: rh-skills ingest normalize <file> --topic <topic>
   ├─ For each source file (sequential):
   │   ├─ Detect extension → select extraction tool
   │   ├─ Extract text (pdftotext | pandoc | markdownify | direct)
   │   ├─ Extract HTML metadata (if HTML source)
   │   ├─ Build YAML frontmatter
   │   ├─ Write sources/normalized/<name>.md
   │   └─ Update tracking.yaml
   └─ Output format:
       ┌────────────────────────────────┐
       │ ---                            │
       │ source: <name>                 │
       │ topic: <topic>                 │
       │ normalized: <ISO-8601>         │
       │ original: sources/<file>       │
       │ text_extracted: true|false     │
       │ html_meta: (if HTML)           │
       │   title: ...                   │
       │   dc_creator: ...              │
       │ ---                            │
       │ <extracted markdown content>   │
       └────────────────────────────────┘

4. CLASSIFY: rh-skills ingest classify <name> --topic <topic> --type <type> --evidence-level <level>
   ├─ For discovery-backed sources:
   │   └─ Read type + evidence_level from plan
   ├─ For manual sources:
   │   ├─ Agent proposes classification
   │   └─ Await user confirmation
   └─ Update tracking.yaml: type, evidence_level, domain_tags, classified_at
       Event: source_classified

5. ANNOTATE: rh-skills ingest annotate <name> --topic <topic> --concept "name:type"
   ├─ For each source (STRICTLY SERIAL — no parallelism):
   │   ├─ Read normalized.md content
   │   ├─ Identify concepts:
   │   │   ├─ Conditions (e.g., "Hypertension")
   │   │   ├─ Medications (e.g., "ACE Inhibitor")
   │   │   ├─ Procedures, Lab tests, Measures
   │   │   ├─ Terminology codes (ICD-10, SNOMED, LOINC, RxNorm)
   │   │   ├─ Guideline references, SDOH factors
   │   │   └─ Quality measures
   │   ├─ Update normalized/<name>.md frontmatter: add concepts[]
   │   ├─ Update topics/<topic>/process/concepts.yaml (de-duped registry)
   │   └─ Update tracking.yaml: annotated_at, concept_count
   └─ Event: source_annotated

6. VERIFY: rh-skills ingest verify <topic>
   ├─ Re-checksum all sources in tracking.yaml
   ├─ Check normalized.md files exist
   ├─ Check classification events recorded
   ├─ Check annotation events recorded
   ├─ Validate concepts.yaml schema
   ├─ Print per-source readiness table
   └─ Exit 0 (pass) or 1 (fail)

7. HANDOFF → rh-inf-extract
```

---

## Key Files

| File | Role |
|------|------|
| `src/rh_skills/commands/ingest.py` | CLI implementation for all ingest subcommands |
| `skills/.curated/rh-inf-ingest/SKILL.md` | Skill definition; agent instructions for 4-stage workflow |
| `skills/.curated/rh-inf-ingest/reference.md` | Normalization rules, classification taxonomy, annotation guidelines |
| `sources/<name>.<ext>` | Raw source files (PDF, HTML, DOCX, etc.) |
| `sources/normalized/<name>.md` | Normalized Markdown with YAML frontmatter |
| `topics/<topic>/process/concepts.yaml` | De-duplicated concept registry (name, type, sources[]) |
| `topics/<topic>/process/plans/discovery-plan.yaml` | Input: source list from discovery (read-only) |
| `tracking.yaml` | Source registry with checksums, events, classification metadata |

---

## Concepts Registry Schema

```yaml
topic: <topic>
generated: <ISO-8601>
concepts:
  - name: "Hypertension"
    type: "condition"
    sources:
      - acc-aha-2017
      - jnc8-guidelines
  - name: "ACE Inhibitor"
    type: "medication"
    sources:
      - jnc8-guidelines
```

---

## Design Details

### Auth-Redirect Detection
When downloading from a URL, if the response redirects to a login/signin/auth/idp page, the command exits with code 3 (non-zero, distinct from other failures). The agent reports the URL requires authentication and advises manual download.

### HTML Metadata Extraction
For HTML sources, the normalizer extracts metadata from: `<meta>` tags, Dublin Core, OpenGraph (`og:`), Twitter Card, and JSON-LD schema.org blocks.

### Serial Annotation Constraint
The `annotate` command must be run **serially** (one source at a time) because it reads and writes `concepts.yaml` — concurrent writes would cause data loss or corruption.
