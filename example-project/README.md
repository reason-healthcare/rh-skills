# Example Project

This directory is a reference **target repository** using the current RH Skills
framework layout. It shows what a clinical team repo looks like after running
`rh-skills init diabetes-screening` and then adding one source, two structured
artifacts, and one computable artifact.

## What is included

```text
example-project/
├── sources/
│   └── ada-guidelines-2024.md
├── tracking.yaml
└── topics/
    └── diabetes-screening/
        ├── TOPIC.md
        ├── structured/
        │   ├── screening-criteria.yaml
        │   └── risk-factors.yaml
        ├── computable/
        │   └── diabetes-screening-computable.yaml
        └── process/
            ├── research.md
            ├── conflicts.md
            ├── contracts/
            │   └── screening-eligibility.yaml
            ├── checklists/
            │   └── clinical-review.md
            ├── fixtures/
            │   └── screening-eligibility.yaml
            └── plans/
                └── tasks.md
```

## How the sample aligns to the framework

- `sources/` holds raw L1 inputs shared across topics
- `topics/<name>/structured/` holds L2 semi-structured YAML artifacts that match
  `schemas/l2-schema.yaml`
- `topics/<name>/computable/` holds L3 computable YAML artifacts that match
  `schemas/l3-schema.yaml`
- `topics/<name>/process/` holds supporting workflow assets such as research,
  contracts, checklists, fixtures, and task lists
- `tracking.yaml` records the repo-level source/topic inventory plus provenance
  links for structured and computable artifacts

## Sample topic

`topics/diabetes-screening/` demonstrates a small, internally consistent topic:

- one ingested source: `ada-guidelines-2024`
- two structured artifacts:
  - `screening-criteria`
  - `risk-factors`
- one computable artifact:
  - `diabetes-screening-computable`

The contract and fixture files are examples of process assets used to review and
exercise the sample computable artifact; they are not additional schema
definitions for `rh-skills validate`.

## Using the example

From the framework repository root, you can inspect the example artifacts
directly or run validation commands against the sample repo by pointing the
`rh-skills` CLI at `example-project`:

```bash
export RH_REPO_ROOT="$PWD/example-project"
export RH_TOPICS_ROOT="$RH_REPO_ROOT/topics"
export RH_TRACKING_FILE="$RH_REPO_ROOT/tracking.yaml"
export RH_SOURCES_ROOT="$RH_REPO_ROOT/sources"

uv run rh-skills validate diabetes-screening screening-criteria
uv run rh-skills validate diabetes-screening risk-factors
uv run rh-skills validate diabetes-screening diabetes-screening-computable
```

Agent-native skill bundles are built from the framework repository's curated
skill library and then installed into a target repo separately. This example is
focused on the clinical topic/project layout rather than on checked-in installed
agent bundles.
