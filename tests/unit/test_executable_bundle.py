"""Executable Bundle closure tests using FHIR R4 Library.content attachments."""

from __future__ import annotations

import base64
import json

import pytest

from rh_skills.commands.executable_bundle import (
    ExecutableBundleError,
    _elm_definition_names,
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
    resource_id: str = "logic",
    url: str = "https://example.org/fhir/Library/logic",
    cql: str | None = 'library Logic version \'1.0.0\'\ndefine "Eligible": true\n',
    elm: dict | None = None,
) -> dict:
    if elm is None:
        elm = {
            "library": {
                "identifier": {"id": name, "version": version},
                "includes": {"def": []},
                "statements": {"def": [{"name": "Eligible", "expression": {"type": "Literal"}}]},
            },
        }
    content = []
    if cql is not None:
        content.append({"contentType": "text/cql", "data": _b64(cql)})
    if elm is not None:
        content.append({"contentType": "application/elm+json", "data": _b64(elm)})
    return {
        "resourceType": "Library",
        "id": resource_id,
        "url": url,
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
            "statements": {"def": [{"name": "Other", "expression": {"type": "Literal"}}]},
        },
    })

    with pytest.raises(ExecutableBundleError, match="compiled ELM is missing CQL definitions"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_rejects_elm_definition_without_executable_expression():
    library = _library(elm={
        "library": {
            "identifier": {"id": "Logic", "version": "1.0.0"},
            "includes": {"def": []},
            "statements": {"def": [{"name": "Eligible"}]},
        },
    })

    with pytest.raises(ExecutableBundleError, match="missing an executable expression"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_elm_permits_official_external_fhirhelpers_function_definition():
    elm = {
        "library": {
            "statements": {
                "def": [
                    {
                        "type": "FunctionDef",
                        "operand": [
                            {
                                "type": "OperandDef",
                                "operandTypeSpecifier": {
                                    "type": "NamedTypeSpecifier",
                                    "name": "{urn:hl7-org:elm-types:r1}String",
                                },
                                "name": "reference",
                            }
                        ],
                        "name": "resolve",
                        "context": "Unfiltered",
                        "accessLevel": "Public",
                        "external": True,
                    }
                ]
            }
        }
    }

    # Matches the official FHIRHelpers 4.0.1 external `resolve` shape. It is
    # accepted for closure but cannot satisfy a zero-operand CQL identifier.
    assert _elm_definition_names(elm) == set()


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
            "statements": {"def": [{"name": "Eligible", "expression": {"type": "Literal"}}]},
        },
    })

    with pytest.raises(ExecutableBundleError, match=r"Unresolved ELM include dependency: MissingLibrary\|1.0.0"):
        _validate_closure([library, _root()], "https://example.org/fhir/PlanDefinition/root|1.0.0")


def test_closure_resolves_pinned_fhirhelpers_from_elm_include():
    logic = _library(elm={
        "library": {
            "identifier": {"id": "Logic", "version": "1.0.0"},
            "includes": {"def": [{"path": "FHIRHelpers", "version": "4.0.1"}]},
            "statements": {"def": [{"name": "Eligible", "expression": {"type": "Literal"}}]},
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


def test_closure_rejects_measure_population_expression_missing_from_elm():
    measure = {
        "resourceType": "Measure",
        "id": "measure",
        "url": "https://example.org/fhir/Measure/measure",
        "version": "1.0.0",
        "library": ["https://example.org/fhir/Library/logic|1.0.0"],
        "group": [{"population": [{"criteria": {"language": "text/cql-identifier", "expression": "Missing"}}]}],
    }

    with pytest.raises(ExecutableBundleError, match="Measure/measure.*Missing"):
        _validate_closure(
            [_library(), _root(), measure],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )


def test_closure_does_not_use_definitions_from_another_library_version():
    version_one = _library(
        cql='library Logic version \'1.0.0\'\ndefine "Other": true\n',
        elm={
            "library": {
                "identifier": {"id": "Logic", "version": "1.0.0"},
                "includes": {"def": []},
                "statements": {"def": [{"name": "Other", "expression": {"type": "Literal"}}]},
            }
        },
    )
    version_two = _library(
        version="2.0.0",
        cql='library Logic version \'2.0.0\'\ndefine "Eligible": true\n',
    )
    version_two["id"] = "logic-v2"

    with pytest.raises(ExecutableBundleError, match="PlanDefinition/root.*Eligible"):
        _validate_closure(
            [version_one, version_two, _root()],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )


def test_closure_rejects_wrong_expansion_code_or_release_with_matching_total():
    value_set = {
        "resourceType": "ValueSet",
        "id": "screening-values",
        "url": "https://example.org/fhir/ValueSet/screening-values",
        "version": "1.0.0",
        "compose": {
            "include": [
                {
                    "system": "http://snomed.info/sct",
                    "version": "20260901",
                    "concept": [{"code": "expected"}],
                }
            ]
        },
        "expansion": {
            "total": 1,
            "contains": [
                {"system": "http://snomed.info/sct", "version": "20260301", "code": "wrong"}
            ],
        },
    }

    with pytest.raises(ExecutableBundleError, match="does not match version-pinned compose membership"):
        _validate_closure(
            [_library(), _root(), value_set],
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
        )


def test_closure_rejects_incomplete_or_unpinned_valueset_expansion():
    value_set = {
        "resourceType": "ValueSet",
        "id": "screening-values",
        "url": "https://example.org/fhir/ValueSet/screening-values",
        "version": "1.0.0",
        "compose": {"include": [{"system": "http://snomed.info/sct"}]},
        "expansion": {
            "total": 2,
            "contains": [
                {"system": "http://snomed.info/sct", "version": "20260901", "code": "1"}
            ],
        },
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
    helper_elm = {
        "library": {
            "identifier": {"id": "FHIRHelpers", "version": "4.0.1"},
            "includes": {"def": []},
            "statements": {"def": [{"name": "HelperValue", "expression": {"type": "Literal"}}]},
        },
    }
    helper_url = "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers"
    _write_json(
        computable / "fhirhelpers.json",
        _library(
            name="FHIRHelpers",
            version="4.0.1",
            resource_id="fhirhelpers-4-0-1",
            url=helper_url,
            cql=None,
            elm=helper_elm,
        ),
    )
    evidence_variable = {
        "resourceType": "EvidenceVariable",
        "id": "evidence-summary-evidencevariable",
        "url": "https://example.org/fhir/EvidenceVariable/evidence-summary-evidencevariable",
        "version": "1.0.0",
        "status": "draft",
        "name": "EvidenceSummaryVariable",
        "description": "Evidence variable used by the summary.",
        "characteristic": [],
    }
    evidence = {
        "resourceType": "Evidence",
        "id": "evidence-summary",
        "url": "https://example.org/fhir/Evidence/evidence-summary",
        "version": "1.0.0",
        "status": "draft",
        "name": "EvidenceSummary",
        "exposureBackground": {"reference": "EvidenceVariable/evidence-summary-evidencevariable"},
    }
    _write_json(computable / "evidence-variable.json", evidence_variable)
    _write_json(computable / "evidence.json", evidence)
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
    executable_bundle = json.loads(result["bundle"].read_text())
    executable_entries = {
        (entry["resource"]["resourceType"], entry["resource"]["id"]): entry
        for entry in executable_bundle["entry"]
    }
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
    assert all(entry["fullUrl"].startswith("urn:uuid:") for entry in executable_bundle["entry"])
    assert len({entry["fullUrl"] for entry in executable_bundle["entry"]}) == len(executable_bundle["entry"])
    helper_entry = executable_entries[("Library", "fhirhelpers-4-0-1")]
    assert helper_entry["resource"]["url"] == helper_url
    assert helper_entry["fullUrl"] != helper_url
    evidence_variable_entry = executable_entries[("EvidenceVariable", "evidence-summary-evidencevariable")]
    evidence_entry = executable_entries[("Evidence", "evidence-summary")]
    assert evidence_entry["resource"]["exposureBackground"]["reference"] == evidence_variable_entry["fullUrl"]
    assert json.loads((computable / "evidence.json").read_text())["exposureBackground"]["reference"] == (
        "EvidenceVariable/evidence-summary-evidencevariable"
    )
    manifest_resources = {
        (resource["resourceType"], resource["id"]): resource
        for resource in executable_manifest["resources"]
    }
    assert manifest_resources[("EvidenceVariable", "evidence-summary-evidencevariable")]["fullUrl"] == (
        evidence_variable_entry["fullUrl"]
    )

    repeated = compose_executable_bundle(
        computable,
        manifest,
        fixture_root,
        tmp_path / "executable-repeat",
        "https://example.org/fhir/PlanDefinition/root|1.0.0",
        "2026-06-15T09:20:00Z",
    )
    repeated_bundle = json.loads(repeated["bundle"].read_text())
    assert {
        (entry["resource"]["resourceType"], entry["resource"]["id"]): entry["fullUrl"]
        for entry in repeated_bundle["entry"]
    } == {
        identity: entry["fullUrl"] for identity, entry in executable_entries.items()
    }
    assert executable_manifest["checksums"]["algorithm"] == "sha256-canonical-json"
    assert len(executable_manifest["checksums"]["rootResourceCanonicalJson"]) == 64
    assert executable_manifest["checksums"]["fixtureBundles"][0]["path"] == "fixtures/case-one.json"
    assert len(executable_manifest["checksums"]["fixtureBundles"][0]["canonicalJsonSha256"]) == 64


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


def test_compose_rejects_reversed_period_and_non_composer_output(tmp_path):
    computable = tmp_path / "computable"
    _write_json(computable / "library.json", _library())
    _write_json(computable / "root.json", _root())
    fixture_root = tmp_path / "fixtures"
    _write_json(fixture_root / "case-one" / "bundle.json", _fixture_bundle())
    _write_json(
        fixture_root / "case-one" / "assertions.json",
        {
            "evaluationContext": {
                "patientId": "example",
                "measurementPeriod": {
                    "start": "2026-12-31",
                    "end": "2026-01-01",
                    "startInclusive": True,
                    "endInclusive": True,
                },
            }
        },
    )
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, {"cases": [{"id": "case-one", "title": "Case one"}]})
    output = tmp_path / "executable"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ExecutableBundleError, match="reversed.*measurement period"):
        compose_executable_bundle(
            computable,
            manifest,
            fixture_root,
            output,
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
            "2026-06-15T09:20:00Z",
        )
    assert (output / "unrelated.txt").read_text() == "keep"
    assertions = json.loads((fixture_root / "case-one" / "assertions.json").read_text())
    assertions["evaluationContext"]["measurementPeriod"]["start"] = "2026-01-01"
    _write_json(fixture_root / "case-one" / "assertions.json", assertions)

    with pytest.raises(ExecutableBundleError, match="non-composer-owned"):
        compose_executable_bundle(
            computable,
            manifest,
            fixture_root,
            output,
            "https://example.org/fhir/PlanDefinition/root|1.0.0",
            "2026-06-15T09:20:00Z",
        )
    assert (output / "unrelated.txt").read_text() == "keep"
