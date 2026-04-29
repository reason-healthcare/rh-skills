# Getting Started with RH Skills

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Installation

```bash
uv tool install rh-skills
rh-skills --help
```

## Choose Your Workflow

There are two ways to use RH Skills — pick the one that fits your workflow:

| | [Agent-native](#agent-native) | [CLI-first](#cli-first) |
|-|-------------------------------|------------------------|
| **Interface** | Natural language with your AI agent | `rh-skills` terminal commands |
| **Best for** | Clinical teams, conversational UX | Full control, CI/CD, scripting |
| **LLM** | Your existing agent platform | Any provider you configure |

Both modes produce identical outputs through the same `rh-skills` CLI. You can
switch between them at any point in a workflow.

## Initialize a Topic

A "topic" is a clinical knowledge domain (e.g., "diabetes-screening", "sepsis-detection").

**`rh-inf-ingest` will propose and create the topic** after normalizing your sources.

If you prefer to initialize manually (e.g., you already know the topic name):

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
    fixtures/        ← test fixtures for skill testing
    notes.md         ← open questions, decisions, source conflicts, notes (human-maintained)
```

A `tracking.yaml` at the repo root records the topic's metadata and lifecycle events.

## The Lifecycle

RH Skills guides clinical knowledge through three artifact levels:

```
L1 (sources)  →  L2 (structured)  →  L3 (computable)
```

Each transition is guided by an **agent skill** — a SKILL.md prompt file invoked by an LLM agent — that follows a `plan → implement → verify` pattern. See [WORKFLOW.md](WORKFLOW.md) for the full lifecycle diagram.

---

## Agent-native

Skills must be installed into your agent platform before use. Run once after
install or upgrade:

```bash
# Install skills for your platform (copilot, claude, gemini)
rh-skills skills init

# Re-install after upgrading rh-skills
rh-skills skills update
```

Then work through the lifecycle by invoking skills in your agent. The agent
reads the skill instructions and calls `rh-skills` commands on your behalf.

### Path A: Discover → Ingest → Extract → Formalize

Use this path when starting from scratch or guided research.

### 1. Discover sources

Invoke the discovery skill in your agent:

```
# Claude Code
/rh-inf-discovery plan --domain diabetes-ccm

# GitHub Copilot — natural language
run rh-inf-discovery plan --domain diabetes-ccm
```

The agent runs an interactive research session and saves `discovery-plan.yaml` and `discovery-readout.md` to the repo root. Use `--domain` when you want to specify the domain explicitly; otherwise, the skill may infer it during discovery plan mode. Verify and hand off:

```
/rh-inf-discovery verify
```

### 2. Ingest and normalize

```
/rh-inf-ingest plan
/rh-inf-ingest implement
```

Ingest plan mode checks tool availability and identifies unregistered files.
The underlying file inventory is the same logic exposed by
`rh-skills ingest list-manual`, but `rh-skills ingest plan` is the canonical
entrypoint for that pre-flight summary.
Implement mode then registers each untracked file individually using the
per-file `rh-skills ingest implement sources/<file>` commands surfaced by
that pre-flight summary,
normalizes everything to Markdown,
then **proposes a topic name** based on the source content, asks for confirmation,
and calls `rh-skills init <topic>` — no separate init step required.

---

### Path B: Bring Your Own Sources

Use this path when you already have files you want to process (no discovery needed).

1. Place your files in `sources/`
2. Run ingest plan first, then implement — no topic init required:
  ```
  /rh-inf-ingest plan
  /rh-inf-ingest implement
  ```
   The agent normalizes your sources, proposes a topic name, asks for confirmation,
   and initializes the topic before proceeding with classify and annotate.

---

### 3. Extract structured artifacts (L2)

```
/rh-inf-extract plan diabetes-screening
```

The agent proposes L2 artifacts in a review packet
(`topics/diabetes-screening/process/plans/extract-plan.md`). Edit and approve
the plan — including any `candidate_codes[]` for terminology artifacts — then
implement:

```
/rh-inf-extract implement diabetes-screening
```

### 4. Formalize to a computable artifact (L3)

```
/rh-inf-formalize plan diabetes-screening
```

Review the formalize plan, then implement:

```
/rh-inf-formalize implement diabetes-screening
```

### 5. Verify at any stage

```
/rh-inf-extract verify diabetes-screening
/rh-inf-formalize verify diabetes-screening
```

---

## CLI-first

Run every step yourself. An LLM is required for the reasoning steps (plan and
implement modes); configure your provider via `.rh-skills.toml` or environment
variables:

```toml
# .rh-skills.toml (local) or ~/.rh-skills.toml (global)
[llm]
provider = "anthropic"   # ollama | anthropic | openai
model    = "claude-3-5-sonnet-20241022"
api_key  = "sk-ant-..."
```

```bash
# or via environment variables
export LLM_PROVIDER=anthropic
export ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
export ANTHROPIC_API_KEY=sk-ant-...
```

See [Usage Modes](USAGE_MODES.md) for all provider options.

### 1. Discover and ingest source materials

```bash
# Option A: Discovery-guided
# Discovery runs via agent skill (domain required):
#   /rh-inf-discovery plan --domain diabetes-ccm
#   /rh-inf-discovery verify

# Download open-access sources from discovery-plan entries
rh-skills source download --url <url> --name <name>

# Optional: append search results only when adding to an existing topic plan
rh-skills search pubmed --query "<terms>" --append-to-plan <topic>

# Register manual sources detected in sources/
rh-skills ingest list-manual [<topic>]
rh-skills ingest implement sources/<file> [--topic <topic>]

# Option B: Bring your own sources
# Place files in sources/, then:
rh-skills ingest list-manual [<topic>]
rh-skills ingest implement sources/<file> [--topic <topic>]
```

### 2. Derive structured artifacts (L2)

```bash
rh-skills promote derive diabetes-screening --source ada-guidelines --name screening-criteria
rh-skills promote derive diabetes-screening --source ada-guidelines --name risk-factors
```

### 3. Validate the L2 artifacts

```bash
rh-skills validate diabetes-screening screening-criteria
rh-skills validate diabetes-screening risk-factors
```

### 4. Converge to a computable artifact (L3)

```bash
rh-skills promote combine diabetes-screening \
  screening-criteria risk-factors \
  diabetes-screening-pathway
```

### 5. Validate the L3 artifact

```bash
rh-skills validate diabetes-screening diabetes-screening-pathway
```

---

## Check Status Anytime

```bash
rh-skills status show diabetes-screening          # basic status
rh-skills status progress diabetes-screening      # detailed progress with % complete
rh-skills status next-steps diabetes-screening    # single most important next action
rh-skills status check-changes diabetes-screening # detect changed source files
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

## List All Topics

```bash
rh-skills list
```

## Reference

- [WORKFLOW.md](WORKFLOW.md) — full lifecycle diagram and many-to-many artifact relationships
- [COMMANDS.md](COMMANDS.md) — complete CLI command reference
- [Usage Modes](USAGE_MODES.md) — full comparison, LLM configuration, and platform support details
