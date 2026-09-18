"""Import a pinned, precompiled external CQL library into a topic."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import click

from rh_skills.common import (
    append_topic_event,
    now_iso,
    require_topic,
    require_tracking,
    repo_root,
    save_tracking,
    sha256_file,
    topic_dir,
)


_CQL_LIBRARY_RE = re.compile(
    r"^\s*library\s+([A-Za-z][A-Za-z0-9_.]*)\s+version\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE | re.MULTILINE,
)
_CQL_INCLUDE_RE = re.compile(
    r"^\s*include\s+([A-Za-z][A-Za-z0-9_.]*)\s+version\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE | re.MULTILINE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_object(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise click.ClickException(f"Manifest field {name!r} must be an object")
    return value


def _required_string(mapping: dict, field: str, path: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException(f"Manifest field {path}.{field} must be a non-empty string")
    return value.strip()


def _manifest_input(manifest_dir: Path, raw_path: object, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise click.ClickException(f"Manifest field {label} must be a local relative path")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise click.ClickException(f"Manifest input {label} must be relative to the manifest directory")
    unresolved = manifest_dir / candidate
    try:
        unresolved.resolve(strict=False).relative_to(manifest_dir)
    except ValueError as exc:
        raise click.ClickException(f"Manifest input {label} escapes the manifest directory") from exc
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as exc:
        raise click.ClickException(f"Manifest input {label} cannot be read: {exc}") from exc
    try:
        resolved.relative_to(manifest_dir)
    except ValueError as exc:
        raise click.ClickException(f"Manifest input {label} escapes the manifest directory") from exc
    if not resolved.is_file():
        raise click.ClickException(f"Manifest input {label} is not a file: {resolved}")
    return resolved


def _assert_digest(path: Path, expected: object, label: str) -> str:
    if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected):
        raise click.ClickException(f"Manifest field {label} must be a lowercase SHA-256 digest")
    actual = sha256_file(path)
    if actual != expected:
        raise click.ClickException(f"SHA-256 mismatch for {label}: expected {expected}, got {actual}")
    return actual


def _load_manifest(path: Path) -> dict:
    manifest_path = path.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Cannot read import manifest {manifest_path}: {exc}") from exc
    manifest = _require_object(manifest, "root")
    resource = _require_object(manifest.get("resource"), "resource")
    source = _require_object(manifest.get("source"), "source")
    compiler = _require_object(source.get("compile_tool"), "source.compile_tool")
    cql = _require_object(manifest.get("cql"), "cql")
    elm = _require_object(manifest.get("elm"), "elm")

    resource_id = _required_string(resource, "id", "resource")
    name = _required_string(resource, "name", "resource")
    version = _required_string(resource, "version", "resource")
    canonical = _required_string(resource, "url", "resource")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,64}", resource_id):
        raise click.ClickException("Manifest resource.id must be a FHIR id (1-64 letters, digits, dots, or hyphens)")
    parsed_url = urlparse(canonical)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc or "|" in canonical:
        raise click.ClickException("Manifest resource.url must be an absolute HTTP(S) canonical without a version")

    compiler_inputs = compiler.get("inputs", [])
    if not isinstance(compiler_inputs, list):
        raise click.ClickException("Manifest field source.compile_tool.inputs must be an array when present")
    captured_inputs: list[dict[str, str]] = []
    for index, entry in enumerate(compiler_inputs):
        input_entry = _require_object(entry, f"source.compile_tool.inputs[{index}]")
        input_name = _required_string(input_entry, "name", f"source.compile_tool.inputs[{index}]")
        input_path = _manifest_input(
            manifest_dir=manifest_path.parent.resolve(strict=True),
            raw_path=input_entry.get("path"),
            label=f"source.compile_tool.inputs[{index}].path",
        )
        input_digest = _assert_digest(
            input_path,
            input_entry.get("sha256"),
            f"source.compile_tool.inputs[{index}].sha256",
        )
        captured_inputs.append({
            "name": input_name,
            "path": input_entry["path"],
            "sha256": input_digest,
        })

    source_metadata = {
        "url": _required_string(source, "url", "source"),
        "tag": _required_string(source, "tag", "source"),
        "license": _required_string(source, "license", "source"),
        "compile_tool": {
            "name": _required_string(compiler, "name", "source.compile_tool"),
            "version": _required_string(compiler, "version", "source.compile_tool"),
            "options": compiler.get("options"),
            "inputs": captured_inputs,
        },
    }
    options = source_metadata["compile_tool"]["options"]
    if not isinstance(options, list) or any(not isinstance(option, str) for option in options):
        raise click.ClickException("Manifest field source.compile_tool.options must be an array of strings")

    manifest_dir = manifest_path.parent.resolve(strict=True)
    cql_path = _manifest_input(manifest_dir, cql.get("path"), "cql.path")
    elm_path = _manifest_input(manifest_dir, elm.get("path"), "elm.path")
    cql_digest = _assert_digest(cql_path, cql.get("sha256"), "cql.sha256")
    elm_digest = _assert_digest(elm_path, elm.get("sha256"), "elm.sha256")

    try:
        cql_source = cql_path.read_text(encoding="utf-8")
        elm_document = json.loads(elm_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Cannot read CQL/ELM inputs: {exc}") from exc
    cql_identity = _CQL_LIBRARY_RE.search(cql_source)
    if not cql_identity or (cql_identity.group(1), cql_identity.group(2)) != (name, version):
        actual = (cql_identity.group(1), cql_identity.group(2)) if cql_identity else None
        raise click.ClickException(
            f"CQL library identifier/version mismatch: expected {(name, version)}, got {actual}"
        )
    if not isinstance(elm_document, dict) or not isinstance(elm_document.get("library"), dict):
        raise click.ClickException("ELM JSON must contain a library object")
    identifier = elm_document["library"].get("identifier")
    if not isinstance(identifier, dict):
        raise click.ClickException("ELM JSON must contain library.identifier")
    elm_identity = (identifier.get("id"), identifier.get("version"))
    if elm_identity != (name, version):
        raise click.ClickException(
            f"ELM library identifier/version mismatch: expected {(name, version)}, got {elm_identity}"
        )
    expected_cql_name = f"{name}-{version}.cql"
    expected_elm_name = f"{name}-{version}.json"
    if cql_path.name != expected_cql_name:
        raise click.ClickException(f"CQL input must be named {expected_cql_name!r} for versioned include resolution")
    if elm_path.name != expected_elm_name:
        raise click.ClickException(f"ELM input must be named {expected_elm_name!r}")

    return {
        "resource": {"id": resource_id, "name": name, "version": version, "url": canonical},
        "source": source_metadata,
        "cql_path": cql_path,
        "cql_bytes": cql_path.read_bytes(),
        "cql_sha256": cql_digest,
        "elm_path": elm_path,
        "elm_bytes": elm_path.read_bytes(),
        "elm_sha256": elm_digest,
    }


def _fhir_library(imported: dict) -> dict:
    resource = imported["resource"]
    return {
        "resourceType": "Library",
        "id": resource["id"],
        "url": resource["url"],
        "version": resource["version"],
        "name": resource["name"],
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/library-type",
                "code": "logic-library",
                "display": "Logic Library",
            }]
        },
        "content": [
            {
                "contentType": "text/cql",
                "data": base64.b64encode(imported["cql_bytes"]).decode("ascii"),
            },
            {
                "contentType": "application/elm+json",
                "data": base64.b64encode(imported["elm_bytes"]).decode("ascii"),
            },
        ],
    }


def _library_identities(computable_dir: Path, imported: dict) -> list[tuple[Path, dict]]:
    """Find FHIR Libraries for CQL files that include the imported library."""
    target = imported["resource"]
    matches: list[tuple[Path, dict]] = []
    for cql_path in sorted(computable_dir.glob("*.cql")):
        if cql_path.name == f"{target['name']}-{target['version']}.cql":
            continue
        source = cql_path.read_text(encoding="utf-8")
        includes = {(match.group(1), match.group(2)) for match in _CQL_INCLUDE_RE.finditer(source)}
        if (target["name"], target["version"]) not in includes:
            continue
        identity = _CQL_LIBRARY_RE.search(source)
        if not identity:
            raise click.ClickException(f"Cannot identify CQL library declared by {cql_path}")
        candidates = []
        for library_path in sorted(computable_dir.glob("Library-*.json")):
            try:
                library = json.loads(library_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise click.ClickException(f"Cannot read {library_path}: {exc}") from exc
            if (
                isinstance(library, dict)
                and library.get("resourceType") == "Library"
                and library.get("name") == identity.group(1)
            ):
                candidates.append((library_path, library))
        if len(candidates) != 1:
            raise click.ClickException(
                f"Expected one FHIR Library matching CQL {identity.group(1)!r} in {computable_dir}; "
                f"found {len(candidates)}"
            )
        matches.extend(candidates)
    if not matches:
        raise click.ClickException(
            f"No topic CQL library includes {target['name']} version {target['version']}; "
            "import would create an unreferenced dependency"
        )
    # Deduplicate when a topic has several CQL files that include one Library.
    unique = {path: resource for path, resource in matches}
    return [(path, unique[path]) for path in sorted(unique)]


def _link_dependency(resource: dict, dependency: dict) -> bool:
    canonical = dependency["url"]
    version = dependency["version"]
    expected = f"{canonical}|{version}"
    related = resource.get("relatedArtifact") or []
    if not isinstance(related, list):
        raise click.ClickException(f"Library/{resource.get('id')} relatedArtifact must be an array")
    for entry in related:
        if not isinstance(entry, dict) or entry.get("type") != "depends-on":
            continue
        existing = str(entry.get("resource") or "")
        if existing.split("|", 1)[0] == canonical:
            if existing != expected:
                raise click.ClickException(
                    f"Library/{resource.get('id')} already depends on {existing}, expected {expected}"
                )
            return False
    related.append({"type": "depends-on", "resource": expected})
    resource["relatedArtifact"] = related
    return True


def _relative_repo_path(path: Path) -> str:
    root = repo_root().resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise click.ClickException(f"Output path escapes the current repository: {path}") from exc


def _update_tracking_checksum(topic_entry: dict, relative_path: str, digest: str) -> None:
    for entry in topic_entry.get("computable", []) or []:
        if not isinstance(entry, dict):
            continue
        if relative_path not in (entry.get("files") or []):
            continue
        checksums = entry.setdefault("checksums", {})
        checksums[relative_path] = digest


@click.command("import-library")
@click.argument("topic")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def import_library(topic: str, manifest: Path) -> None:
    """Import a locally pinned CQL/ELM library dependency into a topic."""
    imported = _load_manifest(manifest)
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)
    computable_dir = topic_dir(topic) / "computable"
    computable_dir.mkdir(parents=True, exist_ok=True)

    resource_identity = imported["resource"]
    cql_name = f"{resource_identity['name']}-{resource_identity['version']}.cql"
    elm_name = f"{resource_identity['name']}-{resource_identity['version']}.json"
    library_name = f"Library-{resource_identity['id']}.json"
    destinations = {
        computable_dir / cql_name: imported["cql_bytes"],
        computable_dir / "elm" / elm_name: imported["elm_bytes"],
        computable_dir / library_name: json.dumps(
            _fhir_library(imported), indent=2, ensure_ascii=False
        ).encode("utf-8") + b"\n",
    }

    # Fail before writing if any destination is already owned by different content.
    for path, content in destinations.items():
        if path.exists() and path.read_bytes() != content:
            raise click.ClickException(f"Refusing to overwrite non-matching dependency output: {path}")

    linked_resources = _library_identities(computable_dir, imported)
    linked_updates: list[tuple[Path, bytes]] = []
    dependency_ref = {
        "url": resource_identity["url"],
        "version": resource_identity["version"],
    }
    for path, library in linked_resources:
        if _link_dependency(library, dependency_ref):
            linked_updates.append((
                path,
                json.dumps(library, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
            ))

    entry_name = f"external-library-{resource_identity['name']}-{resource_identity['version']}"
    imported_entry = {
        "name": entry_name,
        "files": [_relative_repo_path(path) for path in destinations],
        "created_at": now_iso(),
        "checksums": {
            _relative_repo_path(path): hashlib.sha256(content).hexdigest()
            for path, content in destinations.items()
        },
        "converged_from": [],
        "strategy": "external-dependency",
        "external_dependency": {
            "canonical": resource_identity["url"],
            "name": resource_identity["name"],
            "version": resource_identity["version"],
            "manifest": _relative_repo_path(manifest),
            "source": imported["source"],
            "cql_sha256": imported["cql_sha256"],
            "elm_sha256": imported["elm_sha256"],
        },
    }
    prior_entries = topic_entry.get("computable", []) or []
    existing_entry = next(
        (entry for entry in prior_entries if isinstance(entry, dict) and entry.get("name") == entry_name),
        None,
    )
    if existing_entry and existing_entry.get("external_dependency") != imported_entry["external_dependency"]:
        raise click.ClickException(f"Tracking entry {entry_name!r} conflicts with this manifest")
    if not existing_entry:
        topic_entry.setdefault("computable", []).append(imported_entry)

    changed = not existing_entry or bool(linked_updates) or any(
        not path.exists() for path in destinations
    )
    if not changed:
        click.echo(f"Dependency already imported: {resource_identity['name']} {resource_identity['version']}")
        return

    for path, content in destinations.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
    for path, content in linked_updates:
        path.write_bytes(content)
        relative_path = _relative_repo_path(path)
        _update_tracking_checksum(topic_entry, relative_path, hashlib.sha256(content).hexdigest())

    topic_entry.setdefault("events", [])
    append_topic_event(
        tracking,
        topic,
        "external_cql_library_imported",
        f"Imported pinned external CQL library {resource_identity['name']} {resource_identity['version']}",
    )
    save_tracking(tracking)
    click.echo(f"Imported Library/{resource_identity['id']} ({resource_identity['url']}|{resource_identity['version']})")
    click.echo(f"CQL: {computable_dir / cql_name}")
    click.echo(f"ELM: {computable_dir / 'elm' / elm_name}")
