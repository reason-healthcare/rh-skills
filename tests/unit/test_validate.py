"""Tests for rh-skills validate command — ported from tests/unit/validate.bats."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.validate import validate


def make_valid_l2(tmp_repo, skill="my-skill", artifact="test-artifact"):
    td = tmp_repo / "topics" / skill / "structured" / artifact
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
id: {artifact}
name: TestArtifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: diabetes
description: |
  A test artifact for validation testing.
derived_from:
  - source-l1
""")


def write_extract_plan(tmp_repo, topic="my-skill", artifact="test-artifact", *, concerns=None):
    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "extract-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    plan = {
        "topic": topic,
        "plan_type": "extract",
        "status": "approved",
        "reviewer": "Tester",
        "reviewed_at": "2026-04-14T00:00:00Z",
        "review_summary": "",
        "cross_artifact_issues": [],
        "artifacts": [{
            "name": artifact,
            "artifact_type": "decision-table",
            "source_files": ["sources/normalized/source-l1.md"],
            "rationale": "Primary criteria artifact",
            "key_questions": ["Who qualifies?"],
            "required_sections": ["summary", "evidence_traceability"],
            "concerns": concerns or [],
            "reviewer_decision": "approved",
            "approval_notes": "Proceed",
        }],
    }
    from io import StringIO
    buf = StringIO()
    y.dump(plan, buf)
    plan_path.write_text(buf.getvalue())
    return plan_path


def make_valid_extract_l2(tmp_repo, skill="my-skill", artifact="test-artifact"):
    td = tmp_repo / "topics" / skill / "structured" / artifact
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
id: {artifact}
name: {artifact}
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: diabetes
description: |
  A test artifact for validation testing.
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Who should be screened?"
sections:
  summary: "Adults at risk should be screened."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Screen adults at risk"
      evidence:
        - source: source-l1
          locator: "Section 2"
concerns: []
""")


def make_invalid_l2(tmp_repo, skill="my-skill", artifact="bad-artifact"):
    td = tmp_repo / "topics" / skill / "structured" / artifact
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
name: BadArtifact
description: "Incomplete artifact"
""")


def make_valid_l3(tmp_repo, skill="my-skill", artifact="test-l3"):
    td = tmp_repo / "topics" / skill / "computable"
    td.mkdir(parents=True, exist_ok=True)
    import json
    (td / f"Questionnaire-{artifact}.json").write_text(json.dumps({
        "resourceType": "Questionnaire",
        "id": artifact,
        "status": "draft",
        "item": [{"linkId": "q1", "text": "Test question", "type": "string"}],
    }))


def make_valid_formalize_l3(tmp_repo, skill="my-skill", artifact="test-l3"):
    td = tmp_repo / "topics" / skill / "computable"
    td.mkdir(parents=True, exist_ok=True)
    import json
    (td / f"Questionnaire-{artifact}.json").write_text(json.dumps({
        "resourceType": "Questionnaire",
        "id": artifact,
        "status": "draft",
        "item": [{"linkId": "q1", "text": "Test question", "type": "string"}],
    }))


# ── L2 validation tests ────────────────────────────────────────────────────────

def test_validate_valid_l2_exits_0(tmp_repo):
    make_valid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "test-artifact"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_invalid_l2_exits_1(tmp_repo):
    make_invalid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "bad-artifact"])
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_validate_missing_required_field_reported(tmp_repo):
    make_invalid_l2(tmp_repo, artifact="missing-fields")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "missing-fields"])
    assert result.exit_code == 1
    # Error messages go to stderr but CliRunner mixes them
    assert "MISSING required field" in result.output or "MISSING required field" in (result.output + str(result.exception or ""))


def test_validate_unknown_skill_exits_2(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(validate, ["nonexistent-skill", "l2", "artifact"])
    assert result.exit_code == 2


def test_validate_unknown_artifact_exits_2(tmp_repo):
    (tmp_repo / "topics" / "my-skill" / "structured").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "nonexistent-artifact"])
    assert result.exit_code == 2


def test_validate_invalid_level_exits_2(tmp_repo):
    (tmp_repo / "topics" / "my-skill").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l1", "some-artifact"])
    assert result.exit_code == 2


# ── L3 validation tests ────────────────────────────────────────────────────────

def test_validate_valid_l3_exits_0(tmp_repo):
    make_valid_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_l3_missing_schema_version_exits_1(tmp_repo):
    td = tmp_repo / "topics" / "my-skill" / "computable"
    td.mkdir(parents=True, exist_ok=True)
    import json
    # Missing resourceType — FHIR validation must fail
    (td / "Questionnaire-bad-l3.json").write_text(json.dumps({
        "id": "bad-l3",
        "status": "draft",
        "item": [{"linkId": "q1", "text": "Test", "type": "string"}],
    }))
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "bad-l3"])
    assert result.exit_code == 1


def test_validate_structured_alias(tmp_repo):
    """Level alias 'structured' should work same as 'l2'."""
    make_valid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "structured", "test-artifact"])
    assert result.exit_code == 0


def test_validate_computable_alias(tmp_repo):
    """Level alias 'computable' should work same as 'l3'."""
    make_valid_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "computable", "test-l3"])
    assert result.exit_code == 0


def test_validate_two_arg_shorthand_defaults_to_l2(tmp_repo):
    make_valid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_extract_artifact_checks_plan_requirements(tmp_repo):
    write_extract_plan(tmp_repo)
    make_valid_extract_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "VALID" in result.output


def test_validate_extract_artifact_fails_missing_traceability(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact"
version: "1.0.0"
status: draft
domain: diabetes
description: "Incomplete extract artifact"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Who should be screened?"
sections:
  summary: "Adults at risk should be screened."
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "evidence traceability" in result.output.lower()


def test_validate_extract_artifact_fails_missing_concerns_when_plan_requires_them(tmp_repo):
    write_extract_plan(tmp_repo, concerns=[{"concern": "Guidelines disagree", "resolution": ""}])
    make_valid_extract_l2(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact" / "test-artifact.yaml"
    data = YAML().load(td.read_text())
    data["concerns"] = []
    y = YAML()
    y.default_flow_style = False
    with open(td, "w") as f:
        y.dump(data, f)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "missing concerns" in result.output.lower()


def test_validate_formalize_artifact_checks_approved_plan_requirements(tmp_repo):
    """Valid Questionnaire FHIR JSON passes l3 validation (plan check no longer applies)."""
    make_valid_formalize_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 0, result.output
    assert "VALID" in result.output


def test_validate_formalize_artifact_fails_when_converged_inputs_mismatch(tmp_repo):
    """Questionnaire missing linkId fails FHIR validation (replaces old converged_from check)."""
    td = tmp_repo / "topics" / "my-skill" / "computable"
    td.mkdir(parents=True, exist_ok=True)
    import json
    (td / "Questionnaire-test-l3.json").write_text(json.dumps({
        "resourceType": "Questionnaire",
        "id": "test-l3",
        "status": "draft",
        "item": [{"text": "Missing linkId", "type": "string"}],
    }))
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 1
    assert "linkId" in result.output


def test_validate_formalize_artifact_fails_when_required_section_incomplete(tmp_repo):
    """Measure missing scoring fails FHIR validation (replaces old required-sections check)."""
    td = tmp_repo / "topics" / "my-skill" / "computable"
    td.mkdir(parents=True, exist_ok=True)
    import json
    (td / "Measure-test-l3.json").write_text(json.dumps({
        "resourceType": "Measure",
        "id": "test-l3",
        "status": "draft",
    }))
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 1
    assert "scoring" in result.output


def test_validate_extract_artifact_fails_unresolved_stub_values(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: diabetes
description: "Artifact with stub values"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Who should be screened?"
sections:
  summary: "Adults at risk should be screened."
  criteria:
    - id: cr-001
      description: "<stub: criterion>"
      requirement_type: clinical
      rule: "<stub: rule>"
  evidence_traceability:
    - claim_id: crit-001
      statement: "Screen adults at risk"
      evidence:
        - source: source-l1
          locator: "Section 2"
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "UNRESOLVED stub" in result.output
    assert "sections.criteria[0].description" in result.output
    assert "re-derive" in result.output


def test_collect_stub_paths_finds_nested_stubs():
    from rh_skills.commands.validate import _collect_stub_paths
    data = {
        "summary": "Real summary",
        "factors": [
            {"factor": "<stub: factor name>", "threshold": "LDL >= 190"},
            {"factor": "Diabetes", "threshold": "<stub: threshold>"},
        ],
        "concerns": "<stub: populate concerns content>",
    }
    paths = _collect_stub_paths(data)
    assert "factors[0].factor" in paths
    assert "factors[1].threshold" in paths
    assert "concerns" in paths
    assert "summary" not in paths


def test_collect_stub_paths_empty_on_clean_data():
    from rh_skills.commands.validate import _collect_stub_paths
    data = {
        "summary": "Clean content",
        "criteria": [{"id": "c1", "description": "Screen adults", "rule": "age >= 40"}],
    }
    assert _collect_stub_paths(data) == []


def test_validate_fails_with_clear_message_on_yaml_parse_error(tmp_repo):
    """Unquoted >= or <= in YAML causes a parse error; validate must report it clearly."""
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text(
        "id: test-artifact\n"
        "threshold: >=190 mg/dL\n"  # unquoted > at start causes ScannerError
    )
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "YAML parse error" in result.output
    assert "quoted" in result.output
