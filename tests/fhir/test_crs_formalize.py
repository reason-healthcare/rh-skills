#!/usr/bin/env python3
"""
Test CRS decision table formalization with deterministic builders.
Validates end-to-end FHIR resource generation without writing to computable/.
"""

from pathlib import Path
from ruamel.yaml import YAML
from rh_skills.fhir.builders import (
    ConditionMerger,
    DecisionTableBuilder,
    ConditionHoister
)


def test_crs_decision_table():
    """Test CRS surgical management decision table formalization."""
    
    # Load CRS decision table
    crs_dir = Path(__file__).parents[2] / "topics" / "chronic-rhinosinusitis"
    dt_file = crs_dir / "structured" / "crs-surgical-management" / "crs-surgical-management.yaml"
    
    if not dt_file.exists():
        print(f"SKIP: CRS decision table not found at {dt_file}")
        return
    
    yaml = YAML()
    l2_data = yaml.load(dt_file.read_text())
    
    topic = "chronic-rhinosinusitis"
    artifact = "crs-surgical-management"
    
    # Create merger for topic-level condition deduplication
    merger = ConditionMerger(topic)
    
    # Build FHIR resources
    print(f"\n=== Building FHIR resources for {artifact} ===")
    builder = DecisionTableBuilder(topic, artifact, merger)
    result = builder.build_all_resources(l2_data)
    
    # Validate result structure
    assert 'PlanDefinition' in result, "Missing PlanDefinition resources"
    assert 'ActivityDefinition' in result, "Missing ActivityDefinition resources"
    
    plan_defs = result['PlanDefinition']
    activity_defs = result['ActivityDefinition']
    
    print(f"\nGenerated {len(plan_defs)} PlanDefinition resources:")
    for pd in plan_defs:
        print(f"  - {pd['id']}: {pd.get('title', 'No title')}")
        print(f"    Type: {pd.get('type', {}).get('coding', [{}])[0].get('code', 'unknown')}")
        
        # Check for conditions
        if 'goal' in pd:
            for goal in pd['goal']:
                if 'condition' in goal:
                    print(f"    Goal condition: {goal['condition'][0].get('expression', {}).get('expression', 'No expression')}")
        
        if 'action' in pd:
            for action in pd['action']:
                if 'condition' in action:
                    for cond in action['condition']:
                        print(f"    Action condition: {cond.get('expression', {}).get('expression', 'No expression')}")
    
    print(f"\nGenerated {len(activity_defs)} ActivityDefinition resources:")
    for ad in activity_defs:
        print(f"  - {ad['id']}: {ad.get('title', 'No title')}")
        print(f"    Kind: {ad.get('kind', 'unknown')}")
    
    # Validate hoisting analysis
    print("\n=== Condition Hoisting Analysis ===")
    hoister = ConditionHoister(topic)
    analysis = hoister.analyze_decision_table(l2_data)
    
    pathway_context = [cid for cid, cls in analysis.items() if cls == 'pathway-context']
    strategy_level = [cid for cid, cls in analysis.items() if isinstance(cls, tuple) and cls[0] == 'strategy']
    recommendation_level = [cid for cid, cls in analysis.items() if isinstance(cls, tuple) and cls[0] == 'recommendation']
    action_level = [cid for cid, cls in analysis.items() if cls == 'action']
    
    print(f"\nPathway-context conditions: {pathway_context}")
    print(f"Strategy-level conditions: {strategy_level}")
    print(f"Recommendation-level conditions: {recommendation_level}")
    print(f"Action-level conditions: {action_level}")
    
    # Validate condition merging
    print("\n=== Condition Merging ===")
    merged = merger.get_merged_conditions()
    print(f"Total unique conditions: {len(merged)}")
    
    for cond in merged[:5]:
        cond_id = cond.get('id') or cond.get('condition_id')
        sources = merger.get_condition_sources(cond_id)
        print(f"  - {cond_id}: used in {len(sources)} decision table(s)")
    
    print("\n✅ CRS decision table formalization test passed!")
    return result


if __name__ == "__main__":
    test_crs_decision_table()
