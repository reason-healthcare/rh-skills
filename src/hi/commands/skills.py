"""rh-skills skills — Manage curated agent skills for agent-native usage."""

import shutil
from pathlib import Path

import click

from hi.common import bundled_skills_dir, log_info, log_warn


@click.group()
def skills():
    """Manage curated RH skills."""
    pass


@skills.command()
@click.option(
    "--from", "source", default=None, metavar="PATH",
    help="Install from a local skills directory (e.g. skills/.curated/) instead of bundled.",
)
@click.option(
    "--dest", default=None, metavar="PATH",
    help="Destination directory (default: .agents/skills/ relative to cwd).",
)
@click.option("--force", is_flag=True, help="Overwrite skills that already exist.")
def install(source, dest, force):
    """Install curated RH skills into .agents/skills/.

    By default installs from the skills bundled with the rh-skills package.
    Pass --from to install from a local directory instead (useful during
    skill development so you can test edits without reinstalling).

    \b
    Examples:
      rh-skills skills install                          # install bundled skills
      rh-skills skills install --from skills/.curated   # install from local dev repo
      rh-skills skills install --force                  # overwrite existing installs
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
        installed.append(skill_src.name)

    for name in installed:
        log_info(f"Installed: {name}")
    for name in skipped:
        log_warn(f"Skipped (already exists): {name}  — use --force to overwrite")

    click.echo()
    click.echo(f"  Source:      {src_dir}")
    click.echo(f"  Destination: {dest_dir}")
    click.echo(f"  Installed:   {len(installed)}  Skipped: {len(skipped)}")
