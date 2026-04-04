"""hi status — Show workflow state of a topic."""

import json

import click

from hi.common import (
    log_error,
    now_iso,
    require_topic,
    require_tracking,
    topic_dir,
)


def _compute_stage(sources_count: int, structured_count: int, computable_count: int) -> str:
    if computable_count > 0:
        return "l3-computable"
    if structured_count > 0:
        return "l2-semi-structured"
    if sources_count > 0:
        return "l1-discovery"
    return "initialized"


@click.command()
@click.argument("topic")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status(topic, as_json):
    """Show workflow state of a topic."""
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    sources_count = len(tracking.get("sources", []))
    structured_count = len(topic_entry.get("structured", []))
    computable_count = len(topic_entry.get("computable", []))

    stage = _compute_stage(sources_count, structured_count, computable_count)

    events = topic_entry.get("events", [])
    last_event = events[-1] if events else {}

    if as_json:
        data = {
            "topic": topic,
            "title": topic_entry.get("title", ""),
            "author": topic_entry.get("author", ""),
            "created_at": topic_entry.get("created_at", ""),
            "stage": stage,
            "sources": sources_count,
            "structured": structured_count,
            "computable": computable_count,
            "last_event": {
                "type": last_event.get("type", ""),
                "timestamp": last_event.get("timestamp", ""),
            },
        }
        click.echo(json.dumps(data, indent=2))
        return

    click.echo(f"Topic:    {topic}")
    click.echo(f"Title:    {topic_entry.get('title', '')}")
    click.echo(f"Author:   {topic_entry.get('author', '')}")
    click.echo(f"Created:  {topic_entry.get('created_at', '')}")
    click.echo(f"Stage:    {stage}")
    click.echo("")
    click.echo("Artifacts:")
    click.echo(f"  L1 (discovery):        {sources_count}")
    click.echo(f"  L2 (semi-structured):  {structured_count}")
    click.echo(f"  L3 (computable):       {computable_count}")
    click.echo("")
    click.echo(f"Last event: {last_event.get('type', '')} ({last_event.get('timestamp', '')})")
