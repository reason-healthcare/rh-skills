"""Tests for rh-skills ingest implement local registration behavior."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.ingest import ingest


@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Set up a minimal repo root with tracking.yaml."""
    monkeypatch.setenv("RH_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("RH_TRACKING_FILE", str(tmp_path / "tracking.yaml"))
    monkeypatch.setenv("RH_SOURCES_ROOT", str(tmp_path / "sources"))

    tracking = tmp_path / "tracking.yaml"
    tracking.write_text("schema_version: '1.0'\nsources: []\ntopics: []\nevents: []\n")
    (tmp_path / "sources").mkdir()
    return tmp_path


def test_ingest_implement_rejects_url_option(tmp_repo):
    """URL acquisition is no longer supported by ingest implement."""
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", "--url", "https://example.com/x.pdf"])

    assert result.exit_code != 0
    assert "No such option: --url" in result.output


def test_ingest_implement_rejects_type_option(tmp_repo):
    """Registration-time type hints are inferred for local files, not user-supplied."""
    src = tmp_repo / "guide.pdf"
    src.write_bytes(b"PDF content")

    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", str(src), "--type", "document"])

    assert result.exit_code != 0
    assert "No such option: --type" in result.output


# ── FILE argument tests ────────────────────────────────────────────────────────

def test_ingest_implement_file_registers_single_source(tmp_repo):
    """FILE argument registers exactly that file in tracking.yaml."""
    src = tmp_repo / "guide.pdf"
    src.write_bytes(b"PDF content")

    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", str(src)])

    assert result.exit_code == 0, result.output
    y = YAML(typ="safe")
    tracking = y.load((tmp_repo / "tracking.yaml").read_text())
    assert len(tracking["sources"]) == 1
    assert tracking["sources"][0]["name"] == "guide_pdf"


def test_ingest_implement_file_with_topic_stamps_metadata(tmp_repo):
    """FILE + --topic stamps the topic field on the registered source."""
    src = tmp_repo / "sources" / "protocol.docx"
    src.write_bytes(b"DOCX")

    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", str(src), "--topic", "diabetes-ccm"])

    assert result.exit_code == 0, result.output
    y = YAML(typ="safe")
    tracking = y.load((tmp_repo / "tracking.yaml").read_text())
    assert tracking["sources"][0]["topic"] == "diabetes-ccm"


def test_ingest_implement_no_args_shows_usage_error(tmp_repo):
    """Calling implement with no FILE argument should produce a UsageError."""
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement"])

    assert result.exit_code != 0
    assert "FILE" in result.output or "Missing argument" in result.output
