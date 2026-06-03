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
            "required_sections": ["summary", "events", "conditions", "data_elements", "actions", "rules", "evidence_traceability"],
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
  events:
    - id: screening-due
      label: Screening Due
      trigger:
        type: named-event
        name: screening-due
  conditions:
    - id: at_risk
      label: At Risk
      description: Patient is at risk
      values:
        - Yes
        - No
  data_elements:
    - id: risk-status
      condition_id: at_risk
      label: Risk status
      description: Review demographics, history, and risk factors used by the guideline.
      data_type: history
  actions:
    - id: order-screening
      label: Order Screening
      kind: ServiceRequest
  rules:
    - id: screen-adults
      event: screening-due
      when:
        at_risk: Yes
      then:
        - order-screening
      action: Order screening
      rationale: Evidence supports screening
concerns: []
""")


def make_valid_concepts_extract_l2(tmp_repo, skill="my-skill"):
    td = tmp_repo / "topics" / skill / "structured" / "concepts"
    td.mkdir(parents=True, exist_ok=True)
    (td / "concepts.yaml").write_text("""\
id: concepts
name: concepts
title: "Concept Catalog"
version: "1.0.0"
status: draft
domain: terminology
description: |
  Deduplicated concept catalog derived from topic concept annotations.
derived_from:
  - source-l1
artifact_type: terminology
sections:
  summary: "Reviewed terminology package."
  value_sets:
    - id: hypertension
      name: Hypertension
      concept_refs:
        - hypertension
concepts:
  - id: hypertension
    name: Hypertension
    type: disorder
    codes:
      - system: http://snomed.info/sct
        code: "38341003"
        display: Hypertensive disorder, systemic arterial (disorder)
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


def write_tracking_with_computable(
    tmp_repo,
    topic="my-skill",
    artifact="test-l3",
    *,
    converged_from=None,
    strategy="assessment",
):
    y = YAML()
    y.default_flow_style = False
    tracking = {
        "schema_version": "1.0",
        "sources": [],
        "topics": [{
            "name": topic,
            "structured": [],
            "computable": [{
                "name": artifact,
                "files": [f"topics/{topic}/computable/Questionnaire-{artifact}.json"],
                "checksums": {},
                "converged_from": converged_from or ["screening-criteria"],
                "strategy": strategy,
            }],
            "events": [],
        }],
    }
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)


def write_formalize_plan_yaml(
    tmp_repo,
    topic="my-skill",
    artifact="test-l3",
    *,
    reviewer_decision="approved",
    implementation_target=True,
):
    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "formalize-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    plan = {
        "topic": topic,
        "plan_type": "formalize",
        "status": "approved",
        "reviewer": "Tester",
        "reviewed_at": "2026-04-14T00:00:00Z",
        "artifacts": [{
            "name": artifact,
            "source_artifact": "screening-criteria",
            "artifact_type": "assessment",
            "strategy": "assessment",
            "input_artifacts": ["screening-criteria"],
            "l3_targets": ["Questionnaire"],
            "required_sections": [],
            "reviewer_decision": reviewer_decision,
            "implementation_target": implementation_target,
        }],
    }
    with open(plan_path, "w") as f:
        y.dump(plan, f)
    return plan_path


# ── L2 validation tests ────────────────────────────────────────────────────────

def test_validate_valid_l2_exits_0(tmp_repo):
    make_valid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "test-artifact"])
    assert result.exit_code == 0
    assert "VALID" in result.output


def test_validate_formalize_artifact_matches_source_artifact(tmp_repo):
    make_valid_l3(tmp_repo, artifact="screening-criteria")
    write_tracking_with_computable(tmp_repo, artifact="screening-criteria")
    write_formalize_plan_yaml(tmp_repo, artifact="synthetic-target-name")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "screening-criteria"])
    assert result.exit_code == 0


def test_validate_l3_decision_table_skips_intermediate_section_checks_for_deterministic_builder(tmp_repo):
    topic = "my-skill"
    artifact = "decision-table"
    computable_dir = tmp_repo / "topics" / topic / "computable"
    computable_dir.mkdir(parents=True, exist_ok=True)
    import json
    (computable_dir / "PlanDefinition-decision-table-event-verify.json").write_text(json.dumps({
        "resourceType": "PlanDefinition",
        "id": "decision-table-event-verify",
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/plan-definition-type", "code": "eca-rule"}]},
        "status": "draft",
        "action": [{"id": "rule-verify", "title": "Verify diagnosis"}],
    }))
    (computable_dir / "ActivityDefinition-action-verify.json").write_text(json.dumps({
        "resourceType": "ActivityDefinition",
        "id": "action-verify",
        "kind": "ServiceRequest",
        "status": "draft",
    }))
    (computable_dir / "Library-my-skill.json").write_text(json.dumps({
        "resourceType": "Library",
        "id": "my-skill",
        "status": "draft",
        "type": {"text": "logic-library"},
    }))

    y = YAML()
    tracking = {
        "schema_version": "1.0",
        "sources": [],
        "topics": [{
            "name": topic,
            "structured": [],
            "computable": [{
                "name": artifact,
                "files": [
                    f"topics/{topic}/computable/PlanDefinition-decision-table-event-verify.json",
                    f"topics/{topic}/computable/ActivityDefinition-action-verify.json",
                    f"topics/{topic}/computable/Library-my-skill.json",
                ],
                "checksums": {},
                "converged_from": ["decision-table"],
                "strategy": "decision-table",
            }],
            "events": [],
        }],
    }
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "formalize-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        "topic": topic,
        "plan_type": "formalize",
        "status": "approved",
        "reviewer": "Tester",
        "reviewed_at": "2026-04-14T00:00:00Z",
        "artifacts": [{
            "name": artifact,
            "source_artifact": artifact,
            "artifact_type": "decision-table",
            "strategy": "decision-table",
            "input_artifacts": [artifact],
            "l3_targets": ["PlanDefinition (eca-rule)", "ActivityDefinition", "Library (CQL)"],
            "required_sections": ["actions", "libraries"],
            "reviewer_decision": "approved",
            "implementation_target": True,
        }],
    }
    with open(plan_path, "w") as f:
        y.dump(plan, f)

    runner = CliRunner()
    result = runner.invoke(validate, [topic, "l3", artifact])
    assert result.exit_code == 0, result.output
    assert "MISSING required formalize section" not in result.output


def test_validate_l3_uses_tracked_computable_files_over_stale_name_matches(tmp_repo):
    topic = "my-skill"
    artifact = "care-pathway"
    computable_dir = tmp_repo / "topics" / topic / "computable"
    computable_dir.mkdir(parents=True, exist_ok=True)
    import json
    valid_path = computable_dir / "PlanDefinition-care-pathway.json"
    valid_path.write_text(json.dumps({
        "resourceType": "PlanDefinition",
        "id": "care-pathway",
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/plan-definition-type", "code": "clinical-protocol"}]},
        "status": "draft",
        "action": [{"id": "assessment", "title": "Assessment"}],
    }))
    stale_path = computable_dir / "PlanDefinition-care-pathway-old-strategy.json"
    stale_path.write_text(json.dumps({
        "resourceType": "PlanDefinition",
        "id": "care-pathway-old-strategy",
        "status": "draft",
    }))

    y = YAML()
    tracking = {
        "schema_version": "1.0",
        "sources": [],
        "topics": [{
            "name": topic,
            "structured": [],
            "computable": [{
                "name": artifact,
                "files": [f"topics/{topic}/computable/{valid_path.name}"],
                "checksums": {},
                "converged_from": ["care-pathway"],
                "strategy": "care-pathway",
            }],
            "events": [],
        }],
    }
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    plan_path = tmp_repo / "topics" / topic / "process" / "plans" / "formalize-plan.yaml"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        "topic": topic,
        "plan_type": "formalize",
        "status": "approved",
        "reviewer": "Tester",
        "reviewed_at": "2026-04-14T00:00:00Z",
        "artifacts": [{
            "name": artifact,
            "source_artifact": artifact,
            "artifact_type": "care-pathway",
            "strategy": "care-pathway",
            "input_artifacts": [artifact],
            "l3_targets": ["PlanDefinition (clinical-protocol)"],
            "required_sections": ["pathways", "actions"],
            "reviewer_decision": "approved",
            "implementation_target": False,
        }],
    }
    with open(plan_path, "w") as f:
        y.dump(plan, f)

    runner = CliRunner()
    result = runner.invoke(validate, [topic, "l3", artifact])
    assert result.exit_code == 0, result.output
    assert stale_path.name not in result.output


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


def test_value_sets_section_accepts_concept_refs():
    from rh_skills.commands.validate import _validate_required_section_completeness

    errors = _validate_required_section_completeness(
        "value_sets",
        [{"id": "hypertension", "name": "Hypertension", "concept_refs": ["hypertension"]}],
        emit=False,
    )
    assert errors == 0


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


def test_validate_concepts_extract_artifact_allows_missing_clinical_question(tmp_repo):
    write_extract_plan(tmp_repo, artifact="concepts")
    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    plan = YAML().load(plan_path.read_text())
    plan["artifacts"][0]["artifact_type"] = "terminology"
    plan["artifacts"][0]["required_sections"] = ["summary", "value_sets"]
    y = YAML()
    y.default_flow_style = False
    with open(plan_path, "w") as f:
        y.dump(plan, f)

    make_valid_concepts_extract_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "concepts"])
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
    """Valid Questionnaire FHIR JSON passes l3 validation with YAML formalize plan checks."""
    write_tracking_with_computable(tmp_repo)
    write_formalize_plan_yaml(tmp_repo)
    make_valid_formalize_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 0, result.output
    assert "VALID" in result.output


def test_validate_formalize_artifact_reads_yaml_plan_and_flags_input_mismatch(tmp_repo):
    write_tracking_with_computable(tmp_repo, converged_from=["different-input"])
    write_formalize_plan_yaml(tmp_repo)
    make_valid_formalize_l3(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l3", "test-l3"])
    assert result.exit_code == 1
    assert "approved formalize plan inputs" in result.output


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


def test_validate_decision_table_rejects_legacy_top_level_pathway_phases(tmp_repo):
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
description: "Artifact with legacy fields"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Who should be screened?"
pathway_phases:
  - id: screening
    label: Screening
sections:
  summary: "Adults at risk should be screened."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Screen adults at risk"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: screening-due
      label: Screening Due
      trigger:
        type: named-event
        name: screening-due
  conditions:
    - id: at_risk
      label: At Risk
      values:
        - Yes
        - No
  data_elements:
    - id: risk-status
      condition_id: at_risk
      label: Risk status
      description: Review demographics, history, and risk factors used by the guideline.
      data_type: history
  actions:
    - id: order-screening
      label: Order Screening
      kind: ServiceRequest
  rules:
    - id: screen-adults
      event: screening-due
      when:
        at_risk: Yes
      then:
        - order-screening
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "top-level 'pathway_phases'" in result.output


def test_validate_decision_table_rejects_condition_derivation(tmp_repo):
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
description: "Artifact with unsupported derived composite condition"
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
  events:
    - id: screening-due
      label: Screening Due
      trigger:
        type: named-event
        name: verification
  conditions:
    - id: symptom-threshold-met
      label: Symptom threshold met
      values: [Yes, No]
    - id: duration-threshold-met
      label: Duration threshold met
      values: [Yes, No]
    - id: objective-evidence-documented
      label: Objective evidence documented
      values: [Yes, No]
    - id: criteria-confirmed
      label: Criteria confirmed
      values: [Yes, No]
      derivation:
        operator: all-of
        inputs:
          - symptom-threshold-met
          - duration-threshold-met
          - objective-evidence-documented
  data_elements:
    - id: symptom-threshold
      condition_id: symptom-threshold-met
      label: Symptom threshold
    - id: duration-threshold
      condition_id: duration-threshold-met
      label: Duration threshold
    - id: objective-evidence
      condition_id: objective-evidence-documented
      label: Objective evidence
    - id: criteria-confirmed-question
      condition_id: criteria-confirmed
      label: Criteria confirmed
  actions:
    - id: order-screening
      label: Order Screening
      kind: ServiceRequest
  rules:
    - id: screen-adults
      event: screening-due
      when:
        criteria-confirmed: Yes
      then:
        - order-screening
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "uses unsupported 'derivation'" in result.output


def test_validate_decision_table_allows_composite_condition_with_supporting_data_elements(tmp_repo):
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
description: "Artifact with composite condition and supporting data elements"
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
  events:
    - id: screening-due
      label: Screening Due
      trigger:
        type: named-event
        name: verification
  conditions:
    - id: crs-diagnostic-criteria-confirmed
      label: CRS diagnostic criteria confirmed
      values: [Yes, No]
  data_elements:
    - id: qualifying-symptoms
      condition_id: crs-diagnostic-criteria-confirmed
      label: Qualifying CRS symptoms
    - id: symptom-duration
      condition_id: crs-diagnostic-criteria-confirmed
      label: Symptom duration
    - id: objective-inflammation
      condition_id: crs-diagnostic-criteria-confirmed
      label: Objective inflammation evidence
  actions:
    - id: order-screening
      label: Order Screening
      kind: ServiceRequest
  rules:
    - id: screen-adults
      event: screening-due
      when:
        crs-diagnostic-criteria-confirmed: Yes
      then:
        - order-screening
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_decision_table_allows_event_driven_rule_without_when(tmp_repo):
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
description: "Artifact with unconditional event-driven rule"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "What should happen during verification?"
sections:
  summary: "Verification should occur during the event."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform verification during the event"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: verification
      label: Verification
      trigger:
        type: named-event
        name: verification
  conditions:
    - id: criteria-confirmed
      label: Criteria confirmed
      values: [Yes, No]
  data_elements:
    - id: qualifying-symptoms
      condition_id: criteria-confirmed
      label: Qualifying symptoms
  actions:
    - id: review-evidence
      label: Review evidence
      kind: ServiceRequest
  rules:
    - id: verify
      event: verification
      then:
        - review-evidence
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_decision_table_allows_event_without_trigger(tmp_repo):
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
description: "Artifact with event-only workflow context"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "What should happen during verification?"
sections:
  summary: "Verification should occur during the event."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform verification during the event"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: verification
      label: Verification
  conditions:
    - id: criteria-confirmed
      label: Criteria confirmed
      values: [Yes, No]
  data_elements:
    - id: qualifying-symptoms
      condition_id: criteria-confirmed
      label: Qualifying symptoms
  actions:
    - id: review-evidence
      label: Review evidence
      kind: ServiceRequest
  rules:
    - id: verify
      event: verification
      then:
        - review-evidence
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_decision_table_rejects_legacy_trigger_type(tmp_repo):
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
description: "Artifact using legacy trigger_type"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "What should happen during verification?"
sections:
  summary: "Verification should occur during the event."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform verification during the event"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: verification
      label: Verification
      trigger_type: named-event
  conditions:
    - id: criteria-confirmed
      label: Criteria confirmed
      values: [Yes, No]
  data_elements:
    - id: qualifying-symptoms
      condition_id: criteria-confirmed
      label: Qualifying symptoms
  actions:
    - id: review-evidence
      label: Review evidence
      kind: ServiceRequest
  rules:
    - id: verify
      event: verification
      then:
        - review-evidence
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "legacy 'trigger_type'" in result.output


def test_validate_decision_table_action_relationship_fields(tmp_repo):
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
description: "Artifact with explicit action relationships"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "How is candidacy assessed?"
sections:
  summary: "Use staged assessment."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform staged assessment"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: assessment
      label: Assessment
      trigger:
        type: named-event
        name: verification
  conditions:
    - id: diagnosis-verified
      label: Diagnosis verified
      values: [Yes, No]
    - id: candidacy-appropriate
      label: Surgical candidacy appropriate
      values: [Yes, No]
  data_elements:
    - id: dx-support
      condition_id: diagnosis-verified
      label: Diagnostic support
    - id: candidacy-support
      condition_id: candidacy-appropriate
      label: Candidacy support
  actions:
    - id: assess-candidacy
      label: Assess candidacy
      kind: ServiceRequest
      produces_conditions: [candidacy-appropriate]
    - id: administer-snot-22
      label: Administer SNOT-22
      kind: assessment
      parent_action_id: assess-candidacy
      produces_data_elements: [candidacy-support]
      assessment_artifact: snot-22
  rules:
    - id: assess
      event: assessment
      when:
        diagnosis-verified: Yes
      then:
        - assess-candidacy
        - administer-snot-22
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_decision_table_rejects_unknown_produced_data_element(tmp_repo):
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
description: "Artifact with invalid produced data element reference"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "What should happen during staged assessment?"
sections:
  summary: "Use staged assessment."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform staged assessment"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: assessment
      label: Assessment
  conditions:
    - id: diagnosis-verified
      label: Diagnosis verified
      values: [Yes, No]
  data_elements:
    - id: dx-support
      condition_id: diagnosis-verified
      label: Diagnostic support
  actions:
    - id: administer-snot-22
      label: Administer SNOT-22
      kind: assessment
      produces_data_elements: [missing-score]
  rules:
    - id: assess
      event: assessment
      then:
        - administer-snot-22
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "unknown produced data element 'missing-score'" in result.output


def test_validate_care_pathway_rejects_nested_substeps(tmp_repo):
    write_extract_plan(tmp_repo, artifact="care-artifact")
    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    plan = YAML().load(plan_path.read_text())
    plan["artifacts"][0]["artifact_type"] = "care-pathway"
    plan["artifacts"][0]["required_sections"] = ["summary", "evidence_traceability", "steps", "transitions"]
    y = YAML()
    y.default_flow_style = False
    with open(plan_path, "w") as f:
        y.dump(plan, f)

    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with legacy nested substeps"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "What is the pathway?"
sections:
  summary: "Pathway summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway statement"
      evidence:
        - source: source-l1
          locator: "Section 2"
  steps:
    - id: phase-1
      label: Phase 1
      description: First phase
      actor: clinician
      substeps:
        - id: s1
          description: Legacy nested step
  transitions:
    - from_id: phase-1
      to_id: phase-1
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 1
    assert "legacy nested 'substeps'" in result.output


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
