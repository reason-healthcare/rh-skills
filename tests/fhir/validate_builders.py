#!/usr/bin/env python
"""Validation script for DecisionTableBuilder and CarePathwayBuilder."""

import json
from rh_skills.fhir.builders import (
    ConditionMerger,
    DecisionTableBuilder,
    CarePathwayBuilder
)


def test_decision_table_formalization():
    """Test DecisionTableBuilder with synthetic decision table."""
    print("# Testing Decision Table Formalization\n")
    
    # Synthetic decision table (diabetes screening example)
    decision_table = {
        'version': '1.0.0',
        'citation': 'Synthetic example for testing',
        'sections': {
            'events': [
                {
                    'id': 'screening-decision',
                    'code': 'Diabetes Screening Decision',
                    'description': 'Determine if patient should be screened for diabetes',
                    'phase': 'assessment'
                },
                {
                    'id': 'screening-method',
                    'code': 'Select Screening Method',
                    'description': 'Choose appropriate screening test',
                    'phase': 'testing'
                }
            ],
            'conditions': [
                {
                    'id': 'has-diabetes-dx',
                    'description': 'Diagnosis of diabetes',
                    'cql_stub': 'exists([Condition: "Diabetes mellitus"])'
                },
                {
                    'id': 'age-45-plus',
                    'description': 'Patient age 45 years or older',
                    'cql_stub': 'AgeInYears() >= 45'
                },
                {
                    'id': 'has-risk-factors',
                    'description': 'Has diabetes risk factors',
                    'cql_stub': 'HasDiabetesRiskFactors'
                },
                {
                    'id': 'fasting-feasible',
                    'description': 'Fasting blood glucose is feasible',
                    'cql_stub': 'PatientCanFast'
                }
            ],
            'actions': [
                {
                    'id': 'recommend-screening',
                    'code': 'Recommend Diabetes Screening',
                    'description': 'Recommend patient undergo diabetes screening',
                    'type': 'order'
                },
                {
                    'id': 'no-screening',
                    'code': 'No Screening Needed',
                    'description': 'Screening not indicated at this time',
                    'type': 'task'
                },
                {
                    'id': 'fasting-glucose',
                    'code': 'Order Fasting Blood Glucose',
                    'description': 'Order fasting blood glucose test',
                    'type': 'order'
                },
                {
                    'id': 'a1c-test',
                    'code': 'Order HbA1c Test',
                    'description': 'Order hemoglobin A1c test',
                    'type': 'order'
                }
            ],
            'rules': [
                {
                    'rule_id': 'r1',
                    'event': 'screening-decision',
                    'when': {'age-45-plus': True},
                    'then': ['recommend-screening'],
                    'rationale': 'Adults 45+ should be screened for diabetes',
                    'evidence': {'source_locator': 'ADA Guidelines 2024, Recommendation 2.1'}
                },
                {
                    'rule_id': 'r2',
                    'event': 'screening-decision',
                    'when': {'has-risk-factors': True},
                    'then': ['recommend-screening'],
                    'rationale': 'Adults with risk factors should be screened',
                    'evidence': {'source_locator': 'ADA Guidelines 2024, Recommendation 2.2'}
                },
                {
                    'rule_id': 'r3',
                    'event': 'screening-decision',
                    'when': {'age-45-plus': False, 'has-risk-factors': False},
                    'then': ['no-screening'],
                    'rationale': 'Low risk adults do not need routine screening',
                    'evidence': {'source_locator': 'ADA Guidelines 2024, Recommendation 2.3'}
                },
                {
                    'rule_id': 'r4',
                    'event': 'screening-method',
                    'when': {'fasting-feasible': True},
                    'then': ['fasting-glucose'],
                    'rationale': 'Fasting glucose preferred when feasible',
                    'evidence': {'source_locator': 'ADA Guidelines 2024, Recommendation 2.4'}
                },
                {
                    'rule_id': 'r5',
                    'event': 'screening-method',
                    'when': {'fasting-feasible': False},
                    'then': ['a1c-test'],
                    'rationale': 'A1c is alternative when fasting not feasible',
                    'evidence': {'source_locator': 'ADA Guidelines 2024, Recommendation 2.5'}
                }
            ]
        }
    }
    
    # Create merger and builder
    merger = ConditionMerger('diabetes')
    builder = DecisionTableBuilder('diabetes', 'diabetes-screening', merger)
    
    # Build resources
    resources = builder.build_all_resources(decision_table)
    
    # Validate
    plan_definitions = resources['PlanDefinition']
    activity_definitions = resources['ActivityDefinition']
    
    print(f"✅ Generated {len(plan_definitions)} Recommendation PlanDefinitions")
    print(f"✅ Generated {len(activity_definitions)} ActivityDefinitions\n")
    
    # Check that we got one PlanDefinition per event
    assert len(plan_definitions) == 2, f"Expected 2 PlanDefinitions, got {len(plan_definitions)}"
    
    # Check that all PlanDefinitions are eca-rule type
    for pd in plan_definitions:
        assert pd['type']['coding'][0]['code'] == 'eca-rule', f"Expected eca-rule, got {pd['type']['coding'][0]['code']}"
        print(f"  - {pd['id']}: {pd['title']}")
        print(f"    Actions: {len(pd['action'])}")
        if pd.get('goal'):
            print(f"    Recommendation-level conditions: {len(pd['goal'][0]['condition'])}")
    
    print(f"\n✅ All {len(plan_definitions)} Recommendation PlanDefinitions have type eca-rule")
    print(f"✅ All {len(activity_definitions)} ActivityDefinitions generated")
    
    # Show one example PlanDefinition
    print("\n## Example: PlanDefinition for screening-decision\n")
    screening_pd = next(pd for pd in plan_definitions if 'screening-decision' in pd['id'])
    print(json.dumps(screening_pd, indent=2))
    
    return resources


def test_care_pathway_formalization():
    """Test CarePathwayBuilder with synthetic care pathway."""
    print("\n\n" + "="*80)
    print("# Testing Care Pathway Formalization\n")
    
    # Synthetic care pathway (diabetes screening workflow)
    care_pathway = {
        'metadata': {
            'version': '1.0.0',
            'title': 'Diabetes Screening Pathway',
            'description': 'Clinical pathway for diabetes screening in adults',
            'auto_generated': False
        },
        'sections': {
            'steps': [
                {
                    'id': 'assessment',
                    'code': 'Risk Assessment',
                    'description': 'Assess patient diabetes risk factors',
                    'substeps': [
                        {
                            'id': 'screening-decision',
                            'code': 'Screening Decision',
                            'event_ref': 'screening-decision'
                        }
                    ]
                },
                {
                    'id': 'testing',
                    'code': 'Laboratory Testing',
                    'description': 'Perform diabetes screening tests',
                    'substeps': [
                        {
                            'id': 'screening-method',
                            'code': 'Select Screening Method',
                            'event_ref': 'screening-method'
                        }
                    ]
                }
            ]
        }
    }
    
    # Create builder
    builder = CarePathwayBuilder('diabetes', 'diabetes-screening-pathway', 'diabetes-screening')
    
    # Build resources
    resources = builder.build_all_resources(care_pathway)
    
    # Validate
    plan_definitions = resources['PlanDefinition']
    
    print(f"✅ Generated {len(plan_definitions)} PlanDefinitions total\n")
    
    # Should be 1 Pathway + 2 Strategies
    pathway_pds = [pd for pd in plan_definitions if pd['type']['coding'][0]['code'] == 'clinical-protocol']
    strategy_pds = [pd for pd in plan_definitions if pd['type']['coding'][0]['code'] == 'event-driven']
    
    print(f"  - Pathway PlanDefinitions: {len(pathway_pds)}")
    print(f"  - Strategy PlanDefinitions: {len(strategy_pds)}\n")
    
    assert len(pathway_pds) == 1, f"Expected 1 Pathway, got {len(pathway_pds)}"
    assert len(strategy_pds) == 2, f"Expected 2 Strategies, got {len(strategy_pds)}"
    
    pathway = pathway_pds[0]
    print(f"## Pathway PlanDefinition: {pathway['title']}")
    print(f"   - ID: {pathway['id']}")
    print(f"   - Type: {pathway['type']['coding'][0]['code']}")
    print(f"   - Actions (phases): {len(pathway['action'])}\n")
    
    for strategy in strategy_pds:
        print(f"## Strategy PlanDefinition: {strategy['title']}")
        print(f"   - ID: {strategy['id']}")
        print(f"   - Type: {strategy['type']['coding'][0]['code']}")
        print(f"   - Actions (recommendations): {len(strategy['action'])}\n")
    
    print("✅ Pathway → Strategy hierarchy validated")
    
    # Show pathway structure
    print("\n## Example: Pathway PlanDefinition\n")
    print(json.dumps(pathway, indent=2))
    
    return resources


def test_condition_merging():
    """Test ConditionMerger with multiple decision tables."""
    print("\n\n" + "="*80)
    print("# Testing Condition Merging Across Decision Tables\n")
    
    merger = ConditionMerger('diabetes')
    
    # Decision table 1: Screening
    screening_conditions = [
        {'id': 'has-diabetes-dx', 'description': 'Diagnosis of diabetes'},
        {'id': 'age-45-plus', 'description': 'Patient age 45 or older'},
        {'id': 'has-risk-factors', 'description': 'Has diabetes risk factors'}
    ]
    
    # Decision table 2: Treatment
    treatment_conditions = [
        {'id': 'has-diabetes-dx', 'description': 'Diagnosis of diabetes'},  # Shared!
        {'id': 'a1c-above-7', 'description': 'HbA1c above 7%'},
        {'id': 'on-metformin', 'description': 'Currently on metformin'}
    ]
    
    # Register both
    merger.register_conditions('diabetes-screening', screening_conditions)
    merger.register_conditions('diabetes-treatment', treatment_conditions)
    
    # Check merging
    merged = merger.get_merged_conditions()
    shared = merger.get_shared_conditions()
    
    print(f"Total unique conditions: {len(merged)}")
    print(f"Shared conditions: {len(shared)}\n")
    
    print("## Shared Conditions:")
    for cond in shared:
        sources = merger.get_condition_sources(cond['id'])
        print(f"  - {cond['id']}: used by {', '.join(sources)}\n")
    
    assert len(merged) == 5, f"Expected 5 unique conditions, got {len(merged)}"
    assert len(shared) == 1, f"Expected 1 shared condition, got {len(shared)}"
    
    print("✅ Condition merging working correctly")
    
    # Show report
    print("\n" + merger.generate_merge_report())
    
    return merger


if __name__ == '__main__':
    print("="*80)
    print("FHIR Builder Validation Suite")
    print("="*80 + "\n")
    
    test_condition_merging()
    test_decision_table_formalization()
    test_care_pathway_formalization()
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED")
    print("="*80)
