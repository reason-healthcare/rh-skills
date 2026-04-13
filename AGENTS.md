# reason-skills-2 Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-04

## Active Technologies
- Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx` (async-capable HTTP for URL download + PubMed API calls), `requests` (fallback for simple GET), `lxml` or `xmltodict` (PubMed XML parsing) (003-rh-inf-discovery)
- File system (`sources/`, `topics/<name>/process/plans/`, `tracking.yaml`, `RESEARCH.md`) (003-rh-inf-discovery)

- Bash 3.2+ (portable macOS/Linux) + `yq` (Go binary), `jq`, `curl`, `bash 3.2+` — same as existing `rh-skills` CLI stack. Optional: `pdftotext` (poppler), `pandoc` for binary file extraction. (002-hi-agent-skills)

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
- 003-rh-inf-discovery: Added Python 3.13+ (existing `rh-skills` CLI stack) + `click >= 8.0`, `ruamel.yaml >= 0.18`, `httpx` (async-capable HTTP for URL download + PubMed API calls), `requests` (fallback for simple GET), `lxml` or `xmltodict` (PubMed XML parsing)

- 002-hi-agent-skills: Added Bash 3.2+ (portable macOS/Linux) + `yq` (Go binary), `jq`, `curl`, `bash 3.2+` — same as existing `rh-skills` CLI stack. Optional: `pdftotext` (poppler), `pandoc` for binary file extraction.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
