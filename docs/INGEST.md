# Ingest Workflow Report

## Overview

The **rh-inf-ingest** skill is the **L1 source preparation** stage of the evidence processing pipeline. It orchestrates a workflow that registers local sources, normalizes clinical source documents (PDFs, HTML, Word, etc.) to Markdown with structured metadata, **infers and initializes topics**, classifies sources according to evidence hierarchy, and extracts key clinical concepts for downstream artifact generation. Source downloads are handled by `rh-inf-discovery` before ingest begins.

**Core Purpose:** Transform raw clinical sources into normalized, classified, and concept-annotated Markdown documents that feed into extraction (L2) and formalization (L3) stages.

---

## CLI Commands

| Command | Purpose | Writes To |
|---------|---------|-----------|
| `rh-skills ingest plan [<topic>]` | Print the canonical read-only pre-flight summary | (stdout only) |
| `rh-skills ingest list-manual [<topic>]` | List untracked files in `sources/` with registration commands | (stdout only) |
| `rh-skills ingest implement <file>` | Register a local file into tracking.yaml | `sources/<file>`, `tracking.yaml` |
| `rh-skills ingest normalize <file> --topic <topic> [--name <name>]` | Extract text from binary formats; write normalized Markdown | `sources/normalized/<name>.md`, `tracking.yaml` |
| `rh-skills ingest classify <name> --topic <topic> --type <type> --evidence-level <level>` | Assign classification metadata | `tracking.yaml` |
| `rh-skills ingest annotate <name> --topic <topic> --concept "name:type" [...]` | Extract clinical concepts from normalized source | `normalized/<name>.md`, `concepts.yaml`, `tracking.yaml` |
| `rh-skills ingest verify [<topic>]` | Audit topic ingest readiness (checksums, completeness) | (read-only) |

---

## Registration

Registration is explicit and per-file.

- Use `rh-skills ingest list-manual [<topic>]` to identify untracked files in `sources/`.
- `rh-skills ingest plan [<topic>]` is the primary pre-flight entrypoint; it wraps the same untracked-file discovery and surfaces the registration commands you will run next.
- Register each untracked file with `rh-skills ingest implement sources/<file> [--topic <topic>]`.
- `rh-skills ingest implement` infers an initial registration type from the file extension; it does not accept `--type`.
- There is no bulk registration path via `ingest implement --all`.
- If no files are untracked, registration is a no-op and ingest proceeds to normalize.
- If a source already has a registration-time type hint (for example from discovery download),
  `rh-skills ingest classify` remains the authoritative stage for final type and evidence metadata.

This keeps registration deterministic and visible in agent execution logs.

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

**Soft-fail behavior:** If `pdftotext` or `pandoc` is missing, normalize succeeds but sets `text_extracted: false` in frontmatter.

**Download ownership:** URL acquisition happens before ingest via
`rh-skills source download --url` in discovery.

---

## Workflow

```
1. PLAN: rh-skills ingest plan [<topic>]
   ├─ Inspect untracked local files and print per-file registration commands
   ├─ Check tool availability (pdftotext, pandoc)
   └─ Print pre-flight summary → await user confirmation

2. REGISTER: rh-skills ingest implement sources/<file> [--topic <topic>]
   ├─ Register each untracked file reported by list-manual
   ├─ Update tracking.yaml with file path, checksum, and ingest timestamp
   └─ If no files are untracked, continue directly to normalize

3. NORMALIZE: rh-skills ingest normalize <file> [--topic <topic>]
   ├─ For each source file (sequential):
   │   ├─ Detect extension → select extraction tool
   │   ├─ Extract text (pdftotext | pandoc | markdownify | direct)
   │   ├─ Extract HTML metadata (if HTML source)
   │   ├─ Build YAML frontmatter
   │   ├─ Write sources/normalized/<name>.md
   │   └─ Update tracking.yaml
   └─ Topic is optional at this stage — inference happens next

4. TOPIC INFERENCE: (when no topic has been established yet)
   ├─ Read normalized source frontmatter + first ~200 lines each
   ├─ Agent proposes kebab-case topic name(s) with rationale
   ├─ Await user confirmation
   └─ rh-skills init <topic>   (for each confirmed topic)

5. CLASSIFY: rh-skills ingest classify <name> --topic <topic> --type <type> --evidence-level <level>
   ├─ Agent proposes classification for each source
   ├─ If discovery-plan.yaml present: use its type + evidence_level as starting proposal
   ├─ Await user confirmation
   └─ Update tracking.yaml: type, evidence_level, domain_tags, classified_at
       Event: source_classified

6. ANNOTATE: rh-skills ingest annotate <name> --topic <topic> --concept "name:type"
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

7. VERIFY: rh-skills ingest verify <topic>
   ├─ Re-checksum all sources in tracking.yaml
   ├─ Check normalized.md files exist
   ├─ Check classification events recorded
   ├─ Check annotation events recorded
   ├─ Validate concepts.yaml schema
   ├─ Print per-source readiness table
   └─ Exit 0 (pass) or 1 (fail)

8. HANDOFF → rh-inf-extract
```

---

## Key Files

| File | Role |
|------|------|
| `src/rh_skills/commands/ingest.py` | CLI implementation for all ingest subcommands |
| `skills/.curated/rh-inf-ingest/SKILL.md` | Skill definition; agent instructions for 5-stage workflow (includes topic inference) |
| `skills/.curated/rh-inf-ingest/reference.md` | Normalization rules, classification taxonomy, annotation guidelines |
| `sources/<name>.<ext>` | Raw source files (PDF, HTML, DOCX, etc.) |
| `sources/normalized/<name>.md` | Normalized Markdown with YAML frontmatter |
| `topics/<topic>/process/concepts.yaml` | De-duplicated concept registry (name, type, sources[]) |
| `./discovery-plan.yaml` | Input: source list from discovery at repo root (read-only) |
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
