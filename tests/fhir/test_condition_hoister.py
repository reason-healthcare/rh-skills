"""Unit tests for ConditionHoister."""

import pytest
from rh_skills.fhir.builders.condition_hoister import ConditionHoister


def test_action_level_classification():
    """Test that single-rule conditions are classified as action-level."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    # Simple decision table with one condition used in one rule
    decision_table = {
        'sections': {
            'events': [
                {'id': 'e1', 'code': 'Operative Approach Selection'}
            ],
            'conditions': [
                {'id': 'extensive-disease', 'description': 'Extensive disease on CT'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'extensive-disease': True}, 'action': 'a1'}
            ]
        }
    }
    
    classifications = hoister.analyze_decision_table(decision_table)
    
    assert classifications['extensive-disease'] == 'action'


def test_recommendation_level_classification():
    """Test that multi-rule same-event conditions are classified as recommendation-level."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    # Decision table with one condition used in multiple rules for same event
    decision_table = {
        'sections': {
            'events': [
                {'id': 'e1', 'code': 'Operative Approach Selection'}
            ],
            'conditions': [
                {'id': 'has-ct-imaging', 'description': 'CT imaging completed'},
                {'id': 'extensive-disease', 'description': 'Extensive disease on CT'},
                {'id': 'limited-disease', 'description': 'Limited disease on CT'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'has-ct-imaging': True, 'extensive-disease': True}, 'action': 'a1'},
                {'id': 'r2', 'event': 'e1', 'when': {'has-ct-imaging': True, 'limited-disease': True}, 'action': 'a2'}
            ]
        }
    }
    
    classifications = hoister.analyze_decision_table(decision_table)
    
    # has-ct-imaging used in both rules for same event → recommendation-level
    assert classifications['has-ct-imaging'] == ('recommendation', 'e1')
    
    # extensive-disease and limited-disease each used in one rule → action-level
    assert classifications['extensive-disease'] == 'action'
    assert classifications['limited-disease'] == 'action'


def test_strategy_level_classification():
    """Test that multi-phase conditions are classified as strategy-level."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    # Decision table with pathway_phases and condition used across multiple phases
    decision_table = {
        'sections': {
            'pathway_phases': [
                {'id': 'planning', 'code': 'Surgical Planning'},
                {'id': 'operative', 'code': 'Operative Phase'}
            ],
            'events': [
                {'id': 'e1', 'code': 'Surgical Decision', 'phase': 'planning'},
                {'id': 'e2', 'code': 'Operative Approach', 'phase': 'operative'}
            ],
            'conditions': [
                {'id': 'failed-medical-therapy', 'description': 'Failed medical management'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'failed-medical-therapy': True}, 'action': 'a1'},
                {'id': 'r2', 'event': 'e2', 'when': {'failed-medical-therapy': True}, 'action': 'a2'}
            ]
        }
    }
    
    classifications = hoister.analyze_decision_table(decision_table)
    
    # failed-medical-therapy used in both planning and operative phases → strategy-level
    assert classifications['failed-medical-therapy'] == ('strategy', ['operative', 'planning'])


def test_pathway_context_classification():
    """Test that population-defining conditions are classified as pathway-context."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    # Decision table with has-crs-dx (matches topic pattern)
    decision_table = {
        'sections': {
            'events': [
                {'id': 'e1', 'code': 'Surgical Evaluation'}
            ],
            'conditions': [
                {'id': 'has-crs-dx', 'description': 'Diagnosis of chronic rhinosinusitis'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'has-crs-dx': True}, 'action': 'a1'}
            ]
        }
    }
    
    classifications = hoister.analyze_decision_table(decision_table)
    
    # has-crs-dx matches topic pattern (has-<topic>-dx) → pathway-context
    assert classifications['has-crs-dx'] == 'pathway-context'


def test_pathway_context_explicit_flag():
    """Test that explicit population_context flag is respected."""
    hoister = ConditionHoister('diabetes')
    
    # Decision table with explicit population_context flag
    decision_table = {
        'sections': {
            'events': [
                {'id': 'e1', 'code': 'Screening Decision'}
            ],
            'conditions': [
                {'id': 'adult-patient', 'description': 'Patient is adult', 'population_context': True}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'adult-patient': True}, 'action': 'a1'}
            ]
        }
    }
    
    classifications = hoister.analyze_decision_table(decision_table)
    
    # explicit flag overrides heuristics
    assert classifications['adult-patient'] == 'pathway-context'


def test_get_strategy_conditions():
    """Test extraction of strategy-level conditions for specific phase."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    decision_table = {
        'sections': {
            'pathway_phases': [
                {'id': 'planning', 'code': 'Surgical Planning'},
                {'id': 'operative', 'code': 'Operative Phase'}
            ],
            'events': [
                {'id': 'e1', 'code': 'Surgical Decision', 'phase': 'planning'},
                {'id': 'e2', 'code': 'Operative Approach', 'phase': 'operative'}
            ],
            'conditions': [
                {'id': 'failed-medical-therapy', 'description': 'Failed medical management'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'failed-medical-therapy': True}, 'action': 'a1'},
                {'id': 'r2', 'event': 'e2', 'when': {'failed-medical-therapy': True}, 'action': 'a2'}
            ]
        }
    }
    
    classifications = hoister.analyze_decision_table(decision_table)
    
    # Both phases should have failed-medical-therapy as condition
    planning_conditions = hoister.get_strategy_conditions(classifications, 'planning')
    operative_conditions = hoister.get_strategy_conditions(classifications, 'operative')
    
    assert 'failed-medical-therapy' in planning_conditions
    assert 'failed-medical-therapy' in operative_conditions


def test_hoisting_report_generation():
    """Test that hoisting report is generated correctly."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    decision_table = {
        'sections': {
            'pathway_phases': [
                {'id': 'planning', 'code': 'Surgical Planning'}
            ],
            'events': [
                {'id': 'e1', 'code': 'Surgical Decision', 'phase': 'planning'},
                {'id': 'e2', 'code': 'Operative Approach', 'phase': 'planning'}
            ],
            'conditions': [
                {'id': 'has-crs-dx', 'description': 'Diagnosis of CRS'},
                {'id': 'failed-medical-therapy', 'description': 'Failed medical management'},
                {'id': 'has-ct-imaging', 'description': 'CT imaging completed'},
                {'id': 'extensive-disease', 'description': 'Extensive disease on CT'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'has-crs-dx': True, 'failed-medical-therapy': True}, 'action': 'a1'},
                {'id': 'r2', 'event': 'e2', 'when': {'has-crs-dx': True, 'has-ct-imaging': True, 'extensive-disease': True}, 'action': 'a2'}
            ]
        }
    }
    
    report = hoister.generate_hoisting_report(decision_table)
    
    # Report should contain all classification types
    assert 'Pathway-Context' in report
    assert 'Strategy-Level' in report or 'Action-Level' in report or 'Recommendation-Level' in report
    assert 'Summary' in report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
