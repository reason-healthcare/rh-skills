# Spec Gate Checklist: HI Framework — CLI & Repository Layout

**Purpose**: Author self-review gate before beginning skill specs 003–008. Validates spec completeness, clarity, consistency, and measurability across all four areas: repository layout, CLI commands, tracking.yaml schema, and framework contracts.
**Created**: 2026-04-04
**Feature**: [spec.md](../spec.md)

---

## Repository Layout Requirements

- [ ] CHK001 — Is the layout fully specified such that a developer could recreate the directory tree from the spec alone, without referencing code? [Completeness, Spec §Repository Layout]
- [ ] CHK002 — Are the distinctions between `structured/`, `computable/`, and `process/` explicitly justified (not just named) so a contributor understands why each artifact level lives where it does? [Clarity, Spec §Repository Layout]
- [ ] CHK003 — Is the `sources/` directory scope defined? Does the spec clarify whether it holds all L1 files or only those registered via `hi ingest`? [Ambiguity, Spec §Repository Layout]
- [ ] CHK004 — Is the stub file created by `hi init` (`notes.md`, `tasks.md`) specified with its initial content or format (even if empty)? [Completeness, FR-001]
- [ ] CHK005 — Is the `skills/.curated/` location rationale documented? Is the `.curated/` naming convention explained so contributors don't rename or move it? [Clarity, Spec §Repository Layout]
- [ ] CHK006 — Are requirements defined for what happens when the `topics/` or `sources/` directories are missing at CLI runtime (pre-`hi init`)? [Edge Case, Gap]
- [ ] CHK007 — Is the `plans/` directory at the repo root (not inside `topics/`) explained and distinguished from `topics/<name>/process/plans/`? [Clarity, Spec §Repository Layout]

---

## CLI Commands — Completeness & Clarity

- [ ] CHK008 — Does every command in the CLI commands table have at least one corresponding FR with measurable acceptance criteria? [Traceability, Spec §CLI Commands]
- [ ] CHK009 — Are the options and arguments for each CLI command fully enumerated in the spec (not only in docs/COMMANDS.md)? [Completeness, Gap]
- [ ] CHK010 — Is the `hi status` command table entry updated to reflect the current subcommand interface (`show`, `progress`, `next-steps`, `check-changes`)? [Consistency, Spec §CLI Commands]
- [ ] CHK011 — Are the `hi promote derive` and `hi promote combine` commands' failure behaviors specified (e.g., what happens when target artifact already exists, when source artifacts are missing)? [Completeness, FR-008, FR-009]
- [ ] CHK012 — Is the behavior of `hi ingest plan` specified for the case where an `ingest-plan.md` already exists? Is the `--force` override required here too (per FR-020)? [Consistency, FR-004, FR-020]
- [ ] CHK013 — Is `hi test <topic> <skill>` fully specified: what "run the skill" means, what constitutes a pass vs. fail, and what the `results/` output format looks like? [Clarity, FR-014]
- [ ] CHK014 — Are the `hi tasks` commands specified with enough detail to understand their behavior when `tasks.md` doesn't exist yet? [Edge Case, FR-011, FR-012]
- [ ] CHK015 — Is the `hi validate` command specified for both L2 and L3 artifacts, including which schema each level validates against? Are the schemas documented or referenced? [Completeness, FR-010, Gap]
- [ ] CHK016 — Are exit code semantics (0/1/2) explicitly mapped to each command, or only stated at the NFR level? [Clarity, NFR-003]

---

## tracking.yaml Schema

- [ ] CHK017 — Is the `tracking.yaml` schema complete enough for a developer to implement it without consulting code? Are all fields typed and constrained? [Completeness, Spec §tracking.yaml]
- [ ] CHK018 — Is the `sources[]` array entry schema defined (not just `sources: []`)? Does it specify `path`, `type`, `checksum`, `ingested_at`, and any other required fields? [Completeness, FR-005]
- [ ] CHK019 — Is the `structured[]` array entry schema defined for each topic? Does it specify what fields a structured artifact entry must contain (name, path, derived_from, created_at)? [Completeness, Gap]
- [ ] CHK020 — Is the `computable[]` array entry schema defined? Does it specify the source structured artifacts it was combined from? [Completeness, Gap]
- [ ] CHK021 — Is the `events[]` array entry schema specified? Is the event entry format (name, timestamp, payload) fully documented, or only a list of event names? [Clarity, FR-021, Spec §data-model.md reference]
- [ ] CHK022 — Is `schema_version` strategy documented? When does this change, who bumps it, and what backward compatibility is expected? [Gap]
- [ ] CHK023 — Is the `tracking.yaml` file creation behavior specified for new repos (i.e., does `hi init` create it if absent, or is it a prerequisite)? [Edge Case, FR-002]

---

## Framework Contracts for Skills (FR-016–FR-021)

- [ ] CHK024 — Is the SKILL.md template referenced in FR-016 available in the repository, or is it only described externally (anthropic skills-developer)? Can contributors find it? [Completeness, FR-016, Gap]
- [ ] CHK025 — Is "MUST follow the anthropic skills-developer SKILL.md template" in FR-016 precise enough for a skill author to know which fields are mandatory? [Clarity, FR-016]
- [ ] CHK026 — Is the boundary between "deterministic operations" (hi CLI) and "reasoning" (SKILL.md) explicitly defined with examples in the spec? Is "file I/O" vs. "LLM reasoning" unambiguous? [Clarity, FR-017]
- [ ] CHK027 — Is the YAML front matter format for plan artifacts (FR-018) specified with required fields, or left for each skill spec (003–008) to define independently? [Completeness, FR-018, Gap]
- [ ] CHK028 — Is the error message contract for FR-019 ("fail immediately with a clear error if plan does not exist") specified well enough for consistent UX across all 6 skills? [Consistency, FR-019]
- [ ] CHK029 — Does FR-020 (`--force` flag) apply to ALL `plan` and `implement` modes across all skills, and is this stated unambiguously? Does it apply to `hi` CLI commands too (e.g., `hi promote derive`)? [Consistency, FR-020]
- [ ] CHK030 — Are the named events required by FR-021 enumerated in this spec (or data-model.md) for each skill mode, or left for skill specs 003–008 to define? [Completeness, FR-021, Gap]
- [ ] CHK031 — Are there framework contracts for the `verify` mode that are missing from FR-016–FR-021? (e.g., "verify MUST be non-destructive" appears in spec prose but not in the FR list) [Consistency, FR-016–FR-021]

---

## Scenario & Edge Case Coverage

- [ ] CHK032 — Are acceptance scenarios defined for `hi promote derive` and `hi promote combine` (the artifact promotion commands) comparable to those for `hi init` and `hi ingest`? [Coverage, Gap]
- [ ] CHK033 — Are acceptance scenarios defined for `hi validate` (both pass and fail cases)? [Coverage, Gap]
- [ ] CHK034 — Is the scenario of concurrent modification (two agents operating on the same topic simultaneously) addressed or explicitly excluded? [Edge Case, Gap]
- [ ] CHK035 — Are requirements defined for the `--force` flag behavior when it would overwrite an artifact that has downstream dependents (e.g., overwriting a structured artifact that a computable artifact was derived from)? [Edge Case, FR-020]
- [ ] CHK036 — Is the many-to-many artifact relationship (one L1 → many L2, many L2 → one L3) reflected in the acceptance scenarios, or only described in prose? [Completeness, Spec §Overview]
- [ ] CHK037 — Are requirements defined for what happens when `hi list` is run in a directory with no `tracking.yaml`? [Edge Case, FR-003]

---

## Non-Functional Requirements

- [ ] CHK038 — Is "Python 3.13+" in NFR-001 the minimum required version or the exact required version? If minimum, what is the upper bound? [Clarity, NFR-001]
- [ ] CHK039 — Are test coverage requirements quantified (e.g., % coverage threshold) or only stated as "all commands must have tests"? [Measurability, NFR-002]
- [ ] CHK040 — Is there an NFR for response time / performance of `hi` CLI commands, or are latency expectations undefined? [Gap]
- [ ] CHK041 — Is there an NFR for `tracking.yaml` file size or performance at scale (e.g., 100+ topics, 1000+ sources)? [Gap]
- [ ] CHK042 — Are security requirements defined for the CLI (e.g., no PHI in tracking.yaml, no secrets in plan artifacts)? The assumptions section mentions PHI exclusion — is this an NFR or only an assumption? [Clarity, Spec §Assumptions]

---

## Consistency Between Spec and Implementation

- [ ] CHK043 — Does the CLI commands table in the spec match the current implemented command interface (including the `hi status show` subcommand change)? [Consistency, Spec §CLI Commands]
- [ ] CHK044 — Are the stage names used in `tracking.yaml` (`initialized`, `l1-discovery`, `l2-semi-structured`, `l3-computable`) documented in the spec, or only present in code? [Completeness, Gap]
- [ ] CHK045 — Is there a spec section describing how stage transitions are computed (i.e., what criteria advance a topic from `initialized` → `l1-discovery` → etc.)? [Completeness, Gap]

---

## Dependencies & Assumptions

- [ ] CHK046 — Is the assumption "SHA-256 via Python `hashlib` — no external tools required" validated against the NFR for Python version compatibility? [Assumption, NFR-001]
- [ ] CHK047 — Is the dependency on `ruamel.yaml` (rather than the stdlib `yaml`) justified in the spec or plan? Is its behavior difference from PyYAML relevant to any FR? [Assumption, NFR-001]
- [ ] CHK048 — Are the optional tool dependencies (`pdftotext`, `pandoc`) and their graceful degradation behavior specified consistently across FR-006 and NFR-002? [Consistency, FR-006, NFR-002]
- [ ] CHK049 — Is the assumption "all clinical content stays inside the repo; no PHI" validated — i.e., does the spec define any enforcement mechanism (e.g., `.gitignore` patterns, `hi validate` PHI checks)? [Assumption, Gap]

## Notes

- Items marked `[Gap]` indicate requirements not currently present in the spec — review whether they should be added or explicitly excluded.
- Items marked `[Ambiguity]` flag language that could be interpreted differently by different implementors.
- Items marked `[Consistency]` flag potential conflicts between spec sections or between spec and implementation.
- Check items off as completed: `- [x]`
