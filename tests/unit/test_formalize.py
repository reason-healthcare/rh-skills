"""Regression tests for rh-skills formalize — CQL stub removal (T019).

Verifies that `rh-skills formalize` never auto-generates a .cql file. CQL
authoring is delegated to the `rh-inf-cql` skill (rh-skills cql …).
"""

from __future__ import annotations

import json
import os
import base64
import hashlib
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.formalize import (
    _activity_definition_kind,
    _activity_definition_intent,
    _build_measure_populations,
    _build_care_pathway_stub_plan_definitions,
    _build_decision_table_activity_definitions,
    _build_decision_table_referenced_actions,
    _build_decision_table_rule_conditions,
    _build_evidence_variable_characteristics,
    _resolve_activity_code,
    _build_terminology_stub_resources,
    _build_questionnaire_items,
    _build_questionnaire_resource,
    _build_stub_resources,
    _collect_information_dynamic_values,
    _embed_cql_in_library,
    _attach_external_library_dependencies,
    _enforce_generated_fhir_ids,
    _fhir_resource_id,
    _get_strategy,
    _hoist_plan_definition_action_conditions,
    _normalize_activity_codeable_concept,
    _orphaned_decision_table_output_files,
    _validate_cql_identifier_links,
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


def test_decision_guidance_remains_inline_without_activity_definition():
    cfg = {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"}
    l2 = {"sections": {
        "actions": [{
            "id": "offer-exercise", "label": "Offer exercise intervention",
            "description": "Recommend exercise when the screen is positive.", "kind": "guidance",
        }],
        "events": [{"id": "screen", "label": "Screening"}],
        "conditions": [{"id": "positive", "label": "Positive screen", "values": ["Yes", "No"]}],
        "rules": [{"id": "r1", "event": "screen", "when": {"positive": "Yes"}, "then": ["offer-exercise"]}],
    }}
    strategy, _ = _get_strategy("decision-table")
    resources = _build_stub_resources("fall-screen", "decision-table", strategy, "topic", cfg, l2)
    assert not [r for r in resources if r.get("resourceType") == "ActivityDefinition"]
    rule_plan = next(r for r in resources if r.get("id") == "fall-screen-screen")
    action = rule_plan["action"][0]
    assert action["title"] == "Offer exercise intervention"
    assert action["description"] == "Recommend exercise when the screen is positive."
    assert "definitionCanonical" not in action
    assert action["condition"][0]["expression"]["expression"] == "PositiveScreen"
    library = next(resource for resource in resources if resource.get("resourceType") == "Library")
    assert library["type"]["coding"] == [{
        "system": "http://terminology.hl7.org/CodeSystem/library-type",
        "code": "logic-library",
    }]


def test_decision_executable_action_requires_authored_or_exact_approved_code():
    cfg = {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"}
    l2 = {"sections": {"actions": [{"id": "refer", "label": "Refer", "kind": "referral"}]}}
    with pytest.raises(ValueError, match="requires an authored code/codings"):
        _build_decision_table_activity_definitions("topic", cfg, l2)


def test_decision_exact_concept_ref_preserves_approved_versioned_code():
    cfg = {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"}
    l2 = {"sections": {"actions": [{
        "id": "screen", "label": "Screen", "kind": "service", "concept_refs": ["fall-screen"],
    }]}}
    candidates = [{
        "normalized_id": "fall-screen",
        "code": {"coding": [{"system": "http://loinc.org", "version": "2.81", "code": "100257-5"}]},
    }]
    resources = _build_decision_table_activity_definitions("topic", cfg, l2, concept_candidates=candidates)
    assert resources[0]["code"]["coding"] == [{"system": "http://loinc.org", "version": "2.81", "code": "100257-5"}]


def test_regenerated_library_keeps_matching_external_dependency(tmp_path):
    cql = tmp_path / "DecisionLogic.cql"
    cql.write_text("library DecisionLogic version '1'\ninclude FHIRHelpers version '4.0.1' called FHIRHelpers\n")
    resources = [{"resourceType": "Library", "id": "decision", "name": "DecisionLogic"}]
    tracking = {"computable": [{
        "strategy": "external-dependency",
        "external_dependency": {
            "canonical": "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers",
            "name": "FHIRHelpers", "version": "4.0.1",
        },
    }]}
    _attach_external_library_dependencies(resources, tmp_path, tracking)
    assert resources[0]["relatedArtifact"] == [{
        "type": "depends-on",
        "resource": "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers|4.0.1",
    }]


def test_evidence_variable_uses_authored_criteria_and_rejects_empty_source():
    characteristics = _build_evidence_variable_characteristics(
        "eligibility-criteria", {"sections": {"criteria": ["Adults age 65 years or older"]}}
    )
    assert characteristics == [{
        "description": "Criteria: Adults age 65 years or older",
        "definitionCodeableConcept": {"text": "Criteria: Adults age 65 years or older"},
    }]
    with pytest.raises(ValueError, match="requires authored criteria"):
        _build_evidence_variable_characteristics("eligibility-criteria", {"sections": {}})


def test_value_set_include_preserves_declared_system_version():
    resources = _build_terminology_stub_resources(
        "screening-items",
        {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"},
        {"sections": {"value_sets": [{
            "id": "screening-items", "system": "http://loinc.org", "version": "2.81",
            "codes": [{"code": "100257-5", "display": "Unsteady"}],
        }]}},
    )
    assert resources[0]["compose"]["include"][0]["version"] == "2.81"


def test_local_complete_code_system_is_emitted_with_authored_identity_and_concepts():
    resources = _build_terminology_stub_resources(
        "assessment-score-terminology",
        {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"},
        {"sections": {
            "code_systems": [{
                "id": "three-question-score",
                "url": "https://example.org/fhir/CodeSystem/three-question-score",
                "version": "0.2.0",
                "name": "ThreeQuestionScore",
                "title": "Three-question yes count",
                "status": "active",
                "content": "complete",
                "case_sensitive": True,
                "concepts": [{
                    "code": "yes-count",
                    "display": "Three-question yes count",
                    "definition": "Number of true answers across the three screening questions.",
                }],
            }],
            "value_sets": [{
                "id": "three-question-score",
                "system": "https://example.org/fhir/CodeSystem/three-question-score",
                "version": "0.2.0",
                "codes": [{"code": "yes-count", "display": "Three-question yes count"}],
            }],
        }},
    )

    code_system = next(resource for resource in resources if resource["resourceType"] == "CodeSystem")
    value_set = next(resource for resource in resources if resource["resourceType"] == "ValueSet")
    assert code_system == {
        "resourceType": "CodeSystem",
        "id": "three-question-score",
        "url": "https://example.org/fhir/CodeSystem/three-question-score",
        "version": "0.2.0",
        "status": "active",
        "content": "complete",
        "caseSensitive": True,
        "name": "ThreeQuestionScore",
        "title": "Three-question yes count",
        "concept": [{
            "code": "yes-count",
            "display": "Three-question yes count",
            "definition": "Number of true answers across the three screening questions.",
        }],
    }
    assert value_set["compose"]["include"] == [{
        "system": "https://example.org/fhir/CodeSystem/three-question-score",
        "version": "0.2.0",
        "concept": [{"code": "yes-count", "display": "Three-question yes count"}],
    }]


@pytest.mark.parametrize("mutation, message", [
    ("missing-url", "url must be a non-empty string"),
    ("unsafe-id", "must be a valid FHIR id"),
    ("fragment", "content must be complete"),
    ("case-sensitive", "case_sensitive must be boolean"),
    ("invalid-status", "must be a valid publication status"),
    ("non-string-title", "title must be a non-empty string"),
    ("missing-definition", "definition must be a non-empty string"),
    ("duplicate-code", "duplicate code"),
])
def test_local_code_system_rejects_incomplete_or_ambiguous_authored_definition(mutation, message):
    code_system = {
        "id": "score",
        "url": "https://example.org/fhir/CodeSystem/score",
        "version": "0.2.0",
        "content": "complete",
        "case_sensitive": True,
        "concepts": [{"code": "count", "display": "Count", "definition": "A count."}],
    }
    if mutation == "missing-url":
        del code_system["url"]
    elif mutation == "unsafe-id":
        code_system["id"] = "../score"
    elif mutation == "fragment":
        code_system["content"] = "fragment"
    elif mutation == "case-sensitive":
        code_system["case_sensitive"] = "true"
    elif mutation == "invalid-status":
        code_system["status"] = "unknown-status"
    elif mutation == "non-string-title":
        code_system["title"] = {"not": "text"}
    elif mutation == "missing-definition":
        del code_system["concepts"][0]["definition"]
    elif mutation == "duplicate-code":
        code_system["case_sensitive"] = False
        code_system["concepts"][0]["code"] = "Count"
        code_system["concepts"].append({"code": "count", "display": "Count again", "definition": "Duplicate."})

    with pytest.raises(ValueError, match=message):
        _build_terminology_stub_resources(
            "terminology",
            {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"},
            {"sections": {"code_systems": [code_system]}},
        )


def test_code_system_only_terminology_does_not_invent_a_placeholder_value_set():
    resources = _build_terminology_stub_resources(
        "terminology",
        {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"},
        {"sections": {"code_systems": [{
            "id": "score",
            "url": "https://example.org/fhir/CodeSystem/score",
            "version": "0.2.0",
            "content": "complete",
            "case_sensitive": True,
            "concepts": [{"code": "count", "display": "Count", "definition": "A count."}],
        }]}},
    )
    assert [resource["resourceType"] for resource in resources] == ["CodeSystem"]


def test_value_set_concept_refs_preserve_approved_code_versions():
    resources = _build_terminology_stub_resources(
        "screening-items",
        {"canonical": "https://example.org/fhir", "version": "1", "status": "draft"},
        {
            "concepts": [{
                "id": "unsteady",
                "codes": [{
                    "system": "http://loinc.org", "version": "2.81",
                    "code": "100257-5", "display": "Feel unsteady when standing or walking",
                }],
            }],
            "sections": {"value_sets": [{
                "id": "screening-items", "concept_refs": ["unsteady"],
            }]},
        },
    )
    include = resources[0]["compose"]["include"][0]
    assert include["system"] == "http://loinc.org"
    assert include["version"] == "2.81"
    assert include["concept"] == [{"code": "100257-5", "display": "Feel unsteady when standing or walking"}]


def _verified_value_set_l2():
    compose = {"include": [{
        "system": "http://loinc.org",
        "version": "2.81",
        "concept": [
            {"code": "100257-5", "display": "Feel unsteady when standing or walking"},
            {"code": "97878-3", "display": "Worried about falling"},
            {"code": "52552-7", "display": "Falls in the past year"},
        ],
    }]}
    response = {
        "total": 3,
        "timestamp": "2026-09-17T23:49:25.532Z",
        "contains": [
            {"system": "http://loinc.org", "code": "100257-5", "display": "Feel unsteady when standing or walking", "version": "2.81"},
            {"system": "http://loinc.org", "code": "97878-3", "display": "Worried about falling", "version": "2.81"},
            {"system": "http://loinc.org", "code": "52552-7", "display": "Falls in the past year", "version": "2.81"},
        ],
    }
    digest = hashlib.sha256(
        json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "artifact_type": "terminology",
        "sections": {"value_sets": [{
            "id": "screening-items",
            "name": "Screening items",
            "system": "http://loinc.org",
            "version": "2.81",
            "codes": [
                {"code": "100257-5", "display": "Feel unsteady when standing or walking"},
                {"code": "97878-3", "display": "Worried about falling"},
                {"code": "52552-7", "display": "Falls in the past year"},
            ],
            "expansion": {
                "source": {
                    "provider": "ReasonHub MCP",
                    "reference": "evidence/loinc-expansion.json",
                    "response_timestamp": response["timestamp"],
                    "response_sha256": digest,
                },
                "requested_compose": compose,
                "response": response,
            },
        }]},
    }


def test_verified_value_set_expansion_preserves_response_after_integrity_checks():
    artifact = _verified_value_set_l2()
    resources = _build_terminology_stub_resources(
        "terminology",
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        artifact,
    )
    assert resources[0]["expansion"] == artifact["sections"]["value_sets"][0]["expansion"]["response"]


@pytest.mark.parametrize("mutation, message", [
    ("requested-compose", "requested_compose does not match"),
    ("response-hash", "response hash does not match"),
    ("response-version", "membership does not match"),
    ("duplicate-membership", "duplicate membership"),
    ("total", "total does not match"),
    ("timestamp", "timestamp does not match"),
])
def test_verified_value_set_expansion_rejects_unverified_or_incomplete_data(mutation, message):
    artifact = _verified_value_set_l2()
    expansion = artifact["sections"]["value_sets"][0]["expansion"]
    if mutation == "requested-compose":
        expansion["requested_compose"]["include"][0]["version"] = "2.82"
    elif mutation == "response-hash":
        expansion["response"]["contains"][0]["display"] = "altered"
    elif mutation == "response-version":
        expansion["response"]["contains"][0]["version"] = "2.82"
        payload = json.dumps(expansion["response"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expansion["source"]["response_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    elif mutation == "duplicate-membership":
        expansion["response"]["contains"].append(dict(expansion["response"]["contains"][0]))
        expansion["response"]["total"] = 4
        payload = json.dumps(expansion["response"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expansion["source"]["response_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    elif mutation == "total":
        expansion["response"]["total"] = 2
        payload = json.dumps(expansion["response"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expansion["source"]["response_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    elif mutation == "timestamp":
        expansion["source"]["response_timestamp"] = "2026-09-18T00:00:00Z"

    with pytest.raises(ValueError, match=message):
        _build_terminology_stub_resources(
            "terminology",
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
            artifact,
        )


def test_event_applicability_is_combined_with_rule_conditions():
    entries = _build_decision_table_rule_conditions(
        {"id": "offer-screen", "when": {"positive-risk": "Yes"}},
        {
            "eligible": {"id": "eligible", "label": "In screening population"},
            "positive-risk": {"id": "positive-risk", "label": "Positive screen"},
        },
        event={"id": "ambulatory-encounter", "applicability": ["eligible"]},
    )

    assert [entry["expression"]["expression"] for entry in entries] == [
        "InScreeningPopulation",
        "PositiveScreen",
    ]


def test_collect_information_dynamic_values_use_activity_fhirpath_and_indexed_inputs():
    values = _collect_information_dynamic_values("https://example.org/Questionnaire/test|1.0")

    assert values == [
        {
            "path": "input[0].type",
            "expression": {"language": "text/fhirpath", "expression": "code"},
        },
        {
            "path": "input[0].valueCanonical",
            "expression": {
                "language": "text/fhirpath",
                "expression": "extension.where(url = 'http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-collectWith').value",
            },
        },
    ]


def test_activity_definition_preserves_authored_coding_version():
    code = _resolve_activity_code(
        {
            "codings": [{
                "system": "http://snomed.info/sct",
                "version": "http://snomed.info/sct/731000124108/version/20250901",
                "code": "710580007",
                "display": "Education about fall prevention",
            }],
        },
        action_id="communicate-positive-screen",
        title="Communicate positive screen",
    )

    assert code["coding"][0] == {
        "system": "http://snomed.info/sct",
        "version": "http://snomed.info/sct/731000124108/version/20250901",
        "code": "710580007",
        "display": "Education about fall prevention",
    }


def test_cql_link_validation_rejects_referenced_identifier_missing_from_library(tmp_path):
    resources = [
        {
            "resourceType": "Library",
            "id": "logic",
            "url": "https://example.org/Library/logic",
            "name": "Logic",
        },
        {
            "resourceType": "PlanDefinition",
            "id": "plan",
            "library": ["https://example.org/Library/logic"],
            "action": [{
                "condition": [{
                    "expression": {
                        "language": "text/cql-identifier",
                        "expression": "PositiveScreen",
                    },
                }],
            }],
        },
    ]
    (tmp_path / "logic.cql").write_text('library Logic version \'1.0.0\'\ndefine "OtherExpression": true\n')

    with pytest.raises(ValueError, match="PositiveScreen"):
        _validate_cql_identifier_links(resources, tmp_path)


def test_cql_link_validation_accepts_identifier_defined_in_linked_library(tmp_path):
    resources = [
        {
            "resourceType": "Library",
            "id": "logic",
            "url": "https://example.org/Library/logic",
            "name": "Logic",
        },
        {
            "resourceType": "PlanDefinition",
            "id": "plan",
            "library": ["https://example.org/Library/logic"],
            "action": [{
                "condition": [{
                    "expression": {
                        "language": "text/cql-identifier",
                        "expression": "PositiveScreen",
                    },
                }],
            }],
        },
    ]
    (tmp_path / "logic.cql").write_text('library Logic version \'1.0.0\'\ndefine "PositiveScreen": true\n')

    assert _validate_cql_identifier_links(resources, tmp_path) == []


def test_decision_table_orphan_cleanup_removes_only_stale_children_and_unreferenced_activities(tmp_path):
    stale_plan = {
        "resourceType": "PlanDefinition",
        "id": "root-negative",
        "url": "https://example.org/fhir/PlanDefinition/root-negative",
        "action": [{
            "definitionCanonical": "https://example.org/fhir/ActivityDefinition/old-action",
        }],
    }
    unrelated_plan = {
        "resourceType": "PlanDefinition",
        "id": "other-plan",
        "url": "https://example.org/fhir/PlanDefinition/other-plan",
        "action": [],
    }
    (tmp_path / "PlanDefinition-root-negative.json").write_text(json.dumps(stale_plan))
    (tmp_path / "PlanDefinition-other-plan.json").write_text(json.dumps(unrelated_plan))
    (tmp_path / "ActivityDefinition-old-action.json").write_text(json.dumps({
        "resourceType": "ActivityDefinition",
        "id": "old-action",
        "url": "https://example.org/fhir/ActivityDefinition/old-action",
    }))

    stale = _orphaned_decision_table_output_files(
        tmp_path,
        "https://example.org/fhir",
        "root",
        {"PlanDefinition-root-current.json"},
        resources=[{
            "resourceType": "PlanDefinition",
            "id": "root",
            "url": "https://example.org/fhir/PlanDefinition/root",
            "action": [],
        }],
        protected_filenames=set(),
    )

    assert stale == ["ActivityDefinition-old-action.json", "PlanDefinition-root-negative.json"]


def test_decision_table_orphan_cleanup_preserves_activity_referenced_by_current_outputs(tmp_path):
    stale_plan = {
        "resourceType": "PlanDefinition",
        "id": "root-negative",
        "url": "https://example.org/fhir/PlanDefinition/root-negative",
        "action": [{
            "definitionCanonical": "https://example.org/fhir/ActivityDefinition/shared-action",
        }],
    }
    (tmp_path / "PlanDefinition-root-negative.json").write_text(json.dumps(stale_plan))
    (tmp_path / "ActivityDefinition-shared-action.json").write_text(json.dumps({
        "resourceType": "ActivityDefinition",
        "id": "shared-action",
        "url": "https://example.org/fhir/ActivityDefinition/shared-action",
    }))

    stale = _orphaned_decision_table_output_files(
        tmp_path,
        "https://example.org/fhir",
        "root",
        set(),
        resources=[{
            "resourceType": "PlanDefinition",
            "id": "current",
            "url": "https://example.org/fhir/PlanDefinition/current",
            "action": [{
                "definitionCanonical": "https://example.org/fhir/ActivityDefinition/shared-action",
            }],
        }],
        protected_filenames=set(),
    )

    assert stale == ["PlanDefinition-root-negative.json"]


def test_questionnaire_item_preserves_coding_and_required_false():
    items = _build_questionnaire_items("assessment", {"sections": {"items": [{
        "id": "unsteady",
        "text": "Feel unsteady?",
        "type": "boolean",
        "required": False,
        "code": {
            "version": "2.81",
            "system": "http://loinc.org",
            "code": "100257-5",
            "display": "Feel unsteady when standing or walking",
        },
    }]}})

    assert items == [{
        "linkId": "unsteady",
        "text": "Feel unsteady?",
        "type": "boolean",
        "required": False,
        "code": [{
            "version": "2.81",
            "system": "http://loinc.org",
            "code": "100257-5",
            "display": "Feel unsteady when standing or walking",
        }],
    }]


def test_questionnaire_item_keeps_omitted_required_omitted():
    items = _build_questionnaire_items("assessment", {"sections": {"items": [{
        "id": "question-1", "text": "Question?", "type": "boolean",
    }]}})
    assert "required" not in items[0]


def test_related_questionnaire_preserves_explicit_canonical_and_version():
    questionnaire = _build_questionnaire_resource(
        "steadi-fall-screening",
        "assessment",
        {
            "title": "STEADI Three-Question Fall-Risk Screen",
            "sections": {"instrument": {
                "id": "steadi-three-question-screen",
                "canonical": "https://example.org/fhir/Questionnaire/steadi-three-question-screen",
                "version": "0.2.0",
            }, "items": []},
        },
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )

    assert questionnaire["id"] == "steadi-three-question-screen"
    assert questionnaire["url"] == "https://example.org/fhir/Questionnaire/steadi-three-question-screen"
    assert questionnaire["version"] == "0.2.0"


def test_questionnaire_emits_authored_sdc_observation_extraction_metadata():
    questionnaire = _build_questionnaire_resource(
        "steadi-fall-screening",
        "assessment",
        {
            "title": "STEADI Three-Question Fall-Risk Screen",
            "sections": {
                "instrument": {
                    "id": "steadi-three-question-screen",
                    "canonical": "https://example.org/fhir/Questionnaire/steadi-three-question-screen",
                    "version": "0.2.0",
                    "version_algorithm": {
                        "system": "http://hl7.org/fhir/version-algorithm",
                        "code": "semver",
                    },
                    "observation_extraction": {
                        "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                        "enabled": True,
                        "category": {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "survey",
                            "display": "Survey",
                        },
                    },
                },
                "items": [{
                    "id": "unsteady",
                    "text": "Do you feel unsteady?",
                    "type": "boolean",
                    "code": {
                        "system": "http://loinc.org",
                        "version": "2.81",
                        "code": "100257-5",
                        "display": "Feel unsteady when standing or walking",
                    },
                }],
            },
        },
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )

    assert questionnaire["meta"]["profile"] == [
        "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0"
    ]
    assert questionnaire["extension"] == [
        {
            "url": "http://hl7.org/fhir/StructureDefinition/artifact-versionAlgorithm",
            "valueCoding": {
                "system": "http://hl7.org/fhir/version-algorithm",
                "code": "semver",
            },
        },
        {
            "url": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-observationExtract",
            "valueBoolean": True,
        },
        {
            "url": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-observation-extract-category",
            "valueCodeableConcept": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "survey",
                    "display": "Survey",
                }]
            },
        },
    ]


def test_questionnaire_omits_sdc_fields_when_extraction_is_disabled():
    questionnaire = _build_questionnaire_resource(
        "topic",
        "assessment",
        {"sections": {"instrument": {
            "observation_extraction": {
                "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                "enabled": False,
            },
        }, "items": [{
            "id": "unsteady", "text": "Do you feel unsteady?", "type": "boolean",
            "code": {"system": "http://loinc.org", "version": "2.81", "code": "100257-5", "display": "Feel unsteady"},
        }]}},
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )
    assert "meta" not in questionnaire
    assert "extension" not in questionnaire


def test_questionnaire_rejects_enabled_sdc_extraction_without_explicit_version_algorithm():
    with pytest.raises(ValueError, match="version_algorithm is required"):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            {"sections": {"instrument": {
                "observation_extraction": {
                    "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                    "enabled": True,
                    "category": {"system": "urn:test", "code": "survey", "display": "Survey"},
                },
            }, "items": []}},
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


def test_questionnaire_preserves_version_algorithm_when_extraction_is_disabled():
    questionnaire = _build_questionnaire_resource(
        "topic",
        "assessment",
        {"sections": {"instrument": {
            "version_algorithm": {
                "system": "http://hl7.org/fhir/version-algorithm",
                "code": "semver",
            },
            "observation_extraction": {
                "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                "enabled": False,
            },
        }, "items": [{
            "id": "unsteady", "text": "Do you feel unsteady?", "type": "boolean",
            "code": {"system": "http://loinc.org", "version": "2.81", "code": "100257-5", "display": "Feel unsteady"},
        }]}},
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )
    assert questionnaire["extension"] == [{
        "url": "http://hl7.org/fhir/StructureDefinition/artifact-versionAlgorithm",
        "valueCoding": {
            "system": "http://hl7.org/fhir/version-algorithm",
            "code": "semver",
        },
    }]


@pytest.mark.parametrize("extraction", [
    {"profile": "http://example.org/Profile|1.0", "enabled": True,
     "category": {"system": "urn:test", "code": "survey", "display": "Survey"}},
    {"profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
     "enabled": "true", "category": {"system": "urn:test", "code": "survey", "display": "Survey"}},
    {"profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
     "enabled": True, "category": {"system": "urn:test", "code": "survey"}},
    {"profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
     "enabled": True, "category": {"system": "urn:test", "code": "survey", "display": "Survey"},
     "extension": []},
])
def test_questionnaire_rejects_unsupported_sdc_extraction_metadata(extraction):
    with pytest.raises(ValueError, match="observation_extraction"):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            {"sections": {"instrument": {"observation_extraction": extraction}, "items": []}},
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


def test_questionnaire_rejects_incomplete_sdc_extraction_item_coding():
    with pytest.raises(ValueError, match="Coding requires non-empty version"):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            {"sections": {"instrument": {
                "version_algorithm": {
                    "system": "http://hl7.org/fhir/version-algorithm",
                    "code": "semver",
                },
                "observation_extraction": {
                    "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                    "enabled": True,
                    "category": {"system": "urn:test", "code": "survey", "display": "Survey"},
                },
            }, "items": [{
                "id": "q1", "text": "Question?", "type": "boolean",
                "code": {"system": "http://loinc.org", "code": "1234-5", "display": "Question"},
            }]}},
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


def _scored_assessment_l2(input_required=True):
    extraction_profile = (
        "http://hl7.org/fhir/uv/sdc/StructureDefinition/"
        "sdc-questionnaire-extr-obsn|4.0.0"
    )
    return {
        "title": "Two-item score example",
        "sections": {
            "instrument": {
                "id": "two-item-assessment",
                "canonical": "https://example.org/fhir/Questionnaire/two-item-assessment",
                "version": "1.0.0",
                "version_algorithm": {
                    "system": "http://hl7.org/fhir/version-algorithm",
                    "code": "semver",
                },
                "observation_extraction": {
                    "profile": extraction_profile,
                    "enabled": True,
                    "category": {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                        "display": "Survey",
                    },
                },
            },
            "items": [
                {
                    "id": "item-a",
                    "text": "Question A?",
                    "type": "boolean",
                    "required": input_required,
                    "code": {"system": "https://example.org/codes", "version": "1", "code": "a", "display": "Question A"},
                },
                {
                    "id": "item-b",
                    "text": "Question B?",
                    "type": "boolean",
                    "required": True,
                    "code": {"system": "https://example.org/codes", "version": "1", "code": "b", "display": "Question B"},
                },
            ],
            "scoring": {
                "algorithm": {
                    "method": "count_boolean_answers",
                    "input_items": ["item-a", "item-b"],
                    "counted_value": True,
                    "completion": "all_inputs_usable",
                    "missing_or_invalid": "omit_result",
                    "evidence_traceability_ids": ["authored-scoring-rule"],
                },
                "result": {
                    "item": {
                        "id": "affirmative-count",
                        "text": "Number of affirmative answers",
                        "type": "integer",
                        "code": {
                            "system": "https://example.org/codes",
                            "version": "1.0.0",
                            "code": "affirmative-count",
                            "display": "Affirmative answer count",
                        },
                    },
                    "range": {"minimum": 0, "maximum": 2},
                },
                "classifications": [{
                    "id": "screen-positive",
                    "label": "At least one affirmative answer",
                    "operator": "greater_than_or_equal",
                    "threshold": 1,
                    "evidence_traceability_ids": ["authored-scoring-rule"],
                }],
            },
            "evidence_traceability": [{
                "claim_id": "authored-scoring-rule",
                "statement": "The source defines this two-item Boolean count.",
                "evidence": [{"source": "source-document", "locator": "scoring section"}],
            }],
        },
    }


def test_scored_questionnaire_emits_optional_readonly_sdc_score_item():
    questionnaire = _build_questionnaire_resource(
        "topic",
        "assessment",
        _scored_assessment_l2(),
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )

    source_items = questionnaire["item"][:2]
    score_item = questionnaire["item"][2]
    assert [item["linkId"] for item in source_items] == ["item-a", "item-b"]
    assert all(item["type"] == "boolean" and item["required"] is True for item in source_items)
    assert score_item["linkId"] == "affirmative-count"
    assert score_item["type"] == "integer"
    assert score_item["readOnly"] is True
    assert score_item["code"] == [{
        "system": "https://example.org/codes",
        "version": "1.0.0",
        "code": "affirmative-count",
        "display": "Affirmative answer count",
    }]
    extensions = {extension["url"]: extension for extension in score_item["extension"]}
    assert extensions["http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-observationExtract"]["valueBoolean"] is True
    expression = extensions["http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-calculatedExpression"]["valueExpression"]
    assert expression["language"] == "text/fhirpath"
    assert "%resource.status" not in expression["expression"]
    assert ".where(linkId = 'item-a').count() = 1" in expression["expression"]
    assert ".where(linkId = 'item-b').answer.value.ofType(boolean).where($this = true).count()" in expression["expression"]


def test_ordinary_assessment_scoring_does_not_force_sdc_or_score_item():
    questionnaire = _build_questionnaire_resource(
        "topic",
        "assessment",
        {"sections": {
            "items": [{"id": "q1", "text": "Question?", "type": "choice"}],
            "scoring": {"method": "classification", "description": "Source narrative only."},
        }},
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )
    assert len(questionnaire["item"]) == 1
    assert questionnaire["item"][0]["linkId"] == "q1"


@pytest.mark.parametrize(("mutate", "error"), [
    (lambda l2: l2["sections"]["scoring"]["algorithm"].update(method="weighted_sum"), "currently supported method"),
    (lambda l2: l2["sections"]["scoring"]["algorithm"].update(missing_or_invalid="count_as_zero"), "missing_or_invalid must be omit_result"),
    (lambda l2: l2["sections"]["scoring"]["result"].update(range={"minimum": 0, "maximum": 3}), "maximum equal to the number"),
    (lambda l2: l2["sections"]["scoring"]["result"]["item"].update(code={"system": "x", "version": "1", "code": "c"}), "code.display"),
    (lambda l2: l2["sections"]["scoring"]["classifications"][0].update(threshold=3), "within the score range"),
])
def test_scored_questionnaire_rejects_unsupported_or_invalid_contract(mutate, error):
    l2 = _scored_assessment_l2()
    mutate(l2)
    with pytest.raises(ValueError, match=error):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            l2,
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


def test_scored_questionnaire_requires_required_boolean_inputs():
    with pytest.raises(ValueError, match="must be required"):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            _scored_assessment_l2(input_required=False),
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


def test_scored_questionnaire_requires_enabled_observation_extraction():
    l2 = _scored_assessment_l2()
    l2["sections"]["instrument"]["observation_extraction"]["enabled"] = False
    with pytest.raises(ValueError, match="requires enabled SDC Observation extraction"):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            l2,
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


@pytest.mark.parametrize("algorithm", [
    "semver",
    {"system": "http://hl7.org/fhir/version-algorithm"},
    {"system": "http://hl7.org/fhir/version-algorithm", "code": "semver", "foo": "bar"},
])
def test_questionnaire_rejects_unsupported_version_algorithm(algorithm):
    with pytest.raises(ValueError, match="version_algorithm"):
        _build_questionnaire_resource(
            "topic",
            "assessment",
            {"sections": {"instrument": {"version_algorithm": algorithm}, "items": []}},
            {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        )


def test_assessment_stub_generation_preserves_explicit_questionnaire_identity():
    strategy, _ = _get_strategy("assessment")
    resources = _build_stub_resources(
        "assessment",
        "assessment",
        strategy,
        "steadi-fall-screening",
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        {"sections": {"instrument": {
            "id": "steadi-three-question-screen",
            "canonical": "https://example.org/fhir/Questionnaire/steadi-three-question-screen",
            "version": "0.2.0",
            "version_algorithm": {
                "system": "http://hl7.org/fhir/version-algorithm",
                "code": "semver",
            },
            "observation_extraction": {
                "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                "enabled": True,
                "category": {
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "survey",
                    "display": "Survey",
                },
            },
        }, "items": [{
            "id": "unsteady", "text": "Do you feel unsteady?", "type": "boolean",
            "code": {"system": "http://loinc.org", "version": "2.81", "code": "100257-5", "display": "Feel unsteady"},
        }]}},
    )
    questionnaire = next(r for r in resources if r["resourceType"] == "Questionnaire")

    assert questionnaire["id"] == "steadi-three-question-screen"
    assert questionnaire["url"] == "https://example.org/fhir/Questionnaire/steadi-three-question-screen"
    assert questionnaire["version"] == "0.2.0"
    assert questionnaire["meta"]["profile"] == [
        "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0"
    ]
    extraction_extension = next(
        extension for extension in questionnaire["extension"]
        if extension["url"].endswith("sdc-questionnaire-observationExtract")
    )
    assert extraction_extension["valueBoolean"] is True


def test_measure_generation_preserves_all_authored_populations_and_bound_codesystems():
    strategy, _ = _get_strategy("measure")
    resources = _build_stub_resources(
        "measure",
        "measure",
        strategy,
        "fall-screening",
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
        {"sections": {"populations": [
            {"id": "initial-population", "type": "initial-population", "description": "Eligible patients."},
            {"id": "denominator", "type": "denominator", "description": "All eligible patients."},
            {"id": "numerator", "type": "numerator", "description": "Eligible patients with a completed screen."},
        ]}},
    )
    measure = next(resource for resource in resources if resource["resourceType"] == "Measure")

    assert measure["scoring"]["coding"] == [{
        "system": "http://terminology.hl7.org/CodeSystem/measure-scoring",
        "code": "proportion",
    }]
    assert measure["group"][0]["population"] == [
        {
            "id": "initial-population",
            "code": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/measure-population",
                "code": "initial-population",
            }]},
            "description": "Eligible patients.",
            "criteria": {"language": "text/cql-identifier", "expression": "Initial Population"},
        },
        {
            "id": "denominator",
            "code": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/measure-population",
                "code": "denominator",
            }]},
            "description": "All eligible patients.",
            "criteria": {"language": "text/cql-identifier", "expression": "Denominator"},
        },
        {
            "id": "numerator",
            "code": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/measure-population",
                "code": "numerator",
            }]},
            "description": "Eligible patients with a completed screen.",
            "criteria": {"language": "text/cql-identifier", "expression": "Numerator"},
        },
    ]


def test_measure_populations_require_authored_l2_definitions():
    with pytest.raises(ValueError, match=r"sections\.populations"):
        _build_measure_populations({"sections": {}})


@pytest.mark.parametrize("bad_coding", [
    "http://loinc.org|100257-5",
    {"system": "http://loinc.org"},
    {"system": "http://loinc.org", "code": "100257-5", "extra": "silently ignored?"},
    {"system": 1, "code": "100257-5"},
])
def test_questionnaire_item_rejects_malformed_coding(bad_coding):
    with pytest.raises(ValueError):
        _build_questionnaire_items("assessment", {"sections": {"items": [{
            "id": "question-1", "text": "Question?", "type": "boolean", "code": bad_coding,
        }]}})


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


def test_embed_cql_in_library_also_embeds_matching_elm_json(tmp_path):
    library_path = tmp_path / "Library-example-logic.json"
    library_path.write_text(json.dumps({
        "resourceType": "Library",
        "id": "example-logic",
        "name": "ExampleLogic",
        "content": [{"contentType": "text/plain", "data": "keep"}],
    }))
    (tmp_path / "ExampleLogic.cql").write_text("library ExampleLogic version '1.0.0'\n")
    elm_dir = tmp_path / "elm"
    elm_dir.mkdir()
    (elm_dir / "ExampleLogic.json").write_text(json.dumps({
        "library": {"identifier": {"id": "ExampleLogic", "version": "1.0.0"}},
    }))
    (tmp_path / "Library-other.json").write_text(json.dumps({
        "resourceType": "Library",
        "id": "other",
    }))

    assert _embed_cql_in_library(library_path, tmp_path) is True

    library = json.loads(library_path.read_text())
    content_types = [entry["contentType"] for entry in library["content"]]
    assert content_types == ["text/plain", "text/cql", "application/elm+json"]
    elm_entry = next(entry for entry in library["content"] if entry["contentType"] == "application/elm+json")
    decoded = json.loads(base64.b64decode(elm_entry["data"]).decode("utf-8"))
    assert decoded["library"]["identifier"]["id"] == "ExampleLogic"


def test_embed_cql_in_library_ignores_root_level_elm_json(tmp_path):
    library_path = tmp_path / "Library-example-logic.json"
    library_path.write_text(json.dumps({
        "resourceType": "Library",
        "id": "example-logic",
        "name": "ExampleLogic",
    }))
    (tmp_path / "ExampleLogic.cql").write_text("library ExampleLogic version '1.0.0'\n")
    (tmp_path / "ExampleLogic.json").write_text(json.dumps({
        "library": {"identifier": {"id": "ExampleLogic", "version": "1.0.0"}},
    }))

    assert _embed_cql_in_library(library_path, tmp_path) is True

    library = json.loads(library_path.read_text())
    content_types = [entry["contentType"] for entry in library["content"]]
    assert content_types == ["text/cql"]


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
    for action in decision_table["sections"]["actions"]:
        action["code"] = {
            "system": "http://snomed.info/sct",
            "code": "385763009",
            "display": "Clinical action",
        }
    care_pathway = {
        "artifact_type": "care-pathway",
        "name": "care-pathway",
        "sections": {
            "steps": [
                {
                    "id": "protocol",
                    "label": "Protocol",
                    "applicability_condition": "adult-age-criterion-met",
                    "applicability_conditions": ["guideline-exclusion-present"],
                },
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
    assert ("AdultAgeCriterionMet", "GuidelineExclusionPresent") in pathway_conditions["protocol"]
    assert ("NoGuidelineExclusionPresent",) in pathway_conditions["eligibility"]
    assert (
        "CrsDiagnosisVerified",
        "NoGuidelineExclusionPresent",
        "SinusSurgeryPlanningActive",
    ) in pathway_conditions["planning"]
    assert any(
        "SinusSurgeryOrderPresent" in conditions
        for conditions in pathway_conditions["educate-step"]
    )
    assert ("CrsDiagnosisVerified",) in pathway_conditions["candidacy"]

    eligibility_plan = next(
        resource for resource in pathway_resources
        if resource.get("resourceType") == "PlanDefinition"
        and str(resource.get("id") or "").endswith("-protocol-eligibility")
    )
    eligibility_child_conditions = [
        set(condition["expression"]["expression"] for condition in action.get("condition") or [])
        for action in eligibility_plan.get("action") or []
    ]
    assert eligibility_child_conditions
    assert all(
        {"AdultAgeCriterionMet", "NoGuidelineExclusionPresent"} <= conditions
        for conditions in eligibility_child_conditions
    ), "Standalone pathway branches must retain all ancestor applicability conditions"

    education_plan = next(
        resource for resource in pathway_resources
        if resource.get("resourceType") == "PlanDefinition"
        and str(resource.get("id") or "").endswith("-protocol-educate-step")
    )
    education_conditions = set(
        condition["expression"]["expression"]
        for action in education_plan.get("action") or []
        for condition in action.get("condition") or []
    )
    assert {
        "AdultAgeCriterionMet",
        "CrsDiagnosisVerified",
        "NoGuidelineExclusionPresent",
        "SinusSurgeryPlanningActive",
        "SinusSurgeryOrderPresent",
    } <= education_conditions, "Standalone leaf branches must retain all ancestor and local gates"

    decision_conditions = _condition_expressions_by_action_id(decision_resources)
    decision_root = next(
        resource for resource in decision_resources
        if resource.get("resourceType") == "PlanDefinition"
        and str(resource.get("id") or "").endswith("-recommendation")
    )
    assert all(action.get("condition") for action in decision_root.get("action") or []), (
        "Root decision-table PlanDefinition links must retain the same gates as child plans"
    )
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified", "NoGuidelineExclusionPresent"} <= set(entry)
               for entry in decision_conditions["verify-diagnosis"])
    assert any({"AdultAgeCriterionMet", "NoGuidelineExclusionPresent"} <= set(entry)
               for entry in decision_conditions["collect-snot"])
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified", "NoGuidelineExclusionPresent",
                "SinusSurgeryPlanningActive", "NoFineCutCtAvailable"} <= set(entry)
               for entry in decision_conditions["obtain-ct"])
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified", "NoGuidelineExclusionPresent",
                "SinusSurgeryPlanningActive", "SinusSurgeryOrderPresent"} <= set(entry)
               for entry in decision_conditions["educate-postop"])
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified"} <= set(entry)
               for entry in decision_conditions["assess-candidacy"])
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified"} <= set(entry)
               for entry in decision_conditions["avoid-fixed-therapy"])
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified", "CrsSubtypeLikelyToBenefitFromSurgery"} <= set(entry)
               for entry in decision_conditions["identify-subtype"])
    assert any({"AdultAgeCriterionMet", "CrsDiagnosisVerified", "SurgicalCandidacyEstablished"} <= set(entry)
               for entry in decision_conditions["offer-surgery"])


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
      code: {{system: http://snomed.info/sct, code: '306206005', display: Refer to specialist}}
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

    def test_force_regeneration_removes_only_orphaned_decision_table_children(self, tmp_repo):
        topic = "bells-palsy"
        artifact = "management-decision"
        topic_dir = tmp_repo / "topics" / topic
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)
        self._make_root_tracking_yaml(tmp_repo, topic, artifact, "decision-table")
        self._make_decision_table_artifact(
            structured_dir,
            artifact,
            [{"id": "c1", "label": "Facial weakness present"}],
        )
        _make_formalize_config(topic_dir, topic)
        stale_plan = {
            "resourceType": "PlanDefinition",
            "id": "management-decision-negative",
            "url": "http://example.org/fhir/PlanDefinition/management-decision-negative",
            "action": [{
                "definitionCanonical": "http://example.org/fhir/ActivityDefinition/old-action",
            }],
        }
        (computable_dir / "PlanDefinition-management-decision-negative.json").write_text(
            json.dumps(stale_plan)
        )
        (computable_dir / "ActivityDefinition-old-action.json").write_text(json.dumps({
            "resourceType": "ActivityDefinition",
            "id": "old-action",
            "url": "http://example.org/fhir/ActivityDefinition/old-action",
        }))

        result = CliRunner().invoke(
            formalize,
            [topic, artifact, "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        assert "Removed stale PlanDefinition-management-decision-negative.json" in result.output
        assert not (computable_dir / "PlanDefinition-management-decision-negative.json").exists()
        assert not (computable_dir / "ActivityDefinition-old-action.json").exists()

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
      code: {system: http://loinc.org, code: 44261-6, display: Assessment outcomes}
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
      code: {system: http://loinc.org, code: 44261-6, display: Assessment outcomes}
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
      code: {system: 'http://www.nlm.nih.gov/research/umls/rxnorm', code: '723', display: Amoxicillin}
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
