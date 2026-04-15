"""Tests for rh-skills validate --plan (FR-019 discovery plan checks)."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from rh_skills.commands.validate import validate


def write_plan(tmp_path: Path, content: str) -> Path:
    """Write a discovery-plan.yaml file with given YAML content."""
    plan = tmp_path / "discovery-plan.yaml"
    plan.write_text(content)
    return plan


def make_source(
    name="ada-guidelines",
    source_type="clinical-guideline",
    rationale="Primary clinical guidance",
    evidence_level="ia",
    search_terms=None,
):
    terms = search_terms or ["diabetes guidelines", "ADA standards"]
    return {
        "name": name,
        "type": source_type,
        "rationale": rationale,
        "evidence_level": evidence_level,
        "search_terms": terms,
        "access": "open",
    }


def yaml_sources(sources: list[dict]) -> str:
    """Convert list of source dicts to YAML content for discovery-plan.yaml."""
    lines = ["sources:"]
    for s in sources:
        lines.append(f"  - name: {s['name']}")
        lines.append(f"    type: {s['type']}")
        lines.append(f"    rationale: {s['rationale']}")
        lines.append(f"    evidence_level: {s['evidence_level']}")
        lines.append(f"    access: {s.get('access', 'open')}")
        terms = s.get("search_terms", [])
        if terms:
            lines.append("    search_terms:")
            for t in terms:
                lines.append(f"      - {t}")
    return "\n".join(lines)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_validate_plan_valid_exits_0(tmp_path):
    """A complete, valid plan exits 0 with all checks passing."""
    sources = [
        make_source(f"source-{i}", source_type="clinical-guideline") for i in range(4)
    ]
    sources.append(make_source("snomed-ct", source_type="terminology"))
    sources.append(make_source("hcup-costs", source_type="health-economics"))

    plan = write_plan(tmp_path, yaml_sources(sources))
    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])

    assert result.exit_code == 0, result.output
    assert "✓ Parses as valid YAML" in result.output
    assert "✓ Source count" in result.output
    assert "✓ Terminology source present" in result.output
    assert "✓ All entries have rationale" in result.output
    assert "VALID" in result.output


# ── Parse errors ──────────────────────────────────────────────────────────────

def test_validate_plan_missing_file_exits_1(tmp_path):
    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_validate_plan_malformed_yaml_exits_1(tmp_path):
    plan = tmp_path / "plan.yaml"
    plan.write_text("sources: [\n  - broken yaml\n")
    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1


def test_validate_plan_no_frontmatter_exits_1(tmp_path):
    """A plain prose file (not a YAML mapping) should fail validation."""
    plan = tmp_path / "plan.yaml"
    plan.write_text("# Not YAML\n\nJust prose.\n")
    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "not a yaml mapping" in result.output.lower()


# ── Source count ──────────────────────────────────────────────────────────────

def test_validate_plan_below_min_count_exits_1(tmp_path):
    """Fewer than 5 sources → exit 1."""
    sources = [make_source(f"s{i}") for i in range(3)]
    sources.append(make_source("terminology-s", source_type="terminology"))
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "too low" in result.output


def test_validate_plan_above_max_count_exits_1(tmp_path):
    """More than 25 sources → exit 1."""
    sources = [make_source(f"s{i}") for i in range(25)]
    sources.append(make_source("extra-s"))  # 26 total
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "too high" in result.output


# ── Terminology source ────────────────────────────────────────────────────────

def test_validate_plan_no_terminology_exits_1(tmp_path):
    sources = [make_source(f"s{i}") for i in range(5)]  # no terminology type
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "terminology" in result.output.lower()
    assert "✗" in result.output


# ── Rationale and search_terms ────────────────────────────────────────────────

def test_validate_plan_missing_rationale_exits_1(tmp_path):
    sources = [make_source(f"s{i}") for i in range(4)]
    sources.append(make_source("terminology-s", source_type="terminology"))
    # Override one source to have empty rationale
    sources[0]["rationale"] = ""
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "rationale" in result.output.lower()


def test_validate_plan_missing_search_terms_exits_1(tmp_path):
    sources = [make_source(f"s{i}") for i in range(4)]
    sources.append(make_source("terminology-s", source_type="terminology"))
    sources[0]["search_terms"] = []
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "search_terms" in result.output.lower()


# ── Evidence level validation ─────────────────────────────────────────────────

def test_validate_plan_invalid_evidence_level_exits_1(tmp_path):
    sources = [make_source(f"s{i}") for i in range(4)]
    sources.append(make_source("terminology-s", source_type="terminology"))
    sources[0]["evidence_level"] = "not-a-real-level"
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 1
    assert "evidence_level" in result.output.lower()
    assert "not-a-real-level" in result.output


# ── Health-economics warning (exit 0) ─────────────────────────────────────────

def test_validate_plan_no_health_econ_warns_but_exits_0(tmp_path):
    """Missing health-economics source → warning only, exit 0."""
    sources = [make_source(f"s{i}") for i in range(4)]
    sources.append(make_source("terminology-s", source_type="terminology"))
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 0
    assert "health-economics" in result.output.lower()
    assert "⚠" in result.output


# ── Unknown source type (warning only) ───────────────────────────────────────

def test_validate_plan_unknown_type_warns_but_exits_0(tmp_path):
    """Unknown source type → warning, not error."""
    sources = [make_source(f"s{i}") for i in range(4)]
    sources.append(make_source("terminology-s", source_type="terminology"))
    sources[0]["type"] = "unknown-custom-type"
    plan = write_plan(tmp_path, yaml_sources(sources))

    runner = CliRunner()
    result = runner.invoke(validate, ["--plan", str(plan)])
    assert result.exit_code == 0
    assert "unknown-custom-type" in result.output
    assert "⚠" in result.output
