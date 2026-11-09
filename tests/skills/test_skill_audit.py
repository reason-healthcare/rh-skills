"""Audit tests for SKILL.md files — structural completeness and framework compliance.

Checks that every implemented curated skill:
  - has required companion files (reference.md, examples/)
  - follows the plan→implement→verify contract defined in 002 spec FR-017–FR-022
  - declares events it appends (FR-021)
  - references rh-skills CLI commands (not direct file I/O) for deterministic operations
  - declares compatibility with rh-skills

These tests run vacuously (skip) when no curated skills are implemented yet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .conftest import curated_skill_dirs, parse_frontmatter, skill_body

# Patterns confirming that implement mode delegates to rh-skills CLI (FR-017)
RH_SKILLS_CLI_DELEGATION_PATTERNS = [
    re.compile(r"`rh-skills\s+(ingest|promote|validate|init|tasks|test|list|status)"),
    re.compile(r"rh-skills\s+(ingest|promote|validate|init|tasks)\s+", re.IGNORECASE),
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
NO_VERIFY_SKILLS = {"rh-inf-discovery", "rh-inf-status"}

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
        # Also accept skills with examples in named subdirectories (e.g. author-example/)
        examples_dir = curated_skill / "examples"
        has_subdir_plan = any(
            (d / "plan.md").exists() or (d / "plan.yaml").exists()
            for d in examples_dir.iterdir()
            if d.is_dir()
        ) if examples_dir.exists() else False
        assert has_plan_md or has_plan_yaml or has_subdir_plan, (
            f"{curated_skill.name}: missing examples/plan.md or examples/plan.yaml — "
            "add a worked example plan artifact"
        )

    def test_examples_output_md_exists(self, curated_skill: Path):
        has_output = (curated_skill / "examples" / "output.md").exists()
        # Also accept skills with examples in named subdirectories (e.g. author-example/)
        examples_dir = curated_skill / "examples"
        has_subdir_output = any(
            (d / "output.md").exists()
            for d in examples_dir.iterdir()
            if d.is_dir()
        ) if examples_dir.exists() else False
        assert has_output or has_subdir_output, (
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

    def test_compatibility_declares_rh_skills(self, curated_skill: Path):
        """FR-016: skills must declare compatibility with rh-skills."""
        fm = parse_frontmatter(curated_skill / "SKILL.md")
        compat = fm.get("compatibility", "")
        assert "rh-skills" in compat, (
            f"{curated_skill.name}: 'compatibility' must reference 'rh-skills', got: '{compat}'"
        )

    def test_implement_mode_references_rh_skills_cli(self, curated_skill: Path):
        """FR-017: implement mode must delegate to rh-skills CLI, never perform file I/O directly."""
        body = skill_body(curated_skill / "SKILL.md")
        if "## Mode: `implement`" not in body and "### `implement`" not in body:
            pytest.skip(f"{curated_skill.name} has no implement mode")
        has_delegation = any(p.search(body) for p in RH_SKILLS_CLI_DELEGATION_PATTERNS)
        assert has_delegation, (
            f"{curated_skill.name}: implement mode must reference rh-skills CLI commands "
            "(e.g. `rh-skills promote derive`, `rh-skills validate`) — never perform file I/O directly (FR-017)"
        )

    def test_plan_mode_writes_to_process_plans(self, curated_skill: Path):
        """FR-018: plan mode must write to topics/<name>/process/plans/<skill>-plan.{yaml,md}."""
        body = skill_body(curated_skill / "SKILL.md")
        if "## Mode: `plan`" not in body and "### `plan`" not in body:
            pytest.skip(f"{curated_skill.name} has no plan mode")
        if curated_skill.name == "rh-inf-ingest":
            assert "read-only" in body.lower(), (
                f"{curated_skill.name}: plan mode is intentionally transient and must state that it is read-only"
            )
            assert "discovery-plan.yaml" in body, (
                f"{curated_skill.name}: plan mode must reference discovery-plan.yaml as the durable upstream planning artifact"
            )
            return
        if curated_skill.name == "rh-inf-discovery":
            assert "topics/<topic>/process/plans/" in body, (
                f"{curated_skill.name}: discovery plan mode must write to topics/<topic>/process/plans/ (FR-018)"
            )
            assert "discovery-plan.yaml" in body and "discovery-readout.md" in body, (
                f"{curated_skill.name}: discovery plan mode must document discovery-plan.yaml and discovery-readout.md (FR-018)"
            )
            return
        assert "process/plans/" in body, (
            f"{curated_skill.name}: plan mode must write to topics/<name>/process/plans/ (FR-018)"
        )
        skill_name = curated_skill.name
        assert f"{skill_name}-plan.yaml" in body or f"{skill_name}-plan.md" in body, (
            f"{curated_skill.name}: plan mode must name its artifact '{skill_name}-plan.yaml' or '{skill_name}-plan.md' (FR-018)"
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
        """FR-017 guiding principle: deterministic work in rh-skills CLI, reasoning in SKILL.md."""
        content = (curated_skill / "SKILL.md").read_text()
        has_principle = (
            "deterministic" in content.lower() and "rh-skills" in content.lower()
            or "CLI" in content and "reasoning" in content.lower()
        )
        assert has_principle, (
            f"{curated_skill.name}: SKILL.md must state the guiding principle that "
            "all deterministic work goes through rh-skills CLI commands (FR-017)"
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
            "rh-inf-discovery", "rh-inf-ingest", "rh-inf-extract",
            "rh-inf-formalize", "rh-inf-verify", "rh-inf-status",
        }
        implemented_names = {d.name for d in implemented}
        missing = expected_skills - implemented_names
        # This is an informational test — report but don't fail
        if missing:
            pytest.skip(f"Skills not yet implemented: {sorted(missing)} ({len(implemented)}/6 done)")


class TestRhInfExtractSkillContract:
    """Focused contract checks for the extract skill's reviewer-packet flow."""

    def test_extract_skill_plan_mode_mentions_canonical_packet(self):
        skill = Path("skills/.curated/rh-inf-extract/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-extract skill not implemented")
        body = skill_body(skill)
        assert "process/plans/extract-plan.yaml" in body
        assert "pending-review" in body

    def test_extract_skill_implement_mode_mentions_approval_gate(self):
        skill = Path("skills/.curated/rh-inf-extract/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-extract skill not implemented")
        body = skill_body(skill)
        assert "approved" in body and "reviewer_decision" in body
        assert "rh-skills validate" in body and "<topic>" in body

    def test_extract_skill_requires_current_run_reasonhub_evidence(self):
        skill = Path("skills/.curated/rh-inf-extract/SKILL.md")
        reference = Path("skills/.curated/rh-inf-extract/reference.md")
        body = skill_body(skill)
        details = reference.read_text()

        assert "does not prove that this run called ReasonHub" in body
        assert "process/reviews/terminology-evidence.json" in body
        for field in (
            "tool",
            "query",
            "system",
            "version",
            "request",
            "response",
            "selected code",
            "display",
            "selection rationale",
        ):
            assert field in body
        assert "exact request and response returned in the run" in details
        assert "not current-run MCP execution evidence" in details

    def test_extract_skill_separates_fixture_codes_and_regimen_candidates(self):
        skill = Path("skills/.curated/rh-inf-extract/SKILL.md")
        reference = Path("skills/.curated/rh-inf-extract/reference.md")
        combined = skill_body(skill) + "\n" + reference.read_text()

        assert "test-only" in combined
        assert "never describe them as standardized or terminology-service-verified" in combined
        assert "order-set candidate analysis" in combined
        assert "RxNorm-first MCP path" in combined
        assert "do not invent components or order details" in combined


class TestRhInfFormalizeSkillContract:
    """Focused contract checks for the formalize skill's reviewer-gated L3 flow."""

    def test_formalize_skill_plan_mode_mentions_canonical_packet(self):
        skill = Path("skills/.curated/rh-inf-formalize/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-formalize skill not implemented")
        body = skill_body(skill)
        assert "process/plans/formalize-plan.yaml" in body
        assert "process/plans/formalize-plan-readout.md" in body
        assert "rh-skills promote formalize-plan" in body

    def test_formalize_skill_implement_mode_mentions_single_target_combine(self):
        skill = Path("skills/.curated/rh-inf-formalize/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-formalize skill not implemented")
        body = skill_body(skill)
        assert "implementation_target" in body
        assert "rh-skills formalize" in body
        assert "rh-skills validate" in body

    def test_formalize_skill_bounds_draft_regimen_order_sets(self):
        skill = Path("skills/.curated/rh-inf-formalize/SKILL.md")
        reference = Path("skills/.curated/rh-inf-formalize/reference.md")
        combined = skill_body(skill) + "\n" + reference.read_text()

        assert "order-set candidate analysis" in combined
        assert "using RxNorm first" in combined
        assert "experimental: true" in combined
        assert "intent: proposal" in combined
        for unsupported_detail in (
            "dose",
            "route",
            "frequency",
            "cycle",
            "sequence",
            "timing",
        ):
            assert unsupported_detail in combined
        assert "broader guidance-applicability action" in combined
        assert "Do not gate" in combined

    def test_formalize_skill_requires_cql_library_identity_conformance(self):
        body = skill_body(Path("skills/.curated/rh-inf-formalize/SKILL.md"))
        assert "conformance.html#conformance-requirement-4-2" in body
        for requirement in (
            "Library.url",
            "Library.subject",
            "IG.packageId",
            "IG.canonicalBase",
            "cql-namespaceUri",
            "underscores",
            "64 characters",
        ):
            assert requirement in body


class TestRhInfVerifySkillContract:
    """Focused contract checks for the unified verify skill."""

    def test_verify_skill_mentions_stage_verify_subagents(self):
        skill = Path("skills/.curated/rh-inf-verify/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-verify skill not implemented")
        body = skill_body(skill)
        assert "subagent" in body.lower()
        assert "rh-inf-ingest verify <topic>" in body
        assert "rh-inf-extract verify <topic>" in body
        assert "rh-inf-formalize verify <topic>" in body

    def test_verify_skill_mentions_consolidated_report_sections(self):
        ref = Path("skills/.curated/rh-inf-verify/reference.md")
        if not ref.exists():
            pytest.skip("rh-inf-verify reference not implemented")
        content = ref.read_text()
        assert "Topic Summary" in content
        assert "Stage Results" in content
        assert "Overall Readiness" in content
        assert "Recommended Next Action" in content

    def test_verify_skill_preserves_applicability_and_normalized_status(self):
        ref = Path("skills/.curated/rh-inf-verify/reference.md")
        if not ref.exists():
            pytest.skip("rh-inf-verify reference not implemented")
        content = ref.read_text()
        assert "applicability" in content
        assert "not-yet-ready" in content
        assert "warning-only" in content
        assert "invocation-error" in content


class TestRhInfStatusSkillContract:
    """Focused contract checks for the status skill's deterministic UX."""

    def test_status_skill_uses_canonical_status_cli(self):
        skill = Path("skills/.curated/rh-inf-status/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-status skill not implemented")
        body = skill_body(skill)
        assert "rh-skills status" in body
        assert "rh-skills status check-changes <topic>" in body

    def test_status_skill_output_contract_uses_bullets_not_lettered_choices(self):
        skill = Path("skills/.curated/rh-inf-status/SKILL.md")
        if not skill.exists():
            pytest.skip("rh-inf-status skill not implemented")
        content = skill.read_text()
        assert "Next steps" in content
        assert "lettered choices" in content.lower() or "lettered menus" in content.lower()

    def test_status_skill_examples_do_not_use_lettered_options(self):
        example = Path("skills/.curated/rh-inf-status/examples/output.md")
        if not example.exists():
            pytest.skip("rh-inf-status examples not implemented")
        content = example.read_text()
        assert "Next steps" in content
        assert "A)" not in content
        assert "B)" not in content
        assert "C)" not in content


class TestRhCqlSkillContract:
    """Focused contract checks for the rh-inf-cql first-class skill."""

    SKILL_PATH = Path("skills/.curated/rh-inf-cql/SKILL.md")
    REF_PATH = Path("skills/.curated/rh-inf-cql/reference.md")
    STYLE_GUIDE_PATH = Path(
        "skills/.curated/rh-inf-cql/docs/cql-style-guide.md"
    )
    REVIEW_CHECKLIST_PATH = Path(
        "skills/.curated/rh-inf-cql/docs/review-checklist.md"
    )
    TERMINOLOGY_POLICY_PATH = Path(
        "skills/.curated/rh-inf-cql/docs/terminology-policy.md"
    )
    TERMINOLOGY_TEST_README_PATH = Path("tests/cql/terminology/README.md")
    EXAMPLES_DIR = Path("skills/.curated/rh-inf-cql/examples")
    AUTHOR_OUTPUT_PATH = EXAMPLES_DIR / "author-example" / "output.md"
    REVIEW_OUTPUT_PATH = EXAMPLES_DIR / "review-example" / "output.md"

    # ── SKILL.md — four mode headings ─────────────────────────────────────────

    def test_skill_md_has_author_mode(self):
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "## Mode: author" in body, "SKILL.md must have '## Mode: author' heading"

    def test_skill_md_has_review_mode(self):
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "## Mode: review" in body, "SKILL.md must have '## Mode: review' heading"

    def test_skill_md_has_debug_mode(self):
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "## Mode: debug" in body, "SKILL.md must have '## Mode: debug' heading"

    def test_skill_md_has_test_plan_mode(self):
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "## Mode: test-plan" in body, "SKILL.md must have '## Mode: test-plan' heading"

    # ── reference.md — four corpus layers ────────────────────────────────────

    def test_reference_md_has_layer_1_core_cql(self):
        if not self.REF_PATH.exists():
            pytest.skip("rh-inf-cql reference.md not implemented")
        content = self.REF_PATH.read_text()
        assert "Layer 1" in content, "reference.md must document Layer 1 — Core CQL Language"

    def test_reference_md_has_layer_2_fhir_facing(self):
        if not self.REF_PATH.exists():
            pytest.skip("rh-inf-cql reference.md not implemented")
        content = self.REF_PATH.read_text()
        assert "Layer 2" in content, "reference.md must document Layer 2 — FHIR-Facing CQL"

    def test_reference_md_has_layer_3_packaging(self):
        if not self.REF_PATH.exists():
            pytest.skip("rh-inf-cql reference.md not implemented")
        content = self.REF_PATH.read_text()
        assert "Layer 3" in content, "reference.md must document Layer 3 — Packaging and Lifecycle"

    def test_reference_md_has_layer_4_tooling(self):
        if not self.REF_PATH.exists():
            pytest.skip("rh-inf-cql reference.md not implemented")
        content = self.REF_PATH.read_text()
        assert "Layer 4" in content, "reference.md must document Layer 4 — Tooling and Runtime"

    # ── examples/ — both subdirs with plan.md + output.md ────────────────────

    def test_author_example_dir_exists(self):
        if not self.EXAMPLES_DIR.exists():
            pytest.skip("rh-inf-cql examples/ not implemented")
        assert (self.EXAMPLES_DIR / "author-example").is_dir(), (
            "rh-inf-cql: examples/author-example/ directory must exist"
        )

    def test_author_example_plan_md_exists(self):
        path = self.EXAMPLES_DIR / "author-example" / "plan.md"
        if not path.parent.exists():
            pytest.skip("rh-inf-cql examples/author-example/ not implemented")
        assert path.exists(), "rh-inf-cql: examples/author-example/plan.md must exist"

    def test_author_example_output_md_exists(self):
        path = self.EXAMPLES_DIR / "author-example" / "output.md"
        if not path.parent.exists():
            pytest.skip("rh-inf-cql examples/author-example/ not implemented")
        assert path.exists(), "rh-inf-cql: examples/author-example/output.md must exist"

    def test_review_example_dir_exists(self):
        if not self.EXAMPLES_DIR.exists():
            pytest.skip("rh-inf-cql examples/ not implemented")
        assert (self.EXAMPLES_DIR / "review-example").is_dir(), (
            "rh-inf-cql: examples/review-example/ directory must exist"
        )

    def test_review_example_plan_md_exists(self):
        path = self.EXAMPLES_DIR / "review-example" / "plan.md"
        if not path.parent.exists():
            pytest.skip("rh-inf-cql examples/review-example/ not implemented")
        assert path.exists(), "rh-inf-cql: examples/review-example/plan.md must exist"

    def test_review_example_output_md_exists(self):
        path = self.EXAMPLES_DIR / "review-example" / "output.md"
        if not path.parent.exists():
            pytest.skip("rh-inf-cql examples/review-example/ not implemented")
        assert path.exists(), "rh-inf-cql: examples/review-example/output.md must exist"

    def test_condition_status_examples_use_typed_terminology_comparison(self):
        """Canonical examples must preserve system and code as one typed identity."""
        for path in (self.AUTHOR_OUTPUT_PATH, self.REVIEW_OUTPUT_PATH):
            if not path.exists():
                pytest.skip(f"rh-inf-cql example not implemented: {path}")

            content = path.read_text()
            assert not re.search(r"\.system(?:\.value)?\s*=", content), (
                f"{path}: do not split coded identity into a system string predicate"
            )
            assert not re.search(r"\.code(?:\.value)?\s*=", content), (
                f"{path}: do not split coded identity into a code string predicate"
            )
            assert not re.search(
                r"clinicalStatus\s*~\s*['\"]active['\"]", content, re.IGNORECASE
            ), (
                f"{path}: do not compare clinicalStatus to a systemless string"
            )
            assert 'codesystem "Condition Clinical Status Codes":' in content
            assert (
                "'http://terminology.hl7.org/CodeSystem/condition-clinical'"
                in content
            )
            assert 'code "Active":' in content
            assert "'active' from \"Condition Clinical Status Codes\"" in content
            assert 'where S ~ "Active"' in content
            assert re.search(r"evaluation[- ]time", content)
            assert "prevalenceInterval()" in content

    # ── CLI boundary ──────────────────────────────────────────────────────────

    def test_skill_md_references_rh_cql_cli_commands(self):
        """rh-inf-cql skill must reference the rh CLI commands it wraps."""
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "rh-skills cql" in body, (
            "SKILL.md must reference `rh-skills cql` CLI commands (validate/translate/test)"
        )

    def test_skill_md_declares_fhirhelpers_agnostic_boundary(self):
        """rh-inf-cql skill must document the FHIRHelpers-agnostic boundary."""
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "FHIRHelpers" in body, (
            "SKILL.md must document the FHIRHelpers-agnostic behavior of rh-inf-cql"
        )

    def test_skill_md_requires_retrieve_based_decision_table_logic(self):
        """Decision-table authoring guidance must prefer ValueSet-backed retrieves."""
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert '[Condition: "' in body or '[Observation: "' in body, (
            "rh-inf-cql SKILL.md must show retrieve-based decision-table logic "
            "using ValueSet-backed FHIR retrieves"
        )

    def test_skill_md_rejects_parameter_only_decision_table_as_finished_output(self):
        """Decision-table scaffolds must not be presented as acceptable end-state CQL."""
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "Parameter-only decision-table libraries are scaffold artifacts" in body, (
            "rh-inf-cql SKILL.md must explicitly reject parameter-only decision-table "
            "libraries as acceptable finished authoring"
        )

    def test_skill_md_requires_cms_qmd_pattern_index_before_authoring(self):
        """CMS QMD patterns are the first-choice FHIR CQL baseline."""
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)
        assert "CMS QMD patterns first" in body, (
            "rh-inf-cql SKILL.md must make CMS QMD patterns the first-choice "
            "FHIR CQL authoring baseline"
        )
        assert (
            "https://build.fhir.org/ig/cqframework/cms-qmd/branches/main/pattern_index.html"
            in body
        ), "rh-inf-cql SKILL.md must link the CMS QMD Pattern Index"

        reference = self.REF_PATH
        if reference.exists():
            reference_body = reference.read_text()
            assert "CMS QMD Pattern Index" in reference_body, (
                "rh-inf-cql reference.md must identify the CMS QMD Pattern Index as "
                "the preferred FHIR CQL pattern source"
            )

    def test_author_mode_preserves_terminology_and_regimen_boundaries(self):
        """CQL authoring must consume reviewed terminology and eligibility evidence."""
        if not self.SKILL_PATH.exists():
            pytest.skip("rh-inf-cql skill not implemented")
        body = skill_body(self.SKILL_PATH)

        assert "process/reviews/terminology-evidence.json" in body
        assert "current-run ReasonHub evidence" in body
        assert "actual MCP call" in body
        assert "test-only" in body
        assert "terminology-service-verified" in body
        assert "Regimen applicability boundary" in body
        assert "Do not turn a broad guidance" in body
        assert "do not invent eligibility, dose, route, timing" in body

    def test_skill_enforces_cql_ig_library_identity_contract(self):
        body = skill_body(self.SKILL_PATH)
        reference = self.REF_PATH.read_text()
        combined = body + "\n" + reference

        assert "conformance.html#conformance-requirement-4-2" in combined
        for requirement in (
            "Library.name",
            "Library.version",
            "Library.url",
            "Library.subject",
            "IG.packageId",
            "IG.canonicalBase",
            "cql-namespaceUri",
            "no underscores",
            "64 characters",
            "<LibraryName>-<LibraryVersion>.cql",
        ):
            assert requirement in combined

    def test_skill_enforces_fhircommon_references_fluent_invocation(self):
        """FHIRCommon.references must use its published fluent-call syntax."""
        skill = skill_body(self.SKILL_PATH)
        style = self.STYLE_GUIDE_PATH.read_text()
        checklist = self.REVIEW_CHECKLIST_PATH.read_text()
        combined = "\n".join((skill, style, checklist))

        assert "O.encounter.references(E)" in skill
        assert "FHIRCommon.references(O.encounter, E)" in skill
        assert "(First(O.focus) as FHIR.Reference).references(C)" in style
        assert "fluent function" in checklist
        assert "namespace-style" in combined

    def test_skill_uses_namespaced_external_cql_source_and_retranslates_elm(self):
        """External package CQL is namespaced source, never trusted package ELM."""
        paths = (
            self.SKILL_PATH,
            self.REF_PATH,
            self.STYLE_GUIDE_PATH,
            self.REVIEW_CHECKLIST_PATH,
            Path("skills/.curated/rh-inf-cql/docs/runtime-assumptions.md"),
            Path("skills/.curated/rh-inf-cql/docs/authoring-guidelines.md"),
            Path(
                "skills/.curated/rh-inf-cql/context/runtime/"
                "engine-notes/README.md"
            ),
            Path(
                "skills/.curated/rh-inf-cql/context/runtime/"
                "translator-options/README.md"
            ),
            self.AUTHOR_OUTPUT_PATH,
        )
        combined = "\n".join(path.read_text() for path in paths)

        assert "fhir.cqf.common@4.0.1" in combined
        assert (
            "include fhir.cqf.common.FHIRHelpers version '4.0.1' "
            "called FHIRHelpers"
        ) in combined
        assert (
            "include fhir.cqf.common.FHIRCommon version '4.0.1' "
            "called FHIRCommon"
        ) in combined
        assert "The namespace is the package ID" in combined
        assert "package-supplied ELM" in combined
        assert "rh-skills cql translate" in combined
        assert "source CQL checksum" in combined
        assert "generated ELM checksum" in combined
        assert "do not create a local" in combined.lower()
        assert "Do not copy helper/common source into first-party" in combined

        for path in paths:
            assert not re.search(
                r"(?m)^\s*include\s+(?:FHIRHelpers|FHIRCommon)\b",
                path.read_text(),
            ), f"{path}: external includes must use their package namespace"

        assert "does not declare the fluent" in combined
        assert "references" in combined
        assert (
            "include hl7.fhir.uv.cql.FHIRCommon version '2.0.0' "
            "called FHIRCommon"
        ) in self.STYLE_GUIDE_PATH.read_text()
        dependencies = Path(
            "skills/.curated/rh-inf-cql/src/manifests/dependencies.yaml"
        ).read_text()
        assert "hl7.fhir.uv.cql" in dependencies
        assert "hl7.fhir.uv.cql.FHIRCommon|2.0.0" in dependencies
        assert "optionalPackages" in dependencies

    def test_skill_uses_valuesets_for_multicode_result_classification(self):
        """Multi-code FHIR results use Concept membership, not direct-code chains."""
        skill = skill_body(self.SKILL_PATH)
        style = self.STYLE_GUIDE_PATH.read_text()
        checklist = self.REVIEW_CHECKLIST_PATH.read_text()
        terminology = self.TERMINOLOGY_POLICY_PATH.read_text()
        test_matrix = self.TERMINOLOGY_TEST_README_PATH.read_text()
        combined = "\n".join((skill, style, checklist, terminology, test_matrix))

        assert 'FHIRHelpers.ToConcept(V) in "Clinical T1c Or Higher"' in skill
        assert style.count("version '1.0.0'") >= 2
        assert '"Clinical T Concept" in "Clinical T1c Or Higher"' in style
        assert '"Clinical T Concept" in "Clinical T Below T1c"' in style
        assert 'if "Clinical T Concept" is null then null' in style
        assert 'and not "Clinical T Is Below T1c"' in style
        assert 'and not "Clinical T Is T1c Or Higher"' in style
        assert "then true" in style
        assert "then false" in style
        assert "else null" in style
        assert "any code in that Concept" in style
        assert "not a FHIR `CodeableConcept`" in style
        assert "repeated direct-code `or` chains" in checklist
        assert "matches both sets" in terminology
        assert "false/contrasting ValueSet" in terminology
        assert "absence or non-membership" in terminology
        for case_type in (
            "paired-positive",
            "paired-negative",
            "paired-neither",
            "paired-conflict",
            "paired-wrong-type",
            "paired-unresolved",
        ):
            assert case_type in test_matrix
        assert "expect execution failure" in test_matrix
        assert "does not infer" in combined

    def test_skill_inventories_all_coded_categorical_classifiers(self):
        """Every coded Boolean/enum category uses one Concept and ValueSets."""
        skill = skill_body(self.SKILL_PATH)
        style = self.STYLE_GUIDE_PATH.read_text()
        checklist = self.REVIEW_CHECKLIST_PATH.read_text()
        terminology = self.TERMINOLOGY_POLICY_PATH.read_text()

        for document in (skill, style, checklist, terminology):
            assert "categorical classifier inventory" in document.lower()
            assert "one code" in document.lower()

        for document in (skill, style, terminology):
            assert re.search(r"exact\s+single-concept predicate", document)
        assert re.search(r"exact\s+single-concept predicates", checklist)
        assert "Applying this pattern to one prominent category" in skill
        assert "applying the ValueSet pattern to one" in style
        assert "converting one category" in terminology

        assert 'valueset "Positive Interpretation":' in style
        assert 'valueset "Negative Interpretation":' in style
        assert style.count(
            'FHIRHelpers.ToConcept(First("Selected Result".interpretation))'
        ) == 1
        assert 'define "Interpretation Is Positive":' in style
        assert 'define "Interpretation Is Negative":' in style
        assert 'else if "Interpretation Is Positive" then' in style
        assert 'else if "Interpretation Is Negative" then' in style

        assert 'valueset "Qualitative Result Detected":' in style
        assert "source-specific result CodeSystem" in style
        assert 'define "Qualitative Result Concept":' in style
        assert 'define "Qualitative Result Is Detected":' in style
        assert (
            '"Qualitative Result Concept" in "Qualitative Result Detected"'
            in style
        )
        assert "category branches using named membership" in checklist
        assert "they do not compare raw Codes" in terminology
