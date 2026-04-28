"""Tests for rh-skills source download --url command."""

import hashlib

import httpx
import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.source import source
from tests.conftest import load_tracking

PDF_BYTES = b"%PDF-1.4 fake pdf content"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _tracking(tmp_repo) -> dict:
    return load_tracking(tmp_repo)


# ── Happy-path tests ───────────────────────────────────────────────────────────


def test_download_url_pdf_registers_source(tmp_repo, httpx_mock):
    """Happy path: PDF downloaded via URL is registered in tracking.yaml."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    assert result.exit_code == 0, result.output
    assert "✓ Downloaded: sources/my-guide.pdf" in result.output

    tracking = _tracking(tmp_repo)
    names = [s["name"] for s in tracking["sources"]]
    assert "my-guide" in names


def test_download_url_writes_file_to_sources(tmp_repo, httpx_mock):
    """Downloaded bytes are persisted inside sources/."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    dest = tmp_repo / "sources" / "my-guide.pdf"
    assert dest.exists()
    assert dest.read_bytes() == PDF_BYTES


def test_download_url_records_checksum(tmp_repo, httpx_mock):
    """Tracking entry carries a correct SHA-256 checksum."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    expected = hashlib.sha256(PDF_BYTES).hexdigest()
    tracking = _tracking(tmp_repo)
    entry = next(s for s in tracking["sources"] if s["name"] == "my-guide")
    assert entry["checksum"] == expected


def test_download_url_records_source_url(tmp_repo, httpx_mock):
    """Tracking entry stores the original URL."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    tracking = _tracking(tmp_repo)
    entry = next(s for s in tracking["sources"] if s["name"] == "my-guide")
    assert entry["url"] == "https://example.com/guide.pdf"


def test_download_url_sets_downloaded_flag(tmp_repo, httpx_mock):
    """Tracking entry has downloaded=True."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    tracking = _tracking(tmp_repo)
    entry = next(s for s in tracking["sources"] if s["name"] == "my-guide")
    assert entry.get("downloaded") is True


def test_download_url_appends_source_ingested_event(tmp_repo, httpx_mock):
    """A source_ingested event is appended to tracking.yaml after download."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    tracking = _tracking(tmp_repo)
    event_types = [e["type"] for e in tracking.get("events", [])]
    assert "source_ingested" in event_types


def test_download_url_with_topic_stamps_metadata(tmp_repo, httpx_mock):
    """--topic option is persisted in the tracking entry."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    runner = CliRunner()
    runner.invoke(
        source,
        [
            "download",
            "--url", "https://example.com/guide.pdf",
            "--name", "my-guide",
            "--topic", "diabetes-ccm",
        ],
    )

    tracking = _tracking(tmp_repo)
    entry = next(s for s in tracking["sources"] if s["name"] == "my-guide")
    assert entry.get("topic") == "diabetes-ccm"


# ── MIME-type / extension mapping ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "content_type,expected_ext",
    [
        ("application/pdf", ".pdf"),
        ("text/html", ".html"),
        ("application/msword", ".doc"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        ),
        ("text/plain", ".txt"),
        ("text/markdown", ".md"),
        ("application/xml", ".xml"),
        ("text/xml", ".xml"),
    ],
)
def test_download_url_mime_extension_mapping(tmp_repo, httpx_mock, content_type, expected_ext):
    """Content-Type header is mapped to the correct file extension."""
    url = "https://example.com/resource"
    httpx_mock.add_response(
        url=url,
        content=b"content",
        headers={"content-type": content_type},
    )
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", url, "--name", "test-source"],
    )

    assert result.exit_code == 0, result.output
    dest = tmp_repo / "sources" / f"test-source{expected_ext}"
    assert dest.exists(), f"Expected {dest} for content-type {content_type!r}"


def test_download_url_unknown_mime_falls_back_to_url_extension(tmp_repo, httpx_mock):
    """When MIME is unrecognised the extension is taken from the URL path."""
    httpx_mock.add_response(
        url="https://example.com/data.csv",
        content=b"a,b,c",
        headers={"content-type": "text/csv"},
    )
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/data.csv", "--name", "my-data"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_repo / "sources" / "my-data.csv").exists()


def test_download_url_unknown_mime_no_url_ext_falls_back_to_bin(tmp_repo, httpx_mock):
    """When neither MIME nor URL extension is known, .bin is used."""
    httpx_mock.add_response(
        url="https://example.com/resource",
        content=b"binary",
        headers={"content-type": "application/octet-stream"},
    )
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/resource", "--name", "my-bin"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_repo / "sources" / "my-bin.bin").exists()


def test_download_url_content_type_with_charset_ignored(tmp_repo, httpx_mock):
    """charset suffix on Content-Type header is stripped before MIME lookup."""
    httpx_mock.add_response(
        url="https://example.com/page",
        content=b"<html/>",
        headers={"content-type": "text/html; charset=utf-8"},
    )
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/page", "--name", "my-page"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_repo / "sources" / "my-page.html").exists()


# ── Error / edge-case tests ───────────────────────────────────────────────────


def test_download_url_missing_name_raises_usage_error(tmp_repo, httpx_mock):
    """--url without --name must produce a UsageError (non-zero exit)."""
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf"],
    )

    assert result.exit_code != 0
    assert "--name is required" in result.output


def test_download_url_auth_redirect_exits_3(tmp_repo):
    """Auth-redirect URL (login marker) causes exit code 3."""
    from unittest.mock import patch, MagicMock

    login_url = "https://example.com/login?next=/guide.pdf"

    mock_response = MagicMock()
    mock_response.url = httpx.URL(login_url)
    mock_response.headers = httpx.Headers({"content-type": "text/html"})
    mock_response.content = b"login page"
    mock_response.raise_for_status = lambda: None

    with patch("httpx.get", return_value=mock_response):
        runner = CliRunner()
        result = runner.invoke(
            source,
            ["download", "--url", "https://example.com/guide.pdf", "--name", "auth-doc"],
        )

    assert result.exit_code == 3


def test_download_url_network_blocked_exits_4(tmp_repo):
    """ConnectError (network blocked) causes exit code 4."""
    from unittest.mock import patch

    with patch("httpx.get", side_effect=httpx.ConnectError("blocked")):
        runner = CliRunner()
        result = runner.invoke(
            source,
            ["download", "--url", "https://example.com/guide.pdf", "--name", "doc"],
        )

    assert result.exit_code == 4


def test_download_url_connect_timeout_exits_4(tmp_repo):
    """ConnectTimeout (network blocked) also causes exit code 4."""
    from unittest.mock import patch

    with patch("httpx.get", side_effect=httpx.ConnectTimeout("timeout")):
        runner = CliRunner()
        result = runner.invoke(
            source,
            ["download", "--url", "https://example.com/guide.pdf", "--name", "doc"],
        )

    assert result.exit_code == 4


def test_download_url_already_exists_exits_2(tmp_repo, httpx_mock):
    """If the destination file already exists on disk, exit code 2 is returned."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        content=PDF_BYTES,
        headers={"content-type": "application/pdf"},
    )
    # Pre-create the destination file
    dest = tmp_repo / "sources" / "my-guide.pdf"
    dest.write_bytes(b"existing content")

    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    assert result.exit_code == 2


def test_download_url_http_error_exits_nonzero(tmp_repo, httpx_mock):
    """A non-2xx HTTP response results in a non-zero exit code."""
    httpx_mock.add_response(
        url="https://example.com/guide.pdf",
        status_code=404,
    )
    runner = CliRunner()
    result = runner.invoke(
        source,
        ["download", "--url", "https://example.com/guide.pdf", "--name", "my-guide"],
    )

    assert result.exit_code != 0
    assert "404" in result.output
