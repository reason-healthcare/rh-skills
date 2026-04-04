"""hi ingest — Register and track raw L1 source artifacts."""

import shutil
from pathlib import Path

import click

from hi.common import (
    append_root_event,
    log_info,
    log_warn,
    now_iso,
    repo_root,
    require_tracking,
    save_tracking,
    sha256_file,
    sources_root,
    tracking_file,
)


@click.group()
def ingest():
    """Register and track raw L1 source artifacts."""


@ingest.command()
def plan():
    """Generate an ingest plan template at plans/ingest-plan.md."""
    root = repo_root()
    plan_file = root / "plans" / "ingest-plan.md"

    if plan_file.exists():
        log_warn("ingest-plan.md already exists. Delete it first to regenerate.")
        return

    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("""\
---
sources:
- name: source-1
  path_or_url: "# TODO: local file path or URL to download"
  type: document
---

# Ingest Plan

Review and update the `sources` list above before running `hi ingest implement <file>`.

## Fields

- **name**: Identifier used for the `sources/<name>.md` file (kebab-case)
- **path_or_url**: Absolute local path to the source file, or a URL to download
- **type**: One of `pdf`, `word`, `excel`, `markdown`, `html`, `document`

## Next Step

After editing this file, run for each source:

```
hi ingest implement <path-to-file>
```
""")
    log_info(f"Created: {plan_file}")


@ingest.command()
@click.argument("file", type=click.Path(exists=True))
def implement(file):
    """Copy FILE to sources/ and register in tracking.yaml."""
    src_path = Path(file)
    src_root = sources_root()
    src_root.mkdir(parents=True, exist_ok=True)

    # Derive source name from filename (without extension)
    source_name = src_path.stem

    dest_file = src_root / f"{source_name}.md"
    if not dest_file.suffix == ".md":
        dest_file = src_root / src_path.name

    # Copy to sources/
    shutil.copy2(src_path, src_root / src_path.name)
    dest_file = src_root / src_path.name

    checksum = sha256_file(dest_file)
    ingested_at = now_iso()

    # Update tracking
    tf = tracking_file()
    if not tf.exists():
        from ruamel.yaml import YAML
        y = YAML()
        y.default_flow_style = False
        y.dump({
            "schema_version": "1.0",
            "sources": [],
            "topics": [],
            "events": [],
        }, tf)

    tracking = require_tracking()

    # Check if already registered
    existing = {s["name"] for s in tracking.get("sources", [])}
    if source_name in existing:
        log_warn(f"{source_name} already registered. Re-registering with updated checksum.")
        # Update existing entry
        for s in tracking["sources"]:
            if s["name"] == source_name:
                s["checksum"] = checksum
                s["ingested_at"] = ingested_at
        append_root_event(tracking, "source_changed", f"Re-ingested source: {source_name}")
    else:
        tracking["sources"].append({
            "name": source_name,
            "file": f"sources/{src_path.name}",
            "type": "document",
            "checksum": checksum,
            "ingested_at": ingested_at,
            "text_extracted": False,
        })
        append_root_event(tracking, "source_added", f"Ingested source: {source_name}")

    save_tracking(tracking)
    log_info(f"Registered: {source_name} (checksum: {checksum[:12]}...)")


@ingest.command()
def verify():
    """Re-checksum all registered sources and report changes."""
    tracking = require_tracking()
    sources = tracking.get("sources", [])

    if not sources:
        click.echo("No L1 sources registered")
        return

    src_root = sources_root()
    any_changed = False

    for src in sources:
        src_name = src.get("name", "")
        src_file = src.get("file", f"sources/{src_name}.md")
        stored_checksum = src.get("checksum", "")

        # Resolve path
        full_path = repo_root() / src_file
        if not full_path.exists():
            full_path = src_root / f"{src_name}.md"

        if not full_path.exists():
            click.echo(f"✗ {src_name:<30} MISSING")
            any_changed = True
            continue

        current = sha256_file(full_path)
        if current == stored_checksum:
            click.echo(f"✓ {src_name:<30} OK")
        else:
            click.echo(f"✗ {src_name:<30} CHANGED")
            click.echo(f"  was: {stored_checksum}")
            click.echo(f"  now: {current}")
            any_changed = True

    if any_changed:
        click.echo("\nRun `hi ingest implement <file>` to re-register changed sources.")
        raise SystemExit(1)
