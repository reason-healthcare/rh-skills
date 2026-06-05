# Example Project

This directory is a compact reference **target repository** using the current
RH Skills framework layout. It shows what a clinical team repo looks like after
running `rh-skills init diabetes-screening` and then adding one source plus a
small set of CLI-generated artifacts.

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
        │   ├── care-pathway/
        │   │   ├── care-pathway.yaml
        │   │   └── care-pathway-report.md
        │   ├── decision-table/
        │   │   ├── decision-table.yaml
        │   │   └── decision-table-report.md
        │   └── concepts/
        │       ├── concepts.yaml
        │       └── concepts-report.md
        ├── computable/
        │   ├── ActivityDefinition-recommend-a1c.json
        │   ├── ActivityDefinition-recommend-fasting-glucose.json
        │   ├── ActivityDefinition-recommend-follow-up.json
        │   ├── DiabetesScreeningLibrary.cql
        │   ├── Library-diabetes-screening-library.json
        │   ├── PlanDefinition-diabetes-screening-care-pathway.json
        │   ├── PlanDefinition-diabetes-screening-follow-up.json
        │   ├── PlanDefinition-diabetes-screening-order-set.json
        │   ├── ValueSet-fasting-plasma-glucose.json
        │   ├── ValueSet-hemoglobin-a1c.json
        │   ├── ValueSet-hypertension.json
        │   └── ValueSet-obesity.json
        └── process/
            ├── formalize-config.yaml
            ├── research.md
            ├── conflicts.md
            ├── fixtures/
            │   └── screening-eligibility.yaml
            └── plans/
                ├── extract-plan-readout.md
                ├── extract-plan.yaml
                ├── concepts-review-meta.yaml
                ├── concepts/
                │   ├── fasting-plasma-glucose.csv
                │   ├── hemoglobin-a1c.csv
                │   ├── hypertension.csv
                │   └── obesity.csv
                └── tasks.md
```

## How the sample aligns to the framework

- `sources/` holds raw L1 inputs shared across topics
- `topics/<name>/structured/` holds L2 semi-structured YAML artifacts that match
  `schemas/l2-schema.yaml`
- `topics/<name>/computable/` holds generated L3 FHIR JSON artifacts and any CQL
  scaffolds that match `schemas/l3-schema.yaml`
- `topics/<name>/process/` holds supporting workflow assets such as research,
  conflicts, fixtures, plans, and task lists
- `tracking.yaml` records the repo-level source/topic inventory plus provenance
  links for structured and computable artifacts

## Sample topic

`topics/diabetes-screening/` demonstrates a small, internally consistent topic:

1. one ingested source: `ada-guidelines-2024`
2. three structured artifacts:
 - `care-pathway`
 - `decision-table`
 - `concepts`
3. generated computable resources:
 - `PlanDefinition-diabetes-screening-care-pathway`
 - `PlanDefinition-diabetes-screening-order-set`
 - `PlanDefinition-diabetes-screening-follow-up`
 - `Library-diabetes-screening-library`
 - `ActivityDefinition-recommend-fasting-glucose`
 - `ActivityDefinition-recommend-a1c`
 - `ActivityDefinition-recommend-follow-up`
 - `ValueSet-*`
 - `DiabetesScreeningLibrary.cql`
 - `process/package-workspace/output/reason.diabetes-screening-0.1.0.tgz`

The sample is intentionally partial: it keeps just enough files to show the
project structure while still demonstrating generated ValueSets, a CQL-backed
screening order set, a follow-up plan definition, and a packaged output archive.

## Using the example

From the framework repository root, you can inspect the example artifacts
directly or run validation commands against the sample repo by pointing the
`rh-skills` CLI at `example-project`:

```bash
export RH_REPO_ROOT="$PWD/example-project"
export RH_TOPICS_ROOT="$RH_REPO_ROOT/topics"
export RH_TRACKING_FILE="$RH_REPO_ROOT/tracking.yaml"
export RH_SOURCES_ROOT="$RH_REPO_ROOT/sources"

uv run rh-skills validate diabetes-screening care-pathway
uv run rh-skills validate diabetes-screening decision-table
uv run rh-skills validate diabetes-screening concepts
```

Agent-native skill bundles are built from the framework repository's curated
skill library and then installed into a target repo separately. This example is
focused on the clinical topic/project layout rather than on checked-in installed
agent bundles.
