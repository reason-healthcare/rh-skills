"""rh-skills package — Bundle FHIR resources into a FHIR NPM package."""

import sys

import click

from rh_skills.commands.formalize_config import load_formalize_config
from rh_skills.common import (
    append_topic_event,
    log_info,
    now_iso,
    require_topic,
    require_tracking,
    save_tracking,
    topic_dir,
)
from rh_skills.fhir.packaging import build_package


@click.command("package")
@click.argument("topic")
@click.option("--dry-run", is_flag=True, help="Print package manifest without writing files")
@click.option("--output-dir", type=click.Path(), default=None, help="Override output directory")
def package(topic, dry_run, output_dir):
    """Bundle formalized FHIR resources into a FHIR NPM package.

    Collects all FHIR JSON + CQL from topics/<topic>/computable/,
    generates package.json and ImplementationGuide, and writes
    everything to topics/<topic>/package/.
    """
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    # Check that computable resources exist
    computable = topic_entry.get("computable", [])
    if not computable:
        click.echo("Error: No computable entries found in tracking for this topic", err=True)
        sys.exit(2)

    td = topic_dir(topic)
    computable_dir = td / "computable"

    if not computable_dir.exists():
        click.echo(f"Error: Computable directory not found: {computable_dir}", err=True)
        sys.exit(2)

    # Load formalize config — warn and use defaults if missing
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
            "id": topic,
            "canonical": "http://example.org/fhir",
            "status": "draft",
            "version": "0.1.0",
        }

    # Determine output directory
    if output_dir:
        pkg_dir = type(td)(output_dir)
    else:
        pkg_dir = td / "package"

    if dry_run:
        from rh_skills.fhir.packaging import (
            collect_computable_files,
            generate_package_json,
        )
        json_files, cql_files = collect_computable_files(computable_dir)
        pkg = generate_package_json(
            topic,
            version=cfg["version"],
            has_cql=bool(cql_files),
            package_id=f"@reason/{cfg['id']}",
        )
        click.echo(f"--- DRY RUN: package '{topic}' ---")
        click.echo(f"  Package: {pkg['name']} v{pkg['version']}")
        click.echo(f"  Resources: {len(json_files)} FHIR JSON + {len(cql_files)} CQL")
        click.echo(f"  Dependencies: {', '.join(f'{k}@{v}' for k, v in pkg['dependencies'].items())}")
        click.echo(f"  Output: {pkg_dir}")
        return

    click.echo(f"Packaging '{topic}' as FHIR package...")

    result = build_package(
        computable_dir,
        pkg_dir,
        topic,
        version=cfg["version"],
        name=cfg["name"],
        ig_id=cfg["id"],
        canonical=cfg["canonical"],
        status=cfg["status"],
        package_id=f"@reason/{cfg['id']}",
    )

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        sys.exit(2)

    # Update tracking
    append_topic_event(
        tracking, topic, "package_created",
        f"Packaged '{topic}' → {result['package_name']} v{result['version']} ({result['json_count'] + result['cql_count']} resources)",
    )
    save_tracking(tracking)

    click.echo(f"\n  package: {result['package_name']} v{result['version']}")
    click.echo(f"  resources: {result['json_count']} FHIR JSON + {result['cql_count']} CQL")
    click.echo(f"\nWrote package to {pkg_dir}")
    click.echo("Event: package_created")
