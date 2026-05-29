#!/usr/bin/env python
"""Simple validation script for ConditionHoister."""

from rh_skills.fhir.builders.condition_hoister import ConditionHoister


def test_basic_functionality():
    """Test basic ConditionHoister functionality."""
    hoister = ConditionHoister('chronic-rhinosinusitis')
    
    # CRS-like decision table
    decision_table = {
        'sections': {
            'pathway_phases': [
                {'id': 'assessment', 'code': 'Assessment'},
                {'id': 'planning', 'code': 'Planning'},
                {'id': 'operative', 'code': 'Operative'}
            ],
            'events': [
                {'id': 'e1', 'code': 'Initial Evaluation', 'phase': 'assessment'},
                {'id': 'e2', 'code': 'Surgical Decision', 'phase': 'planning'},
                {'id': 'e3', 'code': 'Operative Approach', 'phase': 'operative'}
            ],
            'conditions': [
                {'id': 'has-crs-dx', 'description': 'Diagnosis of chronic rhinosinusitis'},
                {'id': 'failed-medical-therapy', 'description': 'Failed medical management'},
                {'id': 'has-ct-imaging', 'description': 'CT imaging completed'},
                {'id': 'extensive-disease', 'description': 'Extensive disease on CT'},
                {'id': 'limited-disease', 'description': 'Limited disease on CT'}
            ],
            'rules': [
                {'id': 'r1', 'event': 'e1', 'when': {'has-crs-dx': True}, 'action': 'a1'},
                {'id': 'r2a', 'event': 'e2', 'when': {'has-crs-dx': True, 'failed-medical-therapy': True}, 'action': 'a2a'},
                {'id': 'r2b', 'event': 'e2', 'when': {'has-crs-dx': True, 'failed-medical-therapy': False}, 'action': 'a2b'},
                {'id': 'r3a', 'event': 'e3', 'when': {'has-crs-dx': True, 'has-ct-imaging': True, 'extensive-disease': True}, 'action': 'a3a'},
                {'id': 'r3b', 'event': 'e3', 'when': {'has-crs-dx': True, 'has-ct-imaging': True, 'limited-disease': True}, 'action': 'a3b'}
            ]
        }
    }
    
    # Analyze
    classifications = hoister.analyze_decision_table(decision_table)
    
    print("# Condition Classification Results\n")
    
    print("has-crs-dx:", classifications.get('has-crs-dx'))
    assert classifications.get('has-crs-dx') == 'pathway-context', f"Expected pathway-context, got {classifications.get('has-crs-dx')}"
    print("  ✓ Correctly classified as pathway-context (matches has-<topic>-dx pattern)\n")

    print("failed-medical-therapy:", classifications.get('failed-medical-therapy'))
    # Used in planning phase only (e2), not across multiple phases
    # Since only used in e2 (which has planning phase), and used by multiple rules for that event
    expected = ('recommendation', 'e2')
    assert classifications.get('failed-medical-therapy') == expected, f"Expected {expected}, got {classifications.get('failed-medical-therapy')}"
    print("  ✓ Correctly classified as recommendation-level (used by multiple rules for event e2)\n")
    
    print("has-ct-imaging:", classifications.get('has-ct-imaging'))
    expected = ('recommendation', 'e3')
    assert classifications.get('has-ct-imaging') == expected, f"Expected {expected}, got {classifications.get('has-ct-imaging')}"
    print("  ✓ Correctly classified as recommendation-level (used by multiple rules for event e3)\n")
    
    print("extensive-disease:", classifications.get('extensive-disease'))
    assert classifications.get('extensive-disease') == 'action', f"Expected action, got {classifications.get('extensive-disease')}"
    print("  ✓ Correctly classified as action-level (used by single rule r3a)\n")
    
    print("limited-disease:", classifications.get('limited-disease'))
    assert classifications.get('limited-disease') == 'action', f"Expected action, got {classifications.get('limited-disease')}"
    print("  ✓ Correctly classified as action-level (used by single rule r3b)\n")
    
    # Test report generation
    print("="*60)
    print("\n")
    report = hoister.generate_hoisting_report(decision_table)
    print(report)
    print("\n")
    print("="*60)
    print("\n✅ All tests passed!")


if __name__ == '__main__':
    test_basic_functionality()
