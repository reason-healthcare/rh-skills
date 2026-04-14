"""SKILL.md schema validation tests.

Validates that every implemented curated skill and the canonical template
conform to the RH skills framework SKILL.md schema:

  - YAML frontmatter present with required fields
  - name is kebab-case, ≤64 chars, matches directory name
  - description is non-empty and references supported modes
  - no unexpected frontmatter keys
  - required section headers present in body
  - no unfilled template placeholder tokens (implemented skills only)
  - companion files declared in context_files actually exist
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .conftest import (
    ALL_ALLOWED_FRONTMATTER_KEYS,
    PLACEHOLDER_PATTERNS,
    REQUIRED_FRONTMATTER_KEYS,
    TEMPLATE_DIR,
    curated_skill_dirs,
    parse_frontmatter,
    skill_body,
)

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LEN = 64

# Sections that every HI SKILL.md body must contain.
REQUIRED_SECTIONS = [
    "## User Input",
    "## Pre-Execution Checks",
    "## Guiding Principles",
]

# Mode sections: at least one of these must be present.
MODE_SECTIONS = [
    "## Mode: `plan`",
    "## Mode: `implement`",
    "## Mode: `verify`",
    "### `plan`",
    "### `implement`",
    "### `verify`",
]


# ---------------------------------------------------------------------------
# Template tests (always run — template must always be valid)
# ---------------------------------------------------------------------------

class TestTemplate:
    """The canonical _template/ must always be well-formed."""

    def test_template_dir_exists(self):
        assert TEMPLATE_DIR.exists(), "skills/_template/ directory must exist"

    def test_template_skill_md_exists(self):
        assert (TEMPLATE_DIR / "SKILL.md").exists(), "skills/_template/SKILL.md must exist"

    def test_template_reference_md_exists(self):
        assert (TEMPLATE_DIR / "reference.md").exists(), "skills/_template/reference.md must exist"

    def test_template_examples_dir_exists(self):
        assert (TEMPLATE_DIR / "examples").is_dir(), "skills/_template/examples/ must exist"

    def test_template_examples_plan_exists(self):
        assert (TEMPLATE_DIR / "examples" / "plan.md").exists(), "skills/_template/examples/plan.md must exist"

    def test_template_examples_output_exists(self):
        assert (TEMPLATE_DIR / "examples" / "output.md").exists(), "skills/_template/examples/output.md must exist"

    def test_template_frontmatter_required_keys(self):
        fm = parse_frontmatter(TEMPLATE_DIR / "SKILL.md")
        missing = REQUIRED_FRONTMATTER_KEYS - set(fm)
        assert not missing, f"Template SKILL.md missing required frontmatter keys: {sorted(missing)}"

    def test_template_frontmatter_no_unknown_keys(self):
        fm = parse_frontmatter(TEMPLATE_DIR / "SKILL.md")
        # Template may have commented-out or structural keys; check only top-level parsed keys.
        unknown = set(fm) - ALL_ALLOWED_FRONTMATTER_KEYS
        assert not unknown, f"Template SKILL.md has unknown frontmatter keys: {sorted(unknown)}"

    def test_template_has_user_input_section(self):
        body = skill_body(TEMPLATE_DIR / "SKILL.md")
        assert "## User Input" in body, "Template must have '## User Input' section"

    def test_template_has_arguments_placeholder(self):
        content = (TEMPLATE_DIR / "SKILL.md").read_text()
        assert "$ARGUMENTS" in content, "Template must contain $ARGUMENTS placeholder"

    def test_template_has_pre_execution_checks(self):
        body = skill_body(TEMPLATE_DIR / "SKILL.md")
        assert "## Pre-Execution Checks" in body

    def test_template_has_guiding_principles(self):
        body = skill_body(TEMPLATE_DIR / "SKILL.md")
        assert "## Guiding Principles" in body

    def test_template_has_at_least_one_mode_section(self):
        body = skill_body(TEMPLATE_DIR / "SKILL.md")
        has_mode = any(section in body for section in MODE_SECTIONS)
        assert has_mode, "Template must document at least one mode section"

    def test_template_reference_md_has_plan_schema_section(self):
        text = (TEMPLATE_DIR / "reference.md").read_text()
        assert "Plan Schema" in text, "reference.md must have a 'Plan Schema' section"

    def test_template_reference_md_has_output_artifact_section(self):
        text = (TEMPLATE_DIR / "reference.md").read_text()
        assert "Output Artifact" in text, "reference.md must have an 'Output Artifact' section"

    def test_template_reference_md_has_glossary(self):
        text = (TEMPLATE_DIR / "reference.md").read_text()
        assert "Glossary" in text, "reference.md must have a Glossary section"


# ---------------------------------------------------------------------------
# Curated skill tests (parametrized — skip gracefully when no skills exist)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not curated_skill_dirs(),
    reason="No implemented curated skills yet (dirs are empty)",
)
class TestCuratedSkillSchema:
    """Schema requirements for every implemented curated skill."""

    def test_skill_md_exists(self, curated_skill: Path):
        assert (curated_skill / "SKILL.md").exists()

    def test_frontmatter_parseable(self, curated_skill: Path):
        # parse_frontmatter raises ValueError if malformed
        parse_frontmatter(curated_skill / "SKILL.md")

    def test_required_frontmatter_keys_present(self, curated_skill: Path):
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        missing = REQUIRED_FRONTMATTER_KEYS - set(fm)
        assert not missing, f"{curated_skill.name}: missing frontmatter keys: {sorted(missing)}"

    def test_no_unknown_frontmatter_keys(self, curated_skill: Path):
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        unknown = set(fm) - ALL_ALLOWED_FRONTMATTER_KEYS
        assert not unknown, f"{curated_skill.name}: unknown frontmatter keys: {sorted(unknown)}"

    def test_name_is_kebab_case(self, curated_skill: Path):
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        name = fm.get("name", "")
        assert KEBAB_RE.match(name), f"{curated_skill.name}: 'name' must be kebab-case, got '{name}'"

    def test_name_length(self, curated_skill: Path):
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        name = fm.get("name", "")
        assert len(name) <= MAX_NAME_LEN, f"{curated_skill.name}: name too long ({len(name)} chars)"

    def test_name_matches_directory(self, curated_skill: Path):
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        assert fm.get("name") == curated_skill.name, (
            f"SKILL.md 'name' ('{fm.get('name')}') must match directory name ('{curated_skill.name}')"
        )

    def test_description_non_empty(self, curated_skill: Path):
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        desc = fm.get("description", "")
        assert desc, f"{curated_skill.name}: 'description' must be non-empty"

    def test_no_unfilled_placeholders(self, curated_skill: Path):
        content = (curated_skill / "SKILL.md").read_text()
        hits = [p.pattern for p in PLACEHOLDER_PATTERNS if p.search(content)]
        assert not hits, (
            f"{curated_skill.name}: SKILL.md still contains template placeholders: {hits}"
        )

    def test_required_sections_present(self, curated_skill: Path):
        body = skill_body(curated_skill / "SKILL.md")
        missing = [s for s in REQUIRED_SECTIONS if s not in body]
        assert not missing, f"{curated_skill.name}: missing required sections: {missing}"

    def test_has_at_least_one_mode_section(self, curated_skill: Path):
        body = skill_body(curated_skill / "SKILL.md")
        has_mode = any(s in body for s in MODE_SECTIONS)
        assert has_mode, f"{curated_skill.name}: must document at least one mode section"

    def test_arguments_placeholder_present(self, curated_skill: Path):
        content = (curated_skill / "SKILL.md").read_text()
        assert "$ARGUMENTS" in content, f"{curated_skill.name}: must contain $ARGUMENTS"

    def test_companion_files_declared_in_context_files_exist(self, curated_skill: Path):
        """Any file listed in context_files frontmatter must exist in the skill dir."""
        content = (curated_skill / "SKILL.md").read_text()
        # Extract context_files block — simple heuristic for the list items
        context_block_match = re.search(r"context_files:\s*\n((?:\s+-\s+\S+\n)+)", content)
        if not context_block_match:
            return  # no context_files declared — OK
        items = re.findall(r"-\s+(\S+)", context_block_match.group(1))
        missing = [f for f in items if not (curated_skill / f).exists()]
        assert not missing, (
            f"{curated_skill.name}: context_files references missing files: {missing}"
        )


class TestRhInfVerifySkillSchema:
    """Focused schema assertions for the standalone verify skill."""

    def test_verify_skill_declares_expected_companion_files(self):
        skill = Path("skills/.curated/rh-inf-verify/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-verify skill not implemented")
        fm = parse_frontmatter(skill)
        context_files = skill.read_text()
        assert fm["name"] == "rh-inf-verify"
        assert "reference.md" in context_files
        assert "examples/plan.md" in context_files
        assert "examples/output.md" in context_files

    def test_verify_output_example_uses_required_report_sections(self):
        example = Path("skills/.curated/rh-inf-verify/examples/output.md")
        if not example.exists():
            pytest.skip("rh-inf-verify output example not implemented")
        content = example.read_text()
        assert "Topic Summary" in content
        assert "Stage Results" in content
        assert "Overall Readiness" in content
        assert "Recommended Next Action" in content

    def test_verify_reference_documents_canonical_status_mapping(self):
        ref = Path("skills/.curated/rh-inf-verify/reference.md")
        if not ref.exists():
            pytest.skip("rh-inf-verify reference not implemented")
        content = ref.read_text()
        for term in (
            "applicable",
            "not-yet-ready",
            "not-applicable",
            "unavailable",
            "pass",
            "fail",
            "warning-only",
            "invocation-error",
        ):
            assert term in content
