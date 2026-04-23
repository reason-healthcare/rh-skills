"""rh-skills cql — CQL command group (validate/translate via rh; eval pending)."""
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
    """CQL authoring commands (validate, translate via rh; test eval pending)."""
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

    elm_file = cql_file.parent / f"{library}.json"
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
    """List fixture test cases (eval pending — rh cql eval not yet wired up)."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")

    fixtures_root = repo_root() / "tests" / "cql" / library
    if not fixtures_root.exists():
        raise click.ClickException(f"No test fixtures found at: {fixtures_root}")

    cases = sorted(fixtures_root.glob("case-*/"))
    if not cases:
        raise click.ClickException(f"No case-* directories found under: {fixtures_root}")

    click.echo("[eval pending] CQL evaluation not yet implemented.")
    click.echo(f"               {len(cases)} case(s) found under {fixtures_root}")
    for case_dir in cases:
        bundle_file = case_dir / "input" / "bundle.json"
        expected_file = case_dir / "expected" / "expression-results.json"
        status = "ready" if bundle_file.exists() and expected_file.exists() else "incomplete"
        if expected_file.exists():
            exprs = list(json.loads(expected_file.read_text()).keys())
            click.echo(f"  {case_dir.name} [{status}]: {', '.join(exprs)}")
        else:
            click.echo(f"  {case_dir.name} [{status}]")
