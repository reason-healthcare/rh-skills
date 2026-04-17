"""Tests for FHIR resource normalization."""

import re
from rh_skills.fhir.normalize import (
    to_kebab_case,
    to_pascal_case,
    canonical_url,
    iso_date_today,
    normalize_resource,
    ALLOWED_RESOURCE_TYPES,
)


class TestToKebabCase:
    def test_simple(self):
        assert to_kebab_case("Sepsis Bundle") == "sepsis-bundle"

    def test_already_kebab(self):
        assert to_kebab_case("sepsis-bundle") == "sepsis-bundle"

    def test_special_chars(self):
        assert to_kebab_case("PHQ-9 Depression!") == "phq-9-depression"

    def test_leading_trailing(self):
        assert to_kebab_case("--hello--") == "hello"

    def test_underscores(self):
        assert to_kebab_case("my_artifact_name") == "my-artifact-name"


class TestToPascalCase:
    def test_from_kebab(self):
        assert to_pascal_case("sepsis-bundle") == "SepsisBundle"

    def test_from_spaces(self):
        assert to_pascal_case("sepsis bundle logic") == "SepsisBundleLogic"

    def test_from_underscores(self):
        assert to_pascal_case("my_artifact") == "MyArtifact"


class TestCanonicalUrl:
    def test_pattern(self):
        url = canonical_url("PlanDefinition", "sepsis-bundle")
        assert url == "http://example.org/fhir/PlanDefinition/sepsis-bundle"


class TestIsoDateToday:
    def test_format(self):
        d = iso_date_today()
        assert re.match(r"\d{4}-\d{2}-\d{2}", d)


class TestNormalizeResource:
    def test_sets_defaults(self):
        r = normalize_resource({"resourceType": "PlanDefinition", "id": "My Test"})
        assert r["id"] == "my-test"
        assert r["version"] == "1.0.0"
        assert r["status"] == "draft"
        assert r["date"]
        assert r["url"] == "http://example.org/fhir/PlanDefinition/my-test"
        assert r["name"] == "MyTest"

    def test_preserves_existing_values(self):
        r = normalize_resource({
            "resourceType": "Measure",
            "id": "phq-9",
            "version": "2.0.0",
            "status": "active",
            "date": "2025-01-01",
            "url": "http://custom.org/fhir/Measure/phq-9",
        })
        assert r["version"] == "2.0.0"
        assert r["status"] == "active"
        assert r["date"] == "2025-01-01"
        assert r["url"] == "http://custom.org/fhir/Measure/phq-9"

    def test_unknown_resource_type_warns(self):
        r = normalize_resource({"resourceType": "FakeResource", "id": "test"})
        assert "_normalization_warnings" in r
        assert "Unknown resourceType" in r["_normalization_warnings"][0]

    def test_name_from_title(self):
        r = normalize_resource({
            "resourceType": "Evidence",
            "id": "test",
            "title": "Statin Therapy Evidence",
        })
        assert r["name"] == "StatinTherapyEvidence"

    def test_allowed_resource_types(self):
        expected = {
            "Evidence", "EvidenceVariable", "Citation", "PlanDefinition",
            "Library", "ActivityDefinition", "ValueSet", "ConceptMap",
            "Measure", "Questionnaire", "QuestionnaireResponse",
            "ImplementationGuide",
        }
        assert ALLOWED_RESOURCE_TYPES == expected
