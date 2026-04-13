"""Tests for rh-skills init research tracking extensions (RESEARCH.md + process/research.md)."""

import pytest
from click.testing import CliRunner

from hi.commands.init import init


@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Set up a minimal repo root."""
    monkeypatch.setenv("HI_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HI_TRACKING_FILE", str(tmp_path / "tracking.yaml"))
    monkeypatch.setenv("HI_SOURCES_ROOT", str(tmp_path / "sources"))
    monkeypatch.setenv("HI_TOPICS_ROOT", str(tmp_path / "topics"))
    return tmp_path


def test_init_creates_research_md(tmp_repo):
    """rh-skills init creates RESEARCH.md at repo root."""
    runner = CliRunner()
    result = runner.invoke(init, ["diabetes-ccm"])
    assert result.exit_code == 0, result.output

    portfolio = tmp_repo / "RESEARCH.md"
    assert portfolio.exists(), "RESEARCH.md should be created at repo root"
    content = portfolio.read_text()
    assert "# Research Portfolio" in content
    assert "## Active Topics" in content
    assert "## Completed Topics" in content
    assert "## Deferred Topics" in content


def test_init_appends_active_topics_row(tmp_repo):
    """RESEARCH.md Active Topics table gets a row for the new topic."""
    runner = CliRunner()
    runner.invoke(init, ["diabetes-ccm"])

    portfolio = tmp_repo / "RESEARCH.md"
    content = portfolio.read_text()
    assert "| diabetes-ccm |" in content
    assert "initialized" in content


def test_init_second_topic_appends_row(tmp_repo):
    """A second rh-skills init appends a new row without corrupting existing rows."""
    runner = CliRunner()
    runner.invoke(init, ["diabetes-ccm"])
    runner.invoke(init, ["sepsis-detection"])

    portfolio = tmp_repo / "RESEARCH.md"
    content = portfolio.read_text()
    assert "| diabetes-ccm |" in content
    assert "| sepsis-detection |" in content


def test_init_idempotent_topic_row(tmp_repo):
    """Re-running rh-skills init on the same topic doesn't fail and doesn't duplicate rows."""
    runner = CliRunner()
    runner.invoke(init, ["diabetes-ccm"])

    # Second init on same topic should fail (topic already exists)
    result2 = runner.invoke(init, ["diabetes-ccm"])
    assert result2.exit_code != 0  # expected: click.ClickException("already exists")

    portfolio = tmp_repo / "RESEARCH.md"
    content = portfolio.read_text()
    # Should still have exactly one row for the topic
    assert content.count("| diabetes-ccm |") == 1


def test_init_creates_process_research_md(tmp_repo):
    """rh-skills init creates topics/<name>/process/notes.md with human-annotation sections."""
    runner = CliRunner()
    runner.invoke(init, ["diabetes-ccm"])

    notes_md = tmp_repo / "topics" / "diabetes-ccm" / "process" / "notes.md"
    assert notes_md.exists(), "process/notes.md should be created"
    content = notes_md.read_text()

    assert "# Research Notes" in content
    assert "## Open Questions" in content
    assert "## Decisions" in content
    assert "## Source Conflicts" in content
    assert "## Notes" in content


def test_init_process_research_md_table_headers(tmp_repo):
    """process/notes.md has no Markdown tables — plain bullets only."""
    runner = CliRunner()
    runner.invoke(init, ["sepsis-detection"])

    notes_md = tmp_repo / "topics" / "sepsis-detection" / "process" / "notes.md"
    content = notes_md.read_text()

    assert "| Source |" not in content, "notes.md must not contain Markdown tables"


def test_init_does_not_clobber_existing_research_md(tmp_repo):
    """If RESEARCH.md already exists, rh-skills init appends row without overwriting."""
    # Create pre-existing RESEARCH.md with custom content
    portfolio = tmp_repo / "RESEARCH.md"
    portfolio.write_text("""\
# Research Portfolio

> Managed by `rh-skills`

## Active Topics

| Topic | Stage | Sources | Initialized | Updated | Notes |
|-------|-------|---------|-------------|---------|-------|
| existing-topic | initialized | 3 | 2026-01-01 | 2026-01-01 | |

## Completed Topics

| Topic | Stage | Sources | Completed | Notes |
|-------|-------|---------|-----------|-------|

## Deferred Topics

| Topic | Reason | Deferred | Notes |
|-------|--------|----------|-------|
""")

    runner = CliRunner()
    runner.invoke(init, ["new-topic"])

    content = portfolio.read_text()
    assert "| existing-topic |" in content
    assert "| new-topic |" in content
    assert "# Research Portfolio" in content
