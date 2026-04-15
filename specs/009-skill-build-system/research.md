# Research: RH Skills Build System

## Decision 1: Use a Bash 3.2 build entrypoint with declarative YAML profiles

- **Decision**: Implement the build entrypoint as a portable Bash 3.2 script that
  reads declarative platform profiles from `skills/_profiles/`.
- **Rationale**: The repo already targets portable shell tooling in contributor
  workflows, and the feature spec explicitly treats the build as a developer
  pipeline rather than an end-user CLI command. Bash keeps onboarding light,
  while YAML profiles prevent platform support from being encoded directly into
  the orchestration script.
- **Alternatives considered**:
  - Python-only build tool — better parsing ergonomics, but adds a second tool
    entrypoint for a feature described as a script-driven build pipeline.
  - Hard-coded per-platform shell branches — simpler for the first platform, but
    directly conflicts with the declarative extensibility goal of 009.

## Decision 2: Keep generated bundles under `dist/` and never modify curated sources

- **Decision**: Generated platform bundles live only under `dist/`, with
  canonical skills remaining in `skills/.curated/`.
- **Rationale**: This preserves one source of truth, keeps generated output
  reviewable and discardable, and supports deterministic rebuilds without
  mutating authored skill files.
- **Alternatives considered**:
  - In-place profile transforms inside curated skill directories — rejected
    because it blurs authored source content with generated distribution output.
  - Platform-specific source directories committed alongside curated skills —
    rejected because it duplicates content and increases drift risk.

## Decision 3: Represent platform differences entirely through profile contracts

- **Decision**: Profiles define output location, frontmatter behavior, preamble
  handling, omitted sections, and validation/installability rules.
- **Rationale**: This keeps the build logic generic while making platform support
  auditable and extensible. The profile is the contract; the script is the
  executor.
- **Alternatives considered**:
  - Separate transformation scripts per platform — rejected because contributor
    maintenance would scale linearly with supported platforms.
  - A single monolithic config file for all platforms — rejected because per-file
    profiles are easier to review, add, and reason about independently.

## Decision 4: Treat CI validation as structural + installability smoke checks

- **Decision**: 009 includes CI validation of generated bundles and
  platform-oriented installability smoke checks, but not full model-driven
  scenario evaluation.
- **Rationale**: This matches the clarified feature scope, captures the main
  safety value from the referenced vermonster workflow, and stays focused on
  distribution readiness rather than model-quality benchmarking.
- **Alternatives considered**:
  - No CI validation in 009 — rejected because the clarified spec explicitly
    includes CI installability as part of releasability.
  - Full scenario replay with local models / Ollama in 009 — rejected because it
    materially expands scope into evaluation infrastructure better handled by a
    follow-on feature.

## Decision 5: Use pytest for fixture-driven build verification

- **Decision**: Use pytest-based fixture tests to verify build output, profile
  behavior, placeholder detection, and conflict handling.
- **Rationale**: The repo already uses pytest as its primary validation surface.
  Reusing it keeps reporting consistent and makes it easier to assert content,
  file paths, and command exit behavior from subprocess-driven build tests.
- **Alternatives considered**:
  - Bats/shell-only tests — rejected because the repo’s active validation surface
    is pytest, and shell-only assertions would duplicate conventions already
    present in the repository.
  - Snapshot-only testing — rejected because structural assertions are easier to
    maintain when profile fields and bundle formatting evolve.

## Decision 6: Model installability checks per platform, not full platform emulation

- **Decision**: CI installability checks should verify each bundled platform’s
  expected file shape and loadability contract without standing up full external
  agent sessions.
- **Rationale**: Platform-specific smoke checks are sufficient to confirm that
  generated bundles are consumable and keep CI deterministic and affordable.
- **Alternatives considered**:
  - Full agent session replay in CI — rejected for 009 because it depends on
    provider-specific runtime behavior and crosses into scenario evaluation.
  - Pure static validation only — rejected because installability readiness is a
    clarified requirement beyond static file shape.
