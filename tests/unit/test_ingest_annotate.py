"""Tests for rh-skills ingest annotate subcommand."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.ingest import ingest
from tests.conftest import load_tracking


@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Set up a minimal repo root with tracking.yaml."""
    monkeypatch.setenv("RH_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("RH_TRACKING_FILE", str(tmp_path / "tracking.yaml"))
    monkeypatch.setenv("RH_SOURCES_ROOT", str(tmp_path / "sources"))

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
        "text_extracted": True,
    })
    y.dump(data, tf)


def _create_normalized_md(tmp_repo, name, topic="test-topic", body="Clinical content here."):
    """Create a sources/normalized/<name>.md stub with YAML frontmatter."""
    norm_dir = tmp_repo / "sources" / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    norm = norm_dir / f"{name}.md"
    norm.write_text(
        f"---\nsource: {name}\ntopic: {topic}\nnormalized: 2025-01-01T00:00:00Z\n"
        f"original: sources/{name}.txt\ntext_extracted: true\n---\n\n{body}"
    )
    return norm


def _parse_frontmatter(text: str) -> dict:
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    y = YAML(typ="safe")
    return y.load(parts[1]) or {}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_annotate_updates_normalized_frontmatter(tmp_repo):
    """After annotate, normalized.md frontmatter contains correct concepts block."""
    _register_source(tmp_repo, "src-a")
    _create_normalized_md(tmp_repo, "src-a")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "annotate", "src-a",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
        "--concept", "Metoprolol:medication",
    ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "src-a.md"
    fm = _parse_frontmatter(norm.read_text())
    assert "concepts" in fm
    names = [c["name"] for c in fm["concepts"]]
    assert "Hypertension" in names
    assert "Metoprolol" in names


def test_annotate_writes_concepts_to_frontmatter_only(tmp_repo):
    """Concept annotations now live only in normalized front matter."""
    _register_source(tmp_repo, "src-b")
    _create_normalized_md(tmp_repo, "src-b")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "annotate", "src-b",
        "--topic", "test-topic",
        "--concept", "SBP:measure",
        "--concept", "ICD-10 I10:code",
    ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "src-b.md"
    fm = _parse_frontmatter(norm.read_text())
    names = [c["name"] for c in fm["concepts"]]
    assert "SBP" in names
    assert "ICD-10 I10" in names
    assert not (tmp_repo / "topics" / "test-topic" / "process" / "concepts.yaml").exists()


def test_annotate_append_across_calls(tmp_repo):
    """Annotate same source twice; concepts accumulate in front matter (no dedup)."""
    _register_source(tmp_repo, "src-c")
    _create_normalized_md(tmp_repo, "src-c")

    runner = CliRunner()
    runner.invoke(ingest, [
        "annotate", "src-c",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
    ])
    runner.invoke(ingest, [
        "annotate", "src-c",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
        "--concept", "Metoprolol:medication",
    ])

    norm = tmp_repo / "sources" / "normalized" / "src-c.md"
    fm = _parse_frontmatter(norm.read_text())
    ht_entries = [c for c in fm["concepts"] if c["name"].lower() == "hypertension"]
    assert len(ht_entries) == 2
    names = [c["name"] for c in fm["concepts"]]
    assert "Metoprolol" in names


def test_annotate_overwrite_replaces_source_concepts(tmp_repo):
    """--overwrite removes prior concepts for this source and adds new ones."""
    _register_source(tmp_repo, "src-c2")
    _create_normalized_md(tmp_repo, "src-c2")

    runner = CliRunner()
    runner.invoke(ingest, [
        "annotate", "src-c2",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
    ])
    runner.invoke(ingest, [
        "annotate", "src-c2",
        "--topic", "test-topic",
        "--overwrite",
        "--concept", "Metoprolol:medication",
    ])

    norm = tmp_repo / "sources" / "normalized" / "src-c2.md"
    fm = _parse_frontmatter(norm.read_text())
    names = [c["name"] for c in fm["concepts"]]
    assert "Metoprolol" in names
    assert "Hypertension" not in names


def test_annotate_append_to_normalized_frontmatter(tmp_repo):
    """Default append mode adds to existing concepts in normalized.md frontmatter."""
    _register_source(tmp_repo, "src-c3")
    _create_normalized_md(tmp_repo, "src-c3")

    runner = CliRunner()
    runner.invoke(ingest, [
        "annotate", "src-c3",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
    ])
    runner.invoke(ingest, [
        "annotate", "src-c3",
        "--topic", "test-topic",
        "--concept", "Metoprolol:medication",
    ])

    norm = tmp_repo / "sources" / "normalized" / "src-c3.md"
    fm = _parse_frontmatter(norm.read_text())
    names = [c["name"] for c in fm["concepts"]]
    assert "Hypertension" in names
    assert "Metoprolol" in names


def test_annotate_two_sources_each_has_own_frontmatter_entry(tmp_repo):
    """Two sources may repeat the same concept in their own normalized front matter."""
    _register_source(tmp_repo, "src-d")
    _register_source(tmp_repo, "src-e")
    _create_normalized_md(tmp_repo, "src-d")
    _create_normalized_md(tmp_repo, "src-e")

    runner = CliRunner()
    runner.invoke(ingest, [
        "annotate", "src-d",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
    ])
    runner.invoke(ingest, [
        "annotate", "src-e",
        "--topic", "test-topic",
        "--concept", "Hypertension:condition",
    ])

    fm_d = _parse_frontmatter((tmp_repo / "sources" / "normalized" / "src-d.md").read_text())
    fm_e = _parse_frontmatter((tmp_repo / "sources" / "normalized" / "src-e.md").read_text())
    assert [c["name"] for c in fm_d["concepts"]] == ["Hypertension"]
    assert [c["name"] for c in fm_e["concepts"]] == ["Hypertension"]


def test_annotate_event_appended(tmp_repo):
    """source_annotated event written to tracking.yaml."""
    _register_source(tmp_repo, "src-f")
    _create_normalized_md(tmp_repo, "src-f")

    runner = CliRunner()
    runner.invoke(ingest, [
        "annotate", "src-f",
        "--topic", "test-topic",
        "--concept", "Glucose:measure",
    ])

    tracking = load_tracking(tmp_repo)
    event_types = [e["type"] for e in tracking.get("events", [])]
    assert "source_annotated" in event_types


def test_annotate_concept_count_in_tracking(tmp_repo):
    """concept_count field set correctly on source record in tracking.yaml."""
    _register_source(tmp_repo, "src-g")
    _create_normalized_md(tmp_repo, "src-g")

    runner = CliRunner()
    runner.invoke(ingest, [
        "annotate", "src-g",
        "--topic", "test-topic",
        "--concept", "A:condition",
        "--concept", "B:medication",
        "--concept", "C:code",
    ])

    tracking = load_tracking(tmp_repo)
    src = next(s for s in tracking["sources"] if s["name"] == "src-g")
    assert src["concept_count"] == 3


def test_annotate_no_normalized_md_exits_1(tmp_repo):
    """ClickException when normalized.md missing."""
    _register_source(tmp_repo, "src-h")
    # Do NOT create normalized.md

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "annotate", "src-h",
        "--topic", "test-topic",
        "--concept", "Something:term",
    ])

    assert result.exit_code == 1
    assert "sources/normalized" in result.output


def test_annotate_concept_default_type_term(tmp_repo):
    """--concept 'SomeConceptWithNoColon' → type defaults to 'term'."""
    _register_source(tmp_repo, "src-i")
    _create_normalized_md(tmp_repo, "src-i")

    runner = CliRunner()
    result = runner.invoke(ingest, [
        "annotate", "src-i",
        "--topic", "test-topic",
        "--concept", "SomeConceptWithNoColon",
    ])

    assert result.exit_code == 0, result.output
    norm = tmp_repo / "sources" / "normalized" / "src-i.md"
    fm = _parse_frontmatter(norm.read_text())
    entry = next(c for c in fm["concepts"] if c["name"] == "SomeConceptWithNoColon")
    assert entry["type"] == "term"
