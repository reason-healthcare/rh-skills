"""Compose a Workbench-ready executable FHIR Bundle and fixture index."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import click

from rh_skills.common import require_topic, require_tracking, repo_root, topic_dir


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
_CANONICAL_KEYS = {
    "definitionCanonical",
    "derivedFrom",
    "sourceCanonical",
    "targetCanonical",
    "valueCanonical",
    "valueSet",
}


class ExecutableBundleError(ValueError):
    """Raised when executable resources or their dependency closure are invalid."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutableBundleError(f"Cannot read JSON from {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temp_path.replace(path)


def _resource_identity(resource: dict[str, Any]) -> tuple[str, str] | None:
    url = resource.get("url")
    version = resource.get("version")
    if isinstance(url, str) and url.strip():
        return url.strip(), version.strip() if isinstance(version, str) and version.strip() else ""
    return None


def _canonical_parts(reference: str) -> tuple[str, str | None]:
    url, separator, version = reference.strip().partition("|")
    return url, version if separator and version else None


def _iter_actions(actions: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(actions, list):
        return
    for action in actions:
        if not isinstance(action, dict):
            continue
        yield action
        yield from _iter_actions(action.get("action"))


def _collect_resource_references(resource: dict[str, Any]) -> list[tuple[str, str]]:
    """Return canonical references declared by computable FHIR resources."""
    refs: list[tuple[str, str]] = []
    resource_type = resource.get("resourceType")

    if resource_type in {"PlanDefinition", "Measure", "ActivityDefinition"}:
        library_refs = resource.get("library", [])
        if isinstance(library_refs, str):
            library_refs = [library_refs]
        if isinstance(library_refs, list):
            refs.extend((value, "library") for value in library_refs if isinstance(value, str))

    if resource_type == "PlanDefinition":
        for action in _iter_actions(resource.get("action")):
            value = action.get("definitionCanonical")
            if isinstance(value, str):
                refs.append((value, "PlanDefinition.action.definitionCanonical"))

    if resource_type == "Library":
        artifacts = resource.get("relatedArtifact", [])
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if not isinstance(artifact, dict) or artifact.get("type") != "depends-on":
                    continue
                value = artifact.get("resource")
                if isinstance(value, str):
                    refs.append((value, "Library.relatedArtifact[type=depends-on].resource"))

    if resource_type == "ValueSet":
        compose = resource.get("compose", {})
        for direction in ("include", "exclude"):
            entries = compose.get(direction, []) if isinstance(compose, dict) else []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                value_sets = entry.get("valueSet", []) if isinstance(entry, dict) else []
                if isinstance(value_sets, str):
                    value_sets = [value_sets]
                if isinstance(value_sets, list):
                    refs.extend((value, f"ValueSet.compose.{direction}.valueSet") for value in value_sets if isinstance(value, str))

    # The CPG collectWith extension binds an ActivityDefinition to its
    # Questionnaire canonical. Keep this explicit instead of treating every
    # extension URL or coding system as a resource dependency.
    if resource_type == "ActivityDefinition":
        for extension in resource.get("extension", []):
            if not isinstance(extension, dict):
                continue
            extension_url = extension.get("url", "")
            value = extension.get("valueCanonical")
            if isinstance(extension_url, str) and "cpg-collectWith" in extension_url and isinstance(value, str):
                refs.append((value, "ActivityDefinition.cpg-collectWith"))

    return refs


def _elm_includes(resource: dict[str, Any]) -> list[tuple[str, str | None, str]]:
    """Read include declarations from FHIR Library.content Attachment elements."""
    if resource.get("resourceType") != "Library":
        return []
    result: list[tuple[str, str | None, str]] = []
    for content in resource.get("content", []):
        if not isinstance(content, dict):
            continue
        if "elm+json" not in str(content.get("contentType", "")):
            continue
        encoded = content.get("data")
        if not isinstance(encoded, str):
            raise ExecutableBundleError(
                f"Library/{resource.get('id')}: ELM content is missing base64 data"
            )
        try:
            elm = json.loads(base64.b64decode(encoded, validate=True))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ExecutableBundleError(
                f"Library/{resource.get('id')}: embedded ELM JSON is invalid: {exc}"
            ) from exc
        library = elm.get("library", {}) if isinstance(elm, dict) else {}
        includes = library.get("includes", {}) if isinstance(library, dict) else {}
        definitions = includes.get("def", []) if isinstance(includes, dict) else []
        if not isinstance(definitions, list):
            continue
        for definition in definitions:
            if not isinstance(definition, dict):
                continue
            path = definition.get("path")
            if isinstance(path, str) and path:
                version = definition.get("version")
                result.append((path, version if isinstance(version, str) and version else None, "ELM include"))
    return result


def _decode_library_content(resource: dict[str, Any], content_type: str) -> list[bytes]:
    decoded: list[bytes] = []
    content = resource.get("content", [])
    if not isinstance(content, list):
        raise ExecutableBundleError(f"Library/{resource.get('id')}: content must be an array")
    for item in content:
        if not isinstance(item, dict) or item.get("contentType") != content_type:
            continue
        encoded = item.get("data")
        if not isinstance(encoded, str):
            raise ExecutableBundleError(
                f"Library/{resource.get('id')}: {content_type} item is missing base64 data"
            )
        try:
            decoded.append(base64.b64decode(encoded, validate=True))
        except (ValueError, base64.binascii.Error) as exc:
            raise ExecutableBundleError(
                f"Library/{resource.get('id')}: invalid base64 in {content_type} content: {exc}"
            ) from exc
    return decoded


def _elm_definition_names(elm: dict[str, Any]) -> set[str]:
    library = elm.get("library", {}) if isinstance(elm, dict) else {}
    statements = library.get("statements", {}) if isinstance(library, dict) else {}
    definitions = statements.get("def", []) if isinstance(statements, dict) else []
    return {
        str(definition.get("name"))
        for definition in definitions
        if isinstance(definition, dict) and isinstance(definition.get("name"), str)
    }


def _validate_library_content(resources: list[dict[str, Any]]) -> dict[str, tuple[set[str], set[str]]]:
    """Check CQL and ELM identity/content and return their define names by Library URL."""
    result: dict[str, tuple[set[str], set[str]]] = {}
    for resource in resources:
        if resource.get("resourceType") != "Library":
            continue
        url = resource.get("url")
        cql_contents = _decode_library_content(resource, "text/cql")
        elm_contents = _decode_library_content(resource, "application/elm+json")
        if cql_contents and not elm_contents:
            raise ExecutableBundleError(
                f"Library/{resource.get('id')}: embedded CQL has no compiled application/elm+json content"
            )
        if len(cql_contents) > 1 or len(elm_contents) > 1:
            raise ExecutableBundleError(
                f"Library/{resource.get('id')}: expected at most one text/cql and one ELM attachment"
            )
        cql_names: set[str] = set()
        elm_names: set[str] = set()
        if cql_contents:
            try:
                source = cql_contents[0].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ExecutableBundleError(
                    f"Library/{resource.get('id')}: CQL source is not UTF-8"
                ) from exc
            identity_match = re.search(
                r"^\s*library\s+([A-Za-z_][A-Za-z0-9_]*)\s+version\s+'([^']+)'",
                source,
                flags=re.MULTILINE | re.IGNORECASE,
            )
            if not identity_match:
                raise ExecutableBundleError(
                    f"Library/{resource.get('id')}: CQL source is missing `library Name version 'x'` identity"
                )
            cql_name, cql_version = identity_match.groups()
            if cql_name != resource.get("name") or cql_version != resource.get("version"):
                raise ExecutableBundleError(
                    f"Library/{resource.get('id')}: CQL identity {cql_name}|{cql_version} does not match "
                    f"FHIR Library identity {resource.get('name')}|{resource.get('version')}"
                )
            cql_names = set(re.findall(
                r'^\s*define\s+"([^"]+)"\s*:', source, flags=re.MULTILINE | re.IGNORECASE
            ))
            cql_names.update(re.findall(
                r"^\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\s*:",
                source,
                flags=re.MULTILINE | re.IGNORECASE,
            ))
        if elm_contents:
            try:
                elm = json.loads(elm_contents[0])
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutableBundleError(
                    f"Library/{resource.get('id')}: embedded ELM JSON is invalid: {exc}"
                ) from exc
            library = elm.get("library", {}) if isinstance(elm, dict) else {}
            identifier = library.get("identifier", {}) if isinstance(library, dict) else {}
            elm_name = identifier.get("id") if isinstance(identifier, dict) else None
            elm_version = identifier.get("version") if isinstance(identifier, dict) else None
            if elm_name != resource.get("name") or elm_version != resource.get("version"):
                raise ExecutableBundleError(
                    f"Library/{resource.get('id')}: ELM identity {elm_name}|{elm_version} does not match "
                    f"FHIR Library identity {resource.get('name')}|{resource.get('version')}"
                )
            elm_names = _elm_definition_names(elm)
            if cql_names and not cql_names.issubset(elm_names):
                missing = sorted(cql_names - elm_names)
                raise ExecutableBundleError(
                    f"Library/{resource.get('id')}: compiled ELM is missing CQL definitions: {', '.join(missing)}"
                )
        if isinstance(url, str):
            result[url] = (cql_names, elm_names)
    return result


def _expansion_concept_count(contains: Any) -> int:
    if not isinstance(contains, list):
        return 0
    return sum(
        1 + _expansion_concept_count(item.get("contains"))
        for item in contains
        if isinstance(item, dict)
    )


def _validate_value_set_expansions(resources: list[dict[str, Any]]) -> None:
    """Require complete, version-pinned local terminology for executable ValueSets."""
    for resource in resources:
        if resource.get("resourceType") != "ValueSet":
            continue
        resource_id = resource.get("id", "unknown")
        compose = resource.get("compose")
        includes = compose.get("include") if isinstance(compose, dict) else None
        if not isinstance(includes, list) or not includes:
            raise ExecutableBundleError(
                f"ValueSet/{resource_id}: executable terminology requires compose.include"
            )
        for index, include in enumerate(includes):
            if not isinstance(include, dict) or not isinstance(include.get("system"), str):
                raise ExecutableBundleError(
                    f"ValueSet/{resource_id}: compose.include[{index}] is missing system"
                )
            if not isinstance(include.get("version"), str) or not include["version"].strip():
                raise ExecutableBundleError(
                    f"ValueSet/{resource_id}: compose.include[{index}] is not version-pinned"
                )
        expansion = resource.get("expansion")
        contains = expansion.get("contains") if isinstance(expansion, dict) else None
        total = expansion.get("total") if isinstance(expansion, dict) else None
        if not isinstance(total, int) or total < 0 or not isinstance(contains, list):
            raise ExecutableBundleError(
                f"ValueSet/{resource_id}: executable terminology requires expansion.total and expansion.contains"
            )
        if _expansion_concept_count(contains) != total:
            raise ExecutableBundleError(
                f"ValueSet/{resource_id}: expansion is incomplete; total {total} does not match local membership"
            )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _validate_evaluation_date(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutableBundleError("Fixture evaluation date is required and must be RFC 3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutableBundleError(
            f"Fixture evaluation date is not RFC 3339: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise ExecutableBundleError("Fixture evaluation date must include a timezone")
    return value


def _ensure_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ExecutableBundleError(f"{label} escapes its configured source directory: {path}") from exc
    return resolved


def _plan_cql_identifiers(resource: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for action in _iter_actions(resource.get("action")):
        for condition in action.get("condition", []) if isinstance(action.get("condition"), list) else []:
            expression = condition.get("expression", {}) if isinstance(condition, dict) else {}
            if (
                isinstance(expression, dict)
                and expression.get("language") == "text/cql-identifier"
                and isinstance(expression.get("expression"), str)
            ):
                names.add(expression["expression"].strip())
    return names


def _validate_closure(resources: list[dict[str, Any]], root_canonical: str) -> dict[str, Any]:
    by_url: dict[str, list[dict[str, Any]]] = {}
    seen_identity: set[tuple[str, str]] = set()
    seen_resource_id: set[tuple[str, str]] = set()

    for resource in resources:
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not isinstance(resource_type, str) or not resource_type:
            raise ExecutableBundleError("A computable JSON resource is missing resourceType")
        if not isinstance(resource_id, str) or not resource_id:
            raise ExecutableBundleError(f"{resource_type} resource is missing id")
        key = (resource_type, resource_id)
        if key in seen_resource_id:
            raise ExecutableBundleError(f"Duplicate resource identity {resource_type}/{resource_id}")
        seen_resource_id.add(key)

        identity = _resource_identity(resource)
        if identity:
            if identity in seen_identity:
                raise ExecutableBundleError(f"Duplicate canonical and version: {identity[0]}|{identity[1]}")
            seen_identity.add(identity)
            by_url.setdefault(identity[0], []).append(resource)

    def resolve(reference: str, source: str) -> dict[str, Any]:
        url, version = _canonical_parts(reference)
        candidates = by_url.get(url, [])
        if version is not None:
            matches = [candidate for candidate in candidates if _resource_identity(candidate) == (url, version)]
            if not matches:
                raise ExecutableBundleError(f"Unresolved {source} dependency: {reference}")
            return matches[0]
        if not candidates:
            raise ExecutableBundleError(f"Unresolved {source} dependency: {reference}")
        if len(candidates) > 1:
            raise ExecutableBundleError(
                f"Ambiguous unversioned {source} dependency {reference}; candidates must be versioned"
            )
        return candidates[0]

    root_resource = resolve(root_canonical, "root")
    _, root_version = _canonical_parts(root_canonical)
    if root_version is None:
        raise ExecutableBundleError("Executable root canonical must include `|version`")
    if root_resource.get("resourceType") != "PlanDefinition":
        raise ExecutableBundleError(
            f"Executable root must be a PlanDefinition; got {root_resource.get('resourceType')}"
        )

    library_definitions = _validate_library_content(resources)
    _validate_value_set_expansions(resources)
    for resource in resources:
        for reference, source in _collect_resource_references(resource):
            resolve(reference, source)
        for path, version, source in _elm_includes(resource):
            matches = [
                candidate for candidate in resources
                if candidate.get("resourceType") == "Library"
                and (candidate.get("name") == path or candidate.get("id") == path)
                and (version is None or candidate.get("version") == version)
            ]
            if not matches:
                version_text = f"|{version}" if version else ""
                raise ExecutableBundleError(f"Unresolved {source} dependency: {path}{version_text}")
            if version is None and len(matches) > 1:
                raise ExecutableBundleError(f"Ambiguous unversioned {source} dependency: {path}")

        if resource.get("resourceType") == "PlanDefinition":
            identifiers = _plan_cql_identifiers(resource)
            if identifiers:
                library_refs = resource.get("library", [])
                if isinstance(library_refs, str):
                    library_refs = [library_refs]
                available: set[str] = set()
                if isinstance(library_refs, list):
                    for reference in library_refs:
                        url, _ = _canonical_parts(reference) if isinstance(reference, str) else ("", None)
                        definitions = library_definitions.get(url)
                        if definitions:
                            available.update(definitions[0])
                            available.update(definitions[1])
                missing = identifiers - available
                if missing:
                    raise ExecutableBundleError(
                        f"PlanDefinition/{resource.get('id')} references CQL identifiers not defined "
                        f"by its linked Library: {', '.join(sorted(missing))}"
                    )

    def reject_placeholders(value: Any, resource_type: str, resource_id: str, path: str = "$") -> None:
        if isinstance(value, str) and "TODO:MCP-UNREACHABLE" in value:
            raise ExecutableBundleError(
                f"Unresolved terminology placeholder in {resource_type}/{resource_id} at {path}"
            )
        if isinstance(value, dict):
            for key, nested in value.items():
                reject_placeholders(nested, resource_type, resource_id, f"{path}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                reject_placeholders(nested, resource_type, resource_id, f"{path}[{index}]")

    for resource in resources:
        reject_placeholders(resource, resource["resourceType"], resource["id"])

    return root_resource


def _description_from_summary(path: Path) -> str | None:
    if not path.is_file():
        return None
    paragraphs: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if paragraphs:
                break
            continue
        paragraphs.append(line)
    return " ".join(paragraphs) or None


def _fixture_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    entries = bundle.get("entry", [])
    if not isinstance(entries, list):
        return []
    return [entry.get("resource") for entry in entries if isinstance(entry, dict) and isinstance(entry.get("resource"), dict)]


def _validate_fixture_bundle(path: Path, patient_id: str) -> dict[str, Any]:
    bundle = _read_json(path)
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise ExecutableBundleError(f"Fixture must be a FHIR Bundle: {path}")
    patients = [
        resource for resource in _fixture_resources(bundle)
        if resource.get("resourceType") == "Patient" and resource.get("id") == patient_id
    ]
    if len(patients) != 1:
        raise ExecutableBundleError(
            f"Fixture {path} must contain exactly one Patient/{patient_id}; found {len(patients)}"
        )
    return bundle


def _write_executable_output_atomically(
    output_dir: Path,
    bundle_resource: dict[str, Any],
    fixture_index: dict[str, Any],
    fixture_payloads: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    """Publish a fully composed output directory only after all validation succeeds."""
    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_parent)
    )
    previous = output_parent / f".{output_dir.name}.previous"
    if previous.exists():
        shutil.rmtree(previous)

    try:
        _write_json(staging / "executable-bundle.json", bundle_resource)
        _write_json(staging / "fixtures" / "index.json", fixture_index)
        for case_id, bundle in sorted(fixture_payloads.items()):
            _write_json(staging / "fixtures" / f"{case_id}.json", bundle)
        _write_json(staging / "executable-manifest.json", manifest)

        if output_dir.exists():
            output_dir.replace(previous)
        staging.replace(output_dir)
    except Exception:
        if not output_dir.exists() and previous.exists():
            previous.replace(output_dir)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if previous.exists():
            shutil.rmtree(previous)


def compose_executable_bundle(
    computable_dir: Path,
    fixture_manifest: Path,
    fixture_dir: Path,
    output_dir: Path,
    root_canonical: str,
    evaluation_date: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic Workbench executable Bundle and fixture index."""
    if not computable_dir.is_dir():
        raise ExecutableBundleError(f"Computable directory not found: {computable_dir}")
    if not fixture_manifest.is_file():
        raise ExecutableBundleError(f"Fixture manifest not found: {fixture_manifest}")
    if not fixture_dir.is_dir():
        raise ExecutableBundleError(f"Fixture directory not found: {fixture_dir}")
    evaluation_date = _validate_evaluation_date(evaluation_date)
    fixture_root = fixture_dir.resolve()

    resources: list[dict[str, Any]] = []
    source_paths: dict[tuple[str, str], str] = {}
    for path in sorted(computable_dir.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict) or "resourceType" not in payload:
            continue
        resources.append(payload)
        source_paths[(payload.get("resourceType", ""), payload.get("id", ""))] = str(path)
    if not resources:
        raise ExecutableBundleError(f"No FHIR JSON resources found in {computable_dir}")

    root_resource = _validate_closure(resources, root_canonical)
    manifest = _read_json(fixture_manifest)
    cases = manifest.get("cases", []) if isinstance(manifest, dict) else []
    if not isinstance(cases, list) or not cases:
        raise ExecutableBundleError(f"Fixture manifest has no cases: {fixture_manifest}")

    fixture_entries: list[dict[str, Any]] = []
    fixture_payloads: dict[str, dict[str, Any]] = {}
    expected_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ExecutableBundleError("Each fixture manifest case must be an object")
        case_id = case.get("id")
        title = case.get("title")
        if not isinstance(case_id, str) or not _ID_RE.fullmatch(case_id):
            raise ExecutableBundleError(f"Invalid fixture case id: {case_id!r}")
        if case_id in expected_ids:
            raise ExecutableBundleError(f"Duplicate fixture case id: {case_id}")
        expected_ids.add(case_id)
        if not isinstance(title, str) or not title.strip():
            raise ExecutableBundleError(f"Fixture case {case_id} is missing title")

        case_dir = _ensure_within(fixture_dir / case_id, fixture_root, "Fixture case")
        assertion_path = case_dir / "assertions.json"
        source_bundle_path = case_dir / "bundle.json"
        _ensure_within(assertion_path, fixture_root, "Fixture assertion")
        _ensure_within(source_bundle_path, fixture_root, "Fixture bundle")
        if not assertion_path.is_file() or not source_bundle_path.is_file():
            raise ExecutableBundleError(
                f"Fixture case {case_id} must contain assertions.json and bundle.json under {case_dir}"
            )
        assertions = _read_json(assertion_path)
        context = assertions.get("evaluationContext", {}) if isinstance(assertions, dict) else {}
        patient_id = context.get("patientId") if isinstance(context, dict) else None
        period = context.get("measurementPeriod") if isinstance(context, dict) else None
        if not isinstance(patient_id, str) or not patient_id:
            raise ExecutableBundleError(f"Fixture {case_id} is missing evaluationContext.patientId")
        if not isinstance(period, dict) or not isinstance(period.get("start"), str) or not isinstance(period.get("end"), str):
            raise ExecutableBundleError(f"Fixture {case_id} is missing measurementPeriod.start/end")
        if not isinstance(period.get("startInclusive"), bool) or not isinstance(period.get("endInclusive"), bool):
            raise ExecutableBundleError(f"Fixture {case_id} must declare measurement-period inclusivity")

        bundle = _validate_fixture_bundle(source_bundle_path, patient_id)
        resources_in_fixture = _fixture_resources(bundle)
        encounters: list[dict[str, Any]] = []
        for resource in resources_in_fixture:
            if resource.get("resourceType") != "Encounter":
                continue
            subject = resource.get("subject")
            if not isinstance(subject, dict) or not isinstance(subject.get("reference"), str):
                raise ExecutableBundleError(
                    f"Fixture {case_id} has Encounter/{resource.get('id', 'unknown')} without subject.reference"
                )
            if subject["reference"] == f"Patient/{patient_id}":
                encounters.append(resource)
        encounter_ref = None
        if len(encounters) == 1 and isinstance(encounters[0].get("id"), str):
            encounter_ref = f"Encounter/{encounters[0]['id']}"

        fixture_payloads[case_id] = bundle
        entry: dict[str, Any] = {
            "id": case_id,
            "title": title.strip(),
            "subject": f"Patient/{patient_id}",
            "dataBundlePath": f"fixtures/{case_id}.json",
            "measurementPeriod": period,
        }
        summary_ref = case.get("summary")
        summary_path = case_dir / "SUMMARY.md"
        if isinstance(summary_ref, str):
            candidate = fixture_manifest.parent / summary_ref
            if candidate.is_file():
                summary_path = candidate
        description = _description_from_summary(summary_path)
        if description:
            entry["description"] = description
        entry["evaluationDate"] = evaluation_date
        if encounter_ref:
            entry["encounter"] = encounter_ref
            practitioners: set[str] = set()
            service_providers: set[str] = set()
            for encounter in encounters:
                participants = encounter.get("participant", [])
                if not isinstance(participants, list):
                    raise ExecutableBundleError(
                        f"Fixture {case_id} has malformed Encounter.participant"
                    )
                for participant in participants:
                    if not isinstance(participant, dict):
                        raise ExecutableBundleError(
                            f"Fixture {case_id} has malformed Encounter.participant entry"
                        )
                    individual = participant.get("individual")
                    if individual is None:
                        continue
                    if not isinstance(individual, dict) or not isinstance(individual.get("reference"), str):
                        raise ExecutableBundleError(
                            f"Fixture {case_id} has malformed Encounter.participant.individual"
                        )
                    practitioners.add(individual["reference"])
                service_provider = encounter.get("serviceProvider")
                if service_provider is None:
                    continue
                if not isinstance(service_provider, dict) or not isinstance(service_provider.get("reference"), str):
                    raise ExecutableBundleError(
                        f"Fixture {case_id} has malformed Encounter.serviceProvider"
                    )
                service_providers.add(service_provider["reference"])
            if len(practitioners) == 1:
                entry["practitioner"] = next(iter(practitioners))
            if len(service_providers) == 1:
                entry["organization"] = next(iter(service_providers))
        parameters = context.get("parameters") if isinstance(context, dict) else None
        if not isinstance(parameters, dict):
            parameters = assertions.get("parameters") if isinstance(assertions, dict) else None
        if isinstance(parameters, dict) and parameters:
            entry["parameters"] = parameters
        fixture_entries.append(entry)

    bundle_resource = {
        "resourceType": "Bundle",
        "id": "executable-cpg",
        "type": "collection",
        "entry": [{"resource": resource} for resource in sorted(
            resources,
            key=lambda item: (
                str(item.get("resourceType", "")),
                str(item.get("url", "")),
                str(item.get("version", "")),
                str(item.get("id", "")),
            ),
        )],
    }
    fixture_index = {"fixtures": fixture_entries}
    manifest_output = {
        "rootCanonical": root_canonical,
        "rootResourceType": root_resource.get("resourceType"),
        "rootId": root_resource.get("id"),
        "bundlePath": "executable-bundle.json",
        "fixtureIndexPath": "fixtures/index.json",
        "resourceCount": len(resources),
        "resources": [
            {
                "resourceType": resource.get("resourceType"),
                "id": resource.get("id"),
                "canonical": _resource_identity(resource),
                "sourcePath": source_paths.get((resource.get("resourceType", ""), resource.get("id", ""))),
            }
            for resource in sorted(resources, key=lambda item: (str(item.get("resourceType", "")), str(item.get("id", ""))))
        ],
    }
    manifest_output["checksums"] = {
        "algorithm": "sha256",
        "bundle": _sha256_json(bundle_resource),
        "fixtureIndex": _sha256_json(fixture_index),
        "rootResource": _sha256_json(root_resource),
        "resources": [
            {
                "resourceType": resource["resourceType"],
                "id": resource["id"],
                "sha256": _sha256_json(resource),
            }
            for resource in sorted(
                resources,
                key=lambda item: (str(item.get("resourceType", "")), str(item.get("id", ""))),
            )
        ],
    }
    _write_executable_output_atomically(
        output_dir,
        bundle_resource,
        fixture_index,
        fixture_payloads,
        manifest_output,
    )
    return {
        "bundle": output_dir / "executable-bundle.json",
        "index": output_dir / "fixtures" / "index.json",
        "manifest": output_dir / "executable-manifest.json",
        "resource_count": len(resources),
        "fixture_count": len(fixture_entries),
        "root_canonical": root_canonical,
    }


@click.command("compose-executable")
@click.argument("topic")
@click.option("--root-canonical", required=True, help="Versioned PlanDefinition canonical URL, e.g. https://example.org/fhir/PlanDefinition/x|1.0.0")
@click.option("--fixture-manifest", type=click.Path(path_type=Path), default=None, help="Fixture manifest JSON; defaults to process/fixtures/manifest.json")
@click.option("--fixture-dir", type=click.Path(path_type=Path), default=None, help="Per-case fixture directory; defaults to process/fixtures/connectathon-cases")
@click.option("--output-dir", type=click.Path(path_type=Path), default=None, help="Executable output directory; defaults to process/package-workspace/executable")
@click.option("--evaluation-date", required=True, help="Fixed RFC 3339 evaluation time included in each fixture index entry")
def compose_executable(topic, root_canonical, fixture_manifest, fixture_dir, output_dir, evaluation_date):
    """Compose a closed FHIR Bundle and Workbench fixture index."""
    tracking = require_tracking()
    require_topic(tracking, topic)
    td = topic_dir(topic)
    manifest_path = fixture_manifest or (td / "process" / "fixtures" / "manifest.json")
    fixture_root = fixture_dir or (td / "process" / "fixtures" / "connectathon-cases")
    out_root = output_dir or (td / "process" / "package-workspace" / "executable")
    try:
        result = compose_executable_bundle(
            td / "computable",
            manifest_path,
            fixture_root,
            out_root,
            root_canonical,
            evaluation_date,
        )
    except ExecutableBundleError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Executable Bundle: {result['bundle']}")
    click.echo(f"Fixture index: {result['index']}")
    click.echo(f"Manifest: {result['manifest']}")
    click.echo(f"Resources: {result['resource_count']} · fixtures: {result['fixture_count']}")
    click.echo(f"Root: {result['root_canonical']}")
