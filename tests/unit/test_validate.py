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


def write_extract_plan_with_artifacts(tmp_repo, artifacts, *, topic="my-skill"):
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
        "artifacts": artifacts,
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
      evidence_traceability_ids:
        - crit-001
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


def test_validate_l3_decision_table_skips_intermediate_section_checks_for_direct_fhir_path(tmp_repo):
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
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "185349003", "display": "Encounter for check up"}]},
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


def test_validate_l3_decision_table_errors_when_condition_expression_missing(tmp_repo):
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
        "action": [{
            "id": "rule-verify",
            "title": "Verify diagnosis",
            "condition": [{"kind": "applicability"}],
        }],
    }))
    (computable_dir / "ActivityDefinition-action-verify.json").write_text(json.dumps({
        "resourceType": "ActivityDefinition",
        "id": "action-verify",
        "kind": "ServiceRequest",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "185349003", "display": "Encounter for check up"}]},
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
    assert result.exit_code == 1
    assert "condition[1] missing expression object" in result.output


def test_validate_l3_decision_table_errors_when_condition_define_missing_from_cql(tmp_repo):
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
        "action": [{
            "id": "rule-verify",
            "title": "Verify diagnosis",
            "condition": [{
                "kind": "applicability",
                "expression": {
                    "language": "text/cql-identifier",
                    "expression": "EligiblePatient",
                },
            }],
        }],
    }))
    (computable_dir / "ActivityDefinition-action-verify.json").write_text(json.dumps({
        "resourceType": "ActivityDefinition",
        "id": "action-verify",
        "kind": "ServiceRequest",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "185349003", "display": "Encounter for check up"}]},
        "status": "draft",
    }))
    (computable_dir / "Library-my-skill.json").write_text(json.dumps({
        "resourceType": "Library",
        "id": "my-skill",
        "status": "draft",
        "type": {"text": "logic-library"},
    }))
    (computable_dir / "MySkill.cql").write_text("""\
library MySkill version '1.0.0'

using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1' called FHIRHelpers

context Patient

define "DifferentCondition":
  exists([Condition])
""")

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
    assert result.exit_code == 1
    assert "references missing CQL define 'EligiblePatient'" in result.output


def test_validate_l3_decision_table_warns_when_condition_define_looks_parameter_based(tmp_repo):
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
        "action": [{
            "id": "rule-verify",
            "title": "Verify diagnosis",
            "condition": [{
                "kind": "applicability",
                "expression": {
                    "language": "text/cql-identifier",
                    "expression": "EligiblePatient",
                },
            }],
        }],
    }))
    (computable_dir / "ActivityDefinition-action-verify.json").write_text(json.dumps({
        "resourceType": "ActivityDefinition",
        "id": "action-verify",
        "kind": "ServiceRequest",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "185349003", "display": "Encounter for check up"}]},
        "status": "draft",
    }))
    (computable_dir / "Library-my-skill.json").write_text(json.dumps({
        "resourceType": "Library",
        "id": "my-skill",
        "status": "draft",
        "type": {"text": "logic-library"},
    }))
    (computable_dir / "MySkill.cql").write_text("""\
library MySkill version '1.0.0'

using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1' called FHIRHelpers

context Patient

parameter "EligiblePatientParameter" Boolean

define "EligiblePatient":
  EligiblePatientParameter
""")

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
    assert "maps to CQL define 'EligiblePatient' that looks parameter-based" in result.output


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


def test_validate_l3_evidence_summary_skips_missing_intermediate_sections_when_files_tracked(tmp_repo):
    topic = "my-skill"
    artifact = "evidence-summary"
    computable_dir = tmp_repo / "topics" / topic / "computable"
    computable_dir.mkdir(parents=True, exist_ok=True)

    import json

    (computable_dir / "Evidence-evidence-summary.json").write_text(json.dumps({
        "resourceType": "Evidence",
        "id": "evidence-summary",
        "status": "draft",
        "certainty": [{"rating": {"coding": [{"code": "moderate"}]}}],
    }))
    (computable_dir / "EvidenceVariable-evidence-summary-evidencevariable.json").write_text(json.dumps({
        "resourceType": "EvidenceVariable",
        "id": "evidence-summary-evidencevariable",
        "status": "draft",
        "characteristic": [{"description": "Adults with chronic rhinosinusitis"}],
    }))
    (computable_dir / "Citation-evidence-summary-citation.json").write_text(json.dumps({
        "resourceType": "Citation",
        "id": "evidence-summary-citation",
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
                "files": [
                    f"topics/{topic}/computable/Evidence-evidence-summary.json",
                    f"topics/{topic}/computable/EvidenceVariable-evidence-summary-evidencevariable.json",
                    f"topics/{topic}/computable/Citation-evidence-summary-citation.json",
                ],
                "checksums": {},
                "converged_from": [artifact],
                "strategy": "evidence-summary",
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
            "name": f"{topic}-evidence-summary",
            "source_artifact": artifact,
            "artifact_type": "evidence-summary",
            "strategy": "evidence-summary",
            "input_artifacts": [artifact],
            "l3_targets": ["Evidence", "EvidenceVariable", "Citation"],
            "required_sections": ["evidence"],
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


def test_validate_invalid_l2_exits_1(tmp_repo):
    make_invalid_l2(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "l2", "bad-artifact"])
    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_validate_assessment_from_grouped_layout(tmp_repo):
    artifact_dir = tmp_repo / "topics" / "my-skill" / "structured" / "assessments" / "phq9"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "assessment.yaml").write_text(
        """\
id: phq9
name: PHQ-9
title: PHQ-9
version: "1.0.0"
status: draft
domain: behavioral-health
description: Depression symptom assessment.
artifact_type: assessment
derived_from:
  - source-l1
sections:
  instrument:
    name: PHQ-9
  items:
    - id: q1
      text: Little interest or pleasure in doing things
      type: choice
  scoring:
    method: Sum item scores.
"""
    )

    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "structured", "phq9"])
    assert result.exit_code == 0, result.output
    assert "structured/assessments/phq9/assessment.yaml" in result.output


def test_validate_custom_artifact_from_generic_nested_layout(tmp_repo):
    artifact_dir = tmp_repo / "topics" / "my-skill" / "structured" / "artifacts" / "local-note"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "local-note.yaml").write_text(
        """\
id: local-note
name: LocalNote
title: Local Note
version: "1.0.0"
status: draft
domain: testing
description: A locally defined structured artifact.
derived_from:
  - source-l1
artifact_type: custom
clinical_question: What local content should be reviewed?
sections:
  summary: Local content.
"""
    )

    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "structured", "local-note"])
    assert result.exit_code == 0, result.output
    assert "structured/artifacts/local-note/local-note.yaml" in result.output


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
      evidence_traceability_ids: [crit-001]
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
      evidence_traceability_ids: [crit-001]
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
      evidence_traceability_ids: [crit-001]
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
      concept_refs: [surgical-candidacy-assessment]
      produces_conditions: [candidacy-appropriate]
    - id: administer-snot-22
      label: Administer SNOT-22
      kind: assessment
      parent_action_id: assess-candidacy
      concept_refs: [snot-22]
      produces_data_elements: [candidacy-support]
      assessment_artifact: snot-22
  rules:
    - id: assess
      event: assessment
      when:
        diagnosis-verified: Yes
      evidence_traceability_ids: [crit-001]
      then:
        - assess-candidacy
        - administer-snot-22
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_decision_table_warns_when_leaf_action_lacks_terminology_linkage(tmp_repo):
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
description: "Artifact with uncoded leaf action"
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
  data_elements:
    - id: dx-support
      condition_id: diagnosis-verified
      label: Diagnostic support
  actions:
    - id: assess-candidacy
      label: Assess candidacy
      kind: ServiceRequest
  rules:
    - id: assess
      event: assessment
      when:
        diagnosis-verified: Yes
      evidence_traceability_ids: [crit-001]
      then:
        - assess-candidacy
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "leaf action 'assess-candidacy' is missing recommended concept_refs[] or code/codings[] terminology linkage" in result.output


def test_validate_decision_table_warns_when_leaf_regimen_even_when_kind_is_task(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: oncology
description: "Artifact with broad regimen leaf action"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which neoadjuvant regimen is offered?"
sections:
  summary: "Use regimen selection."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Offer neoadjuvant regimen"
      evidence:
        - source: source-l1
          locator: "Recommendation 5.1"
  events:
    - id: regimen-selection
      label: Regimen selection
      trigger:
        type: named-event
        name: regimen-selection
  conditions:
    - id: high-risk
      label: High risk
      values: [Yes, No]
  data_elements:
    - id: risk-status
      condition_id: high-risk
      label: Risk status
  actions:
    - id: offer-anthracycline-taxane
      label: Offer anthracycline and taxane neoadjuvant regimen
      kind: Task
      codings:
        - system: http://www.nlm.nih.gov/research/umls/rxnorm
          code: "8812"
          display: Anthracycline
  rules:
    - id: offer-regimen
      event: regimen-selection
      when:
        high-risk: Yes
      evidence_traceability_ids: [rec-001]
      then:
        - offer-anthracycline-taxane
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert (
        "leaf action 'offer-anthracycline-taxane' appears to represent a regimen/order set"
        in result.output
    )


def test_validate_decision_table_parent_action_without_coding_does_not_warn_when_only_grouping(tmp_repo):
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
description: "Artifact with grouping parent action"
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
  data_elements:
    - id: dx-support
      condition_id: diagnosis-verified
      label: Diagnostic support
  actions:
    - id: assess-candidacy
      label: Offer anthracycline and taxane neoadjuvant regimen
    - id: administer-snot-22
      label: Administer SNOT-22
      kind: Task
      parent_action_id: assess-candidacy
      concept_refs: [snot-22]
  rules:
    - id: assess
      event: assessment
      when:
        diagnosis-verified: Yes
      evidence_traceability_ids: [crit-001]
      then:
        - assess-candidacy
        - administer-snot-22
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "leaf action 'assess-candidacy'" not in result.output
    assert "leaf action 'assess-candidacy' appears to represent a regimen/order set" not in result.output


def test_validate_decision_table_warns_when_parent_action_has_executable_kind(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: oncology
description: "Artifact with parent executable kind"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "How is the regimen decomposed?"
sections:
  summary: "Use component medication actions."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Offer regimen"
      evidence:
        - source: source-l1
          locator: "Recommendation 1"
  events:
    - id: regimen-selection
      label: Regimen selection
      trigger:
        type: named-event
        name: regimen-selection
  conditions:
    - id: eligible
      label: Eligible
      values: [Yes, No]
  data_elements:
    - id: eligibility
      condition_id: eligible
      label: Eligibility
  actions:
    - id: offer-regimen
      label: Offer anthracycline and taxane regimen
      kind: Task
    - id: order-anthracycline
      label: Order anthracycline
      kind: MedicationRequest
      parent_action_id: offer-regimen
      concept_refs: [anthracycline]
  rules:
    - id: offer
      event: regimen-selection
      when:
        eligible: Yes
      evidence_traceability_ids: [rec-001]
      then:
        - offer-regimen
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "parent action 'offer-regimen' has executable kind" in result.output


def test_validate_decision_table_rejects_leaf_action_missing_kind(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: oncology
description: "Artifact with leaf action missing kind"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which therapy is ordered?"
sections:
  summary: "Order medication."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Order medication"
      evidence:
        - source: source-l1
          locator: "Recommendation 1"
  events:
    - id: therapy-selection
      label: Therapy selection
      trigger:
        type: named-event
        name: therapy-selection
  conditions:
    - id: eligible
      label: Eligible
      values: [Yes, No]
  data_elements:
    - id: eligibility
      condition_id: eligible
      label: Eligibility
  actions:
    - id: order-anthracycline
      label: Order anthracycline
      concept_refs: [anthracycline]
  rules:
    - id: order
      event: therapy-selection
      when:
        eligible: Yes
      evidence_traceability_ids: [rec-001]
      then:
        - order-anthracycline
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "leaf action 'order-anthracycline' missing required 'kind' field" in result.output


def test_validate_decision_table_warns_for_task_leaf_kind(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: oncology
description: "Artifact with generic task action"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which action is performed?"
sections:
  summary: "Perform action."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Perform action"
      evidence:
        - source: source-l1
          locator: "Recommendation 1"
  events:
    - id: action-selection
      label: Action selection
      trigger:
        type: named-event
        name: action-selection
  conditions:
    - id: eligible
      label: Eligible
      values: [Yes, No]
  data_elements:
    - id: eligibility
      condition_id: eligible
      label: Eligibility
  actions:
    - id: review-care-plan
      label: Review care plan
      kind: Task
      concept_refs: [care-plan-review]
  rules:
    - id: review
      event: action-selection
      when:
        eligible: Yes
      evidence_traceability_ids: [rec-001]
      then:
        - review-care-plan
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "uses kind 'Task', which is too generic" in result.output


def test_validate_decision_table_warns_for_unknown_leaf_kind(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: oncology
description: "Artifact with unknown action kind"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which action is performed?"
sections:
  summary: "Perform action."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Perform action"
      evidence:
        - source: source-l1
          locator: "Recommendation 1"
  events:
    - id: action-selection
      label: Action selection
      trigger:
        type: named-event
        name: action-selection
  conditions:
    - id: eligible
      label: Eligible
      values: [Yes, No]
  data_elements:
    - id: eligibility
      condition_id: eligible
      label: Eligibility
  actions:
    - id: perform-thing
      label: Perform thing
      kind: CustomAction
      concept_refs: [thing]
  rules:
    - id: perform
      event: action-selection
      when:
        eligible: Yes
      evidence_traceability_ids: [rec-001]
      then:
        - perform-thing
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "uses unknown kind 'CustomAction'" in result.output


def test_validate_decision_table_warns_for_repeated_unhoisted_event_condition(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: surgery
description: "Artifact with repeated unhoisted condition"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which surgical actions apply?"
sections:
  summary: "Use scoped surgical recommendations."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Use recommendations for adults"
      evidence:
        - source: source-l1
          locator: "Recommendation 1"
  events:
    - id: surgical-planning
      label: Surgical planning
      trigger:
        type: named-event
        name: surgical-planning
  conditions:
    - id: adult-patient
      label: Adult patient
      values: [Yes, No]
    - id: ct-available
      label: CT available
      values: [Yes, No]
    - id: advanced-disease
      label: Advanced disease
      values: [Yes, No]
  data_elements:
    - id: patient-age
      condition_id: adult-patient
      label: Patient age
    - id: ct-status
      condition_id: ct-available
      label: CT status
    - id: disease-features
      condition_id: advanced-disease
      label: Disease features
  actions:
    - id: obtain-ct
      label: Obtain CT
      kind: service
      concept_refs: [computed-tomography]
    - id: plan-extent
      label: Plan extent
      kind: service
      concept_refs: [surgical-planning]
  rules:
    - id: obtain-ct
      event: surgical-planning
      when:
        adult-patient: Yes
        ct-available: No
      action: Obtain CT
      rationale: "Obtain CT when unavailable."
      evidence_traceability_ids: [rec-001]
      then:
        - obtain-ct
    - id: plan-extent
      event: surgical-planning
      when:
        adult-patient: Yes
        advanced-disease: Yes
      action: Plan extent
      rationale: "Plan extent for advanced disease."
      evidence_traceability_ids: [rec-001]
      then:
        - plan-extent
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "condition 'adult-patient: Yes' repeats across 2 rules for event 'surgical-planning'" in result.output
    assert "event.applicability[]" in result.output


def test_validate_decision_table_allows_repeated_condition_when_hoisted_to_event_applicability(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "test-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "test-artifact.yaml").write_text("""\
id: test-artifact
name: test-artifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: surgery
description: "Artifact with hoisted condition"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which surgical actions apply?"
sections:
  summary: "Use scoped surgical recommendations."
  evidence_traceability:
    - claim_id: rec-001
      statement: "Use recommendations for adults"
      evidence:
        - source: source-l1
          locator: "Recommendation 1"
  events:
    - id: surgical-planning
      label: Surgical planning
      applicability:
        - adult-patient
      trigger:
        type: named-event
        name: surgical-planning
  conditions:
    - id: adult-patient
      label: Adult patient
      values: [Yes, No]
    - id: ct-available
      label: CT available
      values: [Yes, No]
    - id: advanced-disease
      label: Advanced disease
      values: [Yes, No]
  data_elements:
    - id: patient-age
      condition_id: adult-patient
      label: Patient age
    - id: ct-status
      condition_id: ct-available
      label: CT status
    - id: disease-features
      condition_id: advanced-disease
      label: Disease features
  actions:
    - id: obtain-ct
      label: Obtain CT
      kind: service
      concept_refs: [computed-tomography]
    - id: plan-extent
      label: Plan extent
      kind: service
      concept_refs: [surgical-planning]
  rules:
    - id: obtain-ct
      event: surgical-planning
      when:
        ct-available: No
      action: Obtain CT
      rationale: "Obtain CT when unavailable."
      evidence_traceability_ids: [rec-001]
      then:
        - obtain-ct
    - id: plan-extent
      event: surgical-planning
      when:
        advanced-disease: Yes
      action: Plan extent
      rationale: "Plan extent for advanced disease."
      evidence_traceability_ids: [rec-001]
      then:
        - plan-extent
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 0, result.output
    assert "condition 'adult-patient'" not in result.output


def test_validate_decision_table_rejects_unknown_evidence_traceability_links(tmp_repo):
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
description: "Artifact with invalid evidence traceability links"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "How is candidacy assessed?"
sections:
  summary: "Use staged assessment."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform staged assessment"
      strength: moderate
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
    - id: assess-candidacy
      label: Assess candidacy
      kind: ServiceRequest
      evidence_traceability_ids: [crit-999]
  rules:
    - id: assess
      event: assessment
      then:
        - assess-candidacy
      evidence_traceability_ids: [crit-999]
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "unknown evidence claim_id 'crit-999'" in result.output


def test_validate_decision_table_rejects_missing_rule_evidence_traceability_links(tmp_repo):
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
description: "Artifact with missing rule evidence traceability links"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "How is candidacy assessed?"
sections:
  summary: "Use staged assessment."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform staged assessment"
      strength: moderate
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
    - id: assess-candidacy
      label: Assess candidacy
      kind: ServiceRequest
      evidence_traceability_ids: [crit-001]
  rules:
    - id: assess
      event: assessment
      then:
        - assess-candidacy
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "rule 'assess' missing required evidence_traceability_ids[] link(s)" in result.output


def test_validate_decision_table_rejects_inferred_provenance_without_rationale(tmp_repo):
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
description: "Artifact with inferred recommendation missing rationale"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "How is candidacy assessed?"
sections:
  summary: "Use staged assessment."
  evidence_traceability:
    - claim_id: crit-001
      statement: "Perform staged assessment"
      strength: moderate
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
    - id: assess-candidacy
      label: Assess candidacy
      kind: ServiceRequest
      evidence_traceability_ids: [crit-001]
      provenance:
        source: inferred
  rules:
    - id: assess
      event: assessment
      then:
        - assess-candidacy
      evidence_traceability_ids: [crit-001]
      provenance:
        source: inferred
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "test-artifact"])
    assert result.exit_code == 1
    assert "inferred provenance requires provenance.rationale" in result.output


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


def test_validate_paired_decision_table_and_care_pathway_require_full_rule_coverage(tmp_repo):
    write_extract_plan_with_artifacts(
        tmp_repo,
        artifacts=[
            {
                "name": "decision-table",
                "artifact_type": "decision-table",
                "source_files": ["sources/normalized/source-l1.md"],
                "rationale": "Decision logic",
                "key_questions": ["Which recommendations apply?"],
                "required_sections": ["summary", "events", "conditions", "data_elements", "actions", "rules", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Proceed",
            },
            {
                "name": "care-pathway",
                "artifact_type": "care-pathway",
                "source_files": ["sources/normalized/source-l1.md"],
                "rationale": "Workflow pathway",
                "key_questions": ["How do recommendations map onto the pathway?"],
                "required_sections": ["summary", "steps", "transitions", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Proceed",
            },
        ],
    )
    dt_dir = tmp_repo / "topics" / "my-skill" / "structured" / "decision-table"
    dt_dir.mkdir(parents=True, exist_ok=True)
    (dt_dir / "decision-table.yaml").write_text("""\
id: decision-table
name: decision-table
title: "Decision Table"
version: "1.0.0"
status: draft
domain: diabetes
description: "Recommendation-scoped decision logic"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which recommendations apply?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: claim-001
      statement: "Recommendation 1"
      evidence:
        - source: source-l1
          locator: "Section 1"
    - claim_id: claim-002
      statement: "Recommendation 2"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: event-001
      label: Verify diagnosis
    - id: event-002
      label: Assess candidacy
  conditions:
    - id: cond-001
      label: Eligible
      description: Eligibility check
      values: [Yes, No]
  data_elements:
    - id: de-001
      condition_id: cond-001
      label: Eligibility
      description: Supporting data
      data_type: boolean
  actions:
    - id: action-001
      label: Verify diagnosis
      kind: ServiceRequest
    - id: action-002
      label: Assess candidacy
      kind: ServiceRequest
  rules:
    - id: rule-001
      event: event-001
      then: [action-001]
      action: Verify diagnosis
      evidence_traceability_ids: [claim-001]
    - id: rule-002
      event: event-002
      then: [action-002]
      action: Assess candidacy
      evidence_traceability_ids: [claim-002]
concerns: []
""")
    cp_dir = tmp_repo / "topics" / "my-skill" / "structured" / "care-pathway"
    cp_dir.mkdir(parents=True, exist_ok=True)
    (cp_dir / "care-pathway.yaml").write_text("""\
id: care-pathway
name: care-pathway
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Pathway missing one recommendation link"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "How do recommendations map onto the pathway?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway step"
      evidence:
        - source: source-l1
          locator: "Section 1"
  steps:
    - id: step-001
      label: Main pathway
      description: Wrapper step
    - id: step-002
      label: Verify diagnosis
      description: Leaf step
      parent_id: step-001
      rule_id: rule-001
      action_labels: [Verify diagnosis]
      evidence_traceability_ids: [cp-001]
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "decision-table"])
    assert result.exit_code == 1
    assert "rule-002" in result.output
    assert "paired decision-table/care-pathway coverage failure" in result.output


def test_validate_paired_decision_table_and_care_pathway_accept_grouped_rule_ids_coverage(tmp_repo):
    write_extract_plan_with_artifacts(
        tmp_repo,
        artifacts=[
            {
                "name": "decision-table",
                "artifact_type": "decision-table",
                "source_files": ["sources/normalized/source-l1.md"],
                "rationale": "Decision logic",
                "key_questions": ["Which recommendations apply?"],
                "required_sections": ["summary", "events", "conditions", "data_elements", "actions", "rules", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Proceed",
            },
            {
                "name": "care-pathway",
                "artifact_type": "care-pathway",
                "source_files": ["sources/normalized/source-l1.md"],
                "rationale": "Workflow pathway",
                "key_questions": ["How do recommendations map onto the pathway?"],
                "required_sections": ["summary", "steps", "transitions", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Proceed",
            },
        ],
    )
    dt_dir = tmp_repo / "topics" / "my-skill" / "structured" / "decision-table"
    dt_dir.mkdir(parents=True, exist_ok=True)
    (dt_dir / "decision-table.yaml").write_text("""\
id: decision-table
name: decision-table
title: "Decision Table"
version: "1.0.0"
status: draft
domain: diabetes
description: "Recommendation-scoped decision logic"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which recommendations apply?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: claim-001
      statement: "Recommendation 1"
      evidence:
        - source: source-l1
          locator: "Section 1"
    - claim_id: claim-002
      statement: "Recommendation 2"
      evidence:
        - source: source-l1
          locator: "Section 2"
  events:
    - id: event-001
      label: Verify diagnosis
    - id: event-002
      label: Assess candidacy
  conditions:
    - id: cond-001
      label: Eligible
      description: Eligibility check
      values: [Yes, No]
  data_elements:
    - id: de-001
      condition_id: cond-001
      label: Eligibility
      description: Supporting data
      data_type: boolean
  actions:
    - id: action-001
      label: Verify diagnosis
      kind: ServiceRequest
    - id: action-002
      label: Assess candidacy
      kind: ServiceRequest
  rules:
    - id: rule-001
      event: event-001
      then: [action-001]
      action: Verify diagnosis
      evidence_traceability_ids: [claim-001]
    - id: rule-002
      event: event-002
      then: [action-002]
      action: Assess candidacy
      evidence_traceability_ids: [claim-002]
concerns: []
""")
    cp_dir = tmp_repo / "topics" / "my-skill" / "structured" / "care-pathway"
    cp_dir.mkdir(parents=True, exist_ok=True)
    (cp_dir / "care-pathway.yaml").write_text("""\
id: care-pathway
name: care-pathway
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Pathway with grouped recommendation coverage"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "How do recommendations map onto the pathway?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway step"
      evidence:
        - source: source-l1
          locator: "Section 1"
  steps:
    - id: step-001
      label: Main pathway
      description: Wrapper step
    - id: step-002
      label: Assessment and surgical decision
      description: Grouped leaf step
      parent_id: step-001
      rule_ids: [rule-001, rule-002]
      action_labels:
        - Verify diagnosis
        - Assess candidacy
      evidence_traceability_ids: [cp-001]
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-pathway"])
    assert result.exit_code == 0, result.output
    assert "paired decision-table/care-pathway coverage failure" not in result.output


def test_validate_grouped_rule_ids_still_fail_when_one_decision_table_rule_is_omitted(tmp_repo):
    write_extract_plan_with_artifacts(
        tmp_repo,
        artifacts=[
            {
                "name": "decision-table",
                "artifact_type": "decision-table",
                "source_files": ["sources/normalized/source-l1.md"],
                "rationale": "Decision logic",
                "key_questions": ["Which recommendations apply?"],
                "required_sections": ["summary", "events", "conditions", "data_elements", "actions", "rules", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Proceed",
            },
            {
                "name": "care-pathway",
                "artifact_type": "care-pathway",
                "source_files": ["sources/normalized/source-l1.md"],
                "rationale": "Workflow pathway",
                "key_questions": ["How do recommendations map onto the pathway?"],
                "required_sections": ["summary", "steps", "transitions", "evidence_traceability"],
                "concerns": [],
                "reviewer_decision": "approved",
                "approval_notes": "Proceed",
            },
        ],
    )
    dt_dir = tmp_repo / "topics" / "my-skill" / "structured" / "decision-table"
    dt_dir.mkdir(parents=True, exist_ok=True)
    (dt_dir / "decision-table.yaml").write_text("""\
id: decision-table
name: decision-table
title: "Decision Table"
version: "1.0.0"
status: draft
domain: diabetes
description: "Recommendation-scoped decision logic"
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "Which recommendations apply?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: claim-001
      statement: "Recommendation 1"
      evidence:
        - source: source-l1
          locator: "Section 1"
    - claim_id: claim-002
      statement: "Recommendation 2"
      evidence:
        - source: source-l1
          locator: "Section 2"
    - claim_id: claim-003
      statement: "Recommendation 3"
      evidence:
        - source: source-l1
          locator: "Section 3"
  events:
    - id: event-001
      label: Verify diagnosis
    - id: event-002
      label: Assess candidacy
    - id: event-003
      label: Offer surgery
  conditions:
    - id: cond-001
      label: Eligible
      description: Eligibility check
      values: [Yes, No]
  data_elements:
    - id: de-001
      condition_id: cond-001
      label: Eligibility
      description: Supporting data
      data_type: boolean
  actions:
    - id: action-001
      label: Verify diagnosis
      kind: ServiceRequest
    - id: action-002
      label: Assess candidacy
      kind: ServiceRequest
    - id: action-003
      label: Offer surgery
      kind: ServiceRequest
  rules:
    - id: rule-001
      event: event-001
      then: [action-001]
      action: Verify diagnosis
      evidence_traceability_ids: [claim-001]
    - id: rule-002
      event: event-002
      then: [action-002]
      action: Assess candidacy
      evidence_traceability_ids: [claim-002]
    - id: rule-003
      event: event-003
      then: [action-003]
      action: Offer surgery
      evidence_traceability_ids: [claim-003]
concerns: []
""")
    cp_dir = tmp_repo / "topics" / "my-skill" / "structured" / "care-pathway"
    cp_dir.mkdir(parents=True, exist_ok=True)
    (cp_dir / "care-pathway.yaml").write_text("""\
id: care-pathway
name: care-pathway
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Grouped pathway branch that still omits one recommendation"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "How do recommendations map onto the pathway?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway step"
      evidence:
        - source: source-l1
          locator: "Section 1"
  steps:
    - id: step-001
      label: Main pathway
      description: Wrapper step
    - id: step-002
      label: Assessment and surgical decision
      description: Grouped leaf step
      parent_id: step-001
      rule_ids: [rule-001, rule-002]
      action_labels:
        - Verify diagnosis
        - Assess candidacy
      evidence_traceability_ids: [cp-001]
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-pathway"])
    assert result.exit_code == 1
    assert "rule-003" in result.output
    assert "paired decision-table/care-pathway coverage failure" in result.output


def test_validate_decision_table_without_care_pathway_skips_paired_coverage_requirement(tmp_repo):
    write_extract_plan(tmp_repo, artifact="decision-table")
    make_valid_extract_l2(tmp_repo, artifact="decision-table")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "decision-table"])
    assert result.exit_code == 0, result.output
    assert "paired decision-table/care-pathway coverage failure" not in result.output


def test_validate_care_pathway_without_decision_table_skips_paired_coverage_requirement(tmp_repo):
    write_extract_plan(tmp_repo, artifact="care-pathway")
    plan_path = tmp_repo / "topics" / "my-skill" / "process" / "plans" / "extract-plan.yaml"
    plan = YAML().load(plan_path.read_text())
    plan["artifacts"][0]["artifact_type"] = "care-pathway"
    plan["artifacts"][0]["required_sections"] = ["summary", "evidence_traceability", "steps", "transitions"]
    y = YAML()
    y.default_flow_style = False
    with open(plan_path, "w") as f:
        y.dump(plan, f)

    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-pathway"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-pathway.yaml").write_text("""\
id: care-pathway
name: care-pathway
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway only"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "What is the pathway?"
sections:
  summary: "Summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway step"
      evidence:
        - source: source-l1
          locator: "Section 1"
  steps:
    - id: step-001
      label: Main pathway
      description: Leaf step
      rule_id: rule-001
      action_labels: [Assess candidacy]
      evidence_traceability_ids: [cp-001]
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-pathway"])
    assert result.exit_code == 0, result.output
    assert "paired decision-table/care-pathway coverage failure" not in result.output


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


def test_validate_care_pathway_accepts_rule_and_action_links(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with explicit decision-table rule links"
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
      rule_id: rule-1
      action_labels:
        - Review prior therapy
        - Offer surgery
      evidence_traceability_ids:
        - cp-001
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_care_pathway_accepts_rule_ids_on_leaf_step(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with grouped recommendation rule links"
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
      rule_ids: [rule-1, rule-2]
      action_labels:
        - Review prior therapy
        - Offer surgery
      evidence_traceability_ids:
        - cp-001
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 0, result.output


def test_validate_care_pathway_rejects_unknown_evidence_traceability_links(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with invalid evidence links on rule-linked steps"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "What is the pathway?"
sections:
  summary: "Pathway summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway statement"
      strength: moderate
      evidence:
        - source: source-l1
          locator: "Section 2"
  steps:
    - id: main-pathway
      label: Main pathway
      description: Overall pathway
    - id: assess-candidacy
      label: Assess surgical candidacy
      description: Recommendation branch
      parent_id: main-pathway
      rule_id: rule-004
      action_labels:
        - Assess surgical candidacy
      evidence_traceability_ids:
        - cp-999
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 1
    assert "unknown evidence claim_id 'cp-999'" in result.output


def test_validate_care_pathway_rejects_missing_recommendation_evidence_traceability_links(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with recommendation branch missing evidence links"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "What is the pathway?"
sections:
  summary: "Pathway summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway statement"
      strength: moderate
      evidence:
        - source: source-l1
          locator: "Section 2"
  steps:
    - id: main-pathway
      label: Main pathway
      description: Overall pathway
    - id: assess-candidacy
      label: Assess surgical candidacy
      description: Recommendation branch
      parent_id: main-pathway
      rule_id: rule-004
      action_labels:
        - Assess surgical candidacy
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 1
    assert "phase 'assess-candidacy' missing required evidence_traceability_ids[] link(s)" in result.output


def test_validate_care_pathway_rejects_inferred_provenance_without_rationale(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with inferred recommendation missing rationale"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "What is the pathway?"
sections:
  summary: "Pathway summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway statement"
      strength: moderate
      evidence:
        - source: source-l1
          locator: "Section 2"
  steps:
    - id: main-pathway
      label: Main pathway
      description: Overall pathway
    - id: assess-candidacy
      label: Evaluate treatment readiness
      description: Recommendation branch
      parent_id: main-pathway
      rule_id: rule-004
      action_labels:
        - Start antihyperglycemic therapy
      evidence_traceability_ids:
        - cp-001
      provenance:
        source: inferred
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 1
    assert "inferred provenance requires provenance.rationale" in result.output


def test_validate_care_pathway_warns_on_semantic_mismatch_between_step_and_actions(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with intentionally mismatched step/action semantics"
derived_from:
  - source-l1
artifact_type: care-pathway
clinical_question: "What is the pathway?"
sections:
  summary: "Pathway summary"
  evidence_traceability:
    - claim_id: cp-001
      statement: "Pathway statement"
      strength: moderate
      evidence:
        - source: source-l1
          locator: "Section 2"
  steps:
    - id: main-pathway
      label: Main pathway
      description: Overall pathway
    - id: retinal-screening
      label: Perform diabetic retinal screening
      description: Screen for retinopathy
      parent_id: main-pathway
      rule_id: rule-004
      action_labels:
        - Initiate insulin pump therapy
      evidence_traceability_ids:
        - cp-001
      provenance:
        source: source_direct
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 0, result.output
    assert "may be semantically misaligned with step intent" in result.output


def test_validate_care_pathway_rejects_children_under_rule_linked_step(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway that incorrectly decomposes one recommendation into child pathway tasks"
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
    - id: main-pathway
      label: Main pathway
      description: Overall pathway
    - id: assess-candidacy
      label: Assess surgical candidacy
      description: Recommendation branch
      parent_id: main-pathway
      rule_id: rule-004
      action_labels:
        - Assess surgical candidacy
    - id: questionnaire
      label: Offer surgery
      description: Separate child branch that should not sit under a rule-linked step
      parent_id: assess-candidacy
    - id: review-history
      label: Review therapy history
      description: Component task that should live in the decision table
      parent_id: assess-candidacy
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 1
    assert "rule-linked pathway steps must be leaves" in result.output


def test_validate_care_pathway_rejects_children_under_rule_ids_linked_step(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with grouped rule links incorrectly attached to a parent step"
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
    - id: assessment
      label: Assessment and surgical decision
      description: Shared parent branch
      rule_ids: [rule-001, rule-004]
      action_labels:
        - Verify diagnosis
        - Assess surgical candidacy
      evidence_traceability_ids:
        - cp-001
    - id: verify-diagnosis
      label: Verify diagnosis
      description: First child branch
      parent_id: assessment
    - id: assess-candidacy
      label: Assess surgical candidacy
      description: Second child branch
      parent_id: assessment
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 1
    assert "rule-linked pathway steps must be leaves" in result.output


def test_validate_care_pathway_allows_distinct_rule_linked_sibling_branches(tmp_repo):
    write_extract_plan(tmp_repo)
    td = tmp_repo / "topics" / "my-skill" / "structured" / "care-artifact"
    td.mkdir(parents=True, exist_ok=True)
    (td / "care-artifact.yaml").write_text("""\
id: care-artifact
name: care-artifact
title: "Care Pathway"
version: "1.0.0"
status: draft
domain: diabetes
description: "Care pathway with sibling recommendation branches"
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
    - id: main-pathway
      label: Main pathway
      description: Overall pathway
    - id: assessment
      label: Assessment and surgical decision
      description: Distinct recommendation branches sit underneath this orchestration step
      parent_id: main-pathway
    - id: verify-diagnosis
      label: Verify diagnosis
      description: First recommendation branch
      parent_id: assessment
      rule_id: rule-001
      action_labels:
        - Verify diagnosis
      evidence_traceability_ids:
        - cp-001
      provenance:
        source: source_direct
    - id: assess-candidacy
      label: Assess surgical candidacy
      description: Second recommendation branch
      parent_id: assessment
      rule_id: rule-004
      action_labels:
        - Assess surgical candidacy
      evidence_traceability_ids:
        - cp-001
      provenance:
        source: source_direct
  transitions: []
concerns: []
""")
    runner = CliRunner()
    result = runner.invoke(validate, ["my-skill", "care-artifact"])
    assert result.exit_code == 0, result.output


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
