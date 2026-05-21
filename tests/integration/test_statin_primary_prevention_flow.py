"""End-to-end orchestration test for a fresh statin topic."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.cql import cql
from rh_skills.commands.formalize import formalize
from rh_skills.commands.init import init
from rh_skills.commands.package import package


def _write_tracking_artifact(tmp_repo: Path, topic: str, artifact: str) -> None:
    y = YAML()
    y.default_flow_style = False
    tracking_path = tmp_repo / "tracking.yaml"
    with open(tracking_path) as f:
        tracking = y.load(f)
    topic_entry = next(t for t in tracking["topics"] if t["name"] == topic)
    topic_entry["structured"].append({
        "name": artifact,
        "artifact_type": "decision-table",
        "status": "approved",
        "file": f"topics/{topic}/structured/{artifact}.yaml",
    })
    with open(tracking_path, "w") as f:
        y.dump(tracking, f)


def test_statin_primary_prevention_flow(tmp_repo, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    runner = CliRunner()

    topic = "statin-primary-prevention"
    artifact = "statin-eligibility"

    result = runner.invoke(init, [topic])
    assert result.exit_code == 0, result.output

    topic_dir = tmp_repo / "topics" / topic
    structured_dir = topic_dir / "structured"
    structured_dir.mkdir(parents=True, exist_ok=True)
    (structured_dir / f"{artifact}.yaml").write_text(
        """\
artifact_type: decision-table
name: statin-eligibility
title: "Statin Eligibility"
version: "1.0.0"
status: draft
domain: cardiology
description: "Decision support for primary prevention statin eligibility."
derived_from:
  - uspstf-statin
sections:
  summary: "Adults at elevated ASCVD risk may benefit from statin therapy."
  conditions:
    - id: elevated-risk
      label: Elevated ASCVD risk
      values: ["yes", "no"]
"""
    )
    _write_tracking_artifact(tmp_repo, topic, artifact)

    process_dir = topic_dir / "process"
    process_dir.mkdir(parents=True, exist_ok=True)
    (process_dir / "formalize-config.yaml").write_text(
        "name: StatinPrimaryPrevention\n"
        f"id: {topic}\n"
        "canonical: https://example.org/fhir\n"
        "status: draft\n"
        "version: 0.1.0\n"
    )
    plans_dir = process_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / "formalize-plan.yaml").write_text(
        f"topic: {topic}\n"
        "plan_type: formalize\n"
        "status: approved\n"
        "artifacts:\n"
        f"  - name: {artifact}\n"
        "    artifact_type: decision-table\n"
        "    strategy: decision-table\n"
        "    input_artifacts:\n"
        f"      - {artifact}\n"
        "    l3_targets:\n"
        "      - PlanDefinition\n"
        "      - Library\n"
        "    reviewer_decision: approved\n"
        "    implementation_target: true\n"
    )

    result = runner.invoke(formalize, [topic, artifact])
    assert result.exit_code == 0, result.output

    computable_dir = topic_dir / "computable"
    library_json = next(computable_dir.glob("Library-*.json"))
    library_resource = json.loads(library_json.read_text())
    library_name = library_resource["name"]
    cql_file = computable_dir / f"{library_name}.cql"
    cql_file.write_text(
        f"library {library_name} version '0.1.0'\n"
        "using FHIR version '4.0.1'\n"
        "context Patient\n"
        "define IsAdult: true\n"
    )

    result = runner.invoke(formalize, [topic, artifact, "--force"])
    assert result.exit_code == 0, result.output
    library_resource = json.loads(library_json.read_text())
    assert any(item.get("contentType") == "text/cql" for item in library_resource.get("content", []))

    case_dir = tmp_repo / "tests" / "cql" / library_name / "case-001-basic-positive"
    (case_dir / "input").mkdir(parents=True, exist_ok=True)
    (case_dir / "expected").mkdir(parents=True, exist_ok=True)
    (case_dir / "input" / "bundle.json").write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": []})
    )
    (case_dir / "expected" / "expression-results.json").write_text(json.dumps({"IsAdult": True}))

    monkeypatch.setenv("RH_CLI_PATH", "/fake/rh")

    def fake_cql_run(args, capture_output=False, text=False):
        if args[1:3] == ["cql", "validate"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[1:3] == ["cql", "compile"]:
            output_path = Path(args[-1])
            output_path.write_text("{}")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[1:3] == ["cql", "eval"]:
            return SimpleNamespace(returncode=0, stdout="true\n", stderr="")
        raise AssertionError(f"Unexpected cql subprocess call: {args}")

    monkeypatch.setattr("rh_skills.commands.cql.subprocess.run", fake_cql_run)

    result = runner.invoke(cql, ["validate", topic, library_name])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cql, ["translate", topic, library_name])
    assert result.exit_code == 0, result.output
    assert (computable_dir / f"{library_name}.json").exists()

    result = runner.invoke(cql, ["test", topic, library_name])
    assert result.exit_code == 0, result.output
    assert "PASS IsAdult" in result.output

    monkeypatch.setattr("rh_skills.commands.package._resolve_rh_binary", lambda: "/fake/rh")
    monkeypatch.setattr(
        "rh_skills.commands.package._run_rh_command",
        lambda args: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    result = runner.invoke(package, [topic])
    assert result.exit_code == 0, result.output
    assert "package_created" in result.output
    assert (topic_dir / "process" / "package-workspace" / "packager.toml").exists()
