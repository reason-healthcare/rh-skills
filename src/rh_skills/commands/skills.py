"""rh-skills skills — Manage curated agent skills for agent-native usage."""

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.common import bundled_skills_dir, log_info, log_warn


# ── Platform registry ──────────────────────────────────────────────────────────

#  key        human label                          project-relative dest dir
PLATFORMS = [
    ("generic", "Generic / Copilot  (.agents/skills/)",  ".agents/skills"),
    ("claude",  "Claude             (.claude/commands/)", ".claude/commands"),
    ("cursor",  "Cursor             (.cursor/rules/)",    ".cursor/rules"),
    ("gemini",  "Gemini             (.gemini/)",          ".gemini"),
]
PLATFORM_KEYS = [p[0] for p in PLATFORMS]

LOCKFILE_NAME = ".rh-skills-lock.yaml"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _profiles_dir() -> Path:
    """Return path to bundled profile support files (preambles, suffixes)."""
    bundled = Path(__file__).parent.parent / "skills_profiles"
    if bundled.exists():
        return bundled
    # dev fallback: repo checkout
    from rh_skills.common import repo_root
    return repo_root() / "skills" / "_profiles" / "support"


def _strip_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown file. Returns (fm_dict, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    yaml = YAML(typ="safe")
    try:
        fm = yaml.load(text[3:end]) or {}
    except Exception:
        fm = {}
    body = text[end + 4:].lstrip("\n")
    return fm, body


def _strip_section(text: str, section_name: str) -> str:
    """Remove a named ## section and its content up to the next ## heading."""
    pattern = rf"(?m)^##\s+{re.escape(section_name)}\s*\n.*?(?=^##|\Z)"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip() + "\n"


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _dir_checksum(directory: Path) -> str:
    """Stable checksum over all files in a directory (sorted by path)."""
    h = hashlib.sha256()
    for f in sorted(directory.rglob("*")):
        if f.is_file():
            h.update(f.relative_to(directory).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def _skill_version(skill_dir: Path) -> str:
    text = (skill_dir / "SKILL.md").read_text()
    fm, _ = _strip_frontmatter(text)
    meta = fm.get("metadata", {})
    return meta.get("version", "unknown") if isinstance(meta, dict) else "unknown"


# ── Per-platform renderers ─────────────────────────────────────────────────────

def _render_claude(skill_dir: Path) -> str:
    preamble_file = _profiles_dir() / "claude-preamble.md"
    preamble = preamble_file.read_text() if preamble_file.exists() else ""
    _, body = _strip_frontmatter((skill_dir / "SKILL.md").read_text())
    parts = [p.strip() for p in [preamble, body] if p.strip()]
    return "\n\n".join(parts) + "\n"


def _render_cursor(skill_dir: Path) -> str:
    fm, body = _strip_frontmatter((skill_dir / "SKILL.md").read_text())
    description = fm.get("description", skill_dir.name)
    if isinstance(description, str) and "\n" in description:
        description = description.split("\n")[0].strip()
    return f"---\ndescription: {description}\n---\n\n{body}"


def _render_generic(skill_dir: Path) -> str:
    """Return SKILL.md with support-file paths rewritten to their installed workspace location.

    Bare references like ``reference.md`` and ``examples/plan.yaml`` become
    ``.agents/skills/<name>/reference.md`` etc., so the agent can resolve them
    from the workspace root where it normally runs.
    """
    name = skill_dir.name
    prefix = f".agents/skills/{name}"
    text = (skill_dir / "SKILL.md").read_text()
    # Rewrite bare `reference.md` references (not already path-qualified)
    text = re.sub(r'(?<![./\w])reference\.md', f'{prefix}/reference.md', text)
    # Rewrite bare `examples/<file>` references
    text = re.sub(r'(?<![./\w])examples/', f'{prefix}/examples/', text)
    return text


def _render_gemini(skill_dir: Path) -> str:
    preamble_file = _profiles_dir() / "gemini-preamble.md"
    suffix_file   = _profiles_dir() / "gemini-suffix.md"
    preamble = preamble_file.read_text() if preamble_file.exists() else ""
    suffix   = suffix_file.read_text()   if suffix_file.exists()   else ""
    _, body = _strip_frontmatter((skill_dir / "SKILL.md").read_text())
    body = _strip_section(body, "Pre-Execution Checks")
    parts = [p.strip() for p in [preamble, body, suffix] if p.strip()]
    return "\n\n".join(parts) + "\n"


# ── Install + checksum per platform ───────────────────────────────────────────

def _install_skill(skill_dir: Path, platform: str, project_root: Path, force: bool) -> str:
    """Install one skill for one platform. Returns checksum of installed content."""
    name = skill_dir.name

    if platform == "generic":
        dest = project_root / ".agents" / "skills" / name
        if dest.exists():
            if not force:
                return _dir_checksum(dest)
            shutil.rmtree(dest)
        shutil.copytree(skill_dir, dest)
        # Rewrite SKILL.md support-file paths to be workspace-root-relative
        (dest / "SKILL.md").write_text(_render_generic(skill_dir))
        return _dir_checksum(dest)

    renderers = {
        "claude":  (_render_claude,  project_root / ".claude"  / "commands", ".md"),
        "cursor":  (_render_cursor,  project_root / ".cursor"  / "rules",    ".mdc"),
        "gemini":  (_render_gemini,  project_root / ".gemini",               ".md"),
    }
    render_fn, dest_dir, ext = renderers[platform]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}{ext}"
    content = render_fn(skill_dir)
    if not dest.exists() or force:
        dest.write_text(content)
    return _sha256(content)


def _current_checksum(skill_name: str, platform: str, project_root: Path) -> str | None:
    """Return checksum of the currently installed skill file(s), or None if missing."""
    if platform == "generic":
        dest = project_root / ".agents" / "skills" / skill_name
        return _dir_checksum(dest) if dest.exists() else None

    paths = {
        "claude": project_root / ".claude"  / "commands" / f"{skill_name}.md",
        "cursor": project_root / ".cursor"  / "rules"    / f"{skill_name}.mdc",
        "gemini": project_root / ".gemini"               / f"{skill_name}.md",
    }
    dest = paths.get(platform)
    if dest is None or not dest.exists():
        return None
    return _sha256(dest.read_text())


# ── Lockfile I/O ───────────────────────────────────────────────────────────────

def _lockfile_path(project_root: Path) -> Path:
    return project_root / LOCKFILE_NAME


def _read_lockfile(project_root: Path) -> dict:
    path = _lockfile_path(project_root)
    if not path.exists():
        return {}
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text()) or {}


def _write_lockfile(project_root: Path, data: dict) -> None:
    from rh_skills import __version__
    data["rh_skills_version"] = __version__
    data["locked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    yaml = YAML()
    yaml.default_flow_style = False
    with open(_lockfile_path(project_root), "w") as f:
        yaml.dump(data, f)


# ── CLI group + commands ───────────────────────────────────────────────────────

@click.group()
def skills():
    """Manage curated RH skills for agent-native usage."""
    pass


@skills.command()
@click.option("--from", "source", default=None, metavar="PATH",
              help="Install from a local skills directory instead of bundled.")
@click.option("--dest", default=None, metavar="PATH",
              help="Destination directory (default: .agents/skills/ relative to cwd).")
@click.option("--force", is_flag=True, help="Overwrite skills that already exist.")
def install(source, dest, force):
    """Install curated RH skills into .agents/skills/ (low-level).

    For interactive first-time setup with platform selection and lockfile
    tracking, use: rh-skills skills init

    \b
    Examples:
      rh-skills skills install
      rh-skills skills install --from skills/.curated
      rh-skills skills install --force
    """
    src_dir = Path(source) if source else bundled_skills_dir()
    if not src_dir.exists():
        raise click.ClickException(f"Skills source directory not found: {src_dir}")

    dest_dir = Path(dest) if dest else Path.cwd() / ".agents" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)

    skill_dirs = sorted(p for p in src_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    if not skill_dirs:
        raise click.ClickException(f"No skills found in: {src_dir}")

    installed, skipped = [], []
    for skill_src in skill_dirs:
        skill_dest = dest_dir / skill_src.name
        if skill_dest.exists() and not force:
            skipped.append(skill_src.name)
            continue
        if skill_dest.exists():
            shutil.rmtree(skill_dest)
        shutil.copytree(skill_src, skill_dest)
        # Rewrite SKILL.md support-file paths to be workspace-root-relative
        (skill_dest / "SKILL.md").write_text(_render_generic(skill_src))
        installed.append(skill_src.name)

    for name in installed:
        log_info(f"Installed: {name}")
    for name in skipped:
        log_warn(f"Skipped (already exists): {name}  — use --force to overwrite")

    click.echo()
    click.echo(f"  Source:      {src_dir}")
    click.echo(f"  Destination: {dest_dir}")
    click.echo(f"  Installed:   {len(installed)}  Skipped: {len(skipped)}")


@skills.command()
@click.option("--from", "source", default=None, metavar="PATH",
              help="Install from a local skills directory instead of bundled.")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite skills that already exist.")
def init(source, force):
    """Interactive first-time skill installation with platform selection.

    Prompts for which agent platforms to support, installs skills to
    platform-appropriate locations, and writes a .rh-skills-lock.yaml
    for drift tracking.

    \b
    Platforms:
      generic  .agents/skills/<skill>/      (GitHub Copilot / AGENTS.md)
      claude   .claude/commands/<skill>.md
      cursor   .cursor/rules/<skill>.mdc
      gemini   .gemini/<skill>.md

    \b
    To update installed skills later:
      rh-skills skills update

    Skills are bundled with the rh-skills package. To get newer skills,
    upgrade the package:  pipx upgrade rh-skills
    """
    src_dir = Path(source) if source else bundled_skills_dir()
    if not src_dir.exists():
        raise click.ClickException(f"Skills source directory not found: {src_dir}")

    skill_dirs = sorted(p for p in src_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    if not skill_dirs:
        raise click.ClickException(f"No skills found in: {src_dir}")

    click.echo()
    click.echo("Select platforms to install skills for:")
    click.echo()
    for i, (key, label, _) in enumerate(PLATFORMS, 1):
        click.echo(f"  [{i}] {label}")
    click.echo()

    raw = click.prompt("Platforms (comma-separated numbers, or 'all')", default="all")

    if raw.strip().lower() == "all":
        selected = list(PLATFORM_KEYS)
    else:
        selected = []
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit() and 1 <= int(token) <= len(PLATFORMS):
                selected.append(PLATFORMS[int(token) - 1][0])
            elif token in PLATFORM_KEYS:
                selected.append(token)
        if not selected:
            raise click.ClickException("No valid platforms selected.")

    click.echo()
    click.echo(f"Installing {len(skill_dirs)} skills for: {', '.join(selected)}")
    click.echo()

    project_root = Path.cwd()
    skill_checksums: dict = {}

    for skill_dir in skill_dirs:
        name = skill_dir.name
        skill_checksums[name] = {
            "version": _skill_version(skill_dir),
            "checksums": {},
        }
        for platform in selected:
            try:
                checksum = _install_skill(skill_dir, platform, project_root, force=force)
                skill_checksums[name]["checksums"][platform] = checksum
                log_info(f"{platform:8s}  {name}")
            except Exception as exc:
                log_warn(f"{platform:8s}  {name}  ERROR: {exc}")

    _write_lockfile(project_root, {"platforms": selected, "source": str(src_dir), "skills": skill_checksums})

    click.echo()
    click.echo(f"  Lockfile written: {_lockfile_path(project_root)}")
    click.echo()
    click.echo("Run 'rh-skills skills check' at any time to detect drift.")


@skills.command()
def check():
    """Check installed skills against the lockfile for drift.

    Exits 0 if everything is up to date, 1 if drift is detected.
    """
    project_root = Path.cwd()
    lock = _read_lockfile(project_root)
    if not lock:
        raise click.ClickException("No lockfile found. Run 'rh-skills skills init' first.")

    platforms   = lock.get("platforms", [])
    skills_lock = lock.get("skills", {})
    drift_found = False

    click.echo()
    for skill_name, skill_data in skills_lock.items():
        locked_checksums = skill_data.get("checksums", {})
        click.echo(f"  {skill_name}")
        for platform in platforms:
            locked  = locked_checksums.get(platform)
            current = _current_checksum(skill_name, platform, project_root)
            if current is None:
                click.echo(f"    {platform:8s}  ✗  missing")
                drift_found = True
            elif current != locked:
                click.echo(f"    {platform:8s}  !  modified")
                drift_found = True
            else:
                click.echo(f"    {platform:8s}  ✓  up to date")
        click.echo()

    if drift_found:
        click.echo("Drift detected — run 'rh-skills skills update' to reconcile.")
        raise SystemExit(1)
    else:
        click.echo("All skills are up to date.")


@skills.command()
@click.option("--from", "source", default=None, metavar="PATH",
              help="Re-install from a specific source directory instead of bundled.")
def update(source):
    """Re-install skills and refresh the lockfile.

    Reads platform configuration from the existing lockfile and re-installs
    all skills, overwriting modified or missing files.

    Skills are bundled with the rh-skills package. To pull in new skills,
    first upgrade the package:  pipx upgrade rh-skills
    """
    project_root = Path.cwd()
    lock = _read_lockfile(project_root)
    if not lock:
        raise click.ClickException("No lockfile found. Run 'rh-skills skills init' first.")

    platforms = lock.get("platforms", [])
    src_dir = Path(source) if source else (
        Path(lock["source"]) if lock.get("source") else bundled_skills_dir()
    )
    if not src_dir.exists():
        raise click.ClickException(f"Skills source not found: {src_dir}")

    skill_dirs = sorted(p for p in src_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    if not skill_dirs:
        raise click.ClickException(f"No skills found in: {src_dir}")

    click.echo()
    click.echo(f"Updating {len(skill_dirs)} skills for: {', '.join(platforms)}")
    click.echo()

    skill_checksums: dict = {}
    for skill_dir in skill_dirs:
        name = skill_dir.name
        skill_checksums[name] = {
            "version": _skill_version(skill_dir),
            "checksums": {},
        }
        for platform in platforms:
            try:
                checksum = _install_skill(skill_dir, platform, project_root, force=True)
                skill_checksums[name]["checksums"][platform] = checksum
                log_info(f"{platform:8s}  {name}")
            except Exception as exc:
                log_warn(f"{platform:8s}  {name}  ERROR: {exc}")

    _write_lockfile(project_root, {"platforms": platforms, "source": str(src_dir), "skills": skill_checksums})

    click.echo()
    click.echo(f"  Lockfile updated: {_lockfile_path(project_root)}")


@skills.command()
@click.argument("skill_name", metavar="SKILL", required=False)
def info(skill_name):
    """Show location and contents of a bundled curated skill.

    \b
    Without SKILL: list all available skills with their version and file counts.
    With SKILL: show full paths to SKILL.md, reference.md, and examples/.

    \b
    Examples:
      rh-skills skills info
      rh-skills skills info rh-inf-discovery
    """
    src_dir = bundled_skills_dir()
    if not src_dir.exists():
        raise click.ClickException(f"Bundled skills directory not found: {src_dir}")

    if skill_name is None:
        skill_dirs = sorted(p for p in src_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
        if not skill_dirs:
            raise click.ClickException(f"No skills found in: {src_dir}")
        click.echo(f"\nBundled skills  ({src_dir})\n")
        for d in skill_dirs:
            ver = _skill_version(d)
            n_files = sum(1 for _ in d.rglob("*") if _.is_file())
            click.echo(f"  {d.name:<28}  v{ver}  ({n_files} files)")
        click.echo()
        return

    skill_dir = src_dir / skill_name
    if not skill_dir.exists() or not (skill_dir / "SKILL.md").exists():
        available = [d.name for d in src_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        raise click.ClickException(
            f"Skill '{skill_name}' not found.\nAvailable: {', '.join(sorted(available))}"
        )

    ver = _skill_version(skill_dir)
    click.echo(f"\n{skill_name}  (version {ver})\n")
    click.echo(f"  Location:    {skill_dir}")

    files = sorted(skill_dir.rglob("*"))
    click.echo(f"\n  Files:")
    for f in files:
        if f.is_file():
            rel = f.relative_to(skill_dir)
            size = f.stat().st_size
            click.echo(f"    {str(rel):<36}  {size:>6} bytes  {f}")
    click.echo()

