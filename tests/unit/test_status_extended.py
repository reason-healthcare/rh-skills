"""Tests for rh-skills status extended subcommands: progress, next-steps, check-changes."""

import pytest
from click.testing import CliRunner

from rh_skills.commands.status import status
from tests.conftest import load_tracking


def make_topic_entry(tmp_repo, name, sources=0, structured=0, computable=0):
    """Set up tracking.yaml with a topic at a given artifact count."""
    from ruamel.yaml import YAML
    y = YAML()
    y.default_flow_style = False
    tracking_path = tmp_repo / "tracking.yaml"
    with open(tracking_path) as f:
        tracking = y.load(f)

    # Add sources to repo-level sources list
    for i in range(sources):
        src_name = f"src-{i}"
        src_file = tmp_repo / "sources" / f"{src_name}.md"
        src_file.write_text(f"Source {i} content")
        tracking["sources"].append({
            "name": src_name,
            "file": f"sources/{src_name}.md",
            "checksum": "abc123",
            "ingested_at": "2026-04-04T00:00:00Z",
        })

    structured_list = [
        {"name": f"artifact-{i}", "derived_from": ["src-0"] if sources > 0 else []}
        for i in range(structured)
    ]
    computable_list = [
        {"name": f"computable-{i}", "converged_from": [f"artifact-{j}" for j in range(structured)]}
        for i in range(computable)
    ]

    (tmp_repo / "topics" / name / "structured").mkdir(parents=True, exist_ok=True)
    (tmp_repo / "topics" / name / "computable").mkdir(parents=True, exist_ok=True)

    tracking["topics"].append({
        "name": name,
        "title": "Test Topic",
        "author": "Test Author",
        "created_at": "2026-04-04T00:00:00Z",
        "structured": structured_list,
        "computable": computable_list,
        "events": [{"type": "created", "timestamp": "2026-04-04T00:00:00Z", "description": "init"}],
    })
    with open(tracking_path, "w") as f:
        y.dump(tracking, f)


# ── rh-skills status progress ─────────────────────────────────────────────────────────

def test_progress_exits_zero(tmp_repo):
    make_topic_entry(tmp_repo, "t1")
    runner = CliRunner()
    result = runner.invoke(status, ["progress", "t1"])
    assert result.exit_code == 0, result.output


def test_progress_shows_artifact_counts(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=2, structured=1)
    runner = CliRunner()
    result = runner.invoke(status, ["progress", "t1"])
    assert result.exit_code == 0, result.output
    assert "L1 sources:     2" in result.output
    assert "L2 structured:  1" in result.output
    assert "L3 computable:  0" in result.output


def test_progress_shows_completeness_percentage(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=1)
    runner = CliRunner()
    result = runner.invoke(status, ["progress", "t1"])
    assert "Complete:" in result.output
    assert "%" in result.output


def test_progress_shows_stage_pipeline(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=1)
    runner = CliRunner()
    result = runner.invoke(status, ["progress", "t1"])
    # The active stage is shown in brackets
    assert "[Ingest]" in result.output


def test_progress_uses_bullet_next_steps(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=1)
    runner = CliRunner()
    result = runner.invoke(status, ["progress", "t1"])
    assert "Next steps:" in result.output
    assert "  - " in result.output
    assert "A)" not in result.output


def test_progress_100_pct_when_computable(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=1, structured=1, computable=1)
    runner = CliRunner()
    result = runner.invoke(status, ["progress", "t1"])
    assert "100%" in result.output


# ── rh-skills status next-steps ───────────────────────────────────────────────────────

def test_next_steps_exits_zero(tmp_repo):
    make_topic_entry(tmp_repo, "t1")
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert result.exit_code == 0, result.output


def test_next_steps_suggests_ingest_when_no_sources(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=0)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "rh-inf-ingest plan" in result.output


def test_next_steps_discovery_plan_aware_without_plan(tmp_repo):
    """Without a discovery-plan.yaml, suggests 'start source discovery'."""
    make_topic_entry(tmp_repo, "t1", sources=0)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "rh-inf-discovery plan t1" in result.output
    assert "Start" in result.output or "start" in result.output or "discovery" in result.output.lower()


def test_next_steps_discovery_plan_aware_with_plan(tmp_repo):
    """With a discovery-plan.yaml present, primary option says 'Update your discovery plan'."""
    make_topic_entry(tmp_repo, "t1", sources=0)
    plan_path = tmp_repo / "topics" / "t1" / "process" / "plans"
    plan_path.mkdir(parents=True, exist_ok=True)
    (plan_path / "discovery-plan.yaml").write_text("topic: t1\nsources: []\n")
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "rh-inf-discovery plan t1" in result.output
    assert "rh-inf-ingest plan t1" in result.output
    assert "Update" in result.output or "existing" in result.output.lower()


def test_next_steps_suggests_extract_when_sources_but_no_structured(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=2, structured=0)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "rh-inf-extract plan" in result.output


def test_next_steps_suggests_formalize_when_structured_but_no_computable(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=1, structured=2, computable=0)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "rh-inf-formalize plan" in result.output


def test_next_steps_output_is_runnable_command(tmp_repo):
    """The next-steps section must contain RH commands, not just prose."""
    make_topic_entry(tmp_repo, "t1", sources=1, structured=0)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "Next steps:" in result.output
    assert "rh-" in result.output  # must be an RH skill command
    assert "A)" not in result.output


def test_next_steps_reports_no_immediate_action_for_computable_topics(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=1, structured=1, computable=1)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "t1"])
    assert "No immediate action required" in result.output
    assert "rh-inf-verify verify t1" in result.output


def test_next_steps_unknown_topic_offers_recovery_guidance(tmp_repo):
    make_topic_entry(tmp_repo, "known-topic", sources=1)
    runner = CliRunner()
    result = runner.invoke(status, ["next-steps", "ghost-topic"])
    assert result.exit_code == 2
    assert "Topic 'ghost-topic' not found" in result.output
    assert "rh-skills list" in result.output
    assert "rh-skills init ghost-topic" in result.output


# ── rh-skills status check-changes ────────────────────────────────────────────────────

def test_check_changes_exits_zero_when_no_sources(tmp_repo):
    make_topic_entry(tmp_repo, "t1", sources=0)
    runner = CliRunner()
    result = runner.invoke(status, ["check-changes", "t1"])
    assert result.exit_code == 0, result.output
    assert "No L1 sources registered" in result.output
    assert "Next steps:" in result.output


def test_check_changes_without_tracking_offers_init_guidance(tmp_repo):
    (tmp_repo / "tracking.yaml").unlink()
    runner = CliRunner()
    result = runner.invoke(status, ["check-changes", "t1"])
    assert result.exit_code == 1
    assert "No tracking.yaml found" in result.output
    assert "rh-skills init <topic>" in result.output


def test_check_changes_ok_when_source_unchanged(tmp_repo):
    import hashlib
    src_file = tmp_repo / "sources" / "stable.md"
    content = "Stable clinical content"
    src_file.write_text(content)
    checksum = hashlib.sha256(content.encode()).hexdigest()

    from ruamel.yaml import YAML
    y = YAML(); y.default_flow_style = False
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    tracking["sources"].append({
        "name": "stable",
        "file": "sources/stable.md",
        "checksum": checksum,
        "ingested_at": "2026-04-04T00:00:00Z",
    })
    tracking["topics"].append({
        "name": "t1", "title": "T", "author": "A", "created_at": "2026-04-04",
        "structured": [], "computable": [], "events": [],
    })
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    runner = CliRunner()
    result = runner.invoke(status, ["check-changes", "t1"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "All sources unchanged" in result.output


def test_check_changes_detects_modified_file(tmp_repo):
    import hashlib
    src_file = tmp_repo / "sources" / "mutable.md"
    src_file.write_text("Original content")
    old_checksum = hashlib.sha256(b"Original content").hexdigest()

    from ruamel.yaml import YAML
    y = YAML(); y.default_flow_style = False
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    tracking["sources"].append({
        "name": "mutable",
        "file": "sources/mutable.md",
        "checksum": old_checksum,
        "ingested_at": "2026-04-04T00:00:00Z",
    })
    tracking["topics"].append({
        "name": "t1", "title": "T", "author": "A", "created_at": "2026-04-04",
        "structured": [], "computable": [], "events": [],
    })
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    src_file.write_text("Modified content")
    runner = CliRunner()
    result = runner.invoke(status, ["check-changes", "t1"])
    assert result.exit_code != 0
    assert "CHANGED" in result.output
    assert "Next steps:" in result.output
    assert "rh-inf-ingest implement t1" in result.output


def test_check_changes_reports_stale_derived_artifacts(tmp_repo):
    import hashlib
    src_file = tmp_repo / "sources" / "source.md"
    src_file.write_text("Original")
    old_checksum = hashlib.sha256(b"Original").hexdigest()

    from ruamel.yaml import YAML
    y = YAML(); y.default_flow_style = False
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    tracking["sources"].append({
        "name": "source",
        "file": "sources/source.md",
        "checksum": old_checksum,
        "ingested_at": "2026-04-04T00:00:00Z",
    })
    tracking["topics"].append({
        "name": "t1", "title": "T", "author": "A", "created_at": "2026-04-04",
        "structured": [{"name": "downstream-artifact", "derived_from": ["source"]}],
        "computable": [], "events": [],
    })
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    src_file.write_text("Modified")
    runner = CliRunner()
    result = runner.invoke(status, ["check-changes", "t1"])
    assert "downstream-artifact" in result.output


def test_check_changes_reports_stale_computable_artifacts(tmp_repo):
    import hashlib
    src_file = tmp_repo / "sources" / "source.md"
    src_file.write_text("Original")
    old_checksum = hashlib.sha256(b"Original").hexdigest()

    from ruamel.yaml import YAML
    y = YAML(); y.default_flow_style = False
    with open(tmp_repo / "tracking.yaml") as f:
        tracking = y.load(f)
    tracking["sources"].append({
        "name": "source",
        "file": "sources/source.md",
        "checksum": old_checksum,
        "ingested_at": "2026-04-04T00:00:00Z",
    })
    tracking["topics"].append({
        "name": "t1",
        "title": "T",
        "author": "A",
        "created_at": "2026-04-04",
        "structured": [{"name": "downstream-artifact", "derived_from": ["source"]}],
        "computable": [{"name": "pathway-artifact", "converged_from": ["downstream-artifact"]}],
        "events": [],
    })
    with open(tmp_repo / "tracking.yaml", "w") as f:
        y.dump(tracking, f)

    src_file.write_text("Modified")
    runner = CliRunner()
    result = runner.invoke(status, ["check-changes", "t1"])
    assert "Potentially stale L3 artifacts: pathway-artifact" in result.output
