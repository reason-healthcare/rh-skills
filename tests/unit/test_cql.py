"""Tests for rh-skills cql commands (validate, translate, test) — deferred stubs."""
from __future__ import annotations

import json
from pathlib import Path

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


def test_validate_cql_not_found(tmp_path, monkeypatch):
    root = tmp_path / "topics" / "test-topic" / "computable"
    root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cql, ["validate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_validate_deferred_exits_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "deferred" in result.output.lower()


# ── translate ─────────────────────────────────────────────────────────────────


def test_translate_cql_not_found(tmp_path, monkeypatch):
    root = tmp_path / "topics" / "test-topic" / "computable"
    root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cql, ["translate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_translate_deferred_exits_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "deferred" in result.output.lower()


# ── test ──────────────────────────────────────────────────────────────────────


def test_test_no_fixtures_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0


def test_test_deferred_lists_cases(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    runner = CliRunner()
    result = runner.invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code == 0
    assert "deferred" in result.output.lower()
    assert "case-001-basic" in result.output
