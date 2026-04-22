"""Tests for FHIR structural validation."""

from rh_skills.fhir.validate import validate_resource, validate_resources


class TestValidateResourceBasics:
    def test_missing_resource_type(self):
        errors = validate_resource({"id": "test"})
        assert any("Missing resourceType" in e for e in errors)

    def test_missing_id(self):
        errors = validate_resource({"resourceType": "PlanDefinition"})
        assert any("Missing id" in e for e in errors)

    def test_valid_minimal_resource(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "type": {"coding": [{"code": "clinical-protocol"}]},
            "action": [{"title": "Step 1"}],
        })
        assert errors == []


class TestPlanDefinitionValidation:
    def test_missing_type(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "action": [{"title": "Step 1"}],
        })
        assert any("PlanDefinition.type" in e for e in errors)

    def test_missing_action(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "type": {"coding": [{"code": "eca-rule"}]},
        })
        assert any("PlanDefinition.action[]" in e for e in errors)

    def test_action_not_a_list_emits_clear_error(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "type": {"coding": [{"code": "eca-rule"}]},
            "action": {"title": "not-a-list"},
        })
        assert any("PlanDefinition.action must be an array" in e for e in errors)
        # Should not produce confusing key-iteration errors
        assert not any("must be an object" in e for e in errors)

    def test_eca_rule_requires_condition_kind_and_expression(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "type": {"coding": [{"code": "eca-rule"}]},
            "action": [{"title": "Step 1"}],
        })
        assert any("missing condition" in e.lower() for e in errors)

    def test_eca_rule_requires_library_for_cql_conditions(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "type": {"coding": [{"code": "eca-rule"}]},
            "action": [{
                "title": "Step 1",
                "condition": [{
                    "kind": "applicability",
                    "expression": {
                        "language": "text/cql",
                        "expression": "InitialEligibility",
                    },
                }],
            }],
        })
        assert any("PlanDefinition.library[]" in e for e in errors)

    def test_valid_eca_rule_with_cql_library(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "test",
            "type": {"coding": [{"code": "eca-rule"}]},
            "library": ["http://example.org/fhir/Library/test-library"],
            "action": [{
                "title": "Step 1",
                "condition": [{
                    "kind": "applicability",
                    "expression": {
                        "language": "text/cql",
                        "expression": "InitialEligibility",
                    },
                }],
            }],
        })
        assert errors == []


class TestMeasureValidation:
    def test_missing_group(self):
        errors = validate_resource({
            "resourceType": "Measure",
            "id": "test",
            "scoring": {"coding": [{"code": "proportion"}]},
        })
        assert any("Measure.group[]" in e for e in errors)

    def test_missing_denominator(self):
        errors = validate_resource({
            "resourceType": "Measure",
            "id": "test",
            "scoring": {"coding": [{"code": "proportion"}]},
            "group": [{
                "population": [{
                    "code": {"coding": [{"code": "numerator"}]},
                    "criteria": {"expression": "Numerator"},
                }],
            }],
        })
        assert any("denominator" in e for e in errors)

    def test_missing_scoring(self):
        errors = validate_resource({
            "resourceType": "Measure",
            "id": "test",
            "group": [{
                "population": [
                    {"code": {"coding": [{"code": "numerator"}]}, "criteria": {"expression": "Num"}},
                    {"code": {"coding": [{"code": "denominator"}]}, "criteria": {"expression": "Den"}},
                ],
            }],
        })
        assert any("Measure.scoring" in e for e in errors)

    def test_valid_measure(self):
        errors = validate_resource({
            "resourceType": "Measure",
            "id": "test",
            "scoring": {"coding": [{"code": "proportion"}]},
            "group": [{
                "population": [
                    {"code": {"coding": [{"code": "numerator"}]}, "criteria": {"expression": "Num"}},
                    {"code": {"coding": [{"code": "denominator"}]}, "criteria": {"expression": "Den"}},
                ],
            }],
        })
        assert errors == []


class TestQuestionnaireValidation:
    def test_missing_item(self):
        errors = validate_resource({
            "resourceType": "Questionnaire",
            "id": "test",
        })
        assert any("Questionnaire.item[]" in e for e in errors)

    def test_missing_link_id(self):
        errors = validate_resource({
            "resourceType": "Questionnaire",
            "id": "test",
            "item": [{"text": "Question 1"}],
        })
        assert any("linkId" in e for e in errors)

    def test_valid_questionnaire(self):
        errors = validate_resource({
            "resourceType": "Questionnaire",
            "id": "test",
            "item": [{"linkId": "q1", "text": "Question 1", "type": "choice"}],
        })
        assert errors == []


class TestValueSetValidation:
    def test_empty_compose(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "test",
        })
        assert any("ValueSet.compose.include[]" in e for e in errors)

    def test_valid_value_set(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "test",
            "compose": {
                "include": [{"system": "http://snomed.info/sct", "concept": [{"code": "123"}]}],
            },
        })
        assert errors == []


class TestEvidenceValidation:
    def test_missing_certainty(self):
        errors = validate_resource({
            "resourceType": "Evidence",
            "id": "test",
        })
        assert any("Evidence.certainty[]" in e for e in errors)


class TestMcpUnreachable:
    def test_detects_placeholder(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "test",
            "compose": {
                "include": [{
                    "system": "http://snomed.info/sct",
                    "concept": [{"code": "TODO:MCP-UNREACHABLE", "display": "Unknown"}],
                }],
            },
        })
        assert any("MCP-UNREACHABLE" in e for e in errors)

    def test_no_false_positive(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "test",
            "compose": {
                "include": [{"system": "http://snomed.info/sct", "concept": [{"code": "12345"}]}],
            },
        })
        assert not any("MCP-UNREACHABLE" in e for e in errors)


class TestValidateResources:
    def test_multiple_resources(self):
        results = validate_resources([
            {"resourceType": "PlanDefinition", "id": "ok",
             "type": {"coding": [{"code": "clinical-protocol"}]},
             "action": [{"title": "x"}]},
            {"resourceType": "Measure", "id": "bad"},
        ])
        assert "PlanDefinition/ok" not in results
        assert "Measure/bad" in results


class TestNegativeVerifyCases:
    """T037: Negative verification test cases — each tests a type-specific
    structural error that generic checks would miss."""

    def test_measure_missing_denominator(self):
        errors = validate_resource({
            "resourceType": "Measure",
            "id": "cms122",
            "scoring": {"coding": [{"code": "proportion"}]},
            "group": [{
                "population": [
                    {"code": {"coding": [{"code": "numerator"}]}, "criteria": {"expression": "x"}},
                ],
            }],
        })
        assert any("denominator" in e.lower() for e in errors)

    def test_measure_missing_numerator(self):
        errors = validate_resource({
            "resourceType": "Measure",
            "id": "cms122",
            "scoring": {"coding": [{"code": "proportion"}]},
            "group": [{
                "population": [
                    {"code": {"coding": [{"code": "denominator"}]}, "criteria": {"expression": "x"}},
                ],
            }],
        })
        assert any("numerator" in e.lower() for e in errors)

    def test_questionnaire_missing_linkid(self):
        errors = validate_resource({
            "resourceType": "Questionnaire",
            "id": "phq9",
            "item": [
                {"text": "Question 1"},
                {"linkId": "q2", "text": "Question 2"},
            ],
        })
        assert any("linkId" in e for e in errors)

    def test_plandefinition_missing_action(self):
        errors = validate_resource({
            "resourceType": "PlanDefinition",
            "id": "sepsis",
            "type": {"coding": [{"code": "eca-rule"}]},
        })
        assert any("action" in e.lower() for e in errors)

    def test_valueset_empty_compose(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "diabetes-dx",
            "compose": {"include": []},
        })
        assert any("compose.include" in e for e in errors)

    def test_valueset_no_compose(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "diabetes-dx",
        })
        assert any("compose.include" in e for e in errors)

    def test_evidence_missing_certainty(self):
        errors = validate_resource({
            "resourceType": "Evidence",
            "id": "copd-evidence",
            "description": "COPD evidence synthesis",
        })
        assert any("certainty" in e.lower() for e in errors)

    def test_evidence_variable_missing_characteristic(self):
        errors = validate_resource({
            "resourceType": "EvidenceVariable",
            "id": "copd-population",
            "description": "Adults with COPD",
        })
        assert any("characteristic" in e.lower() for e in errors)

    def test_resource_with_mcp_unreachable(self):
        errors = validate_resource({
            "resourceType": "ValueSet",
            "id": "test-vs",
            "compose": {
                "include": [{
                    "system": "http://snomed.info/sct",
                    "concept": [{"code": "TODO:MCP-UNREACHABLE", "display": "Unknown concept"}],
                }],
            },
        })
        assert any("MCP-UNREACHABLE" in e for e in errors)

    def test_library_missing_type(self):
        errors = validate_resource({
            "resourceType": "Library",
            "id": "cql-lib",
        })
        assert any("type" in e.lower() for e in errors)

    def test_concept_map_missing_group(self):
        errors = validate_resource({
            "resourceType": "ConceptMap",
            "id": "dx-map",
        })
        assert any("group" in e.lower() for e in errors)

    def test_activity_definition_missing_kind(self):
        errors = validate_resource({
            "resourceType": "ActivityDefinition",
            "id": "med-admin",
        })
        assert any("kind" in e.lower() for e in errors)
