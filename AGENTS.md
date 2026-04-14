# reason-skills-2 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-14

## Active Technologies
- Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx` (async-capable HTTP for URL download + PubMed API calls), `requests` (fallback for simple GET), `lxml` or `xmltodict` (PubMed XML parsing) (003-rh-inf-discovery)
- File system (`sources/`, `topics/<name>/process/plans/`, `tracking.yaml`, `RESEARCH.md`) (003-rh-inf-discovery)
- Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx >= 0.27`, `markdownify >= 0.13`, Python stdlib `html.parser`, external tools `pdftotext` and `pandoc` when available (004-rh-inf-ingest)
- File system (`sources/`, `sources/normalized/`, `topics/<name>/process/`, `tracking.yaml`) (004-rh-inf-ingest)
- Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, existing `promote`/`validate` command stack, LLM provider abstraction in `src/hi/commands/promote.py` (005-rh-inf-extract)
- File system (`topics/<topic>/process/plans/`, `topics/<topic>/structured/`, `topics/<topic>/process/concepts.yaml`, `sources/normalized/`, `tracking.yaml`) (005-rh-inf-extract)
- File system only for reads (`topics/<topic>/process/plans/`, (007-rh-inf-verify)
- File system reads only (`tracking.yaml`, `topics/<topic>/...`, (008-rh-inf-status)

- Bash 3.2+ (portable macOS/Linux) + `yq` (Go binary), `jq`, `curl`, `bash 3.2+` — same as existing `rh-skills` CLI stack. Optional: `pdftotext` (poppler), `pandoc` for binary file extraction. (002-rh-agent-skills)

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
- 008-rh-inf-status: Added Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, existing
- 007-rh-inf-verify: Added Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, existing
- 006-rh-inf-formalize: Added Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, existing


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
