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
            "type": {"coding": [{"code": "eca-rule"}]},
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
             "type": {"coding": [{"code": "eca-rule"}]},
             "action": [{"title": "x"}]},
            {"resourceType": "Measure", "id": "bad"},
        ])
        assert "PlanDefinition/ok" not in results
        assert "Measure/bad" in results
