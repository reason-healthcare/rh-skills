# reason-skills-2 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-22

## Active Technologies
- Python 3.13+ (click 8.3, ruamel.yaml 0.19) + click, ruamel.yaml, pathlib (stdlib) (010-l2-artifact-catalog)
- YAML files on filesystem under `topics/<topic>/structured/` (010-l2-artifact-catalog)
- Python 3.13+ + Click 8.0+, ruamel.yaml 0.18+, json (stdlib, for FHIR JSON output) (011-formalize-strategies)
- File-based — FHIR JSON to `topics/<topic>/computable/`, FHIR packages to `topics/<topic>/package/` (011-formalize-strategies)
- Python 3.13 + click + ruamel.yaml (existing stack) + existing (`httpx`, `ruamel.yaml`, `click`); external runtime: CQFramework `cql-to-elm` JAR (optional, path-configured); AHRQ CQL Testing Framework (optional, for `cql test`) (014-rh-inf-cql-skill)
- Files — `.cql` in `topics/<topic>/computable/`; ELM JSON in same dir; review reports in `topics/<topic>/process/reviews/`; test plans in `topics/<topic>/process/test-plans/`; test fixtures in `tests/cql/<library-name>/` (014-rh-inf-cql-skill)

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
- 014-rh-inf-cql-skill: Added Python 3.13 + click + ruamel.yaml (existing stack) + existing (`httpx`, `ruamel.yaml`, `click`); external runtime: CQFramework `cql-to-elm` JAR (optional, path-configured); AHRQ CQL Testing Framework (optional, for `cql test`)
- 011-formalize-strategies: Added Python 3.13+ + Click 8.0+, ruamel.yaml 0.18+, json (stdlib, for FHIR JSON output)
- 010-l2-artifact-catalog: Added Python 3.13+ (click 8.3, ruamel.yaml 0.19) + click, ruamel.yaml, pathlib (stdlib)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
