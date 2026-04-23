"""Tests for rh-skills cql commands (validate/translate via rh; test eval pending)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rh_skills.commands.cql import cql


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_topic(tmp_path: Path, library: str = "TestLib", content: str = "") -> Path:
    computable = tmp_path / "topics" / "test-topic" / "computable"
    computable.mkdir(parents=True)
    (computable / f"{library}.cql").write_text(content or f"library {library} version '1.0.0'\n")
    return tmp_path


def _make_fixture(tmp_path: Path, library: str, case: str, expected: dict) -> None:
    case_dir = tmp_path / "tests" / "cql" / library / case
    (case_dir / "input").mkdir(parents=True)
    (case_dir / "expected").mkdir(parents=True)
    (case_dir / "input" / "bundle.json").write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": []})
    )
    (case_dir / "expected" / "expression-results.json").write_text(json.dumps(expected))


# ── validate ──────────────────────────────────────────────────────────────────


def test_validate_rh_absent_emits_install_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.delenv("RH_CLI_PATH", raising=False)
    with patch("shutil.which", return_value=None):
        result = CliRunner().invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "cargo" in (result.output + str(result.exception or "")).lower()


def test_validate_cql_not_found(tmp_path, monkeypatch):
    (tmp_path / "topics" / "test-topic" / "computable").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cql, ["validate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_validate_success_exits_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = CliRunner().invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd[1:] == ["cql", "validate", str(tmp_path / "topics/test-topic/computable/TestLib.cql")]


def test_validate_errors_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = CliRunner().invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code != 0


# ── translate ─────────────────────────────────────────────────────────────────


def test_translate_rh_absent_emits_install_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.delenv("RH_CLI_PATH", raising=False)
    with patch("shutil.which", return_value=None):
        result = CliRunner().invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "cargo" in (result.output + str(result.exception or "")).lower()


def test_translate_cql_not_found(tmp_path, monkeypatch):
    (tmp_path / "topics" / "test-topic" / "computable").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cql, ["translate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_translate_success_echoes_elm_path(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = CliRunner().invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "TestLib.json" in result.output
    cmd = mock_run.call_args[0][0]
    assert cmd[1:3] == ["cql", "compile"]


def test_translate_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = CliRunner().invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code != 0


# ── test ──────────────────────────────────────────────────────────────────────


def test_test_no_fixtures_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0


def test_test_eval_pending_lists_cases(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "eval pending" in result.output.lower()
    assert "case-001-basic" in result.output
