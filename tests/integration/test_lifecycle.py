"""Integration tests for full skill lifecycle — ported from tests/integration/skill-lifecycle.bats."""

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.ingest import ingest
from rh_skills.commands.init import init
from rh_skills.commands.promote import promote
from rh_skills.commands.validate import validate


# ── Phase 1: Init ─────────────────────────────────────────────────────────────

def test_lifecycle_init_creates_valid_scaffold(tmp_repo):
    runner = CliRunner()
    result = runner.invoke(init, ["test-workflow-skill"])
    assert result.exit_code == 0
    assert (tmp_repo / "topics" / "test-workflow-skill").is_dir()
    assert (tmp_repo / "tracking.yaml").exists()
    assert (tmp_repo / "topics" / "test-workflow-skill" / "TOPIC.md").exists()


def test_lifecycle_tracking_yaml_valid_after_init(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    y = YAML()
    with open(tmp_repo / "tracking.yaml") as f:
        data = y.load(f)
    assert isinstance(data, dict)
    assert "topics" in data


def test_lifecycle_sources_dir_ready_after_init(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    assert (tmp_repo / "sources").is_dir()


# ── Phase 2: L1 artifact ──────────────────────────────────────────────────────

def test_lifecycle_l1_artifact_can_be_added(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    src_file = tmp_repo / "sources" / "guideline.md"
    src_file.write_text("Clinical guideline content.")
    assert src_file.exists()


# ── Phase 3: L2 promotion (dry-run) ───────────────────────────────────────────

def test_lifecycle_derive_dry_run_prints_prompt(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])

    # Register source in tracking
    y = YAML()
    y.default_flow_style = False
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    tracking["sources"].append({
        "name": "guideline",
        "file": "sources/guideline.md",
        "checksum": "abc",
        "ingested_at": "2026-04-03T00:00:00Z",
    })
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    result = runner.invoke(promote, ["derive", "test-workflow-skill", "criteria", "--source", "guideline", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output


# ── Phase 4: L2 validation ────────────────────────────────────────────────────

def test_lifecycle_validate_accepts_well_formed_l2(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    l2_dir = tmp_repo / "topics" / "test-workflow-skill" / "structured" / "criteria"
    l2_dir.mkdir(parents=True, exist_ok=True)
    l2_file = l2_dir / "criteria.yaml"
    l2_file.write_text("""\
id: criteria
name: Criteria
title: "Screening Criteria"
version: "1.0.0"
status: draft
domain: testing
description: |
  A test L2 artifact for lifecycle validation.
derived_from:
  - guideline
""")
    result = runner.invoke(validate, ["test-workflow-skill", "l2", "criteria"])
    assert result.exit_code == 0


def test_lifecycle_validate_rejects_missing_fields_l2(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    bad_dir = tmp_repo / "topics" / "test-workflow-skill" / "structured" / "bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    bad_file = bad_dir / "bad.yaml"
    bad_file.write_text("name: Bad\n")
    result = runner.invoke(validate, ["test-workflow-skill", "l2", "bad"])
    assert result.exit_code == 1


# ── Phase 5: L3 promotion (dry-run) ───────────────────────────────────────────

def test_lifecycle_combine_dry_run_prints_prompt(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])

    # Create an L2 artifact and register it
    l2_dir = tmp_repo / "topics" / "test-workflow-skill" / "structured" / "criteria"
    l2_dir.mkdir(parents=True, exist_ok=True)
    l2_file = l2_dir / "criteria.yaml"
    l2_file.write_text("""\
id: criteria
name: Criteria
title: "Screening Criteria"
version: "1.0.0"
status: draft
domain: testing
description: Test L2 artifact.
derived_from:
  - guideline
""")
    y = YAML()
    y.default_flow_style = False
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    for t in tracking["topics"]:
        if t["name"] == "test-workflow-skill":
            t["structured"].append({
                "name": "criteria",
                "file": "topics/test-workflow-skill/structured/criteria/criteria.yaml",
                "created_at": "2026-04-03T00:00:00Z",
                "derived_from": ["guideline"],
            })
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    result = runner.invoke(promote, ["combine", "test-workflow-skill", "criteria", "computable", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output


# ── Phase 6: L3 validation ────────────────────────────────────────────────────

def test_lifecycle_validate_accepts_well_formed_l3(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    l3_file = tmp_repo / "topics" / "test-workflow-skill" / "computable" / "computable.yaml"
    l3_file.write_text("""\
artifact_schema_version: "1.0"
metadata:
  id: computable
  name: Computable
  title: "Test Computable Artifact"
  version: "1.0.0"
  status: draft
  domain: testing
  created_date: "2026-04-03"
  description: |
    A test L3 artifact for lifecycle validation.
converged_from:
  - criteria
""")
    result = runner.invoke(validate, ["test-workflow-skill", "l3", "computable"])
    assert result.exit_code == 0


# ── Tracking audit ────────────────────────────────────────────────────────────

def test_lifecycle_tracking_arrays_are_lists(tmp_repo):
    runner = CliRunner()
    runner.invoke(init, ["test-workflow-skill"])
    y = YAML()
    with open(tmp_repo / "tracking.yaml") as f:
        data = y.load(f)
    assert isinstance(data["sources"], list)
    topic = next(t for t in data["topics"] if t["name"] == "test-workflow-skill")
    assert isinstance(topic["structured"], list)
    assert isinstance(topic["computable"], list)


def test_lifecycle_diabetes_screening_fixture_flow(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv(
        "RH_STUB_RESPONSE",
        """\
id: screening-criteria
name: screening-criteria
title: "Diabetes Screening Criteria"
version: "1.0.0"
status: draft
domain: diabetes
description: |
  Evidence-based criteria for identifying adults who should be screened for
  diabetes and prediabetes.
derived_from:
  - ada-guidelines-2024
""",
    )

    runner = CliRunner()
    init_result = runner.invoke(init, ["diabetes-screening"])
    assert init_result.exit_code == 0, init_result.output

    source_file = tmp_repo / "ada-guidelines-2024.md"
    source_file.write_text(
        """\
ADA 2024 diabetes screening guidance:
- Begin routine screening at age 35
- Screen earlier when overweight or obese with additional risk factors
"""
    )

    ingest_result = runner.invoke(ingest, ["implement", str(source_file)])
    assert ingest_result.exit_code == 0, ingest_result.output

    derive_result = runner.invoke(
        promote,
        [
            "derive",
            "diabetes-screening",
            "screening-criteria",
            "--source",
            "ada-guidelines-2024",
        ],
    )
    assert derive_result.exit_code == 0, derive_result.output

    validate_result = runner.invoke(
        validate, ["diabetes-screening", "l2", "screening-criteria"]
    )
    assert validate_result.exit_code == 0, validate_result.output

    y = YAML()
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)

    assert tracking["sources"][0]["name"] == "ada-guidelines-2024"
    topic = next(t for t in tracking["topics"] if t["name"] == "diabetes-screening")
    assert topic["structured"][0]["name"] == "screening-criteria"
