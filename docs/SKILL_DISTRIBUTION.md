# RH Skills Distribution

The curated RH skill library lives under `skills/.curated/`. The build system
turns that canonical source into deterministic, platform-specific bundles under
`dist/` without mutating the authored skill files.

## Prerequisites

```bash
uv sync
yq --version
```

The repository must contain one or more implemented curated skills under
`skills/.curated/`.

## Build bundles

Build one bundled platform:

```bash
scripts/build-skills.sh --platform copilot
```

Build all bundled platforms:

```bash
scripts/build-skills.sh --all
```

Each run stages output first, validates conflicts before writing, and then
publishes deterministic artifacts under `dist/`.

## Preview and validate

Preview without writing files:

```bash
scripts/build-skills.sh --all --dry-run
```

Validate staged bundles and installability rules during the same run:

```bash
scripts/build-skills.sh --all --validate
```

`--dry-run` renders the same bundles in a temporary staging area and surfaces
the same blocking issues, but it leaves `dist/` untouched.

## Bundled platform profiles

The default bundled profiles are:

| Platform | Profile | Output |
|----------|---------|--------|
| GitHub Copilot | `skills/_profiles/copilot.yaml` | `dist/copilot/<skill>/` |
| Claude Code | `skills/_profiles/claude.yaml` | `dist/claude/<skill>/` |
| Gemini CLI | `skills/_profiles/gemini.yaml` | `dist/gemini/<skill>/` |

An optional aggregate target is available at
`skills/_profiles/agents-md.yaml`, which writes `dist/agents-md/AGENTS.md`.

## Author a new profile

Normal onboarding should require only a new profile file plus any referenced
support content:

```yaml
platform: custom
bundled: false
bundle_mode: per_skill
output_path_pattern: dist/custom/{skill_name}
frontmatter_policy: keep
preamble:
  inline: |
    <!-- Custom bundle -->
validation_rules:
  - skill_entry_exists
installability_checks:
  - file_nonempty
```

Supported top-level profile fields:

- `platform`
- `bundled`
- `bundle_mode`
- `output_path_pattern`
- `frontmatter_policy`
- `preamble`
- `suffix`
- `omit_sections`
- `field_map`
- `validation_rules`
- `installability_checks`

Unknown optional fields produce warnings so maintainers can spot drift instead
of silently assuming the build script understands them.

## Failure modes

The build exits non-zero before writing output when:

- no curated skills are available
- a requested profile is missing
- a profile is invalid or references missing support content
- two selected profiles would generate the same output destination
- any curated skill still contains unresolved template placeholders

Validation and installability failures also exit non-zero and include the
affected platform, skill, and rule name.

## CI and local reproduction

The GitHub Actions workflow at `.github/workflows/skill-build.yml` runs the
fixture-backed build/validation/installability suite for bundled profiles.

When CI fails, reproduce locally with:

```bash
uv run pytest tests/build/test_build_skills.py -q
```

If the failure involves a specific generated bundle, re-run the build script for
that platform with `--validate` to see the same rule-level diagnostics.

