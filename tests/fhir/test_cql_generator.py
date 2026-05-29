#!/usr/bin/env python3
"""Tests for composite state generation in the CQL generator."""

from rh_skills.fhir.builders.cql_generator import CQLGenerator


def test_allows_diagnosis_confirmation_composite():
    """Diagnosis-confirmation pairs can become composite workflow states."""
    generator = CQLGenerator('chronic-rhinosinusitis')

    conditions = [
        {'id': 'has-crs-diagnosis', 'label': 'Patient has CRS diagnosis'},
        {'id': 'objective-findings-documented', 'label': 'Objective findings documented'},
    ]
    rules = [
        {
            'id': 'r1',
            'when': {
                'has-crs-diagnosis': 'true',
                'objective-findings-documented': 'true',
            },
        }
    ]

    states = generator._detect_composite_workflow_states(conditions, rules)

    assert states


def test_build_condition_definition_composes_from_data_elements():
    generator = CQLGenerator('chronic-rhinosinusitis')

    condition = {
        'id': 'established-crs-diagnostic-criteria-confirmed',
        'label': 'Established CRS diagnostic criteria confirmed',
        'data_elements': [
            {'id': 'de-qualifying-crs-symptoms', 'label': 'Qualifying CRS symptoms'},
            {'id': 'de-symptom-duration', 'label': 'Symptom duration of at least 12 weeks'},
            {'id': 'de-objective-inflammation-evidence', 'label': 'Objective sinonasal inflammation evidence'},
        ],
    }

    cql = generator._build_condition_definition(condition)

    assert 'define "QualifyingCrsSymptoms"' in cql
    assert 'define "SymptomDurationOfAtLeast12Weeks"' in cql
    assert 'define "ObjectiveSinonasalInflammationEvidence"' in cql
    assert 'define "EstablishedCrsDiagnosticCriteriaConfirmed"' in cql
    assert '"QualifyingCrsSymptoms" and "SymptomDurationOfAtLeast12Weeks" and "ObjectiveSinonasalInflammationEvidence"' in cql


def test_build_condition_definition_adds_specific_stub_guidance_by_feature_type():
    generator = CQLGenerator('chronic-rhinosinusitis')

    condition = {
        'id': 'surgical-candidacy-established',
        'label': 'Surgical candidacy established',
        'data_elements': [
            {
                'id': 'de-qol',
                'label': 'Quality of life burden score',
                'description': 'Validated quality of life instrument threshold',
                'data_type': 'patient-reported',
            },
            {
                'id': 'de-dx',
                'label': 'Active CRS diagnosis',
                'description': 'Confirmed active CRS diagnosis',
                'data_type': 'diagnosis',
            },
        ],
    }

    cql = generator._build_condition_definition(condition)

    assert 'specific questionnaire or patient-reported instrument' in cql
    assert 'explicit score/threshold' in cql
    assert 'active clinicalStatus' in cql
    assert 'exists([Observation] O)' in cql
    assert 'exists([Condition] C)' in cql
