# Feature Specification: `hi-discovery` Skill

**Feature Branch**: `003-hi-discovery`
**Created**: 2026-04-04 | **Updated**: 2026-04-04
**Status**: Draft
**Depends On**: [002 — HI Framework CLI](../002-hi-agent-skills/)

## Overview

`hi-discovery` is an active **information-gathering and research guidance tool** for clinical informaticists starting a new topic. It does three things:

1. **Domain advice** — reasons about the clinical domain and tells the user what to consider (diagnostic criteria, population characteristics, existing measures, regulatory context, evidence gaps)
2. **Source identification** — searches PubMed, PubMed Central, ClinicalTrials.gov, and known medical society URL patterns to surface relevant guidelines, systematic reviews, terminology systems, and measure libraries
3. **Source acquisition** — optionally downloads discovered sources into `sources/` and registers them in `tracking.yaml` via `hi ingest implement`

**Guiding principle**: all deterministic work (API calls, downloads, file registration, checksum) via `hi` CLI; all reasoning (domain advice, relevance judgement, evidence prioritisation) by the agent.

The skill has three modes:

| Mode | Agent role | `hi` CLI called | Output |
|------|-----------|----------------|--------|
| `plan` | Advises on domain; searches databases; produces structured source plan | `hi search pubmed`, `hi search clinicaltrials`, `hi search pmc` | `process/plans/discovery-plan.md`, `process/research.md` stub, `process/conflicts.md` stub |
| `implement` | Iterates approved plan; decides which sources to download now vs. defer | `hi ingest implement --url` (per downloadable source) | Sources downloaded to `sources/`; registered in `tracking.yaml`; `process/plans/ingest-plan.md` populated |
| `verify` | Validates plan quality and coverage | (read-only) | Per-check report; no file writes |

---

## User Scenarios & Testing

### User Story 1 — Research a clinical topic from scratch (Priority: P1)

A clinical informaticist starts a new topic "sepsis-early-detection" and has no idea where to begin. They invoke `hi-discovery plan`. The agent:
- Explains what to consider in sepsis informatics (diagnostic criteria like qSOFA/SOFA, organ dysfunction coding, time-sensitive treatment windows, population subtypes, existing SEP-1 measure)
- Searches PubMed for recent systematic reviews and guidelines
- Searches ClinicalTrials.gov for active/completed relevant trials
- Produces a structured discovery plan with specific sources, evidence levels, and search strategies

**Acceptance Scenarios**:

1. **Given** an initialised topic, **When** `hi-discovery plan` runs, **Then** `process/plans/discovery-plan.md` is written with: (a) a prose domain advice section, (b) a `sources[]` YAML list with name, type, rationale, evidence_level, search_terms, and optional url per entry.
2. **Given** plan mode runs, **Then** `hi search pubmed` is called with topic-relevant terms; results are used to populate the `sources[]` list.
3. **Given** plan mode runs, **Then** `process/research.md` and `process/conflicts.md` stubs are created (create-unless-exists).
4. **Given** `discovery-plan.md` already exists without `--force`, **When** plan runs, **Then** the skill warns and stops; no files modified.
5. **Given** `--dry-run`, **When** plan runs, **Then** the proposed plan and domain advice are printed; no files written and no events appended.
6. **Given** plan completes, **Then** a `discovery_planned` event is appended to `tracking.yaml`.

---

### User Story 2 — Download discovered sources (Priority: P1)

After reviewing the plan and approving the source list, the informaticist runs `hi-discovery implement`. The agent iterates the approved sources, downloads those with accessible URLs via `hi ingest implement --url`, and notes which sources require manual acquisition (paywalled journals, society portals requiring login).

**Acceptance Scenarios**:

1. **Given** a valid `discovery-plan.md`, **When** `hi-discovery implement` runs, **Then** for each source entry with a `url`: `hi ingest implement --url <url> --name <name> --topic <topic>` is called; the source is downloaded to `sources/` and registered in `tracking.yaml`.
2. **Given** a source entry with no `url` or `access: manual`, **When** `implement` runs, **Then** the agent notes the source as requiring manual acquisition and adds it to `process/plans/ingest-plan.md` as a pending manual entry — no download is attempted.
3. **Given** a download fails (network error, 404, auth required), **When** `implement` runs, **Then** the failure is logged per-source; the skill continues with remaining sources; exit 1 at the end if any download failed.
4. **Given** no `discovery-plan.md` exists, **When** `implement` runs, **Then** exit non-zero: `discovery-plan.md not found — run hi-discovery plan first`.
5. **Given** `implement` completes, **Then** a `discovery_implemented` event is appended to `tracking.yaml` with counts: downloaded, manual-pending, failed.
6. **Given** the plan contains `access: authenticated` sources, **When** `implement` runs, **Then** the agent prints a formatted access advisory for each — name, relevance to the topic, URL, authentication method, and suggested search terms — before starting any downloads.
7. **Given** Cochrane Library is in the plan as an authenticated source, **When** `implement` prints its advisory, **Then** it specifies: `cochranelibrary.com`, access method ("institutional login or free personal registration"), and topic-specific search terms.
6. **Given** `--dry-run`, **When** `implement` runs, **Then** the agent lists which sources would be downloaded and which would be flagged manual; no downloads, no events.

---

### User Story 3 — Verify discovery coverage (Priority: P2)

Before proceeding to ingest, the informaticist runs `hi-discovery verify` to confirm the plan is well-formed and covers required evidence categories.

**Acceptance Scenarios**:

1. **Given** a complete plan, **When** `verify` runs, **Then** exit 0 with a per-check report: `✓ frontmatter valid`, `✓ terminology source present`, `✓ all entries have rationale and evidence_level`, etc.
2. **Given** a plan with no terminology source, **When** `verify` runs, **Then** exit 1: `✗ No terminology source (SNOMED/LOINC/ICD/RxNorm) — required for L3 computable output`.
3. **Given** a plan entry missing `rationale` or `evidence_level`, **When** `verify` runs, **Then** exit 1 naming the source and missing field.
4. **Given** `verify` runs under any condition, **Then** no files are written and `tracking.yaml` is not modified.

---

### Edge Cases

- PubMed API returns zero results — agent falls back to domain knowledge and known society URL patterns; warns user that search was sparse.
- Source URL returns a redirect to a login page — download fails gracefully; source is flagged as `access: manual`.
- Plan `sources[]` is empty — `implement` exits non-zero before downloading anything.
- Plan YAML frontmatter is malformed — `implement` and `verify` fail at parse time with a line-level error.
- A source file is already present in `sources/` with matching checksum — `hi ingest implement` skips re-download (idempotent).
- Topic name not found in `tracking.yaml` — all modes exit non-zero with: `topic '<name>' not initialised — run hi init first`.
- Network unavailable during `implement` — all URL downloads fail gracefully; manual-acquisition list is produced; exit 1.

---

## Requirements

### Functional Requirements

**`hi` CLI extensions required by this skill**

- **FR-001**: A new `hi search` command group MUST be implemented with the following subcommands:
  - `hi search pubmed --query <terms> [--max N] [--json]` — calls PubMed Entrez esearch + efetch APIs; returns structured list of results (PMID, title, authors, journal, year, abstract, DOI, open-access flag).
  - `hi search pmc --query <terms> [--max N] [--json]` — searches PubMed Central for open-access full-text articles.
  - `hi search clinicaltrials --query <terms> [--max N] [--status <status>] [--json]` — calls ClinicalTrials.gov API v2; returns NCT ID, title, status, phase, conditions, interventions.
- **FR-002**: `hi ingest implement` MUST accept `--url <url>` as an alternative to a local file path. When `--url` is given, the CLI downloads the resource to `sources/<name>.<ext>`, computes its SHA-256, and registers it in `tracking.yaml` identically to a local file ingest.
- **FR-003**: `hi search` subcommands MUST require no API key for PubMed and ClinicalTrials.gov (both are free/public). A `NCBI_API_KEY` environment variable MAY be set to increase PubMed rate limits (10 req/s vs. 3 req/s).

**plan mode**

- **FR-004**: `hi-discovery plan` MUST produce `process/plans/discovery-plan.md`. The file MUST contain: (a) a prose **Domain Advice** section with what to consider for the clinical domain; (b) YAML frontmatter with a `sources[]` list; (c) a **Research Expansion Suggestions** section (see FR-025).
- **FR-005**: Each source entry in `sources[]` MUST have: `name`, `type` (see FR-009), `rationale`, `search_terms[]`, `evidence_level` (see FR-010), `access` (`open | authenticated | manual`). `url` is optional but MUST be present when `access: open`. When `access: authenticated`, the entry MUST include `auth_note` — a plain-English description of how to obtain access (e.g., institutional login, free registration, society membership).
- **FR-005a**: For `access: authenticated` sources, the agent MUST include a `recommended: true` flag when the source is considered authoritative or high-value for the topic domain, regardless of whether it can be downloaded automatically. The discovery plan is the authoritative recommendation — access difficulty does not reduce a source's priority.
- **FR-006**: The agent MUST call `hi search pubmed` and at least one other `hi search` subcommand during `plan`; results inform the `sources[]` list. The agent decides which results are relevant.
- **FR-007**: `plan` MUST populate `process/research.md` Pending Review table with all `sources[]` entries from the discovery plan (name, URL or "TBD", date added). `plan` MUST also create `process/conflicts.md` stub (create-unless-exists). Existing files MUST NOT be modified (only the Pending Review table is appended).
- **FR-008**: If `discovery-plan.md` already exists, `plan` MUST warn and stop unless `--force` is passed. Successful `plan` (non-dry-run) MUST append `discovery_planned` to `tracking.yaml`.

**implement mode**

- **FR-011**: `hi-discovery implement` MUST read `discovery-plan.md` and for each source with `access: open` and a `url`: call `hi ingest implement --url <url> --name <name> --topic <topic>`.
- **FR-011a**: For sources with `access: authenticated`, the agent MUST print a formatted per-source access advisory to stdout — naming the source, explaining why it is recommended for this topic, and providing the specific URL, login mechanism, and what to search for once authenticated. These advisories MUST appear before any download activity so the user can act on them in parallel.
- **FR-011b**: The access advisory format MUST include: source name, why it is relevant, access URL, authentication method (institutional login / free registration / society membership / library proxy), and suggested search terms to use once inside.
- **FR-012**: Sources with `access: manual` or no `url` MUST be added to `process/plans/ingest-plan.md` as pending manual entries. No download is attempted.
- **FR-013**: Download failures (non-2xx HTTP, network error, auth redirect) MUST be caught per-source; the skill continues with remaining sources and reports a summary at completion. Exit 1 if any download failed.
- **FR-014**: `implement` MUST create `process/research.md` stub (create-unless-exists).
- **FR-015**: If `discovery-plan.md` does not exist, `implement` MUST exit non-zero: `discovery-plan.md not found — run hi-discovery plan first`.
- **FR-016**: If `sources[]` is empty, `implement` MUST exit non-zero before attempting any download.
- **FR-017**: Successful `implement` MUST append `discovery_implemented` event to `tracking.yaml` with payload: `{ downloaded: N, manual_pending: M, failed: F }`. It MUST also update `process/research.md`: move each downloaded source from Pending Review → Ruled In; move each manual/failed source from Pending Review → Ruled Out (with reason). It MUST update `RESEARCH.md` root portfolio: source count and updated date for this topic.

**verify mode**

- **FR-018**: `hi-discovery verify` MUST be strictly read-only (no file writes, no `tracking.yaml` modifications).
- **FR-019**: `verify` MUST check: (a) `discovery-plan.md` exists and parses as valid YAML; (b) `sources[]` is non-empty; (c) at least one entry has `type: terminology`; (d) every entry has non-empty `rationale`; (e) every entry has non-empty `search_terms[]`; (f) every `evidence_level` is from the allowed set; (g) every `type` is from the allowed set (unknown types → warning only).
- **FR-020**: `verify` MUST exit 0 iff all checks pass; exit 1 otherwise. Per-check output uses `✓` / `✗`.

**general**

- **FR-021**: All modes accept `TOPIC` positional argument and `--dry-run`. `plan` and `implement` accept `--force`.
- **FR-022**: The skill MUST reside at `skills/.curated/hi-discovery/SKILL.md` following the `skills/_template/` three-level progressive disclosure format.
- **FR-023**: For any topic with a US clinical care or population health angle, the agent MUST actively search and include sources from the US government healthcare ecosystem. Minimum coverage: (a) check CMS eCQM Library and CMIT for existing quality measures; (b) check QPP/MIPS if a clinician performance angle exists; (c) check USPSTF for preventive service grades; (d) assess SDOH relevance using Gravity Project domain taxonomy; (e) check AHRQ for evidence-based practice reports; (f) include CDC surveillance or MMWR if epidemiological evidence is needed.
- **FR-024**: The domain advice section of `discovery-plan.md` MUST address the `reference.md` Domain Advice Checklist in full, including: CMS program alignment, SDOH relevance (with specific Gravity domains if applicable), health equity lens, and existing quality measure landscape.
- **FR-025**: After producing the source plan, the agent MUST present a **Research Expansion Suggestions** section in `discovery-plan.md` with 3–7 numbered, clinically-grounded prompts the user can choose to pursue. These are prospective adjacent areas — NOT sources already in the plan. Each suggestion MUST include: the adjacent topic, why it is relevant to the primary topic, and the first `hi` command the user would run to explore it. Suggestions MUST NOT be added to `sources[]` automatically; they are offered for the user to act on.
- **FR-025a**: Research Expansion Suggestions MUST cover at minimum these categories when applicable: (a) adjacent comorbidities or closely related conditions; (b) a healthcare economics angle (cost of care, disease burden, cost-effectiveness); (c) a health equity or disparate-population angle; (d) an implementation science gap (known barriers to guideline adoption); (e) a data / registry gap (areas with limited evidence or active clinical trial inquiry).
- **FR-026**: When the topic involves a chronic condition, a preventive intervention, or a CMS quality program, the agent MUST include at least one `health-economics` source in `sources[]`. Minimum content: a cost-of-care or disease-burden estimate source (e.g., HCUP, MEPS, GBD) and, where a clinical intervention is involved, a cost-effectiveness reference (e.g., CEA Registry, NICE HTA).
- **FR-027**: The agent MUST function as an interactive research assistant throughout the `plan` interaction. After presenting the plan and expansion suggestions, the agent MUST explicitly prompt the user: which expansion areas (if any) to pursue, whether to run `hi-discovery implement` now, and whether to refine the source list before proceeding.

### Source Type Taxonomy (FR-009)

| `type` value | Examples |
|---|---|
| `guideline` | ADA Standards, ACC/AHA guidelines, USPSTF recommendations, NICE guidance, WHO protocols |
| `systematic-review` | Cochrane reviews, AHRQ evidence reports |
| `terminology` | SNOMED CT, LOINC, ICD-10-CM, RxNorm, UCUM |
| `value-set` | VSAC (NLM), FHIR value sets, PHIN VADS |
| `measure-library` | CMS eCQMs, HEDIS, MIPS/QPP measures, NQF-endorsed measures, Joint Commission |
| `fhir-ig` | US Core, QI-Core, CARIN BB, SMART, Gravity SDOH FHIR IG, condition-specific IGs |
| `sdoh-assessment` | PRAPARE, AHC HRSN Tool, HealthLeads screening, CDC SVI, CDC PLACES |
| `health-economics` | HCUP, MEPS, GBD, CEA Registry, ICER reports, NICE HTA, CMS National Health Expenditure Data |
| `government-program` | CMS CMMI model specs, Medicaid state plan amendments, CMS LCD/NCD coverage policies, HRSA program guidance |
| `cds-library` | CDS Hooks registry, OpenCDS |
| `registry` | ClinicalTrials.gov, disease registries |
| `pubmed-article` | PubMed / PMC research articles |
| `other` | Anything not covered above |

At least one `terminology` entry is required for any plan that passes `verify`.

### Evidence Level Taxonomy (FR-010)

GRADE: `grade-a`, `grade-b`, `grade-c`, `grade-d`
USPSTF: `uspstf-a`, `uspstf-b`, `uspstf-c`, `uspstf-d`, `uspstf-i`
Other: `expert-consensus`, `reference-standard`, `n/a`

### Key Entities

- **Discovery Plan** (`discovery-plan.md`): YAML frontmatter + Markdown prose. Contains domain advice, `sources[]`, and Research Expansion Suggestions. Human-editable between `plan` and `implement`.
- **Source Entry**: One item in `sources[]` with `name`, `type`, `rationale`, `search_terms[]`, `evidence_level`, `access` (`open | authenticated | manual`), optional `url`, optional `auth_note` (required when `access: authenticated`), optional `recommended` (bool, for high-value authenticated sources).
- **Research Portfolio** (`RESEARCH.md` at repo root): Cross-topic portfolio log. CLI-managed table of all topics with stage, source count, and dates. Human-editable Notes column and prose.
- **Per-Topic Research Notes** (`process/research.md`): Source-level disposition tracking — Ruled In, Ruled Out (with reason), Pending Review. CLI appends rows; humans maintain Open Questions and Related Topics sections.
- **Ingest Plan** (`ingest-plan.md`): Populated by `implement` with manual-acquisition sources. Consumed by `hi-ingest` (004) for any remaining local-file registration.
- **Conflicts Stub** (`conflicts.md`): Created-unless-exists. Human-maintained guideline contradictions.

---

## Success Criteria

- **SC-001**: A clinical informaticist with no prior knowledge of a domain receives actionable domain advice and a populated source list from a single `hi-discovery plan` invocation.
- **SC-002**: Running `hi-discovery implement` on a plan with five open-access sources downloads all five to `sources/`, registers them in `tracking.yaml`, and reports any failures per-source.
- **SC-003**: `verify` catches a missing terminology source and exits 1 with an actionable message.
- **SC-004**: `hi search pubmed --query "diabetes screening" --max 10` returns structured JSON output in under 5 seconds.
- **SC-005**: The SKILL.md passes all `tests/skills/` checks with zero failures.
- **SC-006**: `--dry-run implement` produces zero downloads and zero `tracking.yaml` events while still reporting which sources would be downloaded vs. flagged manual.
- **SC-007**: After completing a plan, the agent presents 3–7 Research Expansion Suggestions with specific next `hi` commands, and explicitly prompts the user for direction — demonstrating interactive research assistant behavior.
- **SC-008**: For a chronic condition topic (e.g., diabetes, hypertension), at least one `health-economics` source appears in `sources[]` and the domain advice section addresses cost-of-care burden.

---

## Assumptions

- PubMed Entrez and ClinicalTrials.gov v2 APIs are free and publicly accessible without authentication.
- NICE, Cochrane, and most society portals require manual download; the skill marks these `access: manual` and does not attempt programmatic fetch.
- The agent has sufficient domain knowledge to provide useful clinical advice without internet access; `hi search` results augment rather than replace that knowledge.
- `hi ingest implement --url` handles redirect following, MIME type detection, and file extension inference from Content-Type headers.
- All downloaded sources are stored in `sources/` at repo root — the same directory used by manually ingested files.
- The optional `NCBI_API_KEY` environment variable, if set, is used to increase PubMed rate limits; it is never written to any artifact.

## Architecture Decision: Skill, not Agent

`hi-discovery` is implemented as a **SKILL.md** (not a standalone agent or sub-process) for the following reasons:

1. **Interactive research assistant** — the primary use case is a conversation: the user asks about a topic, the skill guides the LLM to search, reason, and suggest; the user asks follow-up questions mid-session. This is inherently dialogic and is best served by the user's own LLM session reading a SKILL.md.
2. **Guiding principle** — all deterministic work (API calls, downloads, file writes) is handled by the `hi` CLI. The skill provides reasoning. A standalone agent would duplicate this boundary without adding value.
3. **Framework consistency** — all six HI framework skills (003–008) follow the SKILL.md pattern established in 002.
4. **User controls the pace** — the user can ask "tell me more about the economics angle" or "what else should I search?" mid-session and the LLM responds in full context. An autonomous agent cannot do this.

A `hi discovery run` non-interactive CLI entrypoint may be added in a future spec for batch/unattended use without changing the SKILL.md design.



## Overview

`hi-discovery` is the entry point skill for every new clinical topic. It guides an agent through structured source discovery — establishing the evidence landscape before any files are registered or extracted.

**Guiding principle**: all deterministic work via `hi` CLI; all reasoning by the agent.

The skill has three modes:

| Mode | What the agent does | `hi` CLI called | Output |
|------|--------------------|--------------------|--------|
| `plan` | Reasons about the topic domain; identifies source types, specific sources, search strategies, and evidence levels | `hi status show` | `process/plans/discovery-plan.md` |
| `implement` | Converts approved plan entries into actionable ingest tasks | `hi ingest plan` (read-only) | `process/plans/ingest-plan.md` (populated) |
| `verify` | Validates plan structure, evidence coverage, and terminology presence | `hi validate` (read-only) | Exit report (no file writes) |

Discovery is intentionally **read-only with respect to `tracking.yaml`**. No sources are registered; no checksums computed. The sole outputs are plan artifacts for human review.

### Many-to-Many Awareness

Discovery does not name L2 artifacts (that is `hi-extract`'s responsibility). However, the plan should group sources by their expected *contribution type* (criteria source, terminology source, measure reference, FHIR IG) so downstream skills have semantic context.

---

## User Scenarios & Testing

### User Story 1 — Plan discovery for a new topic (Priority: P1)

A clinical informaticist initializes a new topic ("sepsis-early-detection") and wants to know what sources to gather before starting. They invoke `hi-discovery plan`. The agent reasons about the clinical domain, identifies authoritative guidelines, relevant terminology systems, existing measure libraries, and FHIR IGs, and writes a structured, human-reviewable plan.

**Why this priority**: Discovery is the entry point for every topic. Without it, teams skip sources and produce incomplete artifacts.

**Independent Test**: Running `plan` on an initialized empty topic produces a well-formed `discovery-plan.md` with at least one entry per required source category.

**Acceptance Scenarios**:

1. **Given** an initialized topic with no sources, **When** `hi-discovery plan` runs, **Then** `process/plans/discovery-plan.md` is created with YAML frontmatter containing a `sources[]` list; each entry has `name`, `type`, `rationale`, `search_terms[]`, `evidence_level`, and optional `url`.
2. **Given** a topic domain implying coded clinical concepts, **When** `plan` runs, **Then** the plan includes at least one source with `type: terminology` (SNOMED CT, LOINC, ICD-10, or RxNorm).
3. **Given** a plan is produced, **When** the human reviews it, **Then** `research.md` and `conflicts.md` stubs exist in `process/` (created-unless-exists by the plan step).
4. **Given** `discovery-plan.md` already exists, **When** `plan` runs without `--force`, **Then** the skill warns and stops; the existing plan is not modified.
5. **Given** `--force` is passed, **When** `plan` runs, **Then** the existing plan is overwritten and a new `discovery_planned` event is appended to `tracking.yaml`.
6. **Given** `--dry-run` is passed, **When** `plan` runs, **Then** the agent's proposed plan is printed to stdout; no files are written and no events appended.

---

### User Story 2 — Implement the discovery plan (Priority: P1)

After reviewing and editing `discovery-plan.md`, the informaticist runs `hi-discovery implement`. The agent reads the approved plan and populates `ingest-plan.md` with one entry per source, preserving source metadata (type, rationale, evidence level) so `hi-ingest` can execute efficiently.

**Why this priority**: Implement is the bridge from discovery reasoning to actionable ingest tasks. Without it, the plan is advisory only.

**Independent Test**: Running `implement` on a valid plan produces a populated `ingest-plan.md` with one entry per source entry in the plan.

**Acceptance Scenarios**:

1. **Given** a valid `discovery-plan.md`, **When** `hi-discovery implement` runs, **Then** `process/plans/ingest-plan.md` is created (or updated) with one entry per source in the plan's `sources[]` list; each entry carries over `name`, `type`, `url`, `rationale`, and `evidence_level`.
2. **Given** no `discovery-plan.md` exists, **When** `implement` runs, **Then** the skill exits non-zero with a clear error: `discovery-plan.md not found — run hi-discovery plan first`.
3. **Given** `ingest-plan.md` already contains entries, **When** `implement` runs without `--force`, **Then** the skill warns and stops; no entries are overwritten.
4. **Given** `implement` succeeds, **When** complete, **Then** a `discovery_implemented` event is appended to `tracking.yaml`.
5. **Given** `research.md` does not yet exist, **When** `implement` runs, **Then** it creates a stub (create-unless-exists); if it already exists it is not modified.

---

### User Story 3 — Verify discovery quality (Priority: P2)

Before handing off to `hi-ingest`, the informaticist wants confidence that the plan is well-formed and covers the required source categories. `hi-discovery verify` reads the plan and reports any structural issues or coverage gaps without modifying anything.

**Why this priority**: Prevents ingesting from an incomplete plan, which would propagate gaps into L2 and L3.

**Independent Test**: Running `verify` on a complete plan exits 0; running it on a plan missing a terminology source exits 1 with a gap report.

**Acceptance Scenarios**:

1. **Given** a complete, well-formed plan, **When** `hi-discovery verify` runs, **Then** exit 0 and a per-check summary: `✓ frontmatter valid`, `✓ terminology source present`, `✓ all entries have rationale`, etc.
2. **Given** a plan with no terminology source, **When** `verify` runs, **Then** exit 1 with: `✗ No terminology source found — L3 computable artifacts require at least one SNOMED/LOINC/ICD/RxNorm source`.
3. **Given** a plan entry missing `rationale`, **When** `verify` runs, **Then** exit 1 with the source name and missing field identified.
4. **Given** no `discovery-plan.md` exists, **When** `verify` runs, **Then** exit 1 with a clear message; no partial output.
5. **Given** `verify` runs under any condition, **Then** no files are written and `tracking.yaml` is not modified.

---

### Edge Cases

- Topic name contains spaces or special characters — `hi` CLI normalises; skill should pass topic name as-is.
- Plan `sources[]` list is empty — `implement` fails with a clear error before writing anything; `verify` flags as a gap.
- Plan frontmatter is syntactically invalid YAML — `implement` and `verify` both fail at parse time with a line-level error.
- Source `type` is an unrecognised value — `verify` emits a warning (not an error); forward-compatible.
- `ingest-plan.md` is partially populated (some entries from a prior run) — `implement` without `--force` warns; with `--force` replaces all entries.
- `--dry-run` on `implement` — prints the entries that would be written to `ingest-plan.md`; no writes.
- Network is unavailable — discovery is offline; agent reasons from domain knowledge, not live search results. URLs in the plan are suggestions, not fetched resources.

---

## Requirements

### Functional Requirements

**plan mode**

- **FR-001**: `hi-discovery plan` MUST produce `topics/<name>/process/plans/discovery-plan.md` with YAML frontmatter containing a `sources[]` list. Each entry MUST have: `name` (string), `type` (see FR-003), `rationale` (non-empty string), `search_terms[]` (non-empty list), and `evidence_level` (see FR-004). `url` is optional.
- **FR-002**: `plan` MUST create `process/research.md` and `process/conflicts.md` as stubs (create-unless-exists). If they already exist they MUST NOT be modified.
- **FR-003**: Valid `type` values: `guideline`, `systematic-review`, `terminology`, `value-set`, `measure-library`, `fhir-ig`, `cds-library`, `registry`, `other`. At least one entry with `type: terminology` MUST be present in any plan that passes `verify`.
- **FR-004**: Valid `evidence_level` values: `grade-a`, `grade-b`, `grade-c`, `grade-d`, `uspstf-a`, `uspstf-b`, `uspstf-c`, `uspstf-d`, `uspstf-i`, `expert-consensus`, `reference-standard`, `n/a`. Required on every source entry.
- **FR-005**: If `discovery-plan.md` already exists, `plan` MUST warn and stop unless `--force` is passed. With `--force`, existing file is overwritten.
- **FR-006**: `--dry-run` on `plan` MUST print the proposed plan to stdout without writing any file or appending any event.
- **FR-007**: Successful `plan` (non-dry-run) MUST append a `discovery_planned` event to `tracking.yaml`.

**implement mode**

- **FR-008**: `hi-discovery implement` MUST read `discovery-plan.md` and write one entry per source into the `sources[]` list in `process/plans/ingest-plan.md` YAML frontmatter. Each entry MUST carry over: `name`, `type`, `url` (if present), `rationale`, `evidence_level`.
- **FR-009**: If `discovery-plan.md` does not exist, `implement` MUST exit non-zero with: `discovery-plan.md not found — run hi-discovery plan first`.
- **FR-010**: If `sources[]` in the plan is empty, `implement` MUST exit non-zero before writing anything.
- **FR-011**: If `ingest-plan.md` already has entries, `implement` MUST warn and stop unless `--force` is passed.
- **FR-012**: `implement` MUST create `process/research.md` stub (create-unless-exists). MUST NOT modify existing file.
- **FR-013**: Successful `implement` MUST append a `discovery_implemented` event to `tracking.yaml`.
- **FR-014**: `--dry-run` on `implement` MUST print the entries that would be written; no file writes, no events.

**verify mode**

- **FR-015**: `hi-discovery verify` MUST be strictly read-only — no file writes, no `tracking.yaml` modifications.
- **FR-016**: `verify` MUST exit 0 only when ALL checks pass; exit 1 if any check fails.
- **FR-017**: `verify` MUST check: (a) `discovery-plan.md` exists and is parseable YAML; (b) `sources[]` is non-empty; (c) at least one entry has `type: terminology`; (d) every entry has a non-empty `rationale`; (e) every entry has a non-empty `search_terms[]`; (f) every `evidence_level` value is from the allowed set (FR-004); (g) every `type` value is from the allowed set (FR-003) — unknown types produce warnings, not failures.
- **FR-018**: `verify` MUST produce a per-check report with `✓` for pass and `✗` for fail, naming the source entry when the failure is entry-specific.

**General**

- **FR-019**: The skill MUST reside at `skills/.curated/hi-discovery/SKILL.md` and follow the three-level progressive disclosure template from `skills/_template/`.
- **FR-020**: All modes MUST accept a `TOPIC` positional argument identifying the topic name.
- **FR-021**: All modes MUST support `--dry-run`.
- **FR-022**: `plan` and `implement` MUST support `--force`.

### Non-Functional Requirements

- **NFR-001**: `verify` is strictly non-destructive (FR-015) — consistent with FR-022 in 002 spec.
- **NFR-002**: The skill requires no runtime dependencies beyond `hi` CLI, `yq`, and bash 3.2+.
- **NFR-003**: The SKILL.md MUST pass all `tests/skills/` checks (schema, security, framework contracts) with zero failures.
- **NFR-004**: Evidence levels and source types are forward-compatible — unknown values produce warnings, not hard failures in `verify`.

### Key Entities

- **Discovery Plan** (`discovery-plan.md`): YAML frontmatter + Markdown prose. The primary output of `plan` mode. Human-editable between `plan` and `implement`. `sources[]` list is the machine-readable core.
- **Ingest Plan** (`ingest-plan.md`): YAML frontmatter populated by `implement`. Consumed by `hi-ingest` (004). Not human-authored; generated from the discovery plan.
- **Source Entry**: One item in `sources[]`. Fields: `name`, `type`, `rationale`, `search_terms[]`, `evidence_level`, `url` (optional).
- **Research Stub** (`research.md`): Created-unless-exists by `plan` and `implement`. Template for the human to fill with evidence notes and citations.
- **Conflicts Stub** (`conflicts.md`): Created-unless-exists by `plan`. Template for the human to record guideline contradictions discovered during review.

---

## Success Criteria

- **SC-001**: A clinical informaticist with no prior knowledge of the topic can produce a discovery plan in a single agent conversation covering all required source categories.
- **SC-002**: `verify` catches a missing terminology source and exits 1 with an actionable error message identifying the gap.
- **SC-003**: `implement` produces an `ingest-plan.md` that `hi-ingest` (004) can consume without modification.
- **SC-004**: The SKILL.md passes all 31 `tests/skills/` parametrized checks (schema, security, contracts) with zero failures.
- **SC-005**: `--dry-run` on both `plan` and `implement` produces zero file writes while still surfacing any validation errors.

---

## Assumptions

- The agent has domain knowledge sufficient to identify relevant guidelines and terminology systems for common clinical topics without live internet search.
- URLs in source entries are suggestions for the human to verify; the skill does not fetch or validate them.
- `research.md` and `conflicts.md` are human-maintained after scaffolding; the skill writes stubs only.
- `ingest-plan.md` is the handoff artifact to `hi-ingest` (004); the schema of its `sources[]` entries must be compatible with what 004 expects.
- Evidence grading uses GRADE and USPSTF scales as the two dominant frameworks in clinical informatics; other frameworks (Oxford CEBM, SIGN) are accommodated via `expert-consensus` or `reference-standard`.
