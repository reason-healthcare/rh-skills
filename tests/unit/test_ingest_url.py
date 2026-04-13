"""Tests for rh-skills ingest implement --url flag."""

import os
import tempfile
from pathlib import Path

import pytest
import httpx
from click.testing import CliRunner

from hi.commands.ingest import ingest


@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Set up a minimal repo root with tracking.yaml."""
    monkeypatch.setenv("HI_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HI_TRACKING_FILE", str(tmp_path / "tracking.yaml"))
    monkeypatch.setenv("HI_SOURCES_ROOT", str(tmp_path / "sources"))

    tracking = tmp_path / "tracking.yaml"
    tracking.write_text(
        "schema_version: '1.0'\nsources: []\ntopics: []\nevents: []\n"
    )
    (tmp_path / "sources").mkdir()
    return tmp_path


# ── URL download: success ─────────────────────────────────────────────────────

def test_ingest_implement_url_pdf(httpx_mock, tmp_repo):
    """Download a PDF from URL, verify file written + SHA-256 computed + tracking updated."""
    pdf_content = b"%PDF-1.4 fake pdf content"
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/guide.pdf",
        content=pdf_content,
        headers={"content-type": "application/pdf"},
    )

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "implement",
        "--url", "https://example.com/guide.pdf",
        "--name", "test-guide",
        "--type", "clinical-guideline",
    ])

    assert result.exit_code == 0, result.output
    assert "✓ Downloaded: sources/test-guide.pdf" in result.output
    assert "SHA-256:" in result.output

    saved = tmp_repo / "sources" / "test-guide.pdf"
    assert saved.exists()
    assert saved.read_bytes() == pdf_content


def test_ingest_implement_url_html(httpx_mock, tmp_repo):
    """Download HTML page, verify .html extension inferred from content-type."""
    httpx_mock.add_response(
        method="GET",
        url="https://cms.gov/program",
        content=b"<html><body>CMS Program</body></html>",
        headers={"content-type": "text/html; charset=utf-8"},
    )

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "implement",
        "--url", "https://cms.gov/program",
        "--name", "cms-program",
    ])

    assert result.exit_code == 0
    saved = tmp_repo / "sources" / "cms-program.html"
    assert saved.exists()


def test_ingest_implement_url_registers_in_tracking(httpx_mock, tmp_repo):
    """Verify source_ingested event is added to tracking.yaml."""
    from ruamel.yaml import YAML

    httpx_mock.add_response(
        method="GET",
        url="https://example.com/doc.pdf",
        content=b"%PDF fake",
        headers={"content-type": "application/pdf"},
    )

    runner = CliRunner()
    runner.invoke(ingest, [
        "implement", "--url", "https://example.com/doc.pdf", "--name", "my-doc",
    ])

    y = YAML(typ="safe")
    tracking = y.load((tmp_repo / "tracking.yaml").read_text())
    sources = tracking["sources"]
    assert len(sources) == 1
    assert sources[0]["name"] == "my-doc"
    assert sources[0]["downloaded"] is True
    assert sources[0]["checksum"] != ""

    events = tracking["events"]
    event_types = [e["type"] for e in events]
    assert "source_ingested" in event_types


# ── URL download: MIME fallback ───────────────────────────────────────────────

def test_ingest_implement_url_unknown_mime_uses_url_ext(httpx_mock, tmp_repo):
    """Fall back to URL path extension when Content-Type is unknown."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/report.docx",
        content=b"fake docx",
        headers={"content-type": "application/octet-stream"},
    )

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "implement", "--url", "https://example.com/report.docx", "--name", "report",
    ])

    assert result.exit_code == 0
    # .docx inferred from URL
    saved = tmp_repo / "sources" / "report.docx"
    assert saved.exists()


# ── URL download: auth redirect ───────────────────────────────────────────────

def test_ingest_implement_url_auth_redirect_exit_3(tmp_repo):
    """Detect auth redirect (final URL contains 'login') and exit 3."""
    # Patch httpx.get to return a response with a final redirect URL containing 'login'
    import unittest.mock as mock

    mock_response = mock.MagicMock()
    mock_response.url = httpx.URL("https://journal.com/login?return=/article/123")
    mock_response.raise_for_status = mock.MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"Please log in"

    with mock.patch("httpx.get", return_value=mock_response):
        runner = CliRunner()
        result = runner.invoke(ingest, [
            "implement",
            "--url", "https://journal.com/article/123",
            "--name", "auth-article",
        ])

    assert result.exit_code == 3
    # No file should be written
    assert not (tmp_repo / "sources" / "auth-article.html").exists()


# ── URL download: already exists ──────────────────────────────────────────────

def test_ingest_implement_url_already_exists_exit_2(httpx_mock, tmp_repo):
    """Exit 2 when destination file already exists."""
    existing = tmp_repo / "sources" / "dup-source.pdf"
    existing.write_bytes(b"already here")

    httpx_mock.add_response(
        method="GET",
        url="https://example.com/dup.pdf",
        content=b"new content",
        headers={"content-type": "application/pdf"},
    )

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "implement",
        "--url", "https://example.com/dup.pdf",
        "--name", "dup-source",
    ])

    assert result.exit_code == 2
    # Original file not overwritten
    assert existing.read_bytes() == b"already here"


# ── URL download: network error ───────────────────────────────────────────────

def test_ingest_implement_url_network_error(httpx_mock, tmp_repo):
    """Exit 1 on network error."""
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "implement",
        "--url", "https://unreachable.example.com/doc.pdf",
        "--name", "unreachable",
    ])

    assert result.exit_code == 1


# ── Missing --name flag ───────────────────────────────────────────────────────

def test_ingest_implement_url_missing_name(tmp_repo):
    """--url without --name should produce a usage error."""
    runner = CliRunner()
    result = runner.invoke(ingest, [
        "implement", "--url", "https://example.com/doc.pdf",
    ])

    assert result.exit_code != 0
