"""rh-skills cql — CQL command group (validate/translate/test via rh)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import click

from rh_skills.common import config_value, repo_root


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
        [rh, "cql", "validate", str(cql_file)],
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
        [rh, "cql", "compile", str(cql_file), "--output", str(elm_file)],
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
            if actual_value != expected_value:
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
