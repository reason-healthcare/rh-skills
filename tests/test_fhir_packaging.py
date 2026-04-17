"""Tests for FHIR package builder."""

import json
from pathlib import Path
from rh_skills.fhir.packaging import (
    generate_package_json,
    generate_implementation_guide,
    collect_computable_files,
    build_package,
)


class TestGeneratePackageJson:
    def test_basic(self):
        pkg = generate_package_json("sepsis-bundle")
        assert pkg["name"] == "@reason/sepsis-bundle"
        assert pkg["version"] == "1.0.0"
        assert pkg["type"] == "fhir.ig"
        assert "4.0.1" in pkg["fhirVersions"]
        assert "hl7.fhir.us.core" in pkg["dependencies"]
        assert "hl7.fhir.uv.crmi" in pkg["dependencies"]

    def test_with_cql(self):
        pkg = generate_package_json("my-topic", has_cql=True)
        assert "hl7.fhir.uv.cql" in pkg["dependencies"]

    def test_without_cql(self):
        pkg = generate_package_json("my-topic", has_cql=False)
        assert "hl7.fhir.uv.cql" not in pkg["dependencies"]

    def test_custom_version(self):
        pkg = generate_package_json("my-topic", version="2.0.0")
        assert pkg["version"] == "2.0.0"

    def test_extra_dependencies(self):
        pkg = generate_package_json("my-topic", extra_dependencies={"custom.ig": "1.0.0"})
        assert "custom.ig" in pkg["dependencies"]


class TestGenerateImplementationGuide:
    def test_basic(self):
        ig = generate_implementation_guide(
            "sepsis-bundle",
            ["PlanDefinition-sepsis.json", "Library-sepsis.json"],
        )
        assert ig["resourceType"] == "ImplementationGuide"
        assert ig["id"] == "sepsis-bundle"
        assert ig["packageId"] == "@reason/sepsis-bundle"
        assert len(ig["definition"]["resource"]) == 2
        assert ig["fhirVersion"] == ["4.0.1"]

    def test_resource_references(self):
        ig = generate_implementation_guide(
            "test",
            ["PlanDefinition-sepsis.json"],
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


class TestBuildPackage:
    def test_full_build(self, tmp_path):
        comp_dir = tmp_path / "computable"
        comp_dir.mkdir()
        (comp_dir / "PlanDefinition-test.json").write_text(json.dumps({"resourceType": "PlanDefinition"}))
        (comp_dir / "TestLogic.cql").write_text("library TestLogic version '1.0.0'")

        out_dir = tmp_path / "package"
        result = build_package(comp_dir, out_dir, "test-topic")

        assert result["package_name"] == "@reason/test-topic"
        assert result["json_count"] == 1
        assert result["cql_count"] == 1
        assert (out_dir / "package.json").exists()
        assert (out_dir / "ImplementationGuide-test-topic.json").exists()
        assert (out_dir / "PlanDefinition-test.json").exists()
        assert (out_dir / "TestLogic.cql").exists()

        pkg = json.loads((out_dir / "package.json").read_text())
        assert pkg["name"] == "@reason/test-topic"
        assert "hl7.fhir.uv.cql" in pkg["dependencies"]  # CQL present

    def test_empty_computable(self, tmp_path):
        comp_dir = tmp_path / "computable"
        comp_dir.mkdir()
        out_dir = tmp_path / "package"
        result = build_package(comp_dir, out_dir, "empty-topic")
        assert "error" in result
