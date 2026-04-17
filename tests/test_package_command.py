"""Integration tests for rh-skills package command."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.package import package
from tests.conftest import make_tracking, load_tracking


@pytest.fixture
def packagable_topic(tmp_repo):
    """Create a topic with formalized computable resources."""
    topic_dir = tmp_repo / "topics" / "test-topic"
    computable_dir = topic_dir / "computable"
    computable_dir.mkdir(parents=True)

    # Write FHIR JSON resources
    pd = {
        "resourceType": "PlanDefinition",
        "id": "test-rules",
        "type": {"coding": [{"code": "eca-rule"}]},
        "action": [{"title": "Step 1"}],
    }
    (computable_dir / "PlanDefinition-test-rules.json").write_text(json.dumps(pd, indent=2))

    lib = {
        "resourceType": "Library",
        "id": "test-rules-library",
        "type": {"coding": [{"code": "logic-library"}]},
    }
    (computable_dir / "Library-test-rules-library.json").write_text(json.dumps(lib, indent=2))

    # Write CQL
    (computable_dir / "TestRulesLogic.cql").write_text(
        "library TestRulesLogic version '1.0.0'\nusing FHIR version '4.0.1'\n"
    )

    # Write tracking
    make_tracking(tmp_repo, topics=[{
        "name": "test-topic",
        "structured": [],
        "computable": [{
            "name": "test-rules",
            "files": ["topics/test-topic/computable/PlanDefinition-test-rules.json"],
            "checksums": {},
            "converged_from": ["test-rules"],
            "strategy": "decision-table",
        }],
        "events": [],
    }])

    return tmp_repo


class TestPackageCommand:
    def test_dry_run(self, packagable_topic):
        runner = CliRunner()
        result = runner.invoke(package, ["test-topic", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "@reason/test-topic" in result.output
        assert "FHIR JSON" in result.output

    def test_basic_package(self, packagable_topic):
        runner = CliRunner()
        result = runner.invoke(package, ["test-topic"])
        assert result.exit_code == 0, result.output
        assert "package_created" in result.output

        pkg_dir = packagable_topic / "topics" / "test-topic" / "package"
        assert (pkg_dir / "package.json").exists()
        assert (pkg_dir / "ImplementationGuide-test-topic.json").exists()
        assert (pkg_dir / "PlanDefinition-test-rules.json").exists()
        assert (pkg_dir / "TestRulesLogic.cql").exists()

        # Verify package.json structure
        pkg = json.loads((pkg_dir / "package.json").read_text())
        assert pkg["name"] == "@reason/test-topic"
        assert "4.0.1" in pkg["fhirVersions"]
        assert "hl7.fhir.uv.cql" in pkg["dependencies"]

    def test_tracking_updated(self, packagable_topic):
        runner = CliRunner()
        result = runner.invoke(package, ["test-topic"])
        assert result.exit_code == 0

        tracking = load_tracking(packagable_topic)
        topic = next(t for t in tracking["topics"] if t["name"] == "test-topic")
        events = topic["events"]
        assert any(e["type"] == "package_created" for e in events)

    def test_no_computable_resources(self, tmp_repo):
        make_tracking(tmp_repo, topics=[{
            "name": "empty-topic",
            "structured": [],
            "computable": [],
            "events": [],
        }])
        runner = CliRunner()
        result = runner.invoke(package, ["empty-topic"])
        assert result.exit_code != 0

    def test_topic_not_found(self, packagable_topic):
        runner = CliRunner()
        result = runner.invoke(package, ["nonexistent-topic"])
        assert result.exit_code != 0
