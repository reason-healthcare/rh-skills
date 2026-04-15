# Quickstart

There are two ways to use RH Skills — pick the one that fits your workflow:

| | [Agent-native](#agent-native) | [CLI-first](#cli-first) |
|-|-------------------------------|------------------------|
| **Interface** | Natural language with your AI agent | `rh-skills` terminal commands |
| **Best for** | Clinical teams, conversational UX | Full control, CI/CD, scripting |
| **LLM** | Your existing agent platform | Any provider you configure |

Both modes produce identical outputs through the same `rh-skills` CLI. You can
switch between them at any point in a workflow.

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

### 1. Initialize a topic

Use `rh-skills` directly — topic init is a deterministic CLI operation:

```bash
rh-skills init diabetes-screening --title "Diabetes Screening" --author "My Team"
```

### 2. Discover sources

Invoke the discovery skill in your agent:

```
# Claude Code
/rh-inf-discovery plan diabetes-screening

# GitHub Copilot — natural language
run rh-inf-discovery plan diabetes-screening
```

Review the generated `discovery-plan.yaml`, approve sources, then run implement:

```
/rh-inf-discovery implement diabetes-screening
```

### 3. Ingest and normalize

```
/rh-inf-ingest plan diabetes-screening
```

Review the ingest plan, then implement:

```
/rh-inf-ingest implement diabetes-screening
```

### 4. Extract structured artifacts

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

### 5. Formalize to a computable artifact

```
/rh-inf-formalize plan diabetes-screening
```

Review the formalize plan, then implement:

```
/rh-inf-formalize implement diabetes-screening
```

### 6. Verify at any stage

```
/rh-inf-extract verify diabetes-screening
/rh-inf-formalize verify diabetes-screening
```

### 7. Check status

```bash
rh-skills status show diabetes-screening
rh-skills status next-steps diabetes-screening
```

---

## CLI-first

Run every step yourself. An LLM is required for the reasoning steps (plan and
implement modes); configure your provider once:

```bash
cp .env.example .env   # set LLM_PROVIDER, model, and API key
```

### 1. Initialize a topic

```bash
rh-skills init diabetes-screening --title "Diabetes Screening" --author "My Team"
```

### 2. Discover and ingest source materials

```bash
# Discovery — identify and plan sources
rh-skills discovery plan diabetes-screening
rh-skills discovery implement diabetes-screening

# Ingest — download, normalize, classify, annotate
rh-skills ingest plan diabetes-screening
rh-skills ingest implement diabetes-screening
```

### 3. Check topic status

```bash
rh-skills status show diabetes-screening
rh-skills status next-steps diabetes-screening
```

### 4. Derive structured artifacts

```bash
rh-skills promote derive diabetes-screening --source ada-guidelines --name screening-criteria
rh-skills promote derive diabetes-screening --source ada-guidelines --name risk-factors
```

### 5. Validate the L2 artifacts

```bash
rh-skills validate diabetes-screening screening-criteria
rh-skills validate diabetes-screening risk-factors
```

### 6. Converge to a computable artifact

```bash
rh-skills promote combine diabetes-screening \
  screening-criteria risk-factors \
  diabetes-screening-pathway
```

### 7. Validate the L3 artifact

```bash
rh-skills validate diabetes-screening diabetes-screening-pathway
```

### 8. Review all topics

```bash
rh-skills list
```

---

→ See [Usage Modes](USAGE_MODES.md) for a full comparison, LLM configuration,
and platform support details.
