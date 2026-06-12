from click.testing import CliRunner
from ruamel.yaml import YAML

from rh_skills.commands.promote import promote
from rh_skills.commands.validate import validate


def _load_yaml(path):
    y = YAML()
    with open(path) as f:
        return y.load(f)


def test_derive_pathway_emits_flat_steps_with_parent_id_and_validates(tmp_repo, monkeypatch):
    topic = "my-topic"
    structured_dir = tmp_repo / "topics" / topic / "structured" / "decision-table"
    structured_dir.mkdir(parents=True, exist_ok=True)
    (structured_dir / "decision-table.yaml").write_text(
        """\
id: decision-table
name: decision-table
title: "Chronic Rhinosinusitis Decision Table"
version: "1.0.0"
status: draft
domain: ent
description: "Decision table with pathway phases."
derived_from:
  - source-l1
artifact_type: decision-table
clinical_question: "What recommendations apply?"
sections:
  summary: "Summary"
  pathway_phases:
    - id: assessment
      label: Assessment
      description: Assess diagnosis and baseline status
    - id: planning
      label: Planning
      description: Determine candidacy and next steps
  evidence_traceability:
    - claim_id: claim-001
      statement: "Assessment precedes planning"
      evidence:
        - source: source-l1
          locator: "Section 1"
  events:
    - id: verify-diagnosis
      label: Verify diagnosis
      phase: assessment
    - id: assess-candidacy
      label: Assess candidacy
      phase: planning
  conditions:
    - id: confirmed
      label: Confirmed
      values: [Yes, No]
  data_elements:
    - id: de-001
      condition_id: confirmed
      label: Confirmation data
  actions:
    - id: act-001
      label: Verify diagnosis
      kind: ServiceRequest
  rules:
    - id: rule-001
      event: verify-diagnosis
      then: [act-001]
      action: Verify diagnosis
      evidence_traceability_ids: [claim-001]
concerns: []
"""
    )

    monkeypatch.chdir(tmp_repo)
    runner = CliRunner()
    result = runner.invoke(promote, ["derive", "pathway", "--from-decision-table", "decision-table"])
    assert result.exit_code == 0, result.output
    assert "flat steps[] with parent_id" in result.output
    assert "fallback scaffold for recommendation-to-pathway alignment repair" in result.output

    pathway_file = tmp_repo / "topics" / topic / "structured" / "decision-table-pathway" / "decision-table-pathway.yaml"
    artifact = _load_yaml(pathway_file)
    steps = artifact["sections"]["steps"]

    assert [step["id"] for step in steps] == ["decision-table-pathway", "assessment", "planning"]
    assert "substeps" not in steps[0]
    assert steps[1]["parent_id"] == "decision-table-pathway"
    assert steps[2]["parent_id"] == "decision-table-pathway"
    assert artifact["sections"]["transitions"][0]["from_id"] == "assessment"
    assert artifact["sections"]["transitions"][0]["to_id"] == "planning"

    validate_result = runner.invoke(validate, [topic, "decision-table-pathway"])
    assert validate_result.exit_code == 0, validate_result.output
