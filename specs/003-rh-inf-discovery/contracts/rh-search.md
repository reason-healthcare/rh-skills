# CLI Contract: `rh-skills search`

**Phase 1 Design Artifact** | **Branch**: `003-rh-inf-discovery`

New command group added to the `rh-skills` CLI.

---

## Command: `rh-skills search pubmed`

```
rh-skills search pubmed [OPTIONS]
```

Search PubMed via NCBI E-utilities (esearch → efetch).

**Options**:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query TEXT` | string | required | PubMed search query (supports MeSH, boolean, filters) |
| `--max INTEGER` | int | 20 | Maximum results to return |
| `--json` | flag | false | Output structured JSON to stdout |
| `--filter TEXT` | string | none | PubMed filter string (e.g., `"systematic review[pt]"`) |
| `--api-key TEXT` | string | env:NCBI_API_KEY | NCBI API key for higher rate limit (10 req/s) |

**Exit codes**:
- `0` — Success; results printed to stdout
- `1` — Network error or NCBI API error
- `2` — Zero results returned (warning printed; not an error)

**Stdout (default, human-readable)**:
```
[1] Chronic Care Management in Diabetes: A Systematic Review (2023)
    ID: 12345678 | Journal of Clinical Informatics | open-access: yes
    Authors: Smith J, Patel R
    DOI: 10.1000/j.jci.2023.001
    https://pubmed.ncbi.nlm.nih.gov/12345678
    Abstract: Chronic care management interventions for type 2 diabetes...

[2] ...
```

**Stdout (`--json`)**:
```json
{
  "query": "diabetes chronic care management systematic review",
  "source": "pubmed",
  "retrieved_at": "2026-04-04T12:00:00Z",
  "total_found": 847,
  "returned": 20,
  "results": [...]
}
```

**Rate limiting**: Adds `time.sleep(0.34)` between esearch and efetch calls (≤3 req/s). If `NCBI_API_KEY` env var is set, reduces sleep to 0.11s.

---

## Command: `rh-skills search pmc`

```
rh-skills search pmc [OPTIONS]
```

Search PubMed Central for open-access full-text articles. Uses `db=pmc` in E-utilities.

**Options**: Same as `rh-skills search pubmed` (uses same API, different `db` parameter).

**Key difference from pubmed**: All PMC results are open-access (full text available). `open_access: true` set on all results by default.

**Exit codes**: Same as `rh-skills search pubmed`.

---

## Command: `rh-skills search clinicaltrials`

```
rh-skills search clinicaltrials [OPTIONS]
```

Search ClinicalTrials.gov via REST API v2.

**Options**:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query TEXT` | string | required | Condition or intervention search term |
| `--max INTEGER` | int | 20 | Maximum results to return |
| `--json` | flag | false | Output structured JSON to stdout |
| `--status TEXT` | string | `COMPLETED,RECRUITING` | Filter by trial status |

**Endpoint**: `GET https://clinicaltrials.gov/api/v2/studies?query.cond=<query>&filter.overallStatus=<status>&pageSize=<max>&format=json`

**Exit codes**: Same as `rh-skills search pubmed`.

**Stdout (`--json`)**:
```json
{
  "query": "diabetes chronic care management",
  "source": "clinicaltrials",
  "retrieved_at": "2026-04-04T12:00:00Z",
  "total_found": 142,
  "returned": 20,
  "results": [
    {
      "id": "NCT04512345",
      "pmid": null,
      "nct_id": "NCT04512345",
      "title": "...",
      "url": "https://clinicaltrials.gov/study/NCT04512345",
      "year": "2021",
      "journal": null,
      "authors": [],
      "doi": null,
      "open_access": true,
      "pmcid": null,
      "abstract_snippet": "This randomized controlled trial...",
      "status": "COMPLETED",
      "phase": "PHASE3",
      "conditions": ["Type 2 Diabetes Mellitus"],
      "interventions": ["Chronic Care Management Program"]
    }
  ]
}
```

---

## Command: `rh-skills source download --url` (extension)

```
rh-skills source download --url URL --name NAME [OPTIONS]
```

Download a URL to `sources/`, compute SHA-256, register in `tracking.yaml`. Extends existing `rh-skills ingest implement FILE` command.

**Options** (new flags only):

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--url TEXT` | string | — | URL to download (mutually exclusive with FILE positional arg) |
| `--name TEXT` | string | required with --url | Stem name for the saved file (kebab-case) |
| `--type TEXT` | string | `document` | Source type (see Source Type Taxonomy) |

**Behavior**:
1. GET `<url>` (follow redirects up to 20 hops)
2. If final URL contains `login`, `signin`, `auth`, `access-denied` → print advisory; exit 3
3. Detect MIME type from `Content-Type` header; map to file extension
4. Write to `sources/<name>.<ext>` (error if file already exists)
5. Compute SHA-256 of saved file
6. Append event to `tracking.yaml` (`source_ingested` event)
7. Print: `✓ Downloaded: sources/<name>.<ext> (SHA-256: <hash>)`

**Exit codes**:
- `0` — Success
- `1` — Network error (HTTP error, DNS failure)
- `2` — File already exists
- `3` — Authentication redirect detected; prints advisory for manual retrieval

**Stdout (success)**:
```
✓ Downloaded: sources/ada-2024-standards.pdf
  SHA-256: a1b2c3d4e5f6...
  MIME: application/pdf
  Size: 2.4 MB
```

**Stdout (auth redirect)**:
```
⚠ Authentication required for: https://example.com/article/123
  Final redirect URL: https://example.com/login?return=...
  Action: Retrieve manually and run: rh-skills ingest implement <downloaded-file>
```

---

## Command: `rh-skills init` — research tracking extensions

**Extended behavior** (additions only; existing behavior unchanged):

When `rh-skills init <topic>` is run:
1. Create `RESEARCH.md` at repo root if not present (canonical format from data-model.md Entity 4)
2. Append one row to the Active Topics table: `| <topic> | initialized | 0 | <date> | <date> | |`
3. Create `topics/<name>/process/notes.md` stub (create-unless-exists) with the canonical format (Entity 5)
4. Print: `✓ Research tracking initialized for topic: <topic>`

**Exit codes**: Inherits from existing `rh-skills init`; no new exit codes.
