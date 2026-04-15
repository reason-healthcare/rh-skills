"""Shared utilities for the rh-skills CLI."""

import contextlib
import fcntl
import hashlib
import os
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

import click


_CONFIG_KEYS = {
    "LLM_PROVIDER",
    "RH_REPO_ROOT",
    "RH_SOURCES_ROOT",
    "RH_STUB_RESPONSE",
    "RH_TOPICS_ROOT",
    "RH_TRACKING_FILE",
}


def _global_config_path() -> Path:
    """Return the global rh-skills config path."""
    return Path.home() / ".rh-skills.toml"


def _local_config_path() -> Path | None:
    """Return the nearest local rh-skills config path from cwd upwards."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        path = parent / ".rh-skills.toml"
        if path.exists():
            return path
    return None


def _load_config_file(path: Path) -> dict[str, str]:
    """Load a TOML config file and normalize supported keys."""
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    data: dict[str, str] = {}

    for key in _CONFIG_KEYS:
        value = raw.get(key)
        if value is not None:
            data[key] = str(value)

    paths = raw.get("paths")
    if isinstance(paths, dict):
        mapping = {
            "repo_root": "RH_REPO_ROOT",
            "topics_root": "RH_TOPICS_ROOT",
            "tracking_file": "RH_TRACKING_FILE",
            "sources_root": "RH_SOURCES_ROOT",
        }
        for key, env_key in mapping.items():
            value = paths.get(key)
            if value is not None:
                data[env_key] = str(value)

    llm = raw.get("llm")
    if isinstance(llm, dict):
        mapping = {
            "provider": "LLM_PROVIDER",
            "stub_response": "RH_STUB_RESPONSE",
        }
        for key, env_key in mapping.items():
            value = llm.get(key)
            if value is not None:
                data[env_key] = str(value)

    return data


def config_value(key: str, default: str | None = None) -> str | None:
    """Return a config value with precedence ENV > local > global."""
    if key not in _CONFIG_KEYS:
        return default

    value = default

    global_config = _global_config_path()
    if global_config.exists():
        value = _load_config_file(global_config).get(key, value)

    local_config = _local_config_path()
    if local_config is not None:
        value = _load_config_file(local_config).get(key, value)

    return os.environ.get(key, value)


# ── Path resolution ────────────────────────────────────────────────────────────

def repo_root() -> Path:
    """Return repo root from config or by walking up from cwd."""
    if env := config_value("RH_REPO_ROOT"):
        return Path(env)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "tracking.yaml").exists() or (parent / "pyproject.toml").exists():
            return parent
    return cwd


def topics_root() -> Path:
    """Return topics root directory."""
    if env := config_value("RH_TOPICS_ROOT"):
        return Path(env)
    return repo_root() / "topics"


def tracking_file() -> Path:
    """Return path to tracking.yaml."""
    if env := config_value("RH_TRACKING_FILE"):
        return Path(env)
    return repo_root() / "tracking.yaml"


def sources_root() -> Path:
    """Return path to sources directory."""
    if env := config_value("RH_SOURCES_ROOT"):
        return Path(env)
    return repo_root() / "sources"


def topic_dir(name: str) -> Path:
    """Return path to a topic directory."""
    return topics_root() / name


def bundled_skills_dir() -> Path:
    """Return path to bundled curated skills.

    Prefers the package-bundled copy (works after uv tool install / wheel install).
    Falls back to the source repo's skills/.curated/ for editable installs.
    """
    bundled = Path(__file__).parent / "skills"
    if bundled.exists():
        return bundled
    return repo_root() / "skills" / ".curated"


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
    """Write data to tracking.yaml atomically (temp file + os.replace)."""
    tf = tracking_file()
    y = _yaml_rt()
    with tempfile.NamedTemporaryFile(
        mode="w", dir=tf.parent, suffix=".tmp", delete=False, encoding="utf-8"
    ) as tmp:
        y.dump(data, tmp)
        tmp_path = tmp.name
    os.replace(tmp_path, tf)


@contextlib.contextmanager
def _tracking_lock():
    """Hold an exclusive advisory lock on tracking.yaml for the duration of the block.

    Uses a sibling .lock file so the lock is independent of the YAML file
    itself; the lock file is never removed (harmless, idempotent).
    """
    lock_path = tracking_file().with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def locked_update_tracking(fn) -> None:
    """Load tracking.yaml, call fn(tracking), then save atomically — all under an exclusive lock.

    Use this for every read-modify-write cycle to prevent concurrent ingest
    processes from racing on tracking.yaml.
    """
    with _tracking_lock():
        tracking = require_tracking()
        fn(tracking)
        save_tracking(tracking)


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
