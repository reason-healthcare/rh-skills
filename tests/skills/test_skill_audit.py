"""Audit tests for SKILL.md files — structural completeness and framework compliance.

Checks that every implemented curated skill:
  - has required companion files (reference.md, examples/)
  - follows the plan→implement→verify contract defined in 002 spec FR-017–FR-022
  - declares events it appends (FR-021)
  - references hi CLI commands (not direct file I/O) for deterministic operations
  - declares compatibility with hi-skills-framework

These tests run vacuously (skip) when no curated skills are implemented yet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .conftest import curated_skill_dirs, parse_frontmatter, skill_body

# Patterns confirming that implement mode delegates to hi CLI (FR-017)
HI_CLI_DELEGATION_PATTERNS = [
    re.compile(r"`hi\s+(ingest|promote|validate|init|tasks|test|list|status)"),
    re.compile(r"hi\s+(ingest|promote|validate|init|tasks)\s+", re.IGNORECASE),
]

# Patterns confirming a plan-existence pre-check (FR-019)
PLAN_EXISTS_CHECK_PATTERNS = [
    re.compile(r"plan.{0,60}(does not exist|not found|missing)", re.IGNORECASE),
    re.compile(r"(fail|error|exit).{0,60}(no plan|plan.*not exist|plan.*missing)", re.IGNORECASE),
    re.compile(r"## Pre-Execution Checks", re.IGNORECASE),
]

# Patterns confirming events are mentioned (FR-021)
EVENT_MENTION_PATTERNS = [
    re.compile(r"event", re.IGNORECASE),
    re.compile(r"tracking\.yaml", re.IGNORECASE),
    re.compile(r"appended", re.IGNORECASE),
]

# Patterns confirming verify is non-destructive (FR-022)
VERIFY_NONDESTRUCT_PATTERNS = [
    re.compile(r"(non.destructive|read.only|must not.{0,40}modif|must not.{0,40}creat|must not.{0,40}delet)", re.IGNORECASE),
    re.compile(r"(never.{0,40}modif|safe to re.?run|does not.{0,40}write)", re.IGNORECASE),
]

# Skills that intentionally have no verify mode
NO_VERIFY_SKILLS = {"hi-discovery", "hi-status"}


# ---------------------------------------------------------------------------
# Companion file completeness
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not curated_skill_dirs(),
    reason="No implemented curated skills yet",
)
class TestCompanionFiles:
    """Every implemented skill should ship with its Level 3 companion files."""

    def test_reference_md_exists(self, curated_skill: Path):
        ref = curated_skill / "reference.md"
        assert ref.exists(), (
            f"{curated_skill.name}: missing reference.md — "
            "move schemas, field definitions, and validation rules here (Level 3 disclosure)"
        )

    def test_reference_md_non_empty(self, curated_skill: Path):
        ref = curated_skill / "reference.md"
        if not ref.exists():
            pytest.skip("reference.md missing (caught by test_reference_md_exists)")
        assert ref.stat().st_size > 100, f"{curated_skill.name}: reference.md appears empty"

    def test_examples_dir_exists(self, curated_skill: Path):
        assert (curated_skill / "examples").is_dir(), (
            f"{curated_skill.name}: missing examples/ directory — "
            "add worked examples for plan and output artifacts"
        )

    def test_examples_plan_md_exists(self, curated_skill: Path):
        has_plan_md = (curated_skill / "examples" / "plan.md").exists()
        has_plan_yaml = (curated_skill / "examples" / "plan.yaml").exists()
        assert has_plan_md or has_plan_yaml, (
            f"{curated_skill.name}: missing examples/plan.md or examples/plan.yaml — "
            "add a worked example plan artifact"
        )

    def test_examples_output_md_exists(self, curated_skill: Path):
        assert (curated_skill / "examples" / "output.md").exists(), (
            f"{curated_skill.name}: missing examples/output.md — "
            "add a worked example output artifact"
        )


# ---------------------------------------------------------------------------
# Framework contract compliance (FR-017 through FR-022)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not curated_skill_dirs(),
    reason="No implemented curated skills yet",
)
class TestFrameworkContracts:
    """Validate that every skill honours the framework contracts from spec FR-017–FR-022."""

    def test_compatibility_declares_hi_skills_framework(self, curated_skill: Path):
        """FR-016: skills must declare compatibility with hi-skills-framework."""
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        compat = fm.get("compatibility", "")
        assert "hi-skills-framework" in compat, (
            f"{curated_skill.name}: 'compatibility' must reference 'hi-skills-framework', got: '{compat}'"
        )

    def test_implement_mode_references_hi_cli(self, curated_skill: Path):
        """FR-017: implement mode must delegate to hi CLI, never perform file I/O directly."""
        body = skill_body(curated_skill / "SKILL.md")
        if "## Mode: `implement`" not in body and "### `implement`" not in body:
            pytest.skip(f"{curated_skill.name} has no implement mode")
        has_delegation = any(p.search(body) for p in HI_CLI_DELEGATION_PATTERNS)
        assert has_delegation, (
            f"{curated_skill.name}: implement mode must reference hi CLI commands "
            "(e.g. `hi promote derive`, `hi validate`) — never perform file I/O directly (FR-017)"
        )

    def test_plan_mode_writes_to_process_plans(self, curated_skill: Path):
        """FR-018: plan mode must write to topics/<name>/process/plans/<skill>-plan.md."""
        body = skill_body(curated_skill / "SKILL.md")
        if "## Mode: `plan`" not in body and "### `plan`" not in body:
            pytest.skip(f"{curated_skill.name} has no plan mode")
        assert "process/plans/" in body, (
            f"{curated_skill.name}: plan mode must write to topics/<name>/process/plans/ (FR-018)"
        )
        skill_name = curated_skill.name
        assert f"{skill_name}-plan.md" in body, (
            f"{curated_skill.name}: plan mode must name its artifact '{skill_name}-plan.md' (FR-018)"
        )

    def test_implement_mode_checks_for_plan(self, curated_skill: Path):
        """FR-019: implement must fail if plan does not exist."""
        body = skill_body(curated_skill / "SKILL.md")
        if "## Mode: `implement`" not in body and "### `implement`" not in body:
            pytest.skip(f"{curated_skill.name} has no implement mode")
        has_check = any(p.search(body) for p in PLAN_EXISTS_CHECK_PATTERNS)
        assert has_check, (
            f"{curated_skill.name}: implement mode must check that plan exists and fail if not (FR-019)"
        )

    def test_skill_mentions_events(self, curated_skill: Path):
        """FR-021: skills must document the events they append to tracking.yaml."""
        body = skill_body(curated_skill / "SKILL.md")
        has_events = any(p.search(body) for p in EVENT_MENTION_PATTERNS)
        assert has_events, (
            f"{curated_skill.name}: SKILL.md must mention tracking.yaml events (FR-021). "
            "Document which events each mode appends."
        )

    def test_verify_mode_is_non_destructive(self, curated_skill: Path):
        """FR-022: verify mode must be non-destructive."""
        if curated_skill.name in NO_VERIFY_SKILLS:
            pytest.skip(f"{curated_skill.name} intentionally has no verify mode")
        body = skill_body(curated_skill / "SKILL.md")
        if "## Mode: `verify`" not in body and "### `verify`" not in body:
            pytest.skip(f"{curated_skill.name} has no verify mode")
        has_nondestruct = any(p.search(body) for p in VERIFY_NONDESTRUCT_PATTERNS)
        assert has_nondestruct, (
            f"{curated_skill.name}: verify mode must explicitly state it is non-destructive "
            "(e.g. 'MUST NOT create, modify, or delete') (FR-022)"
        )

    def test_guiding_principle_states_cli_delegation(self, curated_skill: Path):
        """FR-017 guiding principle: deterministic work in hi CLI, reasoning in SKILL.md."""
        content = (curated_skill / "SKILL.md").read_text()
        has_principle = (
            "deterministic" in content.lower() and "hi" in content.lower()
            or "CLI" in content and "reasoning" in content.lower()
        )
        assert has_principle, (
            f"{curated_skill.name}: SKILL.md must state the guiding principle that "
            "all deterministic work goes through hi CLI commands (FR-017)"
        )


# ---------------------------------------------------------------------------
# Audit summary (always run — gives a quick library health overview)
# ---------------------------------------------------------------------------

class TestSkillLibraryHealth:
    """Sanity checks that always run regardless of whether skills are implemented."""

    def test_curated_dir_exists(self):
        from .conftest import CURATED_DIR
        assert CURATED_DIR.exists(), "skills/.curated/ directory must exist"

    def test_template_dir_exists(self):
        from .conftest import TEMPLATE_DIR
        assert TEMPLATE_DIR.exists(), "skills/_template/ directory must exist"

    def test_no_skill_dir_named_template_in_curated(self):
        from .conftest import CURATED_DIR
        assert not (CURATED_DIR / "_template").exists(), (
            "skills/.curated/_template/ must not exist — template is at skills/_template/"
        )

    def test_skill_library_count_matches_expected_specs(self):
        """There should eventually be exactly 6 curated skills (003–008).
        This test warns (not fails) when fewer are implemented."""
        from .conftest import CURATED_DIR
        implemented = [
            d for d in CURATED_DIR.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ] if CURATED_DIR.exists() else []
        expected_skills = {
            "hi-discovery", "hi-ingest", "hi-extract",
            "hi-formalize", "hi-verify", "hi-status",
        }
        implemented_names = {d.name for d in implemented}
        missing = expected_skills - implemented_names
        # This is an informational test — report but don't fail
        if missing:
            pytest.skip(f"Skills not yet implemented: {sorted(missing)} ({len(implemented)}/6 done)")
