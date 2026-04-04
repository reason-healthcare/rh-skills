"""Shared utilities for the hi CLI."""

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

import click


# ── Path resolution ────────────────────────────────────────────────────────────

def repo_root() -> Path:
    """Return repo root: HI_REPO_ROOT env or walk up from cwd looking for tracking.yaml/pyproject.toml."""
    if env := os.environ.get("HI_REPO_ROOT"):
        return Path(env)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "tracking.yaml").exists() or (parent / "pyproject.toml").exists():
            return parent
    return cwd


def topics_root() -> Path:
    """Return topics root directory."""
    if env := os.environ.get("HI_TOPICS_ROOT"):
        return Path(env)
    return repo_root() / "topics"


def tracking_file() -> Path:
    """Return path to tracking.yaml."""
    if env := os.environ.get("HI_TRACKING_FILE"):
        return Path(env)
    return repo_root() / "tracking.yaml"


def sources_root() -> Path:
    """Return path to sources directory."""
    if env := os.environ.get("HI_SOURCES_ROOT"):
        return Path(env)
    return repo_root() / "sources"


def topic_dir(name: str) -> Path:
    """Return path to a topic directory."""
    return topics_root() / name


def schemas_dir() -> Path:
    """Return path to schemas directory.

    Prefers bundled schemas next to this module (works after uv tool install).
    Falls back to repo_root()/schemas for dev-repo use.
    """
    bundled = Path(__file__).parent / "schemas"
    if bundled.exists():
        return bundled
    return repo_root() / "schemas"


# ── Tracking YAML ─────────────────────────────────────────────────────────────

def _yaml_rt() -> YAML:
    """Round-trip YAML instance for tracking.yaml (preserves ordering/comments)."""
    y = YAML()
    y.default_flow_style = False
    y.preserve_quotes = True
    return y


def _yaml_safe() -> YAML:
    """Safe YAML instance for read-only schema files."""
    y = YAML(typ="safe")
    return y


def load_tracking() -> dict:
    """Load tracking.yaml and return as dict."""
    y = _yaml_rt()
    with open(tracking_file()) as f:
        return y.load(f)


def save_tracking(data: dict) -> None:
    """Write data to tracking.yaml."""
    y = _yaml_rt()
    with open(tracking_file(), "w") as f:
        y.dump(data, f)


def require_tracking() -> dict:
    """Load tracking or raise ClickException if missing."""
    tf = tracking_file()
    if not tf.exists():
        raise click.ClickException(f"tracking.yaml not found: {tf}")
    return load_tracking()


def append_root_event(tracking: dict, type_: str, description: str) -> None:
    """Append an event to the root events list."""
    tracking["events"].append({
        "timestamp": now_iso(),
        "type": type_,
        "description": description,
    })


def append_topic_event(tracking: dict, topic_name: str, type_: str, description: str) -> None:
    """Append an event to a topic's events list."""
    for topic in tracking.get("topics", []):
        if topic["name"] == topic_name:
            topic["events"].append({
                "timestamp": now_iso(),
                "type": type_,
                "description": description,
            })
            return


def require_topic(tracking: dict, name: str) -> dict:
    """Return topic dict or raise UsageError if not found."""
    for topic in tracking.get("topics", []):
        if topic["name"] == name:
            return topic
    raise click.UsageError(f"Topic '{name}' not found")


# ── SHA-256 ────────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Timestamps ─────────────────────────────────────────────────────────────────

def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_date() -> str:
    """Return current UTC date as YYYY-MM-DD string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Logging ────────────────────────────────────────────────────────────────────

def log_info(msg: str) -> None:
    click.echo(f"✓ {msg}")


def log_warn(msg: str) -> None:
    click.echo(f"! [WARN] {msg}")


def log_error(msg: str) -> None:
    click.echo(f"[ERROR] {msg}", err=True)


# ── Schema loading ─────────────────────────────────────────────────────────────

def load_schema(schema_name: str) -> dict:
    """Load a schema YAML file (read-only, safe)."""
    path = schemas_dir() / schema_name
    if not path.exists():
        raise click.ClickException(f"Schema not found: {path}")
    y = _yaml_safe()
    with open(path) as f:
        return y.load(f)
