"""Tests for rh-skills formalize-config command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.formalize_config import (
    formalize_config,
    load_formalize_config,
    save_formalize_config,
    suggest_defaults,
    config_path,
    CONFIG_FILENAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tracking(tmp_path: Path, topic: str) -> None:
    y = YAML()
    tracking = {
        "topics": [{
            "name": topic,
            "status": "active",
            "structured": [],
            "computable": [],
            "events": [],
        }]
    }
    (tmp_path / "tracking.yaml").write_text("")
    with open(tmp_path / "tracking.yaml", "w") as f:
        y.dump(tracking, f)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestSuggestDefaults:
    def test_basic_slug(self):
        defaults = suggest_defaults("lipid-management", {})
        assert defaults["id"] == "lipid-management"
        assert defaults["name"] == "LipidManagement"
        assert defaults["canonical"] == "http://example.org/fhir"
        assert defaults["status"] == "draft"
        assert defaults["version"] == "0.1.0"

    def test_preserves_existing_values(self):
        existing = {"id": "my-custom-id", "version": "1.2.3"}
        defaults = suggest_defaults("lipid-management", existing)
        assert defaults["id"] == "my-custom-id"
        assert defaults["version"] == "1.2.3"
        assert defaults["name"] == "LipidManagement"  # derived from slug not existing id


class TestLoadSave:
    def test_returns_none_when_missing(self, tmp_path):
        td = tmp_path / "topics" / "my-topic"
        td.mkdir(parents=True)
        assert load_formalize_config(td) is None

    def test_round_trip(self, tmp_path):
        td = tmp_path / "topics" / "my-topic"
        td.mkdir(parents=True)
        cfg = {
            "name": "MyTopic",
            "id": "my-topic",
            "canonical": "http://example.org/fhir",
            "status": "draft",
            "version": "0.1.0",
        }
        save_formalize_config(td, cfg)
        loaded = load_formalize_config(td)
        assert loaded == cfg

    def test_config_path_location(self, tmp_path):
        td = tmp_path / "topics" / "my-topic"
        td.mkdir(parents=True)
        expected = td / "process" / CONFIG_FILENAME
        assert config_path(td) == expected


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestFormalizeConfigCommand:
    @pytest.fixture()
    def repo(self, tmp_path, monkeypatch):
        (tmp_path / "topics" / "my-topic").mkdir(parents=True)
        _write_tracking(tmp_path, "my-topic")
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_creates_config_with_defaults(self, repo):
        runner = CliRunner()
        result = runner.invoke(
            formalize_config, ["my-topic", "--non-interactive"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        cfg = load_formalize_config(repo / "topics" / "my-topic")
        assert cfg is not None
        assert cfg["id"] == "my-topic"
        assert cfg["name"] == "MyTopic"
        assert cfg["status"] == "draft"
        assert cfg["version"] == "0.1.0"

    def test_accepts_explicit_values(self, repo):
        runner = CliRunner()
        result = runner.invoke(
            formalize_config,
            [
                "my-topic",
                "--non-interactive",
                "--name", "CustomName",
                "--id", "custom-id",
                "--canonical", "http://custom.example.com/fhir",
                "--status", "active",
                "--version", "2.0.0",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        cfg = load_formalize_config(repo / "topics" / "my-topic")
        assert cfg["name"] == "CustomName"
        assert cfg["id"] == "custom-id"
        assert cfg["canonical"] == "http://custom.example.com/fhir"
        assert cfg["status"] == "active"
        assert cfg["version"] == "2.0.0"

    def test_shows_written_config(self, repo):
        runner = CliRunner()
        result = runner.invoke(
            formalize_config, ["my-topic", "--non-interactive"],
            catch_exceptions=False,
        )
        assert "formalize-config.yaml" in result.output

    def test_fails_for_unknown_topic(self, repo):
        runner = CliRunner()
        result = runner.invoke(
            formalize_config, ["nonexistent-topic", "--non-interactive"],
        )
        assert result.exit_code != 0

    def test_does_not_overwrite_existing_without_force(self, repo):
        td = repo / "topics" / "my-topic"
        runner = CliRunner()
        # First write
        runner.invoke(formalize_config, ["my-topic", "--non-interactive"], catch_exceptions=False)
        # Second write should warn/skip by default
        result = runner.invoke(
            formalize_config,
            ["my-topic", "--non-interactive", "--version", "9.9.9"],
        )
        cfg = load_formalize_config(td)
        assert cfg["version"] == "0.1.0"  # not overwritten

    def test_force_overwrites_existing(self, repo):
        td = repo / "topics" / "my-topic"
        runner = CliRunner()
        runner.invoke(formalize_config, ["my-topic", "--non-interactive"], catch_exceptions=False)
        result = runner.invoke(
            formalize_config,
            ["my-topic", "--non-interactive", "--force", "--version", "9.9.9"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        cfg = load_formalize_config(td)
        assert cfg["version"] == "9.9.9"
