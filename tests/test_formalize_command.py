"""Integration tests for rh-skills formalize command."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.formalize import formalize, STRATEGY_REGISTRY
from tests.conftest import make_tracking, load_tracking


@pytest.fixture
def formalize_topic(tmp_repo):
    """Create a topic with an approved L2 artifact ready for formalization."""
    topic_dir = tmp_repo / "topics" / "test-topic"
    structured_dir = topic_dir / "structured"
    computable_dir = topic_dir / "computable"
    structured_dir.mkdir(parents=True)
    computable_dir.mkdir(parents=True)

    # Write L2 artifact
    y = YAML()
    y.default_flow_style = False
    l2 = {
        "artifact_schema_version": "1.0",
        "metadata": {"id": "test-rules", "title": "Test Decision Rules"},
        "decision_table": [{"condition": "temp > 38", "action": "order blood culture"}],
    }
    with open(structured_dir / "test-rules.yaml", "w") as f:
        y.dump(l2, f)

    # Write tracking with structured artifact
    make_tracking(tmp_repo, topics=[{
        "name": "test-topic",
        "structured": [{
            "name": "test-rules",
            "artifact_type": "decision-table",
            "status": "approved",
            "file": "topics/test-topic/structured/test-rules.yaml",
        }],
        "computable": [],
        "events": [],
    }])

    os.environ["LLM_PROVIDER"] = "stub"
    yield tmp_repo
    os.environ.pop("LLM_PROVIDER", None)


class TestFormalizeCommand:
    def test_dry_run(self, formalize_topic):
        runner = CliRunner()
        result = runner.invoke(formalize, ["test-topic", "test-rules", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "PlanDefinition" in result.output
        assert "eca-rule" in result.output

    def test_basic_formalize(self, formalize_topic):
        runner = CliRunner()
        result = runner.invoke(formalize, ["test-topic", "test-rules"])
        assert result.exit_code == 0, result.output
        assert "computable_converged" in result.output

        # Check files were written
        comp_dir = formalize_topic / "topics" / "test-topic" / "computable"
        json_files = list(comp_dir.glob("*.json"))
        assert len(json_files) >= 1

        # Check FHIR JSON structure
        for jf in json_files:
            resource = json.loads(jf.read_text())
            assert "resourceType" in resource
            assert "id" in resource

        # Check CQL was generated (decision-table has Library support)
        cql_files = list(comp_dir.glob("*.cql"))
        assert len(cql_files) >= 1

    def test_tracking_updated(self, formalize_topic):
        runner = CliRunner()
        result = runner.invoke(formalize, ["test-topic", "test-rules"])
        assert result.exit_code == 0

        tracking = load_tracking(formalize_topic)
        topic = next(t for t in tracking["topics"] if t["name"] == "test-topic")

        # Check computable entry
        assert len(topic["computable"]) == 1
        entry = topic["computable"][0]
        assert entry["name"] == "test-rules"
        assert isinstance(entry["files"], list)
        assert isinstance(entry["checksums"], dict)
        assert entry["converged_from"] == ["test-rules"]
        assert entry["strategy"] == "decision-table"

        # Check event
        events = topic["events"]
        assert any(e["type"] == "computable_converged" for e in events)

    def test_artifact_not_found(self, formalize_topic):
        runner = CliRunner()
        result = runner.invoke(formalize, ["test-topic", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_topic_not_found(self, formalize_topic):
        runner = CliRunner()
        result = runner.invoke(formalize, ["nonexistent-topic", "test-rules"])
        assert result.exit_code != 0

    def test_force_overwrite(self, formalize_topic):
        runner = CliRunner()
        # First run
        result = runner.invoke(formalize, ["test-topic", "test-rules"])
        assert result.exit_code == 0

        # Second run without force — should fail on existing files
        result2 = runner.invoke(formalize, ["test-topic", "test-rules"])
        assert result2.exit_code != 0 or "already exists" in (result2.output + (result2.stderr or ""))

        # Third run with force — should succeed
        result3 = runner.invoke(formalize, ["test-topic", "test-rules", "--force"])
        assert result3.exit_code == 0


class TestUnknownTypeFallback:
    def test_unknown_type_falls_back(self, tmp_repo):
        """FR-009: Unknown artifact_type falls back to generic strategy."""
        topic_dir = tmp_repo / "topics" / "test-topic"
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        # Write L2 with unknown type
        y = YAML()
        y.default_flow_style = False
        with open(structured_dir / "custom-artifact.yaml", "w") as f:
            y.dump({"metadata": {"id": "custom"}}, f)

        make_tracking(tmp_repo, topics=[{
            "name": "test-topic",
            "structured": [{
                "name": "custom-artifact",
                "artifact_type": "custom-unknown-type",
                "status": "approved",
            }],
            "computable": [],
            "events": [],
        }])

        os.environ["LLM_PROVIDER"] = "stub"
        try:
            runner = CliRunner()
            result = runner.invoke(formalize, ["test-topic", "custom-artifact"])
            assert result.exit_code == 0, result.output

            # Check tracking records generic strategy
            tracking = load_tracking(tmp_repo)
            topic = next(t for t in tracking["topics"] if t["name"] == "test-topic")
            entry = topic["computable"][0]
            assert entry["strategy"] == "generic"
        finally:
            os.environ.pop("LLM_PROVIDER", None)


class TestStrategyRegistry:
    def test_all_seven_types_registered(self):
        expected = {
            "evidence-summary", "decision-table", "care-pathway",
            "terminology", "measure", "assessment", "policy",
        }
        assert set(STRATEGY_REGISTRY.keys()) == expected

    def test_each_strategy_has_required_keys(self):
        for atype, strategy in STRATEGY_REGISTRY.items():
            assert "primary" in strategy, f"{atype} missing primary"
            assert "supporting" in strategy, f"{atype} missing supporting"
            assert "description" in strategy, f"{atype} missing description"
