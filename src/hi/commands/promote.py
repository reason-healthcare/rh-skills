"""hi promote — Promote artifacts between lifecycle levels."""

import os
from pathlib import Path

import click

from hi.common import (
    append_topic_event,
    log_info,
    log_warn,
    now_iso,
    require_topic,
    require_tracking,
    save_tracking,
    sha256_file,
    today_date,
    topic_dir,
)


def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke LLM or return stub response."""
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    if provider == "stub":
        stub = os.environ.get("HI_STUB_RESPONSE", "Stub response")
        return stub
    raise click.ClickException(
        f"LLM provider '{provider}' not available in Python port — use LLM_PROVIDER=stub for testing"
    )


@click.group()
def promote():
    """Promote artifacts between lifecycle levels."""


@promote.command()
@click.argument("topic")
@click.argument("name")
@click.option("--source", required=True, multiple=True, help="L1 source name (can repeat)")
@click.option("--count", default=1, help="Number of L2 artifacts to generate")
@click.option("--dry-run", is_flag=True, help="Print what would be created without doing it")
def derive(topic, name, source, count, dry_run):
    """Promote L1 source(s) to L2 structured artifact(s)."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    # Validate each source exists in tracking
    registered_sources = {s["name"] for s in tracking.get("sources", [])}
    for src in source:
        if src not in registered_sources:
            raise click.UsageError(f"Source '{src}' not found in tracking.yaml sources")

    td = topic_dir(topic)

    if count > 1:
        artifact_names = [f"{name}-{i}" for i in range(1, count + 1)]
    else:
        artifact_names = [name]

    system_prompt = """\
You are a healthcare informatics specialist. Your task is to extract and structure \
clinical knowledge from raw discovery artifacts into a semi-structured YAML format.

The output MUST be valid YAML with these required fields:
  id, name, title, version, status, domain, description, derived_from

Rules:
- id: kebab-case identifier
- name: short machine name (no spaces)
- title: human-readable title
- version: "1.0.0"
- status: draft
- domain: clinical domain (e.g. diabetes, sepsis, hypertension)
- description: clear clinical description (2-4 sentences)
- derived_from: list containing the source L1 artifact name

Output ONLY the YAML block. No markdown fences, no explanation."""

    for artifact_name in artifact_names:
        user_prompt = f"Source L1 artifact name: {', '.join(source)}\nGenerate L2 artifact: {artifact_name}"

        if dry_run:
            click.echo(f"--- DRY RUN: derive prompt for {artifact_name} ---")
            click.echo(f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}")
            continue

        click.echo(f"Deriving L2 artifact: {artifact_name} (from {', '.join(source)})...")

        llm_output = _invoke_llm(system_prompt, user_prompt)

        l2_file = td / "structured" / f"{artifact_name}.yaml"

        if llm_output == "Stub response":
            # Write a minimal valid L2 artifact template for stub mode
            l2_file.write_text(f"""\
id: {artifact_name}
name: {artifact_name}
title: ""
version: "1.0.0"
status: draft
domain: ""
description: ""
derived_from:
{chr(10).join(f"  - {s}" for s in source)}
""")
        else:
            l2_file.write_text(llm_output + "\n")

        timestamp = now_iso()
        checksum = sha256_file(l2_file)
        topic_entry = require_topic(tracking, topic)
        topic_entry["structured"].append({
            "name": artifact_name,
            "file": f"topics/{topic}/structured/{artifact_name}.yaml",
            "created_at": timestamp,
            "checksum": checksum,
            "derived_from": list(source),
        })
        append_topic_event(tracking, topic, "structured_derived", f"Derived {artifact_name} from {', '.join(source)}")
        save_tracking(tracking)

        log_info(f"Created: {l2_file}")


@promote.command()
@click.argument("topic")
@click.argument("sources", nargs=-1, required=True)
@click.option("--dry-run", is_flag=True, help="Print what would be created without doing it")
def combine(topic, sources, dry_run):
    """Promote L2 artifacts to a single L3 computable artifact.

    Sources: all positional args — last one is the target name, rest are L2 source names.
    Example: hi promote combine mytopic l2-a l2-b l3-target
    """
    if len(sources) < 2:
        raise click.UsageError("combine requires at least one source and one target name")

    l2_source_names = list(sources[:-1])
    target_name = sources[-1]

    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    # Validate L2 sources exist in tracking
    registered_l2 = {a["name"] for a in topic_entry.get("structured", [])}
    for src in l2_source_names:
        if src not in registered_l2:
            raise click.UsageError(f"L2 artifact '{src}' not found in topic '{topic}'")

    td = topic_dir(topic)
    today = today_date()

    system_prompt = """\
You are a healthcare informatics specialist. Your task is to converge multiple \
semi-structured L2 YAML artifacts into a single computable L3 YAML artifact.

The output MUST be valid YAML with this structure:

artifact_schema_version: "1.0"
metadata:
  id: # kebab-case
  name: # short machine name
  title: # human-readable title
  version: "1.0.0"
  status: draft
  domain: # clinical domain
  created_date: # YYYY-MM-DD
  description: # clear description
converged_from:
  - <l2-artifact-name>

Output ONLY the YAML block. No markdown fences, no explanation."""

    user_prompt = f"Output artifact name (id): {target_name}\nToday's date: {today}\nSources: {', '.join(l2_source_names)}"

    if dry_run:
        click.echo(f"--- DRY RUN: combine prompt for {target_name} ---")
        click.echo(f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}")
        return

    click.echo(f"Combining L2 artifacts into L3: {target_name}...")
    click.echo(f"Sources: {', '.join(l2_source_names)}")

    llm_output = _invoke_llm(system_prompt, user_prompt)

    l3_file = td / "computable" / f"{target_name}.yaml"

    if llm_output == "Stub response":
        l3_file.write_text(f"""\
artifact_schema_version: "1.0"
metadata:
  id: {target_name}
  name: {target_name}
  title: ""
  version: "1.0.0"
  status: draft
  domain: ""
  created_date: {today}
  description: ""
converged_from:
{chr(10).join(f"  - {s}" for s in l2_source_names)}
""")
    else:
        l3_file.write_text(llm_output + "\n")

    timestamp = now_iso()
    checksum = sha256_file(l3_file)
    topic_entry["computable"].append({
        "name": target_name,
        "file": f"topics/{topic}/computable/{target_name}.yaml",
        "created_at": timestamp,
        "checksum": checksum,
        "converged_from": l2_source_names,
    })
    append_topic_event(tracking, topic, "computable_converged", f"Converged {target_name} from {', '.join(l2_source_names)}")
    save_tracking(tracking)

    log_info(f"Created: {l3_file}")
