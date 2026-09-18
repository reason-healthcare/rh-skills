"""Tests for rh-skills cql commands (validate/translate/test via rh)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rh_skills.commands.cql import _strict_json_equal, cql


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


def test_strict_json_equality_distinguishes_boolean_null_and_number():
    assert not _strict_json_equal(True, 1)
    assert not _strict_json_equal(False, 0)
    assert not _strict_json_equal(None, False)
    assert _strict_json_equal(1, 1.0)
    assert not _strict_json_equal({"risk": True}, {"risk": 1})


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
    expected_elm = tmp_path / "topics/test-topic/computable/elm/TestLib.json"
    assert str(expected_elm) in result.output
    cmd = mock_run.call_args[0][0]
    assert cmd[1:3] == ["cql", "compile"]
    assert cmd[-1] == str(expected_elm)


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


def test_test_runs_eval_and_reports_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd[1:3] == ["cql", "eval"]
    assert "PASS IsAdult" in result.output
    assert "case-001-basic" in result.output


def test_test_passes_explicit_evaluation_context_period_and_parameters(tmp_path, monkeypatch):
    topic = _make_topic(
        tmp_path,
        content='library TestLib version \'1.0.0\'\nparameter "Measurement Period" Interval<DateTime>\n',
    )
    monkeypatch.chdir(topic)
    _make_fixture(tmp_path, "TestLib", "case-002-context", {"IsAdult": True})
    case = tmp_path / "tests" / "cql" / "TestLib" / "case-002-context"
    bundle_path = case / "input" / "bundle.json"
    bundle_path.write_text(json.dumps({
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {"resourceType": "Patient", "id": "selected-patient"}}],
    }))
    (case / "input" / "evaluation-context.json").write_text(json.dumps({
        "subject": "Patient/selected-patient",
        "evaluationDate": "2026-06-15T09:20:00Z",
        "measurementPeriod": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
            "startInclusive": True,
            "endInclusive": False,
        },
        "parameters": {"RiskThreshold": 2},
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])

    assert result.exit_code == 0, result.output
    command = mock_run.call_args[0][0]
    assert command[command.index("--subject") + 1] == "Patient/selected-patient"
    assert command[command.index("--evaluation-date") + 1] == "2026-06-15T09:20:00Z"
    assert command[command.index("--measurement-period-start") + 1] == "2026-01-01T00:00:00Z"
    assert command[command.index("--measurement-period-end") + 1] == "2026-12-31T23:59:59Z"
    assert "--parameter" in command
    parameter_pairs = [command[idx + 1] for idx, value in enumerate(command[:-1]) if value == "--parameter"]
    assert "RiskThreshold=2" in parameter_pairs
    assert (
        'Measurement Period={"start":"2026-01-01T00:00:00Z","end":"2026-12-31T23:59:59Z",'
        '"startInclusive":true,"endInclusive":false}'
    ) in parameter_pairs


def test_test_converts_fhir_parameters_file_into_cli_overrides(tmp_path, monkeypatch):
    topic = _make_topic(tmp_path)
    monkeypatch.chdir(topic)
    _make_fixture(tmp_path, "TestLib", "case-003-parameters", {"HasConsent": True})
    case = tmp_path / "tests" / "cql" / "TestLib" / "case-003-parameters"
    (case / "input" / "parameters.json").write_text(json.dumps({
        "resourceType": "Parameters",
        "parameter": [{"name": "HasConsent", "valueBoolean": True}],
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])

    assert result.exit_code == 0, result.output
    command = mock_run.call_args[0][0]
    assert command[command.index("--parameter") + 1] == "HasConsent=true"


def test_test_reports_expression_mismatch(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "expected true, got false" in result.output.lower()


def test_test_rejects_boolean_result_when_expected_value_is_number_one(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": 1})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "expected 1, got true" in result.output.lower()


def test_test_reports_eval_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="compile error")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "compile error" in result.output
