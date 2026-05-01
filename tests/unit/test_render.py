"""Tests for rh-skills render command."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.render import (
    render,
    _check_completeness,
    REQUIRED_SECTIONS,
)


def _write_artifact(tmp_repo, topic, artifact, data):
    """Write a YAML artifact at the subdirectory path."""
    artifact_dir = tmp_repo / "topics" / topic / "structured" / artifact
    artifact_dir.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    path = artifact_dir / f"{artifact}.yaml"
    from io import StringIO
    buf = StringIO()
    y.dump(data, buf)
    path.write_text(buf.getvalue())
    return path


# ── Generic renderer ────────────────────────────────────────────────────────────


def test_render_generic_summary(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "evidence-item", {
        "id": "evidence-item",
        "name": "evidence-item",
        "title": "Evidence Item",
        "version": "1.0.0",
        "status": "draft",
        "domain": "testing",
        "description": "A test artifact.",
        "artifact_type": "custom-type",
        "sections": {"summary": "This is a summary."},
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "evidence-item"])
    assert result.exit_code == 0
    assert "1 view(s)" in result.output
    artifact_dir = tmp_repo / "topics" / "my-skill" / "structured" / "evidence-item"
    assert (artifact_dir / "evidence-item-report.md").exists()
    content = (artifact_dir / "evidence-item-report.md").read_text()
    assert "Evidence Item" in content


# ── Missing artifact ────────────────────────────────────────────────────────────


def test_render_missing_artifact_exits_1(tmp_repo):
    (tmp_repo / "topics" / "my-skill").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


# ── Missing required sections ───────────────────────────────────────────────────


def test_render_missing_required_sections_exits_1(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "bad-dt", {
        "id": "bad-dt",
        "artifact_type": "decision-table",
        "sections": {
            "conditions": [{"id": "c1", "label": "Condition", "values": ["Yes", "No"]}],
            "actions": [{"id": "a1", "label": "Action"}],
            "rules": [{"id": "r1", "when": {"c1": "Yes"}, "then": ["a1"]}],
        },  # missing events
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "bad-dt"])
    assert result.exit_code == 1


def test_render_decision_table_shows_event_column_when_present(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "good-dt", {
        "id": "good-dt",
        "title": "Good Decision Table",
        "artifact_type": "decision-table",
        "sections": {
            "events": [
                {"id": "ev1", "label": "Screening encounter", "description": "Initial screening trigger"},
            ],
            "conditions": [
                {"id": "c1", "label": "High risk", "values": ["Yes", "No"]},
            ],
            "actions": [
                {"id": "a1", "label": "Order test"},
            ],
            "rules": [
                {"id": "r1", "event": "ev1", "when": {"c1": "Yes"}, "then": ["a1"]},
            ],
        },
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "good-dt"])
    assert result.exit_code == 0
    artifact_dir = tmp_repo / "topics" / "my-skill" / "structured" / "good-dt"
    content = (artifact_dir / "good-dt-report.md").read_text()
    assert "Decision Matrix" in content
    assert "## Rules" in content
    assert "Screening encounter" in content
    assert "| Event Pattern | c1 High risk | Actions |" in content
    assert "| ev1 Screening encounter | Yes | a1 Order test |" in content
    assert "Order test" in content


# ── Evidence-summary ────────────────────────────────────────────────────────────


def test_render_evidence_summary(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "scope-frame", {
        "id": "scope-frame",
        "title": "Evidence Synthesis",
        "artifact_type": "evidence-summary",
        "sections": {
            "summary_points": [
                {"finding_id": "f-1", "statement": "HbA1c screening is effective", "grade": "grade-a"},
            ],
            "risk_factors": [
                {"id": "rf-1", "factor": "Age over 45", "direction": "increases",
                 "magnitude": "2x", "evidence_quality": "grade-b"},
            ],
            "frames": [
                {
                    "id": "frame-1",
                    "population": "Adults 45+",
                    "intervention": "HbA1c screening",
                    "comparison": "No screening",
                    "outcomes": ["Early detection", "Reduced complications"],
                    "timing": "Annual",
                    "setting": "Primary care",
                },
            ],
        },
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "scope-frame"])
    assert result.exit_code == 0
    art_dir = tmp_repo / "topics" / "my-skill" / "structured" / "scope-frame"
    assert (art_dir / "scope-frame-report.md").exists()
    content = (art_dir / "scope-frame-report.md").read_text()
    assert "Adults 45+" in content
    assert "HbA1c screening" in content
    assert "Age over 45" in content
    assert "grade-a" in content


# ── Assessment ──────────────────────────────────────────────────────────────────


def test_render_assessment(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "phq9", {
        "id": "phq9",
        "title": "PHQ-9",
        "artifact_type": "assessment",
        "sections": {
            "instrument": {
                "name": "PHQ-9",
                "purpose": "Depression screening",
                "population": "Adults",
            },
            "items": [
                {
                    "id": "q1",
                    "text": "Little interest or pleasure?",
                    "type": "ordinal",
                    "options": [
                        {"value": 0, "label": "Not at all"},
                        {"value": 1, "label": "Several days"},
                    ],
                },
            ],
            "scoring": {
                "method": "sum",
                "ranges": [
                    {"range": "0-4", "interpretation": "Minimal depression"},
                    {"range": "5-9", "interpretation": "Mild depression"},
                ],
            },
        },
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "phq9"])
    assert result.exit_code == 0
    views = tmp_repo / "topics" / "my-skill" / "structured" / "phq9"
    assert (views / "phq9-report.md").exists()
    assert (views / "phq9-scoring-report.md").exists()
    assert "Little interest" in (views / "phq9-report.md").read_text()
    assert "Minimal depression" in (views / "phq9-scoring-report.md").read_text()


# ── Policy ──────────────────────────────────────────────────────────────────────


def test_render_policy(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "auth-policy", {
        "id": "auth-policy",
        "title": "Prior Auth Policy",
        "artifact_type": "policy",
        "sections": {
            "applicability": {
                "payer_types": ["Commercial"],
                "service_category": "outpatient",
                "codes": [{"system": "CPT", "values": ["99213"]}],
            },
            "criteria": [
                {
                    "id": "cr1",
                    "description": "Clinical necessity documented",
                    "requirement_type": "clinical",
                    "rule": "Must have documented diagnosis",
                },
            ],
            "actions": {
                "approve": {"conditions": "All criteria met"},
                "deny": {"conditions": "Criteria not met", "details": "Appeal available"},
                "pend": {"conditions": "Insufficient documentation"},
            },
        },
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "auth-policy"])
    assert result.exit_code == 0
    views = tmp_repo / "topics" / "my-skill" / "structured" / "auth-policy"
    assert (views / "auth-policy-flowchart.md").exists()
    assert (views / "auth-policy-report.md").exists()
    flowchart = (views / "auth-policy-flowchart.md").read_text()
    assert "```mermaid" in flowchart
    assert "flowchart" in flowchart
    checklist = (views / "auth-policy-report.md").read_text()
    assert "Clinical necessity" in checklist


# ── Decision-table ──────────────────────────────────────────────────────────────


def _make_complete_binary_table():
    """3 binary conditions, 8 rules → complete."""
    return {
        "id": "dt-complete",
        "title": "Complete Decision Table",
        "artifact_type": "decision-table",
        "sections": {
            "events": [
                {"id": "ev1", "label": "Decision evaluation"},
            ],
            "conditions": [
                {"id": "c1", "label": "Condition A", "values": ["yes", "no"]},
                {"id": "c2", "label": "Condition B", "values": ["yes", "no"]},
                {"id": "c3", "label": "Condition C", "values": ["yes", "no"]},
            ],
            "actions": [
                {"id": "a1", "label": "Action 1"},
                {"id": "a2", "label": "Action 2"},
            ],
            "rules": [
                {"id": "r1", "event": "ev1", "when": {"c1": "yes", "c2": "yes", "c3": "yes"}, "then": ["a1"]},
                {"id": "r2", "event": "ev1", "when": {"c1": "yes", "c2": "yes", "c3": "no"}, "then": ["a1"]},
                {"id": "r3", "event": "ev1", "when": {"c1": "yes", "c2": "no", "c3": "yes"}, "then": ["a2"]},
                {"id": "r4", "event": "ev1", "when": {"c1": "yes", "c2": "no", "c3": "no"}, "then": ["a2"]},
                {"id": "r5", "event": "ev1", "when": {"c1": "no", "c2": "yes", "c3": "yes"}, "then": ["a1"]},
                {"id": "r6", "event": "ev1", "when": {"c1": "no", "c2": "yes", "c3": "no"}, "then": ["a2"]},
                {"id": "r7", "event": "ev1", "when": {"c1": "no", "c2": "no", "c3": "yes"}, "then": ["a2"]},
                {"id": "r8", "event": "ev1", "when": {"c1": "no", "c2": "no", "c3": "no"}, "then": ["a2"]},
            ],
        },
    }


def test_render_decision_table_complete(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "dt-complete", _make_complete_binary_table())
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "dt-complete"])
    assert result.exit_code == 0
    art_dir = tmp_repo / "topics" / "my-skill" / "structured" / "dt-complete"
    assert (art_dir / "dt-complete-report.md").exists()
    assert not (art_dir / "dt-complete-decision-tree.md").exists()
    rules_table = (art_dir / "dt-complete-report.md").read_text()
    assert "Decision Matrix" in rules_table
    assert "## Rules" in rules_table
    assert "| Event Pattern | c1 Condition A | c2 Condition B | c3 Condition C | Actions |" in rules_table
    assert "a1 Action 1" in rules_table


def test_render_decision_table_incomplete(tmp_repo):
    data = _make_complete_binary_table()
    # Remove last rule to make it incomplete
    data["sections"]["rules"] = data["sections"]["rules"][:7]
    _write_artifact(tmp_repo, "my-skill", "dt-incomplete", data)
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "dt-incomplete"])
    assert result.exit_code == 0
    report_path = tmp_repo / "topics" / "my-skill" / "structured" / "dt-incomplete" / "dt-incomplete-report.md"
    report = report_path.read_text()
    assert "rules" in report.lower() or "Rule" in report


def test_render_decision_table_shows_full_long_labels(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "dt-long-header", {
        "id": "dt-long-header",
        "title": "Long Header Decision Table",
        "artifact_type": "decision-table",
        "sections": {
            "events": [{"id": "ev1", "label": "Review"}],
            "conditions": [
                {
                    "id": "c1",
                    "label": "Significant or persistent purulent nasal discharge",
                    "values": ["yes", "no"],
                },
            ],
            "actions": [{"id": "a1", "label": "Consider prolonged oral antibiotic therapy"}],
            "rules": [{"id": "r1", "event": "ev1", "when": {"c1": "yes"}, "then": ["a1"]}],
        },
    })
    runner = CliRunner()
    result = runner.invoke(render, ["my-skill", "dt-long-header"])
    assert result.exit_code == 0
    report_path = tmp_repo / "topics" / "my-skill" / "structured" / "dt-long-header" / "dt-long-header-report.md"
    report = report_path.read_text()
    assert "| Event Pattern | c1 Significant or persistent purulent nasal discharge | Actions |" in report
    assert "a1 Consider prolonged oral antibiotic therapy" in report
    assert "| ev1 Review | yes |" in report


# ── Idempotent re-render ────────────────────────────────────────────────────────


def test_render_is_idempotent(tmp_repo):
    _write_artifact(tmp_repo, "my-skill", "evidence-item", {
        "id": "evidence-item",
        "artifact_type": "custom-type",
        "sections": {"summary": "Original."},
    })
    runner = CliRunner()
    runner.invoke(render, ["my-skill", "evidence-item"])
    # Render again — should overwrite without error
    result = runner.invoke(render, ["my-skill", "evidence-item"])
    assert result.exit_code == 0


# ── Completeness unit tests (T027) ─────────────────────────────────────────────


def test_completeness_complete_table():
    """3 binary conditions, 8 rules → 8/8 complete."""
    conditions = [
        {"id": "c1", "values": ["yes", "no"]},
        {"id": "c2", "values": ["yes", "no"]},
        {"id": "c3", "values": ["yes", "no"]},
    ]
    rules = [
        {"id": "r1", "when": {"c1": "yes", "c2": "yes", "c3": "yes"}, "then": ["a1"]},
        {"id": "r2", "when": {"c1": "yes", "c2": "yes", "c3": "no"}, "then": ["a1"]},
        {"id": "r3", "when": {"c1": "yes", "c2": "no", "c3": "yes"}, "then": ["a2"]},
        {"id": "r4", "when": {"c1": "yes", "c2": "no", "c3": "no"}, "then": ["a2"]},
        {"id": "r5", "when": {"c1": "no", "c2": "yes", "c3": "yes"}, "then": ["a1"]},
        {"id": "r6", "when": {"c1": "no", "c2": "yes", "c3": "no"}, "then": ["a2"]},
        {"id": "r7", "when": {"c1": "no", "c2": "no", "c3": "yes"}, "then": ["a2"]},
        {"id": "r8", "when": {"c1": "no", "c2": "no", "c3": "no"}, "then": ["a2"]},
    ]
    result = _check_completeness(conditions, rules)
    assert result["total_space"] == 8
    assert result["complete"] is True
    assert len(result["missing"]) == 0


def test_completeness_incomplete_table():
    """Missing 1 rule from 8 → 7/8, identifies missing combo."""
    conditions = [
        {"id": "c1", "values": ["yes", "no"]},
        {"id": "c2", "values": ["yes", "no"]},
        {"id": "c3", "values": ["yes", "no"]},
    ]
    rules = [
        {"id": "r1", "when": {"c1": "yes", "c2": "yes", "c3": "yes"}, "then": ["a1"]},
        {"id": "r2", "when": {"c1": "yes", "c2": "yes", "c3": "no"}, "then": ["a1"]},
        {"id": "r3", "when": {"c1": "yes", "c2": "no", "c3": "yes"}, "then": ["a2"]},
        {"id": "r4", "when": {"c1": "yes", "c2": "no", "c3": "no"}, "then": ["a2"]},
        {"id": "r5", "when": {"c1": "no", "c2": "yes", "c3": "yes"}, "then": ["a1"]},
        {"id": "r6", "when": {"c1": "no", "c2": "yes", "c3": "no"}, "then": ["a2"]},
        {"id": "r7", "when": {"c1": "no", "c2": "no", "c3": "yes"}, "then": ["a2"]},
        # r8 omitted
    ]
    result = _check_completeness(conditions, rules)
    assert result["complete"] is False
    assert len(result["missing"]) == 1
    assert result["missing"][0] == {"c1": "no", "c2": "no", "c3": "no"}


def test_completeness_contradiction():
    """Two rules cover same combo with different actions → flags conflict."""
    conditions = [
        {"id": "c1", "values": ["yes", "no"]},
    ]
    rules = [
        {"id": "r1", "when": {"c1": "yes"}, "then": ["a1"]},
        {"id": "r2", "when": {"c1": "yes"}, "then": ["a2"]},
        {"id": "r3", "when": {"c1": "no"}, "then": ["a1"]},
    ]
    result = _check_completeness(conditions, rules)
    assert result["complete"] is True  # all combos covered
    assert len(result["contradictions"]) == 1
    assert set(result["contradictions"][0]["rules"]) == {"r1", "r2"}


def test_completeness_wildcard_dash():
    """Rule with dash in binary condition covers 2 combos."""
    conditions = [
        {"id": "c1", "values": ["yes", "no"]},
        {"id": "c2", "values": ["yes", "no"]},
    ]
    rules = [
        {"id": "r1", "when": {"c1": "yes", "c2": "-"}, "then": ["a1"]},  # covers 2
        {"id": "r2", "when": {"c1": "no", "c2": "yes"}, "then": ["a2"]},
        {"id": "r3", "when": {"c1": "no", "c2": "no"}, "then": ["a2"]},
    ]
    result = _check_completeness(conditions, rules)
    assert result["total_space"] == 4
    assert result["covered"] == 4  # r1 covers 2 + r2 covers 1 + r3 covers 1
    assert result["complete"] is True


def test_completeness_large_table_warning():
    """>10 binary conditions → total_space > 1024 → warning."""
    conditions = [{"id": f"c{i}", "values": ["yes", "no"]} for i in range(11)]
    # No rules — just testing the warning
    result = _check_completeness(conditions, [])
    assert result["total_space"] == 2048
    assert result["large_table_warning"] is True
    assert result["complete"] is False
