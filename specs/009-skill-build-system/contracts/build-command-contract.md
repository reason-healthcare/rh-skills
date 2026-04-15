# Contract: Build Command

## Purpose

Define the contributor-facing contract for generating RH skill distribution bundles.

## Invocation Surface

`scripts/build-skills.sh`

## Required Modes

- build one platform
- build all bundled platforms
- dry-run preview
- validation after build

## Required Inputs

- a curated skill library as the canonical source
- one selected platform or an all-platforms mode
- optional validation flag
- optional dry-run flag

## Required Outputs

- generated bundles under the configured output tree for each selected platform
- a contributor-facing build summary listing successes, failures, skips, and warnings
- a non-zero exit on blocking build, validation, or installability failure

## Failure Contract

- unresolved placeholders stop the build before distribution output is considered ready
- missing or conflicting profile definitions fail clearly before ambiguous output is written
- validation and installability failures identify both the affected skill and platform

## Determinism Contract

- unchanged inputs must yield unchanged output paths and content
- dry-run mode reports the same blocking errors as a real build without writing files
