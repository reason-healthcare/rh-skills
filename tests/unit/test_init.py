"""Tests for rh-skills init command — ported from tests/unit/init.bats."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from hi.commands.init import init


def load_yaml(path):
    y = YAML()
    with open(path) as f:
        return y.load(f)


# ── Basic scaffolding ──────────────────────────────────────────────────────────

def test_init_creates_directory_structure(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(init, ["test-skill"])
    assert result.exit_code == 0, result.output
    topics = tmp_repo / "topics"
    assert (topics / "test-skill").is_dir()
    assert (topics / "test-skill" / "structured").is_dir()
    assert (topics / "test-skill" / "computable").is_dir()
    assert (topics / "test-skill" / "process" / "fixtures").is_dir()
    assert (tmp_repo / "sources").is_dir()


def test_init_creates_tracking_yaml(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(init, ["test-skill"])
    assert result.exit_code == 0
    assert (tmp_repo / "tracking.yaml").exists()


def test_init_tracking_schema_version(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    assert str(data["schema_version"]) == "1.0"


def test_init_tracking_records_skill_name(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["my-skill"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    names = [t["name"] for t in data["topics"]]
    assert "my-skill" in names


def test_init_tracking_has_created_event(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "test-skill")
    assert topic["events"][0]["type"] == "created"


def test_init_creates_topic_md(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(init, ["test-skill"])
    assert result.exit_code == 0
    assert (tmp_repo / "topics" / "test-skill" / "TOPIC.md").exists()


def test_init_topic_md_contains_name(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    content = (tmp_repo / "topics" / "test-skill" / "TOPIC.md").read_text()
    assert 'name: "test-skill"' in content


# ── Flag handling ──────────────────────────────────────────────────────────────

def test_init_title_sets_tracking_title(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill", "--title", "My Custom Title"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "test-skill")
    assert topic["title"] == "My Custom Title"


def test_init_description_sets_tracking_description(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill", "--description", "A clinical decision support skill"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "test-skill")
    assert topic["description"] == "A clinical decision support skill"


def test_init_author_sets_tracking_author(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill", "--author", "Clinical Informatics Team"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "test-skill")
    assert topic["author"] == "Clinical Informatics Team"


def test_init_default_title_from_kebab(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["diabetes-screening"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "diabetes-screening")
    assert topic["title"] == "Diabetes Screening"


# ── Error handling ─────────────────────────────────────────────────────────────

def test_init_fails_exit_1_if_skill_exists(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    result = runner.invoke(init, ["test-skill"])
    assert result.exit_code == 1


def test_init_fails_exit_2_for_uppercase(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(init, ["MySkill"])
    assert result.exit_code == 2


def test_init_fails_exit_2_for_spaces(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(init, ["my skill"])
    assert result.exit_code == 2


def test_init_creates_plans_tasks_md(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    assert (tmp_repo / "topics" / "test-skill" / "process" / "plans" / "tasks.md").exists()


def test_init_creates_notes_md(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    assert (tmp_repo / "topics" / "test-skill" / "process" / "notes.md").exists()


def test_init_does_not_create_research_md(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    assert not (tmp_repo / "topics" / "test-skill" / "process" / "research.md").exists()


def test_init_does_not_create_conflicts_md(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    assert not (tmp_repo / "topics" / "test-skill" / "process" / "conflicts.md").exists()


def test_init_tracking_has_topic_created_root_event(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    root_event_types = [e["type"] for e in data["events"]]
    assert "topic_created" in root_event_types


def test_init_topic_structured_is_list(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-skill"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "test-skill")
    assert isinstance(topic["structured"], list)
    assert isinstance(topic["computable"], list)
