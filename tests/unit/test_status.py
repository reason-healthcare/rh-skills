"""Tests for hi status and hi list commands — ported from tests/unit/status.bats."""

import json

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from hi.commands.status import status
from hi.commands.list_cmd import list_


def load_yaml(path):
    y = YAML()
    with open(path) as f:
        return y.load(f)


def make_topic(tmp_repo, name, stage="initialized"):
    """Create a topic in tracking.yaml at the given stage."""
    td = tmp_repo / "topics" / name
    (td / "structured").mkdir(parents=True, exist_ok=True)
    (td / "computable").mkdir(parents=True, exist_ok=True)
    (td / "fixtures" / "results").mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    # Add source if needed
    if stage in ("l1-discovery", "l2-semi-structured", "l3-computable"):
        src_file = tmp_repo / "sources" / "discovery-1.md"
        src_file.write_text("Raw content")
        if not any(s["name"] == "discovery-1" for s in tracking["sources"]):
            tracking["sources"].append({
                "name": "discovery-1",
                "file": "sources/discovery-1.md",
                "created_at": "2026-04-03T00:00:00Z",
            })

    structured = []
    if stage in ("l2-semi-structured", "l3-computable"):
        structured = [{"name": "criteria-1", "created_at": "2026-04-03T00:00:00Z", "derived_from": ["discovery-1"]}]

    computable = []
    if stage == "l3-computable":
        computable = [{"name": "computable-1", "created_at": "2026-04-03T00:00:00Z", "converged_from": ["criteria-1"]}]

    tracking["topics"].append({
        "name": name,
        "title": "Test Topic",
        "description": "A test topic",
        "author": "Test Author",
        "created_at": "2026-04-03T00:00:00Z",
        "structured": structured,
        "computable": computable,
        "events": [{"timestamp": "2026-04-03T00:00:00Z", "type": "created", "description": "scaffolded"}],
    })

    with open(tracking_path, "w") as f:
        y.dump(tracking, f)


# ── hi status tests ────────────────────────────────────────────────────────────

def test_status_exits_0_for_valid_skill(tmp_repo):
    make_topic(tmp_repo, "my-skill")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill"])
    assert result.exit_code == 0


def test_status_shows_skill_name(tmp_repo):
    make_topic(tmp_repo, "my-skill")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill"])
    assert "my-skill" in result.output


def test_status_shows_stage_initialized(tmp_repo):
    make_topic(tmp_repo, "my-skill", "initialized")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill"])
    assert "initialized" in result.output


def test_status_shows_stage_l1_discovery(tmp_repo):
    make_topic(tmp_repo, "my-skill", "l1-discovery")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill"])
    assert "l1-discovery" in result.output


def test_status_shows_stage_l2_semi_structured(tmp_repo):
    make_topic(tmp_repo, "my-skill", "l2-semi-structured")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill"])
    assert "l2-semi-structured" in result.output


def test_status_shows_stage_l3_computable(tmp_repo):
    make_topic(tmp_repo, "my-skill", "l3-computable")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill"])
    assert "l3-computable" in result.output


def test_status_json_outputs_valid_json(tmp_repo):
    make_topic(tmp_repo, "my-skill", "l2-semi-structured")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, dict)


def test_status_json_includes_artifact_counts(tmp_repo):
    make_topic(tmp_repo, "my-skill", "l2-semi-structured")
    runner = CliRunner()
    result = runner.invoke(status, ["my-skill", "--json"])
    data = json.loads(result.output)
    assert data["structured"] == 1


def test_status_exits_2_for_unknown_skill(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(status, ["ghost-skill"])
    assert result.exit_code == 2


# ── hi list tests ──────────────────────────────────────────────────────────────

def test_list_exits_0_with_no_skills(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(list_, [])
    assert result.exit_code == 0


def test_list_shows_skill_names(tmp_repo):
    make_topic(tmp_repo, "alpha-skill")
    make_topic(tmp_repo, "beta-skill")
    runner = CliRunner()
    result = runner.invoke(list_, [])
    assert "alpha-skill" in result.output
    assert "beta-skill" in result.output


def test_list_json_outputs_array(tmp_repo):
    make_topic(tmp_repo, "my-skill")
    runner = CliRunner()
    result = runner.invoke(list_, ["--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


def test_list_json_includes_name_and_stage(tmp_repo):
    make_topic(tmp_repo, "my-skill", "l1-discovery")
    runner = CliRunner()
    result = runner.invoke(list_, ["--json"])
    data = json.loads(result.output)
    assert data[0]["name"] == "my-skill"
    assert data[0]["stage"] == "l1-discovery"


def test_list_stage_filter(tmp_repo):
    make_topic(tmp_repo, "alpha-skill", "l1-discovery")
    make_topic(tmp_repo, "beta-skill", "l2-semi-structured")
    runner = CliRunner()
    result = runner.invoke(list_, ["--stage", "l1-discovery"])
    assert "alpha-skill" in result.output
    assert "beta-skill" not in result.output


def test_list_stage_l3_computable_filter(tmp_repo):
    make_topic(tmp_repo, "alpha-skill", "l1-discovery")
    make_topic(tmp_repo, "beta-skill", "l3-computable")
    runner = CliRunner()
    result = runner.invoke(list_, ["--stage", "l3-computable"])
    assert "alpha-skill" not in result.output
    assert "beta-skill" in result.output


def test_list_no_tracking_exits_0(tmp_repo):
    """When no tracking.yaml exists, list exits 0 cleanly."""
    (tmp_repo / "tracking.yaml").unlink()
    runner = CliRunner()
    result = runner.invoke(list_, [])
    assert result.exit_code == 0
