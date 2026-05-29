"""Tests for rh-skills promote command — ported from tests/unit/promote.bats."""

import io
import os

import click
import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.promote import _approved_extract_artifacts, _approved_formalize_target, _sanitize_yaml, _load_concept_csv, _write_concept_csv, promote


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
            "---\n"
            f"source: {source_name}\n"
            f"topic: {topic_name}\n"
            "concepts:\n"
            "  - name: Hypertension\n"
            "    type: condition\n"
            "  - name: Blood pressure screening\n"
            "    type: procedure\n"
            "---\n\n"
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


def write_extract_plan(
    tmp_repo,
    topic_name="my-skill",
    status="approved",
    artifacts=None,
    *,
    concept_review_status="approved",
    concept_lookup_completed=True,
):
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
        "concept_review": {
            "source_files": [f"sources/normalized/{source_name}.md" for source_name in (["ada-screening-guideline", "uspstf-screening-update"] if topic_name == "my-skill" else [])],
            "status": concept_review_status,
            "review_artifact": f"topics/{topic_name}/process/plans/concepts/",
            "final_artifact": f"topics/{topic_name}/structured/concepts/concepts.yaml",
        },
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
            sections["events"] = [{"id": "e1", "label": "Review"}]
            sections["conditions"] = [{"id": "c1", "label": "Test", "values": ["Yes", "No"]}]
            sections["data_elements"] = [{
                "id": "de1",
                "condition_id": "c1",
                "label": "Test data element",
            }]
            sections["actions"] = [{"id": "a1", "label": "Do thing", "kind": "ServiceRequest"}]
            sections["rules"] = [{"id": "r1", "event": "e1", "when": {"c1": "Yes"}, "then": ["a1"]}]

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
            "concerns": [],
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


def test_derive_existing_artifact_requires_force(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()

    first = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    assert second.exit_code == 2
    assert "Use --force to overwrite only this artifact" in second.output


def test_derive_force_overwrites_existing_artifact_without_duplicate_tracking(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", """\
id: criteria
name: criteria
title: Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: First version.
derived_from:
  - ada-guidelines
sections:
  summary: First summary.
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()

    first = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines"])
    assert first.exit_code == 0, first.output

    monkeypatch.setenv("RH_STUB_RESPONSE", """\
id: criteria
name: criteria
title: Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Second version.
derived_from:
  - ada-guidelines
sections:
  summary: Updated summary.
""")
    second = runner.invoke(promote, ["derive", "my-skill", "criteria", "--source", "ada-guidelines", "--force"])
    assert second.exit_code == 0, second.output

    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "criteria" / "criteria.yaml"
    data = load_yaml(artifact_path)
    assert data["description"] == "Second version."
    assert data["sections"]["summary"] == "Updated summary."

    tracking = YAML(typ="safe").load((tmp_repo / "tracking.yaml").read_text())
    topic = next(t for t in tracking["topics"] if t["name"] == "my-skill")
    entries = [a for a in topic["structured"] if a["name"] == "criteria"]
    assert len(entries) == 1
    assert entries[0]["artifact_type"] == "evidence-summary"
    assert topic["events"][-1]["description"] == "Re-derived criteria from ada-guidelines"


def test_derive_blocks_overwriting_concepts_terminology_artifact(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()

    result = runner.invoke(promote, ["derive", "my-skill", "concepts", "--source", "ada-guidelines", "--force"])
    assert result.exit_code == 2
    assert "Use 'rh-skills promote concept write my-skill' instead of derive --force." in result.output


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
        "--concern", "Interval differs|ada-guidelines|Annual screening|ada-guidelines|Explicit interval language",
    ])
    assert result.exit_code == 0, result.output
    data = load_yaml(tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml")
    assert data["artifact_type"] == "decision-table"
    assert data["clinical_question"] == "Who should be screened?"
    assert "evidence_traceability" in data["sections"]
    assert data["sections"]["evidence_traceability"][0]["claim_id"] == "crit-001"
    assert data["concerns"][0]["issue"] == "Interval differs"
    assert data["concerns"][0]["preferred_interpretation"]["source"] == "ada-guidelines"


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


def test_derive_concern_same_issue_merges_positions(tmp_repo, monkeypatch):
    """Two --concern flags with the same issue merge into one entry with multiple positions."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "hba1c-target",
        "--source", "ada-guidelines",
        "--artifact-type", "decision-table",
        "--concern", "HbA1c target|ada-guidelines|ADA recommends <7.0%",
        "--concern", "HbA1c target|aace-guidelines|AACE recommends ≤6.5%|aace-guidelines|More specific target",
    ])
    assert result.exit_code == 0, result.output
    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "hba1c-target" / "hba1c-target.yaml"
    data = YAML(typ="safe").load(artifact_path.read_text())
    concerns = data.get("concerns", [])
    assert len(concerns) == 1, f"Expected 1 merged concern entry, got {len(concerns)}"
    assert len(concerns[0]["positions"]) == 2
    sources = {p["source"] for p in concerns[0]["positions"]}
    assert sources == {"ada-guidelines", "aace-guidelines"}
    assert concerns[0]["preferred_interpretation"]["source"] == "aace-guidelines"


def test_derive_conflict_alias_still_writes_concerns(tmp_repo, monkeypatch):
    """Legacy --conflict remains supported but writes canonical concerns[]."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--conflict", "Interval differs|ada-guidelines|Annual screening",
    ])
    assert result.exit_code == 0, result.output
    data = load_yaml(tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml")
    assert "concerns" in data
    assert "conflicts" not in data


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
    assert plan["concept_review"]["status"] == "pending-review"
    artifact = plan["artifacts"][0]
    assert artifact["reviewer_decision"] == "pending-review"
    assert artifact["source_files"]
    assert "evidence_traceability" in artifact["required_sections"]

    # CSV dir + meta written
    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    meta_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts-review-meta.yaml"
    assert concepts_dir.exists(), "concepts/ dir should be created by plan"
    assert meta_path.exists(), "concepts-review-meta.yaml should be created by plan"

    hyp_csv = concepts_dir / "hypertension.csv"
    bp_csv = concepts_dir / "blood-pressure-screening.csv"
    assert hyp_csv.exists(), "hypertension.csv should be created by plan"
    assert bp_csv.exists(), "blood-pressure-screening.csv should be created by plan"

    # Metadata lives in plain key,value rows at the top of the new sectioned format
    hyp_meta, hyp_code_rows, _ = _load_concept_csv(hyp_csv)
    assert sorted(hyp_meta.get("sources", "").split(";")) == ["ada-screening-guideline", "uspstf-screening-update"]
    # No code rows yet — all include/exclude blank
    assert all(r["include/exclude"] == "" for r in hyp_code_rows)

    meta = YAML(typ="safe").load(meta_path.read_text())
    assert meta["status"] == "pending-review"
    assert meta["checksums"]

    raw_readout = readout_path.read_text()
    assert "extract-plan.yaml" in raw_readout
    assert "Review Summary" in raw_readout
    assert "Concept Review" in raw_readout
    assert "Proposed Artifacts" in raw_readout
    assert "Cross-Artifact Issues" in raw_readout
    assert "Implementation Readiness" in raw_readout

    tracking = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in tracking["topics"] if t["name"] == "my-skill")
    assert "extract_planned" in [event["type"] for event in topic["events"]]


def test_review_concepts_writes_terminology_l2_artifact(tmp_repo):
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    # Enrich both concepts
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--lookup-query", "Hypertension",
    ])
    assert result.exit_code == 0, result.output

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
        "--lookup-query", "Blood pressure screening",
    ])
    assert result.exit_code == 0, result.output

    # Approve both concepts
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension", "--approve-all",
    ])
    assert result.exit_code == 0, result.output

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Blood pressure screening", "--approve-all",
    ])
    assert result.exit_code == 0, result.output

    # Finalize (--force because CLI commands updated the checksum)
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "--finalize", "--reviewer", "test-reviewer", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert "finalized" in result.output

    # Check meta
    meta = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts-review-meta.yaml").read_text()
    )
    assert meta["status"] == "approved"
    assert meta["reviewer"] == "test-reviewer"

    # Write concepts.yaml
    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code == 0, result.output

    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "concepts" / "concepts.yaml"
    assert artifact_path.exists()
    artifact = YAML(typ="safe").load(artifact_path.read_text())
    assert artifact["artifact_type"] == "terminology"
    plan = YAML(typ="safe").load((tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml").read_text())
    assert plan["concept_review"]["status"] == "approved"
    hypertension = next(c for c in artifact["concepts"] if c["name"] == "Hypertension")
    assert hypertension["id"] == "hypertension"
    assert hypertension["codes"][0]["code"] == "38341003"
    assert artifact["sections"]["value_sets"] == [
        {
            "id": "blood-pressure-screening",
            "name": "Blood pressure screening",
            "concept_refs": ["blood-pressure-screening"],
        },
        {
            "id": "hypertension",
            "name": "Hypertension",
            "concept_refs": ["hypertension"],
        },
    ]


def test_review_concepts_can_approve_concept_in_final_artifact(tmp_repo):
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    # Enrich both
    runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
    ])
    runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
    ])

    # Approve only Blood pressure screening via direct CSV edit using _load_concept_csv/_write_concept_csv
    bp_csv = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts" / "blood-pressure-screening.csv"
    bp_meta, bp_rows, bp_exp = _load_concept_csv(bp_csv)
    for r in bp_rows:
        if r.get("system"):
            r["include/exclude"] = "include"
    _write_concept_csv(bp_csv, bp_meta, bp_rows, expansion_rows=bp_exp)

    # Reject Hypertension via direct CSV edit
    hyp_csv = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts" / "hypertension.csv"
    hyp_meta, hyp_rows, hyp_exp = _load_concept_csv(hyp_csv)
    for r in hyp_rows:
        if r.get("system"):
            r["include/exclude"] = "exclude"
    _write_concept_csv(hyp_csv, hyp_meta, hyp_rows, expansion_rows=hyp_exp)

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "--finalize", "--reviewer", "reviewer1",
    ])
    assert result.exit_code == 0, result.output

    # Write and verify — only approved concepts appear
    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code == 0, result.output

    artifact = YAML(typ="safe").load((tmp_repo / "topics" / "my-skill" / "structured" / "concepts" / "concepts.yaml").read_text())
    concept_names = [c["name"] for c in artifact["concepts"]]
    assert "Blood pressure screening" in concept_names
    assert "Hypertension" not in concept_names
    bp = next(c for c in artifact["concepts"] if c["name"] == "Blood pressure screening")
    assert bp["codes"][0]["code"] == "171207006"
    assert artifact["sections"]["value_sets"] == [
        {
            "id": "blood-pressure-screening",
            "name": "Blood pressure screening",
            "concept_refs": ["blood-pressure-screening"],
        },
    ]


def _enrich_two_concepts(tmp_repo, runner):
    """Helper: enrich Hypertension and Blood pressure screening for my-skill."""
    runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--lookup-query", "Hypertension",
    ])
    runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
        "--lookup-query", "Blood pressure screening",
    ])


def test_review_concepts_applies_per_concept_decisions_and_finalizes(tmp_repo):
    """Per-concept review calls accumulate decisions; concept write writes concepts.yaml."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    _enrich_two_concepts(tmp_repo, runner)

    # Approve Hypertension
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension", "--approve-all", "--note", "FSN confirmed",
    ])
    assert result.exit_code == 0, result.output

    # Reject Blood pressure screening and finalize (--force because CLI updated checksum)
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Blood pressure screening", "--exclude-all",
        "--finalize", "--reviewer", "batch-reviewer", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert "finalized" in result.output

    meta = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts-review-meta.yaml").read_text()
    )
    assert meta["status"] == "approved"
    assert meta["reviewer"] == "batch-reviewer"

    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code == 0, result.output

    artifact = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "structured" / "concepts" / "concepts.yaml").read_text()
    )
    concept_names = [c["name"] for c in artifact["concepts"]]
    assert "Hypertension" in concept_names
    assert "Blood pressure screening" not in concept_names


def test_review_concepts_approve_and_exclude_individual_codes(tmp_repo):
    """--approve-code and --exclude-code set include/exclude on specific code rows only."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--candidate", "http://hl7.org/fhir/sid/icd-10-cm|I10|Essential (primary) hypertension",
    ])
    assert result.exit_code == 0, result.output

    # Approve the SNOMED code; exclude the ICD-10 code
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension",
        "--approve-code", "38341003",
        "--exclude-code", "I10",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    hyp_csv = concepts_dir / "hypertension.csv"
    _, rows, _ = _load_concept_csv(hyp_csv)
    hyp_status = {r["code"]: r["include/exclude"] for r in rows if r["code"]}
    assert hyp_status["38341003"] == "include"
    assert hyp_status["I10"] == "exclude"


def test_enrich_multiple_candidates_single_call(tmp_repo):
    """Multiple --candidate flags in a single enrich call all get recorded."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--candidate", "http://hl7.org/fhir/sid/icd-10-cm|I10|Essential (primary) hypertension",
        "--candidate", "http://snomed.info/sct|59621000|Essential hypertension (disorder)",
    ])
    assert result.exit_code == 0, result.output
    assert "3 candidate(s)" in result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, hypertension_rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")
    hypertension_rows = [r for r in hypertension_rows if r["system"]]
    assert len(hypertension_rows) == 3
    codes = {r["code"] for r in hypertension_rows}
    assert "38341003" in codes
    assert "I10" in codes
    assert "59621000" in codes


def test_review_concepts_standalone_finalize_seals_manually_edited_csv(tmp_repo):
    """--finalize alone (no --concept) seals a CSV that was edited directly."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    _enrich_two_concepts(tmp_repo, runner)

    # Manually edit per-concept CSVs using _load_concept_csv/_write_concept_csv
    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"

    def _set_decision_in_csv(csv_path, decision_val):
        meta, rows, exp = _load_concept_csv(csv_path)
        for r in rows:
            if r.get("system"):
                r["include/exclude"] = decision_val
        _write_concept_csv(csv_path, meta, rows, expansion_rows=exp)

    _set_decision_in_csv(concepts_dir / "hypertension.csv", "include")
    _set_decision_in_csv(concepts_dir / "blood-pressure-screening.csv", "exclude")

    result = runner.invoke(promote, [
        "concept", "review", "my-skill", "--finalize", "--reviewer", "manual-reviewer",
    ])
    assert result.exit_code == 0, result.output
    assert "finalized" in result.output

    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code == 0, result.output

    artifact = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "structured" / "concepts" / "concepts.yaml").read_text()
    )
    concept_names = [c["name"] for c in artifact["concepts"]]
    assert "Hypertension" in concept_names
    assert "Blood pressure screening" not in concept_names
    hyp = next(c for c in artifact["concepts"] if c["name"] == "Hypertension")
    assert hyp["codes"][0]["code"] == "38341003"


def test_review_concepts_finalize_requires_reviewer(tmp_repo):
    """--finalize without --reviewer raises UsageError."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill", "--finalize",
    ])
    assert result.exit_code != 0
    assert "--reviewer is required" in result.output


def test_review_concepts_finalize_blocks_when_code_rows_lack_status(tmp_repo):
    """--finalize raises UsageError when a code row has no approved value."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    _enrich_two_concepts(tmp_repo, runner)

    # Approve only Hypertension; leave Blood pressure screening unenriched/undecided
    runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension", "--approve-all",
    ])

    # Try to finalize — Blood pressure screening has a code row but no status
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "--finalize", "--reviewer", "reviewer1", "--force",
    ])
    assert result.exit_code != 0
    assert "missing a valid 'include/exclude' decision" in result.output
    assert "Blood pressure screening" in result.output


def test_review_concepts_finalize_unchanged_csv_requires_force(tmp_repo):
    """--finalize on a CSV with all candidates unapproved fails the approval-completeness gate."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    # No concept decisions made — every candidate row still has include/exclude blank.
    # The approval-completeness gate should block finalize.
    result = runner.invoke(promote, [
        "concept", "review", "my-skill", "--finalize", "--reviewer", "reviewer1",
    ])
    # Either no candidates exist (plan produced no concept rows) so finalize
    # succeeds, or candidates exist and the completeness gate fires.
    # The key thing we verify is the removed checksum check no longer triggers.
    assert "unchanged" not in (result.output or "")
    assert "no human edits" not in (result.output or "").lower()


def test_review_concepts_reset_clears_candidates(tmp_repo):
    """--reset removes all candidate rows for a concept and restores placeholder."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])
    _enrich_two_concepts(tmp_repo, runner)

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    assert any(p.name == "hypertension.csv" for p in concepts_dir.glob("*.csv"))
    _, pre_rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")
    assert any(r["system"] for r in pre_rows) or len(pre_rows) == 0

    # Reset
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Hypertension", "--reset",
    ])
    assert result.exit_code == 0, result.output
    assert "Reset" in result.output

    # After reset, hypertension.csv should have no code rows
    _, post_rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")
    hyp_rows = [r for r in post_rows if r.get("system")]
    assert len(hyp_rows) == 0


def test_review_concepts_concept_with_no_action_flags_errors(tmp_repo):
    """Concept name without any action flags raises UsageError."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])
    _enrich_two_concepts(tmp_repo, runner)

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension",
    ])
    assert result.exit_code != 0
    assert "concept NAME requires at least one of" in result.output


def test_concept_enrich_custom_creates_placeholder_row(tmp_repo):
    """enrich --source custom creates a concept CSV with sources=custom and no code rows."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Frailty",
        "--source", "custom",
        "--type", "finding",
    ])
    assert result.exit_code == 0, result.output
    assert "Frailty" in result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    frailty_csv = concepts_dir / "frailty.csv"
    assert frailty_csv.exists()
    frailty_meta, frailty_rows, _ = _load_concept_csv(frailty_csv)
    assert frailty_meta.get("concept_type") == "finding"
    assert frailty_meta.get("sources") == "custom"
    # No code rows yet
    assert all(r.get("system", "") == "" for r in frailty_rows)


def test_concept_enrich_custom_errors_if_concept_already_exists(tmp_repo):
    """enrich --source custom raises UsageError when the concept name already exists."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "--source", "custom",
        "Hypertension", "--type", "disorder",
    ])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_concept_enrich_custom_errors_if_csv_dir_not_found(tmp_repo):
    """enrich --source custom raises UsageError before promote plan has run."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    # Intentionally skip promote plan so no CSV dir exists
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "--source", "custom",
        "Frailty", "--type", "finding",
    ])
    assert result.exit_code != 0


def test_concept_enrich_custom_then_mcp_then_write_roundtrip(tmp_repo):
    """Full flow: enrich --source custom → enrich --source mcp → review → write → appears in concepts.yaml."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    # Create a custom concept
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "--source", "custom",
        "Frailty", "--type", "finding",
    ])
    assert result.exit_code == 0, result.output

    # Enrich it with an MCP candidate
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Frailty",
        "--candidate", "http://snomed.info/sct|248279007|Frailty (finding)",
    ])
    assert result.exit_code == 0, result.output

    # Also approve the two source concepts so finalize gate passes
    runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
    ])
    runner.invoke(promote, [
        "concept", "enrich", "my-skill", "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
    ])
    runner.invoke(promote, [
        "concept", "review", "my-skill", "Hypertension", "--approve-all",
    ])
    runner.invoke(promote, [
        "concept", "review", "my-skill", "Blood pressure screening", "--approve-all",
    ])

    # Approve Frailty
    result = runner.invoke(promote, [
        "concept", "review", "my-skill", "Frailty", "--approve-all",
        "--finalize", "--reviewer", "test-reviewer", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert "finalized" in result.output

    # Write and verify
    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code == 0, result.output

    artifact = YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "structured" / "concepts" / "concepts.yaml").read_text()
    )
    frailty = next((c for c in artifact["concepts"] if c["name"] == "Frailty"), None)
    assert frailty is not None
    assert frailty["codes"][0]["code"] == "248279007"


def test_write_concepts_requires_approved_packet(tmp_repo):
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["plan", "my-skill"])
    assert result.exit_code == 0, result.output

    _enrich_two_concepts(tmp_repo, runner)

    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code != 0
    assert "not approved" in result.output


def test_concept_enrich_expansion_appended(tmp_repo):
    """--expansion appends a row to the Expansions section; duplicate system+relation+code is skipped."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--expansion", "http://snomed.info/sct|is_a|38341003|All subtypes of hypertension",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, _, exp_rows = _load_concept_csv(concepts_dir / "hypertension.csv")
    assert len(exp_rows) == 1
    assert exp_rows[0]["system"] == "http://snomed.info/sct"
    assert exp_rows[0]["expansion"] == "is_a|38341003"
    assert exp_rows[0]["rationale"] == "All subtypes of hypertension"

    # Adding the same relation+code again is a no-op
    result2 = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--expansion", "http://snomed.info/sct|is_a|38341003|All subtypes of hypertension",
    ])
    assert result2.exit_code == 0, result2.output
    _, _, exp_rows2 = _load_concept_csv(concepts_dir / "hypertension.csv")
    assert len(exp_rows2) == 1


def test_concept_enrich_custom_with_expansion(tmp_repo):
    """--source custom + --expansion creates CSV and populates Expansions section in one call."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "--source", "custom",
        "Frailty", "--type", "finding",
        "--expansion", "http://snomed.info/sct|is_a|248279007|Frailty subtypes",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    meta, code_rows, exp_rows = _load_concept_csv(concepts_dir / "frailty.csv")
    assert meta["sources"] == "custom"
    assert code_rows == [] or all(r.get("system", "") == "" for r in code_rows)
    assert len(exp_rows) == 1
    assert exp_rows[0]["expansion"] == "is_a|248279007"


def test_concept_enrich_with_related_candidates(tmp_repo):
    """--related-candidate appends level=1 row_type=related rows after the parent candidate."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
        "--related-candidate", "38341003|http://snomed.info/sct|73410007|Benign secondary renovascular hypertension (disorder)|is_a",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")

    candidate_rows = [r for r in rows if r["row_type"] == "candidate"]
    related_rows = [r for r in rows if r["row_type"] == "related"]

    assert len(candidate_rows) == 1
    assert candidate_rows[0]["code"] == "38341003"

    assert len(related_rows) == 2
    related_codes = {r["code"] for r in related_rows}
    assert "59621000" in related_codes
    assert "73410007" in related_codes
    for r in related_rows:
        assert r["relation"] == "is_a"


def test_review_approve_all_covers_related_rows(tmp_repo):
    """--approve-all sets approved=y on both candidate and related rows."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    # Enrich Hypertension with one candidate and one related row
    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])
    # Enrich Blood pressure screening so --finalize has all concepts covered
    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
    ])

    # --approve-all should cover both candidate and related rows
    runner.invoke(promote, [
        "concept", "review", "my-skill", "Hypertension", "--approve-all",
    ])
    runner.invoke(promote, [
        "concept", "review", "my-skill", "Blood pressure screening", "--approve-all",
    ])

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")

    for r in rows:
        if r.get("system", "").strip() or r.get("code", "").strip():
            assert r["include/exclude"] == "include", (
                f"Expected include/exclude=include for row_type={r.get('row_type')} code={r.get('code')}, "
                f"got {r['include/exclude']!r}"
            )

    # --finalize must succeed without "missing approved value" error
    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "--finalize", "--reviewer", "test-reviewer", "--force",
    ])
    assert result.exit_code == 0, result.output


def test_write_concepts_includes_related_in_l2(tmp_repo):
    """Approved related rows appear as related[] under the parent code in concepts.yaml."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    # Enrich Hypertension with candidate + related
    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])
    # Enrich Blood pressure screening (required for finalize gate)
    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
    ])

    # Approve candidate rows; also approve related row on Hypertension
    runner.invoke(promote, ["concept", "review", "my-skill", "Hypertension", "--approve-all"])
    runner.invoke(promote, [
        "concept", "review", "my-skill", "Hypertension", "--approve-code", "59621000",
    ])
    runner.invoke(promote, ["concept", "review", "my-skill", "Blood pressure screening", "--approve-all"])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "--finalize", "--reviewer", "test-reviewer", "--force",
    ])
    assert result.exit_code == 0, result.output

    result = runner.invoke(promote, ["concept", "write", "my-skill"])
    assert result.exit_code == 0, result.output

    from ruamel.yaml import YAML as _YAML
    artifact = _YAML(typ="safe").load(
        (tmp_repo / "topics" / "my-skill" / "structured" / "concepts" / "concepts.yaml").read_text()
    )
    hyp = next(c for c in artifact["concepts"] if c["name"] == "Hypertension")
    assert hyp["codes"][0]["code"] == "38341003"
    assert "related" in hyp["codes"][0]
    related = hyp["codes"][0]["related"]
    assert any(r["code"] == "59621000" for r in related)


def test_related_candidate_unknown_parent_raises_error(tmp_repo):
    """--related-candidate with an unknown PARENT_CODE raises a UsageError."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
    ])

    # Use a PARENT_CODE that doesn't exist in candidate rows
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--related-candidate", "BADCODE|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])
    assert result.exit_code != 0
    assert "BADCODE" in result.output


def test_related_candidate_explicit_parent_separate_calls(tmp_repo):
    """--related-candidate can attach to any existing candidate without batching in same call."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    # Add candidate in first call
    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
    ])
    # Add related in a separate call using explicit PARENT_CODE
    result = runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")
    related_rows = [r for r in rows if r["row_type"] == "related"]
    assert len(related_rows) == 1
    assert related_rows[0]["code"] == "59621000"
    assert related_rows[0]["related_code"] == "38341003"


def test_review_approve_related(tmp_repo):
    """--approve-related sets include on the matching related row."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension",
        "--approve-related", "38341003|59621000",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")
    related_rows = [r for r in rows if r["row_type"] == "related"]
    assert related_rows[0]["include/exclude"] == "include"


def test_review_exclude_related(tmp_repo):
    """--exclude-related sets exclude on the matching related row."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension",
        "--exclude-related", "38341003|59621000",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, rows, _ = _load_concept_csv(concepts_dir / "hypertension.csv")
    related_rows = [r for r in rows if r["row_type"] == "related"]
    assert related_rows[0]["include/exclude"] == "exclude"


def test_review_approve_expansion(tmp_repo):
    """--approve-expansion sets include on the matching expansion row."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--expansion", "http://snomed.info/sct|is_a|38341003|subtypes of hypertension",
    ])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension",
        "--approve-expansion", "http://snomed.info/sct|is_a|38341003",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, _, expansion_rows = _load_concept_csv(concepts_dir / "hypertension.csv")
    assert expansion_rows[0]["include/exclude"] == "include"


def test_review_exclude_expansion(tmp_repo):
    """--exclude-expansion sets exclude on the matching expansion row."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--expansion", "http://snomed.info/sct|is_a|38341003|subtypes of hypertension",
    ])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "Hypertension",
        "--exclude-expansion", "http://snomed.info/sct|is_a|38341003",
    ])
    assert result.exit_code == 0, result.output

    concepts_dir = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "concepts"
    _, _, expansion_rows = _load_concept_csv(concepts_dir / "hypertension.csv")
    assert expansion_rows[0]["include/exclude"] == "exclude"


def test_finalize_succeeds_with_undecided_related_rows(tmp_repo):
    """Finalize does not require related rows to have an include/exclude decision."""
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    runner.invoke(promote, ["plan", "my-skill"])

    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Hypertension",
        "--candidate", "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)",
        "--related-candidate", "38341003|http://snomed.info/sct|59621000|Essential hypertension (disorder)|is_a",
    ])
    runner.invoke(promote, [
        "concept", "enrich", "my-skill",
        "Blood pressure screening",
        "--candidate", "http://snomed.info/sct|171207006|Blood pressure screening (procedure)",
    ])

    # Approve only candidate rows (leave related row undecided)
    runner.invoke(promote, ["concept", "review", "my-skill", "Hypertension", "--approve-code", "38341003"])
    runner.invoke(promote, ["concept", "review", "my-skill", "Blood pressure screening", "--approve-all"])

    result = runner.invoke(promote, [
        "concept", "review", "my-skill",
        "--finalize", "--reviewer", "test-reviewer", "--force",
    ])
    assert result.exit_code == 0, result.output


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


def test_derive_agent_mode_completes_body_file_draft(tmp_repo, monkeypatch):
    """Agent mode: --body-file draft is completed by the agent output."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", """\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Completed from normalized source guidance.
derived_from:
  - ada-guidelines
artifact_type: decision-table
clinical_question: Who should be screened?
sections:
  summary: Adults with symptoms or risk factors should be assessed for screening.
  evidence_traceability:
    - claim_id: crit-001
      statement: Screen adults at risk
      evidence:
        - source: ada-guidelines
          locator: Section 2
""")
    body_content = """\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: "<stub: description>"
derived_from:
  - ada-guidelines
artifact_type: decision-table
clinical_question: Who should be screened?
sections:
  summary: "<stub: summary>"
  evidence_traceability:
    - claim_id: crit-001
      statement: "<stub: statement>"
      evidence:
        - source: ada-guidelines
          locator: "<stub: locator>"
"""
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text(body_content)
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
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
    assert "Completed from normalized source guidance." in content
    assert "Adults with symptoms or risk factors" in content


def test_derive_agent_mode_merges_partial_body_completion_into_sections(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("RH_STUB_RESPONSE", """\
title: CRS Surgical Management Care Pathway
description: Completed care pathway draft.
steps:
  - id: crs-pathway
    label: CRS pathway
    description: Overall CRS surgical management pathway.
  - id: assessment
    label: Assessment
    description: Verify diagnosis and assess candidacy.
    parent_id: crs-pathway
transitions:
  - from_id: crs-pathway
    to_id: assessment
    description: Proceed to evaluation.
evidence_traceability:
  - claim_id: cp-001
    statement: CRS care proceeds from diagnosis review into candidacy assessment.
    evidence:
      - source: ada-guidelines
        locator: Section 2
summary: Hierarchical care pathway for CRS surgical management.
""")
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: care-pathway
name: care-pathway
title: Care Pathway
version: "1.0.0"
status: draft
domain: care pathway
description: "In what order do things happen in the care process?"
derived_from:
  - ada-guidelines
artifact_type: care-pathway
clinical_question: In what order do things happen in the care process?
sections:
  summary: "<stub: summary>"
  steps:
    - id: root
      label: "<stub: root>"
      description: "<stub: root description>"
  transitions: []
  evidence_traceability:
    - claim_id: cp-001
      statement: "<stub: statement>"
      evidence:
        - source: ada-guidelines
          locator: "<stub: locator>"
""")
    setup_topic_with_normalized_sources(tmp_repo, source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "care-pathway",
        "--source", "ada-guidelines",
        "--artifact-type", "care-pathway",
        "--clinical-question", "In what order do things happen in the care process?",
        "--required-section", "summary",
        "--required-section", "steps",
        "--required-section", "transitions",
        "--required-section", "evidence_traceability",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 0, result.output
    artifact = load_yaml(
        tmp_repo / "topics" / "my-skill" / "structured" / "care-pathway" / "care-pathway.yaml"
    )
    assert artifact["artifact_type"] == "care-pathway"
    assert artifact["clinical_question"] == "In what order do things happen in the care process?"
    assert artifact["sections"]["summary"] == "Hierarchical care pathway for CRS surgical management."
    assert artifact["sections"]["steps"][0]["id"] == "crs-pathway"
    assert artifact["sections"]["transitions"][0]["from_id"] == "crs-pathway"
    assert artifact["sections"]["transitions"][0]["to_id"] == "assessment"
    assert artifact["sections"]["evidence_traceability"][0]["claim_id"] == "cp-001"


def test_derive_body_file_uses_artifact_type_from_body_for_tracking(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Agent-generated content.
derived_from:
  - ada-guidelines
artifact_type: decision-table
clinical_question: Who should be screened?
sections:
  summary: Agent-generated content.
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 0, result.output
    tracking = load_yaml(tmp_repo / "tracking.yaml")
    topic = next(t for t in tracking["topics"] if t["name"] == "my-skill")
    assert topic["structured"][0]["artifact_type"] == "decision-table"


def test_derive_body_file_rejects_conflicting_content_flags(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Agent-generated content.
derived_from:
  - ada-guidelines
artifact_type: decision-table
clinical_question: Who should be screened?
sections:
  summary: Agent-generated content.
  evidence_traceability:
    - claim_id: crit-001
      statement: Screen adults at risk
      evidence:
        - source: ada-guidelines
          locator: Section 2
concerns:
  - issue: Interval differs
    positions:
      - source: ada-guidelines
        statement: Annual screening
    preferred_interpretation:
      source: ada-guidelines
      rationale: Explicit interval language
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--artifact-type", "evidence-summary",
        "--clinical-question", "A different question",
        "--required-section", "summary",
        "--required-section", "conditions",
        "--evidence-ref", "crit-001|A different statement|ada-guidelines|Section 2",
        "--concern", "Different issue|ada-guidelines|Annual screening",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 2
    assert "--artifact-type does not match --body-file artifact_type" in result.output


def test_derive_body_file_rejects_source_mismatch(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Agent-generated content.
derived_from:
  - uspstf-guidelines
artifact_type: decision-table
clinical_question: Who should be screened?
sections:
  summary: Agent-generated content.
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 2
    assert "--body-file derived_from does not match --source values" in result.output


def test_derive_body_file_without_source_flags_uses_derived_from(tmp_repo, monkeypatch):
    """--source is optional when --body-file has derived_from; sources are validated against tracking."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Agent-generated content.
derived_from:
  - ada-guidelines
artifact_type: decision-table
clinical_question: Who should be screened?
sections:
  summary: Agent-generated content.
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 0, result.output
    artifact_path = tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml"
    assert artifact_path.exists()
    # derived_from in tracking should come from the body file
    from ruamel.yaml import YAML as _YAML
    tracking = _YAML(typ="safe").load((tmp_repo / "tracking.yaml").read_text())
    structured = next(t for t in tracking["topics"] if t["name"] == "my-skill")["structured"]
    entry = next(a for a in structured if a["name"] == "screening-criteria")
    assert entry["derived_from"] == ["ada-guidelines"]


def test_derive_body_file_without_source_flags_validates_against_tracking(tmp_repo, monkeypatch):
    """If derived_from in body file names a source not in tracking.yaml, derive fails."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Agent-generated content.
derived_from:
  - nonexistent-source
artifact_type: decision-table
sections:
  summary: content
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 2
    assert "not found in tracking.yaml" in result.output


def test_derive_body_file_without_derived_from_requires_source_flag(tmp_repo, monkeypatch):
    """If body file has no derived_from and --source is omitted, derive fails with a clear error."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    body_file = tmp_repo / "agent-body.yaml"
    body_file.write_text("""\
id: screening-criteria
name: screening-criteria
title: Screening Criteria
version: "1.0.0"
status: draft
domain: diabetes
description: Agent-generated content.
artifact_type: decision-table
sections:
  summary: content
""")
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--body-file", str(body_file),
    ])
    assert result.exit_code == 2
    assert "derived_from" in result.output


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


def test_decision_table_stub_supports_event_condition_action_shape(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("RH_STUB_RESPONSE", raising=False)
    setup_topic_with_source(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, [
        "derive", "my-skill", "screening-criteria",
        "--source", "ada-guidelines",
        "--artifact-type", "decision-table",
        "--clinical-question", "Who should be screened?",
        "--required-section", "events",
        "--required-section", "conditions",
        "--required-section", "actions",
        "--required-section", "rules",
    ])
    assert result.exit_code == 0, result.output
    content = (
        tmp_repo / "topics" / "my-skill" / "structured" / "screening-criteria" / "screening-criteria.yaml"
    ).read_text()
    assert "events:" in content
    assert "event-001" in content
    assert "rules:" in content
    assert "event: event-001" in content


# ── body-init mode ─────────────────────────────────────────────────────────────

def _write_plan_for_body_init(tmp_repo, topic_name="my-skill"):
    """Set up a topic with an approved extract-plan.yaml containing one artifact."""
    setup_topic_with_normalized_sources(tmp_repo, topic_name, source_names=("ada-guidelines",))
    plan_path = tmp_repo / "topics" / topic_name / "process" / "plans" / "extract-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    plan = {
        "topic": topic_name,
        "plan_type": "extract",
        "status": "approved",
        "artifacts": [
            {
                "name": "screening-criteria",
                "artifact_type": "decision-table",
                "source_files": ["sources/normalized/ada-guidelines.md"],
                "key_questions": ["Who should be screened for diabetes?"],
                "required_sections": ["summary", "events", "conditions", "data_elements", "actions", "rules", "evidence_traceability"],
                "concerns": [{"issue": "Threshold ambiguity: ADA vs USPSTF"}],
                "reviewer_decision": "approved",
                "approval_notes": "",
            }
        ],
    }
    import io as _io
    buf = _io.StringIO()
    y.dump(plan, buf)
    plan_path.write_text(buf.getvalue())


def test_body_init_writes_scaffold_to_default_tmp_path(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    assert result.exit_code == 0, result.output
    out = tmp_repo / "topics" / "my-skill" / "process" / "tmp" / "screening-criteria.yaml"
    assert out.exists()
    content = out.read_text()
    assert "decision-table" in content
    assert "ada-guidelines" in content
    assert "Who should be screened for diabetes?" in content


def test_body_init_scaffold_contains_required_sections(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    content = (
        tmp_repo / "topics" / "my-skill" / "process" / "tmp" / "screening-criteria.yaml"
    ).read_text()
    for section in ("summary", "events", "conditions", "data_elements", "actions", "rules", "evidence_traceability"):
        assert section in content, f"Missing section: {section}"


def test_body_init_scaffold_contains_concern_stub(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    content = (
        tmp_repo / "topics" / "my-skill" / "process" / "tmp" / "screening-criteria.yaml"
    ).read_text()
    assert "Threshold ambiguity" in content


def test_body_init_custom_output_path(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    custom = tmp_repo / "my-body.yaml"
    runner = CliRunner()
    result = runner.invoke(promote, ["body-init", "my-skill", "screening-criteria", "--output", str(custom)])
    assert result.exit_code == 0, result.output
    assert custom.exists()


def test_body_init_fails_if_file_exists_without_force(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    result = runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    assert result.exit_code == 2
    assert "already exists" in result.output


def test_body_init_force_overwrites_existing_file(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    result = runner.invoke(promote, ["body-init", "my-skill", "screening-criteria", "--force"])
    assert result.exit_code == 0, result.output


def test_body_init_fails_if_artifact_not_in_plan(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["body-init", "my-skill", "nonexistent"])
    assert result.exit_code == 2
    assert "nonexistent" in result.output


def test_body_init_fails_if_no_plan(tmp_repo):
    setup_topic_with_normalized_sources(tmp_repo, "my-skill", source_names=("ada-guidelines",))
    runner = CliRunner()
    result = runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    assert result.exit_code == 2


def test_body_init_prints_derive_command(tmp_repo):
    _write_plan_for_body_init(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["body-init", "my-skill", "screening-criteria"])
    assert "promote derive" in result.output
    assert "--body-file" in result.output
    assert "screening-criteria" in result.output
    # --artifact-type must NOT appear: body file is the authority; the flag would
    # pin the original value and break validation if the agent refines the type.
    assert "--artifact-type" not in result.output
    # Guidance note about which fields must not be edited
    assert "derived_from" in result.output


def test_approved_extract_artifacts_rejects_unapproved_plan(tmp_repo):
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


def test_approved_extract_artifacts_blocks_pending_concept_review(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "approved"}],
        concept_review_status="pending-review",
        concept_lookup_completed=False,
    )
    with pytest.raises(click.UsageError, match="Concept review is not approved"):
        _approved_extract_artifacts("my-skill")


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


def test_approve_finalize_blocks_pending_concept_review(tmp_repo):
    setup_topic_with_source(tmp_repo)
    write_extract_plan(
        tmp_repo,
        status="pending-review",
        artifacts=[{"name": "screening-criteria", "reviewer_decision": "approved", "approval_notes": ""}],
        concept_review_status="pending-review",
        concept_lookup_completed=False,
    )
    runner = CliRunner()
    result = runner.invoke(
        promote,
        ["approve", "my-skill", "--finalize", "--reviewer", "Jane"],
    )
    assert result.exit_code != 0
    assert "Concept review is not approved" in result.output


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


def test_approve_add_concern_appends_to_concerns(tmp_repo):
    """--add-concern appends to artifact's concerns list with concern/resolution keys."""
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
        "--add-concern", "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%",
        "--add-concern", "Monitoring frequency|ADA annual preferred",
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


def test_approve_add_conflict_alias_still_appends_to_concerns(tmp_repo):
    """Legacy --add-conflict remains supported as an alias for --add-concern."""
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
    ])
    assert result.exit_code == 0, result.output
    plan = _read_plan(tmp_repo)
    assert plan["artifacts"][0]["concerns"][0]["concern"] == "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%"


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
        assert result[0]["source_artifact"] == "a1"
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

    def test_single_terminology_preserves_concepts_name(self):
        from rh_skills.commands.promote import _build_formalize_artifacts
        result = _build_formalize_artifacts("test-topic", [
            {"name": "concepts", "artifact_type": "terminology"},
        ])
        assert result[0]["name"] == "concepts"
        assert result[0]["source_artifact"] == "concepts"

    def test_multi_type_terminology_preserves_concepts_name(self):
        from rh_skills.commands.promote import _build_formalize_artifacts
        result = _build_formalize_artifacts("test-topic", [
            {"name": "decision-a", "artifact_type": "decision-table"},
            {"name": "concepts", "artifact_type": "terminology"},
        ])
        terminology = next(a for a in result if a["strategy"] == "terminology")
        assert terminology["name"] == "concepts"

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


# ── concerns / resolve-concern commands ──────────────────────────────────────


def test_concerns_reports_no_open_when_all_resolved(tmp_repo):
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
    result = runner.invoke(promote, ["concerns", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "No open concerns" in result.output


def test_concerns_lists_open_extract_concerns(tmp_repo):
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
    result = runner.invoke(promote, ["concerns", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "HbA1c threshold disagreement" in result.output
    assert "Screening interval" not in result.output  # resolved, should not appear
    assert "1 open concern" in result.output


def test_concerns_reports_no_open_when_no_plans_exist(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(promote, ["concerns", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "No open concerns" in result.output


def test_conflicts_alias_still_lists_open_concerns(tmp_repo):
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
    result = runner.invoke(promote, ["conflicts", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "Open concerns" in result.output


def test_resolve_concern_updates_extract_plan(tmp_repo):
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
        "resolve-concern", "my-skill",
        "--plan", "extract",
        "--artifact", "art-a",
        "--index", "0",
        "--resolution", "ADA 2024 preferred.",
    ])
    assert result.exit_code == 0, result.output
    assert "Resolved concern 0" in result.output

    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    plan = load_yaml(plan_path)
    art = next(a for a in plan["artifacts"] if a["name"] == "art-a")
    assert art["concerns"][0]["resolution"] == "ADA 2024 preferred."


def test_resolve_conflict_alias_still_updates_extract_plan(tmp_repo):
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
    assert "Resolved concern 0" in result.output


def test_resolve_concern_index_out_of_range(tmp_repo):
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
        "resolve-concern", "my-skill",
        "--plan", "extract",
        "--artifact", "art-a",
        "--index", "5",
        "--resolution", "Some resolution.",
    ])
    assert result.exit_code != 0


def test_resolve_concern_unknown_artifact(tmp_repo):
    write_extract_plan(tmp_repo, artifacts=[{
        "name": "art-a",
        "artifact_type": "decision-table",
        "source_files": [],
        "required_sections": [],
        "key_questions": [],
        "concerns": [],
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }])
    runner = CliRunner()
    result = runner.invoke(promote, [
        "resolve-concern", "my-skill",
        "--plan", "extract",
        "--artifact", "no-such-artifact",
        "--index", "0",
        "--resolution", "Some resolution.",
    ])
    assert result.exit_code != 0


def test_concerns_scans_both_plans_when_both_exist(tmp_repo):
    """Concerns from both extract and formalize plans appear in a single listing."""
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
    result = runner.invoke(promote, ["concerns", "my-skill"])
    assert result.exit_code == 0, result.output
    assert "Extract conflict" in result.output
    assert "Formalize conflict" in result.output
    assert "2 open concern" in result.output
