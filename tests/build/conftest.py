from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SCRIPT_PATH = REPO_ROOT / "scripts" / "build-skills.sh"


def _copytree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, dirs_exist_ok=True)


@pytest.fixture
def build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "skills" / ".curated").mkdir(parents=True)
    (repo_root / "skills" / "_profiles").mkdir(parents=True)
    (repo_root / "dist").mkdir()

    _copytree(
        FIXTURES_ROOT / "curated" / "rh-inf-sample",
        repo_root / "skills" / ".curated" / "rh-inf-sample",
    )
    _copytree(REPO_ROOT / "skills" / "_profiles", repo_root / "skills" / "_profiles")

    return repo_root


@pytest.fixture
def build_env(build_repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["RH_SKILLS_REPO_ROOT"] = str(build_repo)
    env["RH_SKILLS_CURATED_DIR"] = str(build_repo / "skills" / ".curated")
    env["RH_SKILLS_PROFILES_DIR"] = str(build_repo / "skills" / "_profiles")
    env["RH_SKILLS_OUTPUT_DIR"] = str(build_repo / "dist")
    return env


@pytest.fixture(autouse=True)
def ensure_script_executable() -> None:
    current_mode = SCRIPT_PATH.stat().st_mode
    SCRIPT_PATH.chmod(current_mode | stat.S_IXUSR)
