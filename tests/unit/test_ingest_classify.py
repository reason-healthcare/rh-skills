"""Tests for hi ingest classify subcommand."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from hi.commands.ingest import ingest
from tests.conftest import load_tracking


@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Set up a minimal repo root with tracking.yaml."""
    monkeypatch.setenv("HI_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HI_TRACKING_FILE", str(tmp_path / "tracking.yaml"))
    monkeypatch.setenv("HI_SOURCES_ROOT", str(tmp_path / "sources"))

    tracking = tmp_path / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    y.dump({"schema_version": "1.0", "sources": [], "topics": [], "events": []}, tracking)
    (tmp_path / "sources").mkdir()
    return tmp_path


def _register_source(tmp_repo, name):
    """Register a source in tracking.yaml."""
    y = YAML()
    y.default_flow_style = False
    tf = tmp_repo / "tracking.yaml"
    data = y.load(tf.read_text())
    data["sources"].append({
        "name": name,
        "file": f"sources/{name}.txt",
        "type": "document",
        "checksum": "abc",
        "ingested_at": "2025-01-01T00:00:00Z",
        "text_extracted": False,
    })
    y.dump(data, tf)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_classify_writes_fields(tmp_repo):
    """Classify a registered source; verify type, evidence_level, domain_tags in tracking.yaml."""
    _register_source(tmp_repo, "guideline-src")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "classify", "guideline-src",
        "--topic", "test-topic",
        "--type", "clinical-guideline",
        "--evidence-level", "ia",
        "--tags", "diabetes,screening",
    ])

    assert result.exit_code == 0, result.output
    tracking = load_tracking(tmp_repo)
    src = next(s for s in tracking["sources"] if s["name"] == "guideline-src")
    assert src["type"] == "clinical-guideline"
    assert src["evidence_level"] == "ia"
    assert src["domain_tags"] == ["diabetes", "screening"]
    assert "classified_at" in src


def test_classify_event_appended(tmp_repo):
    """Verify source_classified event in tracking.yaml."""
    _register_source(tmp_repo, "my-source")

    runner = CliRunner()
    runner.invoke(ingest, [
        "classify", "my-source",
        "--topic", "test-topic",
        "--type", "systematic-review",
        "--evidence-level", "ib",
    ])

    tracking = load_tracking(tmp_repo)
    event_types = [e["type"] for e in tracking.get("events", [])]
    assert "source_classified" in event_types


def test_classify_invalid_type_exits_1(tmp_repo):
    """Invalid source type → ClickException (exit 1)."""
    _register_source(tmp_repo, "my-source")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "classify", "my-source",
        "--topic", "test-topic",
        "--type", "not-a-real-type",
        "--evidence-level", "ia",
    ])

    assert result.exit_code == 1
    assert "Invalid type" in result.output


def test_classify_invalid_evidence_level_exits_1(tmp_repo):
    """Invalid evidence level → ClickException (exit 1)."""
    _register_source(tmp_repo, "my-source")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "classify", "my-source",
        "--topic", "test-topic",
        "--type", "clinical-guideline",
        "--evidence-level", "z9",
    ])

    assert result.exit_code == 1
    assert "Invalid evidence level" in result.output


def test_classify_unknown_source_exits_1(tmp_repo):
    """Source not in tracking.yaml → ClickException."""
    runner = CliRunner()
    result = runner.invoke(ingest, [
        "classify", "ghost-source",
        "--topic", "test-topic",
        "--type", "clinical-guideline",
        "--evidence-level", "ia",
    ])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_classify_tags_parsed_as_list(tmp_repo):
    """--tags 'diabetes,screening' → domain_tags: ['diabetes', 'screening']."""
    _register_source(tmp_repo, "tagged-src")

    runner = CliRunner()
    runner.invoke(ingest, [
        "classify", "tagged-src",
        "--topic", "test-topic",
        "--type", "clinical-guideline",
        "--evidence-level", "ia",
        "--tags", "diabetes,screening",
    ])

    tracking = load_tracking(tmp_repo)
    src = next(s for s in tracking["sources"] if s["name"] == "tagged-src")
    assert src["domain_tags"] == ["diabetes", "screening"]


def test_classify_no_tags(tmp_repo):
    """Omitting --tags → domain_tags: []."""
    _register_source(tmp_repo, "no-tags-src")

    runner = CliRunner()
    runner.invoke(ingest, [
        "classify", "no-tags-src",
        "--topic", "test-topic",
        "--type", "clinical-guideline",
        "--evidence-level", "ia",
    ])

    tracking = load_tracking(tmp_repo)
    src = next(s for s in tracking["sources"] if s["name"] == "no-tags-src")
    assert src["domain_tags"] == []
