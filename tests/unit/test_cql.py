"""Tests for rh-skills cql commands (validate/translate/test via rh)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rh_skills.commands.cql import _strict_json_equal, cql


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_topic(tmp_path: Path, library: str = "TestLib", content: str = "") -> Path:
    computable = tmp_path / "topics" / "test-topic" / "computable"
    computable.mkdir(parents=True)
    (computable / f"{library}.cql").write_text(content or f"library {library} version '1.0.0'\n")
    return tmp_path


def _make_fixture(tmp_path: Path, library: str, case: str, expected: dict) -> None:
    case_dir = tmp_path / "tests" / "cql" / library / case
    (case_dir / "input").mkdir(parents=True)
    (case_dir / "expected").mkdir(parents=True)
    (case_dir / "input" / "bundle.json").write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": []})
    )
    (case_dir / "expected" / "expression-results.json").write_text(json.dumps(expected))


def _make_library_import_workspace(tmp_path: Path, *, name: str = "FHIRHelpers", version: str = "4.0.1") -> Path:
    topic = "test-topic"
    computable = tmp_path / "topics" / topic / "computable"
    computable.mkdir(parents=True)
    (tmp_path / "tracking.yaml").write_text(
        "topics:\n"
        "  - name: test-topic\n"
        "    computable:\n"
        "      - name: primary-library\n"
        "        files:\n"
        "          - topics/test-topic/computable/Library-Primary.json\n"
        "        checksums:\n"
        "          topics/test-topic/computable/Library-Primary.json: initial\n"
    )
    (computable / "Primary.cql").write_text(
        "library Primary version '1.0.0'\n"
        "using FHIR version '4.0.1'\n"
        f"include {name} version '{version}' called Helper\n"
    )
    (computable / "Library-Primary.json").write_text(json.dumps({
        "resourceType": "Library",
        "id": "primary",
        "url": "https://example.org/fhir/Library/primary",
        "version": "1.0.0",
        "name": "Primary",
        "status": "active",
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/library-type", "code": "logic-library"}]},
        "content": [],
    }, indent=2) + "\n")

    manifest_dir = tmp_path / "dependencies"
    manifest_dir.mkdir()
    cql = f"library {name} version '{version}'\nusing FHIR version '4.0.1'\n"
    elm = {"library": {"identifier": {"id": name, "version": version}}}
    cql_path = manifest_dir / f"{name}-{version}.cql"
    elm_path = manifest_dir / f"{name}-{version}.json"
    cql_path.write_text(cql)
    elm_path.write_text(json.dumps(elm, separators=(",", ":")))
    import hashlib

    manifest = {
        "resource": {
            "id": "fhir-helpers-4-0-1",
            "url": "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers",
            "name": name,
            "version": version,
        },
        "source": {
            "url": "https://example.org/source/FHIRHelpers.cql",
            "tag": "v3.26.0",
            "license": "Apache-2.0",
            "compile_tool": {"name": "CQFramework cql-to-elm-cli", "version": "3.26.0", "options": ["--format", "JSON"]},
        },
        "cql": {"path": cql_path.name, "sha256": hashlib.sha256(cql_path.read_bytes()).hexdigest()},
        "elm": {"path": elm_path.name, "sha256": hashlib.sha256(elm_path.read_bytes()).hexdigest()},
    }
    manifest_path = manifest_dir / "import.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


def test_strict_json_equality_distinguishes_boolean_null_and_number():
    assert not _strict_json_equal(True, 1)
    assert not _strict_json_equal(False, 0)
    assert not _strict_json_equal(None, False)
    assert _strict_json_equal(1, 1.0)
    assert not _strict_json_equal({"risk": True}, {"risk": 1})


# ── validate ──────────────────────────────────────────────────────────────────


def test_validate_rh_absent_emits_install_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.delenv("RH_CLI_PATH", raising=False)
    with patch("shutil.which", return_value=None):
        result = CliRunner().invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "cargo" in (result.output + str(result.exception or "")).lower()


def test_validate_cql_not_found(tmp_path, monkeypatch):
    (tmp_path / "topics" / "test-topic" / "computable").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cql, ["validate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_validate_success_exits_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = CliRunner().invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd[1:] == [
        "cql", "validate", str(tmp_path / "topics/test-topic/computable/TestLib.cql"),
        "--lib-path", str(tmp_path / "topics/test-topic/computable"),
    ]


def test_validate_errors_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = CliRunner().invoke(cql, ["validate", "test-topic", "TestLib"])
    assert result.exit_code != 0


# ── translate ─────────────────────────────────────────────────────────────────


def test_translate_rh_absent_emits_install_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.delenv("RH_CLI_PATH", raising=False)
    with patch("shutil.which", return_value=None):
        result = CliRunner().invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "cargo" in (result.output + str(result.exception or "")).lower()


def test_translate_cql_not_found(tmp_path, monkeypatch):
    (tmp_path / "topics" / "test-topic" / "computable").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cql, ["translate", "test-topic", "Missing"])
    assert result.exit_code != 0


def test_translate_success_echoes_elm_path(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = CliRunner().invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code == 0
    expected_elm = tmp_path / "topics/test-topic/computable/elm/TestLib.json"
    assert str(expected_elm) in result.output
    cmd = mock_run.call_args[0][0]
    assert cmd[1:3] == ["cql", "compile"]
    assert str(expected_elm) in cmd
    assert cmd[-2:] == ["--lib-path", str(tmp_path / "topics/test-topic/computable")]


def test_translate_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = CliRunner().invoke(cql, ["translate", "test-topic", "TestLib"])
    assert result.exit_code != 0


# ── test ──────────────────────────────────────────────────────────────────────


def test_test_no_fixtures_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0


def test_test_runs_eval_and_reports_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd[1:3] == ["cql", "eval"]
    assert "PASS IsAdult" in result.output
    assert "case-001-basic" in result.output


def test_test_passes_explicit_evaluation_context_period_and_parameters(tmp_path, monkeypatch):
    topic = _make_topic(
        tmp_path,
        content='library TestLib version \'1.0.0\'\nparameter "Measurement Period" Interval<DateTime>\n',
    )
    monkeypatch.chdir(topic)
    _make_fixture(tmp_path, "TestLib", "case-002-context", {"IsAdult": True})
    case = tmp_path / "tests" / "cql" / "TestLib" / "case-002-context"
    bundle_path = case / "input" / "bundle.json"
    bundle_path.write_text(json.dumps({
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "selected-patient"}},
            {"resource": {"resourceType": "Patient", "id": "other-patient"}},
        ],
    }))
    (case / "input" / "evaluation-context.json").write_text(json.dumps({
        "subject": "Patient/selected-patient",
        "evaluationDate": "2026-06-15T09:20:00Z",
        "measurementPeriod": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
            "startInclusive": True,
            "endInclusive": False,
        },
        "parameters": {"RiskThreshold": 2},
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])

    assert result.exit_code == 0, result.output
    command = mock_run.call_args[0][0]
    assert command[command.index("--subject") + 1] == "Patient/selected-patient"
    assert command[command.index("--evaluation-date") + 1] == "2026-06-15T09:20:00Z"
    assert command[command.index("--measurement-period-start") + 1] == "2026-01-01T00:00:00Z"
    assert command[command.index("--measurement-period-end") + 1] == "2026-12-31T23:59:59Z"
    assert "--parameter" in command
    assert command[command.index("--subject") + 1] == "Patient/selected-patient"
    parameter_pairs = [command[idx + 1] for idx, value in enumerate(command[:-1]) if value == "--parameter"]
    assert "RiskThreshold=2" in parameter_pairs
    assert (
        'Measurement Period={"start":"2026-01-01T00:00:00Z","end":"2026-12-31T23:59:59Z",'
        '"startInclusive":true,"endInclusive":false}'
    ) in parameter_pairs


def test_test_passes_optional_preexpanded_valueset_sidecar(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-006-terminology", {"HasCode": True})
    case = tmp_path / "tests" / "cql" / "TestLib" / "case-006-terminology"
    terminology_path = case / "input" / "terminology.json"
    terminology_path.write_text(json.dumps({
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {"resourceType": "ValueSet", "url": "https://example.org/ValueSet/a", "version": "0.2.0", "expansion": {"contains": []}}}],
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code == 0, result.output
    command = mock_run.call_args[0][0]
    assert command[command.index("--terminology") + 1] == str(terminology_path)


@pytest.mark.parametrize("terminology", [
    {"resourceType": "Bundle", "type": "collection", "entry": []},
    {"resourceType": "ValueSet", "url": "https://example.org/ValueSet/a"},
    {"resourceType": "Patient", "id": "not-terminology"},
])
def test_test_rejects_invalid_terminology_sidecar_before_eval(tmp_path, monkeypatch, terminology):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-007-invalid-terminology", {"HasCode": True})
    case = tmp_path / "tests" / "cql" / "TestLib" / "case-007-invalid-terminology"
    (case / "input" / "terminology.json").write_text(json.dumps(terminology))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    mock_run.assert_not_called()


def test_test_converts_fhir_parameters_file_into_cli_overrides(tmp_path, monkeypatch):
    topic = _make_topic(tmp_path)
    monkeypatch.chdir(topic)
    _make_fixture(tmp_path, "TestLib", "case-003-parameters", {"HasConsent": True})
    case = tmp_path / "tests" / "cql" / "TestLib" / "case-003-parameters"
    (case / "input" / "parameters.json").write_text(json.dumps({
        "resourceType": "Parameters",
        "parameter": [{"name": "HasConsent", "valueBoolean": True}],
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])

    assert result.exit_code == 0, result.output
    command = mock_run.call_args[0][0]
    assert command[command.index("--parameter") + 1] == "HasConsent=true"


def test_test_rejects_multiple_patients_without_explicit_subject(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-004-multiple-patients", {"IsAdult": True})
    case = tmp_path / "tests/cql/TestLib/case-004-multiple-patients"
    (case / "input/bundle.json").write_text(json.dumps({
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "patient-a"}},
            {"resource": {"resourceType": "Patient", "id": "patient-b"}},
        ],
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "set input/evaluation-context.json subject explicitly" in result.output
    mock_run.assert_not_called()


def test_test_rejects_explicit_subject_missing_from_fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-005-wrong-subject", {"IsAdult": True})
    case = tmp_path / "tests/cql/TestLib/case-005-wrong-subject"
    (case / "input/bundle.json").write_text(json.dumps({
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {"resourceType": "Patient", "id": "actual-patient"}}],
    }))
    (case / "input/evaluation-context.json").write_text(json.dumps({
        "subject": "Patient/not-in-fixture",
    }))
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "does not exist in the fixture input" in result.output
    mock_run.assert_not_called()


def test_test_reports_expression_mismatch(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "expected true, got false" in result.output.lower()


def test_test_rejects_boolean_result_when_expected_value_is_number_one(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": 1})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "expected 1, got true" in result.output.lower()


def test_test_reports_eval_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(_make_topic(tmp_path))
    _make_fixture(tmp_path, "TestLib", "case-001-basic", {"IsAdult": True})
    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="compile error")
        result = CliRunner().invoke(cql, ["test", "test-topic", "TestLib"])
    assert result.exit_code != 0
    assert "compile error" in result.output


def test_import_library_pins_identity_links_primary_and_is_idempotent(tmp_path, monkeypatch):
    manifest = _make_library_import_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cql, ["import-library", "test-topic", str(manifest)])
    assert result.exit_code == 0, result.output

    computable = tmp_path / "topics/test-topic/computable"
    helper_path = computable / "Library-fhir-helpers-4-0-1.json"
    helper = json.loads(helper_path.read_text())
    assert helper["url"] == "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers"
    assert helper["version"] == "4.0.1"
    assert [content["contentType"] for content in helper["content"]] == [
        "text/cql", "application/elm+json"
    ]
    primary_path = computable / "Library-Primary.json"
    primary = json.loads(primary_path.read_text())
    assert primary["relatedArtifact"] == [{
        "type": "depends-on",
        "resource": "http://hl7.org/fhir/uv/cql/Library/FHIRHelpers|4.0.1",
    }]
    tracking_text = (tmp_path / "tracking.yaml").read_text()
    assert "external-library-FHIRHelpers-4.0.1" in tracking_text
    assert "external-dependency" in tracking_text

    before = {
        path: path.read_bytes()
        for path in [
            helper_path,
            computable / "FHIRHelpers-4.0.1.cql",
            computable / "elm/FHIRHelpers-4.0.1.json",
            primary_path,
        ]
    }
    repeated = CliRunner().invoke(cql, ["import-library", "test-topic", str(manifest)])
    assert repeated.exit_code == 0, repeated.output
    assert "already imported" in repeated.output
    assert all(path.read_bytes() == content for path, content in before.items())


def test_import_library_rejects_bad_hash_before_writing(tmp_path, monkeypatch):
    manifest = _make_library_import_workspace(tmp_path)
    data = json.loads(manifest.read_text())
    data["cql"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cql, ["import-library", "test-topic", str(manifest)])
    assert result.exit_code != 0
    assert "SHA-256 mismatch" in result.output
    assert not (tmp_path / "topics/test-topic/computable/Library-fhir-helpers-4-0-1.json").exists()


def test_import_library_rejects_elm_identity_mismatch(tmp_path, monkeypatch):
    manifest = _make_library_import_workspace(tmp_path)
    data = json.loads(manifest.read_text())
    elm_path = manifest.parent / data["elm"]["path"]
    elm = json.loads(elm_path.read_text())
    elm["library"]["identifier"]["version"] = "4.0.0"
    elm_path.write_text(json.dumps(elm, separators=(",", ":")))
    import hashlib

    data["elm"]["sha256"] = hashlib.sha256(elm_path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cql, ["import-library", "test-topic", str(manifest)])
    assert result.exit_code != 0
    assert "ELM library identifier/version mismatch" in result.output


def test_import_library_rejects_manifest_path_escape(tmp_path, monkeypatch):
    manifest = _make_library_import_workspace(tmp_path)
    data = json.loads(manifest.read_text())
    data["cql"]["path"] = "../outside.cql"
    manifest.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cql, ["import-library", "test-topic", str(manifest)])
    assert result.exit_code != 0
    assert "escapes the manifest directory" in result.output
