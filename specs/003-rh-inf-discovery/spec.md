# Feature Specification: `rh-inf-discovery` Skill

**Feature Branch**: `003-rh-inf-discovery`
**Created**: 2026-04-04 | **Updated**: 2026-04-04
**Status**: ✅ Complete
**Depends On**: [002 — RH Skills CLI](../002-rh-agent-skills/)

## Clarifications

### Session 2026-04-04

- Q: Does `implement` download sources now or only populate `ingest-plan.md` for rh-inf-ingest to handle later? → A: Discovery is pure planning — no downloads occur during the session. `rh-inf-ingest` (004) owns all source acquisition. The discovery session produces `discovery-plan.yaml` (machine-readable work queue) and `discovery-readout.md` (narrative); `rh-inf-ingest` reads `discovery-plan.yaml` to execute downloads.
- Q: What are the source count bounds for a discovery plan? → A: 5 minimum, 25 maximum sources per plan.
- Q: Should `verify` check for a health-economics source? → A: Warning only — `verify` emits `⚠ No health-economics source found — recommended for chronic conditions` but does not exit 1.
- Q: What should the default result count be for `rh-skills search pubmed`? → A: Default 20, configurable via `--max`. All `rh-skills search` subcommands share this default.
- Q: Should the discovery plan be mutable during the agent session? → A: Yes — the plan is a living document during the session. The agent updates it as the conversation evolves; it writes to disk only on user approval or an explicit save checkpoint.

## Overview

`rh-inf-discovery` is an active **interactive research assistant** for clinical informaticists starting a new topic. It is a single conversational session with two checkpointed operations:

1. **Domain advice** — reasons about the clinical domain and tells the user what to consider (diagnostic criteria, population characteristics, existing measures, regulatory context, evidence gaps)
2. **Source identification & curation** — searches PubMed, PubMed Central, ClinicalTrials.gov, and known medical society URL patterns; produces a curated source list in memory, advising on access method for each source; updates the discovery plan as the conversation evolves
3. **Research expansion** — after each pass, suggests adjacent areas (comorbidities, economics, equity, implementation gaps) and prompts the user to explore further

**Guiding principle**: all deterministic work (search API calls, downloads) via `rh-skills` CLI; all reasoning (domain advice, relevance judgement, evidence prioritisation, expansion suggestions) by the agent. Downloads of open-access sources happen at the end of the plan session (Step 12), after the user approves and saves the plan.

The skill has two modes:

| Mode | Agent role | `rh-skills` CLI called | Output |
|------|-----------|----------------|--------|
| `plan` | Interactive research conversation — searches, advises, expands, iterates; writes plan to disk on user approval; downloads open-access sources after save | `rh-skills search pubmed/pmc/clinicaltrials`, `rh-skills ingest implement --url` | `discovery-plan.yaml` + `discovery-readout.md` (on save), `RESEARCH.md` updated, source files in `sources/` |
| `verify` | Validates a saved plan for structural completeness and coverage | (read-only) | Per-check report; no file writes |

---

## User Scenarios & Testing

### User Story 1 — Research a clinical topic from scratch (Priority: P1)

A clinical informaticist starts a new topic "sepsis-early-detection" and has no idea where to begin. They invoke `rh-inf-discovery`. The agent:
- Explains what to consider in sepsis informatics (diagnostic criteria like qSOFA/SOFA, organ dysfunction coding, time-sensitive treatment windows, population subtypes, existing SEP-1 measure)
- Searches PubMed for recent systematic reviews and guidelines
- Searches ClinicalTrials.gov for active/completed relevant trials
- Produces a discovery-plan.yaml listing all sources with access advisories for authenticated ones
- Suggests adjacent research areas (economics of sepsis care, SDOH factors, implementation barriers)
- Saves the discovery plan to disk when the user approves it

**Acceptance Scenarios**:

1. **Given** an initialised topic, **When** `rh-inf-discovery` session starts, **Then** the agent advises on domain considerations and calls `rh-skills search pubmed` with topic-relevant terms.
2. **Given** an `access: open` source is identified, **Then** the agent records it in the in-session plan with `url` populated; `rh-inf-ingest` will download it later when consuming `discovery-plan.yaml`.
3. **Given** an `access: authenticated` source is identified, **Then** the agent prints an access advisory (name, relevance, URL, auth method, search terms) and includes the source in `discovery-plan.yaml` with `auth_note`; no download is attempted during discovery.
4. **Given** `discovery-plan.yaml` already exists when the session starts, **Then** the agent warns and offers to load it for continuation or start fresh with `--force`.
5. **Given** `--dry-run`, **When** the session runs, **Then** proposed sources and domain advice are shown; no files written and no events appended.
6. **Given** the user approves the plan, **Then** `discovery-plan.yaml` and `discovery-readout.md` are written, `RESEARCH.md` portfolio is updated, and a `discovery_planned` event is appended to `tracking.yaml`.

---

### User Story 2 — Iterative research expansion (Priority: P1)

After the initial pass, the user asks the agent to explore the healthcare economics angle for diabetes screening. The agent searches additional sources and adds them to the working plan, updating the living discovery-plan.yaml.

**Acceptance Scenarios**:

1. **Given** the user requests expansion into an adjacent area, **When** the agent searches and finds relevant sources, **Then** new entries are added to the in-session plan without overwriting existing entries.
2. **Given** the user asks to save mid-session, **Then** the current plan state is written to `discovery-plan.yaml` (and `discovery-readout.md`) as a checkpoint; the session continues.
3. **Given** the plan reaches 25 sources, **Then** the agent warns that the maximum is reached and moves additional candidates to the Research Expansion Suggestions section rather than `sources[]`.
4. **Given** the plan has fewer than 5 sources after all searches, **Then** the agent searches additional databases or source categories before presenting the plan for approval.

---

### User Story 3 — Verify discovery coverage (Priority: P2)

Before proceeding to ingest, the informaticist runs `rh-inf-discovery verify` to confirm the plan is well-formed and covers required evidence categories.

**Acceptance Scenarios**:

1. **Given** a complete plan, **When** `verify` runs, **Then** exit 0 with a per-check report: `✓ frontmatter valid`, `✓ terminology source present`, `✓ all entries have rationale and evidence_level`, etc.
2. **Given** a plan with no terminology source, **When** `verify` runs, **Then** exit 1: `✗ No terminology source (SNOMED/LOINC/ICD/RxNorm) — required for L3 computable output`.
3. **Given** a plan entry missing `rationale` or `evidence_level`, **When** `verify` runs, **Then** exit 1 naming the source and missing field.
4. **Given** `verify` runs under any condition, **Then** no files are written and `tracking.yaml` is not modified.

---

### Edge Cases

- PubMed API returns zero results — agent falls back to domain knowledge and known society URL patterns; warns user that search was sparse.
- Source URL is known to require authentication or redirect to a login page — source is included in `discovery-plan.yaml` with `access: authenticated` or `access: manual` and an `auth_note` describing retrieval method; no download is attempted during discovery.
- Plan reaches 25-source cap — agent moves additional candidates to Research Expansion Suggestions rather than silently dropping them.
- Plan has fewer than 5 sources after all searches — agent explicitly searches additional databases before presenting for approval.
- Plan YAML is malformed — `verify` fails at parse time with a line-level error.
- Topic name not found in `tracking.yaml` — session exits non-zero with: `topic '<name>' not initialised — run rh-skills init first`.
- Network unavailable during session — agent reasons from domain knowledge; records all sources as `access: manual` in `discovery-plan.yaml` with appropriate `auth_note`; warns the user clearly.
- User asks to save mid-session — current plan state is checkpointed to `discovery-plan.yaml` and `discovery-readout.md`; session continues; subsequent save with `--force` implied.

---

## Requirements

### Functional Requirements

**`rh-skills` CLI extensions required by this skill**

- **FR-001**: A new `rh-skills search` command group MUST be implemented with the following subcommands:
  - `rh-skills search pubmed --query <terms> [--max N] [--json]` — calls PubMed Entrez esearch + efetch APIs; returns structured list of results including PMID, title, authors, journal, year, abstract snippet, DOI, URL, PMC ID, and open-access flag. Default `--max 20`.
  - `rh-skills search pmc --query <terms> [--max N] [--json]` — searches PubMed Central for open-access full-text articles and returns the same metadata shape as PubMed, with `open_access: true`. Default `--max 20`.
  - `rh-skills search clinicaltrials --query <terms> [--max N] [--status <status>] [--json]` — calls ClinicalTrials.gov API v2; returns NCT ID, title, status, phase, conditions, interventions, summary snippet, and canonical study URL. Default `--max 20`.
- **FR-002**: Implemented in `rh-skills ingest implement` (see spec 004-rh-inf-ingest). Discovery does not call this command. `rh-skills ingest implement` accepts `--url <url>` as an alternative to a local file path; when given, it downloads the resource to `sources/<name>.<ext>`, computes SHA-256, and registers it in `tracking.yaml`.
- **FR-003**: `rh-skills search` subcommands MUST require no API key for PubMed and ClinicalTrials.gov (both are free/public). A `NCBI_API_KEY` environment variable MAY be set to increase PubMed rate limits (10 req/s vs. 3 req/s).

**plan mode**

- **FR-004**: `rh-inf-discovery session` MUST produce two files on user approval or explicit save: (a) `process/plans/discovery-plan.yaml` — pure YAML (no frontmatter delimiters), the single machine-readable source of truth containing `topic`, `date`, `sources[]`, and related fields; (b) `process/plans/discovery-readout.md` — generated Markdown narrative containing the **Domain Advice** section and the **Research Expansion Suggestions** section, with a header note "This file is derived from discovery-plan.yaml. Do not edit directly." The plan is a **living document during the session** — the agent updates it as the conversation evolves and only writes to disk at a save checkpoint (user approval or explicit "save" instruction).
- **FR-004a**: A discovery plan MUST contain a minimum of 5 and a maximum of 25 source entries. If fewer than 5 sources are identified, the agent MUST search additional databases or source categories before presenting the plan. If the agent identifies more than 25 high-quality sources, it MUST select the 25 most relevant and note the remainder as expansion candidates in the Research Expansion Suggestions section.
- **FR-005**: Each source entry in `sources[]` MUST have: `name`, `type` (see FR-009), `rationale`, `search_terms[]`, `evidence_level` (see FR-010), `access` (`open | authenticated | manual`). `url` is optional but MUST be present when `access: open`. When `access: authenticated`, the entry MUST include `auth_note` — a plain-English description of how to obtain access (e.g., institutional login, free registration, society membership).
- **FR-005a**: For `access: authenticated` sources, the agent MUST include a `recommended: true` flag when the source is considered authoritative or high-value for the topic domain, regardless of whether it can be downloaded automatically. The discovery plan is the authoritative recommendation — access difficulty does not reduce a source's priority.
- **FR-006**: The agent MUST call `rh-skills search pubmed` and at least one other `rh-skills search` subcommand during `plan`; results inform the `sources[]` list. The agent decides which results are relevant.
- **FR-007**: `plan` MUST create `process/notes.md` stub (create-unless-exists) using the canonical format (Open Questions, Decisions, Source Conflicts, Notes sections). Existing `notes.md` MUST NOT be modified.
- **FR-008**: If `discovery-plan.yaml` already exists, `plan` MUST warn and stop unless `--force` is passed. Successful `plan` (non-dry-run) MUST append `discovery_planned` to `tracking.yaml`. `--force` applies to both `discovery-plan.yaml` and `discovery-readout.md`.

**session mode**

- **FR-011 (REMOVED)**: Discovery does not download sources. All source acquisition is delegated to `rh-inf-ingest`. Approved open-access sources are recorded in `discovery-plan.yaml` with `access: open` and `url`; rh-inf-ingest reads this file and handles download.
- **FR-011a**: For `access: authenticated` sources, the agent MUST print a formatted per-source access advisory during the session — naming the source, explaining why it is recommended for this topic, providing the specific URL, login mechanism, and what to search for once authenticated.
- **FR-011b**: The access advisory format MUST include: source name, why it is relevant, access URL, authentication method (institutional login / free registration / society membership / library proxy), and suggested search terms to use once inside.
- **FR-012**: Sources with `access: manual` or `access: authenticated` MUST be included in `discovery-plan.yaml` with an `auth_note` field describing how to obtain access. `rh-inf-ingest` reads `discovery-plan.yaml` directly to determine which sources require manual retrieval. No `ingest-plan.md` is generated.
- **FR-013**: Sources that cannot be accessed programmatically (non-2xx HTTP, auth redirect) MUST be recorded in `discovery-plan.yaml` with `access: manual` or `access: authenticated` and an `auth_note`; the agent reports the access barrier inline and continues. No download is attempted during discovery.
- **FR-014**: When the user approves the session plan or issues a save checkpoint, the agent MUST write `process/plans/discovery-plan.yaml` and `process/plans/discovery-readout.md`, and update `RESEARCH.md` root portfolio (source count, updated date). `process/notes.md` is human-maintained and is NOT updated by the CLI.
- **FR-015**: If `discovery-plan.yaml` already exists when the session starts, the agent MUST warn the user and offer to load it for continuation or start fresh with `--force`.
- **FR-016**: If no sources are identified after exhausting all search strategies, the session MUST exit with a clear message listing what was searched and suggesting the user try alternate search terms.
- **FR-017**: Successful session save MUST append `discovery_planned` event to `tracking.yaml` with payload: `{ sources: N, downloaded: D, manual_pending: M }`.

**verify mode**

- **FR-018**: `rh-inf-discovery verify` MUST be strictly read-only (no file writes, no `tracking.yaml` modifications).
- **FR-019**: `verify` MUST check: (a) `discovery-plan.yaml` exists and parses as valid YAML (no frontmatter extraction needed — file is pure YAML); (b) `sources[]` is non-empty and contains 5–25 entries; (c) at least one entry has `type: terminology`; (d) every entry has non-empty `rationale`; (e) every entry has non-empty `search_terms[]`; (f) every `evidence_level` is from the allowed set; (g) every `type` is from the allowed set (unknown types → warning only); (h) if no `health-economics` source is present → emit `⚠ No health-economics source found — recommended for chronic conditions and preventive interventions` (warning only, does not fail the check).
- **FR-020**: `verify` MUST exit 0 iff all checks pass; exit 1 otherwise. Per-check output uses `✓` / `✗`.

**general**

- **FR-021**: Both modes accept `TOPIC` positional argument and `--dry-run`. The `session` mode accepts `--force` (to overwrite an existing plan).
- **FR-022**: The skill MUST reside at `skills/.curated/rh-inf-discovery/SKILL.md` following the `skills/_template/` three-level progressive disclosure format.
- **FR-023**: For any topic with a US clinical care or population health angle, the agent MUST actively search and include sources from the US government healthcare ecosystem. Minimum coverage: (a) check CMS eCQM Library and CMIT for existing quality measures; (b) check QPP/MIPS if a clinician performance angle exists; (c) check USPSTF for preventive service grades; (d) assess SDOH relevance using Gravity Project domain taxonomy; (e) check AHRQ for evidence-based practice reports; (f) include CDC surveillance or MMWR if epidemiological evidence is needed.
- **FR-024**: The domain advice section of `discovery-readout.md` MUST address the `reference.md` Domain Advice Checklist in full, including: CMS program alignment, SDOH relevance (with specific Gravity domains if applicable), health equity lens, and existing quality measure landscape.
- **FR-025**: After producing the source plan, the agent MUST present a **Research Expansion Suggestions** section in `discovery-readout.md` with 3–7 numbered, clinically-grounded prompts the user can choose to pursue. These are prospective adjacent areas — NOT sources already in the plan. Each suggestion MUST include: the adjacent topic, why it is relevant to the primary topic, and the first `rh-skills` command the user would run to explore it. Suggestions MUST NOT be added to `sources[]` automatically; they are offered for the user to act on.
- **FR-025a**: Research Expansion Suggestions MUST cover at minimum these categories when applicable: (a) adjacent comorbidities or closely related conditions; (b) a healthcare economics angle (cost of care, disease burden, cost-effectiveness); (c) a health equity or disparate-population angle; (d) an implementation science gap (known barriers to guideline adoption); (e) a data / registry gap (areas with limited evidence or active clinical trial inquiry).
- **FR-026**: When the topic involves a chronic condition, a preventive intervention, or a CMS quality program, the agent MUST include at least one `health-economics` source in `sources[]`. Minimum content: a cost-of-care or disease-burden estimate source (e.g., HCUP, MEPS, GBD) and, where a clinical intervention is involved, a cost-effectiveness reference (e.g., CEA Registry, NICE HTA).
- **FR-027**: The agent MUST function as an interactive research assistant throughout the session. The plan is a **living document** — the agent may add, remove, or revise source entries and expansion suggestions as the conversation develops. The plan is written to disk only when the user explicitly approves it or issues a save instruction. After each research pass, the agent MUST present the scripted interactive prompt verbatim: "**What would you like to do next?** A) Explore an expansion area — tell me the number  B) Add, remove, or modify sources  C) Save the plan and move on to `rh-inf-ingest`". The agent MUST then emit the status block and stop — no text after the block, no pre-answering of unchosen options.

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

- **Discovery Plan** (`discovery-plan.yaml`): Pure YAML file (no frontmatter delimiters) — the single machine-readable source of truth. Contains `topic`, `date`, `sources[]`, and related metadata. Operated on by `rh-skills validate --plan`. Human-editable between sessions. `rh-inf-ingest` reads this file directly for source acquisition.
- **Discovery Readout** (`discovery-readout.md`): Generated Markdown narrative derived from `discovery-plan.yaml`. Contains `## Domain Advice` and `## Research Expansion Suggestions` sections. For human/agent reading only — never machine-parsed. Includes a note: "This file is derived from discovery-plan.yaml. Do not edit directly."
- **Source Entry**: One item in `sources[]` with `name`, `type`, `rationale`, `search_terms[]`, `evidence_level`, `access` (`open | authenticated | manual`), optional `url`, optional `auth_note` (required when `access: authenticated`), optional `recommended` (bool, for high-value authenticated sources).
- **Research Portfolio** (`RESEARCH.md` at repo root): Cross-topic portfolio log. CLI-managed table of all topics with stage, source count, and dates. Human-editable Notes column and prose.
- **Per-Topic Human Annotations** (`process/notes.md`): Human-maintained stub created by `rh-skills init`. Sections: Open Questions, Decisions, Source Conflicts, Notes. The CLI creates the stub only — no further writes.

---

## Success Criteria

- **SC-001**: A clinical informaticist with no prior knowledge of a domain receives actionable domain advice and a populated source list from a single `rh-inf-discovery plan` invocation.
- **SC-003**: `verify` catches a missing terminology source and exits 1 with an actionable message.
- **SC-004**: `rh-skills search pubmed --query "diabetes screening" --max 10` returns structured JSON output in under 5 seconds.
- **SC-005**: The SKILL.md passes all `tests/skills/` checks with zero failures.
- **SC-007**: After completing a plan, the agent presents 3–7 Research Expansion Suggestions with specific next `rh-skills` commands, then presents the scripted A/B/C prompt verbatim (A: explore expansion area, B: add/remove/modify sources, C: save plan), emits the status block, and stops — no trailing prose after the block.
- **SC-008**: For a chronic condition topic (e.g., diabetes, hypertension), at least one `health-economics` source appears in `sources[]` and the domain advice section addresses cost-of-care burden.

---

## Assumptions

- PubMed Entrez and ClinicalTrials.gov v2 APIs are free and publicly accessible without authentication.
- NICE, Cochrane, and most society portals require manual download; the skill marks these `access: manual` and does not attempt programmatic fetch.
- The agent has sufficient domain knowledge to provide useful clinical advice without internet access; `rh-skills search` results augment rather than replace that knowledge.
- See spec 004-rh-inf-ingest for download implementation details (`rh-skills ingest implement --url` redirect following, MIME type detection, and file extension inference).
- All downloaded sources are stored in `sources/` at repo root — the same directory used by manually ingested files.
- The optional `NCBI_API_KEY` environment variable, if set, is used to increase PubMed rate limits; it is never written to any artifact.

## Architecture Decision: Skill, not Agent

`rh-inf-discovery` is implemented as a **SKILL.md** (not a standalone agent or sub-process) for the following reasons:

1. **Interactive research assistant** — the primary use case is a conversation: the user asks about a topic, the skill guides the LLM to search, reason, and suggest; the user asks follow-up questions mid-session. This is inherently dialogic and is best served by the user's own LLM session reading a SKILL.md.
2. **Guiding principle** — all deterministic work (search API calls) is handled by the `rh-skills` CLI. The skill provides reasoning. A standalone agent would duplicate this boundary without adding value.
3. **Framework consistency** — all six RH skills framework skills (003–008) follow the SKILL.md pattern established in 002.
4. **User controls the pace** — the user can ask "tell me more about the economics angle" or "what else should I search?" mid-session and the LLM responds in full context. An autonomous agent cannot do this.

A non-interactive `rh-skills discovery run` entrypoint may be added in a future spec for batch or unattended use without changing the SKILL.md design.

### Many-to-Many Awareness

Discovery does not name L2 artifacts (that is `rh-inf-extract`'s responsibility). However, the plan should group sources by their expected *contribution type* (criteria source, terminology source, measure reference, FHIR IG) so downstream skills have semantic context.
