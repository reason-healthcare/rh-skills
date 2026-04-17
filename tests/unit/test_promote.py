"""Tests for rh-skills promote command — ported from tests/unit/promote.bats."""

import io
import os

import click
import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.promote import _approved_extract_artifacts, _approved_formalize_target, promote


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
        {"name": "screening-criteria", "artifact_type": "eligibility-criteria"},
        {"name": "workflow-steps", "artifact_type": "workflow-steps"},
        {"name": "terminology-value-sets", "artifact_type": "terminology-value-sets"},
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
        if artifact_type == "workflow-steps":
            sections["workflow"] = [{"step": "Assess patient"}]
        elif artifact_type == "terminology-value-sets":
            sections["terminology"] = [{"system": "SNOMED"}]
        else:
            sections["criteria"] = ["Adults at risk"]

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
                "conflicts": [],
                "reviewer_decision": "approved",
                "approval_notes": "Use in formalize",
            }
            for spec in artifact_specs
        ],
    )


def write_formalize_plan(tmp_repo, topic_name="my-skill", status="approved", artifacts=None):
    plan_path = tmp_repo / "topics" / topic_name / "process" / "plans" / "formalize-plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    frontmatter = {
        "topic": topic_name,
        "plan_type": "formalize",
        "status": status,
        "reviewer": "Reviewer",
        "reviewed_at": "2026-04-14T12:00:00Z" if status == "approved" else None,
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
        "--artifact-type", "eligibility-criteria",
        "--clinical-question", "Who should be screened?",
        "--required-section", "summary",
        "--required-section", "evidence_traceability",
        "--evidence-ref", "crit-001|Screen adults at risk|ada-guidelines|Section 2",
        "--conflict", "Interval differs|ada-guidelines|Annual screening|ada-guidelines|Explicit interval language",
    ])
    assert result.exit_code == 0, result.output
    data = load_yaml(tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml")
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


def test_derive_conflict_same_issue_merges_positions(tmp_repo, monkeypatch):
    """Two --conflict flags with the same issue merge into one entry with multiple positions."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "hba1c-target",
        "--source", "ada-guidelines",
        "--artifact-type", "decision-points",
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


def test_formalize_plan_writes_review_packet_and_records_event(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["formalize-plan", "my-skill"])
    assert result.exit_code == 0, result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan.md"
    assert plan_path.exists()
    raw = plan_path.read_text()
    assert raw.index("# Review Summary") < raw.index("# Proposed Artifacts") < raw.index("# Cross-Artifact Issues") < raw.index("# Implementation Readiness")

    parts = raw.split("---\n", 2)
    plan = YAML(typ="safe").load(parts[1])
    assert plan["topic"] == "my-skill"
    assert plan["plan_type"] == "formalize"
    assert plan["status"] == "pending-review"
    assert len(plan["artifacts"]) == 1
    artifact = plan["artifacts"][0]
    assert artifact["name"] == "my-skill-pathway"
    assert artifact["implementation_target"] is True
    assert artifact["input_artifacts"] == ["screening-criteria", "workflow-steps", "terminology-value-sets"]
    assert "pathways" in artifact["required_sections"]
    assert "value_sets" in artifact["required_sections"]

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
    assert not (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan.md").exists()


def test_formalize_plan_force_overwrites_existing_packet(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "formalize-plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("old plan")

    runner = CliRunner()
    result = runner.invoke(promote, ["formalize-plan", "my-skill", "--force"])
    assert result.exit_code == 0, result.output
    assert "old plan" not in plan_path.read_text()


def test_approved_formalize_target_requires_approved_target_and_valid_inputs(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    write_formalize_plan(
        tmp_repo,
        artifacts=[{
            "name": "my-skill-pathway",
            "artifact_type": "pathway-package",
            "input_artifacts": ["screening-criteria", "workflow-steps"],
            "rationale": "Primary package",
            "required_sections": ["pathways", "actions"],
            "implementation_target": True,
            "reviewer_decision": "approved",
            "approval_notes": "Proceed",
        }],
    )

    target = _approved_formalize_target("my-skill")
    assert target["name"] == "my-skill-pathway"
    assert target["input_artifacts"] == ["screening-criteria", "workflow-steps"]


def test_approved_formalize_target_blocks_invalid_inputs(tmp_repo):
    setup_topic_with_valid_extract_artifacts(tmp_repo)
    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "workflow-steps" / "workflow-steps.yaml"
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
            "input_artifacts": ["workflow-steps"],
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
        artifacts=[{"name": "decision-points", "reviewer_decision": "pending-review", "approval_notes": ""}],
    )
    runner = CliRunner()
    result = runner.invoke(promote, [
        "approve", "my-skill",
        "--artifact", "decision-points",
        "--decision", "approved",
        "--review-summary", "ADA vs AACE conflict documented; plan approved.",
        "--finalize", "--reviewer", "Test",
    ])
    assert result.exit_code == 0, result.output
    plan = _read_plan(tmp_repo)
    assert plan["review_summary"] == "ADA vs AACE conflict documented; plan approved."
    assert plan["status"] == "approved"


def test_approve_add_conflict_appends_to_conflicts(tmp_repo):
    """--add-conflict appends to artifact's conflicts list with conflict/resolution keys."""
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "hba1c-target", "reviewer_decision": "pending-review",
                    "approval_notes": "", "conflicts": []}],
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
    conflicts = plan["artifacts"][0]["conflicts"]
    assert len(conflicts) == 2
    assert conflicts[0]["conflict"] == "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%"
    assert conflicts[0]["resolution"] == ""
    assert conflicts[1]["conflict"] == "Monitoring frequency"
    assert conflicts[1]["resolution"] == "ADA annual preferred"


# ── Formalize section mapping tests (T031) ───────────────────────────────────


class TestFormalizeSectionMapping:
    """Test _formalize_required_sections() returns correct sections by type."""

    def test_decision_table_includes_actions(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "decision-table"}])
        assert "actions" in result
        assert "pathways" in result

    def test_policy_includes_actions(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "policy"}])
        assert "actions" in result

    def test_assessment_includes_assessments(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "assessment"}])
        assert "assessments" in result
        assert "pathways" in result

    def test_clinical_frame_no_extra_sections(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([{"artifact_type": "clinical-frame"}])
        assert result == ["pathways"]

    def test_mixed_types_union(self):
        from rh_skills.commands.promote import _formalize_required_sections
        result = _formalize_required_sections([
            {"artifact_type": "decision-table"},
            {"artifact_type": "assessment"},
            {"artifact_type": "terminology-value-sets"},
        ])
        assert "pathways" in result
        assert "actions" in result
        assert "assessments" in result
        assert "value_sets" in result


class TestInferArtifactProfiles:
    def test_single_match_returns_one_profile(self):
        from rh_skills.commands.promote import _infer_artifact_profiles
        profiles = _infer_artifact_profiles("ada-guidelines", "risk factors and thresholds for patients")
        types = [p["artifact_type"] for p in profiles]
        assert "risk-factors" in types

    def test_multi_keyword_source_returns_multiple_profiles(self):
        from rh_skills.commands.promote import _infer_artifact_profiles
        content = "screening criteria for eligibility, workflow algorithm steps, and risk factor scoring"
        profiles = _infer_artifact_profiles("guideline", content)
        types = {p["artifact_type"] for p in profiles}
        assert "eligibility-criteria" in types
        assert "workflow-steps" in types
        assert "risk-factors" in types

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
                "content": "risk factors, exclusions, decision points, and evidence summary for lipid management",
                "relative_path": "sources/normalized/acc-aha-lipid.md",
            }
        ]
        groups = _group_sources_for_extract_plan(records)
        types = {g["artifact_type"] for g in groups}
        assert len(types) > 1
        assert "risk-factors" in types
        assert "exclusions" in types

    def test_source_not_duplicated_within_group(self):
        from rh_skills.commands.promote import _group_sources_for_extract_plan
        record = {
            "name": "risk-and-risk-again",
            "content": "risk risk risk factors for many risk conditions",
            "relative_path": "sources/normalized/r.md",
        }
        groups = _group_sources_for_extract_plan([record])
        risk_group = next(g for g in groups if g["artifact_type"] == "risk-factors")
        assert len(risk_group["sources"]) == 1

    def test_two_sources_same_type_grouped_together(self):
        from rh_skills.commands.promote import _group_sources_for_extract_plan
        records = [
            {"name": "src-a", "content": "risk factors for cardiovascular events", "relative_path": "a.md"},
            {"name": "src-b", "content": "additional risk factor analysis", "relative_path": "b.md"},
        ]
        groups = _group_sources_for_extract_plan(records)
        risk_group = next(g for g in groups if g["artifact_type"] == "risk-factors")
        assert len(risk_group["sources"]) == 2
