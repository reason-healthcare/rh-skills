"""Tests for hi validate command — ported from tests/unit/validate.bats."""

import pytest
from click.testing import CliRunner

from hi.commands.validate import validate


def make_valid_l2(tmp_repo, skill="my-skill", artifact="test-artifact"):
    td = tmp_repo / "topics" / skill / "structured"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
id: {artifact}
name: TestArtifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: diabetes
description: |
  A test artifact for validation testing.
derived_from:
  - source-l1
""")


def make_invalid_l2(tmp_repo, skill="my-skill", artifact="bad-artifact"):
    td = tmp_repo / "topics" / skill / "structured"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
name: BadArtifact
description: "Incomplete artifact"
""")


def make_valid_l3(tmp_repo, skill="my-skill", artifact="test-l3"):
    td = tmp_repo / "topics" / skill / "computable"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
artifact_schema_version: "1.0"
metadata:
  id: {artifact}
  name: TestL3
  title: "Test L3 Artifact"
  version: "1.0.0"
  status: draft
  domain: diabetes
  created_date: "2026-04-03"
  description: |
    A valid L3 artifact for testing.
converged_from:
  - test-l2-artifact
""")


# ── L2 validation tests ────────────────────────────────────────────────────────

def test_validate_valid_l2_exits_0(tmp_repo):
    make_valid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "test-artifact"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_invalid_l2_exits_1(tmp_repo):
    make_invalid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "bad-artifact"])
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_validate_missing_required_field_reported(tmp_repo):
    make_invalid_l2(tmp_repo, artifact="missing-fields")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "missing-fields"])
    assert result.exit_code == 1
    # Error messages go to stderr but CliRunner mixes them
    assert "MISSING required field" in result.output or "MISSING required field" in (result.output + str(result.exception or ""))


def test_validate_unknown_skill_exits_2(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(validate, ["nonexistent-skill", "l2", "artifact"])
    assert result.exit_code == 2


def test_validate_unknown_artifact_exits_2(tmp_repo):
    (tmp_repo / "topics" / "my-skill" / "structured").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "nonexistent-artifact"])
    assert result.exit_code == 2


def test_validate_invalid_level_exits_2(tmp_repo):
    (tmp_repo / "topics" / "my-skill").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l1", "some-artifact"])
    assert result.exit_code == 2


# ── L3 validation tests ────────────────────────────────────────────────────────

def test_validate_valid_l3_exits_0(tmp_repo):
    make_valid_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_l3_missing_schema_version_exits_1(tmp_repo):
    td = tmp_repo / "topics" / "my-skill" / "computable"
    td.mkdir(parents=True, exist_ok=True)
    (td / "bad-l3.yaml").write_text("""\
metadata:
  id: bad-l3
  name: BadL3
  title: "Bad L3"
  version: "1.0.0"
  status: draft
  domain: testing
  created_date: "2026-04-03"
  description: "Missing artifact_schema_version"
converged_from:
  - some-l2
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "bad-l3"])
    assert result.exit_code == 1


def test_validate_structured_alias(tmp_repo):
    """Level alias 'structured' should work same as 'l2'."""
    make_valid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "structured", "test-artifact"])
    assert result.exit_code == 0


def test_validate_computable_alias(tmp_repo):
    """Level alias 'computable' should work same as 'l3'."""
    make_valid_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "computable", "test-l3"])
    assert result.exit_code == 0
