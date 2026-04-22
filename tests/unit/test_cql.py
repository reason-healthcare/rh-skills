"""Tests for rh-skills cql commands (validate, translate, test)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rh_skills.commands.cql import cql


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_topic(tmp_path: Path, library: str = "TestLib", content: str = "") -> Path:
    """Create a minimal topic/computable directory with a .cql file."""
    computable = tmp_path / "topics" / "test-topic" / "computable"
    computable.mkdir(parents=True)
    cql_file = computable / f"{library}.cql"
    cql_file.write_text(content or f"library {library} version '1.0.0'\n")
    return tmp_path


def _make_fixture(tmp_path: Path, library: str, case: str, expected: dict) -> None:
    """Create a test fixture directory with input bundle and expected results."""
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
        runner = CliRunner()
        result = runner.invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code != 0
    output = (result.output or "") + str(result.exception or "")
    assert "install" in output.lower() or "cargo" in output.lower()


def test_validate_cql_not_found(tmp_path, monkeypatch):
    root = tmp_path / "topics" / "test-topic" / "computable"
    root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RH_CLI_PATH", "/usr/bin/rh")
    runner = CliRunner()
    result = runner.invoke(cql, ["validate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_validate_success_exits_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        runner = CliRunner()
        result = runner.invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[1] == "cql"
    assert args[2] == "validate"


def test_validate_errors_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        runner = CliRunner()
        result = runner.invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code != 0


# ── translate ─────────────────────────────────────────────────────────────────


def test_translate_success_echoes_elm_path(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    # Create the expected ELM output file to simulate rh writing it
    elm_file = tmp_path / "topics" / "test-topic" / "computable" / "TestLib.json"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        runner = CliRunner()
        result = runner.invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "TestLib.json" in result.output
    args = mock_run.call_args[0][0]
    assert args[1] == "cql"
    assert args[2] == "compile"


def test_translate_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        runner = CliRunner()
        result = runner.invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code != 0


# ── test ──────────────────────────────────────────────────────────────────────


def test_test_all_pass_exits_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        runner = CliRunner()
        result = runner.invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_test_one_fail_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    with patch("subprocess.run") as mock_run:
        # rh returns "false" but expected is true
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        runner = CliRunner()
        result = runner.invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "FAIL" in result.output


def test_test_no_fixtures_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    runner = CliRunner()
    result = runner.invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0


def test_test_rh_absent_emits_install_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.delenv("RH_CLI_PATH", raising=False)
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    with patch("shutil.which", return_value=None):
        runner = CliRunner()
        result = runner.invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    output = (result.output or "") + str(result.exception or "")
    assert "install" in output.lower() or "cargo" in output.lower()
