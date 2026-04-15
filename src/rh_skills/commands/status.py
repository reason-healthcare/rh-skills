"""rh-skills status — Show workflow state of a topic."""

import json

import click

from rh_skills.common import (
    load_tracking,
    repo_root,
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


def _next_step_options(sources: int, structured: int, computable: int, topic: str) -> list[tuple[str, str | None]]:
    """Return ordered list of (description, exact_command) options based on lifecycle state."""
    if sources == 0:
        has_plan = _has_discovery_plan(topic)
        if has_plan:
            return [
                (f"Update your discovery plan", f"rh-inf-discovery session {topic}"),
                (f"Ingest sources using your existing discovery plan", f"rh-inf-ingest plan {topic}"),
                (f"Full pipeline summary", f"rh-skills status progress {topic}"),
            ]
        return [
            ("Start source discovery for this topic", f"rh-inf-discovery session {topic}"),
            ("Ingest sources if you already have a discovery plan", f"rh-inf-ingest plan {topic}"),
            ("Full pipeline summary", f"rh-skills status progress {topic}"),
        ]
    if structured == 0:
        return [
            ("Extract structured criteria from ingested sources (L2)", f"rh-inf-extract plan {topic}"),
            ("Check whether any source files have changed since ingest", f"rh-skills status check-changes {topic}"),
            ("Re-run ingest if sources need refreshing", f"rh-inf-ingest implement {topic}"),
        ]
    if computable == 0:
        return [
            ("Formalize structured artifacts into a computable format (L3)", f"rh-inf-formalize plan {topic}"),
            ("Run extract-stage verification for existing structured artifacts", f"rh-inf-extract verify {topic}"),
            ("Check whether any source files have changed since ingest", f"rh-skills status check-changes {topic}"),
        ]
    return [
        ("No immediate action required — this topic already has computable artifacts", None),
        ("Run unified verification for this topic", f"rh-inf-verify verify {topic}"),
        ("Check whether any source files have changed since ingest", f"rh-skills status check-changes {topic}"),
    ]


def _render_next_steps(options: list[tuple[str, str | None]], indent: str = "") -> None:
    """Render deterministic next-step bullets."""
    click.echo(f"{indent}Next steps:")
    for desc, cmd in options:
        if cmd:
            click.echo(f"{indent}  - {desc}: {cmd}")
        else:
            click.echo(f"{indent}  - {desc}")


def _load_status_tracking() -> dict:
    """Load tracking with status-specific recovery guidance."""
    tracking_path = repo_root() / "tracking.yaml"
    if not tracking_path.exists():
        raise click.ClickException(
            "No tracking.yaml found. Run `rh-skills init <topic>` to start a topic."
        )
    return load_tracking()


def _require_status_topic(tracking: dict, topic: str) -> dict:
    """Return topic or raise a user-facing status error with recovery guidance."""
    topics = tracking.get("topics", [])
    if not topics:
        raise click.UsageError("No topics yet. Run `rh-skills init <topic>` to start one.")

    for topic_entry in topics:
        if topic_entry.get("name") == topic:
            return topic_entry

    raise click.UsageError(
        f"Topic '{topic}' not found. Run `rh-skills list` to see available topics or "
        f"`rh-skills init {topic}` to start it."
    )


@click.group(invoke_without_command=True)
@click.pass_context
def status(ctx):
    """Show workflow state of a topic. Subcommands: show, progress, next-steps, check-changes."""
    if ctx.invoked_subcommand is None:
        _portfolio_summary()


def _portfolio_summary() -> None:
    """Print project-level status and per-topic recommendations from tracking.yaml."""
    tracking = _load_status_tracking()
    topics = tracking.get("topics", [])
    global_sources = tracking.get("sources", [])
    source_count = len(global_sources)

    if not topics:
        click.echo("No topics yet. Run `rh-skills init <topic>` to start one.")
        click.echo("")
        _render_next_steps([("Initialize a new topic", "rh-skills init <topic>")])
        return

    # Project-level header
    click.echo(f"Research Portfolio")
    click.echo(f"  Topics:   {len(topics)}")
    click.echo(f"  Sources:  {source_count}")
    click.echo("")

    for t in topics:
        name = t.get("name", "")
        title = t.get("title", "")
        structured_count = len(t.get("structured", []))
        computable_count = len(t.get("computable", []))
        stage = _compute_stage(source_count, structured_count, computable_count)
        label = _STAGE_LABELS.get(stage, stage)
        has_plan = _has_discovery_plan(name)
        options = _next_step_options(source_count, structured_count, computable_count, name)

        header = f"{name}"
        if title:
            header += f" — {title}"
        click.echo(header)

        plan_note = "· discovery plan ✓" if has_plan else ""
        click.echo(f"  Stage:  {label} {plan_note}".rstrip())

        if source_count:
            click.echo(f"  Sources:     {source_count}")
        if structured_count:
            click.echo(f"  Structured:  {structured_count}")
        if computable_count:
            click.echo(f"  Computable:  {computable_count}")

        if options:
            _render_next_steps(options, indent="  ")

        click.echo("")


@status.command("show")
@click.argument("topic")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def status_show(topic, as_json):
    """Show basic workflow state of a topic."""
    tracking = _load_status_tracking()
    topic_entry = _require_status_topic(tracking, topic)

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
    click.echo("")
    _render_next_steps(_next_step_options(sources_count, structured_count, computable_count, topic))


@status.command("progress")
@click.argument("topic")
def status_progress(topic):
    """Detailed progress report with completeness percentage."""
    tracking = _load_status_tracking()
    topic_entry = _require_status_topic(tracking, topic)

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
    _render_next_steps(options)


@status.command("next-steps")
@click.argument("topic")
def status_next_steps(topic):
    """Recommend the single most important next action."""
    tracking = _load_status_tracking()
    topic_entry = _require_status_topic(tracking, topic)

    sources_count = len(tracking.get("sources", []))
    structured_count = len(topic_entry.get("structured", []))
    computable_count = len(topic_entry.get("computable", []))

    options = _next_step_options(sources_count, structured_count, computable_count, topic)

    click.echo(f"Topic: {topic}")
    click.echo("")
    _render_next_steps(options)


@status.command("check-changes")
@click.argument("topic")
def status_check_changes(topic):
    """Check source files for checksum drift; report stale downstream artifacts."""
    tracking = _load_status_tracking()
    topic_entry = _require_status_topic(tracking, topic)

    sources = tracking.get("sources", [])
    if not sources:
        click.echo("No L1 sources registered.")
        click.echo("")
        _render_next_steps([
            ("Start source discovery for this topic", f"rh-inf-discovery session {topic}"),
            ("Review topic status", f"rh-skills status show {topic}"),
        ])
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

    computable = topic_entry.get("computable", [])

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
            stale_l3 = [
                art.get("name", "")
                for art in computable
                if any(parent in stale for parent in art.get("converged_from", []))
            ]
            if stale:
                click.echo(f"    Potentially stale L2 artifacts: {', '.join(stale)}")
            if stale_l3:
                click.echo(f"    Potentially stale L3 artifacts: {', '.join(stale_l3)}")
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
            stale_l3 = [
                art.get("name", "")
                for art in computable
                if any(parent in stale for parent in art.get("converged_from", []))
            ]
            if stale:
                click.echo(f"    Potentially stale L2 artifacts: {', '.join(stale)}")
            if stale_l3:
                click.echo(f"    Potentially stale L3 artifacts: {', '.join(stale_l3)}")
            any_changed = True

    click.echo("")
    if any_changed:
        _render_next_steps([
            ("Re-ingest or refresh the affected sources for this topic", f"rh-inf-ingest implement {topic}"),
            ("Re-check drift after source refresh", f"rh-skills status check-changes {topic}"),
            ("Review topic status before continuing", f"rh-skills status show {topic}"),
        ])
        raise SystemExit(1)
    else:
        click.echo("All sources unchanged.")
        click.echo("")
        _render_next_steps([
            ("No immediate action required — no source drift was detected", None),
            ("Review topic status", f"rh-skills status show {topic}"),
            ("Run unified verification for this topic", f"rh-inf-verify verify {topic}"),
        ])
