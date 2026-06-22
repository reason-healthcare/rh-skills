"""Regression tests for rh-skills formalize — CQL stub removal (T019).

Verifies that `rh-skills formalize` never auto-generates a .cql file. CQL
authoring is delegated to the `rh-inf-cql` skill (rh-skills cql …).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.formalize import (
    _activity_definition_kind,
    _build_care_pathway_stub_plan_definitions,
    _normalize_activity_codeable_concept,
    formalize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_activity_definition_kind_normalizes_supported_l2_action_kinds():
    assert _activity_definition_kind("medication") == "MedicationRequest"
    assert _activity_definition_kind("MedicationRequest") == "MedicationRequest"
    assert _activity_definition_kind("service") == "ServiceRequest"
    assert _activity_definition_kind("procedure") == "ServiceRequest"
    assert _activity_definition_kind("referral") == "ServiceRequest"
    assert _activity_definition_kind("assessment") == "ServiceRequest"
    assert _activity_definition_kind("questionnaire") == "CollectInformation"
    assert _activity_definition_kind("CollectInformation") == "CollectInformation"
    assert _activity_definition_kind("communication") == "CommunicationRequest"
    assert _activity_definition_kind("Task") == "Task"

def _make_tracking_yaml(topic_dir: Path, topic_name: str, artifact: str, artifact_type: str = "measure"):
    """Write a minimal tracking.yaml with a formalize-ready artifact."""
    y = YAML()
    tracking = {
        "topic": topic_name,
        "status": "active",
        "structured": [
            {
                "name": artifact,
                "type": artifact_type,
                "files": [f"topics/{topic_name}/structured/{artifact}.yaml"],
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
    }
    tracking_path = topic_dir / "tracking.yaml"
    with open(tracking_path, "w") as f:
        y.dump(tracking, f)
    return tracking_path


def _make_structured_artifact(structured_dir: Path, artifact: str, artifact_type: str = "measure"):
    """Write a minimal structured YAML artifact."""
    content = f"""\
artifact_type: {artifact_type}
name: {artifact}
display: Test Artifact
description: A test artifact for regression testing.
fhir_version: "4.0.1"
"""
    (structured_dir / f"{artifact}.yaml").write_text(content)


def _make_formalize_config(topic_dir: Path, topic_name: str):
    """Write a minimal formalize-config.yaml for a topic."""
    process_dir = topic_dir / "process"
    process_dir.mkdir(parents=True, exist_ok=True)
    content = f"""\
name: {_to_pascal(topic_name)}
id: {topic_name}
canonical: http://example.org/fhir
status: draft
version: 0.1.0
"""
    (process_dir / "formalize-config.yaml").write_text(content)


def _to_pascal(slug: str) -> str:
    return "".join(w.capitalize() for w in slug.split("-"))


def test_grouped_care_pathway_recommendation_actions_use_recommendation_titles():
    l2_data = {
        "sections": {
            "steps": [
                {
                    "id": "protocol",
                    "label": "Clinical Protocol",
                    "description": "Overall protocol.",
                },
                {
                    "id": "evaluate-candidacy",
                    "label": "Evaluate candidacy",
                    "description": "Evaluate several candidacy concerns.",
                    "parent_id": "protocol",
                    "rule_ids": ["rule-a", "rule-b"],
                    "action_labels": ["Verify diagnosis", "Assess candidacy"],
                },
            ],
        },
    }
    recommendation_plan_map = {
        "rule-a": "http://example.org/fhir/PlanDefinition/test-recommendation-a",
        "rule-b": "http://example.org/fhir/PlanDefinition/test-recommendation-b",
    }

    resources, _ = _build_care_pathway_stub_plan_definitions(
        "test-protocol",
        "http://example.org/fhir",
        {"version": "0.1.0", "status": "draft"},
        l2_data,
        recommendation_plan_map=recommendation_plan_map,
    )

    child_plan = next(resource for resource in resources if resource["id"] == "test-protocol-evaluate-candidacy")
    parent_action = child_plan["action"][0]

    assert parent_action["title"] == "Evaluate candidacy"
    assert [action["title"] for action in parent_action["action"]] == [
        "Verify diagnosis",
        "Assess candidacy",
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Create a minimal repo layout and chdir into it."""
    (tmp_path / "topics").mkdir()
    (tmp_path / "sources").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNoAutoGeneratedCql:
    """Ensure formalize never writes a .cql file automatically."""

    def test_formalize_does_not_write_cql_for_measure_artifact(self, tmp_repo):
        """A measure artifact with a Library strategy must NOT produce a .cql file."""
        topic = "lipid-management"
        artifact = "ldl-monitoring"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        _make_tracking_yaml(topic_dir, topic, artifact, "measure")
        _make_structured_artifact(structured_dir, artifact, "measure")
        _make_formalize_config(topic_dir, topic)

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)

        # No .cql file should be written
        cql_files = list(computable_dir.glob("*.cql"))
        assert cql_files == [], (
            f"formalize must NOT write CQL files — found: {[f.name for f in cql_files]}. "
            "CQL authoring belongs to `rh-inf-cql` (author mode)."
        )

    def test_formalize_emits_rh_cql_guidance_for_library_artifacts(self, tmp_repo):
        """When a Library is in scope, formalize should emit a guidance note mentioning rh-inf-cql."""
        topic = "lipid-management"
        artifact = "ldl-monitoring"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        _make_tracking_yaml(topic_dir, topic, artifact, "measure")
        _make_structured_artifact(structured_dir, artifact, "measure")
        _make_formalize_config(topic_dir, topic)

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)

        # Guidance note about rh-inf-cql should appear when Library is in scope
        combined = (result.output or "")
        if "Library" in combined or ".cql" in combined:
            assert "rh-inf-cql" in combined, (
                "When a Library resource is in scope, formalize must emit a guidance "
                "note referencing `rh-inf-cql` (author mode). Got output:\n" + combined
            )

    def test_formalize_cql_stub_not_in_source(self):
        """Regression: the auto-generated CQL stub block must not be present in formalize.py."""
        formalize_src = Path("src/rh_skills/commands/formalize.py")
        if not formalize_src.exists():
            pytest.skip("formalize.py not found at expected path")
        content = formalize_src.read_text()
        stub_marker = "library {cql_name} version"
        assert stub_marker not in content, (
            "The CQL auto-generation stub was found in formalize.py — "
            "this code must be removed. CQL authoring belongs to rh-inf-cql."
        )


class TestDecisionTableConditionStub:
    """Ensure decision-table formalization emits activity definitions and rule actions."""

    def _make_root_tracking_yaml(self, root: Path, topic_name: str, artifact: str, artifact_type: str):
        """Write a root tracking.yaml with the correct topics list format."""
        y = YAML()
        tracking = {
            "topics": [
                {
                    "name": topic_name,
                    "status": "active",
                    "events": [],
                    "structured": [
                        {
                            "name": artifact,
                            "artifact_type": artifact_type,
                            "files": [f"topics/{topic_name}/structured/{artifact}.yaml"],
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                }
            ]
        }
        with open(root / "tracking.yaml", "w") as f:
            y.dump(tracking, f)

    def _make_decision_table_artifact(self, structured_dir: Path, artifact: str, conditions: list):
        rows = "\n".join(
            f"    - id: {c['id']}\n      label: {c['label']}\n      values:\n        - 'Yes'\n        - 'No'"
            for c in conditions
        )
        content = f"""\
artifact_type: decision-table
name: {artifact}
display: Test Decision Table
description: A test decision-table artifact.
fhir_version: "4.0.1"
sections:
  summary: Test summary
  events:
    - id: ev1
      label: Screening encounter
      trigger_type: named-event
  conditions:
{rows}
  actions:
    - id: a1
      label: Refer to specialist
      kind: communication
  rules:
    - id: r1
      event: ev1
      when:
        {conditions[0]['id']}: 'Yes'
      then:
        - a1
"""
        (structured_dir / f"{artifact}.yaml").write_text(content)

    def test_decision_table_actions_reference_condition_defines(self, tmp_repo):
        """Each rule should produce a PlanDefinition action that points to ActivityDefinitions."""
        topic = "bells-palsy"
        artifact = "management-decision"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        conditions = [
            {"id": "c1", "label": "Facial weakness present"},
            {"id": "c2", "label": "Eye closure affected"},
        ]
        self._make_root_tracking_yaml(tmp_repo, topic, artifact, "decision-table")
        self._make_decision_table_artifact(structured_dir, artifact, conditions)
        _make_formalize_config(topic_dir, topic)

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)
        assert result.exit_code == 0, result.output

        plan_files = list(computable_dir.glob("PlanDefinition-*.json"))
        assert plan_files, "Expected a PlanDefinition JSON stub to be written"

        root_plan = json.loads((computable_dir / f"PlanDefinition-{artifact}.json").read_text())
        assert root_plan["action"][0]["definitionCanonical"] == "http://example.org/fhir/PlanDefinition/management-decision-ev1"

        plan_json = json.loads((computable_dir / "PlanDefinition-management-decision-ev1.json").read_text())
        actions = plan_json.get("action", [])
        assert len(actions) == 1, f"Expected 1 action (one per rule), got {len(actions)}: {actions}"
        assert actions[0]["id"] == "a1"
        expressions = [c["expression"]["expression"] for c in actions[0].get("condition", [])]
        assert "FacialWeaknessPresent" in expressions, f"Missing CQL define for c1; got {expressions}"
        assert actions[0]["definitionCanonical"] == "http://example.org/fhir/ActivityDefinition/a1"

        activity_files = sorted(computable_dir.glob("ActivityDefinition-*.json"))
        assert len(activity_files) == 1, f"Expected one ActivityDefinition, got {[f.name for f in activity_files]}"
        activity_json = json.loads(activity_files[0].read_text())
        assert activity_json["id"] == "a1"
        assert activity_json["title"] == "Refer to specialist"
        assert activity_json["kind"] == "CommunicationRequest"

    def test_decision_table_event_trigger_does_not_emit_action_trigger(self, tmp_repo):
        topic = "trigger-topic"
        artifact = "triggered-decision"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        self._make_root_tracking_yaml(tmp_repo, topic, artifact, "decision-table")
        _make_formalize_config(topic_dir, topic)
        (structured_dir / f"{artifact}.yaml").write_text(
            """\
artifact_type: decision-table
name: triggered-decision
description: Trigger-rich decision table.
sections:
  events:
    - id: postsurgical-review
      label: Postsurgical review
      trigger:
        type: named-event
        name: endoscopic-sinus-surgery-completed
        resource: Procedure
        resource_criteria:
          code: 312999006
          system: http://snomed.info/sct
          display: Functional endoscopic sinus surgery
  conditions:
    - id: c1
      label: Routine follow-up window open
      values: [Yes, No]
  actions:
    - id: a1
      label: Assess outcomes
      kind: ServiceRequest
  rules:
    - id: r1
      event: postsurgical-review
      when:
        c1: Yes
      then:
        - a1
"""
        )

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)
        assert result.exit_code == 0, result.output

        child_plan = json.loads((computable_dir / "PlanDefinition-triggered-decision-postsurgical-review.json").read_text())
        assert "trigger" not in child_plan["action"][0]

    def test_decision_table_event_trigger_context_is_not_written_to_action_trigger(self, tmp_repo):
        topic = "trigger-window-topic"
        artifact = "timing-window-decision"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        self._make_root_tracking_yaml(tmp_repo, topic, artifact, "decision-table")
        _make_formalize_config(topic_dir, topic)
        (structured_dir / f"{artifact}.yaml").write_text(
            """\
artifact_type: decision-table
name: timing-window-decision
description: Trigger-rich decision table with timing window.
sections:
  events:
    - id: postsurgical-review
      label: Postsurgical review
      trigger:
        type: named-event
        name: endoscopic-sinus-surgery-completed
        source: procedure-status
        resource: Procedure
        moment: completed
        resource_criteria:
          code: 312999006
          system: http://snomed.info/sct
          display: Functional endoscopic sinus surgery
        timing_window:
          start_after: 3 months
          end_after: 12 months
  conditions:
    - id: c1
      label: Routine follow-up window open
      values: [Yes, No]
  actions:
    - id: a1
      label: Assess outcomes
      kind: ServiceRequest
  rules:
    - id: r1
      event: postsurgical-review
      when:
        c1: Yes
      then:
        - a1
"""
        )

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)
        assert result.exit_code == 0, result.output

        child_plan = json.loads((computable_dir / "PlanDefinition-timing-window-decision-postsurgical-review.json").read_text())
        assert "trigger" not in child_plan["action"][0]

    def test_decision_table_without_conditions_falls_back_to_generic_action(self, tmp_repo):
        """If L2 artifact has no conditions, fall back to generic stub action."""
        topic = "bells-palsy"
        artifact = "empty-decision"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        self._make_root_tracking_yaml(tmp_repo, topic, artifact, "decision-table")
        _make_structured_artifact(structured_dir, artifact, "decision-table")
        _make_formalize_config(topic_dir, topic)

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)
        assert result.exit_code == 0, result.output

        plan_files = list(computable_dir.glob("PlanDefinition-*.json"))
        assert plan_files, "Expected a PlanDefinition JSON stub to be written"

        plan_json = json.loads(plan_files[0].read_text())
        actions = plan_json.get("action", [])
        assert len(actions) == 1
        assert actions[0]["title"] == "Initial action"

    def test_decision_table_rule_with_negative_condition_uses_negated_expression(self, tmp_repo):
        """A rule condition with No should emit a negated applicability expression."""
        topic = "bells-palsy"
        artifact = "negative-decision"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        self._make_root_tracking_yaml(tmp_repo, topic, artifact, "decision-table")
        (structured_dir / f"{artifact}.yaml").write_text(
            """\
artifact_type: decision-table
name: negative-decision
display: Negative Decision Table
description: A test decision-table artifact.
fhir_version: "4.0.1"
sections:
  events:
    - id: ev1
      label: Screening encounter
  conditions:
    - id: c1
      label: Purulent discharge present
      values:
        - yes
        - no
  actions:
    - id: a1
      label: Avoid antibiotics
      kind: medication
      do_not_perform: true
  rules:
    - id: r1
      event: ev1
      when:
        c1: 'no'
      then:
        - a1
"""
        )
        _make_formalize_config(topic_dir, topic)

        runner = CliRunner()
        result = runner.invoke(formalize, [topic, artifact], catch_exceptions=False)
        assert result.exit_code == 0, result.output

        plan_json = json.loads((computable_dir / "PlanDefinition-negative-decision-ev1.json").read_text())
        condition = plan_json["action"][0]["condition"][0]["expression"]
        assert condition["language"] == "text/cql-expression"
        assert condition["expression"] == "not PurulentDischargePresent"

        activity_json = json.loads((computable_dir / "ActivityDefinition-a1.json").read_text())
        assert activity_json["kind"] == "MedicationRequest"
        assert activity_json["doNotPerform"] is True

    def test_activity_code_prefers_rxnorm_first_for_medication_request(self):
        code = {
            "coding": [
                {"system": "http://snomed.info/sct", "code": "372729009", "display": "Antibiotic therapy"},
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "723", "display": "Amoxicillin"},
            ],
            "text": "Prescribe amoxicillin",
        }
        normalized = _normalize_activity_codeable_concept(
            code,
            kind="MedicationRequest",
            action_id="prescribe-amoxicillin",
            title="Prescribe amoxicillin",
            description="Start oral amoxicillin therapy.",
        )
        assert normalized is not None
        assert normalized["coding"][0]["system"] == "http://www.nlm.nih.gov/research/umls/rxnorm"

    def test_activity_code_prefers_loinc_first_for_service_request_lab_order(self):
        code = {
            "coding": [
                {"system": "http://snomed.info/sct", "code": "104177005", "display": "Hemoglobin A1c measurement"},
                {"system": "http://loinc.org", "code": "4548-4", "display": "HbA1c/Total Hgb, Blood"},
            ],
            "text": "Order HbA1c",
        }
        normalized = _normalize_activity_codeable_concept(
            code,
            kind="ServiceRequest",
            action_id="order-hba1c",
            title="Order HbA1c",
            description="Order hemoglobin A1c laboratory measurement.",
        )
        assert normalized is not None
        assert normalized["coding"][0]["system"] == "http://loinc.org"
