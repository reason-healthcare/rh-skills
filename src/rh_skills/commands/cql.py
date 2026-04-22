"""rh-skills cql — CQL command group wrapping the `rh` CLI."""
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


@click.group("cql")
def cql():
    """CQL authoring commands (validate, translate, test) powered by the rh CLI."""
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
    """Compile a .cql file to ELM JSON using `rh cql compile`."""
    rh = _resolve_rh_binary()
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")

    output_dir = cql_file.parent
    result = subprocess.run(
        [rh, "cql", "compile", str(cql_file), "--output", str(output_dir)],
        capture_output=False,
    )
    if result.returncode == 0:
        elm_file = output_dir / f"{library}.json"
        click.echo(str(elm_file))
    raise SystemExit(result.returncode)


@cql.command("test")
@click.argument("topic")
@click.argument("library")
def test(topic: str, library: str) -> None:
    """Run fixture-based test cases for a CQL library using `rh cql eval`."""
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

    any_fail = False
    for case_dir in cases:
        expected_file = case_dir / "expected" / "expression-results.json"
        bundle_file = case_dir / "input" / "bundle.json"
        if not expected_file.exists() or not bundle_file.exists():
            click.echo(f"  SKIP {case_dir.name}: missing input/bundle.json or expected/expression-results.json")
            continue

        expected = json.loads(expected_file.read_text())
        case_pass = True
        for expr_name, expected_value in expected.items():
            result = subprocess.run(
                [rh, "cql", "eval", str(cql_file), "--expr", expr_name, "--data", str(bundle_file)],
                capture_output=True,
                text=True,
            )
            actual_raw = result.stdout.strip()
            if result.returncode != 0:
                click.echo(f"  FAIL {case_dir.name} [{expr_name}]: rh cql eval exited {result.returncode}")
                if result.stderr:
                    click.echo(f"       {result.stderr.strip()}")
                case_pass = False
                any_fail = True
            else:
                # Compare as JSON values when possible, else as strings
                try:
                    actual = json.loads(actual_raw)
                except (json.JSONDecodeError, ValueError):
                    actual = actual_raw
                if actual != expected_value:
                    click.echo(
                        f"  FAIL {case_dir.name} [{expr_name}]:"
                        f" expected={json.dumps(expected_value)} actual={json.dumps(actual)}"
                    )
                    case_pass = False
                    any_fail = True

        if case_pass:
            click.echo(f"  PASS {case_dir.name}")

    if any_fail:
        raise SystemExit(1)
    click.echo(f"\n{len(cases)} case(s) passed.")
