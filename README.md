# rh-skills

[![CI](https://github.com/reason-healthcare/rh-skills/actions/workflows/skill-build.yml/badge.svg)](https://github.com/reason-healthcare/rh-skills/actions/workflows/skill-build.yml)

rh-skills is an agentic workflow toolset providing superpowers for clinical
informaticists: it orchestrates AI reasoning over raw clinical source material
and produces **deterministic, computable rules** — structured artifacts that can
be embedded directly into EHRs, quality programs, and clinical decision support
systems.

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

## Documentation

- [Introduction](docs/INTRODUCTION.md): high-level orientation to RH Skills and its intended use cases
- [Getting Started](docs/GETTING_STARTED.md): prerequisites, installation, and first hands-on walkthrough
- [Workflow](docs/WORKFLOW.md): lifecycle model, artifact flow, and repository structure
  - [Discovery](docs/DISCOVERY.md): L1 evidence search and source registry
  - [Ingest](docs/INGEST.md): L1 source acquisition and normalization
  - [Extract](docs/EXTRACT.md): L2 structured artifact derivation
  - [Formalize](docs/FORMALIZE.md): L3 FHIR R4 computable conversion
- [Usage Modes](docs/USAGE_MODES.md): CLI-first vs agent-native usage and configuration guidance
- [Commands](docs/COMMANDS.md): full CLI reference with commands, subcommands, and options
- [Example Project](example-project/): sample repository showing the expected project layout and artifacts
- [Windows Installation](docs/WINDOWS_PYTHON_INSTALLATION.md): end user workflow for Python and RH Skills installation

## Prerequisites

- Python 3.13+
- [pipx](https://pipx.pypa.io/stable/)
- An LLM provider only if you plan to use **CLI-first** mode — local Ollama,
  Anthropic, OpenAI, or any OpenAI-compatible endpoint. Agent-native users can
  rely on their existing agent platform.

## Recommended: ReasonHub MCP

The RH skills use the **ReasonHub MCP** service for terminology support —
code-system searching (SNOMED CT, LOINC, ICD-10-CM, RxNorm, UCUM), value set
expansion, and code validation. Without it the skills still function, but
`terminology / value sets` artifacts and `value_sets[]` sections in computable
artifacts will contain placeholder text rather than validated codes.

**Setup (free)**:

1. Sign up at **<https://reasonhub.app/>**
2. Retrieve your API key from the dashboard
3. Add the MCP server to your agent configuration under the service name
   **`reasonhub`**:

```json
{
  "mcpServers": {
    "reasonhub": {
      "url": "https://reasonhub.app/mcp",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
  }
}
```

> The service name **`reasonhub`** is required — the skills reference MCP tools
> by that name. If your agent platform uses a different config format (YAML,
> TOML, etc.), adapt the snippet accordingly but keep the service name the same.

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

## Contributors

See [DEVELOPER.md](DEVELOPER.md) for contributor setup, development workflows,
and framework implementation guidance.

## Supported By

This project is proudly supported by [Vermonster](https://vermonster.com) / [ReasonHealth](https://reason.health).

<p>
  <span style="padding: 0 20px; display: inline-block;">
    <a href="https://vermonster.com"><img src="https://www.vermonster.com/images/vermonster-logo.svg" alt="Vermonster Logo" height="20px"></a>
  </span>
  <span>&nbsp;&nbsp;&nbsp;</span>
  <span style="padding: 0 20px; display: inline-block;">
    <a href="https://reason.health"><img src="https://www.vermonster.com/images/reasonhub-logo-full-color-rgb.svg" alt="ReasonHealth Logo" height="20px"></a>
  </span>
</p>