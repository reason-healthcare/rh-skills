from __future__ import annotations

from pathlib import Path

import pytest

from rh_skills.cql_identity import (
    CqlLibraryIdentityError,
    apply_cql_namespace_extensions,
    parse_cql_context,
    subject_for_cql_context,
    validate_fhir_library_identity,
)


def _write_cql(tmp_path: Path, source: str, name: str = "ExampleLogic-1.0.0.cql") -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def _library(**overrides) -> dict:
    resource = {
        "resourceType": "Library",
        "id": "example-logic",
        "url": "https://example.org/fhir/Library/ExampleLogic",
        "name": "ExampleLogic",
        "version": "1.0.0",
        "subjectCodeableConcept": subject_for_cql_context("Patient"),
    }
    apply_cql_namespace_extensions(
        resource,
        namespace_name="reason.example",
        namespace_url="https://example.org/fhir",
    )
    resource.update(overrides)
    return resource


def test_matching_patient_context_identity_passes(tmp_path):
    cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\nusing FHIR version '4.0.1'\ncontext Patient\n",
    )

    assert validate_fhir_library_identity(
        _library(),
        namespace_name="reason.example",
        namespace_url="https://example.org/fhir",
        cql_path=cql,
    ) == []


def test_omitted_subject_defaults_only_to_patient(tmp_path):
    patient_cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\ncontext Patient\n",
    )
    patient_library = _library()
    patient_library.pop("subjectCodeableConcept")
    assert validate_fhir_library_identity(patient_library, cql_path=patient_cql) == []

    unfiltered_cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\ncontext Unfiltered\n",
    )
    with pytest.raises(CqlLibraryIdentityError, match="context 'Unfiltered'"):
        validate_fhir_library_identity(patient_library, cql_path=unfiltered_cql)


def test_unfiltered_context_uses_cql_context_code(tmp_path):
    cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\ncontext Unfiltered\n",
    )
    library = _library(subjectCodeableConcept=subject_for_cql_context("Unfiltered"))

    assert validate_fhir_library_identity(library, cql_path=cql) == []


def test_subject_context_matching_uses_coding_semantics_not_display_text(tmp_path):
    cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\ncontext Patient\n",
    )
    library = _library(subjectCodeableConcept={
        "coding": [{"system": "http://hl7.org/fhir/resource-types", "code": "Patient"}],
    })

    assert validate_fhir_library_identity(library, cql_path=cql) == []


def test_explicit_subject_reference_is_not_treated_as_omitted_patient_subject(tmp_path):
    cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\ncontext Patient\n",
    )
    library = _library(subjectReference={"reference": "Organization/not-a-patient"})
    library.pop("subjectCodeableConcept")

    with pytest.raises(CqlLibraryIdentityError, match="subjectReference"):
        validate_fhir_library_identity(library, cql_path=cql)


def test_namespace_extensions_must_match_ig_package_and_canonical(tmp_path):
    cql = _write_cql(tmp_path, "library ExampleLogic version '1.0.0'\n")
    library = _library()

    with pytest.raises(CqlLibraryIdentityError, match="namespace name"):
        validate_fhir_library_identity(
            library,
            namespace_name="reason.other",
            namespace_url="https://example.org/fhir",
            cql_path=cql,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"url": "https://example.org/fhir/Library/example-logic"}, "Library.url"),
        ({"name": "Example_Logic", "url": "https://example.org/fhir/Library/Example_Logic"}, "underscores"),
        ({"name": "A" * 65, "url": f"https://example.org/fhir/Library/{'A' * 65}"}, "maximum is 64"),
        ({"version": "2.0.0"}, "does not match CQL declaration"),
    ],
)
def test_identity_shall_constraints_fail(tmp_path, overrides, message):
    cql = _write_cql(tmp_path, "library ExampleLogic version '1.0.0'\ncontext Patient\n")

    with pytest.raises(CqlLibraryIdentityError, match=message):
        validate_fhir_library_identity(_library(**overrides), cql_path=cql)


def test_should_guidance_returns_warnings(tmp_path):
    long_name = "LongButStillValidLibraryName12345"
    cql = _write_cql(
        tmp_path,
        f"library {long_name} version '1.0.0'\ncontext Patient\n",
        name=f"{long_name}.cql",
    )
    library = _library(
        name=long_name,
        url=f"https://example.org/fhir/Library/{long_name}",
    )

    warnings = validate_fhir_library_identity(library, cql_path=cql)

    assert any("30 or fewer" in warning for warning in warnings)
    assert any(f"{long_name}-1.0.0.cql" in warning for warning in warnings)


def test_context_parser_ignores_comments_and_rejects_multiple_contexts(tmp_path):
    cql = _write_cql(
        tmp_path,
        "library ExampleLogic version '1.0.0'\n/* context Unfiltered */\n// context Device\ncontext Patient\n",
    )
    assert parse_cql_context(cql) == "Patient"

    cql.write_text(
        "library ExampleLogic version '1.0.0'\ncontext Patient\ncontext Unfiltered\n",
        encoding="utf-8",
    )
    with pytest.raises(CqlLibraryIdentityError, match="multiple contexts"):
        parse_cql_context(cql)
