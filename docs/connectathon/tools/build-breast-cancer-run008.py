#!/usr/bin/env python3
"""Reproduce the diagnostic Questionnaire addition from an immutable run007 workspace.

Run with rh-skills' Python environment. This authors a new workspace, invokes the
actual formalize/package/compose commands, and leaves run007 untouched. Pass
--phase prepare, build, or snapshot to inspect each boundary before continuing.
"""

from __future__ import annotations

import argparse
import base64
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from ruamel.yaml import YAML

REPO = Path(__file__).resolve().parents[3]
TOPIC = "breast-cancer-neoadjuvant-review"
LIBRARY = "NeoadjuvantTnbcOncologyReviewRecommendationLogic"
CANONICAL = "https://reason-healthcare.github.io/hl7-agentic-knowledge-connectathon/fhir"
LOINC = "http://loinc.org"
LOCAL = CANONICAL + "/CodeSystem/breast-cancer-fixture"
Q_ID = "breast-cancer-pretreatment-diagnostic-review"
Q_IDENTITY = CANONICAL + "/Questionnaire/" + Q_ID + "|1.1.0"
EVALUATION_DATE = "2026-09-20T00:00:00Z"
SDC_PROFILE = "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn|4.0.0"
QUESTIONS = {
    "estrogen-receptor": ("85337-4", "Estrogen receptor Ag [Presence] in Breast cancer specimen by Immune stain"),
    "progesterone-receptor": ("85339-0", "Progesterone receptor Ag [Presence] in Breast cancer specimen by Immune stain"),
    "her2": ("48676-1", "HER2 [Interpretation] in Tissue"),
    "clinical-t": ("21905-5", "Primary tumor.clinical [Class] Cancer"),
    "clinical-n": ("21906-3", "Regional lymph nodes.clinical [Class] Cancer"),
    "clinical-m": ("21907-1", "Distant metastases.clinical [Class] Cancer"),
}
STAGE_ANSWERS = {
    "cT1mi": "LA21854-7", "cT1a": "LA3636-3", "cT1b": "LA3633-0",
    "cT1c": "LA3630-6", "cT2": "LA3628-0", "cT3": "LA3624-9", "cT4": "LA3620-7",
    "cN0": "LA4368-2", "cN1": "LA4537-2", "cN2": "LA4534-9", "cN3": "LA4545-5",
    "cM0": "LA4629-7", "cM1": "LA4628-9",
}
ANSWER_DISPLAYS = {
    "LA6577-6": "Negative", "LA6576-8": "Positive",
    "LA11885-3": "Equivocal", "LA11884-6": "Indeterminate",
    **{value: key[1:] for key, value in STAGE_ANSWERS.items()},
}
yaml = YAML()
yaml.width = 100


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def write_yaml(path, value):
    with path.open("w") as stream:
        yaml.dump(value, stream)


def code(value, display, version=None):
    result = {"system": LOINC, "code": value, "display": display}
    if version:
        result["version"] = version
    return result


def category(value):
    return {"system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": value, "display": value.capitalize()}


def run(workspace, arguments, log):
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    command = [str(REPO / ".venv/bin/rh-skills"), *arguments]
    result = subprocess.run(command, cwd=workspace, env=env, text=True, capture_output=True)
    (workspace / "evidence" / log).write_text("$ " + " ".join(command) + "\n" + result.stdout + result.stderr)
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}")


def prepare(source, workspace):
    if workspace.exists():
        raise RuntimeError(f"Refusing to overwrite existing workspace {workspace}")
    shutil.copytree(source, workspace)
    # Copied run007 evidence stays identifiable and cannot be mistaken for run008 tests.
    (workspace / "evidence").rename(workspace / "evidence-run007")
    (workspace / "evidence").mkdir()
    config = workspace / ".rh-skills.toml"
    config.write_text(config.read_text().replace(str(source), str(workspace)))
    topic = workspace / "topics" / TOPIC
    assessment_path = topic / "structured/assessments/assessment/assessment.yaml"
    assessment = yaml.load(assessment_path)
    assessment.update({"title": "Breast cancer pretreatment diagnostic review", "version": "1.1.0",
        "description": "Clinician-entered diagnostic review with coded answers and SDC Observation extraction. "
                       "The clinician records established receptor interpretations and clinical stage; missing or unresolved results remain unknown."})
    assessment["sections"]["summary"] = (
        "Record ER, PR, HER2, clinical T, N and M using the coded Questionnaire. "
        "A completed, valid response extracts clinical Observations; the runtime must supply the explicitly selected cancer focus. "
        "CQL continues to consume final, non-future Observations focused on the indexed cancer. "
        "Incomplete responses do not extract and do not create negative findings.")
    instrument = assessment["sections"]["instrument"]
    instrument.update({"id": Q_ID, "canonical": CANONICAL + "/Questionnaire/" + Q_ID,
        "version": "1.1.0", "version_algorithm": {"system": "http://hl7.org/fhir/version-algorithm", "code": "semver"},
        "purpose": "Record established pretreatment diagnostic results for extraction to clinical Observations.",
        "observation_extraction": {"profile": SDC_PROFILE, "enabled": True, "category": category("exam")}})
    for item in assessment["sections"]["items"]:
        question_code, display = QUESTIONS[item["id"]]
        item["code"] = code(question_code, display, "2.81")
        if item["id"].startswith("clinical-"):
            prefix = "c" + item["id"][-1].upper()
            values = [value for key, value in STAGE_ANSWERS.items() if key.startswith(prefix)]
            item["observation_extraction"] = {"category": category("exam")}
        else:
            values = ["LA6577-6", "LA6576-8", "LA11884-6"]
            if item["id"] == "her2":
                values.insert(2, "LA11885-3")
            item["observation_extraction"] = {"category": category("laboratory")}
        item["options"] = [{"valueCoding": code(value, ANSWER_DISPLAYS[value])} for value in values]
    assessment["concerns"] = [{"issue": "Run007 excluded the assessment Questionnaire",
        "positions": [{"source": "User direction 2026-09-20", "statement": "Create the question artifact in all cases, with coding so SDC extraction produces Observation answers."}],
        "preferred_interpretation": {"source": "User direction 2026-09-20", "rationale": "Clinician-entered diagnostic data are represented by a coded Questionnaire; extracted Observations retain their clinical categories and provenance."}}]
    write_yaml(assessment_path, assessment)
    plan_path = topic / "process/plans/formalize-plan.yaml"
    plan = yaml.load(plan_path)
    for artifact in plan["artifacts"]:
        if artifact.get("source_artifact") == "assessment":
            artifact.update({"reviewer_decision": "approved", "implementation_target": False,
                "approval_notes": "User direction 2026-09-20 supersedes run007 exclusion: formalize coded clinical assessment with SDC Observation extraction."})
    write_yaml(plan_path, plan)
    terminology_path = topic / "structured/terminologies/concepts/terminology.yaml"
    terminology = yaml.load(terminology_path)
    stage_sets = {"clinical-tumor-category": "clinical-t", "clinical-node-category": "clinical-n",
                  "clinical-metastasis-category": "clinical-m", "distant-metastasis-assessment": "clinical-m"}
    for concept in terminology["concepts"]:
        if concept["id"] in stage_sets:
            loinc_code, display = QUESTIONS[stage_sets[concept["id"]]]
            concept["codes"].append(code(loinc_code, display, "2.81"))
            concept["context"] = "Includes standardized clinical-stage question code plus legacy test-only local fixture code; no dual coding or unreviewed equivalence is asserted."
    write_yaml(terminology_path, terminology)
    for name, question in stage_sets.items():
        loinc_code, display = QUESTIONS[question]
        csv_path = topic / "process/plans/concepts" / (name + ".csv")
        with csv_path.open("a", newline="") as stream:
            csv.writer(stream).writerow(["include", LOINC, loinc_code, display, "2.81", "0.0", "high", "candidate", "", "",
                "Run008 ReasonHub exact lookup confirmed active; standardized clinical-stage question. Legacy local fixture code remains test-only."])
        # Preserve run007 resource identity while authoring the reviewed added membership.
        vs_path = topic / "computable" / ("ValueSet-" + name + ".json")
        value_set = read_json(vs_path)
        value_set["compose"]["include"].append({"system": LOINC, "version": "2.81", "concept": [{"code": loinc_code, "display": display}]})
        value_set["expansion"]["contains"].append(code(loinc_code, display, "2.81"))
        value_set["expansion"]["total"] = len(value_set["expansion"]["contains"])
        value_set["expansion"]["timestamp"] = EVALUATION_DATE
        value_set["experimental"] = True
        value_set["description"] = "Clinical-stage question codes. Legacy local code is retained only for synthetic fixture compatibility."
        write_json(vs_path, value_set)
    cql_path = topic / "computable" / (LIBRARY + ".cql")
    cql = cql_path.read_text()
    declarations = "\n".join(f'code "LOINC {key}": \'{value}\' from "LOINC" display \'{ANSWER_DISPLAYS[value]}\'' for key, value in STAGE_ANSWERS.items())
    cql = cql.replace("context Patient", declarations + "\n\ncontext Patient")
    for key in STAGE_ANSWERS:
        pattern = r'\(("Clinical [TMN] Result")\.value as FHIR\.CodeableConcept\) ~ "' + re.escape(key) + '"'
        cql = re.sub(pattern, lambda match: '(' + match.group(0) + '\n    or (' + match.group(1) + '.value as FHIR.CodeableConcept) ~ "LOINC ' + key + '")', cql)
    cql_path.write_text(cql)
    write_json(workspace / "tests/cql/breast-cancer-terminology.json", {
        "resourceType": "Bundle", "type": "collection",
        "entry": [{"resource": read_json(path)} for path in sorted((topic / "computable").glob("ValueSet-*.json"))]})
    evidence = REPO / "docs/connectathon/evidence/breast-cancer-run008-terminology.json"
    if evidence.exists():
        shutil.copyfile(evidence, workspace / "evidence/terminology-run008.json")
    (workspace / "evidence/cql-pattern-selection.md").write_text(
        "# Run008 CQL pattern selection\n\n"
        "Consulted https://build.fhir.org/ig/cqframework/cms-qmd/branches/main/pattern_index.html and pattern_observations.html on 2026-09-20. "
        "Laboratory Result and Clinical Result patterns apply. The existing FHIR R4 4.0.1/FHIRCommon 2.0.0 library retains typed ValueSet retrieval, final status, effective-time and indexed-cancer focus. "
        "The current CMS examples use newer US Quality Core profiles/helpers, so run008 preserves their coded-result/status intent in the pinned baseline. "
        "Only coded staging answer comparisons are broadened to explicit LOINC LA choices; legacy fixture code comparisons and unknown behavior are preserved. "
        "No QuestionnaireResponse is retrieved by clinical CQL.\n")
    print(f"Prepared {workspace}")


def add_qr_fixtures(workspace):
    topic = workspace / "topics" / TOPIC
    fixtures = topic / "process/package-workspace/executable/fixtures"
    index = read_json(fixtures / "index.json")
    originals = copy.deepcopy(index["fixtures"])
    evidence = []
    for fixture in originals:
        original = read_json(fixtures / (fixture["id"] + ".json"))
        retained, answers, removed = [], [], []
        for entry in original["entry"]:
            resource = entry["resource"]
            item_id = None
            if resource["resourceType"] == "Observation":
                for coding in resource.get("code", {}).get("coding", []):
                    for key, (value, _) in QUESTIONS.items():
                        if (coding.get("system") == LOINC and coding.get("code") == value) or (coding.get("system") == LOCAL and coding.get("code") == key):
                            item_id = key
            if item_id:
                value = resource["valueCodeableConcept"]["coding"][0]
                if value["system"] == LOCAL:
                    answer_code = {**STAGE_ANSWERS, "equivocal": "LA11885-3", "indeterminate": "LA11884-6"}[value["code"]]
                else:
                    answer_code = value["code"]
                answers.append({"linkId": item_id, "text": next(item["text"] for item in yaml.load(topic / "structured/assessments/assessment/assessment.yaml")["sections"]["items"] if item["id"] == item_id),
                    "answer": [{"valueCoding": code(answer_code, ANSWER_DISPLAYS[answer_code])}]})
                removed.append(resource["id"])
            else:
                retained.append(entry)
        is_complete = len(answers) == 6
        qr_id = "qr-" + fixture["id"]
        practitioner = {"resourceType": "Practitioner", "id": "synthetic-diagnostic-reviewer",
            "active": True, "name": [{"family": "Synthetic", "given": ["Diagnostic reviewer"]}]}
        retained.append({"fullUrl": CANONICAL + "/Practitioner/" + practitioner["id"], "resource": practitioner})
        encounter = {"resourceType": "Encounter", "id": "diagnostic-review-" + fixture["id"],
            "status": "finished", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
            "subject": {"reference": fixture["subject"]},
            "participant": [{"individual": {"reference": "Practitioner/" + practitioner["id"]}}],
            "period": {"start": "2026-06-02T09:00:00Z", "end": "2026-06-02T11:00:00Z"}}
        retained.append({"fullUrl": CANONICAL + "/Encounter/" + encounter["id"], "resource": encounter})
        qr = {"resourceType": "QuestionnaireResponse", "id": qr_id,
            "questionnaire": Q_IDENTITY, "status": "completed" if is_complete else "in-progress",
            "subject": {"reference": fixture["subject"]}, "encounter": {"reference": "Encounter/" + encounter["id"]},
            "author": {"reference": "Practitioner/" + practitioner["id"]},
            "authored": "2026-06-02T10:00:00Z", "item": answers}
        bundle = copy.deepcopy(original)
        bundle["id"] = "bundle-" + qr_id
        bundle["identifier"] = {"system": CANONICAL + "/fixture", "value": TOPIC + "/" + qr_id}
        bundle["entry"] = retained + [{"fullUrl": CANONICAL + "/QuestionnaireResponse/" + qr_id, "resource": qr}]
        write_json(fixtures / (qr_id + ".json"), bundle)
        new_fixture = copy.deepcopy(fixture)
        new_fixture.update({"id": qr_id, "title": "Questionnaire: " + fixture["title"],
            "dataBundlePath": "fixtures/" + qr_id + ".json",
            "description": "Synthetic diagnostic QuestionnaireResponse input. Matching receptor/staging Observations removed; diagnosis and tumor size retained. " + ("Completed coded answers extract to clinical Observations." if is_complete else "Incomplete response: zero extracted Observations; missing data remains unknown.")})
        condition = next((entry["resource"] for entry in retained if entry["resource"]["resourceType"] == "Condition"), None)
        if condition:
            new_fixture["parameters"] = {"sdcObservationFocus": [{"reference": "Condition/" + condition["id"]}]}
        index["fixtures"].append(new_fixture)
        assertions = read_json(workspace / "process/fixtures/cases" / fixture["id"] / "assertions.json")
        expected = {item["expression"]: item["expected"]["value"] for item in assertions["assertions"]}
        if not is_complete:
            expected = {key: (True if key == "Has Active Confirmed Invasive Breast Cancer" else None) for key in expected}
        evidence.append({"fixtureId": qr_id, "sourceFixture": fixture["id"], "removedObservationIds": removed,
            "expectedExtractionCount": 6 if is_complete else 0, "expectedExpressions": expected,
            "focus": new_fixture.get("parameters", {}).get("sdcObservationFocus", [])})
    write_json(fixtures / "index.json", index)
    write_json(workspace / "evidence/questionnaire-fixture-contract.json", {"questionnaire": Q_IDENTITY, "fixtures": evidence,
        "answerCorrection": "Legacy local equivocal maps in the QR case to verified LOINC LA11885-3 Equivocal; original fixture remains unchanged. Any LA11884-6 answer uses its official Indeterminate meaning."})
    print(f"Prepared {len(evidence)} QR scenarios plus {len(originals)} original Observation scenarios")


def version_changed_content(workspace):
    """Give every changed canonical new identity; keep original regimen/helper identities."""
    topic = workspace / "topics" / TOPIC
    computable = topic / "computable"
    assessment_path = topic / "structured/assessments/assessment/assessment.yaml"
    assessment = yaml.load(assessment_path)
    for item in assessment["sections"]["items"]:
        if item["id"] in ("estrogen-receptor", "progesterone-receptor"):
            item["options"] = [option for option in item["options"] if option["valueCoding"]["code"] != "LA11885-3"]
    scope_note = " Draft educational scope: available clinical-stage choices cover the demonstrated decision criterion."
    assessment["description"] = assessment["description"].replace(scope_note, "") + scope_note
    write_yaml(assessment_path, assessment)
    changed_vs = {"clinical-tumor-category", "clinical-node-category",
                  "clinical-metastasis-category", "distant-metastasis-assessment"}
    legacy_logic_url = CANONICAL + "/Library/neoadjuvant-tnbc-oncology-review-recommendation-logic"
    logic_url = CANONICAL + "/Library/" + LIBRARY
    logic_urls = {legacy_logic_url, logic_url}
    resources = {path: read_json(path) for path in computable.glob("*.json")}
    changed_urls = {resource["url"] for resource in resources.values()
        if resource.get("id") in changed_vs or resource.get("url") in logic_urls
        or any(reference.split("|")[0] in logic_urls for reference in resource.get("library", []))}
    def pin(value):
        if isinstance(value, str):
            canonical = value.split("|")[0]
            if canonical in changed_urls:
                # Current CQL identity validation uses the declared Library.name
                # in its canonical. Rewrite dependents with the same migration.
                return (logic_url if canonical in logic_urls else canonical) + "|1.1.0"
            return value
        if isinstance(value, list):
            return [pin(item) for item in value]
        if isinstance(value, dict):
            return {key: item if key == "url" else pin(item) for key, item in value.items()}
        return value
    for path, resource in resources.items():
        if resource.get("url") in changed_urls:
            resource = pin(resource)
            if resource["url"] in logic_urls:
                resource["url"] = logic_url
            resource["version"] = "1.1.0"
            resource["date"] = "2026-09-20"
            write_json(path, resource)
    cql_path = computable / (LIBRARY + ".cql")
    cql = cql_path.read_text().replace("library " + LIBRARY + " version '1.0.0'", "library " + LIBRARY + " version '1.1.0'")
    for name in changed_vs:
        cql = cql.replace("/ValueSet/" + name + "' version '1.0.0'", "/ValueSet/" + name + "' version '1.1.0'")
    cql_path.write_text(cql)
    for relative in ["process/formalize-config.yaml", "structured/terminologies/concepts/terminology.yaml",
                     "structured/decision-tables/decision-table/decision-table.yaml", "structured/care-pathways/care-pathway/care-pathway.yaml"]:
        target = topic / relative
        document = yaml.load(target)
        document["version"] = "1.1.0"
        write_yaml(target, document)
    packager = topic / "process/package-workspace/packager.toml"
    packager.write_text(re.sub(r'(?m)^version = "1.0.0"$', 'version = "1.1.0"', packager.read_text()))
    write_json(workspace / "tests/cql/breast-cancer-terminology.json", {
        "resourceType": "Bundle", "type": "collection",
        "entry": [{"resource": read_json(path)} for path in sorted(computable.glob("ValueSet-*.json"))]})


def build(workspace):
    version_changed_content(workspace)
    run(workspace, ["formalize", TOPIC, "assessment", "--force"], "formalize-assessment.log")
    run(workspace, ["cql", "validate", TOPIC, LIBRARY], "cql-validate.log")
    run(workspace, ["cql", "translate", TOPIC, LIBRARY], "cql-translate.log")
    # CLI translation emits ELM; packaging synchronizes its exact generated bytes
    # and authored CQL into the existing FHIR Library wrapper.
    computable = workspace / "topics" / TOPIC / "computable"
    library_path = computable / "Library-neoadjuvant-tnbc-oncology-review-recommendation-logic.json"
    library = read_json(library_path)
    library["content"] = [
        {"contentType": "text/cql", "data": base64.b64encode((computable / (LIBRARY + ".cql")).read_bytes()).decode()},
        {"contentType": "application/elm+json", "data": base64.b64encode((computable / "elm" / (LIBRARY + ".json")).read_bytes()).decode()},
    ]
    write_json(library_path, library)
    run(workspace, ["package", TOPIC, "--pack"], "package.log")
    run(workspace, ["compose-executable", TOPIC, "--root-canonical", CANONICAL + "/PlanDefinition/neoadjuvant-tnbc-oncology-review-pathway-protocol|1.1.0",
        "--fixture-manifest", str(workspace / "process/fixtures/manifest.json"), "--fixture-dir", str(workspace / "process/fixtures/cases"),
        "--evaluation-date", EVALUATION_DATE], "compose-executable.log")
    add_qr_fixtures(workspace)


def snapshot(workspace, workbench):
    out = REPO / "dist/connectathon-20260920/snapshots"
    topic = workspace / "topics" / TOPIC
    hasher = hashlib.sha256()
    paths = [workspace / "tracking.yaml", topic / "TOPIC.md"]
    for directory in [workspace / "sources/normalized", topic / "structured", topic / "computable",
                      topic / "process/package-workspace/output", topic / "process/package-workspace/executable",
                      topic / "process/review"]:
        if directory.exists():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    for path in sorted(paths):
        hasher.update(str(path.relative_to(workspace)).encode())
        hasher.update(path.read_bytes())
    digest = hasher.hexdigest()[:10]
    source_commit = "run008-" + digest
    root = out / ("connectathon-breast-cancer-" + source_commit + "-snapshot")
    if root.exists():
        raise RuntimeError(f"Refusing to replace existing snapshot {root}")
    command = ["node", "scripts/build-aao-snapshot.mjs", "--workspace", str(workspace), "--topic", TOPIC,
        "--project-id", "connectathon-breast-cancer", "--project-title", "Connectathon Breast Cancer",
        "--topic-title", "Breast cancer neoadjuvant review", "--customer", "Reason Healthcare",
        "--source-commit", source_commit, "--created-at", EVALUATION_DATE,
        "--label", "008 · Coded diagnostic questionnaire", "--out", str(out)]
    result = subprocess.run(command, cwd=workbench, text=True, capture_output=True, check=True)
    (workspace / "evidence/snapshot-build.log").write_text(result.stdout + result.stderr)
    print(result.stdout)
    write_json(workspace / "evidence/snapshot-location.json", {"path": str(root), "zip": str(root) + ".zip", "id": "snap_connectathon-breast-cancer_" + source_commit,
        "workspaceContentSha256": hasher.hexdigest(), "hashedInputs": [str(path.relative_to(workspace)) for path in sorted(paths)]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--workbench", type=Path, default=REPO.parent / "workbench")
    parser.add_argument("--phase", choices=["prepare", "build", "snapshot"], required=True)
    args = parser.parse_args()
    source, workspace = args.source.resolve(), args.workspace.resolve()
    if source == workspace or source in workspace.parents:
        parser.error("The run008 workspace must be separate from immutable run007")
    if args.phase == "prepare":
        prepare(source, workspace)
    elif args.phase == "build":
        build(workspace)
    else:
        snapshot(workspace, args.workbench.resolve())


if __name__ == "__main__":
    main()
