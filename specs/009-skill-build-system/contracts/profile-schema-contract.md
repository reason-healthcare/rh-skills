# Contract: Platform Profile Schema

## Purpose

Define the declarative contract for describing one distribution target.

## Profile Responsibilities

Each platform profile must declare enough information for the build workflow to:

1. identify the target platform
2. decide where generated bundles should be written
3. determine how canonical metadata and sections are transformed
4. define validation rules for generated bundles
5. define CI installability checks required before release readiness

## Required Fields

- platform identifier
- output path pattern
- frontmatter handling policy
- validation rule set

## Optional Fields

- preamble source
- suffix source
- metadata field mapping
- omitted sections
- installability check configuration

## Validation Rules

- profiles must be independently loadable
- conflicting output destinations are invalid
- missing referenced supporting files are invalid
- unsupported optional fields produce warnings, not silent behavior changes

## Extensibility Contract

Adding a new target should normally require only a new profile file and any
referenced supporting content, not a core build-workflow rewrite.
