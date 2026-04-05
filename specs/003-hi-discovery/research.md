# Research: `hi-discovery` Skill — Phase 0

**Branch**: `003-hi-discovery` | **Date**: 2026-04-04

---

## Decision 1: HTTP client for PubMed + ClinicalTrials.gov

**Decision**: `httpx` (sync mode) as the HTTP client for all `hi search` API calls and URL downloads in `hi ingest implement --url`.

**Rationale**:
- `httpx` is already a common dependency in modern Python CLIs; supports both sync and async
- Better timeout + redirect handling than `urllib` for real-world PDF downloads
- `requests` is equally viable but `httpx` is more actively maintained and type-annotated
- Sync mode sufficient — `hi search` is called once per query; no need for async

**Alternatives considered**:
- `requests` — simpler, widely known; rejected only because `httpx` is a strict superset with better defaults
- `aiohttp` — async only; adds complexity not needed for CLI usage
- `urllib.request` — stdlib, no extra dep; rejected because redirect handling and timeout ergonomics are inferior

---

## Decision 2: PubMed Entrez API strategy

**Decision**: Use NCBI E-utilities (Entrez API) — specifically `esearch` → `efetch` two-step pattern in XML, parsed with Python stdlib `xml.etree.ElementTree`.

**Rationale**:
- `esearch` returns PMIDs matching the query; `efetch` retrieves full metadata (title, authors, journal, year, abstract, DOI, PMC ID) in PubMed XML format
- No auth required; `NCBI_API_KEY` env var passed as `&api_key=` query param when present
- Rate limit: 3 req/s without key, 10 req/s with key — well within single-user CLI usage
- `xml.etree.ElementTree` is stdlib; no extra dependency
- PubMed XML format is stable and well-documented

**Endpoints**:
```
esearch: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
         ?db=pubmed&term=<query>&retmax=<N>&retmode=json
efetch:  https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
         ?db=pubmed&id=<pmid,pmid,...>&rettype=xml&retmode=xml
```

**Open-access flag**: If `PmcID` element is present in efetch response, article is available in PMC (open access). Set `open_access: true` in output.

**Alternatives considered**:
- `Biopython Entrez` — higher-level wrapper; rejected to avoid a large dependency for a small use case
- Direct JSON mode for efetch — PubMed XML has richer metadata than JSON; XML preferred

---

## Decision 3: ClinicalTrials.gov API v2

**Decision**: Use ClinicalTrials.gov REST API v2 (`/studies` endpoint) with JSON response.

**Rationale**:
- Free, no auth required
- v2 launched 2023; v1 deprecated; v2 has cleaner REST semantics and structured JSON
- Supports filtering by `query.cond` (condition), `query.intr` (intervention), `filter.overallStatus`, and pagination via `pageToken`

**Endpoint**:
```
GET https://clinicaltrials.gov/api/v2/studies
    ?query.cond=<condition>&filter.overallStatus=COMPLETED,RECRUITING
    &pageSize=<N>&format=json
```

**Fields to extract**: `nctId`, `briefTitle`, `overallStatus`, `phases`, `conditions`, `interventions`, `startDate`, `completionDate`, `briefSummary`

---

## Decision 4: PMC search strategy

**Decision**: Use PubMed's `esearch` with `pmc[sb]` (PubMed Central subset filter) rather than a separate PMC API.

**Rationale**:
- `hi search pmc` can reuse the same `esearch` + `efetch` infrastructure as `hi search pubmed`
- Adding `AND "open access"[Filter]` or searching `pmc[sb]` database targets full-text PMC articles
- Avoids maintaining a separate client for the PMC E-utilities which have different XML schemas

**Query pattern**: `esearch?db=pmc&term=<query>&retmax=<N>` → `efetch?db=pmc&id=<pmcid,...>&rettype=xml`

---

## Decision 5: URL download for `hi ingest implement --url`

**Decision**: Download URL to a temp file, detect MIME type from `Content-Type` header and/or file extension, then move to `sources/<name>.<ext>`. Compute SHA-256, register in `tracking.yaml`.

**Rationale**:
- Consistent with how local file ingest works (same checksum + registration path)
- MIME type detection: prefer `Content-Type` header; fall back to URL extension; fall back to `application/octet-stream` → `.bin`
- Redirect following: `httpx` follows redirects by default (up to 20 hops)
- Auth redirect detection: if response URL differs from request URL and final URL contains `login`, `signin`, `auth` → flag as `access: manual` rather than registering a login page

**Extension map**:
```python
MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
}
```

---

## Decision 6: RESEARCH.md and process/research.md update strategy

**Decision**: Implement as append-only table row operations using `ruamel.yaml` for `discovery-plan.yaml` parsing and direct string manipulation for Markdown table rows.

**Rationale**:
- `RESEARCH.md` is Markdown with no frontmatter — row appends are simple string operations
- `process/notes.md` is human-maintained (Open Questions, Decisions, Source Conflicts, Notes sections) — the CLI creates the stub only via `hi init`; no further writes
- `ruamel.yaml` already used for `tracking.yaml`; table row manipulation is straightforward Python string ops
- Never modifying existing rows preserves the audit trail (FR-030 from 002 spec)

**Update pattern** for `hi init` (creates stubs):
1. Check if `RESEARCH.md` exists at repo root; create if not
2. Append one row to the Active Topics table
3. Create `topics/<name>/process/notes.md` stub (create-unless-exists)

**Update pattern** for session save (FR-014):
1. Move each downloaded source: Pending Review → Ruled In (by name match)
2. Move each failed/manual source: Pending Review → Ruled Out (with reason)
3. Update Active Topics row in `RESEARCH.md`: source count, updated date

---

## Decision 7: SKILL.md session model (not plan/implement/verify)

**Decision**: The SKILL.md uses two modes (`session` and `verify`) rather than the standard three-mode template. The `session` mode is the primary interactive research assistant mode.

**Rationale**: Confirmed in speckit-clarify (2026-04-04). Discovery is pure planning — no downloads occur during the session. `hi-ingest` (004) owns all source acquisition. The `session` mode guides the agent to search, curate, and save `discovery-plan.yaml`; `hi-ingest` reads that file to execute downloads. The SKILL.md template supports custom modes; we adapt accordingly.

**Frontmatter modes**:
```yaml
modes:
  - session
  - verify
```

**Session flow** (agent-side):
1. Call `hi status show <topic>` to confirm topic is initialized
2. Reason about clinical domain; produce initial Domain Advice
3. Call `hi search pubmed --query <terms> --max 20 --json`
4. Call `hi search clinicaltrials --query <terms> --max 20 --json`
5. Call `hi search pmc --query <terms> --max 20 --json` (for open-access articles)
6. Build working `sources[]` list in memory (living document)
7. Present sources to user with access tier, rationale, evidence level
8. For each authenticated source: print access advisory (FR-011a/b)
9. For each `access: manual` source: record `auth_note` describing retrieval steps
10. Present Research Expansion Suggestions (3–7)
11. Prompt user: expand an area? save now? verify?
12. On save: write `discovery-plan.yaml` (pure YAML) and `discovery-readout.md` (narrative), create `notes.md` stub (create-unless-exists), update `RESEARCH.md`, append event

---

## Decision 8: `hi init` extensions for research tracking

**Decision**: Extend `hi init` to create `RESEARCH.md` at repo root and `topics/<name>/process/notes.md` (canonical stub format).

**`RESEARCH.md` format** (append row to Active Topics table):
```markdown
| <topic> | initialized | 0 | <date> | <date> | |
```

**`process/notes.md` format** (created fresh per topic, create-unless-exists):
```markdown
# Research Notes — <topic>

## Open Questions
<!-- checkbox bullets -->
- [ ] 

## Decisions
<!-- key choices and why -->
- 

## Source Conflicts
<!-- contradictions between sources -->

## Notes
<!-- free-form -->
```
