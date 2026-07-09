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
    _activity_definition_intent,
    _build_care_pathway_stub_plan_definitions,
    _build_stub_resources,
    _enforce_generated_fhir_ids,
    _fhir_resource_id,
    _get_strategy,
    _hoist_plan_definition_action_conditions,
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
    assert _activity_definition_kind("diagnostic-test") == "ServiceRequest"
    assert _activity_definition_kind("assessment") == "ServiceRequest"
    assert _activity_definition_kind("questionnaire") == "Task"
    assert _activity_definition_kind("CollectInformation") == "Task"
    assert _activity_definition_kind("communication") == "CommunicationRequest"
    assert _activity_definition_kind("Task") == "Task"


def test_activity_definition_intent_normalizes_to_r4_request_intent_codes():
    assert _activity_definition_intent("order") == "order"
    assert _activity_definition_intent("Plan") == "plan"
    assert _activity_definition_intent("collect quality of life score") == "proposal"
    assert _activity_definition_intent(None) == "proposal"


def test_fhir_resource_id_preserves_short_ids_and_shortens_long_ids_deterministically():
    short_id = "adult-crs-recommendation"
    long_id = "adult-crs-surgical-management-recommendation-for-revision-surgery-candidacy-review"

    assert _fhir_resource_id(short_id) == short_id
    shortened = _fhir_resource_id(long_id)
    assert len(shortened) <= 64
    assert shortened == _fhir_resource_id(long_id)
    assert shortened.startswith("adult-crs-surgical-management-recommendation")


def test_enforce_generated_fhir_ids_rewrites_canonical_and_relative_references():
    long_plan_id = (
        "adult-crs-surgical-management-recommendation-for-revision-surgery-"
        "candidacy-review"
    )
    long_library_id = f"{long_plan_id}-logic"
    resources = [
        {
            "resourceType": "PlanDefinition",
            "id": long_plan_id,
            "url": f"http://example.org/fhir/PlanDefinition/{long_plan_id}",
            "library": [f"http://example.org/fhir/Library/{long_library_id}"],
            "action": [{
                "definitionCanonical": f"http://example.org/fhir/PlanDefinition/{long_plan_id}",
            }],
        },
        {
            "resourceType": "Library",
            "id": long_library_id,
            "url": f"http://example.org/fhir/Library/{long_library_id}",
        },
        {
            "resourceType": "Evidence",
            "id": "short-evidence",
            "exposureBackground": {
                "reference": f"PlanDefinition/{long_plan_id}",
            },
        },
    ]

    rewrites = _enforce_generated_fhir_ids(resources)
    plan_id = resources[0]["id"]
    library_id = resources[1]["id"]

    assert {rewrite["resourceType"] for rewrite in rewrites} == {"PlanDefinition", "Library"}
    assert len(plan_id) <= 64
    assert len(library_id) <= 64
    assert resources[0]["url"] == f"http://example.org/fhir/PlanDefinition/{plan_id}"
    assert resources[0]["library"] == [f"http://example.org/fhir/Library/{library_id}"]
    assert resources[0]["action"][0]["definitionCanonical"] == (
        f"http://example.org/fhir/PlanDefinition/{plan_id}"
    )
    assert resources[2]["exposureBackground"]["reference"] == f"PlanDefinition/{plan_id}"


def test_plan_definition_condition_hoisting_moves_shared_sibling_conditions_to_parent():
    shared = {
        "kind": "applicability",
        "expression": {
            "language": "text/cql-identifier",
            "expression": "CrsDiagnosisVerified",
        },
    }
    branch_only = {
        "kind": "applicability",
        "expression": {
            "language": "text/cql-identifier",
            "expression": "SurgeryPlanningActive",
        },
    }
    plan = {
        "resourceType": "PlanDefinition",
        "action": [{
            "id": "shared-branch",
            "action": [
                {"id": "a", "condition": [shared]},
                {"id": "b", "condition": [shared, branch_only]},
            ],
        }],
    }

    _hoist_plan_definition_action_conditions(plan)

    parent = plan["action"][0]
    assert parent["condition"] == [shared]
    assert "condition" not in parent["action"][0]
    assert parent["action"][1]["condition"] == [branch_only]


def test_plan_definition_condition_hoisting_requires_all_siblings_to_share_condition():
    shared = {
        "kind": "applicability",
        "expression": {
            "language": "text/cql-identifier",
            "expression": "CrsDiagnosisVerified",
        },
    }
    plan = {
        "resourceType": "PlanDefinition",
        "action": [{
            "id": "mixed-branch",
            "action": [
                {"id": "a", "condition": [shared]},
                {"id": "b"},
            ],
        }],
    }

    _hoist_plan_definition_action_conditions(plan)

    parent = plan["action"][0]
    assert "condition" not in parent
    assert parent["action"][0]["condition"] == [shared]
    assert "condition" not in parent["action"][1]


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


def _condition_expressions_by_action_id(resources: list[dict]) -> dict[str, list[tuple[str, ...]]]:
    expressions_by_id: dict[str, list[tuple[str, ...]]] = {}

    def walk(actions: list[dict] | None) -> None:
        for action in actions or []:
            if not isinstance(action, dict):
                continue
            action_id = str(action.get("id") or "").strip()
            condition_expressions = tuple(
                str(condition.get("expression", {}).get("expression") or "")
                for condition in action.get("condition") or []
                if isinstance(condition, dict)
            )
            if action_id:
                expressions_by_id.setdefault(action_id, []).append(condition_expressions)
            walk(action.get("action"))

    for resource in resources:
        if resource.get("resourceType") == "PlanDefinition":
            walk(resource.get("action"))
    return expressions_by_id


def test_paired_care_pathway_condition_context_hoists_and_prunes_rule_conditions(tmp_repo):
    topic = "mini-crs"
    topic_dir = tmp_repo / "topics" / topic
    structured_dir = topic_dir / "structured"
    structured_dir.mkdir(parents=True)
    _make_formalize_config(topic_dir, topic)

    decision_table = {
        "artifact_type": "decision-table",
        "name": "decision-table",
        "sections": {
            "applicability": [{"condition_id": "adult-age-criterion-met", "value": "Yes"}],
            "events": [{"id": "event", "label": "Clinical review"}],
            "conditions": [
                {"id": "adult-age-criterion-met", "label": "Adult age criterion met", "values": ["Yes", "No"]},
                {"id": "crs-diagnosis-verified", "label": "CRS diagnosis verified", "values": ["Yes", "No"]},
                {"id": "guideline-exclusion-present", "label": "Guideline exclusion present", "values": ["Yes", "No"]},
                {"id": "sinus-surgery-planning-active", "label": "Sinus surgery planning active", "values": ["Yes", "No"]},
                {"id": "fine-cut-ct-available", "label": "Fine cut CT available", "values": ["Yes", "No"]},
                {"id": "sinus-surgery-order-present", "label": "Sinus surgery order present", "values": ["Yes", "No"]},
                {"id": "purulent-discharge-present", "label": "Purulent discharge present", "values": ["Yes", "No"]},
                {"id": "crs-subtype-likely-to-benefit", "label": "CRS subtype likely to benefit from surgery", "values": ["Yes", "No"]},
                {"id": "surgical-candidacy-established", "label": "Surgical candidacy established", "values": ["Yes", "No"]},
            ],
            "actions": [
                {"id": "verify-diagnosis", "label": "Verify diagnosis", "kind": "Task"},
                {"id": "collect-snot", "label": "Collect SNOT-22", "kind": "Task"},
                {"id": "obtain-ct", "label": "Obtain CT", "kind": "ServiceRequest"},
                {"id": "educate-postop", "label": "Educate about postoperative care", "kind": "CommunicationRequest"},
                {"id": "avoid-antibiotic", "label": "Avoid antibiotic therapy", "kind": "CommunicationRequest"},
                {"id": "assess-candidacy", "label": "Assess candidacy", "kind": "Task"},
                {"id": "identify-subtype", "label": "Identify CRS subtype", "kind": "Task"},
                {"id": "avoid-fixed-therapy", "label": "Do not require fixed medical therapy", "kind": "CommunicationRequest"},
                {"id": "offer-surgery", "label": "Offer sinus surgery", "kind": "ServiceRequest"},
            ],
            "rules": [
                {
                    "id": "rule-verify",
                    "event": "event",
                    "when": {"crs-diagnosis-verified": "Yes", "guideline-exclusion-present": "No"},
                    "then": ["verify-diagnosis"],
                },
                {
                    "id": "rule-snot",
                    "event": "event",
                    "when": {"guideline-exclusion-present": "No"},
                    "then": ["collect-snot"],
                },
                {
                    "id": "rule-ct",
                    "event": "event",
                    "when": {
                        "crs-diagnosis-verified": "Yes",
                        "guideline-exclusion-present": "No",
                        "sinus-surgery-planning-active": "Yes",
                        "fine-cut-ct-available": "No",
                    },
                    "then": ["obtain-ct"],
                },
                {
                    "id": "rule-educate",
                    "event": "event",
                    "when": {
                        "crs-diagnosis-verified": "Yes",
                        "guideline-exclusion-present": "No",
                        "sinus-surgery-planning-active": "Yes",
                        "sinus-surgery-order-present": "Yes",
                    },
                    "then": ["educate-postop"],
                },
                {
                    "id": "rule-antibiotic",
                    "event": "event",
                    "when": {"purulent-discharge-present": "No"},
                    "then": ["avoid-antibiotic"],
                },
                {
                    "id": "rule-assess-candidacy",
                    "event": "event",
                    "when": {"crs-diagnosis-verified": "Yes"},
                    "then": ["assess-candidacy"],
                },
                {
                    "id": "rule-identify-subtype",
                    "event": "event",
                    "when": {
                        "crs-diagnosis-verified": "Yes",
                        "crs-subtype-likely-to-benefit": "Yes",
                    },
                    "then": ["identify-subtype"],
                },
                {
                    "id": "rule-avoid-fixed-therapy",
                    "event": "event",
                    "when": {"crs-diagnosis-verified": "Yes"},
                    "then": ["avoid-fixed-therapy"],
                },
                {
                    "id": "rule-offer-surgery",
                    "event": "event",
                    "when": {
                        "crs-diagnosis-verified": "Yes",
                        "surgical-candidacy-established": "Yes",
                    },
                    "then": ["offer-surgery"],
                },
            ],
        },
    }
    care_pathway = {
        "artifact_type": "care-pathway",
        "name": "care-pathway",
        "sections": {
            "steps": [
                {"id": "protocol", "label": "Protocol", "applicability_condition": "adult-age-criterion-met"},
                {"id": "eligibility", "label": "Eligibility", "parent_id": "protocol"},
                {"id": "verify-step", "label": "Verify diagnosis", "parent_id": "eligibility", "rule_id": "rule-verify"},
                {"id": "snot-step", "label": "Collect SNOT-22", "parent_id": "eligibility", "rule_id": "rule-snot"},
                {"id": "planning", "label": "Planning", "parent_id": "protocol"},
                {"id": "ct-step", "label": "Obtain CT", "parent_id": "planning", "rule_id": "rule-ct"},
                {
                    "id": "educate-step",
                    "label": "Educate postoperative care",
                    "parent_id": "planning",
                    "applicability_condition": "sinus-surgery-order-present",
                    "rule_id": "rule-educate",
                },
                {"id": "antibiotic-review", "label": "Antibiotic review", "parent_id": "protocol"},
                {
                    "id": "avoid-antibiotic-step",
                    "label": "Avoid antibiotics",
                    "parent_id": "antibiotic-review",
                    "rule_id": "rule-antibiotic",
                },
                {
                    "id": "candidacy",
                    "label": "Assess surgical candidacy",
                    "parent_id": "protocol",
                    "rule_ids": [
                        "rule-assess-candidacy",
                        "rule-identify-subtype",
                        "rule-avoid-fixed-therapy",
                        "rule-offer-surgery",
                    ],
                },
            ],
        },
    }

    y = YAML()
    with open(structured_dir / "decision-table.yaml", "w") as f:
        y.dump(decision_table, f)
    with open(structured_dir / "care-pathway.yaml", "w") as f:
        y.dump(care_pathway, f)
    topic_entry = {
        "name": topic,
        "structured": [
            {"name": "decision-table", "artifact_type": "decision-table"},
            {"name": "care-pathway", "artifact_type": "care-pathway"},
        ],
    }

    cfg = {"canonical": "http://example.org/fhir", "version": "0.1.0", "status": "draft"}
    decision_strategy, _ = _get_strategy("decision-table")
    pathway_strategy, _ = _get_strategy("care-pathway")

    decision_resources = _build_stub_resources(
        "decision-table",
        "decision-table",
        decision_strategy,
        topic,
        cfg,
        decision_table,
        topic_entry=topic_entry,
    )
    pathway_resources = _build_stub_resources(
        "care-pathway",
        "care-pathway",
        pathway_strategy,
        topic,
        cfg,
        care_pathway,
        topic_entry=topic_entry,
    )

    pathway_conditions = _condition_expressions_by_action_id(pathway_resources)
    assert ("AdultAgeCriterionMet",) in pathway_conditions["protocol"]
    assert ("NoGuidelineExclusionPresent",) in pathway_conditions["eligibility"]
    assert (
        "CrsDiagnosisVerified",
        "NoGuidelineExclusionPresent",
        "SinusSurgeryPlanningActive",
    ) in pathway_conditions["planning"]
    assert ("SinusSurgeryOrderPresent",) in pathway_conditions["educate-step"]
    assert ("CrsDiagnosisVerified",) in pathway_conditions["candidacy"]

    decision_conditions = _condition_expressions_by_action_id(decision_resources)
    assert ("CrsDiagnosisVerified",) in decision_conditions["verify-diagnosis"]
    assert ("NoGuidelineExclusionPresent",) not in decision_conditions["verify-diagnosis"]
    assert decision_conditions["collect-snot"] == [()]
    assert ("NoFineCutCtAvailable",) in decision_conditions["obtain-ct"]
    assert all("NoGuidelineExclusionPresent" not in entry for entry in decision_conditions["obtain-ct"])
    assert decision_conditions["educate-postop"] == [()]
    assert all(entry == () for entry in decision_conditions["assess-candidacy"])
    assert all(entry == () for entry in decision_conditions["avoid-fixed-therapy"])
    assert ("CrsSubtypeLikelyToBenefitFromSurgery",) in decision_conditions["identify-subtype"]
    assert all("CrsDiagnosisVerified" not in entry for entry in decision_conditions["identify-subtype"])
    assert ("SurgicalCandidacyEstablished",) in decision_conditions["offer-surgery"]
    assert all("CrsDiagnosisVerified" not in entry for entry in decision_conditions["offer-surgery"])


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

    def test_decision_table_rule_with_negative_condition_uses_named_negative_define(self, tmp_repo):
        """A rule condition with No should reference a named CQL define."""
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
        assert condition["language"] == "text/cql-identifier"
        assert condition["expression"] == "NoPurulentDischargePresent"

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
