"""Tests for rh-skills ingest command — plan / implement / verify."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from hi.commands.ingest import ingest
from tests.conftest import load_tracking


# ── rh-skills ingest plan ─────────────────────────────────────────────────────────────

def test_plan_creates_ingest_plan_md(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(ingest, ["plan"])
    assert result.exit_code == 0, result.output
    plan_file = tmp_repo / "plans" / "ingest-plan.md"
    assert plan_file.exists()


def test_plan_has_yaml_front_matter(tmp_repo):
    runner = CliRunner()
    runner.invoke(ingest, ["plan"])
    content = (tmp_repo / "plans" / "ingest-plan.md").read_text()
    assert content.startswith("---")
    assert "sources:" in content


def test_plan_rerun_guard(tmp_repo):
    runner = CliRunner()
    runner.invoke(ingest, ["plan"])
    result = runner.invoke(ingest, ["plan"])
    assert result.exit_code == 0
    assert "already exists" in result.output


# ── rh-skills ingest implement ────────────────────────────────────────────────────────

def test_implement_registers_source_in_tracking(tmp_repo):
    src = tmp_repo / "test-source.md"
    src.write_text("# Test source\nSome clinical content.")
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", str(src)])
    assert result.exit_code == 0, result.output
    tracking = load_tracking(tmp_repo)
    names = [s["name"] for s in tracking["sources"]]
    assert "test-source" in names


def test_implement_stores_checksum(tmp_repo):
    import hashlib
    src = tmp_repo / "guideline.md"
    content = "# Clinical guideline content"
    src.write_text(content)
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    tracking = load_tracking(tmp_repo)
    entry = next(s for s in tracking["sources"] if s["name"] == "guideline")
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert entry["checksum"] == expected


def test_implement_stores_ingested_at_timestamp(tmp_repo):
    src = tmp_repo / "report.md"
    src.write_text("Report content")
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    tracking = load_tracking(tmp_repo)
    entry = next(s for s in tracking["sources"] if s["name"] == "report")
    assert "ingested_at" in entry
    assert entry["ingested_at"]  # non-empty


def test_implement_appends_source_added_event(tmp_repo):
    src = tmp_repo / "notes.md"
    src.write_text("Notes")
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    tracking = load_tracking(tmp_repo)
    event_types = [e["type"] for e in tracking.get("events", [])]
    assert "source_added" in event_types


def test_implement_error_when_file_not_found(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", str(tmp_repo / "nonexistent.pdf")])
    assert result.exit_code != 0


def test_implement_reregisters_changed_source(tmp_repo):
    src = tmp_repo / "updated.md"
    src.write_text("Original content")
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    src.write_text("Updated content")
    result = runner.invoke(ingest, ["implement", str(src)])
    assert result.exit_code == 0, result.output
    tracking = load_tracking(tmp_repo)
    entries = [s for s in tracking["sources"] if s["name"] == "updated"]
    assert len(entries) == 1  # still one entry, not duplicated


# ── rh-skills ingest verify ───────────────────────────────────────────────────────────

def test_verify_exits_zero_for_unchanged_file(tmp_repo):
    src = tmp_repo / "stable.md"
    src.write_text("Stable content")
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    result = runner.invoke(ingest, ["verify"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_verify_detects_modified_file(tmp_repo):
    src = tmp_repo / "mutable.md"
    src.write_text("Original content")
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    # Modify the copied file in sources/
    sources_copy = tmp_repo / "sources" / "mutable.md"
    sources_copy.write_text("Modified content")
    result = runner.invoke(ingest, ["verify"])
    assert result.exit_code != 0
    assert "CHANGED" in result.output


def test_verify_detects_missing_file(tmp_repo):
    src = tmp_repo / "ephemeral.md"
    src.write_text("Will be deleted")
    runner = CliRunner()
    runner.invoke(ingest, ["implement", str(src)])
    (tmp_repo / "sources" / "ephemeral.md").unlink()
    result = runner.invoke(ingest, ["verify"])
    assert result.exit_code != 0
    assert "MISSING" in result.output


def test_verify_no_sources_exits_cleanly(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(ingest, ["verify"])
    assert result.exit_code == 0
    assert "No" in result.output
