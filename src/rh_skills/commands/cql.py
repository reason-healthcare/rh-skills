"""rh-skills cql — CQL command group (validate/translate/test via rh)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import click

from rh_skills.common import config_value, repo_root
from rh_skills.commands.cql_library import import_library


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
    rh = _resolve_rh_binary()
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")

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
    rh = _resolve_rh_binary()
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")

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
    rh = _resolve_rh_binary()
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")

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
