from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build-skills.sh"


def run_build(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_foundational_fails_for_missing_profile(build_env):
    result = run_build("--platform", "missing", env=build_env)

    assert result.returncode != 0
    assert "No profile found for platform 'missing'" in result.stderr


def test_foundational_fails_for_placeholder_skills_before_writing_output(build_repo, build_env):
    skill_file = build_repo / "skills" / ".curated" / "rh-inf-sample" / "SKILL.md"
    skill_file.write_text(skill_file.read_text().replace("rh-inf-sample", "<skill-name>", 1))

    result = run_build("--platform", "copilot", env=build_env)

    assert result.returncode != 0
    assert "contains unresolved placeholder text" in result.stderr
    assert not (build_repo / "dist" / "copilot").exists()


def test_foundational_warns_on_unknown_profile_fields(build_repo, build_env):
    profile = build_repo / "skills" / "_profiles" / "custom.yaml"
    profile.write_text(
        """
platform: custom
bundled: false
bundle_mode: per_skill
output_path_pattern: dist/custom/{skill_name}
frontmatter_policy: keep
unsupported_knob: true
validation_rules:
  - skill_entry_exists
installability_checks:
  - file_nonempty
""".strip()
        + "\n"
    )

    result = run_build("--platform", "custom", env=build_env)

    assert result.returncode == 0
    assert "ignores unsupported field 'unsupported_knob'" in result.stderr
    assert (build_repo / "dist" / "custom" / "rh-inf-sample" / "SKILL.md").exists()


def test_foundational_fails_for_conflicting_outputs(build_repo, build_env):
    profile = build_repo / "skills" / "_profiles" / "copilot-shadow.yaml"
    profile.write_text(
        """
platform: copilot-shadow
bundled: true
bundle_mode: per_skill
output_path_pattern: dist/copilot/{skill_name}
frontmatter_policy: keep
validation_rules:
  - skill_entry_exists
installability_checks:
  - file_nonempty
""".strip()
        + "\n"
    )

    result = run_build("--all", env=build_env)

    assert result.returncode != 0
    assert "Conflicting output destination detected" in result.stderr


def test_foundational_fails_for_missing_support_files(build_repo, build_env):
    profile = build_repo / "skills" / "_profiles" / "custom.yaml"
    profile.write_text(
        """
platform: custom
bundled: false
bundle_mode: per_skill
output_path_pattern: dist/custom/{skill_name}
frontmatter_policy: keep
preamble:
  file: skills/_profiles/support/does-not-exist.md
validation_rules:
  - skill_entry_exists
installability_checks:
  - file_nonempty
""".strip()
        + "\n"
    )

    result = run_build("--platform", "custom", env=build_env)

    assert result.returncode != 0
    assert "references missing preamble file" in result.stderr


def test_builds_single_platform_bundle_with_companions(build_repo, build_env):
    result = run_build("--platform", "copilot", env=build_env)

    assert result.returncode == 0, result.stderr
    skill_root = build_repo / "dist" / "copilot" / "rh-inf-sample"
    assert (skill_root / "SKILL.md").exists()
    assert (skill_root / "reference.md").exists()
    assert (skill_root / "examples" / "plan.md").exists()
    assert (skill_root / "examples" / "output.md").exists()
    assert (skill_root / "SKILL.md").read_text().startswith("---\n")


def test_builds_all_bundled_platforms_deterministically(build_repo, build_env):
    first = run_build("--all", env=build_env)
    assert first.returncode == 0, first.stderr

    copilot_skill = build_repo / "dist" / "copilot" / "rh-inf-sample" / "SKILL.md"
    claude_skill = build_repo / "dist" / "claude" / "rh-inf-sample" / "SKILL.md"
    gemini_skill = build_repo / "dist" / "gemini" / "rh-inf-sample" / "SKILL.md"

    baseline = {
        "copilot": copilot_skill.read_text(),
        "claude": claude_skill.read_text(),
        "gemini": gemini_skill.read_text(),
    }

    second = run_build("--all", env=build_env)
    assert second.returncode == 0, second.stderr

    assert copilot_skill.read_text() == baseline["copilot"]
    assert claude_skill.read_text() == baseline["claude"]
    assert gemini_skill.read_text() == baseline["gemini"]
    assert not claude_skill.read_text().startswith("---\n")
    assert "platform_compatibility:" in gemini_skill.read_text()
    assert "## Pre-Execution Checks" not in gemini_skill.read_text()


def test_supports_new_profiles_without_script_changes(build_repo, build_env):
    profile = build_repo / "skills" / "_profiles" / "custom.yaml"
    profile.write_text(
        """
platform: custom
bundled: false
bundle_mode: per_skill
output_path_pattern: dist/custom/{skill_name}
frontmatter_policy: transform
preamble:
  inline: |
    <!-- Custom bundle -->
field_map:
  compatibility: target_compatibility
validation_rules:
  - skill_entry_exists
  - frontmatter_present
installability_checks:
  - file_nonempty
""".strip()
        + "\n"
    )

    result = run_build("--platform", "custom", env=build_env)

    assert result.returncode == 0, result.stderr
    rendered = (build_repo / "dist" / "custom" / "rh-inf-sample" / "SKILL.md").read_text()
    assert "<!-- Custom bundle -->" in rendered
    assert "target_compatibility:" in rendered


def test_dry_run_writes_no_files(build_repo, build_env):
    result = run_build("--platform", "copilot", "--dry-run", env=build_env)

    assert result.returncode == 0, result.stderr
    assert "No files were written because --dry-run was enabled." in result.stdout
    assert not (build_repo / "dist" / "copilot").exists()


def test_validate_reports_platform_rule_results(build_repo, build_env):
    result = run_build("--platform", "gemini", "--validate", env=build_env)

    assert result.returncode == 0, result.stderr
    assert "PASS [validation] gemini/rh-inf-sample rule=skill_entry_exists" in result.stdout
    assert "PASS [installability] gemini/rh-inf-sample rule=file_nonempty" in result.stdout


def test_validate_fails_when_profile_expectations_do_not_match_output(build_repo, build_env):
    profile = build_repo / "skills" / "_profiles" / "invalid.yaml"
    profile.write_text(
        """
platform: invalid
bundled: false
bundle_mode: per_skill
output_path_pattern: dist/invalid/{skill_name}
frontmatter_policy: keep
validation_rules:
  - frontmatter_absent
installability_checks:
  - file_nonempty
""".strip()
        + "\n"
    )

    result = run_build("--platform", "invalid", "--validate", env=build_env)

    assert result.returncode != 0
    assert "FAIL [validation] invalid/rh-inf-sample rule=frontmatter_absent" in result.stderr


def test_builds_optional_aggregate_bundle(build_repo, build_env):
    result = run_build("--platform", "agents-md", "--validate", env=build_env)

    assert result.returncode == 0, result.stderr
    aggregate = build_repo / "dist" / "agents-md" / "AGENTS.md"
    assert aggregate.exists()
    text = aggregate.read_text()
    assert "# RH Informatics Skills" in text
    assert "## rh-inf-sample" in text
