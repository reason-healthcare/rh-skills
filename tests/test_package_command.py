"""Integration-style tests for the rh-skills package command."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from rh_skills.commands.package import package
from tests.conftest import load_tracking, make_tracking


@pytest.fixture
def packagable_topic(tmp_repo):
    """Create a topic with computable FHIR JSON + CQL artifacts."""
    topic_dir = tmp_repo / "topics" / "test-topic"
    computable_dir = topic_dir / "computable"
    computable_dir.mkdir(parents=True)

    pd = {
        "resourceType": "PlanDefinition",
        "id": "test-rules",
        "type": {"coding": [{"code": "eca-rule"}]},
        "action": [{"title": "Step 1"}],
    }
    (computable_dir / "PlanDefinition-test-rules.json").write_text(json.dumps(pd, indent=2))

    lib = {
        "resourceType": "Library",
        "id": "test-rules-library",
        "type": {"coding": [{"code": "logic-library"}]},
    }
    (computable_dir / "Library-test-rules-library.json").write_text(json.dumps(lib, indent=2))

    (computable_dir / "TestRulesLogic.cql").write_text(
        "library TestRulesLogic version '1.0.0'\nusing FHIR version '4.0.1'\n"
    )

    make_tracking(tmp_repo, topics=[{
        "name": "test-topic",
        "structured": [],
        "computable": [{
            "name": "test-rules",
            "files": ["topics/test-topic/computable/PlanDefinition-test-rules.json"],
            "checksums": {},
            "converged_from": ["test-rules"],
            "strategy": "decision-table",
        }],
        "events": [],
    }])

    return tmp_repo


def _ok(stdout: str = ""):
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


class TestPackageCommand:
    def test_dry_run(self, packagable_topic, monkeypatch):
        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        runner = CliRunner()
        result = runner.invoke(package, ["test-topic", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "reason.test-topic" in result.output
        assert "Canonical L3 source" in result.output
        assert "package-workspace" in result.output
        assert "package check" in result.output
        assert "Build output:" in result.output
        assert "[defaulted (<workspace>/output)]" in result.output
        assert "package build" in result.output
        assert "--out" not in result.output

    def test_basic_package_runs_rh_pipeline_and_updates_tracking(self, packagable_topic, monkeypatch):
        calls = []

        def fake_run(args):
            calls.append(args)
            return _ok()

        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        monkeypatch.setattr("rh_skills.commands.package._run_rh_command", fake_run)

        runner = CliRunner()
        result = runner.invoke(package, ["test-topic"])
        assert result.exit_code == 0, result.output
        assert "package_created" in result.output

        workspace_dir = packagable_topic / "topics" / "test-topic" / "process" / "package-workspace"
        assert (workspace_dir / "packager.toml").exists()
        assert (workspace_dir / "ImplementationGuide.json").exists()
        assert (workspace_dir / "input" / "resources" / "ImplementationGuide.json").exists()
        assert (workspace_dir / "input" / "examples" / "PlanDefinition-test-rules.json").exists()
        assert (workspace_dir / "input" / "cql" / "TestRulesLogic.cql").exists()

        assert calls == [
            ["/fake/rh", "package", "check", str(workspace_dir)],
            ["/fake/rh", "package", "build", str(workspace_dir)],
        ]

        tracking = load_tracking(packagable_topic)
        topic = next(t for t in tracking["topics"] if t["name"] == "test-topic")
        assert any(e["type"] == "package_created" for e in topic["events"])

    def test_check_only_skips_build(self, packagable_topic, monkeypatch):
        calls = []

        def fake_run(args):
            calls.append(args)
            return _ok("check ok")

        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        monkeypatch.setattr("rh_skills.commands.package._run_rh_command", fake_run)

        runner = CliRunner()
        result = runner.invoke(package, ["test-topic", "--check-only"])
        assert result.exit_code == 0
        assert "Package source check passed." in result.output
        assert len(calls) == 1
        assert calls[0][1:3] == ["package", "check"]

    def test_pack_runs_pack_after_build(self, packagable_topic, monkeypatch):
        calls = []

        def fake_run(args):
            calls.append(args)
            return _ok()

        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        monkeypatch.setattr("rh_skills.commands.package._run_rh_command", fake_run)

        runner = CliRunner()
        result = runner.invoke(package, ["test-topic", "--pack"])
        assert result.exit_code == 0, result.output
        assert [call[1:3] for call in calls] == [
            ["package", "check"],
            ["package", "build"],
            ["package", "pack"],
        ]
        workspace_dir = packagable_topic / "topics" / "test-topic" / "process" / "package-workspace"
        assert calls[2] == ["/fake/rh", "package", "pack", str(workspace_dir / "output")]

    def test_output_dir_override_passes_out_to_build_and_pack(self, packagable_topic, monkeypatch):
        calls = []

        def fake_run(args):
            calls.append(args)
            return _ok()

        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        monkeypatch.setattr("rh_skills.commands.package._run_rh_command", fake_run)

        runner = CliRunner()
        result = runner.invoke(package, ["test-topic", "--pack", "--output-dir", "/tmp/pkg-out"])
        assert result.exit_code == 0, result.output

        workspace_dir = packagable_topic / "topics" / "test-topic" / "process" / "package-workspace"
        assert calls == [
            ["/fake/rh", "package", "check", str(workspace_dir)],
            ["/fake/rh", "package", "build", str(workspace_dir), "--out", "/tmp/pkg-out"],
            ["/fake/rh", "package", "pack", "/tmp/pkg-out"],
        ]

    def test_dry_run_with_output_dir_shows_override_and_out(self, packagable_topic, monkeypatch):
        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        runner = CliRunner()
        result = runner.invoke(package, ["test-topic", "--dry-run", "--output-dir", "/tmp/pkg-out"])
        assert result.exit_code == 0
        assert "Build output: /tmp/pkg-out [overridden (--output-dir)]" in result.output
        assert "Build command: /fake/rh package build" in result.output
        assert "--out /tmp/pkg-out" in result.output

    def test_no_computable_resources(self, tmp_repo):
        make_tracking(tmp_repo, topics=[{
            "name": "empty-topic",
            "structured": [],
            "computable": [],
            "events": [],
        }])
        runner = CliRunner()
        result = runner.invoke(package, ["empty-topic"])
        assert result.exit_code != 0

    def test_topic_not_found(self, packagable_topic):
        runner = CliRunner()
        result = runner.invoke(package, ["nonexistent-topic"])
        assert result.exit_code != 0

    def test_failed_rh_check_exits_nonzero(self, packagable_topic, monkeypatch):
        def fake_run(args):
            return SimpleNamespace(returncode=1, stdout="", stderr="check failed")

        monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
        monkeypatch.setattr("rh_skills.commands.package._run_rh_command", fake_run)

        runner = CliRunner()
        result = runner.invoke(package, ["test-topic"])
        assert result.exit_code == 1
        assert "check failed" in result.output
