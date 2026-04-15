# RH Skills

RH Skills is an agentic workflow toolset for clinical informaticists: it
orchestrates AI reasoning over raw clinical source material and produces
**deterministic, computable rules** — structured artifacts that can be embedded
directly into EHRs, quality programs, and clinical decision support systems.

This matters. Clinically, evidence shows it takes up to 17 years for research
findings to reach routine practice,¹ and even published guidelines are routinely
inconsistently applied due to the gap between narrative prose and implementable
logic. Computable rules close that gap: once encoded, a guideline can fire
consistently at the point of care across every patient, every encounter, every
system — reducing diagnostic errors, preventing harmful drug interactions, and
improving adherence to best practices without relying on individual clinician
recall.


> RH Skills focuses on turning guidelines, quality measures, assessments,
> clinical logic, and prior authorization policies into computable, 
> deterministic logic. 

---

¹ Morris ZS, Wooding S, Grant J. "The answer is 17 years, what is the question:
understanding time lags in translational research." *J R Soc Med.* 2011;104(12):510–520.
[doi:10.1258/jrsm.2011.110180](https://doi.org/10.1258/jrsm.2011.110180) · PMID 22179294

---

## What it does

The RH Skills framework guides clinical knowledge through three artifact levels:

```
  PDF, DOCX, HTML, XLSX, ...          (L1 raw — any format)
           │
           │  ingest + normalize
           ▼
       Markdown                        (L1 normalized)
           │
           │  extract  ┌─────────────────────────┐
           ├──────────▶│  Structured artifact    │  (L2)
           ├──────────▶│  Structured artifact    │  (L2)
           └──────────▶│  Structured artifact    │  (L2)
                       └────────┬──────────┬─────┘
                                │          │
                                │ converge │
                                ▼          ▼
                        ┌────────────────────────┐
                        │  Computable artifact   │  (L3)
                        │  (FHIR-aligned)        │
                        └────────────────────────┘
```


| Level | Format | Description |
|-------|--------|-------------|
| **L1 (raw)** | Any | Original source files as-obtained — PDFs, Word docs, web pages, spreadsheets |
| **L1 (normalized)** | Markdown | Source content converted to plain Markdown for consistent downstream processing |
| **L2** | YAML | Structured — discrete clinical criteria, coded concepts |
| **L3** | YAML | Computable — pathways, measures, value sets (FHIR-compatible) |

Raw files are ingested and normalized to Markdown (L1) before extraction. The relationships are many-to-many: one L1 source can yield several L2 artifacts; multiple L2 artifacts can converge into a single L3.

## Prerequisites

- Python 3.13+
- [pipx](https://pipx.pypa.io/stable/)
- An LLM provider only if you plan to use **CLI-first** mode — local Ollama,
  Anthropic, OpenAI, or any OpenAI-compatible endpoint. Agent-native users can
  rely on their existing agent platform.

## Installation

One-line CLI install:

```bash
pipx install git+https://github.com/reason-healthcare/rh-skills.git
```

Then verify the install:

```bash
rh-skills --help
```

If you are using **CLI-first** mode (see below), configure your LLM provider
with either environment variables or config files:

```toml
# .rh-skills.toml (local) or ~/.rh-skills.toml (global)
[llm]
provider = "ollama"

[paths]
repo_root = "/path/to/repo"
```

Supported precedence is: **environment variables > local `.rh-skills.toml` >
global `~/.rh-skills.toml`**.

## Usage Modes

The framework supports two modes — both use the `rh-skills` CLI for
deterministic work and an agent for reasoning:

| Mode | How it works | Best for |
|------|-------------|----------|
| **CLI-first** | You call `rh-skills` commands directly; use any LLM provider (including local models) | Full control, CI/CD, bring-your-own-model |
| **Agent-native** | Your AI agent (Copilot, Claude, Gemini) reads the RH skills and calls `rh-skills` on your behalf | Conversational UX, clinical teams |

→ See [docs/USAGE_MODES.md](docs/USAGE_MODES.md) for a full comparison,
platform support, and LLM configuration.

### Agent-native setup

Install the RH skills into your project so your agent can find them:

```bash
# First-time setup — prompts for which agents to support
rh-skills skills init

# Check for drift (files modified or missing since last install)
rh-skills skills check

# Re-install / update after upgrading rh-skills
rh-skills skills update
```

Skills are bundled with the package, so no network access is required during
install. To get new or updated skills, upgrade the package first:

```bash
pipx upgrade rh-skills
rh-skills skills update
```

Supported platforms and their install locations:

| Platform | Install location |
|----------|-----------------|
| Generic (Copilot, etc.) | `.agents/skills/<skill>/` |
| Claude | `.claude/commands/<skill>.md` |
| Cursor | `.cursor/rules/<skill>.mdc` |
| Gemini | `.gemini/<skill>.md` |

A `.rh-skills-lock.yaml` file is written to your project root to track which
skills and versions are installed. Commit this file alongside your agent config.

## End-user documentation

- Introduction: high-level orientation to RH Skills and its intended use cases
- [Quickstart](docs/QUICKSTART.md): first hands-on walkthrough from topic init to validated outputs
- [Workflow](docs/WORKFLOW.md): lifecycle model, artifact flow, and repository structure
- [Usage Modes](docs/USAGE_MODES.md): CLI-first vs agent-native usage and configuration guidance
- [Commands](docs/COMMANDS.md): full CLI reference with commands, subcommands, and options
- [Example Project](example-project/): sample repository showing the expected project layout and artifacts

## Contributors

See [DEVELOPER.md](DEVELOPER.md) for contributor setup, development workflows,
and framework implementation guidance.
