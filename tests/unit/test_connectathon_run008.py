"""Regression coverage for replaying the retained run007 content with the current CLI."""

import importlib.util
import json
from pathlib import Path

from rh_skills.fhir.validate import validate_resource


_BUILDER_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/connectathon/tools/build-breast-cancer-run008.py"
)
_SPEC = importlib.util.spec_from_file_location("connectathon_run008", _BUILDER_PATH)
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


def test_replay_migrates_library_canonical_and_pinned_dependents(tmp_path):
    topic = tmp_path / "topics" / builder.TOPIC
    computable = topic / "computable"
    computable.mkdir(parents=True)
    legacy_url = builder.CANONICAL + "/Library/neoadjuvant-tnbc-oncology-review-recommendation-logic"
    current_url = builder.CANONICAL + "/Library/" + builder.LIBRARY
    library_path = computable / "Library-neoadjuvant-tnbc-oncology-review-recommendation-logic.json"
    builder.write_json(library_path, {
        "resourceType": "Library",
        "id": "neoadjuvant-tnbc-oncology-review-recommendation-logic",
        "name": builder.LIBRARY,
        "url": legacy_url,
        "version": "1.0.0",
        "status": "draft",
        "type": {"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/library-type",
            "code": "logic-library",
        }]},
    })
    for name, reference in [("unpinned", legacy_url), ("pinned", legacy_url + "|1.0.0")]:
        builder.write_json(computable / f"PlanDefinition-{name}.json", {
            "resourceType": "PlanDefinition", "id": name,
            "url": builder.CANONICAL + "/PlanDefinition/" + name,
            "version": "1.0.0", "library": [reference],
        })
    unchanged = {
        "resourceType": "PlanDefinition", "id": "regimen",
        "url": builder.CANONICAL + "/PlanDefinition/regimen", "version": "1.0.0",
    }
    builder.write_json(computable / "PlanDefinition-regimen.json", unchanged)
    builder.write_json(computable / "ValueSet-clinical-tumor-category.json", {
        "resourceType": "ValueSet", "id": "clinical-tumor-category",
        "url": builder.CANONICAL + "/ValueSet/clinical-tumor-category", "version": "1.0.0",
    })
    cql_path = computable / (builder.LIBRARY + ".cql")
    cql_path.write_text(f"library {builder.LIBRARY} version '1.0.0'\n")

    documents = {
        "structured/assessments/assessment/assessment.yaml": {
            "description": "Synthetic diagnostic review",
            "sections": {"items": []},
        },
        "process/formalize-config.yaml": {"version": "1.0.0"},
        "structured/terminologies/concepts/terminology.yaml": {"version": "1.0.0"},
        "structured/decision-tables/decision-table/decision-table.yaml": {"version": "1.0.0"},
        "structured/care-pathways/care-pathway/care-pathway.yaml": {"version": "1.0.0"},
    }
    for relative, value in documents.items():
        target = topic / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        builder.write_yaml(target, value)
    packager = topic / "process/package-workspace/packager.toml"
    packager.parent.mkdir(parents=True)
    packager.write_text('version = "1.0.0"\n')

    builder.version_changed_content(tmp_path)

    library = json.loads(library_path.read_text())
    assert library["url"] == current_url
    assert library["version"] == "1.1.0"
    assert library["id"] == "neoadjuvant-tnbc-oncology-review-recommendation-logic"
    assert validate_resource(library) == []
    for name in ["unpinned", "pinned"]:
        plan = builder.read_json(computable / f"PlanDefinition-{name}.json")
        assert plan["library"] == [current_url + "|1.1.0"]
        assert plan["version"] == "1.1.0"
    assert builder.read_json(computable / "PlanDefinition-regimen.json") == unchanged
    assert f"library {builder.LIBRARY} version '1.1.0'" in cql_path.read_text()

    # Repeating the build phase must preserve the migrated identities.
    first_resources = {path.name: path.read_bytes() for path in computable.glob("*.json")}
    builder.version_changed_content(tmp_path)
    assert {path.name: path.read_bytes() for path in computable.glob("*.json")} == first_resources
