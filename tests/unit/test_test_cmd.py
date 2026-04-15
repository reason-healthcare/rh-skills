"""Tests for rh-skills test command — ported from tests/unit/test-cmd.bats."""

import json

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.test_cmd import test


def setup_skill_with_fixture(tmp_repo, skill="my-skill", fixture_name="my-fixture"):
    """Create skill + tracking entry + fixture file."""
    skill_dir = tmp_repo / "topics" / skill
    (skill_dir / "process" / "fixtures" / "results").mkdir(parents=True, exist_ok=True)
    (skill_dir / "structured").mkdir(parents=True, exist_ok=True)
    (skill_dir / "computable").mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    if not any(t["name"] == skill for t in tracking["topics"]):
        tracking["topics"].append({
            "name": skill,
            "title": "Test Topic",
            "author": "test",
            "created_at": "2026-04-03T00:00:00Z",
            "structured": [],
            "computable": [],
            "events": [],
        })
        with open(tracking_path, "w") as f:
            y.dump(tracking, f)

    fixture_file = skill_dir / "process" / "fixtures" / f"{fixture_name}.yaml"
    fixture_file.write_text("""\
system_prompt: "You are a clinical assistant."
user_prompt: "What is HbA1c used for?"
expected_response: "Stub"
compare_mode: contains
""")


# ── Basic functionality ────────────────────────────────────────────────────────

def test_test_runs_all_fixtures_exits_0(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", "Stub response")
    setup_skill_with_fixture(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(test, ["my-skill", "--mode", "contains"])
    assert result.exit_code == 0, result.output
    assert "passed" in result.output


def test_test_writes_results_json(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", "Stub response")
    setup_skill_with_fixture(tmp_repo)
    runner = CliRunner()
    runner.invoke(test, ["my-skill", "--mode", "contains"])
    results_dir = tmp_repo / "topics" / "my-skill" / "process" / "fixtures" / "results"
    json_files = list(results_dir.glob("*.json"))
    assert len(json_files) >= 1


def test_test_result_json_has_correct_structure(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", "Stub response")
    setup_skill_with_fixture(tmp_repo)
    runner = CliRunner()
    runner.invoke(test, ["my-skill", "--mode", "contains"])
    results_dir = tmp_repo / "topics" / "my-skill" / "process" / "fixtures" / "results"
    result_file = sorted(results_dir.glob("*.json"))[0]
    data = json.loads(result_file.read_text())
    assert data["topic"] == "my-skill"


def test_test_result_json_has_summary(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", "Stub response")
    setup_skill_with_fixture(tmp_repo)
    runner = CliRunner()
    runner.invoke(test, ["my-skill", "--mode", "contains"])
    results_dir = tmp_repo / "topics" / "my-skill" / "process" / "fixtures" / "results"
    result_file = sorted(results_dir.glob("*.json"))[0]
    data = json.loads(result_file.read_text())
    assert "summary" in data
    assert "passed" in data["summary"]
    assert "failed" in data["summary"]
    assert "errored" in data["summary"]


def test_test_fixture_option_runs_only_named(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", "Stub response")
    setup_skill_with_fixture(tmp_repo, fixture_name="fixture-a")
    setup_skill_with_fixture(tmp_repo, fixture_name="fixture-b")
    runner = CliRunner()
    result = runner.invoke(test, ["my-skill", "--fixture", "fixture-a", "--mode", "contains"])
    assert result.exit_code == 0
    assert "passed" in result.output


def test_test_exits_1_when_fixture_fails(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", "completely different answer")
    setup_skill_with_fixture(tmp_repo)
    # Overwrite fixture with a non-matching expected
    fixture_file = tmp_repo / "topics" / "my-skill" / "process" / "fixtures" / "my-fixture.yaml"
    fixture_file.write_text("""\
system_prompt: "You are a clinical assistant."
user_prompt: "What is HbA1c?"
expected_response: "NOMATCH_STRING_XYZ"
""")
    runner = CliRunner()
    result = runner.invoke(test, ["my-skill"])
    assert result.exit_code == 1


def test_test_exits_0_with_no_fixtures(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    skill_dir = tmp_repo / "topics" / "my-skill"
    (skill_dir / "process" / "fixtures" / "results").mkdir(parents=True, exist_ok=True)
    (skill_dir / "structured").mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)
    tracking["topics"].append({
        "name": "my-skill",
        "structured": [],
        "computable": [],
        "events": [],
    })
    with open(tracking_path, "w") as f:
        y.dump(tracking, f)

    runner = CliRunner()
    result = runner.invoke(test, ["my-skill"])
    assert result.exit_code == 0


def test_test_exits_2_for_unknown_skill(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    runner = CliRunner()
    result = runner.invoke(test, ["nonexistent-skill"])
    assert result.exit_code == 2


def test_test_exits_2_for_nonexistent_named_fixture(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_skill_with_fixture(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(test, ["my-skill", "--fixture", "no-such-fixture"])
    assert result.exit_code == 2
