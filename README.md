# RH Skills

RH Skills is a toolset for superpowering informaticists: it helps teams
synthesize clinical knowledge from raw source material into structured and
computable artifacts.

Today that means workflows for turning guidelines, quality measures,
assessments, and related clinical logic into FHIR-aligned outputs. Over time it
is intended to grow into a broader informatics workbench with terminology and
ontology tooling as well.

## What it does

The RH Skills framework guides clinical knowledge through three artifact levels:

| Level | Format | Description |
|-------|--------|-------------|
| **Raw** | Any | Pre-ingestion files — PDFs, Word docs, web pages, spreadsheets |
| **L1** | Markdown | Raw sources — guideline extracts, clinical notes, literature |
| **L2** | YAML | Structured — discrete clinical criteria, coded concepts |
| **L3** | YAML | Computable — pathways, measures, value sets (FHIR-compatible) |

The relationships are many-to-many: one L1 source can yield several L2 artifacts; multiple L2 artifacts can converge into a single L3.

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
