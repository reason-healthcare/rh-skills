from rh_skills.fhir.builders import CarePathwayBuilder, ConditionMerger, DecisionTableBuilder


def _extension_code(action):
    for ext in action.get("extension", []):
        if ext.get("url") == "http://hl7.org/fhir/StructureDefinition/cqf-strengthOfRecommendation":
            coding = ext.get("valueCodeableConcept", {}).get("coding", [])
            if coding:
                return coding[0].get("code")
    return None


def _documentation_text(action):
    docs = action.get("documentation", [])
    return " ".join(str(doc.get("citation", "")) for doc in docs if isinstance(doc, dict))


def test_decision_table_builder_carries_evidence_and_strength():
    decision_table = {
        "version": "1.0.0",
        "citation": "Decision table citation",
        "sections": {
            "evidence_traceability": [
                {
                    "claim_id": "claim-001",
                    "statement": "Guideline evidence statement",
                    "evidence": [{"source": "Guideline A", "locator": "p. 12"}],
                }
            ],
            "events": [{"id": "event-1", "label": "Event 1", "description": "Decision point"}],
            "conditions": [{"id": "cond-1", "description": "Condition 1"}],
            "actions": [{"id": "act-1", "code": "Act 1", "description": "Action 1", "type": "order"}],
            "rules": [
                {
                    "id": "rule-1",
                    "event": "event-1",
                    "then": ["act-1"],
                    "evidence_traceability_ids": ["claim-001"],
                    "recommendation_strength": "strong",
                }
            ],
        },
    }

    builder = DecisionTableBuilder("topic", "artifact", ConditionMerger("topic"))
    result = builder.build_all_resources(decision_table)
    plan_definition = result["PlanDefinition"][0]
    action = plan_definition["action"][0]

    assert _extension_code(action) == "strong"
    assert "Guideline evidence statement" in _documentation_text(action)
    assert "Guideline A: p. 12" in _documentation_text(action)
    assert any(
        doc.get("type") == "documentation" and "Guideline evidence statement" in doc.get("citation", "")
        for doc in plan_definition.get("relatedArtifact", [])
    )


def test_care_pathway_builder_carries_evidence_without_strength_extension():
    care_pathway = {
        "metadata": {
            "version": "1.0.0",
            "title": "Care Pathway",
            "description": "Pathway description",
        },
        "sections": {
            "steps": [
                {
                    "id": "phase-1",
                    "label": "Phase 1",
                    "description": "First phase",
                    "evidence_traceability_ids": ["path-claim-001"],
                    "recommendation_strength": "weak",
                }
            ]
        },
    }
    decision_table = {
        "version": "1.0.0",
        "sections": {
            "evidence_traceability": [
                {
                    "claim_id": "rule-claim-001",
                    "statement": "Decision rule evidence",
                    "evidence": [{"source": "Guideline B", "locator": "section 3"}],
                }
            ],
            "events": [
                {"id": "event-1", "label": "Event 1", "description": "Decision event", "phase": "phase-1"}
            ],
            "conditions": [{"id": "cond-1", "description": "Condition 1"}],
            "actions": [{"id": "act-1", "code": "Act 1", "description": "Action 1", "type": "order"}],
            "rules": [
                {
                    "id": "rule-1",
                    "event": "event-1",
                    "phase": "phase-1",
                    "then": ["act-1"],
                    "evidence_traceability_ids": ["rule-claim-001"],
                    "recommendation_strength": "strong",
                }
            ],
        },
    }

    builder = CarePathwayBuilder("topic", "pathway", "decision-table")
    result = builder.build_all_resources(care_pathway, decision_table, generate_strategies=True)
    plan_definitions = result["PlanDefinition"]
    pathway_pd = next(pd for pd in plan_definitions if pd["type"]["coding"][0]["code"] == "clinical-protocol")
    strategy_pd = next(pd for pd in plan_definitions if pd["type"]["coding"][0]["code"] == "workflow-definition")

    pathway_action = pathway_pd["action"][0]
    strategy_action = strategy_pd["action"][0]

    assert _extension_code(pathway_action) is None
    assert "Decision rule evidence" in _documentation_text(pathway_action)
    assert _extension_code(strategy_action) is None
    assert "Decision rule evidence" in _documentation_text(strategy_action)
    assert "Guideline B: section 3" in _documentation_text(strategy_action)
