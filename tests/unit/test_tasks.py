"""Tests for rh-skills tasks command — ported from tests/unit/tasks.bats."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from hi.commands.tasks import tasks


def setup_topic_with_tasks(tmp_repo, topic_name="my-topic"):
    """Create a topic with a pre-populated tasks.md."""
    td = tmp_repo / "topics" / topic_name
    (td / "process" / "plans").mkdir(parents=True, exist_ok=True)
    (td / "structured").mkdir(parents=True, exist_ok=True)
    (td / "computable").mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    if not any(t["name"] == topic_name for t in tracking["topics"]):
        tracking["topics"].append({
            "name": topic_name,
            "title": "My Topic",
            "structured": [],
            "computable": [],
            "events": [],
        })
        with open(tracking_path, "w") as f:
            y.dump(tracking, f)

    tasks_file = td / "process" / "plans" / "tasks.md"
    tasks_file.write_text("""\
---
topic: "my-topic"
---

## Pending
- [ ] First task
- [ ] Second task

## In Progress
- [~] Third task

## Done
- [x] Fourth task
""")


# ── Basic functionality ────────────────────────────────────────────────────────

def test_tasks_list_exits_0(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(tasks, ["list", "my-topic"])
    assert result.exit_code == 0


def test_tasks_list_shows_numbered_pending(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(tasks, ["list", "my-topic"])
    assert "[1]" in result.output
    assert "First task" in result.output
    assert "[2]" in result.output
    assert "Second task" in result.output


def test_tasks_list_shows_summary_counts(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(tasks, ["list", "my-topic"])
    assert "2 pending" in result.output
    assert "1 in-progress" in result.output
    assert "1 done" in result.output


def test_tasks_list_creates_tasks_file_if_missing(tmp_repo):
    td = tmp_repo / "topics" / "my-topic"
    (td / "structured").mkdir(parents=True, exist_ok=True)
    (td / "computable").mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)
    tracking["topics"].append({
        "name": "my-topic",
        "structured": [],
        "computable": [],
        "events": [],
    })
    with open(tracking_path, "w") as f:
        y.dump(tracking, f)

    runner = CliRunner()
    result = runner.invoke(tasks, ["list", "my-topic"])
    assert result.exit_code == 0
    assert (td / "process" / "plans" / "tasks.md").exists()


def test_tasks_add_appends_pending_task(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(tasks, ["add", "New task description", "my-topic"])
    assert result.exit_code == 0
    tasks_file = tmp_repo / "topics" / "my-topic" / "process" / "plans" / "tasks.md"
    content = tasks_file.read_text()
    assert "- [ ] New task description" in content


def test_tasks_complete_marks_task_done(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(tasks, ["complete", "1", "my-topic"])
    assert result.exit_code == 0
    tasks_file = tmp_repo / "topics" / "my-topic" / "process" / "plans" / "tasks.md"
    content = tasks_file.read_text()
    assert "- [x] First task" in content


def test_tasks_complete_exits_1_for_out_of_range(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(tasks, ["complete", "99", "my-topic"])
    assert result.exit_code == 1


def test_tasks_complete_appends_event_to_tracking(tmp_repo):
    setup_topic_with_tasks(tmp_repo)
    runner = CliRunner()
    runner.invoke(tasks, ["complete", "1", "my-topic"])
    y = YAML()
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    topic = next(t for t in tracking["topics"] if t["name"] == "my-topic")
    event_types = [e["type"] for e in topic["events"]]
    assert "task_completed" in event_types


def test_tasks_list_works_at_repo_root(tmp_repo):
    plans_dir = tmp_repo / "plans"
    plans_dir.mkdir(exist_ok=True)
    (plans_dir / "tasks.md").write_text("""\
---
topic: "repo-root"
---

## Pending
- [ ] Ingest ada-guidelines-2024

## In Progress

## Done
""")
    runner = CliRunner()
    result = runner.invoke(tasks, ["list"])
    assert result.exit_code == 0
    assert "Ingest ada-guidelines" in result.output


def test_tasks_exits_2_for_unknown_topic(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(tasks, ["list", "nonexistent-topic"])
    assert result.exit_code == 2


def test_tasks_add_works_at_repo_root(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(tasks, ["add", "Root level task"])
    assert result.exit_code == 0
    content = (tmp_repo / "plans" / "tasks.md").read_text()
    assert "- [ ] Root level task" in content
