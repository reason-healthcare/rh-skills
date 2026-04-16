"""rh-skills source — Build and manage discovery-plan source entries."""

import hashlib
import json
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.commands.validate import VALID_EVIDENCE_LEVELS, VALID_SOURCE_TYPES
from rh_skills.common import log_info, log_warn, require_tracking, sources_root, topic_dir


def _yaml_rt() -> YAML:
    y = YAML()
    y.default_flow_style = False
    y.width = 120
    return y


def _plan_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "discovery-plan.yaml"


def _load_plan(path: Path) -> dict:
    y = YAML(typ="safe")
    with path.open() as f:
        return y.load(f) or {}


def _save_plan(path: Path, data: dict) -> None:
    y = _yaml_rt()
    with path.open("w") as f:
        y.dump(data, f)


# ── CLI group ──────────────────────────────────────────────────────────────────

@click.group()
def source():
    """Build and manage discovery-plan source entries."""


# ── rh-skills source add ───────────────────────────────────────────────────────

@source.command("add")
@click.option("--type",     "source_type", required=True,
              help=f"Source type. One of: {', '.join(sorted(VALID_SOURCE_TYPES))}")
@click.option("--url",      default=None,  help="URL of the source (required when --access open).")
@click.option("--title",    required=True, help="Human-readable title of the source.")
@click.option("--evidence", default=None,
              help=f"Evidence level. One of: {', '.join(sorted(VALID_EVIDENCE_LEVELS))}")
@click.option("--rationale", required=True,
              help="Why this source is relevant to the discovery plan.")
@click.option("--search-terms", "search_terms", multiple=True,
              help="Search terms used to find this source (repeatable).")
@click.option("--access",   default="open",
              type=click.Choice(["open", "authenticated", "manual"]),
              show_default=True, help="Access level for this source.")
@click.option("--year",     default=None, help="Publication year (e.g. 2024).")
@click.option("--authors",  default=None, help="Author(s) as a free-text string.")
@click.option("--notes",    default=None, help="Optional free-text notes.")
@click.option("--name",     default=None,
              help="Short slug for the source (default: derived from --title).")
@click.option("--append-to-plan", "append_to", default=None, metavar="TOPIC",
              help="If given, append the new entry to this topic's discovery-plan.yaml.")
@click.option("--dry-run",  is_flag=True, default=False,
              help="Print the entry YAML without writing to disk.")
def add(source_type, url, title, evidence, rationale, search_terms,
        access, year, authors, notes, name, append_to, dry_run):
    """Add a single source entry, validate it, and optionally append to a plan.

    \b
    Examples:
      rh-skills source add \\
        --type clinical-guideline \\
        --title "ADA Standards of Care 2025" \\
        --url "https://diabetesjournals.org/care/issue/48/Supplement_1" \\
        --evidence grade-a \\
        --rationale "Primary guideline for diabetes management" \\
        --search-terms "diabetes standards of care" \\
        --access open \\
        --year 2025 \\
        --append-to-plan diabetes-ccm
    """
    # ── Validate type ──────────────────────────────────────────────────────────
    if source_type not in VALID_SOURCE_TYPES:
        closest = sorted(VALID_SOURCE_TYPES)
        raise click.ClickException(
            f"Unknown source type: {source_type!r}\n"
            f"Valid types: {', '.join(closest)}"
        )

    # ── Validate evidence level ────────────────────────────────────────────────
    if evidence and evidence not in VALID_EVIDENCE_LEVELS:
        raise click.ClickException(
            f"Unknown evidence level: {evidence!r}\n"
            f"Valid levels: {', '.join(sorted(VALID_EVIDENCE_LEVELS))}"
        )

    # ── Warn on missing URL for open sources ───────────────────────────────────
    if access == "open" and not url:
        log_warn("--access open but no --url provided; consider adding a URL.")

    # ── Derive slug name ───────────────────────────────────────────────────────
    if not name:
        import re
        name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]

    # ── Build entry dict ───────────────────────────────────────────────────────
    entry: dict = {
        "name": name,
        "type": source_type,
        "title": title,
        "rationale": rationale,
        "search_terms": list(search_terms) if search_terms else [],
        "evidence_level": evidence or "n/a",
        "access": access,
    }
    if url:
        entry["url"] = url
    if year:
        entry["year"] = year
    if authors:
        entry["authors"] = authors
    if notes:
        entry["notes"] = notes

    # ── Render YAML ────────────────────────────────────────────────────────────
    y = _yaml_rt()
    import io
    buf = io.StringIO()
    y.dump({"source": entry}, buf)
    entry_yaml = buf.getvalue()

    click.echo()
    click.echo("─── Source entry ───────────────────────────────────────────")
    click.echo(entry_yaml.replace("source:\n", "").rstrip())
    click.echo("────────────────────────────────────────────────────────────")

    if dry_run:
        click.echo("\n(dry-run — not written)")
        return

    if not append_to:
        click.echo("\nUse --append-to-plan <topic> to append this entry to a plan.")
        return

    # ── Append to plan ─────────────────────────────────────────────────────────
    tracking = require_tracking()
    plan_file = _plan_path(append_to)

    if not plan_file.exists():
        raise click.ClickException(
            f"No discovery plan found at {plan_file}\n"
            f"Run 'rh-skills validate --plan <file>' to create or validate one first."
        )

    plan = _load_plan(plan_file)
    sources = plan.get("sources", [])

    # Check for duplicate name
    existing_names = {s.get("name") for s in sources if isinstance(s, dict)}
    if name in existing_names:
        raise click.ClickException(
            f"A source named {name!r} already exists in the plan.\n"
            f"Use --name to provide a different slug."
        )

    sources.append(entry)
    plan["sources"] = sources
    _save_plan(plan_file, plan)

    log_info(f"Appended '{name}' to {plan_file}  ({len(sources)} sources total)")


# ── rh-skills source scan ──────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _type_hint(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf": "document",
        ".csv": "dataset",
        ".tsv": "dataset",
        ".xlsx": "dataset",
        ".xls": "dataset",
        ".md": "document",
        ".txt": "document",
        ".docx": "document",
        ".xml": "data",
        ".json": "data",
    }.get(ext, "unknown")


@source.command("scan")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output results as JSON.")
def scan(as_json):
    """Scan sources/ for untracked files or files with SHA drift.

    \b
    Reports three categories:
      UNTRACKED   — file is in sources/ but not registered in tracking.yaml
      SHA-CHANGED — file is registered but its contents have changed
      TRACKED     — file is registered and SHA matches

    \b
    Example:
      rh-skills source scan
    """
    src_root = sources_root()
    if not src_root.exists():
        if as_json:
            click.echo(json.dumps({"untracked": [], "sha_changed": [], "tracked": [],
                                   "note": "sources/ directory does not exist"}))
        else:
            click.echo("sources/ directory does not exist.")
        return

    try:
        tracking = require_tracking()
    except SystemExit:
        tracking = {}

    tracked_entries: dict[str, dict] = {}
    for source in tracking.get("sources", []):
        file_key = source.get("file")
        if file_key:
            tracked_entries[file_key] = source

    untracked: list[dict] = []
    sha_changed: list[dict] = []
    tracked_ok: list[dict] = []

    for path in sorted(src_root.iterdir()):
        if not path.is_file():
            continue
        rel = f"sources/{path.name}"
        size_kb = round(path.stat().st_size / 1024, 1)
        sha = _sha256_file(path)
        hint = _type_hint(path)

        entry = tracked_entries.get(rel)
        if entry is None:
            untracked.append({
                "file": rel,
                "size_kb": size_kb,
                "sha256": sha,
                "type_hint": hint,
            })
        elif entry.get("checksum") and entry["checksum"] != sha:
            sha_changed.append({
                "file": rel,
                "name": entry.get("name"),
                "size_kb": size_kb,
                "sha256": sha,
                "tracked_sha256": entry["checksum"],
                "type_hint": hint,
            })
        else:
            tracked_ok.append({
                "file": rel,
                "name": entry.get("name"),
                "size_kb": size_kb,
                "sha256": sha,
                "type_hint": hint,
            })

    if as_json:
        click.echo(json.dumps({
            "untracked": untracked,
            "sha_changed": sha_changed,
            "tracked": tracked_ok,
        }, indent=2))
        return

    total = len(untracked) + len(sha_changed) + len(tracked_ok)
    click.echo(f"sources/ scan — {total} file(s)")
    click.echo()

    for item in untracked:
        click.echo(f"  UNTRACKED    {item['file']:<50}  {item['size_kb']:>6} KB  [{item['type_hint']}]")
    for item in sha_changed:
        click.echo(f"  SHA-CHANGED  {item['file']:<50}  {item['size_kb']:>6} KB  [{item['type_hint']}]")
    for item in tracked_ok:
        click.echo(f"  TRACKED      {item['file']:<50}  {item['size_kb']:>6} KB  [{item['type_hint']}]")

    if untracked or sha_changed:
        click.echo()
        click.echo(f"{len(untracked)} untracked, {len(sha_changed)} SHA-changed, {len(tracked_ok)} tracked")
        if untracked:
            click.echo()
            click.echo("To add untracked files to your discovery plan:")
            click.echo("  rh-skills source add --type <type> --name <slug> --title \"...\" \\")
            click.echo("    --rationale \"...\" --access manual --append-to-plan <topic>")
    else:
        click.echo()
        click.echo(f"All {total} file(s) are tracked and up to date.")
