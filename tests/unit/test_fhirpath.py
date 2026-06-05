"""Tests for rh-skills fhirpath commands."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from rh_skills.commands.fhirpath import fhirpath


def _make_data_file(tmp_path: Path) -> Path:
    data_file = tmp_path / "patient.json"
    data_file.write_text(json.dumps({"resourceType": "Patient", "active": True}))
    return data_file


def test_parse_rh_absent_emits_install_hint(monkeypatch):
    monkeypatch.delenv("RH_CLI_PATH", raising=False)
    with patch("shutil.which", return_value=None):
        result = CliRunner().invoke(fhirpath, ["parse", "Patient.active"])
    assert result.exit_code != 0
    assert "cargo" in (result.output + str(result.exception or "")).lower()


def test_parse_success_exits_zero(monkeypatch):
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = CliRunner().invoke(fhirpath, ["parse", "Patient.active", "--format", "json"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd == ["/fake/rh", "fhirpath", "parse", "Patient.active", "--format", "json"]


def test_eval_requires_existing_data_file(tmp_path, monkeypatch):
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    missing = tmp_path / "missing.json"
    result = CliRunner().invoke(fhirpath, ["eval", "Patient.active", "--data", str(missing)])
    assert result.exit_code != 0


def test_eval_success_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    data_file = _make_data_file(tmp_path)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = CliRunner().invoke(
            fhirpath,
            ["eval", "active", "--data", str(data_file), "--format", "pretty"],
        )
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd == ["/fake/rh", "fhirpath", "eval", "active", "--data", str(data_file), "--format", "pretty"]
