# Data Model: RH Skills Build System

## Entity 1: Canonical Skill

Represents one authored RH skill before distribution.

**Fields**:
- `name`: canonical skill identifier
- `source_dir`: curated source directory
- `skill_file`: canonical primary content file
- `companion_files[]`: supporting reference/example files required for profile transforms
- `placeholder_status`: whether unresolved placeholders remain
- `eligibility`: `buildable | skipped | failed`

**Rules**:
- Canonical skills are the sole authored source of truth for distributed skill content.
- A skill with unresolved placeholders is not buildable.

## Entity 2: Platform Profile

Represents one declarative distribution target.

**Fields**:
- `platform`: target platform name
- `output_path_pattern`: generated bundle destination pattern
- `frontmatter_policy`: `keep | strip | transform`
- `preamble_source`: inline or file-backed preamble definition
- `suffix_source`: optional trailing content
- `omit_sections[]`: canonical sections excluded for this platform
- `field_map[]`: metadata transforms, if any
- `validation_rules[]`: structural validation rules for generated bundles
- `installability_checks[]`: smoke checks required in CI before distribution is considered ready
- `profile_status`: `valid | warning | invalid`

**Rules**:
- Profiles are independently reviewable and should not require core build logic changes in normal onboarding.
- Conflicting output destinations across profiles are invalid.

## Entity 3: Generated Skill Bundle

Represents one platform-specific distribution artifact derived from a canonical skill.

**Fields**:
- `platform`
- `skill_name`
- `source_skill`
- `output_path`
- `content_digest`
- `build_status`: `pending | built | failed`
- `validation_status`: `not_run | pass | warning | fail`
- `installability_status`: `not_run | pass | fail`

**Rules**:
- Generated bundles are derived artifacts and never become the authoritative editing surface.
- The same inputs must produce the same generated bundle content and path.

## Entity 4: Validation Finding

Represents one result from local validation or CI installability checks.

**Fields**:
- `scope`: `build | validation | installability`
- `platform`
- `skill_name`
- `severity`: `info | warning | error`
- `rule_id`
- `message`
- `evidence`: file path, section name, or command context tied to the finding

**Rules**:
- Errors block distribution readiness.
- Warnings are surfaced in summaries but do not silently mutate output.

## Entity 5: Build Summary

Represents the contributor-facing outcome of one build invocation.

**Fields**:
- `requested_platforms[]`
- `processed_skills[]`
- `built_count`
- `skipped_count`
- `warning_count`
- `error_count`
- `duration`
- `result`: `success | failure`

**Rules**:
- The summary must make it clear which skill/platform pairs succeeded, failed, or were skipped.
- Dry-run summaries must report the same blocking errors as real builds while recording zero file writes.

## Relationships

- One canonical skill can produce many generated skill bundles.
- One platform profile governs many generated skill bundles for the same target.
- One generated skill bundle can accumulate many validation findings.
- One build summary covers many canonical skill / platform profile pairings.
