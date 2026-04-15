"""Verify bundled and repo-root schema directories stay in sync."""

import filecmp
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_SCHEMAS = REPO_ROOT / "schemas"
BUNDLED_SCHEMAS = REPO_ROOT / "src" / "rh_skills" / "schemas"


def test_schema_dirs_exist():
    assert ROOT_SCHEMAS.is_dir(), f"Missing {ROOT_SCHEMAS}"
    assert BUNDLED_SCHEMAS.is_dir(), f"Missing {BUNDLED_SCHEMAS}"


def test_schema_dirs_have_same_files():
    root_files = sorted(p.name for p in ROOT_SCHEMAS.glob("*.yaml"))
    bundled_files = sorted(p.name for p in BUNDLED_SCHEMAS.glob("*.yaml"))
    assert root_files == bundled_files, (
        f"Schema file mismatch:\n"
        f"  schemas/:              {root_files}\n"
        f"  src/rh_skills/schemas: {bundled_files}"
    )


@pytest.mark.parametrize("name", sorted(p.name for p in (Path(__file__).resolve().parents[2] / "schemas").glob("*.yaml")))
def test_schema_file_identical(name):
    root = ROOT_SCHEMAS / name
    bundled = BUNDLED_SCHEMAS / name
    assert bundled.exists(), f"Missing bundled copy: {bundled}"
    assert filecmp.cmp(root, bundled, shallow=False), (
        f"Schema drift detected: schemas/{name} differs from src/rh_skills/schemas/{name}.\n"
        f"Edit the root copy and run: cp schemas/{name} src/rh_skills/schemas/{name}"
    )
