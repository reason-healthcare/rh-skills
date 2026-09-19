#!/usr/bin/env python3
"""Run the real native extractor on source QR inputs and capture its outputs.

The expected extracted-bundle files are never read by this runner. Compare its
manifest separately with verify-sdc-extraction.py.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rh", type=Path, required=True)
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--questionnaire", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    binary = args.rh.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    questionnaire_source = (args.questionnaire or args.oracle_root / "questionnaire.json").resolve()
    questionnaire = out / "questionnaire-input.json"
    questionnaire.write_bytes(questionnaire_source.read_bytes())
    binary_hash = sha(binary)
    cases = []
    for source in sorted((args.oracle_root / "cases").iterdir()):
        if not (source / "bundle.json").is_file():
            continue
        bundle = json.loads((source / "bundle.json").read_text())
        resources = [entry["resource"] for entry in bundle["entry"]]
        responses = [r for r in resources if r["resourceType"] == "QuestionnaireResponse"]
        patients = [r for r in resources if r["resourceType"] == "Patient"]
        encounters = [r for r in resources if r["resourceType"] == "Encounter"]
        if len(responses) > 1 or len(patients) != 1 or len(encounters) != 1:
            raise ValueError(f"Unexpected fixture context: {source.name}")
        case = {"fixtureId": source.name, "inputSha256": sha(source / "bundle.json"), "invoked": False}
        if responses:
            response_path = out / f"{source.name}--response.json"
            save(response_path, responses[0])
            command = [str(binary), "cpg", "extract-questionnaire-observations", "--format", "json",
                       "--questionnaire", str(questionnaire), "--response", str(response_path),
                       "--subject", "Patient/" + patients[0]["id"],
                       "--encounter", "Encounter/" + encounters[0]["id"]]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            raw_path = out / f"{source.name}--raw.json"
            raw_path.write_text(result.stdout)
            envelope = json.loads(result.stdout)
            if envelope.get("ok") is not True:
                raise ValueError(f"Extractor failed: {source.name}: {envelope}")
            payload = envelope["result"]
            if payload["status"] not in ("extracted", "not-invoked"):
                raise ValueError(f"Unknown extraction status: {payload}")
            case.update(command=command, rawPath=raw_path.name, status=payload["status"],
                        invoked=payload["status"] == "extracted")
            if case["invoked"]:
                transaction = payload["transaction"]
                transaction_path = out / f"{source.name}--transaction.json"
                save(transaction_path, transaction)
                case["resultPath"] = transaction_path.name
                # Preserve local entry identity but omit transaction requests.
                bundle["entry"].extend({k: v for k, v in entry.items() if k in ("fullUrl", "resource")}
                                       for entry in transaction.get("entry", []))
            else:
                case["reason"] = payload.get("reason")
        else:
            case["reason"] = "No QuestionnaireResponse; extraction was not invoked"
        data_path = out / f"{source.name}--clinical-data.json"
        save(data_path, bundle)
        case["clinicalDataPath"] = data_path.name
        cases.append(case)
    if sha(binary) != binary_hash:
        raise RuntimeError("Runtime binary changed during capture; rerun against a stable build")
    manifest = {"checkedAt": datetime.now(timezone.utc).isoformat(), "runtimePath": str(binary),
                "runtimeSha256": binary_hash, "questionnaireSource": str(questionnaire_source),
                "questionnairePath": str(questionnaire),
                "questionnaireSha256": sha(questionnaire), "cases": cases}
    save(out / "manifest.json", manifest)
    print(json.dumps({"cases": len(cases), "extracted": sum(c["invoked"] for c in cases),
                      "manifest": str(out / "manifest.json")}))


if __name__ == "__main__":
    main()
