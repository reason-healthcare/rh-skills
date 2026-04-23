"""rh-skills formalize-config — Configure formalize metadata for a topic."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.common import require_topic, require_tracking, topic_dir
from rh_skills.fhir.normalize import to_kebab_case

CONFIG_FILENAME = "formalize-config.yaml"

# Fields and the order they appear in the written file
_FIELD_ORDER = ["name", "id", "canonical", "status", "version"]

_STATUS_CHOICES = click.Choice(["draft", "active", "retired", "unknown"])


# ── Public helpers (imported by formalize.py and package.py) ──────────────────

def config_path(td: Path) -> Path:
    return td / "process" / CONFIG_FILENAME


def load_formalize_config(td: Path) -> dict | None:
    """Return the formalize config dict for a topic, or None if not found."""
    path = config_path(td)
    if not path.exists():
        return None
    y = YAML()
    with open(path) as f:
        return y.load(f) or {}


def save_formalize_config(td: Path, cfg: dict) -> None:
    """Write formalize-config.yaml for a topic."""
    path = config_path(td)
    path.parent.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    # Preserve field order
    ordered = {k: cfg[k] for k in _FIELD_ORDER if k in cfg}
    ordered.update({k: v for k, v in cfg.items() if k not in _FIELD_ORDER})
    with open(path, "w") as f:
        y.dump(ordered, f)


def suggest_defaults(topic: str, existing: dict | None = None) -> dict:
    """Return suggested default values for config fields."""
    slug = to_kebab_case(topic)
    name = "".join(w.capitalize() for w in slug.split("-"))
    ex = existing or {}
    return {
        "name": ex.get("name") or name,
        "id": ex.get("id") or slug,
        "canonical": ex.get("canonical") or "http://example.org/fhir",
        "status": ex.get("status") or "draft",
        "version": ex.get("version") or "0.1.0",
    }


# ── Click command ─────────────────────────────────────────────────────────────

@click.command("formalize-config")
@click.argument("topic")
@click.option(
    "--non-interactive", is_flag=True,
    help="Accept all suggested defaults without prompting.",
)
@click.option("--name", "opt_name", default=None, help="PascalCase IG name override.")
@click.option("--id", "opt_id", default=None, help="Kebab-case ID override.")
@click.option("--canonical", "opt_canonical", default=None, help="Base canonical URL override.")
@click.option("--status", "opt_status", default=None, type=_STATUS_CHOICES, help="FHIR status override.")
@click.option("--version", "opt_version", default=None, help="SemVer version override.")
@click.option("--force", is_flag=True, help="Overwrite existing config without prompting.")
def formalize_config(
    topic: str,
    non_interactive: bool,
    opt_name: str | None,
    opt_id: str | None,
    opt_canonical: str | None,
    opt_status: str | None,
    opt_version: str | None,
    force: bool,
) -> None:
    """Set up or update formalize metadata for a topic.

    Creates (or updates) topics/<topic>/process/formalize-config.yaml with
    the values used when generating FHIR artifacts and CQL libraries:

    \b
      name      — PascalCase machine name (used in ImplementationGuide.name)
      id        — kebab-case identifier (used in IG id and packageId)
      canonical — base URL for resource.url (e.g. https://example.org/fhir)
      status    — FHIR publication status (default: draft)
      version   — SemVer artifact version (default: 0.1.0)
    """
    tracking = require_tracking()
    require_topic(tracking, topic)
    td = topic_dir(topic)

    existing = load_formalize_config(td)

    if existing and not force and not non_interactive:
        # Interactive update: existing values become the defaults
        pass
    elif existing and not force and non_interactive:
        click.echo(
            f"formalize-config.yaml already exists for '{topic}'. "
            "Use --force to overwrite.",
            err=True,
        )
        return

    defaults = suggest_defaults(topic, existing)

    # Apply any explicit CLI overrides
    cli_overrides: dict = {}
    if opt_name is not None:
        cli_overrides["name"] = opt_name
    if opt_id is not None:
        cli_overrides["id"] = opt_id
    if opt_canonical is not None:
        cli_overrides["canonical"] = opt_canonical
    if opt_status is not None:
        cli_overrides["status"] = opt_status
    if opt_version is not None:
        cli_overrides["version"] = opt_version

    action = "Updating" if existing else "Setting up"
    click.echo(f"{action} formalize config for '{topic}'")
    click.echo()

    if non_interactive or cli_overrides:
        cfg = {**defaults, **cli_overrides}
    else:
        cfg = {
            "name": click.prompt("  Name (PascalCase)", default=defaults["name"]),
            "id": click.prompt("  ID (kebab-case)", default=defaults["id"]),
            "canonical": click.prompt(
                "  Canonical base URL",
                default=defaults["canonical"],
            ),
            "status": click.prompt(
                "  Status",
                default=defaults["status"],
                type=_STATUS_CHOICES,
            ),
            "version": click.prompt("  Version", default=defaults["version"]),
        }

    save_formalize_config(td, cfg)

    click.echo()
    click.echo(f"  Wrote topics/{topic}/process/{CONFIG_FILENAME}")
    click.echo(f"  name:      {cfg['name']}")
    click.echo(f"  id:        {cfg['id']}")
    click.echo(f"  canonical: {cfg['canonical']}")
    click.echo(f"  status:    {cfg['status']}")
    click.echo(f"  version:   {cfg['version']}")
