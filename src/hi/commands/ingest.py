"""hi ingest — Register and track raw L1 source artifacts."""

import hashlib
import shutil
import time
from pathlib import Path

import click
import httpx

from hi.common import (
    append_root_event,
    locked_update_tracking,
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

AUTH_REDIRECT_MARKERS = ("login", "signin", "sign-in", "auth", "access-denied", "sso", "idp")

MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/xml": ".xml",
    "text/xml": ".xml",
}


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
@click.argument("file", required=False, type=click.Path(exists=False))
@click.option("--url", "source_url", default=None, help="URL to download instead of a local file")
@click.option("--name", "source_name", default=None, help="Stem name for saved file (required with --url)")
@click.option("--type", "source_type", default="document", help="Source type (see Source Type Taxonomy)")
def implement(file, source_url, source_name, source_type):
    """Copy FILE to sources/ and register in tracking.yaml.

    Alternatively, pass --url <url> --name <name> to download from a URL.
    """
    if source_url:
        _implement_url(source_url, source_name, source_type)
    else:
        if file is None:
            raise click.UsageError("Provide FILE argument or --url flag")
        _implement_file(Path(file), source_type)


def _implement_file(src_path: Path, source_type: str = "document") -> None:
    """Copy a local file to sources/ and register it."""
    if not src_path.exists():
        raise click.ClickException(f"File not found: {src_path}")

    src_root = sources_root()
    src_root.mkdir(parents=True, exist_ok=True)

    source_name = src_path.stem

    shutil.copy2(src_path, src_root / src_path.name)
    dest_file = src_root / src_path.name

    checksum = sha256_file(dest_file)
    ingested_at = now_iso()

    _ensure_tracking()

    def _update(tracking):
        existing = {s["name"] for s in tracking.get("sources", [])}
        if source_name in existing:
            log_warn(f"{source_name} already registered. Re-registering with updated checksum.")
            for s in tracking["sources"]:
                if s["name"] == source_name:
                    s["checksum"] = checksum
                    s["ingested_at"] = ingested_at
            append_root_event(tracking, "source_changed", f"Re-ingested source: {source_name}")
        else:
            tracking["sources"].append({
                "name": source_name,
                "file": f"sources/{src_path.name}",
                "type": source_type,
                "checksum": checksum,
                "ingested_at": ingested_at,
                "text_extracted": False,
            })
            append_root_event(tracking, "source_added", f"Ingested source: {source_name}")

    locked_update_tracking(_update)
    log_info(f"Registered: {source_name} (checksum: {checksum[:12]}...)")


def _implement_url(url: str, source_name: str | None, source_type: str = "document") -> None:
    """Download a URL to sources/ and register it. Exit 3 on auth redirect."""
    if not source_name:
        raise click.UsageError("--name is required when using --url")

    src_root = sources_root()
    src_root.mkdir(parents=True, exist_ok=True)

    click.echo(f"Downloading: {url}")
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise click.ClickException(f"HTTP {e.response.status_code}: {url}") from e
    except httpx.HTTPError as e:
        raise click.ClickException(f"Network error: {e}") from e

    final_url = str(response.url)
    final_url_lower = final_url.lower()
    if any(marker in final_url_lower for marker in AUTH_REDIRECT_MARKERS):
        click.echo(f"⚠ Authentication required for: {url}", err=True)
        click.echo(f"  Final redirect URL: {final_url}", err=True)
        click.echo("  Action: Retrieve manually and run: hi ingest implement <downloaded-file>", err=True)
        raise SystemExit(3)

    # Detect file extension from Content-Type
    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    ext = MIME_TO_EXT.get(content_type, "")
    if not ext:
        # Fall back to URL extension
        from urllib.parse import urlparse
        url_path = urlparse(url).path
        ext = Path(url_path).suffix or ".bin"

    dest_file = src_root / f"{source_name}{ext}"
    if dest_file.exists():
        log_warn(f"File already exists: {dest_file}")
        raise SystemExit(2)

    dest_file.write_bytes(response.content)

    checksum = sha256_file(dest_file)
    size_mb = len(response.content) / (1024 * 1024)
    ingested_at = now_iso()

    _ensure_tracking()

    def _update(tracking):
        existing = {s["name"] for s in tracking.get("sources", [])}
        if source_name in existing:
            log_warn(f"{source_name} already registered — updating checksum.")
            for s in tracking["sources"]:
                if s["name"] == source_name:
                    s["checksum"] = checksum
                    s["ingested_at"] = ingested_at
                    s["url"] = url
            append_root_event(tracking, "source_changed", f"Re-downloaded source: {source_name}")
        else:
            tracking["sources"].append({
                "name": source_name,
                "file": f"sources/{source_name}{ext}",
                "type": source_type,
                "url": url,
                "checksum": checksum,
                "ingested_at": ingested_at,
                "text_extracted": False,
                "downloaded": True,
            })
            append_root_event(tracking, "source_ingested", f"Downloaded source: {source_name}")

    locked_update_tracking(_update)
    click.echo(f"✓ Downloaded: sources/{source_name}{ext}")
    click.echo(f"  SHA-256: {checksum}")
    click.echo(f"  MIME: {content_type or 'unknown'}")
    click.echo(f"  Size: {size_mb:.1f} MB")


def _ensure_tracking() -> None:
    """Create tracking.yaml skeleton if it doesn't exist (safe under concurrent calls)."""
    tf = tracking_file()
    if tf.exists():
        return
    from ruamel.yaml import YAML
    y = YAML()
    y.default_flow_style = False
    skeleton = {"schema_version": "1.0", "sources": [], "topics": [], "events": []}
    try:
        # 'x' mode is an atomic exclusive create — only one concurrent caller wins
        with open(tf, "x") as f:
            y.dump(skeleton, f)
    except FileExistsError:
        pass  # another process beat us to it; that's fine


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
