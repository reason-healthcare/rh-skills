"""Tests for rh-skills promote command — ported from tests/unit/promote.bats."""

import io
import os

import click
import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from hi.commands.promote import _approved_extract_artifacts, promote


def load_yaml(path):
    y = YAML()
    with open(path) as f:
        return y.load(f)


def setup_topic_with_source(tmp_repo, topic_name="my-skill", source_name="ada-guidelines"):
    """Create topic + register a source in tracking.yaml."""
    td = tmp_repo / "topics" / topic_name
    (td / "structured").mkdir(parents=True, exist_ok=True)
    (td / "computable").mkdir(parents=True, exist_ok=True)
    (td / "process" / "fixtures" / "results").mkdir(parents=True, exist_ok=True)

    # Create source file in sources/
    src_file = tmp_repo / "sources" / f"{source_name}.md"
    src_file.write_text("Raw clinical content for testing.")

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    tracking["sources"].append({
        "name": source_name,
        "file": f"sources/{source_name}.md",
        "checksum": "abc123",
        "ingested_at": "2026-04-03T00:00:00Z",
    })
    tracking["topics"].append({
        "name": topic_name,
        "title": "Test Skill",
        "description": "A test skill",
        "author": "test",
        "created_at": "2026-04-03T00:00:00Z",
        "structured": [],
        "computable": [],
        "events": [{"timestamp": "2026-04-03T00:00:00Z", "type": "created", "description": "scaffolded"}],
    })
    with open(tracking_path, "w") as f:
        y.dump(tracking, f)


def setup_topic_with_l2(tmp_repo, topic_name="my-skill"):
    """Create topic + source + two L2 artifacts in tracking."""
    setup_topic_with_source(tmp_repo, topic_name)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    td = tmp_repo / "topics" / topic_name
    for artifact_name in ["l2-artifact-a", "l2-artifact-b"]:
        l2_file = td / "structured" / f"{artifact_name}.yaml"
        l2_file.write_text(f"""\
id: {artifact_name}
name: {artifact_name}
title: "Test L2 {artifact_name}"
version: "1.0.0"
status: draft
domain: testing
description: |
  Test L2 artifact.
derived_from:
  - ada-guidelines
""")
        for t in tracking["topics"]:
            if t["name"] == topic_name:
                t["structured"].append({
                    "name": artifact_name,
                    "file": f"topics/{topic_name}/structured/{artifact_name}.yaml",
                    "created_at": "2026-04-03T00:00:00Z",
                    "derived_from": ["ada-guidelines"],
                })
                break

    with open(tracking_path, "w") as f:
        y.dump(tracking, f)


def setup_topic_with_normalized_sources(tmp_repo, topic_name="my-skill", source_names=("ada-guidelines",)):
    """Create a topic plus normalized source markdown files."""
    td = tmp_repo / "topics" / topic_name
    (td / "structured").mkdir(parents=True, exist_ok=True)
    (td / "computable").mkdir(parents=True, exist_ok=True)
    (td / "process").mkdir(parents=True, exist_ok=True)
    normalized_root = tmp_repo / "sources" / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    tracking["topics"].append({
        "name": topic_name,
        "title": "Test Skill",
        "description": "A test skill",
        "author": "test",
        "created_at": "2026-04-03T00:00:00Z",
        "structured": [],
        "computable": [],
        "events": [{"timestamp": "2026-04-03T00:00:00Z", "type": "created", "description": "scaffolded"}],
    })
    for source_name in source_names:
        normalized_path = normalized_root / f"{source_name}.md"
        normalized_path.write_text(
            f"{source_name} guidance covering screening criteria, workflow steps, and evidence traceability."
        )
        tracking["sources"].append({
            "name": source_name,
            "file": f"sources/{source_name}.md",
            "checksum": "abc123",
            "ingested_at": "2026-04-03T00:00:00Z",
            "topic": topic_name,
        })

    with open(tracking_path, "w") as f:
        y.dump(tracking, f)


def write_extract_plan(tmp_repo, topic_name="my-skill", status="approved", artifacts=None):
    plan_path = tmp_repo / "topics" / topic_name / "process" / "plans" / "extract-plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    frontmatter = {
        "topic": topic_name,
        "plan_type": "extract",
        "status": status,
        "reviewer": "Reviewer",
        "reviewed_at": "2026-04-14T00:00:00Z" if status == "approved" else None,
        "artifacts": artifacts or [],
    }
    buf = io.StringIO()
    y.dump(frontmatter, buf)
    plan_path.write_text(
        f"---\n{buf.getvalue()}---\n\n# Review Summary\n\n# Proposed Artifacts\n\n# Cross-Artifact Issues\n\n# Implementation Readiness\n"
    )
    return plan_path


# ── Derive mode ────────────────────────────────────────────────────────────────

def test_derive_creates_l2_artifact_file(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    assert result.exit_code == 0, result.output
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "criteria.yaml").exists()


def test_derive_updates_tracking_structured_list(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "my-skill")
    assert len(topic["structured"]) == 1


def test_derive_records_structured_derived_event(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "my-skill")
    event_types = [e["type"] for e in topic["events"]]
    assert "structured_derived" in event_types


def test_derive_count_creates_n_artifacts(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "my-skill", "risk", "--source", "ada-guidelines", "--count", "3"])
    assert result.exit_code == 0, result.output
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "risk-1.yaml").exists()
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "risk-2.yaml").exists()
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "risk-3.yaml").exists()


def test_derive_dry_run_does_not_create_file(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines", "--dry-run"])
    assert result.exit_code == 0
    assert not (tmp_repo / "topics" / "my-skill" / "structured" / "criteria.yaml").exists()
    assert "DRY RUN" in result.output


def test_derive_fails_exit_2_if_source_not_found(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "nonexistent"])
    assert result.exit_code == 2


def test_derive_fails_exit_2_if_topic_not_found(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "ghost-skill", "criteria", "--source", "l1-art"])
    assert result.exit_code == 2


def test_derive_rich_extract_fields_written_in_stub_mode(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--artifact-type", "eligibility-criteria",
        "--clinical-question", "Who should be screened?",
        "--required-section", "summary",
        "--required-section", "evidence_traceability",
        "--evidence-ref", "crit-001|Screen adults at risk|ada-guidelines|Section 2",
        "--conflict", "Interval differs|ada-guidelines|Annual screening|ada-guidelines|Explicit interval language",
    ])
    assert result.exit_code == 0, result.output
    data = load_yaml(tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria.yaml")
    assert data["artifact_type"] == "eligibility-criteria"
    assert data["clinical_question"] == "Who should be screened?"
    assert "evidence_traceability" in data["sections"]
    assert data["sections"]["evidence_traceability"][0]["claim_id"] == "crit-001"
    assert data["conflicts"][0]["issue"] == "Interval differs"
    assert data["conflicts"][0]["preferred_interpretation"]["source"] == "ada-guidelines"


def test_derive_invalid_evidence_ref_format_exits_2(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "criteria",
        "--source", "ada-guidelines",
        "--evidence-ref", "broken-format",
    ])
    assert result.exit_code == 2


def test_plan_writes_extract_review_packet_and_records_event(tmp_repo):
    setup_topic_with_normalized_sources(
        tmp_repo,
        source_names=("ada-screening-guideline", "uspstf-screening-update"),
    )
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.md"
    assert plan_path.exists()
    raw = plan_path.read_text()
    assert raw.index("# Review Summary") < raw.index("# Proposed Artifacts") < raw.index("# Cross-Artifact Issues") < raw.index("# Implementation Readiness")

    parts = raw.split("---\n", 2)
    plan = YAML(typ="safe").load(parts[1])
    assert plan["topic"] == "my-skill"
    assert plan["plan_type"] == "extract"
    assert plan["status"] == "pending-review"
    assert plan["artifacts"]
    artifact = plan["artifacts"][0]
    assert artifact["reviewer_decision"] == "pending-review"
    assert artifact["source_files"]
    assert "evidence_traceability" in artifact["required_sections"]

    tracking = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in tracking["topics"] if t["name"] == "my-skill")
    assert "extract_planned" in [event["type"] for event in topic["events"]]


def test_plan_warns_and_does_not_write_without_normalized_sources(tmp_repo):
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0
    assert "No normalized sources found" in result.output
    assert not (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.md").exists()


def test_approved_extract_artifacts_requires_approved_plan(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "approved"}],
    )
    with pytest.raises(click.UsageError, match="not approved"):
        _approved_extract_artifacts("my-skill")


def test_approved_extract_artifacts_selects_only_approved_entries_when_not_strict(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        artifacts=[
            {"name": "screening-criteria", "reviewer_decision": "approved"},
            {"name": "risk-factors", "reviewer_decision": "needs-revision"},
        ],
    )
    approved = _approved_extract_artifacts("my-skill", strict=False)
    assert [artifact["name"] for artifact in approved] == ["screening-criteria"]


def test_approved_extract_artifacts_blocks_unapproved_entries_in_strict_mode(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        artifacts=[
            {"name": "screening-criteria", "reviewer_decision": "approved"},
            {"name": "risk-factors", "reviewer_decision": "pending-review"},
        ],
    )
    with pytest.raises(click.UsageError, match="Artifacts not approved"):
        _approved_extract_artifacts("my-skill")


# ── Combine mode ───────────────────────────────────────────────────────────────

def test_combine_creates_l3_artifact_file(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["combine", "my-skill", "l2-artifact-a", "l2-artifact-b", "computable"])
    assert result.exit_code == 0, result.output
    assert (tmp_repo / "topics" / "my-skill" / "computable" / "computable.yaml").exists()


def test_combine_updates_tracking_computable_list(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["combine", "my-skill", "l2-artifact-a", "l2-artifact-b", "computable"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "my-skill")
    assert len(topic["computable"]) == 1


def test_combine_records_computable_converged_event(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["combine", "my-skill", "l2-artifact-a", "l2-artifact-b", "computable"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "my-skill")
    event_types = [e["type"] for e in topic["events"]]
    assert "computable_converged" in event_types


def test_combine_converged_from_recorded_in_tracking(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["combine", "my-skill", "l2-artifact-a", "l2-artifact-b", "computable"])
    data = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in data["topics"] if t["name"] == "my-skill")
    assert len(topic["computable"][0]["converged_from"]) == 2


def test_combine_dry_run_does_not_create_file(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["combine", "my-skill", "l2-artifact-a", "l2-artifact-b", "computable", "--dry-run"])
    assert result.exit_code == 0
    assert not (tmp_repo / "topics" / "my-skill" / "computable" / "computable.yaml").exists()
    assert "DRY RUN" in result.output


def test_combine_fails_exit_2_if_l2_not_found(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["combine", "my-skill", "l2-artifact-a", "ghost", "computable"])
    assert result.exit_code == 2


def test_combine_fails_exit_2_if_only_one_arg(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["combine", "my-skill", "only-target"])
    assert result.exit_code == 2
