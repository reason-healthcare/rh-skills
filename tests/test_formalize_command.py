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
    structured_dir = topic_dir / "structured" / "test-rules"
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
            "file": "topics/test-topic/structured/test-rules/test-rules.yaml",
        }],
        "computable": [],
        "events": [],
    }])

    # Write formalize config
    process_dir = topic_dir / "process"
    process_dir.mkdir(parents=True, exist_ok=True)
    (process_dir / "formalize-config.yaml").write_text(
        "name: TestTopic\nid: test-topic\ncanonical: http://example.org/fhir\nstatus: draft\nversion: 0.1.0\n"
    )

    os.environ["LLM_PROVIDER"] = "stub"
    yield tmp_repo
    os.environ.pop("LLM_PROVIDER", None)


@pytest.fixture
def formalize_topic_with_rules(tmp_repo):
    """Create a topic with a structured L2 decision-table (rules, conditions, actions)."""
    topic_dir = tmp_repo / "topics" / "test-topic"
    structured_dir = topic_dir / "structured" / "test-rules"
    computable_dir = topic_dir / "computable"
    structured_dir.mkdir(parents=True)
    computable_dir.mkdir(parents=True)

    l2 = {
        "artifact_type": "decision-table",
        "sections": {
            "conditions": [
                {"id": "c1", "label": "Diagnosis confirmed", "values": ["yes", "no"]},
                {"id": "c2", "label": "Purulent discharge present", "values": ["yes", "no", "N/A"]},
            ],
            "actions": [
                {"id": "a1", "label": "Do not proceed — diagnosis not confirmed"},
                {"id": "a2", "label": "Do not prescribe antibiotics — discharge absent"},
                {"id": "a3", "label": "Offer surgery"},
            ],
            "rules": [
                {"id": "r1", "when": {"c1": "no", "c2": "N/A"}, "then": ["a1"]},
                {"id": "r2", "when": {"c1": "yes", "c2": "no"}, "then": ["a2"]},
                {"id": "r3", "when": {"c1": "yes", "c2": "yes"}, "then": ["a3"]},
            ],
        },
    }
    y = YAML()
    y.default_flow_style = False
    with open(structured_dir / "test-rules.yaml", "w") as f:
        y.dump(l2, f)

    make_tracking(tmp_repo, topics=[{
        "name": "test-topic",
        "structured": [{
            "name": "test-rules",
            "artifact_type": "decision-table",
            "status": "approved",
            "file": "topics/test-topic/structured/test-rules/test-rules.yaml",
        }],
        "computable": [],
        "events": [],
    }])

    # Write formalize config
    process_dir = topic_dir / "process"
    process_dir.mkdir(parents=True, exist_ok=True)
    (process_dir / "formalize-config.yaml").write_text(
        "name: TestTopic\nid: test-topic\ncanonical: http://example.org/fhir\nstatus: draft\nversion: 0.1.0\n"
    )

    os.environ["LLM_PROVIDER"] = "stub"
    yield tmp_repo
    os.environ.pop("LLM_PROVIDER", None)


@pytest.fixture
def formalize_topic_nested_path(tmp_repo):
    """Create a topic where L2 is stored at structured/<artifact>/<artifact>.yaml."""
    topic_dir = tmp_repo / "topics" / "test-topic"
    nested_dir = topic_dir / "structured" / "test-rules"
    computable_dir = topic_dir / "computable"
    nested_dir.mkdir(parents=True)
    computable_dir.mkdir(parents=True)

    l2 = {
        "artifact_type": "decision-table",
        "sections": {
            "conditions": [{"id": "c1", "label": "Diagnosis confirmed", "values": ["yes", "no"]}],
            "actions": [{"id": "a1", "label": "Do not proceed"}],
            "rules": [{"id": "r1", "when": {"c1": "no"}, "then": ["a1"]}],
        },
    }
    y = YAML()
    y.default_flow_style = False
    with open(nested_dir / "test-rules.yaml", "w") as f:
        y.dump(l2, f)

    make_tracking(tmp_repo, topics=[{
        "name": "test-topic",
        "structured": [{
            "name": "test-rules",
            "artifact_type": "decision-table",
            "status": "approved",
            "file": "topics/test-topic/structured/test-rules/test-rules.yaml",
        }],
        "computable": [],
        "events": [],
    }])

    # Write formalize config
    process_dir = topic_dir / "process"
    process_dir.mkdir(parents=True, exist_ok=True)
    (process_dir / "formalize-config.yaml").write_text(
        "name: TestTopic\nid: test-topic\ncanonical: http://example.org/fhir\nstatus: draft\nversion: 0.1.0\n"
    )

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
        saw_plan_definition = False
        for jf in json_files:
            resource = json.loads(jf.read_text())
            assert "resourceType" in resource
            assert "id" in resource
            if resource["resourceType"] == "PlanDefinition":
                saw_plan_definition = True
                assert resource["type"]["coding"][0]["code"] == "eca-rule"
                assert resource["type"]["coding"][0]["system"] == "http://terminology.hl7.org/CodeSystem/plan-definition-type"
                assert resource.get("library")
                assert resource["action"][0].get("condition")
                assert resource["action"][0].get("trigger")
        assert saw_plan_definition

        # CQL is NOT auto-generated by formalize — the rh-inf-cql skill owns .cql files.
        # If a Library is in scope, formalize emits a guidance note instead.
        cql_files = list(comp_dir.glob("*.cql"))
        assert len(cql_files) == 0, (
            "formalize must NOT auto-generate .cql files — "
            "CQL authoring is delegated to `rh-inf-cql` (author mode)"
        )

    def test_decision_table_rules_scaffold(self, formalize_topic_with_rules):
        """Structured L2 rules are deterministically scaffolded into PlanDefinition.action[]."""
        runner = CliRunner()
        result = runner.invoke(formalize, ["test-topic", "test-rules"])
        assert result.exit_code == 0, result.output

        comp_dir = formalize_topic_with_rules / "topics" / "test-topic" / "computable"
        plan = next(
            json.loads(f.read_text())
            for f in comp_dir.glob("*.json")
            if json.loads(f.read_text()).get("resourceType") == "PlanDefinition"
        )

        actions = plan["action"]
        # 3 rules → 3 actions
        assert len(actions) == 3

        # Rule IDs preserved
        assert actions[0]["id"] == "r1"
        assert actions[1]["id"] == "r2"
        assert actions[2]["id"] == "r3"

        # r1: c1=no, c2=N/A → 1 condition (c2 skipped); negated form
        r1_conditions = actions[0]["condition"]
        assert len(r1_conditions) == 1
        assert r1_conditions[0]["kind"] == "applicability"
        assert r1_conditions[0]["expression"]["language"] == "text/cql-expression"
        assert "Not" in r1_conditions[0]["expression"]["expression"]

        # r2: c1=yes, c2=no → 2 conditions
        r2_conditions = actions[1]["condition"]
        assert len(r2_conditions) == 2

        # r3: c1=yes, c2=yes → 2 conditions; no negation
        r3_conditions = actions[2]["condition"]
        assert len(r3_conditions) == 2
        assert all("Not" not in c["expression"]["expression"] for c in r3_conditions)

        # Action descriptions map from action labels
        assert "diagnosis not confirmed" in actions[0]["description"]
        assert "antibiotics" in actions[1]["description"]

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

    def test_nested_structured_path_resolution(self, formalize_topic_nested_path):
        """Formalize reads L2 from structured/<artifact>/<artifact>.yaml when tracked."""
        runner = CliRunner()
        result = runner.invoke(formalize, ["test-topic", "test-rules"])
        assert result.exit_code == 0, result.output

        comp_dir = formalize_topic_nested_path / "topics" / "test-topic" / "computable"
        plan = next(
            json.loads(f.read_text())
            for f in comp_dir.glob("*.json")
            if json.loads(f.read_text()).get("resourceType") == "PlanDefinition"
        )
        assert plan["action"][0]["id"] == "r1"

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
                "file": "topics/test-topic/structured/custom-artifact.yaml",
                "status": "approved",
            }],
            "computable": [],
            "events": [],
        }])

        # Write formalize config
        process_dir = topic_dir / "process"
        process_dir.mkdir(parents=True, exist_ok=True)
        (process_dir / "formalize-config.yaml").write_text(
            "name: TestTopic\nid: test-topic\ncanonical: http://example.org/fhir\nstatus: draft\nversion: 0.1.0\n"
        )

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


class TestCqlEmbedding:
    """CQL source is embedded as base64 content in Library JSON when present."""

    def _make_measure_topic(self, tmp_repo):
        topic_dir = tmp_repo / "topics" / "test-measure"
        structured_dir = topic_dir / "structured"
        computable_dir = topic_dir / "computable"
        structured_dir.mkdir(parents=True)
        computable_dir.mkdir(parents=True)

        y = YAML()
        y.default_flow_style = False
        with open(structured_dir / "test-measure.yaml", "w") as f:
            y.dump({
                "metadata": {"id": "test-measure", "title": "Test Measure"},
                "populations": [{"id": "ip", "type": "initial-population"}],
            }, f)

        make_tracking(tmp_repo, topics=[{
            "name": "test-measure",
            "structured": [{
                "name": "test-measure",
                "artifact_type": "measure",
                "status": "approved",
                "file": "topics/test-measure/structured/test-measure.yaml",
            }],
            "computable": [],
            "events": [],
        }])

        # Write formalize config
        process_dir = topic_dir / "process"
        process_dir.mkdir(parents=True, exist_ok=True)
        (process_dir / "formalize-config.yaml").write_text(
            "name: TestMeasure\nid: test-measure\ncanonical: http://example.org/fhir\nstatus: draft\nversion: 0.1.0\n"
        )

        return computable_dir

    def test_cql_embedded_when_file_present(self, tmp_repo):
        """Library JSON gets content[].data (base64 CQL) when .cql exists in computable/."""
        import base64

        computable_dir = self._make_measure_topic(tmp_repo)
        cql_source = b"library TestMeasureLogic version '1.0.0'\nusing FHIR version '4.0.1'\n"
        (computable_dir / "TestMeasureLogic.cql").write_bytes(cql_source)

        os.environ["LLM_PROVIDER"] = "stub"
        try:
            runner = CliRunner()
            result = runner.invoke(formalize, ["test-measure", "test-measure"])
            assert result.exit_code == 0, result.output
            assert "Embedded CQL source" in result.output

            lib_files = list(computable_dir.glob("Library-*.json"))
            assert len(lib_files) == 1, "Expected exactly one Library JSON"
            library = json.loads(lib_files[0].read_text())
            content = library.get("content", [])
            cql_items = [c for c in content if c.get("contentType") == "text/cql"]
            assert len(cql_items) == 1, "Expected one text/cql content item"
            decoded = base64.b64decode(cql_items[0]["data"])
            assert decoded == cql_source
        finally:
            os.environ.pop("LLM_PROVIDER", None)

    def test_guidance_note_when_no_cql(self, tmp_repo):
        """Guidance note emitted when no .cql file is present."""
        self._make_measure_topic(tmp_repo)

        os.environ["LLM_PROVIDER"] = "stub"
        try:
            runner = CliRunner()
            result = runner.invoke(formalize, ["test-measure", "test-measure"])
            assert result.exit_code == 0, result.output
            assert "rh-inf-cql" in result.output
            assert "author mode" in result.output

            # Library JSON written but no content[].data for CQL
            lib_files = list((tmp_repo / "topics" / "test-measure" / "computable").glob("Library-*.json"))
            assert len(lib_files) == 1
            library = json.loads(lib_files[0].read_text())
            cql_items = [c for c in library.get("content", []) if c.get("contentType") == "text/cql"]
            assert len(cql_items) == 0
        finally:
            os.environ.pop("LLM_PROVIDER", None)

    def test_cql_not_duplicated_on_rerun(self, tmp_repo):
        """Re-running formalize --force replaces, not appends, the CQL content item."""
        import base64

        computable_dir = self._make_measure_topic(tmp_repo)
        cql_source = b"library TestMeasureLogic version '1.0.0'\n"
        (computable_dir / "TestMeasureLogic.cql").write_bytes(cql_source)

        os.environ["LLM_PROVIDER"] = "stub"
        try:
            runner = CliRunner()
            runner.invoke(formalize, ["test-measure", "test-measure"])
            runner.invoke(formalize, ["test-measure", "test-measure", "--force"])

            lib_files = list(computable_dir.glob("Library-*.json"))
            library = json.loads(lib_files[0].read_text())
            cql_items = [c for c in library.get("content", []) if c.get("contentType") == "text/cql"]
            assert len(cql_items) == 1, "Must not duplicate text/cql content item on re-run"
        finally:
            os.environ.pop("LLM_PROVIDER", None)
