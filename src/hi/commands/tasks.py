"""rh-skills tasks — Manage workflow tasks for a topic or the repo root."""

from pathlib import Path

import click

from hi.common import (
    append_topic_event,
    log_error,
    now_iso,
    repo_root,
    require_topic,
    save_tracking,
    today_date,
    topic_dir,
    topics_root,
    tracking_file,
)


def _tasks_file(topic: str | None) -> Path:
    """Return the tasks file path for a topic or repo root."""
    if topic:
        return topic_dir(topic) / "process" / "plans" / "tasks.md"
    return repo_root() / "plans" / "tasks.md"


def _ensure_tasks_file(file: Path, topic: str | None) -> None:
    """Create tasks file with template if it doesn't exist."""
    if file.exists():
        return
    file.parent.mkdir(parents=True, exist_ok=True)
    label = topic or "repo-root"
    today = today_date()
    file.write_text(f"""\
---
topic: "{label}"
updated: "{today}"
---

## Pending

## In Progress

## Done
""")


def _list_tasks(topic: str | None) -> None:
    """Print tasks grouped by status."""
    file = _tasks_file(topic)
    _ensure_tasks_file(file, topic)

    pending = 0
    inprogress = 0
    done = 0
    idx = 0

    header = "=== Tasks"
    if topic:
        header += f": {topic}"
    header += " ==="
    click.echo(header)
    click.echo("")

    with open(file) as f:
        for line in f:
            line = line.rstrip("\n")
            if line == "## Pending":
                pass
            elif line == "## In Progress":
                pass
            elif line == "## Done":
                pass
            elif line.startswith("- [ ] "):
                idx += 1
                desc = line[6:]
                click.echo(f"  [{idx}] {desc}")
                pending += 1
            elif line.startswith("- [~] "):
                desc = line[6:]
                click.echo(f"  [~] {desc}")
                inprogress += 1
            elif line.startswith("- [x] "):
                done += 1

    click.echo(f"\nSummary: {pending} pending, {inprogress} in-progress, {done} done")


def _add_task(desc: str, topic: str | None) -> None:
    """Append a new pending task after ## Pending."""
    file = _tasks_file(topic)
    _ensure_tasks_file(file, topic)

    lines = file.read_text().splitlines(keepends=True)
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if line.rstrip("\n") == "## Pending" and not inserted:
            new_lines.append(f"- [ ] {desc}\n")
            inserted = True

    file.write_text("".join(new_lines))
    click.echo(f"Added task: {desc}")


def _complete_task(n: int, topic: str | None) -> None:
    """Mark the nth pending task as done."""
    file = _tasks_file(topic)
    if not file.exists():
        raise click.ClickException(f"No tasks file found at: {file}")

    lines = file.read_text().splitlines(keepends=True)
    new_lines = []
    count = 0
    found_desc = None

    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("- [ ] ") and found_desc is None:
            count += 1
            if count == n:
                found_desc = stripped[6:]
                new_lines.append(f"- [x] {found_desc}\n")
                continue
        new_lines.append(line)

    if found_desc is None:
        raise click.ClickException(f"No pending task #{n} found")

    file.write_text("".join(new_lines))

    # Append event to tracking
    tf = tracking_file()
    if tf.exists():
        from ruamel.yaml import YAML
        y = YAML()
        y.default_flow_style = False
        y.preserve_quotes = True
        with open(tf) as f:
            tracking = y.load(f)
        if topic:
            try:
                require_topic(tracking, topic)
                append_topic_event(tracking, topic, "task_completed", f"Completed task: {found_desc}")
            except Exception:
                pass
        else:
            from hi.common import append_root_event
            append_root_event(tracking, "task_completed", f"Completed task: {found_desc}")
        with open(tf, "w") as f:
            y.dump(tracking, f)

    click.echo(f"Completed task #{n}: {found_desc}")


@click.group()
def tasks():
    """Manage workflow tasks for a topic or the repo root."""


@tasks.command(name="list")
@click.argument("topic", required=False)
def list_tasks(topic):
    """List tasks (pending / in-progress / done)."""
    if topic:
        # Validate topic exists
        tf = tracking_file()
        if not tf.exists():
            raise click.UsageError(f"Topic '{topic}' not found")
        from ruamel.yaml import YAML
        y = YAML()
        with open(tf) as f:
            tracking = y.load(f)
        require_topic(tracking, topic)
    _list_tasks(topic)


@tasks.command()
@click.argument("desc")
@click.argument("topic", required=False)
def add(desc, topic):
    """Append a new pending task."""
    if topic:
        tf = tracking_file()
        if not tf.exists():
            raise click.UsageError(f"Topic '{topic}' not found")
        from ruamel.yaml import YAML
        y = YAML()
        with open(tf) as f:
            tracking = y.load(f)
        require_topic(tracking, topic)
    _add_task(desc, topic)


@tasks.command()
@click.argument("n", type=int)
@click.argument("topic", required=False)
def complete(n, topic):
    """Mark the Nth pending task as done (1-indexed)."""
    if n < 1:
        raise click.UsageError(f"Task number must be a positive integer (got: {n})")
    if topic:
        tf = tracking_file()
        if not tf.exists():
            raise click.UsageError(f"Topic '{topic}' not found")
        from ruamel.yaml import YAML
        y = YAML()
        with open(tf) as f:
            tracking = y.load(f)
        require_topic(tracking, topic)
    _complete_task(n, topic)
