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


def test_ingest_implement_registers_all_untracked_when_file_omitted(tmp_repo):
    """`ingest implement --all` registers all untracked files in sources/."""
    (tmp_repo / "sources" / "a.pdf").write_bytes(b"A")
    (tmp_repo / "sources" / "b.md").write_text("B")

    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", "--all"])

    assert result.exit_code == 0, result.output
    assert "Registered 2 untracked file(s)" in result.output

    y = YAML(typ="safe")
    tracking = y.load((tmp_repo / "tracking.yaml").read_text())
    names = {s["name"] for s in tracking["sources"]}
    assert names == {"a_pdf", "b_md"}


def test_ingest_implement_all_no_untracked_is_noop(tmp_repo):
    """`ingest implement --all` is a no-op when sources/ is already tracked."""
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", "--all"])

    assert result.exit_code == 0, result.output
    assert "No untracked files in sources/" in result.output


def test_ingest_implement_no_args_shows_usage_error(tmp_repo):
    """No FILE and no --all should produce a UsageError."""
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement"])

    assert result.exit_code != 0
    assert "--all" in result.output


def test_ingest_implement_all_applies_topic_to_registered_sources(tmp_repo):
    """Bulk registration should stamp topic metadata when --topic is provided."""
    (tmp_repo / "sources" / "topic-doc.pdf").write_bytes(b"PDF")

    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", "--all", "--topic", "hypertension"])

    assert result.exit_code == 0, result.output
    y = YAML(typ="safe")
    tracking = y.load((tmp_repo / "tracking.yaml").read_text())
    assert tracking["sources"][0]["topic"] == "hypertension"


def test_ingest_implement_rejects_url_option(tmp_repo):
    """URL acquisition is no longer supported by ingest implement."""
    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", "--url", "https://example.com/x.pdf"])

    assert result.exit_code != 0
    assert "No such option: --url" in result.output


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


def test_ingest_implement_file_and_all_are_mutually_exclusive(tmp_repo):
    """Passing both FILE and --all should produce a UsageError."""
    src = tmp_repo / "sources" / "doc.pdf"
    src.write_bytes(b"X")

    runner = CliRunner()
    result = runner.invoke(ingest, ["implement", str(src), "--all"])

    assert result.exit_code != 0
    assert "--all" in result.output

