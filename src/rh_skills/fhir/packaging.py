"""FHIR package workspace preparation helpers.

Stages computable FHIR JSON + CQL into a package source workspace suitable for
``rh package check/build/pack`` while keeping ``computable/`` as the canonical
L3 artifact directory.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path

FHIR_VERSION = "4.0.1"
DEFAULT_LICENSE = "CC0-1.0"
DEFAULT_DEPENDENCIES: dict[str, str] = {
    "hl7.fhir.r4.core": FHIR_VERSION,
    "hl7.fhir.us.core": "6.1.0",
    "hl7.fhir.uv.crmi": "1.0.0",
}
SUPPORTED_TEST_FIXTURE_INPUT_FILES = (
    Path("input") / "bundle.json",
    Path("input") / "patient.json",
    Path("input") / "parameters.json",
)


def load_packager_toml(path: Path) -> dict[str, str]:
    """Load packager.toml metadata or return an empty mapping."""
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text())
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("id", "version", "canonical", "status"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


def build_dependency_map(
    *,
    has_cql: bool = False,
    extra_dependencies: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return the package dependency map for a staged workspace."""
    deps = dict(DEFAULT_DEPENDENCIES)
    if has_cql:
        deps["hl7.fhir.uv.cql"] = "2.0.0"
    if extra_dependencies:
        deps.update(extra_dependencies)
    return deps


def infer_package_id(topic_slug: str) -> str:
    """Return a FHIR package id for the topic with the 'reason.' prefix.
    
    The package ID is used for NPM-style package distribution and should be
    globally unique. We prefix all reason-healthcare packages with 'reason.'
    to namespace them consistently.
    
    Note: This is different from ImplementationGuide.id, which is a simple
    resource identifier without the prefix. The formalize-config.id field
    maps to IG.id, while this function generates IG.packageId.
    """
    return f"reason.{topic_slug}"


def dependency_uri(package_id: str, version: str) -> str:
    """Return a dependency URI for ImplementationGuide.dependsOn entries."""
    if package_id == "hl7.fhir.r4.core":
        return f"http://hl7.org/fhir/{version}"
    return f"https://packages.fhir.org/{package_id}/{version}"


def dependency_ref_id(package_id: str) -> str:
    """Return a compact id for ImplementationGuide.dependsOn entries."""
    return "".join(ch for ch in package_id if ch.isalnum())


def generate_implementation_guide(
    topic_slug: str,
    resource_files: list[str],
    *,
    version: str = "0.1.0",
    name: str | None = None,
    ig_id: str | None = None,
    canonical: str = "http://example.org/fhir",
    status: str = "draft",
    package_id: str | None = None,
    dependencies: dict[str, str] | None = None,
) -> dict:
    """Build the root ImplementationGuide resource for a package workspace.
    
    Note on identity fields:
    - ig_id (→ IG.id): Simple resource identifier, used in canonical URL
    - package_id (→ IG.packageId): NPM package name, globally unique with 'reason.' prefix
    - The canonical URL uses ig_id (not package_id) per FHIR spec
    """
    resolved_id = ig_id or topic_slug
    resolved_name = name or "".join(word.capitalize() for word in topic_slug.split("-"))
    resolved_pkg_id = package_id or infer_package_id(topic_slug)

    resources = []
    for fname in resource_files:
        stem = fname.rsplit(".", 1)[0] if "." in fname else fname
        parts = stem.split("-", 1)
        if len(parts) == 2:
            ref = f"{parts[0]}/{parts[1]}"
        else:
            ref = stem
        resources.append({
            "reference": {"reference": ref},
            "name": stem,
        })

    depends_on = []
    for dep_id, dep_version in (dependencies or {}).items():
        depends_on.append({
            "id": dependency_ref_id(dep_id),
            "packageId": dep_id,
            "uri": dependency_uri(dep_id, dep_version),
            "version": dep_version,
        })

    return {
        "resourceType": "ImplementationGuide",
        "id": resolved_id,  # Simple identifier (unprefixed)
        "url": f"{canonical}/ImplementationGuide/{resolved_id}",  # URL uses id, not packageId
        "version": version,
        "name": resolved_name,
        "title": topic_slug.replace("-", " ").title(),
        "status": status,
        "packageId": resolved_pkg_id,
        "fhirVersion": [FHIR_VERSION],
        "dependsOn": depends_on,
        "definition": {
            "resource": resources,
        },
    }


def generate_packager_toml(
    *,
    package_id: str,
    version: str,
    canonical: str,
    status: str,
    dependencies: dict[str, str],
    fhir_version: str = FHIR_VERSION,
    license_name: str = DEFAULT_LICENSE,
) -> str:
    """Return deterministic packager.toml content."""
    lines = [
        "# packager.toml — rh package configuration",
        f'id = "{package_id}"',
        f'version = "{version}"',
        f'canonical = "{canonical}"',
        f'fhir_version = "{fhir_version}"',
        f'license = "{license_name}"',
        f'status = "{status}"',
        "",
        "[dependencies]",
    ]
    for dep_id, dep_version in dependencies.items():
        lines.append(f'"{dep_id}" = "{dep_version}"')
    lines.extend(
        [
            "",
            "[hooks]",
            "before_build = []",
            "after_build  = []",
            "before_pack  = []",
            "after_pack   = []",
            "",
        ]
    )
    return "\n".join(lines)


def collect_computable_files(computable_dir: Path) -> tuple[list[Path], list[Path]]:
    """Collect FHIR JSON and CQL files from a computable directory."""
    json_files = sorted(computable_dir.glob("*.json"))
    cql_files = sorted(computable_dir.glob("*.cql"))
    return json_files, cql_files


def _filename_token(value: str) -> str:
    """Return a stable token for generated package example file names."""
    token = re.sub(r"[^A-Za-z0-9.-]+", "-", value.strip())
    token = re.sub(r"-{2,}", "-", token).strip("-.")
    return token or "unnamed"


def stage_test_fixture_examples(
    fixture_root: Path,
    examples_dir: Path,
    *,
    library: str | None = None,
    case: str | None = None,
) -> dict:
    """Copy supported CQL fixture input resources into package examples."""
    if not fixture_root.exists():
        return {
            "fixture_root": fixture_root,
            "library_count": 0,
            "case_count": 0,
            "file_count": 0,
            "resource_files": [],
        }

    library_dirs = (
        [fixture_root / library]
        if library
        else sorted(p for p in fixture_root.iterdir() if p.is_dir())
    )
    missing_library = library and not (fixture_root / library).is_dir()
    if missing_library:
        return {
            "error": f"Fixture library not found: {library}",
            "fixture_root": fixture_root,
        }

    selected_libraries: set[str] = set()
    selected_cases: set[tuple[str, str]] = set()
    resource_files: list[str] = []
    file_count = 0

    for library_dir in library_dirs:
        case_dirs = (
            [library_dir / case]
            if case
            else sorted(p for p in library_dir.iterdir() if p.is_dir())
        )
        if case and not (library_dir / case).is_dir():
            continue

        for case_dir in case_dirs:
            copied_for_case = False
            for relative_input in SUPPORTED_TEST_FIXTURE_INPUT_FILES:
                source = case_dir / relative_input
                if not source.exists():
                    continue
                try:
                    resource = json.loads(source.read_text())
                except json.JSONDecodeError as exc:
                    return {"error": f"Fixture input is not valid JSON: {source} ({exc})"}
                if not isinstance(resource, dict):
                    return {"error": f"Fixture input is not a FHIR JSON object: {source}"}
                resource_type = str(resource.get("resourceType") or "").strip()
                resource_id = str(resource.get("id") or "").strip()
                if not resource_type or not resource_id:
                    return {"error": f"Fixture input must have resourceType and id: {source}"}

                file_name = f"{_filename_token(resource_type)}-{_filename_token(resource_id)}.json"
                destination = examples_dir / file_name
                if destination.exists():
                    return {"error": f"Fixture example destination already exists: {destination}"}
                shutil.copy2(source, destination)
                copied_for_case = True
                file_count += 1
                resource_files.append(file_name)
            if copied_for_case:
                selected_libraries.add(library_dir.name)
                selected_cases.add((library_dir.name, case_dir.name))

    if case and not selected_cases:
        return {
            "error": f"Fixture case not found or has no supported input data: {case}",
            "fixture_root": fixture_root,
        }

    return {
        "fixture_root": fixture_root,
        "library_count": len(selected_libraries),
        "case_count": len(selected_cases),
        "file_count": file_count,
        "resource_files": resource_files,
    }


def prepare_package_workspace(
    computable_dir: Path,
    workspace_dir: Path,
    topic_slug: str,
    *,
    version: str = "0.1.0",
    name: str | None = None,
    ig_id: str | None = None,
    canonical: str = "http://example.org/fhir",
    status: str = "draft",
    package_id: str | None = None,
    extra_dependencies: dict[str, str] | None = None,
    test_fixture_root: Path | None = None,
    fixture_library: str | None = None,
    fixture_case: str | None = None,
) -> dict:
    """Stage a package source workspace for ``rh package`` commands."""
    json_files, cql_files = collect_computable_files(computable_dir)
    if not json_files and not cql_files:
        return {"error": "No FHIR JSON or CQL files found in computable directory"}

    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)

    input_dir = workspace_dir / "input"
    resources_dir = input_dir / "resources"
    examples_dir = input_dir / "examples"
    cql_dir = input_dir / "cql"
    for path in (
        resources_dir,
        examples_dir,
        cql_dir,
        input_dir / "fsh",
        input_dir / "docs",
        input_dir / "narrative",
    ):
        path.mkdir(parents=True, exist_ok=True)

    for resource_file in json_files:
        shutil.copy2(resource_file, examples_dir / resource_file.name)
    for cql_file in cql_files:
        shutil.copy2(cql_file, cql_dir / cql_file.name)

    staged_fixtures = None
    fixture_resource_files: list[str] = []
    if test_fixture_root is not None:
        staged_fixtures = stage_test_fixture_examples(
            test_fixture_root,
            examples_dir,
            library=fixture_library,
            case=fixture_case,
        )
        if "error" in staged_fixtures:
            return staged_fixtures
        fixture_resource_files = list(staged_fixtures["resource_files"])

    resolved_package_id = package_id or infer_package_id(topic_slug)
    dependencies = build_dependency_map(
        has_cql=bool(cql_files),
        extra_dependencies=extra_dependencies,
    )
    packager_text = generate_packager_toml(
        package_id=resolved_package_id,
        version=version,
        canonical=canonical,
        status=status,
        dependencies=dependencies,
    )
    (workspace_dir / "packager.toml").write_text(packager_text)

    ig = generate_implementation_guide(
        topic_slug,
        [resource_file.name for resource_file in json_files] + fixture_resource_files,
        version=version,
        name=name,
        ig_id=ig_id,
        canonical=canonical,
        status=status,
        package_id=resolved_package_id,
        dependencies=dependencies,
    )
    ig_text = json.dumps(ig, indent=2, ensure_ascii=False) + "\n"
    (workspace_dir / "ImplementationGuide.json").write_text(ig_text)
    (resources_dir / "ImplementationGuide.json").write_text(ig_text)

    return {
        "workspace_dir": workspace_dir,
        "package_name": resolved_package_id,
        "version": version,
        "json_count": len(json_files),
        "cql_count": len(cql_files),
        "fixture_count": staged_fixtures["file_count"] if staged_fixtures else 0,
        "fixture_library_count": staged_fixtures["library_count"] if staged_fixtures else 0,
        "fixture_case_count": staged_fixtures["case_count"] if staged_fixtures else 0,
        "examples_dir": examples_dir,
        "cql_dir": cql_dir,
    }
