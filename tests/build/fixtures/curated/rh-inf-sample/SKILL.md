---
name: "rh-inf-sample"
description: "Sample RH informatics skill used for bundle generation tests. Modes: plan · implement · verify."
compatibility: "rh-skills-framework >= 0.1.0"
version: "1.0.0"
modes:
  - plan
  - implement
  - verify
context_files:
  - reference.md
  - examples/plan.md
  - examples/output.md
metadata:
  author: "RH Tests"
  source: "skills/.curated/rh-inf-sample/SKILL.md"
  lifecycle_stage: "l1-discovery"
  reads_from:
    - tracking.yaml
  writes_via_cli:
    - rh-skills status show
---

# RH INF Sample

## Overview

This fixture skill exists only to exercise the build system. It has enough
frontmatter, body sections, and companion files to verify platform-specific
transforms without depending on the real curated library.

## User Input

```text
$ARGUMENTS
```

The fixture accepts any text because tests only care about bundle generation.

## Pre-Execution Checks

1. Confirm the sample topic exists.
2. Confirm a sample plan exists.

## Mode: `plan`

Plan mode writes a sample plan.

## Mode: `implement`

Implement mode calls deterministic CLI commands.

## Mode: `verify`

Verify mode is read-only.

