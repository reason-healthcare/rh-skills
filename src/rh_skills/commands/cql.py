"""rh-skills cql — CQL command group (evaluation deferred; backend TBD)."""
from __future__ import annotations

import json
from pathlib import Path

import click

from rh_skills.common import repo_root


def _cql_path(topic: str, library: str) -> Path:
    """Return the canonical .cql file path for a topic/library."""
    root = repo_root()
    return root / "topics" / topic / "computable" / f"{library}.cql"


@click.group("cql")
def cql():
    """CQL authoring commands (validate, translate, test) — backend pending."""
    pass


@cql.command("validate")
@click.argument("topic")
@click.argument("library")
def validate(topic: str, library: str) -> None:
    """Validate a .cql file (deferred — CQL backend not yet wired up)."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")
    click.echo(f"[deferred] CQL validation not yet implemented. File: {cql_file}")


@cql.command("translate")
@click.argument("topic")
@click.argument("library")
def translate(topic: str, library: str) -> None:
    """Translate a .cql file to ELM JSON (deferred — CQL backend not yet wired up)."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")
    click.echo(f"[deferred] CQL translation not yet implemented. File: {cql_file}")


@cql.command("test")
@click.argument("topic")
@click.argument("library")
def test(topic: str, library: str) -> None:
    """Run fixture-based test cases for a CQL library (deferred — evaluator not yet wired up)."""
    cql_file = _cql_path(topic, library)
    if not cql_file.exists():
        raise click.ClickException(f"CQL file not found: {cql_file}")

    fixtures_root = repo_root() / "tests" / "cql" / library
    if not fixtures_root.exists():
        raise click.ClickException(f"No test fixtures found at: {fixtures_root}")

    cases = sorted(fixtures_root.glob("case-*/"))
    if not cases:
        raise click.ClickException(f"No case-* directories found under: {fixtures_root}")

    click.echo(f"[deferred] CQL evaluation not yet implemented.")
    click.echo(f"           {len(cases)} case(s) found under {fixtures_root}")
    for case_dir in cases:
        bundle_file = case_dir / "input" / "bundle.json"
        expected_file = case_dir / "expected" / "expression-results.json"
        status = "ready" if bundle_file.exists() and expected_file.exists() else "incomplete"
        if expected_file.exists():
            exprs = list(json.loads(expected_file.read_text()).keys())
            click.echo(f"  {case_dir.name} [{status}]: {', '.join(exprs)}")
        else:
            click.echo(f"  {case_dir.name} [{status}]")
