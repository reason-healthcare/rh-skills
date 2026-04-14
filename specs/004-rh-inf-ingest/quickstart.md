# Quickstart: `rh-inf-ingest`

**A minimal worked example of the ingest pipeline.**

---

## Prerequisites

```bash
# Install local dependencies
uv sync

# Initialize a topic and complete discovery
rh-skills init diabetes-ccm
# ...produce topics/diabetes-ccm/process/plans/discovery-plan.yaml first
```

Optional local tools:

```bash
brew install poppler    # for pdftotext
brew install pandoc     # for docx/xlsx/html conversion help
```

---

## Step 1: Review ingest readiness

```bash
# run from the agent / skill
rh-inf-ingest plan diabetes-ccm
```

Expected summary:
- open-access sources ready for download
- authenticated/manual sources that must be placed manually
- files already present in `sources/`
- tool availability (`pdftotext`, `pandoc`)

This step is read-only.

---

## Step 2: Download/register an open-access source

```bash
rh-skills ingest implement \
  --url https://example.org/guideline.pdf \
  --name ada-2024-guideline \
  --type guideline \
  --topic diabetes-ccm
```

Expected output:

```text
✓ Downloaded: sources/ada-2024-guideline.pdf
  SHA-256: ...
  MIME: application/pdf
  Size: 1.2 MB
```

For authenticated sources, the user places the file manually in `sources/` and ingest proceeds from there.

---

## Step 3: Normalize

```bash
rh-skills ingest normalize sources/ada-2024-guideline.pdf --topic diabetes-ccm
```

Expected output:

```text
✓ Normalized: sources/normalized/ada-2024-guideline.md
```

If `pdftotext` or `pandoc` is unavailable for the file type, normalization still writes the normalized file with `text_extracted: false`.

---

## Step 4: Classify

For a source already curated in discovery, the skill copies the known classification into tracking. For a manual example:

```bash
rh-skills ingest classify ada-2024-guideline \
  --topic diabetes-ccm \
  --type guideline \
  --evidence-level ia \
  --tags diabetes,ccm
```

---

## Step 5: Annotate concepts

```bash
rh-skills ingest annotate ada-2024-guideline \
  --topic diabetes-ccm \
  --concept "HbA1c:measure" \
  --concept "SNOMED CT:terminology" \
  --concept "CMS122:measure"
```

Outputs:
- `sources/normalized/ada-2024-guideline.md` updated with `concepts[]` in frontmatter
- `topics/diabetes-ccm/process/concepts.yaml` created or updated

---

## Step 6: Verify readiness

```bash
rh-skills ingest verify diabetes-ccm
```

Expected output:

```text
Ingest readiness for 'diabetes-ccm'
ada-2024-guideline: file=OK checksum=OK normalized=YES classified=YES annotated=YES
cms122-quality-measure: file=OK checksum=OK normalized=YES classified=YES annotated=YES
journal-article: file=MISSING checksum=MISSING normalized=NO classified=NO annotated=NO
```

This topic-aware verify path reports normalized/classified/annotated readiness and `concepts.yaml` validity without mutating tracking state.

---

## Resulting artifacts

```text
sources/
├── ada-2024-guideline.pdf
└── normalized/
    └── ada-2024-guideline.md

topics/diabetes-ccm/process/
└── concepts.yaml

tracking.yaml
```

These outputs become the source corpus and vocabulary that `rh-inf-extract` uses to propose L2 structured artifacts.
