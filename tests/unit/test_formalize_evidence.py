"""Tests for evidence traceability linking in L3 FHIR formalization."""

from rh_skills.commands.formalize import (
    _build_evidence_claim_index,
    _build_evidence_related_artifacts,
    _build_strength_of_recommendation_extension,
    _build_decision_table_rule_plan_actions,
)


class TestEvidenceTraceabilityArtifacts:
    """Test the evidence artifact helpers."""

    def test_build_related_artifacts_with_valid_ids(self):
        evidence_index = {
            "claim-001": {
                "claim_id": "claim-001",
                "statement": "Example evidence statement",
                "strength": "high",
                "evidence": [{"source": "source-a", "locator": "loc-1"}],
            }
        }

        artifacts = _build_evidence_related_artifacts(["claim-001"], evidence_index)

        assert len(artifacts) == 1
        assert artifacts[0]["type"] == "citation"
        assert artifacts[0]["label"] == "claim-001"
        assert "Example evidence statement" in artifacts[0]["citation"]
        assert "source-a: loc-1" in artifacts[0]["citation"]

    def test_build_related_artifacts_ignores_missing_ids(self):
        artifacts = _build_evidence_related_artifacts(["missing-claim"], {})
        assert artifacts == []

    def test_build_claim_index(self):
        l2_data = {
            "sections": {
                "evidence_traceability": [
                    {"claim_id": "claim-001", "statement": "Statement one", "strength": "high"},
                    {"claim_id": "claim-002", "statement": "Statement two", "strength": "moderate"},
                ]
            }
        }
        index = _build_evidence_claim_index(l2_data)
        assert set(index.keys()) == {"claim-001", "claim-002"}

    def test_build_strength_of_recommendation_extension(self):
        ext = _build_strength_of_recommendation_extension("strong")
        assert ext is not None
        assert ext["url"] == "http://hl7.org/fhir/StructureDefinition/cqf-strengthOfRecommendation"
        assert ext["valueCodeableConcept"]["coding"][0]["code"] == "strong"
        assert "display" not in ext["valueCodeableConcept"]["coding"][0]
        assert "text" not in ext["valueCodeableConcept"]

    def test_build_strength_of_recommendation_extension_rejects_unknown(self):
        assert _build_strength_of_recommendation_extension("maybe") is None
class TestPlanDefinitionRuleEvidenceLinks:
    """Test evidence linking in PlanDefinition rule actions."""

    def test_rule_plan_action_includes_evidence_documentation(self):
        """PlanDefinition rule actions should include evidence_traceability_ids as documentation."""
        rule = {
            "id": "test-rule",
            "event": "test-event",
            "then": ["action-1"],
            "evidence_traceability_ids": ["claim-001"],
        }
        event = {
            "id": "test-event",
            "label": "Test Event",
        }
        canonical = "http://example.org/fhir"
        action_index = {
            "action-1": {
                "id": "action-1",
                "label": "Action 1",
            }
        }
        condition_index = {}
        evidence_index = {
            "claim-001": {
                "claim_id": "claim-001",
                "statement": "Example evidence statement",
                "strength": "moderate",
            }
        }

        actions = _build_decision_table_rule_plan_actions(
            rule,
            event,
            canonical,
            action_index,
            condition_index,
            evidence_index,
            fallback_name="test-rule",
        )

        assert len(actions) > 0
        action = actions[0]
        assert "extension" not in action
        assert "documentation" in action
        assert any(
            doc.get("type") == "citation" and doc.get("label") == "claim-001"
            for doc in action["documentation"]
        )

    def test_rule_plan_action_without_evidence_ids(self):
        """PlanDefinition rule actions should not have evidence documentation if IDs not present."""
        rule = {
            "id": "test-rule",
            "event": "test-event",
            "then": ["action-1"],
        }
        event = {
            "id": "test-event",
            "label": "Test Event",
        }
        canonical = "http://example.org/fhir"
        action_index = {
            "action-1": {
                "id": "action-1",
                "label": "Action 1",
            }
        }
        condition_index = {}

        actions = _build_decision_table_rule_plan_actions(
            rule,
            event,
            canonical,
            action_index,
            condition_index,
            {},
            fallback_name="test-rule",
        )

        assert len(actions) > 0
        action = actions[0]
        evidence_docs = [
            doc for doc in action.get("documentation", [])
            if doc.get("type") == "citation"
        ]
        assert len(evidence_docs) == 0
