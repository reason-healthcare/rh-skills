"""rh-skills package — Build distribution packages from computable artifacts."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click

from rh_skills.commands.formalize_config import load_formalize_config
from rh_skills.common import (
    append_topic_event,
    config_value,
    require_topic,
    require_tracking,
    repo_root,
    save_tracking,
    topic_dir,
)
from rh_skills.fhir.packaging import (
    infer_package_id,
    load_packager_toml,
    prepare_package_workspace,
)


def _resolve_rh_binary() -> str:
    """Return the path to the ``rh`` binary or raise with install guidance."""
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


def _run_rh_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an ``rh`` subprocess and capture combined output for reporting."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
    )


@click.command("package")
@click.argument("topic")
@click.option("--dry-run", is_flag=True, help="Print the planned package workspace and rh commands")
@click.option("--check-only", is_flag=True, help="Run `rh package check` but do not build")
@click.option("--pack", "pack_tgz", is_flag=True, help="Run `rh package pack` after a successful build")
@click.option("--output-dir", type=click.Path(), default=None, help="Override build output directory (default: <workspace>/output)")
@click.option("--workspace-dir", type=click.Path(), default=None, help="Override package workspace directory")
@click.option(
    "--include-test-fixtures",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    metavar="DIR",
    help="Include supported CQL fixture inputs from DIR",
)
@click.option("--fixture-library", default=None, help="Limit included fixtures to one CQL fixture library")
@click.option("--fixture-case", default=None, help="Limit included fixtures to one CQL fixture case")
def package(
    topic,
    dry_run,
    check_only,
    pack_tgz,
    output_dir,
    workspace_dir,
    include_test_fixtures,
    fixture_library,
    fixture_case,
):
    """Build a FHIR distribution package from topics/<topic>/computable/."""
    if (fixture_library or fixture_case) and not include_test_fixtures:
        raise click.ClickException("--fixture-library and --fixture-case require --include-test-fixtures")

    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    computable = topic_entry.get("computable", [])
    if not computable:
        click.echo("Error: No computable entries found in tracking for this topic", err=True)
        sys.exit(2)

    td = topic_dir(topic)
    computable_dir = td / "computable"
    if not computable_dir.exists():
        click.echo(f"Error: Computable directory not found: {computable_dir}", err=True)
        sys.exit(2)

    cfg = load_formalize_config(td)
    if cfg is None:
        click.echo(
            f"Warning: formalize-config.yaml not found for topic '{topic}'. "
            "Using defaults (canonical=http://example.org/fhir, version=0.1.0, status=draft).\n"
            f"Run 'rh-skills formalize-config {topic}' to configure.",
            err=True,
        )
        cfg = {
            "name": "".join(w.capitalize() for w in topic.split("-")),
            "id": topic,  # Simple ID (IG.id), packageId will add 'reason.' prefix
            "canonical": "http://example.org/fhir",
            "status": "draft",
            "version": "0.1.0",
        }

    if workspace_dir:
        pkg_workspace = Path(workspace_dir)
    else:
        pkg_workspace = td / "process" / "package-workspace"

    packager_cfg = load_packager_toml(pkg_workspace / "packager.toml")
    canonical = packager_cfg.get("canonical", cfg["canonical"])

    build_dir = Path(output_dir) if output_dir else (pkg_workspace / "output")
    output_mode = "overridden (--output-dir)" if output_dir else "defaulted (<workspace>/output)"

    fixture_root = None
    if include_test_fixtures:
        fixture_root = Path(include_test_fixtures)
        if not fixture_root.is_absolute():
            fixture_root = repo_root() / fixture_root
        if not fixture_root.is_dir():
            click.echo(f"Error: Test fixture directory not found: {fixture_root}", err=True)
            sys.exit(2)

    resolved_package_id = infer_package_id(cfg["id"])
    staged = prepare_package_workspace(
        computable_dir,
        pkg_workspace,
        topic,
        version=cfg["version"],
        name=cfg["name"],
        ig_id=cfg["id"],
        canonical=canonical,
        status=cfg["status"],
        package_id=resolved_package_id,
        test_fixture_root=fixture_root,
        fixture_library=fixture_library,
        fixture_case=fixture_case,
    )

    if "error" in staged:
        click.echo(f"Error: {staged['error']}", err=True)
        sys.exit(2)

    rh = _resolve_rh_binary()
    check_cmd = [rh, "package", "check", str(pkg_workspace)]
    build_cmd = [rh, "package", "build", str(pkg_workspace)]
    if output_dir:
        build_cmd.extend(["--out", str(build_dir)])
    pack_cmd = [rh, "package", "pack", str(build_dir)]

    if dry_run:
        click.echo(f"--- DRY RUN: package '{topic}' ---")
        click.echo(f"  Package: {staged['package_name']} v{staged['version']}")
        click.echo(f"  Resources: {staged['json_count']} FHIR JSON + {staged['cql_count']} CQL")
        click.echo(f"  Canonical L3 source: {computable_dir}")
        click.echo(f"  Workspace: {pkg_workspace}")
        click.echo(f"  Build output: {build_dir} [{output_mode}]")
        if fixture_root is not None:
            click.echo(
                "  Fixture examples: "
                f"{staged['fixture_count']} files from "
                f"{staged['fixture_case_count']} cases / "
                f"{staged['fixture_library_count']} libraries"
            )
        click.echo(f"  Check command: {' '.join(check_cmd)}")
        if not check_only:
            click.echo(f"  Build command: {' '.join(build_cmd)}")
        if pack_tgz and not check_only:
            click.echo(f"  Pack command: {' '.join(pack_cmd)}")
        return

    click.echo(f"Preparing package workspace from {computable_dir}...")
    if fixture_root is not None:
        click.echo(
            "Copied fixture examples: "
            f"{staged['fixture_count']} files from "
            f"{staged['fixture_case_count']} cases / "
            f"{staged['fixture_library_count']} libraries"
        )

    check_result = _run_rh_command(check_cmd)
    if check_result.stdout:
        click.echo(check_result.stdout.rstrip())
    if check_result.returncode != 0:
        if check_result.stderr:
            click.echo(check_result.stderr.rstrip(), err=True)
        sys.exit(check_result.returncode)

    if check_only:
        click.echo("Package source check passed.")
        return

    build_result = _run_rh_command(build_cmd)
    if build_result.stdout:
        click.echo(build_result.stdout.rstrip())
    if build_result.returncode != 0:
        if build_result.stderr:
            click.echo(build_result.stderr.rstrip(), err=True)
        sys.exit(build_result.returncode)

    if pack_tgz:
        pack_result = _run_rh_command(pack_cmd)
        if pack_result.stdout:
            click.echo(pack_result.stdout.rstrip())
        if pack_result.returncode != 0:
            if pack_result.stderr:
                click.echo(pack_result.stderr.rstrip(), err=True)
            sys.exit(pack_result.returncode)

    append_topic_event(
        tracking,
        topic,
        "package_created",
        f"Packaged '{topic}' → {staged['package_name']} v{staged['version']} ({staged['json_count'] + staged['cql_count']} resources)",
    )
    save_tracking(tracking)

    click.echo(f"\n  package: {staged['package_name']} v{staged['version']}")
    click.echo(f"  resources: {staged['json_count']} FHIR JSON + {staged['cql_count']} CQL")
    if fixture_root is not None:
        click.echo(
            "  fixture examples: "
            f"{staged['fixture_count']} files from "
            f"{staged['fixture_case_count']} cases / "
            f"{staged['fixture_library_count']} libraries"
        )
    click.echo(f"  workspace: {pkg_workspace}")
    click.echo(f"  build output: {build_dir}")
    click.echo("Event: package_created")
