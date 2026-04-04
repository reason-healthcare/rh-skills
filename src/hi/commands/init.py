"""hi init — Scaffold a new healthcare informatics topic."""

import re
import subprocess
from pathlib import Path

import click
from ruamel.yaml import YAML

from hi.common import (
    append_root_event,
    append_topic_event,
    log_info,
    now_iso,
    sources_root,
    today_date,
    topic_dir,
    topics_root,
    tracking_file,
)


def _default_title(name: str) -> str:
    """Convert kebab-case name to Title Case."""
    return " ".join(word.capitalize() for word in name.split("-"))


def _default_author() -> str:
    """Get git user.name or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5,
        )
        name = result.stdout.strip()
        return name if name else "unknown"
    except Exception:
        return "unknown"


@click.command()
@click.argument("topic")
@click.option("--title", default=None, help="Human-readable title")
@click.option("--description", default=None, help="Brief description")
@click.option("--author", default=None, help="Author name or team")
def init(topic, title, description, author):
    """Scaffold a new topic directory and register in tracking.yaml."""
    # Validate topic name
    if not re.match(r"^[a-z][a-z0-9-]*$", topic):
        raise click.UsageError(
            f"Topic name must be kebab-case (lowercase letters, digits, hyphens only): {topic}"
        )

    # Defaults
    if not title:
        title = _default_title(topic)
    if not description:
        description = "A healthcare informatics topic"
    if not author:
        author = _default_author()

    td = topic_dir(topic)
    if td.exists():
        raise click.ClickException(f"Topic '{topic}' already exists at {td}")

    # Create directory structure
    for subdir in [
        "structured", "computable",
        "fixtures/results", "plans", "contracts", "checklists",
    ]:
        (td / subdir).mkdir(parents=True, exist_ok=True)

    # Ensure sources/ exists
    sources_root().mkdir(parents=True, exist_ok=True)

    timestamp = now_iso()
    today = today_date()

    # Init tracking.yaml if missing
    tf = tracking_file()
    if not tf.exists():
        y = YAML()
        y.default_flow_style = False
        y.dump({
            "schema_version": "1.0",
            "sources": [],
            "topics": [],
            "events": [],
        }, tf)

    # Load and update tracking
    y = YAML()
    y.default_flow_style = False
    y.preserve_quotes = True
    with open(tf) as f:
        tracking = y.load(f)

    tracking["topics"].append({
        "name": topic,
        "title": title,
        "description": description,
        "author": author,
        "created_at": timestamp,
        "structured": [],
        "computable": [],
        "events": [],
    })
    append_root_event(tracking, "topic_created", f"Topic scaffolded with hi init")
    append_topic_event(tracking, topic, "created", "Topic scaffolded with hi init")

    with open(tf, "w") as f:
        y.dump(tracking, f)

    # Write research.md
    (td / "research.md").write_text(f"""\
---
topic: "{topic}"
updated: "{today}"
---

## Background

<!-- Clinical background, evidence base, and relevant literature for this topic. -->

## Evidence Sources

<!-- List key guidelines, studies, and authoritative references. -->

## Evidence Grading

<!-- Grade the quality of evidence for key clinical assertions (e.g., GRADE, AHA levels). -->
""")

    # Write conflicts.md
    (td / "conflicts.md").write_text(f"""\
---
topic: "{topic}"
updated: "{today}"
---

## Open Conflicts

<!-- Document contradictions between sources. Format:
- **Conflict**: <description of contradiction>
  - **Source A**: <source name> says <X>
  - **Source B**: <source name> says <Y>
  - **Resolution**: <pending | resolved: <decision>>
-->

## Resolved Conflicts

<!-- Move resolved conflicts here with the resolution decision. -->
""")

    # Write plans/tasks.md
    (td / "plans" / "tasks.md").write_text(f"""\
---
topic: "{topic}"
updated: "{today}"
---

## Pending

<!-- Tasks yet to be started. Format: - [ ] Description -->

## In Progress

<!-- Tasks currently being worked on. Format: - [~] Description -->

## Done

<!-- Completed tasks. Format: - [x] Description -->
""")

    # Write TOPIC.md
    (td / "TOPIC.md").write_text(f"""\
---
name: "{topic}"
description: "{description}"
compatibility: "hi-skills-framework >= 0.1.0"
metadata:
  author: "{author}"
  created: "{today}"
  domain: ""
---

## Overview

{description}

## Artifact Levels

- **L1 (Discovery)**: Raw clinical knowledge — guidelines, notes, research extracts
- **L2 (Semi-structured)**: Structured YAML artifacts derived from L1 content
- **L3 (Computable)**: Computable YAML artifacts converged from L2, FHIR-compatible

## Instructions

<!-- Describe how an agent or human should reason about and use this topic. -->
""")

    log_info(f"Initialized topic: {topic}")
    click.echo(f"  Location: {td}")
    click.echo(f"  Tracking: {tf}")
    click.echo("  Structure:")
    click.echo("    sources/   (shared raw sources — repo root)")
    click.echo(f"    {topic}/")
    click.echo("      structured/  (semi-structured artifacts)")
    click.echo("      computable/  (computable artifacts)")
    click.echo("      contracts/   (YAML assertions for validation)")
    click.echo("      checklists/  (clinical review checklists)")
    click.echo("      plans/       (tasks and plan artifacts)")
    click.echo("      fixtures/    (LLM test fixtures)")
    click.echo("      TOPIC.md     (topic description)")
    click.echo("      research.md  (evidence and citations)")
    click.echo("      conflicts.md (source contradictions)")
