"""Tests for FHIR package workspace preparation."""

from __future__ import annotations

import json
import tomllib

from rh_skills.fhir.packaging import (
    build_dependency_map,
    collect_computable_files,
    generate_implementation_guide,
    generate_packager_toml,
    infer_package_id,
    prepare_package_workspace,
    stage_test_fixture_inputs,
)


class TestInferPackageId:
    def test_uses_unscoped_reason_prefix(self):
        assert infer_package_id("sepsis-bundle") == "reason.sepsis-bundle"


class TestBuildDependencyMap:
    def test_basic(self):
        deps = build_dependency_map()
        assert deps["hl7.fhir.r4.core"] == "4.0.1"
        assert "hl7.fhir.us.core" in deps
        assert "hl7.fhir.uv.crmi" in deps

    def test_with_cql(self):
        deps = build_dependency_map(has_cql=True)
        assert deps["hl7.fhir.uv.cql"] == "2.0.0"

    def test_extra_dependencies(self):
        deps = build_dependency_map(extra_dependencies={"custom.ig": "1.0.0"})
        assert deps["custom.ig"] == "1.0.0"


class TestGeneratePackagerToml:
    def test_parses_as_toml(self):
        content = generate_packager_toml(
            package_id="reason.test-topic",
            version="2.0.0",
            canonical="https://example.org/fhir",
            status="draft",
            dependencies=build_dependency_map(has_cql=True),
        )
        data = tomllib.loads(content)
        assert data["id"] == "reason.test-topic"
        assert data["version"] == "2.0.0"
        assert data["canonical"] == "https://example.org/fhir"
        assert data["dependencies"]["hl7.fhir.uv.cql"] == "2.0.0"


class TestGenerateImplementationGuide:
    def test_basic(self):
        ig = generate_implementation_guide(
            "sepsis-bundle",
            ["PlanDefinition-sepsis.json", "Library-sepsis.json"],
            package_id="reason.sepsis-bundle",
            dependencies=build_dependency_map(has_cql=True),
        )
        assert ig["resourceType"] == "ImplementationGuide"
        assert ig["id"] == "sepsis-bundle"
        assert ig["packageId"] == "reason.sepsis-bundle"
        assert len(ig["definition"]["resource"]) == 2
        assert ig["fhirVersion"] == ["4.0.1"]
        assert any(d["packageId"] == "hl7.fhir.r4.core" for d in ig["dependsOn"])

    def test_resource_references(self):
        ig = generate_implementation_guide(
            "test",
            ["PlanDefinition-sepsis.json"],
            package_id="reason.test",
            dependencies=build_dependency_map(),
        )
        ref = ig["definition"]["resource"][0]["reference"]["reference"]
        assert ref == "PlanDefinition/sepsis"


class TestCollectComputableFiles:
    def test_collects_json_and_cql(self, tmp_path):
        (tmp_path / "PlanDefinition-test.json").write_text("{}")
        (tmp_path / "Library-test.json").write_text("{}")
        (tmp_path / "TestLogic.cql").write_text("library TestLogic")
        (tmp_path / "notes.txt").write_text("not a fhir file")

        json_files, cql_files = collect_computable_files(tmp_path)
        assert len(json_files) == 2
        assert len(cql_files) == 1
        assert all(f.suffix == ".json" for f in json_files)
        assert all(f.suffix == ".cql" for f in cql_files)

    def test_empty_dir(self, tmp_path):
        json_files, cql_files = collect_computable_files(tmp_path)
        assert json_files == []
        assert cql_files == []


class TestPreparePackageWorkspace:
    def test_full_workspace(self, tmp_path):
        comp_dir = tmp_path / "computable"
        comp_dir.mkdir()
        (comp_dir / "PlanDefinition-test.json").write_text(json.dumps({"resourceType": "PlanDefinition"}))
        (comp_dir / "TestLogic.cql").write_text("library TestLogic version '1.0.0'")

        workspace_dir = tmp_path / "workspace"
        result = prepare_package_workspace(comp_dir, workspace_dir, "test-topic")

        assert result["package_name"] == "reason.test-topic"
        assert result["json_count"] == 1
        assert result["cql_count"] == 1
        assert (workspace_dir / "packager.toml").exists()
        assert (workspace_dir / "ImplementationGuide.json").exists()
        assert (workspace_dir / "input" / "resources" / "ImplementationGuide.json").exists()
        assert (workspace_dir / "input" / "examples" / "PlanDefinition-test.json").exists()
        assert (workspace_dir / "input" / "cql" / "TestLogic.cql").exists()

        ig = json.loads((workspace_dir / "ImplementationGuide.json").read_text())
        assert ig["packageId"] == "reason.test-topic"

        packager = tomllib.loads((workspace_dir / "packager.toml").read_text())
        assert packager["dependencies"]["hl7.fhir.uv.cql"] == "2.0.0"

    def test_workspace_rewrites_existing_directory(self, tmp_path):
        comp_dir = tmp_path / "computable"
        comp_dir.mkdir()
        (comp_dir / "PlanDefinition-test.json").write_text(json.dumps({"resourceType": "PlanDefinition"}))
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        (workspace_dir / "old.txt").write_text("stale")

        prepare_package_workspace(comp_dir, workspace_dir, "test-topic")
        assert not (workspace_dir / "old.txt").exists()

    def test_empty_computable(self, tmp_path):
        comp_dir = tmp_path / "computable"
        comp_dir.mkdir()
        workspace_dir = tmp_path / "workspace"
        result = prepare_package_workspace(comp_dir, workspace_dir, "empty-topic")
        assert "error" in result


class TestStageTestFixtureInputs:
    def test_copies_only_supported_fixture_input_files(self, tmp_path):
        fixture_root = tmp_path / "tests" / "cql"
        case_dir = fixture_root / "ExampleLogic" / "case-positive"
        (case_dir / "input").mkdir(parents=True)
        (case_dir / "expected").mkdir()
        (case_dir / "input" / "bundle.json").write_text('{"resourceType":"Bundle"}')
        (case_dir / "input" / "patient.json").write_text('{"resourceType":"Patient"}')
        (case_dir / "input" / "parameters.json").write_text('{"resourceType":"Parameters"}')
        (case_dir / "expected" / "expression-results.json").write_text("{}")
        (case_dir / "notes.md").write_text("# Notes")

        workspace_dir = tmp_path / "workspace"
        result = stage_test_fixture_inputs(fixture_root, workspace_dir)

        staged_case = workspace_dir / "tests" / "cql" / "ExampleLogic" / "case-positive"
        assert result["library_count"] == 1
        assert result["case_count"] == 1
        assert result["file_count"] == 3
        assert (staged_case / "input" / "bundle.json").exists()
        assert (staged_case / "input" / "patient.json").exists()
        assert (staged_case / "input" / "parameters.json").exists()
        assert not (staged_case / "expected" / "expression-results.json").exists()
        assert not (staged_case / "notes.md").exists()

    def test_filters_by_library_and_case(self, tmp_path):
        fixture_root = tmp_path / "tests" / "cql"
        selected = fixture_root / "SelectedLogic" / "case-a" / "input"
        skipped = fixture_root / "OtherLogic" / "case-a" / "input"
        selected.mkdir(parents=True)
        skipped.mkdir(parents=True)
        (selected / "bundle.json").write_text("{}")
        (skipped / "bundle.json").write_text("{}")

        workspace_dir = tmp_path / "workspace"
        result = stage_test_fixture_inputs(
            fixture_root,
            workspace_dir,
            library="SelectedLogic",
            case="case-a",
        )

        assert result["file_count"] == 1
        staged_bundle = (
            workspace_dir
            / "tests"
            / "cql"
            / "SelectedLogic"
            / "case-a"
            / "input"
            / "bundle.json"
        )
        assert staged_bundle.exists()
        assert not (workspace_dir / "tests" / "cql" / "OtherLogic").exists()
