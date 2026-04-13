# Feature Specification: HI Skills Build System

**Feature Branch**: `009-skill-build-system`
**Created**: 2026-04-04
**Status**: Draft

## Overview

The RH Skills supports two usage modes:

1. **CLI-first** — users call `rh-skills` commands directly
2. **Agent-native** — users interact with an AI agent (Copilot, Claude, Gemini, etc.) which reads RH skills and calls `rh-skills` commands on their behalf

In both modes, the guiding principle is identical: **all deterministic work via `rh-skills` CLI, all reasoning by the agent.** The SKILL.md content does not change between modes — only the *installation format* differs per agent platform.

The build system compiles the canonical `skills/.curated/<name>/SKILL.md` files into platform-specific output formats using per-platform profiles. A single source of truth; multiple deployment targets.

---

## User Scenarios & Testing

### User Story 1 — Build all skills for a target platform (Priority: P1)

A contributor has finished implementing a skill (or updated an existing one) and wants to publish it to one or more agent platforms so clinical teams can install it.

**Why this priority**: Core value of the build system — without this, multi-platform support doesn't exist.

**Independent Test**: Running the build script for a single platform produces correctly formatted output files that can be installed in the target agent environment.

**Acceptance Scenarios**:

1. **Given** canonical skills in `skills/.curated/`, **When** `scripts/build-skills.sh --platform copilot` runs, **Then** formatted output is written to `dist/copilot/<name>/SKILL.md` for each curated skill, passing all platform validation rules.
2. **Given** canonical skills in `skills/.curated/`, **When** `scripts/build-skills.sh --platform claude` runs, **Then** formatted output is written to `dist/claude/<name>.md` with frontmatter stripped and Claude-compatible structure applied.
3. **Given** `scripts/build-skills.sh --all` runs, **Then** all configured platforms are built in sequence; a summary reports skill count and any per-platform warnings.
4. **Given** a canonical SKILL.md has an unfilled `<placeholder>`, **When** the build runs, **Then** the build fails with a clear error identifying the skill and the placeholder.

---

### User Story 2 — Define a platform profile (Priority: P2)

A contributor adds support for a new agent platform by creating a profile that describes how canonical SKILL.md files should be transformed for that platform.

**Why this priority**: Profiles are what make the build system extensible — adding a platform must not require touching the build script itself.

**Independent Test**: A new profile YAML file alone (no script changes) is sufficient to produce valid output for that platform when the build runs.

**Acceptance Scenarios**:

1. **Given** a new profile at `skills/_profiles/<platform>.yaml`, **When** `scripts/build-skills.sh --platform <platform>` runs, **Then** the build reads the profile and produces output without any script modification.
2. **Given** a profile specifying `frontmatter: strip`, **When** the build runs, **Then** YAML frontmatter is removed from all output files for that platform.
3. **Given** a profile specifying `frontmatter: keep`, **When** the build runs, **Then** YAML frontmatter is preserved verbatim in output files.
4. **Given** a profile specifying a `preamble` template, **When** the build runs, **Then** the preamble is prepended to each output file with `{{skill_name}}` and `{{description}}` substituted.
5. **Given** a profile specifying `output_path_pattern`, **When** the build runs, **Then** output files are written to paths matching the pattern.

---

### User Story 3 — Validate build output (Priority: P2)

A contributor wants confidence that the build output is correctly formed before distributing it.

**Why this priority**: Prevents broken skills reaching clinical teams.

**Independent Test**: Running the validate flag on build output produces a per-skill, per-platform pass/fail report.

**Acceptance Scenarios**:

1. **Given** `scripts/build-skills.sh --all --validate`, **When** the build runs, **Then** each output file is checked against its platform profile's validation rules; failures are reported with skill name, platform, and reason.
2. **Given** a Claude output file missing a required `## Usage` section, **When** validate runs, **Then** the build exits non-zero with a clear diagnostic.
3. **Given** all output files pass validation, **When** validate runs, **Then** the build exits 0 and prints a summary: `N skills × M platforms — all valid`.

---

### User Story 4 — Dry-run mode (Priority: P3)

A contributor wants to preview what the build would produce without writing any files.

**Acceptance Scenarios**:

1. **Given** `scripts/build-skills.sh --all --dry-run`, **When** the build runs, **Then** no files are written; the script prints each output path and a diff-style preview of transformations applied.
2. **Given** `--dry-run` is active, **When** the build would fail (e.g., unfilled placeholder), **Then** the error is reported the same as a real build.

---

### Edge Cases

- A curated skill directory exists but contains no `SKILL.md` — skip with a warning, do not fail the build.
- A platform profile references a `preamble_file` that does not exist — fail with a clear error identifying the missing file.
- Two profiles produce output to the same path — fail at profile load time with a conflict error.
- A profile field is unrecognized — emit a warning and continue (forward-compatible).
- `skills/.curated/` contains zero skills — build succeeds with an informational message; no output written.
- `--platform` is specified but no matching profile exists — fail immediately with the list of known platforms.

---

## Requirements

### Functional Requirements

**Build Script**

- **FR-001**: A shell script at `scripts/build-skills.sh` MUST compile all skills in `skills/.curated/` into platform-specific outputs using the profile for the specified platform(s).
- **FR-002**: The script MUST support `--platform <name>` (single platform) and `--all` (all configured platforms).
- **FR-003**: The script MUST support `--dry-run` to preview output paths and transformations without writing files.
- **FR-004**: The script MUST support `--validate` to check output files against platform profile validation rules after building.
- **FR-005**: The script MUST exit 0 on success, exit 1 on any build or validation error, and print a per-skill summary.
- **FR-006**: The script MUST detect unfilled `<placeholder>` tokens in any canonical SKILL.md and fail with a diagnostic identifying the skill name and the placeholder text before producing any output.
- **FR-007**: The script MUST be compatible with bash 3.2+ (macOS default) and require no dependencies beyond standard POSIX utilities and `yq` (already required by the framework).

**Platform Profiles**

- **FR-008**: Platform profiles MUST be YAML files at `skills/_profiles/<platform>.yaml`.
- **FR-009**: Each profile MUST declare: `platform` (name), `output_dir` (base output path), `output_path_pattern` (per-skill file path with `{{skill_name}}` interpolation), `frontmatter` (`keep` | `strip` | `transform`), and `validation_rules[]`.
- **FR-010**: Profiles MAY declare: `preamble` (inline text), `preamble_file` (path to a Markdown file), `suffix` (appended text), `field_map` (frontmatter field renames), `omit_sections[]` (SKILL.md section headings to exclude from output).
- **FR-011**: The build script MUST apply profiles declaratively — adding a new profile MUST produce output for the new platform with no script changes.
- **FR-012**: Unknown profile fields MUST produce a warning, not a build failure (forward-compatible).

**Bundled Profiles**

- **FR-013**: A profile for **GitHub Copilot** (`copilot.yaml`) MUST be included. Output: `dist/copilot/<skill-name>/SKILL.md`. Frontmatter: keep. This is effectively a passthrough (canonical format = Copilot format).
- **FR-014**: A profile for **Claude Code** (`claude.yaml`) MUST be included. Output: `dist/claude/<skill-name>.md`. Frontmatter: strip (Claude reads context from file content, not YAML). Preamble: slash-command header with skill name and description.
- **FR-015**: A profile for **Gemini CLI** (`gemini.yaml`) MUST be included. Output: `dist/gemini/<skill-name>.md`. Format details derived from Gemini CLI tool conventions.
- **FR-016**: A profile for **AGENTS.md injection** (`agents-md.yaml`) MAY be included as a convenience target: concatenates all skill names and descriptions into an `AGENTS.md`-compatible block.

**Output**

- **FR-017**: All build output MUST be written under `dist/` (repo root). The `dist/` directory MUST be listed in `.gitignore` by default; contributors may opt to commit it.
- **FR-018**: The build script MUST be idempotent — running it multiple times produces identical output (no timestamps or run IDs in generated files).

### Key Entities

- **Canonical Skill**: `skills/.curated/<name>/SKILL.md` — the single source of truth for skill content.
- **Platform Profile**: `skills/_profiles/<platform>.yaml` — declares transformation rules and output format for one agent platform.
- **Build Output**: `dist/<platform>/<name>.<ext>` — platform-specific skill file ready for installation.
- **Preamble Template**: Optional Markdown prepended to each output file; supports `{{skill_name}}` and `{{description}}` interpolation.

---

## Success Criteria

- **SC-001**: A contributor can add a new agent platform by creating one profile YAML file with no changes to `build-skills.sh`.
- **SC-002**: Running `scripts/build-skills.sh --all` from a clean clone (with `uv` and `yq` installed) succeeds in under 10 seconds for six skills across three platforms.
- **SC-003**: Output files for all bundled platforms pass their respective platform's skill loading validation (Copilot, Claude Code, Gemini CLI).
- **SC-004**: `--dry-run` mode produces zero file writes while still reporting all errors a real build would report.
- **SC-005**: The build system is documented in `DEVELOPER.md` such that a new contributor can build and distribute skills for any supported platform without reading the script source.

---

## Assumptions

- `yq` (Go binary, v4+) and bash 3.2+ are available in all contributor environments — consistent with existing framework tooling.
- The canonical SKILL.md format is stable (defined in 002); the build system transforms it, never modifies the source.
- `dist/` is gitignored by default; teams that want to version-control generated outputs can remove it from `.gitignore`.
- Gemini CLI skill format will be derived from Gemini CLI documentation at implementation time; profile fields are sufficient to accommodate any discovered nuances.
- Claude Code reads skill context from plain Markdown files in `.claude/commands/`; frontmatter stripping plus a slash-command preamble is sufficient for compatibility.
- The build script is a developer tool only — it is never invoked by `rh-skills` CLI or called by end users.
- Platform profiles for 003–008 skills (once implemented) will be validated as part of the build; the build system does not need to know skill semantics.

