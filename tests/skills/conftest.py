"""Shared fixtures and helpers for skill validation tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURATED_DIR = REPO_ROOT / "skills" / ".curated"
TEMPLATE_DIR = REPO_ROOT / "skills" / "_template"

# Frontmatter keys allowed in RH skills framework SKILL.md files.
# Extends the base Agent Skills standard with HI-specific fields.
REQUIRED_FRONTMATTER_KEYS = {"name", "description", "compatibility"}
OPTIONAL_FRONTMATTER_KEYS = {
    "context_files",
    "metadata",
    "license",
    "allowed-tools",
    "lifecycle_stage",
    "reads_from",
    "writes_via_cli",
}
ALL_ALLOWED_FRONTMATTER_KEYS = REQUIRED_FRONTMATTER_KEYS | OPTIONAL_FRONTMATTER_KEYS

# Template placeholder tokens that must NOT appear in implemented skills.
PLACEHOLDER_PATTERNS = [
    re.compile(r"<skill-name>"),
    re.compile(r"<Author Name"),
    re.compile(r"<One sentence"),
    re.compile(r"<One-line"),
    re.compile(r"Modes: plan · implement · verify\.$"),  # template default, should be customised
]


def curated_skill_dirs() -> list[Path]:
    """Skill dirs in skills/.curated/ that have a SKILL.md (i.e. are implemented)."""
    if not CURATED_DIR.exists():
        return []
    return sorted(
        d for d in CURATED_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def parse_frontmatter(skill_md: Path) -> dict[str, str]:
    """Parse YAML frontmatter from a SKILL.md file.

    Returns a flat dict of key → raw string value.
    Raises ValueError if frontmatter is missing or malformed.
    """
    content = skill_md.read_text()
    if not content.startswith("---\n"):
        raise ValueError(f"{skill_md}: missing YAML frontmatter opening '---'")
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_md}: missing YAML frontmatter closing '---'")
    frontmatter_text = parts[1]
    data: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if not line.strip() or line.startswith("#") or line.startswith(" ") or line.startswith("\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip().strip("'\"")
    if not data:
        raise ValueError(f"{skill_md}: frontmatter parsed to empty dict")
    return data


def skill_body(skill_md: Path) -> str:
    """Return the Markdown body of a SKILL.md (everything after closing ---)."""
    content = skill_md.read_text()
    parts = content.split("---\n", 2)
    return parts[2] if len(parts) >= 3 else content


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=curated_skill_dirs(),
    ids=lambda d: d.name,
)
def curated_skill(request) -> Path:
    """Parametrized fixture: one value per implemented curated skill directory."""
    return request.param
