"""Executable Bundle closure tests using FHIR R4 Library.content attachments."""

from __future__ import annotations

import base64
import json

import pytest

from rh_skills.commands.executable_bundle import (
    ExecutableBundleError,
    _validate_closure,
    compose_executable_bundle,
)


def _b64(value: str | dict) -> str:
    if isinstance(value, dict):
        value = json.dumps(value)
    return base64.b64encode(value.encode()).decode()


def _library(
    *,
    name: str = "Logic",
    version: str = "1.0.0",
    cql: str | None = 'library Logic version \'1.0.0\'\ndefine "Eligible": true\n',
    elm: dict | None = None,
) -> dict:
    if elm is None:
        elm = {
            "library": {
                "identifier": {"id": name, "version": version},
                "includes": {"def": []},
                "statements": {"def": [{"name": "Eligible"}]},
            },
        }
    content = []
    if cql is not None:
        content.append({"contentType": "text/cql", "data": _b64(cql)})
    if elm is not None:
        content.append({"contentType": "application/elm+json", "data": _b64(elm)})
    return {
        "resourceType": "Library",
        "id": "logic",
        "url": "https://example.org/fhir/Library/logic",
        "version": version,
        "name": name,
        "content": content,
    }


def _root(*, expression: str = "Eligible", version: str = "1.0.0") -> dict:
    return {
        "resourceType": "PlanDefinition",
        "id": "root",
        "url": "https://example.org/fhir/PlanDefinition/root",
        "version": version,
        "library": ["https://example.org/fhir/Library/logic|1.0.0"],
        "action": [{
            "condition": [{
                "expression": {"language": "text/cql-identifier", "expression": expression},
            }],
        }],
    }


def test_closure_reads_real_library_content_shape_and_cql_expression_names():
    library = _library()

    root = _validate_closure(
        [library, _root()],
        "https://example.org/fhir/PlanDefinition/root|1.0.0",
    )

    assert root["id"] == "root"


def test_closure_rejects_missing_elm_for_embedded_cql():
    library = _library(elm=None)
    library["content"] = [library["content"][0]]

    with pytest.raises(ExecutableBundleError, match=r"no compiled application/elm\+json"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_rejects_invalid_library_content_base64():
    library = _library()
    library["content"][1]["data"] = "not base64"

    with pytest.raises(ExecutableBundleError, match="invalid base64"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


@pytest.mark.parametrize("identity", [
    {"id": "Other", "version": "1.0.0"},
    {"id": "Logic", "version": "2.0.0"},
])
def test_closure_rejects_elm_identity_mismatch(identity):
    library = _library(elm={
        "library": {
            "identifier": identity,
            "includes": {"def": []},
            "statements": {"def": [{"name": "Eligible"}]},
        },
    })

    with pytest.raises(ExecutableBundleError, match="ELM identity"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_rejects_cql_identity_mismatch():
    library = _library(cql='library Logic version \'2.0.0\'\ndefine "Eligible": true\n')

    with pytest.raises(ExecutableBundleError, match="CQL identity"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_rejects_cql_definition_missing_from_compiled_elm():
    library = _library(elm={
        "library": {
            "identifier": {"id": "Logic", "version": "1.0.0"},
            "includes": {"def": []},
            "statements": {"def": [{"name": "Other"}]},
        },
    })

    with pytest.raises(ExecutableBundleError, match="compiled ELM is missing CQL definitions"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_rejects_cql_identifier_missing_from_linked_library():
    library = _library()

    with pytest.raises(ExecutableBundleError, match="PositiveScreen"):
        _validate_closure(
            [library, _root(expression="PositiveScreen")],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )


def test_closure_rejects_missing_library_from_elm_include():
    library = _library(elm={
        "library": {
            "identifier": {"id": "Logic", "version": "1.0.0"},
            "includes": {"def": [{"path": "MissingLibrary", "version": "1.0.0"}]},
            "statements": {"def": [{"name": "Eligible"}]},
        },
    })

    with pytest.raises(ExecutableBundleError, match=r"Unresolved ELM include dependency: MissingLibrary\|1.0.0"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_resolves_pinned_fhirhelpers_from_elm_include():
    logic = _library(elm={
        "library": {
            "identifier": {"id": "Logic", "version": "1.0.0"},
            "includes": {"def": [{"path": "FHIRHelpers", "version": "4.0.1"}]},
            "statements": {"def": [{"name": "Eligible"}]},
        },
    })
    helpers = _library(name="FHIRHelpers", version="4.0.1", cql=None)
    helpers["id"] = "fhirhelpers"
    helpers["url"] = "http://hl7.org/fhir/Library/FHIRHelpers"

    root = _validate_closure(
        [helpers, logic, _root()],
        "https://example.org/fhir/PlanDefinition/root|1.0.0",
    )

    assert root["id"] == "root"


def test_closure_rejects_unversioned_root_canonical():
    with pytest.raises(ExecutableBundleError, match=r"root canonical must include `\|version`"):
        _validate_closure(
            [_library(), _root()],
            "https://example.org/fhir/PlanDefinition/root",
        )


def test_closure_rejects_duplicate_canonical_and_version():
    duplicate = _library()
    duplicate["id"] = "logic-copy"

    with pytest.raises(ExecutableBundleError, match="Duplicate canonical and version"):
        _validate_closure(
            [_library(), duplicate, _root()],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )


def test_closure_rejects_incomplete_or_unpinned_valueset_expansion():
    value_set = {
        "resourceType": "ValueSet",
        "id": "screening-values",
        "url": "https://example.org/fhir/ValueSet/screening-values",
        "version": "1.0.0",
        "compose": {"include": [{"system": "http://snomed.info/sct"}]},
        "expansion": {"total": 2, "contains": [{"code": "1"}]},
    }

    with pytest.raises(ExecutableBundleError, match="not version-pinned"):
        _validate_closure(
            [_library(), _root(), value_set],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )

    value_set["compose"]["include"][0]["version"] = "20260901"
    with pytest.raises(ExecutableBundleError, match="expansion is incomplete"):
        _validate_closure(
            [_library(), _root(), value_set],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "example"}},
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "visit",
                    "subject": {"reference": "Patient/example"},
                }
            },
        ],
    }


def test_compose_writes_deterministic_locked_bundle_and_fixture_sidecars(tmp_path):
    computable = tmp_path / "computable"
    _write_json(computable / "library.json", _library())
    _write_json(computable / "root.json", _root())
    fixture_root = tmp_path / "fixtures"
    case_dir = fixture_root / "case-one"
    _write_json(case_dir / "bundle.json", _fixture_bundle())
    _write_json(
        case_dir / "assertions.json",
        {
            "evaluationContext": {
                "patientId": "example",
                "measurementPeriod": {
                    "start": "2026-01-01",
                    "end": "2026-12-31",
                    "startInclusive": True,
                    "endInclusive": True,
                },
            }
        },
    )
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, {"cases": [{"id": "case-one", "title": "Case one"}]})
    output = tmp_path / "executable"

    result = compose_executable_bundle(
        computable,
        manifest,
        fixture_root,
        output,
        "https://example.org/fhir/PlanDefinition/root|1.0.0",
        "2026-06-15T09:20:00Z",
    )

    fixture_index = json.loads(result["index"].read_text())
    executable_manifest = json.loads(result["manifest"].read_text())
    assert fixture_index["fixtures"] == [
        {
            "id": "case-one",
            "title": "Case one",
            "subject": "Patient/example",
            "dataBundlePath": "fixtures/case-one.json",
            "measurementPeriod": {
                "start": "2026-01-01",
                "end": "2026-12-31",
                "startInclusive": True,
                "endInclusive": True,
            },
            "evaluationDate": "2026-06-15T09:20:00Z",
            "encounter": "Encounter/visit",
        }
    ]
    assert json.loads((output / "fixtures" / "case-one.json").read_text()) == _fixture_bundle()
    assert executable_manifest["checksums"]["algorithm"] == "sha256"
    assert len(executable_manifest["checksums"]["rootResource"]) == 64


def test_compose_failure_preserves_existing_output(tmp_path):
    output = tmp_path / "executable"
    _write_json(output / "fixtures" / "old.json", {"preserved": True})
    computable = tmp_path / "computable"
    _write_json(computable / "library.json", _library())
    _write_json(computable / "root.json", _root())
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, {"cases": [{"id": "missing", "title": "Missing"}]})
    (tmp_path / "fixtures").mkdir()

    with pytest.raises(ExecutableBundleError, match="assertions.json and bundle.json"):
        compose_executable_bundle(
            computable,
            manifest,
            tmp_path / "fixtures",
            output,
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
            "2026-06-15T09:20:00Z",
        )

    assert json.loads((output / "fixtures" / "old.json").read_text()) == {"preserved": True}


def test_compose_rejects_malformed_encounter_participant(tmp_path):
    computable = tmp_path / "computable"
    _write_json(computable / "library.json", _library())
    _write_json(computable / "root.json", _root())
    fixture_root = tmp_path / "fixtures"
    bundle = _fixture_bundle()
    bundle["entry"][1]["resource"]["participant"] = {"individual": "bad"}
    _write_json(fixture_root / "case-one" / "bundle.json", bundle)
    _write_json(
        fixture_root / "case-one" / "assertions.json",
        {
            "evaluationContext": {
                "patientId": "example",
                "measurementPeriod": {
                    "start": "2026-01-01",
                    "end": "2026-12-31",
                    "startInclusive": True,
                    "endInclusive": True,
                },
            }
        },
    )
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, {"cases": [{"id": "case-one", "title": "Case one"}]})

    with pytest.raises(ExecutableBundleError, match="malformed Encounter.participant"):
        compose_executable_bundle(
            computable,
            manifest,
            fixture_root,
            tmp_path / "executable",
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
            "2026-06-15T09:20:00Z",
        )
