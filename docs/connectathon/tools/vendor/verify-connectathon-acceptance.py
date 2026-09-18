#!/usr/bin/env python3
"""Roll up concrete Connectathon evidence without masking unsupported gates.

Every core report is required and independently checked. Optional full-track
claims are reported as explicitly unsupported unless a caller supplies a report
whose `supported` field is true. The command exits nonzero only when a required
core input is absent or fails.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def nested_count_ok(report: dict[str, Any]) -> bool:
    counts = report.get("counts", {})
    if not isinstance(counts, dict):
        return False
    if all(isinstance(counts.get(key), int) for key in ("total", "passed")):
        return counts["total"] > 0 and counts["passed"] == counts["total"] and counts.get("failed", 0) == 0
    segments = [value for value in counts.values() if isinstance(value, dict)]
    return bool(segments) and all(
        isinstance(item.get("total"), int)
        and isinstance(item.get("passed"), int)
        and item["total"] > 0
        and item["passed"] == item["total"]
        and item.get("failed", 0) == 0
        for item in segments
    )


def operation_outcome_ok(report: dict[str, Any]) -> bool:
    if report.get("resourceType") != "OperationOutcome":
        return False
    return not any(issue.get("severity") in {"error", "fatal"} for issue in report.get("issue", []))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parity", required=True, help="standalone API parity report")
    parser.add_argument("--native", required=True, help="native 96-case report")
    parser.add_argument("--node", required=True, help="public Node/WASM one-hot report")
    parser.add_argument("--run002", required=True, help="portable CQL run-002 report")
    parser.add_argument("--validation", required=True, help="resolved FHIR validator OperationOutcome")
    parser.add_argument("--package-loader", required=True, help="TGZ/knowledge-content boundary inspection")
    parser.add_argument("--output", required=True, help="output acceptance JSON")
    parser.add_argument(
        "--unsupported-gate",
        action="append",
        default=[],
        metavar="NAME=REASON",
        help="full-track gate deliberately outside this acceptance command",
    )
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    parity = load(args.parity)
    parity_counts = parity.get("counts", {})
    parity_ok = (
        parity.get("sourceFixturesUnchanged") is True
        and parity_counts.get("total") == 6
        and parity_counts.get("parityPassed") == 6
        and parity_counts.get("semanticPassed") == 6
    )
    checks.append({"name": "standalone-api-parity", "path": args.parity, "passed": parity_ok, "detail": parity_counts})

    for name, path in (("native-cql", args.native), ("public-node-wasm", args.node), ("portable-run002-cql", args.run002)):
        report = load(path)
        checks.append({"name": name, "path": path, "passed": nested_count_ok(report), "detail": report.get("counts")})

    validation = load(args.validation)
    checks.append({"name": "resolved-fhir-validation", "path": args.validation, "passed": operation_outcome_ok(validation), "detail": {"issues": len(validation.get("issue", []))}})

    loader = load(args.package_loader)
    loader_ok = (
        loader.get("packageExampleBundleCount") == 6
        and loader.get("executableBundleResourceCount") == 0
        and loader.get("testResult") == "passed (1 test)"
    )
    checks.append({"name": "package-fixture-knowledge-boundary", "path": args.package_loader, "passed": loader_ok, "detail": {key: loader.get(key) for key in ("packageExampleBundleCount", "executableBundleResourceCount", "testResult")}})

    unsupported: list[dict[str, str]] = []
    for value in args.unsupported_gate:
        name, separator, reason = value.partition("=")
        if not separator or not name or not reason:
            parser.error("--unsupported-gate must be NAME=REASON")
        unsupported.append({"name": name, "status": "unsupported", "reason": reason})

    report = {
        "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "Required local FHIR package validation and runtime execution evidence. Unsupported full-track gates are reported separately and never converted into a pass.",
        "coreChecks": checks,
        "corePassed": all(check["passed"] for check in checks),
        "unsupportedFullTrackGates": unsupported,
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["corePassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
