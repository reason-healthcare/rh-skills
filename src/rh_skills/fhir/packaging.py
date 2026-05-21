"""FHIR package workspace preparation helpers.

Stages computable FHIR JSON + CQL into a package source workspace suitable for
``rh package check/build/pack`` while keeping ``computable/`` as the canonical
L3 artifact directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FHIR_VERSION = "4.0.1"
DEFAULT_LICENSE = "CC0-1.0"
DEFAULT_DEPENDENCIES: dict[str, str] = {
    "hl7.fhir.r4.core": FHIR_VERSION,
    "hl7.fhir.us.core": "6.1.0",
    "hl7.fhir.uv.crmi": "1.0.0",
}


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
    """Return a FHIR package id for the topic.

    The ``rh package`` workflow expects an unscoped package id rather than an
    npm-style ``@scope/name`` identifier.
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
    """Build the root ImplementationGuide resource for a package workspace."""
    resolved_id = ig_id or topic_slug
    resolved_name = name or "".join(word.capitalize() for word in topic_slug.split("-"))
    resolved_pkg_id = package_id or infer_package_id(resolved_id)

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
        "id": resolved_id,
        "url": f"{canonical}/ImplementationGuide/{resolved_pkg_id}",
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
) -> dict:
    """Stage a package source workspace for ``rh package`` commands."""
    json_files, cql_files = collect_computable_files(computable_dir)
    if not json_files and not cql_files:
        return {"error": "No FHIR JSON or CQL files found in computable directory"}

    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)

    input_dir = workspace_dir / "input"
    examples_dir = input_dir / "examples"
    cql_dir = input_dir / "cql"
    for path in (
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
        [resource_file.name for resource_file in json_files],
        version=version,
        name=name,
        ig_id=ig_id,
        canonical=canonical,
        status=status,
        package_id=resolved_package_id,
        dependencies=dependencies,
    )
    (workspace_dir / "ImplementationGuide.json").write_text(
        json.dumps(ig, indent=2, ensure_ascii=False) + "\n"
    )

    return {
        "workspace_dir": workspace_dir,
        "package_name": resolved_package_id,
        "version": version,
        "json_count": len(json_files),
        "cql_count": len(cql_files),
        "examples_dir": examples_dir,
        "cql_dir": cql_dir,
    }
