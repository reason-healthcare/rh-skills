"""rh-skills ingest — Register and track raw L1 source artifacts."""

import hashlib
import json
import shutil
import time
from html.parser import HTMLParser
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

# Meta name prefixes to include; values are normalized to these short keys
_META_NAME_MAP = {
    "description": "description",
    "author": "author",
    "keywords": "keywords",
    "date": "date",
    "language": "language",
    "generator": "generator",
    # Dublin Core
    "dc.title": "dc_title",
    "dc.creator": "dc_creator",
    "dc.date": "dc_date",
    "dc.description": "dc_description",
    "dc.subject": "dc_subject",
    "dc.publisher": "dc_publisher",
    "dc.type": "dc_type",
    "dc.format": "dc_format",
    "dc.identifier": "dc_identifier",
    # OpenGraph
    "og:title": "og_title",
    "og:description": "og_description",
    "og:url": "og_url",
    "og:type": "og_type",
    "og:site_name": "og_site_name",
    # Twitter card
    "twitter:title": "twitter_title",
    "twitter:description": "twitter_description",
}


class _HTMLMetaParser(HTMLParser):
    """Extracts <title>, <meta>, and <script type="application/ld+json"> from HTML."""

    def __init__(self):
        super().__init__()
        self.title: str | None = None
        self.meta: dict[str, str] = {}
        self.json_ld: list[dict] = []
        self._in_title = False
        self._in_json_ld = False
        self._title_buf: list[str] = []
        self._json_ld_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (
                attrs_d.get("name") or
                attrs_d.get("property") or
                attrs_d.get("itemprop") or ""
            ).lower().strip()
            content = (attrs_d.get("content") or "").strip()
            if name and content:
                key = _META_NAME_MAP.get(name)
                if key:
                    self.meta[key] = content
        elif tag == "script" and attrs_d.get("type") == "application/ld+json":
            self._in_json_ld = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            self.title = "".join(self._title_buf).strip() or None
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            raw = "".join(self._json_ld_buf).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    self.json_ld.extend(parsed)
                elif isinstance(parsed, dict):
                    self.json_ld.append(parsed)
            except json.JSONDecodeError:
                pass
            self._json_ld_buf = []

    def handle_data(self, data):
        if self._in_title:
            self._title_buf.append(data)
        elif self._in_json_ld:
            self._json_ld_buf.append(data)


def _extract_html_meta(html_text: str) -> dict:
    """Return a dict of metadata extracted from HTML head tags and JSON-LD."""
    parser = _HTMLMetaParser()
    parser.feed(html_text)

    result: dict = {}

    if parser.title:
        result["title"] = parser.title

    result.update(parser.meta)

    # Flatten useful JSON-LD fields (first schema.org object wins)
    for obj in parser.json_ld:
        if not isinstance(obj, dict):
            continue
        schema_type = obj.get("@type", "")
        ld: dict = {}
        for field, key in [
            ("name", "ld_name"),
            ("headline", "ld_headline"),
            ("description", "ld_description"),
            ("author", "ld_author"),
            ("datePublished", "ld_date_published"),
            ("dateModified", "ld_date_modified"),
            ("publisher", "ld_publisher"),
            ("url", "ld_url"),
        ]:
            val = obj.get(field)
            if isinstance(val, dict):
                val = val.get("name") or val.get("@id")
            if val and isinstance(val, str):
                ld[key] = val
        if ld:
            if schema_type:
                ld["ld_type"] = schema_type
            result.update(ld)
            break  # only use first schema.org object

    return result


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

Review and update the `sources` list above before running `rh-skills ingest implement <file>`.

## Fields

- **name**: Identifier used for the `sources/<name>.md` file (kebab-case)
- **path_or_url**: Absolute local path to the source file, or a URL to download
- **type**: One of `pdf`, `word`, `excel`, `markdown`, `html`, `document`

## Next Step

After editing this file, run for each source:

```
rh-skills ingest implement <path-to-file>
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
        click.echo("  Action: Retrieve manually and run: rh-skills ingest implement <downloaded-file>", err=True)
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
@click.argument("file", type=click.Path(exists=True))
@click.option("--topic", required=True, help="Topic slug")
@click.option("--name", "source_name", default=None, help="Source name override (default: file stem)")
def normalize(file, topic, source_name):
    """Convert a source file to normalized Markdown at sources/normalized/<name>.md."""
    import subprocess

    src_path = Path(file)
    name = source_name or src_path.stem
    out_dir = sources_root() / "normalized"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{name}.md"

    text_extracted = True
    html_meta: dict = {}
    ext = src_path.suffix.lower()

    if ext == ".pdf":
        if shutil.which("pdftotext") is None:
            log_warn("Install poppler: brew install poppler")
            text_extracted = False
            content = ""
        else:
            result = subprocess.run(
                ["pdftotext", str(src_path), "-"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                log_warn(f"pdftotext failed: {result.stderr.strip()}")
                text_extracted = False
                content = ""
            else:
                content = result.stdout
    elif ext in (".docx", ".doc", ".xlsx"):
        if shutil.which("pandoc") is None:
            log_warn("Install pandoc: brew install pandoc")
            text_extracted = False
            content = ""
        else:
            result = subprocess.run(
                ["pandoc", str(src_path), "-t", "markdown"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                log_warn(f"pandoc failed: {result.stderr.strip()}")
                text_extracted = False
                content = ""
            else:
                content = result.stdout
    elif ext in (".html", ".htm"):
        from markdownify import markdownify as md
        html_text = src_path.read_text(errors="replace")
        # TODO(js-render): static HTML only. Sites that require JavaScript to
        # render (SPAs, dynamically loaded content) will produce empty or
        # incomplete content here. Future: detect empty body post-parse and
        # offer `--js-render` flag backed by Playwright
        # (`playwright install chromium`; `playwright.sync_api` Page.goto +
        # Page.content()). Guard behind optional dep to avoid forcing browser
        # install on all users. Track as FR-016 in specs/004-rh-inf-ingest/spec.md.
        html_meta = _extract_html_meta(html_text)
        content = md(html_text, heading_style="ATX")
    else:
        content = src_path.read_text(errors="replace")

    from ruamel.yaml import YAML as _YAML
    import io
    _y = _YAML()
    _y.default_flow_style = False
    frontmatter_data: dict = {
        "source": name,
        "topic": topic,
        "normalized": now_iso(),
        "original": f"sources/{src_path.name}",
        "text_extracted": text_extracted,
    }
    if html_meta:
        frontmatter_data["html_meta"] = html_meta
    buf = io.StringIO()
    _y.dump(frontmatter_data, buf)
    fm_text = buf.getvalue()
    out_file.write_text(f"---\n{fm_text}---\n\n{content}")

    # Update tracking.yaml — soft-fail if source not registered
    source_found = False
    try:
        tracking_data = require_tracking()
        sources_list = tracking_data.get("sources", [])
        source_found = any(s.get("name") == name for s in sources_list)
    except Exception:
        pass

    if source_found:
        def _update(tracking):
            for s in tracking.get("sources", []):
                if s.get("name") == name:
                    s["normalized"] = f"sources/normalized/{name}.md"
                    s["text_extracted"] = text_extracted
            append_root_event(tracking, "source_normalized", f"Normalized: {name}")
        locked_update_tracking(_update)
    else:
        log_warn(f"Source '{name}' not found in tracking.yaml — skipping tracking update")
        try:
            def _update_event(tracking):
                append_root_event(tracking, "source_normalized", f"Normalized: {name}")
            locked_update_tracking(_update_event)
        except Exception:
            pass

    if text_extracted:
        click.echo(f"✓ Normalized: sources/normalized/{name}.md")
    else:
        click.echo(f"⚠ Normalized (text not extracted): sources/normalized/{name}.md")


@ingest.command()
@click.argument("name")
@click.option("--topic", required=True, help="Topic slug")
@click.option("--type", "source_type", required=True, help="Source type")
@click.option("--evidence-level", required=True, help="Evidence level")
@click.option("--tags", default="", help="Comma-separated domain tags")
def classify(name, topic, source_type, evidence_level, tags):
    """Assign classification metadata to a registered source."""
    from hi.commands.search import VALID_SOURCE_TYPES, VALID_EVIDENCE_LEVELS

    if source_type not in VALID_SOURCE_TYPES:
        raise click.ClickException(
            f"Invalid type '{source_type}'. Valid types: {', '.join(sorted(VALID_SOURCE_TYPES))}"
        )
    if evidence_level not in VALID_EVIDENCE_LEVELS:
        raise click.ClickException(
            f"Invalid evidence level '{evidence_level}'. Valid levels: {', '.join(sorted(VALID_EVIDENCE_LEVELS))}"
        )

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    require_tracking()

    def _update(tracking):
        for s in tracking.get("sources", []):
            if s.get("name") == name:
                s["type"] = source_type
                s["evidence_level"] = evidence_level
                s["domain_tags"] = tag_list
                s["classified_at"] = now_iso()
                append_root_event(tracking, "source_classified", f"Classified: {name}")
                return
        raise click.ClickException(
            f"Source '{name}' not found in tracking.yaml. Run rh-skills ingest implement first."
        )

    locked_update_tracking(_update)
    click.echo(f"✓ Classified: {name} (type={source_type}, evidence_level={evidence_level})")


@ingest.command()
@click.argument("name")
@click.option("--topic", required=True, help="Topic slug")
@click.option("--concept", "concepts", multiple=True,
              help="Concept in 'canonical-name:type' format. Repeatable.")
def annotate(name, topic, concepts):
    """Add concept annotations to normalized.md and update concepts.yaml."""
    from ruamel.yaml import YAML as _YAML
    import io

    normalized_md = sources_root() / "normalized" / f"{name}.md"
    if not normalized_md.exists():
        raise click.ClickException(
            f"sources/normalized/{name}.md not found. "
            f"Run: rh-skills ingest normalize <file> --topic {topic} first."
        )

    # Parse concepts
    parsed_concepts = []
    for c in concepts:
        if ":" in c:
            cname, ctype = c.split(":", 1)
            parsed_concepts.append({"name": cname.strip(), "type": ctype.strip()})
        else:
            parsed_concepts.append({"name": c.strip(), "type": "term"})

    # Update normalized.md frontmatter
    raw = normalized_md.read_text()
    parts = raw.split("---\n", 2)
    if len(parts) >= 3:
        fm_text = parts[1]
        body = parts[2]
    else:
        fm_text = ""
        body = raw

    _y = _YAML()
    _y.default_flow_style = False
    _y.preserve_quotes = True
    fm_data = _y.load(fm_text) if fm_text.strip() else {}
    if fm_data is None:
        fm_data = {}
    fm_data["concepts"] = [{"name": c["name"], "type": c["type"]} for c in parsed_concepts]
    buf = io.StringIO()
    _y.dump(dict(fm_data), buf)
    new_fm = buf.getvalue()
    normalized_md.write_text(f"---\n{new_fm}---\n\n{body.lstrip()}")

    # Update concepts.yaml
    concepts_path = repo_root() / "topics" / topic / "process" / "concepts.yaml"
    concepts_path.parent.mkdir(parents=True, exist_ok=True)
    _yc = _YAML()
    _yc.default_flow_style = False
    if concepts_path.exists():
        existing = _yc.load(concepts_path.read_text())
        if existing is None:
            existing = {"topic": topic, "generated": now_iso(), "concepts": []}
    else:
        existing = {"topic": topic, "generated": now_iso(), "concepts": []}
    existing_concepts = existing.get("concepts", [])

    for pc in parsed_concepts:
        pc_name_lower = pc["name"].lower()
        match = next(
            (ec for ec in existing_concepts if ec.get("name", "").lower() == pc_name_lower),
            None,
        )
        if match is not None:
            sources_list = match.get("sources", [])
            if name not in sources_list:
                sources_list.append(name)
            match["sources"] = sources_list
        else:
            existing_concepts.append({
                "name": pc["name"],
                "type": pc["type"],
                "sources": [name],
            })
    existing["concepts"] = existing_concepts
    buf2 = io.StringIO()
    _yc.dump(dict(existing), buf2)
    concepts_path.write_text(buf2.getvalue())

    # Update tracking.yaml — soft-fail if source not found
    try:
        tracking_data = require_tracking()
        source_found = any(s.get("name") == name for s in tracking_data.get("sources", []))
    except Exception:
        source_found = False

    if source_found:
        def _update(tracking):
            for s in tracking.get("sources", []):
                if s.get("name") == name:
                    s["annotated_at"] = now_iso()
                    s["concept_count"] = len(parsed_concepts)
            append_root_event(
                tracking, "source_annotated",
                f"Annotated: {name} ({len(parsed_concepts)} concepts)"
            )
        locked_update_tracking(_update)
    else:
        try:
            def _update_event(tracking):
                append_root_event(
                    tracking, "source_annotated",
                    f"Annotated: {name} ({len(parsed_concepts)} concepts)"
                )
            locked_update_tracking(_update_event)
        except Exception:
            pass

    click.echo(f"✓ Annotated: {name} ({len(parsed_concepts)} concepts added to concepts.yaml)")


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
        click.echo("\nRun `rh-skills ingest implement <file>` to re-register changed sources.")
        raise SystemExit(1)
