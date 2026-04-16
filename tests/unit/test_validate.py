"""Tests for rh-skills validate command — ported from tests/unit/validate.bats."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.validate import validate


def make_valid_l2(tmp_repo, skill="my-skill", artifact="test-artifact"):
    td = tmp_repo / "topics" / skill / "structured"
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


def write_extract_plan(tmp_repo, topic="my-skill", artifact="test-artifact", *, unresolved_conflicts=None):
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
            "artifact_type": "eligibility-criteria",
            "source_files": ["sources/normalized/source-l1.md"],
            "rationale": "Primary criteria artifact",
            "key_questions": ["Who qualifies?"],
            "required_sections": ["summary", "evidence_traceability"],
            "unresolved_conflicts": unresolved_conflicts or [],
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
    td = tmp_repo / "topics" / skill / "structured"
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
artifact_type: eligibility-criteria
clinical_question: "Who should be screened?"
sections:
  summary: "Adults at risk should be screened."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Screen adults at risk"
      evidence:
        - source: source-l1
          locator: "Section 2"
conflicts: []
""")


def make_invalid_l2(tmp_repo, skill="my-skill", artifact="bad-artifact"):
    td = tmp_repo / "topics" / skill / "structured"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
name: BadArtifact
description: "Incomplete artifact"
""")


def make_valid_l3(tmp_repo, skill="my-skill", artifact="test-l3"):
    td = tmp_repo / "topics" / skill / "computable"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
artifact_schema_version: "1.0"
metadata:
  id: {artifact}
  name: TestL3
  title: "Test L3 Artifact"
  version: "1.0.0"
  status: draft
  domain: diabetes
  created_date: "2026-04-03"
  description: |
    A valid L3 artifact for testing.
converged_from:
  - test-l2-artifact
""")


def write_formalize_plan(tmp_repo, topic="my-skill", artifact="test-l3", *, required_sections=None, input_artifacts=None):
    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "formalize-plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    frontmatter = {
        "topic": topic,
        "plan_type": "formalize",
        "status": "approved",
        "reviewer": "Tester",
        "reviewed_at": "2026-04-14T00:00:00Z",
        "artifacts": [{
            "name": artifact,
            "artifact_type": "pathway-package",
            "input_artifacts": input_artifacts or ["test-l2-artifact"],
            "rationale": "Primary computable package",
            "required_sections": required_sections or ["pathways", "value_sets"],
            "implementation_target": True,
            "reviewer_decision": "approved",
            "approval_notes": "Proceed",
        }],
    }
    from io import StringIO
    buf = StringIO()
    y.dump(frontmatter, buf)
    plan_path.write_text(
        f"---\n{buf.getvalue()}---\n\n# Review Summary\n\n# Proposed Artifacts\n\n# Cross-Artifact Issues\n\n# Implementation Readiness\n"
    )
    return plan_path


def make_valid_formalize_l3(tmp_repo, skill="my-skill", artifact="test-l3"):
    td = tmp_repo / "topics" / skill / "computable"
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{artifact}.yaml").write_text(f"""\
artifact_schema_version: "1.0"
metadata:
  id: {artifact}
  name: {artifact}
  title: "Test L3 Artifact"
  version: "1.0.0"
  status: draft
  domain: diabetes
  created_date: "2026-04-03"
  description: |
    A valid L3 artifact for formalize validation testing.
converged_from:
  - test-l2-artifact
pathways:
  - id: pathway-1
    title: "Screening pathway"
    description: "Screening workflow"
    steps:
      - id: step-1
        title: "Screen patient"
value_sets:
  - id: value-set-1
    title: "Conditions"
    description: "Condition codes"
    system: http://snomed.info/sct
    codes:
      - code: "44054006"
        display: "Diabetes mellitus type 2"
""")


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
    (td / "bad-l3.yaml").write_text("""\
metadata:
  id: bad-l3
  name: BadL3
  title: "Bad L3"
  version: "1.0.0"
  status: draft
  domain: testing
  created_date: "2026-04-03"
  description: "Missing artifact_schema_version"
converged_from:
  - some-l2
""")
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
    td = tmp_repo / "topics" / "my-skill" / "structured"
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
artifact_type: eligibility-criteria
clinical_question: "Who should be screened?"
sections:
  summary: "Adults at risk should be screened."
conflicts: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "evidence traceability" in result.output.lower()


def test_validate_extract_artifact_fails_missing_conflicts_when_plan_requires_them(tmp_repo):
    write_extract_plan(tmp_repo, unresolved_conflicts=["Guidelines disagree"])
    make_valid_extract_l2(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact.yaml"
    data = YAML().load(td.read_text())
    data["conflicts"] = []
    y = YAML()
    y.default_flow_style = False
    with open(td, "w") as f:
        y.dump(data, f)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "missing conflicts" in result.output.lower()


def test_validate_formalize_artifact_checks_approved_plan_requirements(tmp_repo):
    write_formalize_plan(tmp_repo)
    make_valid_formalize_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 0, result.output
    assert "VALID" in result.output


def test_validate_formalize_artifact_fails_when_converged_inputs_mismatch(tmp_repo):
    write_formalize_plan(tmp_repo, input_artifacts=["screening-criteria", "workflow-steps"])
    make_valid_formalize_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 1
    assert "converged_from does not match approved formalize plan inputs" in result.output


def test_validate_formalize_artifact_fails_when_required_section_incomplete(tmp_repo):
    write_formalize_plan(tmp_repo, required_sections=["pathways", "measures"])
    td = tmp_repo / "topics" / "my-skill" / "computable"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-l3.yaml").write_text("""\
artifact_schema_version: "1.0"
metadata:
  id: test-l3
  name: test-l3
  title: "Test L3 Artifact"
  version: "1.0.0"
  status: draft
  domain: diabetes
  created_date: "2026-04-03"
  description: "Incomplete formalize artifact"
converged_from:
  - test-l2-artifact
pathways:
  - id: pathway-1
    title: "Screening pathway"
    description: "Screening workflow"
    steps:
      - id: step-1
        title: "Screen patient"
measures:
  - id: measure-1
    title: "Screening measure"
    description: "Missing denominator"
    numerator: "Numerator expression"
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 1
    assert "measures require numerator and denominator" in result.output
