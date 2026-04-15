# Getting Started with the RH Skills

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Installation

```bash
uv tool install rh-skills
rh-skills --help
```

## Initialize a Topic

A "topic" is a clinical knowledge domain (e.g., "diabetes-screening", "sepsis-detection").

```bash
rh-skills init diabetes-screening --title "Diabetes Screening" --author "Jane Smith"
```

This creates:

```
topics/diabetes-screening/
  structured/        ← L2 artifacts live here (prominent)
  computable/        ← L3 artifacts live here (prominent)
  process/
    plans/           ← discovery, ingest, extract, formalize plans
    contracts/       ← YAML validation contracts
    checklists/      ← clinical review checklists
    fixtures/        ← test fixtures for skill testing
    notes.md         ← open questions, decisions, source conflicts, notes (human-maintained)
```

A `tracking.yaml` at the repo root records the topic's metadata and lifecycle events.

## The Lifecycle

The RH Skills guides clinical knowledge through three artifact levels:

```
L1 (sources)  →  L2 (structured)  →  L3 (computable)
```

Each transition is guided by an **agent skill** — a SKILL.md prompt file invoked by an LLM agent — that follows a `plan → implement → verify` pattern. See [WORKFLOW.md](WORKFLOW.md) for the full lifecycle diagram.

## Your First Topic Walkthrough

### Step 1: Discover sources

```
rh-inf-discovery plan diabetes-screening
```

The agent generates `topics/diabetes-screening/process/plans/discovery-plan.md` — a list of suggested source types (guidelines, terminology systems, research papers). Review and edit the plan.

```
rh-inf-discovery implement diabetes-screening
```

Converts the approved plan into ingest tasks.

### Step 2: Ingest raw sources

```
rh-inf-ingest plan diabetes-screening
```

Displays the ingest plan for review.

```
rh-inf-ingest implement diabetes-screening
```

Registers each source file with its SHA-256 checksum in `tracking.yaml`.

### Step 3: Extract structured artifacts (L2)

```
rh-inf-extract plan diabetes-screening
```

The agent proposes candidate structured artifact names (e.g., "screening-criteria", "diagnostic-thresholds"). Review the plan at `topics/diabetes-screening/process/plans/extract-plan.md`.

```
rh-inf-extract implement diabetes-screening
```

Calls `rh-skills promote derive` for each planned artifact, producing YAML files in `topics/diabetes-screening/structured/`.

### Step 4: Formalize into computable artifact (L3)

```
rh-inf-formalize plan diabetes-screening
```

The agent identifies which structured artifacts to combine and drafts the computable artifact's sections.

```
rh-inf-formalize implement diabetes-screening
```

Calls `rh-skills promote combine`, producing a FHIR-compatible YAML file in `topics/diabetes-screening/computable/`.

## Check Status Anytime

```bash
rh-skills status show diabetes-screening          # basic status
rh-skills status progress diabetes-screening      # detailed progress with % complete
rh-skills status next-steps diabetes-screening    # single most important next action
rh-skills status check-changes diabetes-screening # detect changed source files
```

## Validate Artifacts

```bash
rh-skills validate diabetes-screening screening-criteria   # validate L2 artifact
rh-skills validate diabetes-screening diabetes-pathway     # validate L3 artifact
```

## Track Tasks

```bash
rh-skills tasks list diabetes-screening           # list per-topic tasks
rh-skills tasks add diabetes-screening "Review screening criteria with cardiologist"
rh-skills tasks complete diabetes-screening 1
```

## Test Skills

```bash
rh-skills test diabetes-screening rh-inf-extract      # run skill against fixtures
```

## Reference

- [WORKFLOW.md](WORKFLOW.md) — full lifecycle diagram and many-to-many artifact relationships
- [COMMANDS.md](COMMANDS.md) — complete CLI command reference
