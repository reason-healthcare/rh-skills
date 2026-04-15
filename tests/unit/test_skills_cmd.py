"""Tests for rh-skills skills init/check/update commands."""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from rh_skills.commands.skills import skills


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_skill(skills_dir: Path, name: str, description: str = "A test skill") -> Path:
    skill = skills_dir / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n"
        f"metadata:\n  version: 1.0.0\n---\n\n# {name}\n\nSkill body.\n"
    )
    (skill / "reference.md").write_text(f"# {name} reference\n")
    return skill


@pytest.fixture()
def tmp_skills(tmp_path):
    """A minimal bundled-skills-like directory with two skills."""
    src = tmp_path / "skills"
    _make_skill(src, "rh-inf-discovery", "Discover clinical sources")
    _make_skill(src, "rh-inf-extract",   "Extract L2 artifacts")
    return src


@pytest.fixture()
def tmp_project(tmp_path, monkeypatch):
    """An empty project directory — CWD is changed to it for the test."""
    proj = tmp_path / "project"
    proj.mkdir()
    monkeypatch.chdir(proj)
    return proj


def run(args, input_text=""):
    return CliRunner().invoke(
        skills, args, input=input_text, catch_exceptions=False
    )


# ── init ───────────────────────────────────────────────────────────────────────

def test_init_all_platforms(tmp_skills, tmp_project):
    result = run(["init", "--from", str(tmp_skills)], input_text="all\n")
    assert result.exit_code == 0, result.output
    assert "Lockfile written" in result.output

    assert (tmp_project / ".agents" / "skills" / "rh-inf-discovery" / "SKILL.md").exists()
    assert (tmp_project / ".claude" / "commands" / "rh-inf-discovery.md").exists()
    assert (tmp_project / ".cursor" / "rules" / "rh-inf-discovery.mdc").exists()
    assert (tmp_project / ".gemini" / "rh-inf-discovery.md").exists()
    assert (tmp_project / ".rh-skills-lock.yaml").exists()


def test_init_selected_platforms(tmp_skills, tmp_project):
    result = run(["init", "--from", str(tmp_skills)], input_text="2,3\n")
    assert result.exit_code == 0, result.output
    assert (tmp_project / ".claude" / "commands" / "rh-inf-discovery.md").exists()
    assert (tmp_project / ".cursor" / "rules" / "rh-inf-discovery.mdc").exists()
    assert not (tmp_project / ".agents").exists()
    assert not (tmp_project / ".gemini").exists()


def test_init_writes_lockfile_with_platforms(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="1\n")
    from ruamel.yaml import YAML
    lock = YAML(typ="safe").load((tmp_project / ".rh-skills-lock.yaml").read_text())
    assert lock["platforms"] == ["generic"]
    assert "rh-inf-discovery" in lock["skills"]
    assert "generic" in lock["skills"]["rh-inf-discovery"]["checksums"]


def test_init_installs_all_skills(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="1\n")
    assert (tmp_project / ".agents" / "skills" / "rh-inf-discovery").exists()
    assert (tmp_project / ".agents" / "skills" / "rh-inf-extract").exists()


# ── check ──────────────────────────────────────────────────────────────────────

def test_check_passes_when_up_to_date(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="1\n")
    result = run(["check"])
    assert result.exit_code == 0
    assert "up to date" in result.output


def test_check_detects_missing_file(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="2\n")
    (tmp_project / ".claude" / "commands" / "rh-inf-discovery.md").unlink()
    result = run(["check"])
    assert result.exit_code == 1
    assert "missing" in result.output


def test_check_detects_modified_file(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="2\n")
    dest = tmp_project / ".claude" / "commands" / "rh-inf-discovery.md"
    dest.write_text(dest.read_text() + "\n# Tampered\n")
    result = run(["check"])
    assert result.exit_code == 1
    assert "modified" in result.output


def test_check_fails_without_lockfile(tmp_project):
    result = CliRunner().invoke(skills, ["check"])
    assert result.exit_code != 0
    assert "init" in result.output.lower()


# ── update ─────────────────────────────────────────────────────────────────────

def test_update_restores_missing_file(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="2\n")
    dest = tmp_project / ".claude" / "commands" / "rh-inf-discovery.md"
    dest.unlink()
    run(["update", "--from", str(tmp_skills)])
    assert dest.exists()


def test_update_refreshes_lockfile_after_tamper(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="2\n")
    dest = tmp_project / ".claude" / "commands" / "rh-inf-discovery.md"
    dest.write_text("tampered")
    run(["update", "--from", str(tmp_skills)])
    result = run(["check"])
    assert result.exit_code == 0


def test_update_fails_without_lockfile(tmp_project):
    result = CliRunner().invoke(skills, ["update"])
    assert result.exit_code != 0
    assert "init" in result.output.lower()


# ── rendering ──────────────────────────────────────────────────────────────────

def test_cursor_render_has_mdc_frontmatter(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="3\n")
    content = (tmp_project / ".cursor" / "rules" / "rh-inf-discovery.mdc").read_text()
    assert content.startswith("---\ndescription:")


def test_claude_render_strips_frontmatter(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="2\n")
    content = (tmp_project / ".claude" / "commands" / "rh-inf-discovery.md").read_text()
    assert "name: rh-inf-discovery" not in content
    assert "Skill body." in content


def test_gemini_render_has_content(tmp_skills, tmp_project):
    run(["init", "--from", str(tmp_skills)], input_text="4\n")
    content = (tmp_project / ".gemini" / "rh-inf-discovery.md").read_text()
    assert "Skill body." in content
