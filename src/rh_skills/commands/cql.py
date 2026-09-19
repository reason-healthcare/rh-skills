"""rh-skills cql — CQL command group (validate/translate/test via rh)."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import click

from rh_skills.common import config_value, repo_root, require_topic, require_tracking, sha256_file, tracking_file
from rh_skills.commands.cql_library import _load_manifest, import_library


def _resolve_rh_binary() -> str:
    """Return the path to the `rh` binary or raise ClickException with install hint."""
    path = config_value("RH_CLI_PATH")
    if path:
        return path
    found = shutil.which("rh")
    if found:
        return found
    raise click.ClickException(
        "The `rh` CLI binary was not found.\n"
        "Install it with:\n"
        "  cargo install --path /path/to/rh/apps/rh-cli\n"
        "Or set RH_CLI_PATH in your environment or .rh-skills.toml:\n"
        "  [cql]\n"
        "  rh_cli_path = \"/path/to/rh\""
    )


def _cql_path(topic: str, library: str) -> Path:
    """Return the canonical .cql file path for a topic/library."""
    root = repo_root()
    return root / "topics" / topic / "computable" / f"{library}.cql"


def _versioned_includes(cql_path: Path) -> set[tuple[str, str]]:
    """Return lexical versioned include directives declared by one CQL file.

    This deliberately does not use a line regex: examples in ``//`` or
    ``/* ... */`` comments, and strings containing the word ``include``, are
    not library dependencies. It only needs the small declaration grammar
    here, while the native compiler remains the authority for full CQL.
    """
    try:
        source = cql_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise click.ClickException(f"Cannot read CQL source {cql_path}: {exc}") from exc

    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            index = len(source) if newline < 0 else newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
            continue
        if character == "'":
            index += 1
            value: list[str] = []
            while index < len(source):
                if source[index] == "\\":
                    if index + 1 >= len(source):
                        # The native parser rejects an unterminated escape.
                        # Treat the remaining token as a string, rather than
                        # scanning its contents as a declaration.
                        index = len(source)
                        break
                    escaped = source[index + 1]
                    value.append({
                        "n": "\n",
                        "r": "\r",
                        "t": "\t",
                        "f": "\f",
                    }.get(escaped, escaped))
                    index += 2
                    continue
                if source[index] == "'":
                    index += 1
                    break
                value.append(source[index])
                index += 1
            tokens.append(("string", "".join(value)))
            continue
        if character in {'"', "`"}:
            delimiter = character
            index += 1
            value = []
            while index < len(source):
                if source[index] == delimiter:
                    index += 1
                    break
                value.append(source[index])
                index += 1
            tokens.append(("identifier", "".join(value)))
            continue
        if character.isalpha() or character == "_":
            end = index + 1
            while end < len(source) and (source[end].isalnum() or source[end] in "._"):
                end += 1
            tokens.append(("identifier", source[index:end]))
            index = end
            continue
        tokens.append(("punctuation", character))
        index += 1

    includes: set[tuple[str, str]] = set()
    for index, (kind, value) in enumerate(tokens):
        if kind != "identifier" or value.lower() != "include":
            continue
        if index + 3 >= len(tokens):
            continue
        name_kind, name = tokens[index + 1]
        version_kind, version_keyword = tokens[index + 2]
        value_kind, version = tokens[index + 3]
        if (
            name_kind == "identifier"
            and version_kind == "identifier"
            and version_keyword.lower() == "version"
            and value_kind == "string"
            and version
        ):
            includes.add((name, version))
    return includes


def _repo_file(raw_path: object, label: str) -> Path:
    """Resolve one tracked repo-relative file without permitting an escape."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise click.ClickException(f"{label} must be a non-empty repository-relative path")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise click.ClickException(f"{label} must be repository-relative")
    root = repo_root().resolve()
    try:
        resolved = (root / candidate).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"{label} escapes or cannot be read from the repository") from exc
    if not resolved.is_file():
        raise click.ClickException(f"{label} is not a file: {resolved}")
    return resolved


def _tracked_external_dependencies(topic: str) -> dict[tuple[str, str], list[dict]]:
    """Return imported dependency tracking entries, keyed by CQL identity.

    A workspace without tracking remains valid for local CQL authoring. It only
    becomes an error when a versioned compiled sidecar is selected below.
    """
    if not tracking_file().is_file():
        return {}
    topic_entry = require_topic(require_tracking(), topic)
    dependencies: dict[tuple[str, str], list[dict]] = {}
    for entry in topic_entry.get("computable", []) or []:
        if not isinstance(entry, dict) or entry.get("strategy") != "external-dependency":
            continue
        dependency = entry.get("external_dependency")
        if not isinstance(dependency, dict):
            raise click.ClickException(
                f"External dependency tracking entry {entry.get('name')!r} has no external_dependency object"
            )
        name = dependency.get("name")
        version = dependency.get("version")
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise click.ClickException(
                f"External dependency tracking entry {entry.get('name')!r} needs name and version"
            )
        dependencies.setdefault((name, version), []).append(entry)
    return dependencies


def _tracked_file_digest(entry: dict, path: Path, label: str) -> None:
    """Require the tracked path and checksum to match the exact on-disk bytes."""
    root = repo_root().resolve()
    try:
        relative = path.resolve().relative_to(root).as_posix()
    except ValueError as exc:  # pragma: no cover - guarded by callers
        raise click.ClickException(f"{label} escapes repository root: {path}") from exc
    files = entry.get("files")
    checksums = entry.get("checksums")
    if not isinstance(files, list) or relative not in files:
        raise click.ClickException(f"Pinned dependency does not track {label}: {relative}")
    expected = checksums.get(relative) if isinstance(checksums, dict) else None
    actual = sha256_file(path)
    if not isinstance(expected, str) or expected != actual:
        raise click.ClickException(
            f"Pinned dependency tracking checksum mismatch for {label}: {relative}"
        )


def _attachment_bytes(library: dict, content_type: str, label: str) -> bytes:
    content = library.get("content")
    if not isinstance(content, list):
        raise click.ClickException(f"{label} Library.content must be an array")
    matches = [attachment for attachment in content if isinstance(attachment, dict)
               and attachment.get("contentType") == content_type]
    if len(matches) != 1 or not isinstance(matches[0].get("data"), str):
        raise click.ClickException(
            f"{label} Library must contain exactly one base64 {content_type} attachment"
        )
    try:
        return base64.b64decode(matches[0]["data"], validate=True)
    except ValueError as exc:
        raise click.ClickException(f"{label} Library {content_type} attachment is not valid base64") from exc


def _verify_imported_dependency(
    entry: dict,
    name: str,
    version: str,
    computable_dir: Path,
) -> Path:
    """Verify one selected compiled dependency and return its CQL sidecar."""
    dependency = entry.get("external_dependency")
    if not isinstance(dependency, dict):  # guarded while indexing, retained for direct calls
        raise click.ClickException("External dependency tracking entry has no provenance")
    manifest_path = _repo_file(dependency.get("manifest"), f"{name} {version} manifest")
    imported = _load_manifest(manifest_path)
    expected_resource = {
        "canonical": imported["resource"]["url"],
        "name": imported["resource"]["name"],
        "version": imported["resource"]["version"],
    }
    actual_resource = {key: dependency.get(key) for key in expected_resource}
    if actual_resource != expected_resource:
        raise click.ClickException(
            f"Pinned dependency provenance does not match its manifest for {name} {version}"
        )
    if dependency.get("source") != imported["source"]:
        raise click.ClickException(
            f"Pinned dependency source provenance does not match its manifest for {name} {version}"
        )
    if dependency.get("cql_sha256") != imported["cql_sha256"] or dependency.get("elm_sha256") != imported["elm_sha256"]:
        raise click.ClickException(
            f"Pinned dependency CQL/ELM provenance does not match its manifest for {name} {version}"
        )

    cql_path = computable_dir / f"{name}-{version}.cql"
    elm_path = computable_dir / "elm" / f"{name}-{version}.json"
    for path, expected, label in [
        (cql_path, imported["cql_sha256"], "CQL sidecar"),
        (elm_path, imported["elm_sha256"], "ELM sidecar"),
    ]:
        if not path.is_file():
            raise click.ClickException(f"Pinned dependency {label} is missing: {path}")
        if sha256_file(path) != expected:
            raise click.ClickException(f"Pinned dependency {label} does not match its manifest: {path}")
        _tracked_file_digest(entry, path, label)

    library_candidates: list[tuple[Path, dict]] = []
    for raw_path in entry.get("files", []) or []:
        if not isinstance(raw_path, str) or not raw_path.endswith(".json"):
            continue
        path = _repo_file(raw_path, f"{name} {version} tracked file")
        try:
            resource = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise click.ClickException(f"Cannot read pinned dependency Library {path}: {exc}") from exc
        if (
            isinstance(resource, dict)
            and resource.get("resourceType") == "Library"
            and resource.get("id") == imported["resource"]["id"]
            and resource.get("url") == imported["resource"]["url"]
            and resource.get("name") == name
            and resource.get("version") == version
        ):
            library_candidates.append((path, resource))
    if len(library_candidates) != 1:
        raise click.ClickException(
            f"Pinned dependency {name} {version} must track exactly one matching FHIR Library, found {len(library_candidates)}"
        )
    library_path, library = library_candidates[0]
    _tracked_file_digest(entry, library_path, "FHIR Library")
    if _attachment_bytes(library, "text/cql", f"{name} {version}") != cql_path.read_bytes():
        raise click.ClickException(f"Pinned dependency FHIR Library CQL attachment differs from {cql_path}")
    if _attachment_bytes(library, "application/elm+json", f"{name} {version}") != elm_path.read_bytes():
        raise click.ClickException(f"Pinned dependency FHIR Library ELM attachment differs from {elm_path}")
    return cql_path


def _verify_pinned_dependencies(topic: str, cql_path: Path) -> None:
    """Verify every selected compiled include has immutable import provenance.

    Versioned local source includes remain supported when no compiled ELM
    sidecar exists. Once ``elm/Name-Version.json`` is present, it must be a
    tracked ``external-dependency`` import; runtime must never select an
    arbitrary sidecar or silently recompile a changed imported source.
    """
    root_includes = _versioned_includes(cql_path)
    if not root_includes:
        return

    computable_dir = cql_path.parent
    dependencies = _tracked_external_dependencies(topic)
    visited: set[tuple[str, str]] = set()

    def verify_include(name: str, version: str) -> None:
        identity = (name, version)
        if identity in visited:
            return
        visited.add(identity)
        selected_elm = computable_dir / "elm" / f"{name}-{version}.json"
        entries = dependencies.get(identity, [])
        if not entries:
            if selected_elm.exists():
                raise click.ClickException(
                    f"Compiled ELM sidecar {selected_elm} is not a tracked imported dependency for {name} {version}"
                )
            # With no selected ELM, native resolution falls back to the first
            # source candidate: input.parent, then --lib-path. rh-skills uses
            # the computable directory for both, so this is the sole local
            # candidate. Scan it for transitive selected sidecars before
            # allowing package-cache or absent-source resolution to proceed.
            source_candidate = computable_dir / f"{name}-{version}.cql"
            if source_candidate.is_file():
                for child_name, child_version in _versioned_includes(source_candidate):
                    verify_include(child_name, child_version)
            return
        if len(entries) != 1:
            raise click.ClickException(
                f"Ambiguous imported dependency provenance for {name} {version}: {len(entries)} tracking entries"
            )
        dependency_cql = _verify_imported_dependency(entries[0], name, version, computable_dir)
        for child_name, child_version in _versioned_includes(dependency_cql):
            verify_include(child_name, child_version)

    for name, version in root_includes:
        verify_include(name, version)


def _parse_eval_output(raw: str):
    """Parse ``rh cql eval`` output into a comparable Python value."""
    text = raw.strip()
    if text == "":
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        return text


def _strict_json_equal(actual, expected) -> bool:
    """Compare JSON values without Python's bool/int equality coercion."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual is expected
    if actual is None or expected is None:
        return actual is None and expected is None
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return actual == expected
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _strict_json_equal(actual[key], expected[key]) for key in actual
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_json_equal(left, right) for left, right in zip(actual, expected)
        )
    return type(actual) is type(expected) and actual == expected


def _fixture_parameters(case_dir: Path) -> dict[str, object]:
    """Read generic parameters from context JSON and the documented FHIR Parameters input."""
    parameters: dict[str, object] = {}
    context_path = case_dir / "input" / "evaluation-context.json"
    if not context_path.is_file():
        context_path = case_dir / "input" / "context.json"
    if context_path.is_file():
        context = json.loads(context_path.read_text())
        values = context.get("parameters", {}) if isinstance(context, dict) else {}
        if values is not None and not isinstance(values, dict):
            raise click.ClickException(f"{context_path}: parameters must be a JSON object")
        if isinstance(values, dict):
            parameters.update(values)

    fhir_parameters_path = case_dir / "input" / "parameters.json"
    if fhir_parameters_path.is_file():
        fhir_parameters = json.loads(fhir_parameters_path.read_text())
        entries = fhir_parameters.get("parameter", []) if isinstance(fhir_parameters, dict) else []
        if not isinstance(entries, list):
            raise click.ClickException(f"{fhir_parameters_path}: parameter must be an array")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise click.ClickException(f"{fhir_parameters_path}: each parameter needs a name")
            value_fields = [
                (key[5:], value)
                for key, value in entry.items()
                if key.startswith("value") and key != "value" and value is not None
            ]
            if len(value_fields) != 1:
                raise click.ClickException(
                    f"{fhir_parameters_path}: parameter {entry['name']!r} must have exactly one value[x]"
                )
            parameters[entry["name"]] = value_fields[0][1]
    return parameters


def _fixture_terminology_args(case_dir: Path) -> list[str]:
    """Return the optional pre-expanded terminology input for native evaluation."""
    terminology_path = case_dir / "input" / "terminology.json"
    if not terminology_path.is_file():
        return []
    try:
        resource = json.loads(terminology_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"{terminology_path}: invalid JSON: {exc}") from exc

    if not isinstance(resource, dict):
        raise click.ClickException(f"{terminology_path}: terminology input must be a FHIR ValueSet or Bundle")
    if resource.get("resourceType") == "ValueSet":
        value_sets = [resource]
    elif resource.get("resourceType") == "Bundle":
        entries = resource.get("entry")
        if not isinstance(entries, list):
            raise click.ClickException(f"{terminology_path}: Bundle.entry must be an array")
        value_sets = []
        for index, entry in enumerate(entries, start=1):
            value_set = entry.get("resource") if isinstance(entry, dict) else None
            if not isinstance(value_set, dict) or value_set.get("resourceType") != "ValueSet":
                raise click.ClickException(
                    f"{terminology_path}: Bundle.entry[{index - 1}] must contain a ValueSet resource"
                )
            value_sets.append(value_set)
    else:
        raise click.ClickException(
            f"{terminology_path}: expected resourceType ValueSet or Bundle, "
            f"got {resource.get('resourceType')!r}"
        )
    if not value_sets:
        raise click.ClickException(f"{terminology_path}: Bundle contains no ValueSet resources")
    for index, value_set in enumerate(value_sets, start=1):
        if not isinstance(value_set.get("url"), str) or not value_set["url"].strip():
            raise click.ClickException(f"{terminology_path}: ValueSet #{index} is missing url")
        if not isinstance(value_set.get("version"), str) or not value_set["version"].strip():
            raise click.ClickException(f"{terminology_path}: ValueSet #{index} is missing version")
    return ["--terminology", str(terminology_path)]


def _fixture_eval_context(case_dir: Path, bundle_file: Path) -> tuple[list[str], list[str]]:
    """Return native `rh cql eval` context flags and JSON parameter arguments."""
    context_path = case_dir / "input" / "evaluation-context.json"
    if not context_path.is_file():
        context_path = case_dir / "input" / "context.json"
    context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    if not isinstance(context, dict):
        raise click.ClickException(f"{context_path}: evaluation context must be a JSON object")

    bundle = json.loads(bundle_file.read_text())
    patients = [
        entry.get("resource")
        for entry in bundle.get("entry", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("resource"), dict)
        and entry["resource"].get("resourceType") == "Patient"
        and isinstance(entry["resource"].get("id"), str)
    ] if isinstance(bundle, dict) else []
    patient_path = case_dir / "input" / "patient.json"
    patient = json.loads(patient_path.read_text()) if patient_path.is_file() else None
    explicit_subject = context.get("subject")
    if isinstance(explicit_subject, str) and explicit_subject:
        subject = explicit_subject if "/" in explicit_subject else f"Patient/{explicit_subject}"
        if not subject.startswith("Patient/") or subject.count("/") != 1:
            raise click.ClickException(f"{context_path}: subject must be Patient/<id>")
        patient_id = subject.removeprefix("Patient/")
        known_ids = {entry["id"] for entry in patients}
        if isinstance(patient, dict) and isinstance(patient.get("id"), str):
            known_ids.add(patient["id"])
        if patient_id not in known_ids:
            raise click.ClickException(
                f"{context_path}: selected subject {subject!r} does not exist in the fixture input"
            )
    else:
        if len(patients) > 1:
            raise click.ClickException(
                f"{bundle_file}: contains {len(patients)} Patients; set input/evaluation-context.json subject explicitly"
            )
        if len(patients) == 1:
            subject = f"Patient/{patients[0]['id']}"
        elif isinstance(patient, dict) and isinstance(patient.get("id"), str):
            subject = f"Patient/{patient['id']}"
        else:
            subject = None

    command_args: list[str] = []
    if isinstance(subject, str) and subject:
        command_args.extend(["--subject", subject])

    evaluation_date = context.get("evaluationDate") or context.get("evaluation_date")
    if isinstance(evaluation_date, str) and evaluation_date:
        command_args.extend(["--evaluation-date", evaluation_date])

    period = context.get("measurementPeriod") or context.get("measurement_period")
    parameters = _fixture_parameters(case_dir)
    if isinstance(period, dict):
        start = period.get("start")
        end = period.get("end")
        if isinstance(start, str) and start:
            command_args.extend(["--measurement-period-start", start])
        if isinstance(end, str) and end:
            command_args.extend(["--measurement-period-end", end])
        # Preserve the whole authored period, including closure flags, in the
        # exact CQL parameter rather than reducing it to start/end flags.
        parameters["Measurement Period"] = period

    parameter_args: list[str] = []
    for name, value in parameters.items():
        if not isinstance(name, str) or not name:
            raise click.ClickException("CQL fixture parameter names must be non-empty strings")
        parameter_args.extend([
            "--parameter",
            f"{name}={json.dumps(value, separators=(',', ':'), ensure_ascii=False)}",
        ])
    return command_args, parameter_args


@click.group("cql")
def cql():
    """CQL authoring commands (validate, translate, test via rh)."""
    pass


@cql.command("validate")
@click.argument("topic")
@click.argument("library")
def validate(topic: str, library: str) -> None:
    """Validate a .cql file using `rh cql validate`."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")
    _verify_pinned_dependencies(topic, cql_file)
    rh = _resolve_rh_binary()

    result = subprocess.run(
        [rh, "cql", "validate", str(cql_file), "--lib-path", str(cql_file.parent)],
        capture_output=False,
    )
    raise SystemExit(result.returncode)


@cql.command("translate")
@click.argument("topic")
@click.argument("library")
def translate(topic: str, library: str) -> None:
    """Compile CQL to topics/<topic>/computable/elm/<library>.json."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")
    _verify_pinned_dependencies(topic, cql_file)
    rh = _resolve_rh_binary()

    elm_dir = cql_file.parent / "elm"
    elm_dir.mkdir(exist_ok=True)
    elm_file = elm_dir / f"{library}.json"
    result = subprocess.run(
        [rh, "cql", "compile", str(cql_file), "--output", str(elm_file), "--lib-path", str(cql_file.parent)],
        capture_output=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    click.echo(str(elm_file))


@cql.command("test")
@click.argument("topic")
@click.argument("library")
def test(topic: str, library: str) -> None:
    """Run fixture-based expression tests using ``rh cql eval``."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")
    _verify_pinned_dependencies(topic, cql_file)
    rh = _resolve_rh_binary()

    fixtures_root = repo_root() / "tests" / "cql" / library
    if not fixtures_root.exists():
        raise click.ClickException(f"No test fixtures found at: {fixtures_root}")

    cases = sorted(fixtures_root.glob("case-*/"))
    if not cases:
        raise click.ClickException(f"No case-* directories found under: {fixtures_root}")

    click.echo(f"Running {len(cases)} CQL fixture case(s) under {fixtures_root}")

    failures = 0
    assertions = 0
    for case_dir in cases:
        bundle_file = case_dir / "input" / "bundle.json"
        expected_file = case_dir / "expected" / "expression-results.json"
        if not bundle_file.exists() or not expected_file.exists():
            missing = []
            if not bundle_file.exists():
                missing.append("input/bundle.json")
            if not expected_file.exists():
                missing.append("expected/expression-results.json")
            click.echo(f"  {case_dir.name}: FAIL missing {', '.join(missing)}")
            failures += 1
            continue

        expected = json.loads(expected_file.read_text())
        if not isinstance(expected, dict) or not expected:
            click.echo(f"  {case_dir.name}: FAIL expected/expression-results.json must be a non-empty object")
            failures += 1
            continue

        click.echo(f"  {case_dir.name}:")
        case_failed = False
        try:
            context_args, parameter_args = _fixture_eval_context(case_dir, bundle_file)
            terminology_args = _fixture_terminology_args(case_dir)
        except click.ClickException as exc:
            click.echo(f"    FAIL evaluation context: {exc.format_message()}")
            failures += 1
            continue
        except (OSError, json.JSONDecodeError) as exc:
            click.echo(f"    FAIL evaluation context: {exc}")
            failures += 1
            continue
        for expression, expected_value in expected.items():
            assertions += 1
            result = subprocess.run(
                [
                    rh,
                    "cql",
                    "eval",
                    str(cql_file),
                    expression,
                    "--data",
                    str(bundle_file),
                    "--lib-path",
                    str(cql_file.parent),
                    *context_args,
                    *parameter_args,
                    *terminology_args,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                case_failed = True
                failures += 1
                detail = (result.stderr or result.stdout or "evaluation failed").strip()
                click.echo(f"    FAIL {expression}: {detail}")
                continue

            actual_value = _parse_eval_output(result.stdout)
            if not _strict_json_equal(actual_value, expected_value):
                case_failed = True
                failures += 1
                click.echo(
                    f"    FAIL {expression}: expected {json.dumps(expected_value)}, "
                    f"got {json.dumps(actual_value)}"
                )
                continue

            click.echo(f"    PASS {expression}")

        if not case_failed:
            click.echo("    case PASS")

    if failures:
        click.echo(f"\nFAIL — {failures} assertion(s) failed across {len(cases)} case(s)")
        raise SystemExit(1)
    click.echo(f"\nPASS — {assertions} assertion(s) across {len(cases)} case(s)")


cql.add_command(import_library)
