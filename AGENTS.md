# reason-skills-2 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-15

## Active Technologies

- Bash 3.2+ (portable macOS/Linux) + `yq`, `jq`, `curl`; same stack used for curated skill authoring and distribution tooling (002-rh-agent-skills)
- Python 3.13+ + `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx`, `requests`, `lxml` or `xmltodict` for discovery/search flows (003-rh-inf-discovery)
- Python 3.13+ + `click >= 8.0`, `ruamel.yaml >= 0.18`, `markdownify`, stdlib `html.parser`, optional `pdftotext` and `pandoc` for ingest normalization (004-rh-inf-ingest)
- Python 3.13+ + existing `promote` / `validate` command stack for structured and computable artifact workflows (005-rh-inf-extract, 006-rh-inf-formalize, 007-rh-inf-verify, 008-rh-inf-status)
- Bash 3.2+ for build orchestration; Python 3.13+ for fixture-driven validation + `yq` v4 and GitHub Actions for generated bundle CI checks (009-skill-build-system)

## Project Structure

```text
src/
tests/
```

## Commands

# Add commands for Bash 3.2+ (portable macOS/Linux)

## Code Style

Bash 3.2+ (portable macOS/Linux): Follow standard conventions

## Recent Changes

- 009-skill-build-system: Added deterministic curated-skill bundle generation, declarative platform profiles, and CI validation for generated distributions
- 008-rh-inf-status: Added deterministic status UX with consistent next-step guidance
- 007-rh-inf-verify: Added unified verify orchestration across lifecycle stages

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
