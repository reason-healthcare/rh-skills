"""Tests for rh-skills promote command — ported from tests/unit/promote.bats."""

import io
import os

import click
import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.promote import _approved_extract_artifacts, _approved_formalize_target, _sanitize_yaml, promote


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
        l2_dir = td / "structured" / artifact_name
        l2_dir.mkdir(parents=True, exist_ok=True)
        l2_file = l2_dir / f"{artifact_name}.yaml"
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
                    "file": f"topics/{topic_name}/structured/{artifact_name}/{artifact_name}.yaml",
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
    plan_path = tmp_repo / "topics" / topic_name / "process" / "plans" / "extract-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    plan = {
        "topic": topic_name,
        "plan_type": "extract",
        "status": status,
        "reviewer": "Reviewer",
        "reviewed_at": "2026-04-14T00:00:00Z" if status == "approved" else None,
        "review_summary": "",
        "cross_artifact_issues": [],
        "artifacts": artifacts or [],
    }
    buf = io.StringIO()
    y.dump(plan, buf)
    plan_path.write_text(buf.getvalue())
    return plan_path


def setup_topic_with_valid_extract_artifacts(tmp_repo, topic_name="my-skill", artifact_specs=None):
    artifact_specs = artifact_specs or [
        {"name": "screening-criteria", "artifact_type": "decision-table"},
        {"name": "care-steps", "artifact_type": "care-pathway"},
        {"name": "code-sets", "artifact_type": "terminology"},
    ]
    setup_topic_with_source(tmp_repo, topic_name)

    td = tmp_repo / "topics" / topic_name / "structured"
    td.mkdir(parents=True, exist_ok=True)

    tracking_path = tmp_repo / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    with open(tracking_path) as f:
        tracking = y.load(f)

    for spec in artifact_specs:
        artifact_name = spec["name"]
        artifact_type = spec["artifact_type"]
        sections = {
            "summary": f"{artifact_name} summary",
            "evidence_traceability": [{
                "claim_id": f"{artifact_name}-001",
                "statement": f"Evidence for {artifact_name}",
                "evidence": [{"source": "ada-guidelines", "locator": "Section 1"}],
            }],
        }
        if artifact_type == "care-pathway":
            sections["steps"] = [{"step": "Assess patient"}]
        elif artifact_type == "terminology":
            sections["value_sets"] = [{"system": "SNOMED"}]
        else:
            sections["conditions"] = [{"id": "c1", "label": "Test", "values": ["Yes", "No"]}]

        buf = io.StringIO()
        y.dump({
            "id": artifact_name,
            "name": artifact_name,
            "title": artifact_name.replace("-", " ").title(),
            "version": "1.0.0",
            "status": "draft",
            "domain": "diabetes",
            "description": f"Structured artifact for {artifact_name}.",
            "derived_from": ["ada-guidelines"],
            "artifact_type": artifact_type,
            "clinical_question": f"What does {artifact_name} contribute?",
            "sections": sections,
            "conflicts": [],
        }, buf)
        artifact_dir = td / artifact_name
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / f"{artifact_name}.yaml").write_text(buf.getvalue())

        topic = next(t for t in tracking["topics"] if t["name"] == topic_name)
        topic["structured"].append({
            "name": artifact_name,
            "file": f"topics/{topic_name}/structured/{artifact_name}/{artifact_name}.yaml",
            "created_at": "2026-04-14T00:00:00Z",
            "checksum": "abc123",
            "derived_from": ["ada-guidelines"],
            "artifact_type": artifact_type,
        })

    with open(tracking_path, "w") as f:
        y.dump(tracking, f)

    write_extract_plan(
        tmp_repo,
        topic_name=topic_name,
        artifacts=[
            {
                "name": spec["name"],
                "artifact_type": spec["artifact_type"],
                "source_files": ["sources/normalized/ada-guidelines.md"],
                "rationale": f"Approved input for {spec['name']}",
                "key_questions": [f"What does {spec['name']} contribute?"],
                "required_sections": ["summary", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Use in formalize",
            }
            for spec in artifact_specs
        ],
    )


def write_formalize_plan(tmp_repo, topic_name="my-skill", status="approved", artifacts=None):
    plan_path = tmp_repo / "topics" / topic_name / "process" / "plans" / "formalize-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    plan = {
        "topic": topic_name,
        "plan_type": "formalize",
        "status": status,
        "reviewer": "Reviewer",
        "reviewed_at": "2026-04-14T12:00:00Z" if status == "approved" else None,
        "artifacts": artifacts or [],
    }
    with open(plan_path, "w") as f:
        y.dump(plan, f)
    return plan_path


# ── Derive mode ────────────────────────────────────────────────────────────────

def test_derive_creates_l2_artifact_file(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    assert result.exit_code == 0, result.output
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "criteria" / "criteria.yaml").exists()


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
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "risk-1" / "risk-1.yaml").exists()
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "risk-2" / "risk-2.yaml").exists()
    assert (tmp_repo / "topics" / "my-skill" / "structured" / "risk-3" / "risk-3.yaml").exists()


def test_derive_dry_run_does_not_create_file(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines", "--dry-run"])
    assert result.exit_code == 0
    assert not (tmp_repo / "topics" / "my-skill" / "structured" / "criteria" / "criteria.yaml").exists()
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
        "--artifact-type", "decision-table",
        "--clinical-question", "Who should be screened?",
        "--required-section", "summary",
        "--required-section", "evidence_traceability",
        "--evidence-ref", "crit-001|Screen adults at risk|ada-guidelines|Section 2",
        "--conflict", "Interval differs|ada-guidelines|Annual screening|ada-guidelines|Explicit interval language",
    ])
    assert result.exit_code == 0, result.output
    data = load_yaml(tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml")
    assert data["artifact_type"] == "decision-table"
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


def test_derive_conflict_same_issue_merges_positions(tmp_repo, monkeypatch):
    """Two --conflict flags with the same issue merge into one entry with multiple positions."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "hba1c-target",
        "--source", "ada-guidelines",
        "--artifact-type", "decision-table",
        "--conflict", "HbA1c target|ada-guidelines|ADA recommends <7.0%",
        "--conflict", "HbA1c target|aace-guidelines|AACE recommends ≤6.5%|aace-guidelines|More specific target",
    ])
    assert result.exit_code == 0, result.output
    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "hba1c-target" / "hba1c-target.yaml"
    data = YAML(typ="safe").load(artifact_path.read_text())
    conflicts = data.get("conflicts", [])
    assert len(conflicts) == 1, f"Expected 1 merged conflict entry, got {len(conflicts)}"
    assert len(conflicts[0]["positions"]) == 2
    sources = {p["source"] for p in conflicts[0]["positions"]}
    assert sources == {"ada-guidelines", "aace-guidelines"}
    assert conflicts[0]["preferred_interpretation"]["source"] == "aace-guidelines"


def test_plan_writes_extract_review_packet_and_records_event(tmp_repo):
    setup_topic_with_normalized_sources(
        tmp_repo,
        source_names=("ada-screening-guideline", "uspstf-screening-update"),
    )
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    assert plan_path.exists()
    readout_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan-readout.md"
    assert readout_path.exists()

    plan = YAML(typ="safe").load(plan_path.read_text())
    assert plan["topic"] == "my-skill"
    assert plan["plan_type"] == "extract"
    assert plan["status"] == "pending-review"
    assert plan["artifacts"]
    artifact = plan["artifacts"][0]
    assert artifact["reviewer_decision"] == "pending-review"
    assert artifact["source_files"]
    assert "evidence_traceability" in artifact["required_sections"]

    raw_readout = readout_path.read_text()
    assert "extract-plan.yaml" in raw_readout
    assert "Review Summary" in raw_readout
    assert "Proposed Artifacts" in raw_readout
    assert "Cross-Artifact Issues" in raw_readout
    assert "Implementation Readiness" in raw_readout

    tracking = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in tracking["topics"] if t["name"] == "my-skill")
    assert "extract_planned" in [event["type"] for event in topic["events"]]


def test_plan_warns_and_does_not_write_without_normalized_sources(tmp_repo):
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0
    assert "No normalized sources found" in result.output
    assert not (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml").exists()


def test_plan_offline_mode_produces_empty_concerns(tmp_repo, monkeypatch):
    """Offline mode (LLM_PROVIDER=stub, no RH_STUB_RESPONSE): concerns[] starts empty."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    setup_topic_with_normalized_sources(
        tmp_repo,
        source_names=("ada-screening-guideline", "uspstf-screening-update"),
    )
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output
    plan = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml").read_text()
    )
    assert plan["artifacts"][0]["concerns"] == []


def test_plan_agent_mode_parses_injected_concerns(tmp_repo, monkeypatch):
    """Agent mode (LLM_PROVIDER=stub, RH_STUB_RESPONSE set): concerns parsed from injected YAML."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv(
        "RH_STUB_RESPONSE",
        '- concern: "Source ada-screening-guideline uses threshold 140 mmHg; uspstf-screening-update uses 160 mmHg"\n',
    )
    setup_topic_with_normalized_sources(
        tmp_repo,
        source_names=("ada-screening-guideline", "uspstf-screening-update"),
    )
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output
    plan = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml").read_text()
    )
    concerns = plan["artifacts"][0]["concerns"]
    assert len(concerns) == 1
    assert "140 mmHg" in concerns[0]["concern"]
    assert concerns[0]["resolution"] == ""


def test_derive_agent_mode_writes_injected_content(tmp_repo, monkeypatch):
    """Agent mode: --body-file content is written as L2 artifact (not scaffold)."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_content = "artifact_type: decision-table\nclinical_question: Who should be screened?\nsections:\n  summary: Agent-generated content.\n"
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text(body_content)
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--artifact-type", "decision-table",
        "--clinical-question", "Who should be screened?",
        "--required-section", "summary",
        "--required-section", "evidence_traceability",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 0, result.output
    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml"
    content = artifact_path.read_text()
    assert "<stub:" not in content
    assert "Agent-generated content." in content


def test_derive_offline_mode_writes_stub_scaffold(tmp_repo, monkeypatch):
    """Offline mode: no RH_STUB_RESPONSE → scaffold with <stub: ...> placeholders."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--artifact-type", "decision-table",
        "--clinical-question", "Who should be screened?",
        "--required-section", "summary",
        "--required-section", "evidence_traceability",
        "--required-section", "decision_rules",
    ])
    assert result.exit_code == 0, result.output
    content = (
        tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml"
    ).read_text()
    assert "<stub:" in content



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
            {"name": "evidence-review", "reviewer_decision": "needs-revision"},
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
            {"name": "evidence-review", "reviewer_decision": "pending-review"},
        ],
    )
    with pytest.raises(click.UsageError, match="Artifacts not approved"):
        _approved_extract_artifacts("my-skill")


def test_formalize_plan_writes_review_packet_and_records_event(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["formalize-plan", "my-skill"])
    assert result.exit_code == 0, result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan.yaml"
    readout_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan-readout.md"
    assert plan_path.exists()
    assert readout_path.exists()

    plan = YAML(typ="safe").load(plan_path.read_text())
    assert plan["topic"] == "my-skill"
    assert plan["plan_type"] == "formalize"
    assert plan["status"] == "pending-review"
    # Multi-type inputs produce per-type artifacts
    assert len(plan["artifacts"]) == 3
    strategies = {a["strategy"] for a in plan["artifacts"]}
    assert strategies == {"decision-table", "care-pathway", "terminology"}
    # First artifact is the implementation target
    assert plan["artifacts"][0]["implementation_target"] is True
    # Overlap between decision-table and care-pathway (both produce PlanDefinition)
    rationales = " ".join(a["rationale"] for a in plan["artifacts"])
    assert "Overlaps" in rationales or "overlap" in rationales.lower()

    readout = readout_path.read_text()
    assert "# Review Summary" in readout
    assert "# Proposed Artifacts" in readout
    assert "# Cross-Artifact Issues" in readout
    assert "# Implementation Readiness" in readout
    assert "formalize-plan.yaml" in readout

    tracking = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in tracking["topics"] if t["name"] == "my-skill")
    assert "formalize_planned" in [event["type"] for event in topic["events"]]


def test_formalize_plan_warns_and_does_not_write_without_eligible_inputs(tmp_repo):
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["formalize-plan", "my-skill"])
    assert result.exit_code == 0
    assert (
        "No approved structured artifacts are ready for formalization" in result.output
        or "extract-plan.yaml is not approved" in result.output
        or "No plan found" in result.output
    )
    assert not (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan.yaml").exists()


def test_formalize_plan_force_overwrites_existing_packet(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("old: plan")

    runner = CliRunner()
    result = runner.invoke(promote, ["formalize-plan", "my-skill", "--force"])
    assert result.exit_code == 0, result.output
    assert "old: plan" not in plan_path.read_text()


def test_approved_formalize_target_requires_approved_target_and_valid_inputs(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    write_formalize_plan(
        tmp_repo,
        artifacts=[{
            "name": "my-skill-pathway",
            "artifact_type": "pathway-package",
            "input_artifacts": ["screening-criteria", "care-steps"],
            "rationale": "Primary package",
            "required_sections": ["pathways", "actions"],
            "implementation_target": True,
            "reviewer_decision": "approved",
            "approval_notes": "Proceed",
        }],
    )

    target = _approved_formalize_target("my-skill")
    assert target["name"] == "my-skill-pathway"
    assert target["input_artifacts"] == ["screening-criteria", "care-steps"]


def test_approved_formalize_target_blocks_invalid_inputs(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "care-steps" / "care-steps.yaml"
    data = load_yaml(artifact_path)
    data["sections"].pop("evidence_traceability")
    y = YAML()
    y.default_flow_style = False
    with open(artifact_path, "w") as f:
        y.dump(data, f)

    write_formalize_plan(
        tmp_repo,
        artifacts=[{
            "name": "my-skill-pathway",
            "artifact_type": "pathway-package",
            "input_artifacts": ["care-steps"],
            "rationale": "Primary package",
            "required_sections": ["pathways", "actions"],
            "implementation_target": True,
            "reviewer_decision": "approved",
            "approval_notes": "Proceed",
        }],
    )

    with pytest.raises(click.UsageError, match="missing or invalid"):
        _approved_formalize_target("my-skill")


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


# ── approve command ──────────────────────────────────────────────────────────

def _read_plan(tmp_repo, topic="my-skill"):
    from ruamel.yaml import YAML as _YAML
    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "extract-plan.yaml"
    return _YAML(typ="safe").load(plan_path.read_text())


def test_approve_artifact_updates_yaml_and_readout(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[
            {"name": "screening-criteria", "reviewer_decision": "pending-review", "approval_notes": ""},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(
        promote,
        ["approve", "my-skill", "--artifact", "screening-criteria", "--decision", "approved", "--notes", "LGTM"],
    )
    assert result.exit_code == 0, result.output
    plan = _read_plan(tmp_repo)
    artifact = plan["artifacts"][0]
    assert artifact["reviewer_decision"] == "approved"
    assert artifact["approval_notes"] == "LGTM"

    readout_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan-readout.md"
    assert readout_path.exists()
    assert "screening-criteria" in readout_path.read_text()


def test_approve_artifact_unknown_raises(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "pending-review", "approval_notes": ""}],
    )
    runner = CliRunner()
    result = runner.invoke(
        promote,
        ["approve", "my-skill", "--artifact", "does-not-exist", "--decision", "approved"],
    )
    assert result.exit_code != 0


def test_approve_requires_decision_with_artifact(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "pending-review", "approval_notes": ""}],
    )
    runner = CliRunner()
    result = runner.invoke(promote, ["approve", "my-skill", "--artifact", "screening-criteria"])
    assert result.exit_code != 0


def test_approve_finalize_sets_status_and_timestamp(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "approved", "approval_notes": ""}],
    )
    runner = CliRunner()
    result = runner.invoke(
        promote,
        ["approve", "my-skill", "--finalize", "--reviewer", "Jane"],
    )
    assert result.exit_code == 0, result.output
    plan = _read_plan(tmp_repo)
    assert plan["status"] == "approved"
    assert plan["reviewer"] == "Jane"
    assert plan["reviewed_at"] is not None


def test_approve_no_plan_raises_usage_error(tmp_repo):
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(
        promote,
        ["approve", "my-skill", "--artifact", "x", "--decision", "approved"],
    )
    assert result.exit_code != 0


def test_approve_no_args_non_tty_raises_usage_error(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "pending-review", "approval_notes": ""}],
    )
    runner = CliRunner()
    # CliRunner does not set up a TTY, so stdin.isatty() → False
    result = runner.invoke(promote, ["approve", "my-skill"])
    assert result.exit_code != 0


def test_approve_finalize_after_separate_artifact_approval_preserves_decision(tmp_repo):
    """Regression: --finalize must not reset reviewer_decision set by a prior invocation."""
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "pending-review", "approval_notes": ""}],
    )
    runner = CliRunner()
    # First invocation: approve artifact
    r1 = runner.invoke(promote, ["approve", "my-skill", "--artifact", "screening-criteria", "--decision", "approved"])
    assert r1.exit_code == 0, r1.output

    # Second invocation: finalize (simulates running after --artifact has already written the file)
    r2 = runner.invoke(promote, ["approve", "my-skill", "--finalize", "--reviewer", "Jane"])
    assert r2.exit_code == 0, r2.output
    assert "1/1" in r2.output

    plan = _read_plan(tmp_repo)
    assert plan["status"] == "approved"
    assert plan["artifacts"][0]["reviewer_decision"] == "approved"


def test_approve_review_summary_written_to_plan(tmp_repo):
    """--review-summary flag sets plan-level review_summary in extract-plan.yaml."""
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "decision-table", "reviewer_decision": "pending-review", "approval_notes": ""}],
    )
    runner = CliRunner()
    result = runner.invoke(promote, [
        "approve", "my-skill",
        "--artifact", "decision-table",
        "--decision", "approved",
        "--review-summary", "ADA vs AACE conflict documented; plan approved.",
        "--finalize", "--reviewer", "Test",
    ])
    assert result.exit_code == 0, result.output
    plan = _read_plan(tmp_repo)
    assert plan["review_summary"] == "ADA vs AACE conflict documented; plan approved."
    assert plan["status"] == "approved"


def test_approve_add_conflict_appends_to_conflicts(tmp_repo):
    """--add-conflict appends to artifact's concerns list with concern/resolution keys."""
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "hba1c-target", "reviewer_decision": "pending-review",
                    "approval_notes": "", "concerns": []}],
    )
    runner = CliRunner()
    result = runner.invoke(promote, [
        "approve", "my-skill",
        "--artifact", "hba1c-target",
        "--decision", "approved",
        "--add-conflict", "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%",
        "--add-conflict", "Monitoring frequency|ADA annual preferred",
        "--finalize", "--reviewer", "Test",
    ])
    assert result.exit_code == 0, result.output
    plan = _read_plan(tmp_repo)
    concerns = plan["artifacts"][0]["concerns"]
    assert len(concerns) == 2
    assert concerns[0]["concern"] == "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%"
    assert concerns[0]["resolution"] == ""
    assert concerns[1]["concern"] == "Monitoring frequency"
    assert concerns[1]["resolution"] == "ADA annual preferred"


# ── Formalize section mapping tests (T031) ───────────────────────────────────


class TestFormalizeSectionMapping:
    """Test _formalize_required_sections() returns correct sections by type."""

    def test_decision_table_includes_actions_and_libraries(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "decision-table"}])
        assert "actions" in result
        assert "libraries" in result

    def test_policy_includes_actions_and_libraries(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "policy"}])
        assert "actions" in result
        assert "libraries" in result

    def test_assessment_includes_assessments_only(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "assessment"}])
        assert "assessments" in result
        assert "pathways" not in result

    def test_evidence_summary_includes_evidence(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "evidence-summary"}])
        assert result == ["evidence"]

    def test_care_pathway_includes_pathways_and_actions(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "care-pathway"}])
        assert "pathways" in result
        assert "actions" in result

    def test_measure_includes_measures_and_libraries(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "measure"}])
        assert "measures" in result
        assert "libraries" in result

    def test_terminology_includes_value_sets(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "terminology"}])
        assert "value_sets" in result

    def test_mixed_types_union(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([
            {"artifact_type": "decision-table"},
            {"artifact_type": "assessment"},
            {"artifact_type": "terminology"},
        ])
        assert "actions" in result
        assert "assessments" in result
        assert "value_sets" in result
        assert "libraries" in result


class TestBuildFormalizeArtifacts:
    def test_single_type_produces_one_artifact(self):
        from rh_skills.commands.promote import _build_formalize_artifacts
        result = _build_formalize_artifacts("test-topic", [
            {"name": "a1", "artifact_type": "decision-table"},
        ])
        assert len(result) == 1
        assert result[0]["strategy"] == "decision-table"
        assert result[0]["implementation_target"] is True

    def test_multi_type_produces_per_type_artifacts(self):
        from rh_skills.commands.promote import _build_formalize_artifacts
        result = _build_formalize_artifacts("test-topic", [
            {"name": "a1", "artifact_type": "decision-table"},
            {"name": "a2", "artifact_type": "terminology"},
            {"name": "a3", "artifact_type": "measure"},
        ])
        assert len(result) == 3
        strategies = {a["strategy"] for a in result}
        assert strategies == {"decision-table", "terminology", "measure"}
        # Only first artifact is implementation_target
        targets = [a for a in result if a["implementation_target"]]
        assert len(targets) == 1

    def test_overlap_detection_flagged_in_rationale(self):
        from rh_skills.commands.promote import _build_formalize_artifacts
        result = _build_formalize_artifacts("test-topic", [
            {"name": "a1", "artifact_type": "decision-table"},
            {"name": "a2", "artifact_type": "care-pathway"},
        ])
        assert len(result) == 2
        rationales = " ".join(a["rationale"] for a in result)
        assert "Overlaps" in rationales or "overlap" in rationales.lower()

    def test_no_overlap_for_distinct_resource_types(self):
        from rh_skills.commands.promote import _build_formalize_artifacts
        result = _build_formalize_artifacts("test-topic", [
            {"name": "a1", "artifact_type": "terminology"},
            {"name": "a2", "artifact_type": "measure"},
        ])
        rationales = " ".join(a["rationale"] for a in result)
        assert "Overlaps" not in rationales


class TestDetectResourceTypeOverlaps:
    def test_plandefinition_overlap(self):
        from rh_skills.commands.promote import _detect_resource_type_overlaps
        overlaps = _detect_resource_type_overlaps({
            "decision-table": [{"name": "a1"}],
            "care-pathway": [{"name": "a2"}],
        })
        assert len(overlaps) == 1
        assert overlaps[0]["resource_type"] == "PlanDefinition"
        assert set(overlaps[0]["strategies"]) == {"decision-table", "care-pathway"}

    def test_no_overlap(self):
        from rh_skills.commands.promote import _detect_resource_type_overlaps
        overlaps = _detect_resource_type_overlaps({
            "terminology": [{"name": "a1"}],
            "measure": [{"name": "a2"}],
        })
        assert len(overlaps) == 0

    def test_triple_overlap(self):
        from rh_skills.commands.promote import _detect_resource_type_overlaps
        overlaps = _detect_resource_type_overlaps({
            "decision-table": [{"name": "a1"}],
            "care-pathway": [{"name": "a2"}],
            "policy": [{"name": "a3"}],
        })
        assert len(overlaps) == 1
        assert len(overlaps[0]["strategies"]) == 3


class TestInferArtifactProfiles:
    def test_single_match_returns_one_profile(self):
        from rh_skills.commands.promote import _infer_artifact_profiles
        profiles = _infer_artifact_profiles("ada-guidelines", "risk factors and thresholds for patients")
        types = [p["artifact_type"] for p in profiles]
        assert "evidence-summary" in types

    def test_multi_keyword_source_returns_multiple_profiles(self):
        from rh_skills.commands.promote import _infer_artifact_profiles
        content = "screening criteria for eligibility, care pathway steps, and risk factor scoring"
        profiles = _infer_artifact_profiles("guideline", content)
        types = {p["artifact_type"] for p in profiles}
        assert "decision-table" in types
        assert "care-pathway" in types
        assert "evidence-summary" in types

    def test_no_match_returns_evidence_summary_fallback(self):
        from rh_skills.commands.promote import _infer_artifact_profiles
        profiles = _infer_artifact_profiles("report", "this document has no clinical keyword matches xyz")
        assert len(profiles) == 1
        assert profiles[0]["artifact_type"] == "evidence-summary"


class TestGroupSourcesManyToMany:
    def test_one_source_produces_multiple_artifact_groups(self):
        from rh_skills.commands.promote import _group_sources_for_extract_plan
        records = [
            {
                "name": "acc-aha-lipid",
                "content": "risk factors, exclusion criteria, decision points, and evidence summary for lipid management",
                "relative_path": "sources/normalized/acc-aha-lipid.md",
            }
        ]
        groups = _group_sources_for_extract_plan(records)
        types = {g["artifact_type"] for g in groups}
        assert len(types) > 1
        assert "evidence-summary" in types
        assert "decision-table" in types

    def test_source_not_duplicated_within_group(self):
        from rh_skills.commands.promote import _group_sources_for_extract_plan
        record = {
            "name": "risk-and-risk-again",
            "content": "risk risk risk factors for many risk conditions with evidence synthesis",
            "relative_path": "sources/normalized/r.md",
        }
        groups = _group_sources_for_extract_plan([record])
        ev_group = next(g for g in groups if g["artifact_type"] == "evidence-summary")
        assert len(ev_group["sources"]) == 1

    def test_two_sources_same_type_grouped_together(self):
        from rh_skills.commands.promote import _group_sources_for_extract_plan
        records = [
            {"name": "src-a", "content": "risk factors for cardiovascular events with evidence", "relative_path": "a.md"},
            {"name": "src-b", "content": "additional risk factor analysis and evidence synthesis", "relative_path": "b.md"},
        ]
        groups = _group_sources_for_extract_plan(records)
        ev_group = next(g for g in groups if g["artifact_type"] == "evidence-summary")
        assert len(ev_group["sources"]) == 2


# ── _sanitize_yaml tests ──────────────────────────────────────────────


def test_sanitize_yaml_quotes_gt_lt_scalars():
    """Values starting with > or < get safely quoted after round-trip."""
    raw = "magnitude: >=190 mg/dL\nage: >75 years\nlow: <40 mg/dL\n"
    result = _sanitize_yaml(raw)
    y = YAML()
    data = y.load(result)
    assert data["magnitude"] == ">=190 mg/dL"
    assert data["age"] == ">75 years"
    assert data["low"] == "<40 mg/dL"


def test_sanitize_yaml_returns_raw_on_parse_failure():
    """Unparseable YAML is returned unchanged (validation will catch it)."""
    bad = "key: [\ninvalid\n"
    assert _sanitize_yaml(bad) == bad


def test_sanitize_yaml_preserves_valid_yaml():
    """Already-valid YAML passes through without data loss."""
    raw = 'id: my-artifact\nvalues:\n  - ">=20%"\n  - 40-75 years\n'
    result = _sanitize_yaml(raw)
    y = YAML()
    data = y.load(result)
    assert data["id"] == "my-artifact"
    assert data["values"] == [">=20%", "40-75 years"]


def test_sanitize_yaml_handles_bare_dash_in_mapping_value():
    """Bare '-' as a mapping value is preserved as a string."""
    raw = 'when:\n  c-diabetes: "-"\n  c-risk: not-applicable\n'
    result = _sanitize_yaml(raw)
    y = YAML()
    data = y.load(result)
    assert data["when"]["c-diabetes"] == "-"
    assert data["when"]["c-risk"] == "not-applicable"


def test_sanitize_yaml_quotes_gt_lt_in_list_values():
    """Sequence values starting with > or < get quoted via the pre-pass."""
    raw = (
        "values:\n"
        "  - 40-75 years\n"
        "  - <40 years\n"
        "  - >75 years\n"
    )
    result = _sanitize_yaml(raw)
    y = YAML()
    data = y.load(result)
    assert data["values"] == ["40-75 years", "<40 years", ">75 years"]


def test_sanitize_yaml_quotes_bare_dash_mapping_value():
    """Unquoted bare '-' mapping value gets quoted to avoid sequence parse."""
    raw = "when:\n  c-diabetes: -\n  c-risk: not-applicable\n"
    result = _sanitize_yaml(raw)
    y = YAML()
    data = y.load(result)
    assert data["when"]["c-diabetes"] == "-"


# ── File-lock approve (race condition) ──────────────────────────────────────


def test_concurrent_approve_preserves_all_decisions(tmp_repo):
    """Parallel approve calls should not clobber each other's artifact decisions."""
    import subprocess

    setup_topic_with_normalized_sources(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    plan = load_yaml(plan_path)
    names = [a["name"] for a in plan["artifacts"]]
    assert len(names) >= 2, f"Need at least 2 artifacts for concurrency test, got {names}"

    # Run all approve calls concurrently via subprocesses (avoids CliRunner thread-safety issues)
    env = dict(os.environ)
    procs = []
    for name in names:
        p = subprocess.Popen(
            ["rh-skills", "promote", "approve", "my-skill", "--artifact", name, "--decision", "approved"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        procs.append((name, p))

    errors = []
    for name, p in procs:
        out, err = p.communicate(timeout=10)
        if p.returncode != 0:
            errors.append(f"{name}: rc={p.returncode} {err.decode()}")

    assert not errors, f"Approve errors: {errors}"

    plan = load_yaml(plan_path)
    approved = [a["name"] for a in plan["artifacts"] if a.get("reviewer_decision") == "approved"]
    assert sorted(approved) == sorted(names), (
        f"Expected all {len(names)} artifacts approved, got {len(approved)}: {approved}"
    )


# ── conflicts / resolve-conflict commands ────────────────────────────────────


def test_conflicts_reports_no_open_when_all_resolved(tmp_repo):
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "concerns": [{"concern": "ADA vs AACE", "resolution": "ADA preferred."}],
        "reviewer_decision": "approved",
        "approval_notes": "",
    }])
    runner = CliRunner()
    result = runner.invoke(promote, ["conflicts", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "No open conflicts" in result.output


def test_conflicts_lists_open_extract_conflicts(tmp_repo):
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "concerns": [
            {"concern": "HbA1c threshold disagreement", "resolution": ""},
            {"concern": "Screening interval", "resolution": "Every 3 years per ADA."},
        ],
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }])
    runner = CliRunner()
    result = runner.invoke(promote, ["conflicts", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "HbA1c threshold disagreement" in result.output
    assert "Screening interval" not in result.output  # resolved, should not appear
    assert "1 open conflict" in result.output


def test_conflicts_reports_no_open_when_no_plans_exist(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(promote, ["conflicts", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "No open conflicts" in result.output


def test_resolve_conflict_updates_extract_plan(tmp_repo):
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "concerns": [{"concern": "ADA vs AACE", "resolution": ""}],
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }])
    runner = CliRunner()
    result = runner.invoke(promote, [
        "resolve-conflict", "my-skill",
        "--plan", "extract",
        "--artifact", "art-a",
        "--index", "0",
        "--resolution", "ADA 2024 preferred.",
    ])
    assert result.exit_code == 0, result.output
    assert "Resolved conflict 0" in result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    plan = load_yaml(plan_path)
    art = next(a for a in plan["artifacts"] if a["name"] == "art-a")
    assert art["concerns"][0]["resolution"] == "ADA 2024 preferred."


def test_resolve_conflict_index_out_of_range(tmp_repo):
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "concerns": [{"concern": "Single conflict", "resolution": ""}],
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }])
    runner = CliRunner()
    result = runner.invoke(promote, [
        "resolve-conflict", "my-skill",
        "--plan", "extract",
        "--artifact", "art-a",
        "--index", "5",
        "--resolution", "Some resolution.",
    ])
    assert result.exit_code != 0


def test_resolve_conflict_unknown_artifact(tmp_repo):
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "conflicts": [],
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }])
    runner = CliRunner()
    result = runner.invoke(promote, [
        "resolve-conflict", "my-skill",
        "--plan", "extract",
        "--artifact", "no-such-artifact",
        "--index", "0",
        "--resolution", "Some resolution.",
    ])
    assert result.exit_code != 0


def test_conflicts_scans_both_plans_when_both_exist(tmp_repo):
    """Conflicts from both extract and formalize plans appear in a single listing."""
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "concerns": [{"concern": "Extract conflict", "resolution": ""}],
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }])
    write_formalize_plan(tmp_repo, artifacts=[{
        "name": "form-art",
        "artifact_type": "measure",
        "reviewer_decision": "pending-review",
        "conflicts": [{"conflict": "Formalize conflict", "resolution": ""}],
    }])
    runner = CliRunner()
    result = runner.invoke(promote, ["conflicts", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "Extract conflict" in result.output
    assert "Formalize conflict" in result.output
    assert "2 open conflict" in result.output
