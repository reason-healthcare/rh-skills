"""Tests for rh-skills ingest command — plan / implement / verify."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.ingest import ingest
from rh_skills.common import sha256_file
from tests.conftest import load_tracking


# ── rh-skills ingest plan ─────────────────────────────────────────────────────────────


def _write_discovery_plan(tmp_repo, topic, sources):
    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "discovery-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    y.dump({"topic": topic, "sources": sources}, plan_path)
    return plan_path


def _register_source(
    tmp_repo,
    name,
    *,
    topic=None,
    file_name=None,
    source_type="document",
    evidence_level=None,
    domain_tags=None,
    normalized=None,
    annotated_at=None,
    checksum=None,
):
    y = YAML()
    y.default_flow_style = False
    tf = tmp_repo / "tracking.yaml"
    data = y.load(tf.read_text())
    record = {
        "name": name,
        "file": file_name or f"sources/{name}.md",
        "type": source_type,
        "checksum": checksum or "abc",
        "ingested_at": "2025-01-01T00:00:00Z",
        "text_extracted": True,
    }
    if topic:
        record["topic"] = topic
    if evidence_level:
        record["evidence_level"] = evidence_level
    if domain_tags is not None:
        record["domain_tags"] = domain_tags
    if normalized:
        record["normalized"] = normalized
    if annotated_at:
        record["annotated_at"] = annotated_at
        record["concept_count"] = 1
    data["sources"].append(record)
    y.dump(data, tf)


def _create_normalized_md(tmp_repo, name, topic="test-topic", *, concepts=None, text_extracted=True):
    norm_dir = tmp_repo / "sources" / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    frontmatter = {
        "source": name,
        "topic": topic,
        "normalized": "2025-01-01T00:00:00Z",
        "original": f"sources/{name}.md",
        "text_extracted": text_extracted,
    }
    if concepts is not None:
        frontmatter["concepts"] = concepts
    from io import StringIO
    buf = StringIO()
    y.dump(frontmatter, buf)
    norm = norm_dir / f"{name}.md"
    norm.write_text(f"---\n{buf.getvalue()}---\n\nNormalized content")
    return norm


def _write_concepts_yaml(tmp_repo, topic, concepts):
    path = tmp_repo / "topics" / topic / "process" / "concepts.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    y.dump({"topic": topic, "generated": "2025-01-01T00:00:00Z", "concepts": concepts}, path)
    return path

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


def test_plan_topic_summarizes_discovery_plan_and_manual_files(tmp_repo):
    _write_discovery_plan(tmp_repo, "hypertension", [
        {
            "name": "open-guideline",
            "type": "clinical-guideline",
            "access": "open",
            "url": "https://example.com/open.pdf",
        },
        {
            "name": "auth-review",
            "type": "systematic-review",
            "access": "authenticated",
            "auth_note": "Use library portal",
        },
    ])
    (tmp_repo / "sources" / "manual.pdf").write_text("manual file")

    runner = CliRunner()
    result = runner.invoke(ingest, ["plan", "hypertension"])

    assert result.exit_code == 0, result.output
    assert "Pre-flight summary for 'hypertension'" in result.output
    assert "Open-access sources ready to download: 1" in result.output
    assert "Authenticated/manual sources requiring manual placement: 1" in result.output
    assert "auth_note: Use library portal" in result.output
    assert "Manually placed untracked files: 1" in result.output
    assert "manual.pdf" in result.output
    assert not (tmp_repo / "plans" / "ingest-plan.md").exists()


def test_plan_topic_without_discovery_plan_lists_manual_files(tmp_repo):
    (tmp_repo / "sources" / "manual-only.pdf").write_text("manual file")

    runner = CliRunner()
    result = runner.invoke(ingest, ["plan", "manual-topic"])

    assert result.exit_code == 0, result.output
    assert "No discovery-plan.yaml found for this topic." in result.output
    assert "Manually placed untracked files: 1" in result.output
    assert "manual-only.pdf" in result.output


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


def test_verify_topic_reports_readiness_and_valid_concepts(tmp_repo):
    src = tmp_repo / "sources" / "topic-source.md"
    src.write_text("Tracked source")
    _register_source(
        tmp_repo,
        "topic-source",
        topic="hypertension",
        source_type="clinical-guideline",
        evidence_level="ia",
        domain_tags=["hypertension"],
        normalized="sources/normalized/topic-source.md",
        annotated_at="2025-01-01T00:00:00Z",
        checksum=sha256_file(src),
    )
    _create_normalized_md(
        tmp_repo,
        "topic-source",
        topic="hypertension",
        concepts=[{"name": "Hypertension", "type": "condition"}],
    )
    _write_concepts_yaml(
        tmp_repo,
        "hypertension",
        [{"name": "Hypertension", "type": "condition", "sources": ["topic-source"]}],
    )

    runner = CliRunner()
    result = runner.invoke(ingest, ["verify", "hypertension"])

    assert result.exit_code == 0, result.output
    assert "Ingest readiness for 'hypertension'" in result.output
    assert "topic-source: file=OK checksum=OK normalized=YES classified=YES annotated=YES" in result.output
    assert "concepts.yaml: VALID" in result.output


def test_verify_topic_reports_untracked_manual_files(tmp_repo):
    (tmp_repo / "sources" / "manual-only.pdf").write_text("manual file")

    runner = CliRunner()
    result = runner.invoke(ingest, ["verify", "manual-topic"])

    assert result.exit_code == 1
    assert "Untracked manual files:" in result.output
    assert "manual-only.pdf" in result.output
