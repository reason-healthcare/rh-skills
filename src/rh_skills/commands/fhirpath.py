"""rh-skills fhirpath — FHIRPath command group (parse/eval via rh)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click

from rh_skills.common import config_value


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


@click.group("fhirpath")
def fhirpath():
    """FHIRPath authoring commands (parse, eval via rh)."""
    pass


@fhirpath.command("parse")
@click.argument("expression")
@click.option("--format", "output_format", default=None, type=click.Choice(["pretty", "json", "debug"]))
def parse(expression: str, output_format: str | None) -> None:
    """Parse a FHIRPath expression using `rh fhirpath parse`."""
    rh = _resolve_rh_binary()
    cmd = [rh, "fhirpath", "parse", expression]
    if output_format:
        cmd.extend(["--format", output_format])
    result = subprocess.run(cmd, capture_output=False)
    raise SystemExit(result.returncode)


@fhirpath.command("eval")
@click.argument("expression")
@click.option("--data", "data_path", required=True, type=click.Path(exists=True, readable=True))
@click.option("--format", "output_format", default=None, type=click.Choice(["pretty", "json", "debug"]))
def eval_expr(expression: str, data_path: str, output_format: str | None) -> None:
    """Evaluate a FHIRPath expression against a JSON resource file."""
    rh = _resolve_rh_binary()
    cmd = [rh, "fhirpath", "eval", expression, "--data", str(Path(data_path))]
    if output_format:
        cmd.extend(["--format", output_format])
    result = subprocess.run(cmd, capture_output=False)
    raise SystemExit(result.returncode)
