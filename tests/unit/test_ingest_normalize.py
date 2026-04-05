"""Tests for hi ingest normalize subcommand."""

import os
from pathlib import Path
from unittest import mock

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


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from normalized.md content."""
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    y = YAML(typ="safe")
    return y.load(parts[1]) or {}


def _register_source(tmp_repo, name, ext=".txt"):
    """Register a source in tracking.yaml."""
    y = YAML()
    y.default_flow_style = False
    tf = tmp_repo / "tracking.yaml"
    data = y.load(tf.read_text())
    data["sources"].append({
        "name": name,
        "file": f"sources/{name}{ext}",
        "type": "document",
        "checksum": "abc",
        "ingested_at": "2025-01-01T00:00:00Z",
        "text_extracted": False,
    })
    y.dump(data, tf)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_normalize_txt(tmp_repo):
    """Normalize a .txt file; verify normalized.md created with correct frontmatter."""
    src = tmp_repo / "my-source.txt"
    src.write_text("Hello world content")
    _register_source(tmp_repo, "my-source", ".txt")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "normalize", str(src), "--topic", "test-topic",
    ])
    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "my-source.md"
    assert norm.exists()
    content = norm.read_text()
    fm = _parse_frontmatter(content)
    assert fm["text_extracted"] is True
    assert fm["source"] == "my-source"
    assert fm["topic"] == "test-topic"
    assert "Hello world content" in content


def test_normalize_md(tmp_repo):
    """Normalize a .md file; frontmatter correct, body preserved."""
    src = tmp_repo / "guide.md"
    src.write_text("# Clinical Guide\nSome content here.")
    _register_source(tmp_repo, "guide", ".md")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "normalize", str(src), "--topic", "health-topic",
    ])
    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "guide.md"
    assert norm.exists()
    fm = _parse_frontmatter(norm.read_text())
    assert fm["text_extracted"] is True
    assert "# Clinical Guide" in norm.read_text()


def test_normalize_pdf_pdftotext_available(tmp_repo):
    """Mock pdftotext present; verify text_extracted: true."""
    src = tmp_repo / "report.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    _register_source(tmp_repo, "report", ".pdf")

    mock_result = mock.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Extracted PDF content"

    with mock.patch("shutil.which", return_value="/usr/bin/pdftotext"), \
         mock.patch("subprocess.run", return_value=mock_result):
        runner = CliRunner()
        result = runner.invoke(ingest, [
            "normalize", str(src), "--topic", "test-topic",
        ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "report.md"
    fm = _parse_frontmatter(norm.read_text())
    assert fm["text_extracted"] is True
    assert "Extracted PDF content" in norm.read_text()


def test_normalize_pdf_pdftotext_absent(tmp_repo):
    """Mock pdftotext absent; exit 0, text_extracted: false."""
    src = tmp_repo / "report.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    _register_source(tmp_repo, "report", ".pdf")

    with mock.patch("shutil.which", return_value=None):
        runner = CliRunner()
        result = runner.invoke(ingest, [
            "normalize", str(src), "--topic", "test-topic",
        ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "report.md"
    assert norm.exists()
    fm = _parse_frontmatter(norm.read_text())
    assert fm["text_extracted"] is False


def test_normalize_docx_pandoc_available(tmp_repo):
    """Mock pandoc present for .docx; text_extracted: true."""
    src = tmp_repo / "doc.docx"
    src.write_bytes(b"fake docx content")
    _register_source(tmp_repo, "doc", ".docx")

    mock_result = mock.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "# Word Document Content"

    with mock.patch("shutil.which", return_value="/usr/bin/pandoc"), \
         mock.patch("subprocess.run", return_value=mock_result):
        runner = CliRunner()
        result = runner.invoke(ingest, [
            "normalize", str(src), "--topic", "test-topic",
        ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "doc.md"
    fm = _parse_frontmatter(norm.read_text())
    assert fm["text_extracted"] is True


def test_normalize_docx_pandoc_absent(tmp_repo):
    """Mock pandoc absent for .docx; exit 0, text_extracted: false."""
    src = tmp_repo / "doc.docx"
    src.write_bytes(b"fake docx content")
    _register_source(tmp_repo, "doc", ".docx")

    with mock.patch("shutil.which", return_value=None):
        runner = CliRunner()
        result = runner.invoke(ingest, [
            "normalize", str(src), "--topic", "test-topic",
        ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "doc.md"
    assert norm.exists()
    fm = _parse_frontmatter(norm.read_text())
    assert fm["text_extracted"] is False


def test_normalize_source_normalized_event(tmp_repo):
    """Verify source_normalized event appended to tracking.yaml."""
    src = tmp_repo / "notes.txt"
    src.write_text("Clinical notes")
    _register_source(tmp_repo, "notes", ".txt")

    runner = CliRunner()
    runner.invoke(ingest, ["normalize", str(src), "--topic", "test-topic"])

    tracking = load_tracking(tmp_repo)
    event_types = [e["type"] for e in tracking.get("events", [])]
    assert "source_normalized" in event_types


def test_normalize_unknown_source_no_crash(tmp_repo):
    """Normalize a file not registered in tracking.yaml; should succeed without crash."""
    src = tmp_repo / "mystery.txt"
    src.write_text("Some mysterious content")
    # Do NOT register in tracking.yaml

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "normalize", str(src), "--topic", "test-topic",
    ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "mystery.md"
    assert norm.exists()
