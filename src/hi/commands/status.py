"""hi status — Show workflow state of a topic."""

import json

import click

from hi.common import (
    load_tracking,
    repo_root,
    require_topic,
    require_tracking,
    sha256_file,
    sources_root,
)


def _compute_stage(sources_count: int, structured_count: int, computable_count: int) -> str:
    if computable_count > 0:
        return "l3-computable"
    if structured_count > 0:
        return "l2-semi-structured"
    if sources_count > 0:
        return "l1-discovery"
    return "initialized"


_STAGE_LABELS = {
    "initialized": "Discovery",
    "l1-discovery": "Ingest",
    "l2-semi-structured": "Extract",
    "l3-computable": "Formalize",
}


def _completeness_pct(sources: int, structured: int, computable: int) -> int:
    if computable > 0:
        return 100
    if structured > 0:
        return 75
    if sources > 0:
        return 50
    return 25


def _has_discovery_plan(topic: str) -> bool:
    """Return True if a discovery-plan.yaml exists for this topic."""
    plan_path = repo_root() / "topics" / topic / "process" / "plans" / "discovery-plan.yaml"
    return plan_path.exists()


def _next_step_options(sources: int, structured: int, computable: int, topic: str) -> list[tuple[str, str]]:
    """Return ordered list of (description, exact_command) options based on lifecycle state."""
    if sources == 0:
        has_plan = _has_discovery_plan(topic)
        if has_plan:
            return [
                (f"Update your discovery plan", f"hi-discovery session {topic}"),
                (f"Ingest sources using your existing discovery plan", f"hi-ingest plan {topic}"),
                (f"Full pipeline summary", f"hi status progress {topic}"),
            ]
        return [
            ("Start source discovery for this topic", f"hi-discovery session {topic}"),
            ("Ingest sources if you already have a discovery plan", f"hi-ingest plan {topic}"),
            ("Full pipeline summary", f"hi status progress {topic}"),
        ]
    if structured == 0:
        return [
            ("Extract structured criteria from ingested sources (L2)", f"hi-extract plan {topic}"),
            ("Check whether any source files have changed since ingest", f"hi status check-changes {topic}"),
            ("Re-run ingest if sources need refreshing", f"hi-ingest implement {topic}"),
        ]
    if computable == 0:
        return [
            ("Formalize structured artifacts into a computable format (L3)", f"hi-formalize plan {topic}"),
            ("Validate existing structured artifacts", f"hi validate {topic}"),
            ("Check whether any source files have changed since ingest", f"hi status check-changes {topic}"),
        ]
    return [
        ("Validate all artifacts for this topic", f"hi validate {topic}"),
        ("Check whether any source files have changed since ingest", f"hi status check-changes {topic}"),
    ]


def _next_step_recommendation(sources: int, structured: int, computable: int) -> tuple[str, str]:
    """Return (description, exact_command) for the single most important next action."""
    if sources == 0:
        return ("Discover and ingest raw source artifacts (L1)", "hi-ingest plan")
    if structured == 0:
        return ("Extract structured (L2) artifacts from ingested sources", "hi-extract plan")
    if computable == 0:
        return ("Formalize structured artifacts into a computable (L3) artifact", "hi-formalize plan")
    return ("Review and validate artifacts", "hi validate <topic> <artifact>")


@click.group(invoke_without_command=True)
@click.pass_context
def status(ctx):
    """Show workflow state of a topic. Subcommands: show, progress, next-steps, check-changes."""
    if ctx.invoked_subcommand is None:
        _portfolio_summary()


def _portfolio_summary() -> None:
    """Print a summary of all topics with stage, completeness, and next steps."""
    tracking_path = repo_root() / "tracking.yaml"
    if not tracking_path.exists():
        click.echo("No tracking.yaml found. Run `hi init <topic>` to start a topic.")
        return

    tracking = load_tracking()
    topics = tracking.get("topics", [])
    global_sources = tracking.get("sources", [])

    if not topics:
        click.echo("No topics yet. Run `hi init <topic>` to start one.")
        return

    click.echo(f"Research Portfolio — {len(topics)} topic(s)\n")

    for t in topics:
        name = t.get("name", "")
        title = t.get("title", "")
        structured_count = len(t.get("structured", []))
        computable_count = len(t.get("computable", []))
        sources_count = len(global_sources)
        stage = _compute_stage(sources_count, structured_count, computable_count)
        pct = _completeness_pct(sources_count, structured_count, computable_count)
        label = _STAGE_LABELS.get(stage, stage)
        options = _next_step_options(sources_count, structured_count, computable_count, name)

        click.echo(f"▸ {name}")
        if title:
            click.echo(f"  Title:    {title}")
        click.echo(f"  Stage:    {label}  ({pct}%)")
        click.echo("  Next steps:")
        for i, (desc, cmd) in enumerate(options, start=1):
            click.echo(f"    {chr(64 + i)}) {cmd}")
        click.echo("")


@status.command("show")
@click.argument("topic")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status_show(topic, as_json):
    """Show basic workflow state of a topic."""
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
    click.echo(f"  L1 (sources):          {sources_count}")
    click.echo(f"  L2 (structured):       {structured_count}")
    click.echo(f"  L3 (computable):       {computable_count}")
    click.echo("")
    click.echo(f"Last event: {last_event.get('type', '')} ({last_event.get('timestamp', '')})")


@status.command("progress")
@click.argument("topic")
def status_progress(topic):
    """Detailed progress report with completeness percentage."""
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    sources_count = len(tracking.get("sources", []))
    structured_count = len(topic_entry.get("structured", []))
    computable_count = len(topic_entry.get("computable", []))

    stage = _compute_stage(sources_count, structured_count, computable_count)
    label = _STAGE_LABELS.get(stage, stage)
    pct = _completeness_pct(sources_count, structured_count, computable_count)

    events = topic_entry.get("events", [])
    last_event = events[-1] if events else {}

    labels = list(_STAGE_LABELS.values())
    bar = " → ".join(f"[{s}]" if s == label else s for s in labels)

    click.echo(f"Topic:      {topic}")
    click.echo(f"Title:      {topic_entry.get('title', '')}")
    click.echo(f"Stage:      {bar}")
    click.echo(f"Complete:   {pct}%")
    click.echo("")
    click.echo("Artifact Counts:")
    click.echo(f"  L1 sources:     {sources_count}")
    click.echo(f"  L2 structured:  {structured_count}")
    click.echo(f"  L3 computable:  {computable_count}")
    click.echo("")
    click.echo(f"Last event: {last_event.get('type', 'none')} ({last_event.get('timestamp', '')})")
    if events:
        click.echo(f"Total events: {len(events)}")

    options = _next_step_options(sources_count, structured_count, computable_count, topic)
    click.echo("")
    click.echo("What to do next:")
    for i, (desc, cmd) in enumerate(options, start=1):
        click.echo(f"  {chr(64 + i)}) {desc}")
        click.echo(f"     {cmd}")


@status.command("next-steps")
@click.argument("topic")
def status_next_steps(topic):
    """Recommend the single most important next action."""
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    sources_count = len(tracking.get("sources", []))
    structured_count = len(topic_entry.get("structured", []))
    computable_count = len(topic_entry.get("computable", []))

    options = _next_step_options(sources_count, structured_count, computable_count, topic)

    click.echo(f"Topic: {topic}")
    click.echo("")
    click.echo("Recommended next step:")
    click.echo(f"  {options[0][0]}")
    click.echo("")
    click.echo("Run:")
    click.echo(f"  {options[0][1]}")
    if len(options) > 1:
        click.echo("")
        click.echo("Other options:")
        for opt_desc, opt_cmd in options[1:]:
            click.echo(f"  • {opt_desc}")
            click.echo(f"    {opt_cmd}")


@status.command("check-changes")
@click.argument("topic")
def status_check_changes(topic):
    """Check source files for checksum drift; report stale downstream artifacts."""
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    sources = tracking.get("sources", [])
    if not sources:
        click.echo("No L1 sources registered.")
        return

    src_root = sources_root()
    root = repo_root()
    any_changed = False

    # Build map: source name → derived structured artifact names
    structured = topic_entry.get("structured", [])
    derived_from: dict[str, list[str]] = {}
    for art in structured:
        for src_name in art.get("derived_from", []):
            derived_from.setdefault(src_name, []).append(art["name"])

    click.echo(f"Topic: {topic}")
    click.echo("")
    click.echo("Source Change Report:")
    click.echo("-" * 50)

    for src in sources:
        src_name = src.get("name", "")
        src_file = src.get("file", f"sources/{src_name}.md")
        stored_checksum = src.get("checksum", "")

        full_path = root / src_file
        if not full_path.exists():
            full_path = src_root / f"{src_name}.md"

        if not full_path.exists():
            click.echo(f"  ✗ {src_name}  MISSING")
            stale = derived_from.get(src_name, [])
            if stale:
                click.echo(f"    Potentially stale: {', '.join(stale)}")
            any_changed = True
            continue

        current = sha256_file(full_path)
        if current == stored_checksum:
            click.echo(f"  ✓ {src_name}  OK")
        else:
            click.echo(f"  ✗ {src_name}  CHANGED")
            click.echo(f"    was: {stored_checksum[:16]}...")
            click.echo(f"    now: {current[:16]}...")
            stale = derived_from.get(src_name, [])
            if stale:
                click.echo(f"    Potentially stale L2 artifacts: {', '.join(stale)}")
            any_changed = True

    click.echo("")
    if any_changed:
        click.echo("Action: Re-ingest changed sources with `hi ingest implement <file>`")
        raise SystemExit(1)
    else:
        click.echo("All sources unchanged.")
