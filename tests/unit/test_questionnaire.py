"""Coded clinical assessments retain the observation and answer identities."""

from copy import deepcopy

import pytest

from rh_skills.commands.formalize import _build_questionnaire_resource
from rh_skills.validators.questionnaire import (
    SDC_OBSERVATION_CATEGORY_EXTENSION,
    questionnaire_metadata_fields,
    validate_observation_extraction_items,
)


@pytest.fixture
def clinical_assessment():
    return {
        "title": "Diagnostic result review",
        "sections": {
            "instrument": {
                "id": "diagnostic-result-review",
                "version_algorithm": {
                    "system": "http://hl7.org/fhir/version-algorithm",
                    "code": "semver",
                },
                "observation_extraction": {
                    "profile": "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0",
                    "enabled": True,
                    "category": {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "exam",
                        "display": "Exam",
                    },
                },
            },
            "items": [{
                "id": "lab-result",
                "text": "Review the documented diagnostic result",
                "type": "choice",
                "required": True,
                "code": {
                    "system": "https://example.org/test-observables",
                    "version": "1.0",
                    "code": "diagnostic-result",
                    "display": "Diagnostic result",
                },
                "options": [
                    {"valueCoding": {
                        "system": "https://example.org/test-answers",
                        "version": "1.0",
                        "code": code,
                        "display": display,
                    }}
                    for code, display in [("positive", "Positive"), ("negative", "Negative")]
                ],
                "observation_extraction": {"category": {
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory",
                }},
            }],
        },
    }


def build(assessment):
    return _build_questionnaire_resource(
        "diagnostic-review", "assessment", assessment,
        {"canonical": "https://example.org/fhir", "version": "1.0.0", "status": "draft"},
    )


@pytest.mark.parametrize("item_type", ["choice", "ordinal", "likert"])
def test_diagnostic_assessment_preserves_coded_answers_and_item_category(clinical_assessment, item_type):
    source = clinical_assessment["sections"]["items"][0]
    source["type"] = item_type
    expected = deepcopy(clinical_assessment)

    questionnaire = build(clinical_assessment)

    assert questionnaire["resourceType"] == "Questionnaire"
    assert questionnaire["item"][0]["type"] == "choice"
    assert questionnaire["item"][0]["code"] == [source["code"]]
    assert questionnaire["item"][0]["answerOption"] == source["options"]
    assert questionnaire["item"][0]["extension"] == [{
        "url": SDC_OBSERVATION_CATEGORY_EXTENSION,
        "valueCodeableConcept": {"coding": [source["observation_extraction"]["category"]]},
    }]
    root_category = next(
        ext["valueCodeableConcept"]["coding"][0]
        for ext in questionnaire["extension"] if ext["url"] == SDC_OBSERVATION_CATEGORY_EXTENSION
    )
    assert root_category["code"] == "exam"
    assert clinical_assessment == expected


@pytest.mark.parametrize("field", ["system", "code", "display"])
def test_extraction_rejects_incomplete_answer_coding(clinical_assessment, field):
    del clinical_assessment["sections"]["items"][0]["options"][0]["valueCoding"][field]
    with pytest.raises(ValueError, match=field):
        build(clinical_assessment)


def test_answer_version_is_omitted_when_not_authored(clinical_assessment):
    options = clinical_assessment["sections"]["items"][0]["options"]
    for option in options:
        del option["valueCoding"]["version"]
    questionnaire = build(clinical_assessment)
    assert questionnaire["item"][0]["answerOption"] == options


@pytest.mark.parametrize("options", [
    [],
    [{"value": "positive", "label": "Positive"}],
    [{"valueCoding": {"system": "urn:test", "code": "positive"}, "label": "Positive"}],
])
def test_extraction_rejects_uncoded_or_ambiguous_answer_options(clinical_assessment, options):
    clinical_assessment["sections"]["items"][0]["options"] = options
    with pytest.raises(ValueError, match="options|option fields"):
        build(clinical_assessment)


def test_extraction_rejects_duplicate_answer_identity(clinical_assessment):
    options = clinical_assessment["sections"]["items"][0]["options"]
    options.append(deepcopy(options[0]))
    with pytest.raises(ValueError, match="duplicate answer Coding"):
        build(clinical_assessment)


def test_item_category_requires_enabled_instrument_extraction(clinical_assessment):
    clinical_assessment["sections"]["instrument"]["observation_extraction"]["enabled"] = False
    with pytest.raises(ValueError, match="requires enabled instrument"):
        build(clinical_assessment)


def test_l2_validation_checks_item_category(clinical_assessment):
    sections = clinical_assessment["sections"]
    _, config = questionnaire_metadata_fields(sections["instrument"])
    del sections["items"][0]["observation_extraction"]["category"]["code"]
    with pytest.raises(ValueError, match="category requires non-empty"):
        validate_observation_extraction_items(sections["items"], config)


def test_ordinary_assessment_still_emits_coded_questionnaire_without_extraction(clinical_assessment):
    sections = clinical_assessment["sections"]
    del sections["instrument"]["observation_extraction"]
    del sections["items"][0]["observation_extraction"]
    questionnaire = build(clinical_assessment)
    assert questionnaire["item"][0]["answerOption"] == sections["items"][0]["options"]
    assert "meta" not in questionnaire


def test_unsupported_extraction_type_is_explicit_capability_error(clinical_assessment):
    clinical_assessment["sections"]["items"][0]["type"] = "quantity"
    with pytest.raises(ValueError, match="unsupported response type 'quantity'"):
        build(clinical_assessment)
