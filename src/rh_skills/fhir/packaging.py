"""FHIR NPM package builder.

Generates ``package.json``, ``ImplementationGuide`` resource JSON, and
collects FHIR JSON + CQL files from a computable directory into a
distributable FHIR package.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def generate_package_json(
    topic_slug: str,
    version: str = "1.0.0",
    has_cql: bool = False,
    extra_dependencies: dict[str, str] | None = None,
) -> dict:
    """Build a FHIR NPM package.json dict.

    Args:
        topic_slug: Topic identifier (kebab-case).
        version: SemVer package version.
        has_cql: Whether CQL files are present (adds cql dependency).
        extra_dependencies: Additional IG dependencies to include.
    """
    deps: dict[str, str] = {
        "hl7.fhir.r4.core": "4.0.1",
        "hl7.fhir.us.core": "6.1.0",
        "hl7.fhir.uv.crmi": "1.0.0",
    }
    if has_cql:
        deps["hl7.fhir.uv.cql"] = "2.0.0"
    if extra_dependencies:
        deps.update(extra_dependencies)

    return {
        "name": f"@reason/{topic_slug}",
        "version": version,
        "type": "fhir.ig",
        "fhirVersions": ["4.0.1"],
        "dependencies": deps,
    }


def generate_implementation_guide(
    topic_slug: str,
    resource_files: list[str],
    version: str = "1.0.0",
) -> dict:
    """Build a FHIR ImplementationGuide resource dict.

    Args:
        topic_slug: Topic identifier (kebab-case).
        resource_files: Filenames of FHIR JSON resources (e.g.,
            ``["PlanDefinition-sepsis.json", "Library-sepsis.json"]``).
        version: Package version string.
    """
    resources = []
    for fname in resource_files:
        # Derive reference from filename: PlanDefinition-sepsis.json → PlanDefinition/sepsis
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

    return {
        "resourceType": "ImplementationGuide",
        "id": topic_slug,
        "url": f"http://example.org/fhir/ImplementationGuide/{topic_slug}",
        "version": version,
        "name": "".join(word.capitalize() for word in topic_slug.split("-")),
        "title": topic_slug.replace("-", " ").title(),
        "status": "draft",
        "packageId": f"@reason/{topic_slug}",
        "fhirVersion": ["4.0.1"],
        "definition": {
            "resource": resources,
        },
    }


def collect_computable_files(computable_dir: Path) -> tuple[list[Path], list[Path]]:
    """Collect FHIR JSON and CQL files from a computable directory.

    Returns:
        Tuple of (json_files, cql_files).
    """
    json_files = sorted(computable_dir.glob("*.json"))
    cql_files = sorted(computable_dir.glob("*.cql"))
    return json_files, cql_files


def build_package(
    computable_dir: Path,
    output_dir: Path,
    topic_slug: str,
    version: str = "1.0.0",
) -> dict:
    """Build a FHIR package from computable directory contents.

    Creates ``output_dir`` with package.json, IG resource, and all
    FHIR JSON + CQL files copied from ``computable_dir``.

    Args:
        computable_dir: Source directory with FHIR JSON + CQL.
        output_dir: Target package directory.
        topic_slug: Topic identifier (kebab-case).
        version: Package version string.

    Returns:
        Summary dict with counts and package metadata.
    """
    json_files, cql_files = collect_computable_files(computable_dir)

    if not json_files and not cql_files:
        return {"error": "No FHIR JSON or CQL files found in computable directory"}

    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy resource files
    for f in json_files + cql_files:
        shutil.copy2(f, output_dir / f.name)

    # Generate package.json
    pkg = generate_package_json(
        topic_slug,
        version=version,
        has_cql=bool(cql_files),
    )
    (output_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")

    # Generate ImplementationGuide
    resource_fnames = [f.name for f in json_files]
    ig = generate_implementation_guide(topic_slug, resource_fnames, version=version)
    ig_fname = f"ImplementationGuide-{topic_slug}.json"
    (output_dir / ig_fname).write_text(json.dumps(ig, indent=2) + "\n")

    return {
        "package_name": pkg["name"],
        "version": version,
        "json_count": len(json_files),
        "cql_count": len(cql_files),
        "total_files": len(json_files) + len(cql_files) + 2,  # +package.json +IG
    }
