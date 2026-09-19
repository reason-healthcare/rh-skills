#!/usr/bin/env python3
"""Compare captured extraction results with the immutable Connectathon oracle.

Manifest: {"cases": [{"fixtureId": "...", "invoked": true,
"resultPath": "path/to/transaction-bundle.json"}, ...]}.
Paths are relative to the manifest. A non-invoked case may omit resultPath.
This verifies captured output; the caller must separately record how it ran
the extractor and the exact runtime/input hashes.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantics(resource):
    # Resource ids, fullUrls and request verbs are deliberately not oracle
    # identities. Code versions and copied provenance ARE part of the contract.
    fields = (
        "resourceType", "status", "category", "code", "subject", "encounter",
        "effectiveDateTime", "issued", "performer", "valueBoolean", "derivedFrom",
    )
    result = {key: resource.get(key) for key in fields}
    result["security"] = resource.get("meta", {}).get("security", [])
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    cases = json.loads(manifest.read_text())["cases"]
    by_id = {case["fixtureId"]: case for case in cases}
    expected_ids = {p.name for p in (args.oracle_root / "cases").iterdir()
                    if (p / "assertions.json").is_file()}
    if len(by_id) != len(cases) or set(by_id) != expected_ids:
        raise ValueError("Manifest must contain exactly the original six cases")
    results = []
    for fixture_id in sorted(expected_ids):
        item = by_id[fixture_id]
        source = args.oracle_root / "cases" / fixture_id
        assertions = json.loads((source / "assertions.json").read_text())
        oracle = assertions["sdcExtraction"]
        expected_file = source / oracle["expectedResourceSet"]
        expected = json.loads(expected_file.read_text()).get("entry", [])
        result_path = (manifest.parent / item["resultPath"]).resolve() if item.get("resultPath") else None
        actual = json.loads(result_path.read_text()) if result_path else None
        entries = actual.get("entry", []) if actual else []
        resources = [entry.get("resource", {}) for entry in entries]
        checks = {
            "invocation": type(item.get("invoked")) is bool and item["invoked"] == oracle["invocationExpected"],
            "count": len(resources) == oracle["expectedObservationCount"],
            "semantics": Counter(map(semantics, resources)) == Counter(semantics(e["resource"]) for e in expected),
            "booleanValues": all(type(r.get("valueBoolean")) is bool for r in resources),
            "transaction": (actual is not None and actual.get("resourceType") == "Bundle" and actual.get("type") == "transaction") if item["invoked"] else not entries,
            "transactionRequests": all(e.get("request", {}).get("method") in ("POST", "PUT") and bool(e.get("request", {}).get("url")) for e in entries),
            "uniquePresentResourceIds": len({r["id"] for r in resources if r.get("id")}) == sum(bool(r.get("id")) for r in resources),
            "transactionEntryIdentities": all(e.get("fullUrl") for e in entries) and len({e["fullUrl"] for e in entries}) == len(entries),
        }
        results.append({"fixtureId": fixture_id, "passed": all(checks.values()), "checks": checks,
                        "inputSha256": digest(source / "bundle.json"),
                        "oracleSha256": digest(expected_file),
                        "actualPath": str(result_path) if result_path else None,
                        "actualSha256": digest(result_path) if result_path else None})
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(),
              "scope": "Independent comparison of captured extraction output against unchanged source oracle; no independent engine claim",
              "manifestSha256": digest(manifest), "passed": all(r["passed"] for r in results), "cases": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "cases": len(results), "output": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
