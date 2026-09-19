#!/usr/bin/env python3
"""Verify bounded runtime components tied to explicit final artifact hashes.

This is not an end-to-end Connectathon acceptance gate. It cannot establish
snapshot/browser replay, final official FHIR validation, package import, or a
second engine. Those are reported as unsupported gates and must remain so.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def parse_gate(value: str) -> dict[str, str]:
    name, separator, reason = value.partition("=")
    if not separator or not name or not reason:
        raise argparse.ArgumentTypeError("must be NAME=REASON")
    return {"name": name, "status": "unsupported", "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parity", required=True)
    parser.add_argument("--native", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--run002", required=True)
    parser.add_argument("--package-loader", required=True)
    parser.add_argument("--content", required=True, help="final executable content Bundle")
    parser.add_argument("--fixtures", required=True, help="final executable fixture index")
    parser.add_argument("--package", required=True, help="final package TGZ")
    parser.add_argument("--native-sha", required=True)
    parser.add_argument("--wasm-sha", required=True)
    parser.add_argument("--runtime-module-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--unsupported-gate", action="append", type=parse_gate, default=[])
    args = parser.parse_args()

    content_sha, fixtures_sha, package_sha = map(sha256, (args.content, args.fixtures, args.package))
    checks: list[dict[str, Any]] = []

    parity = load(args.parity)
    parity_inputs, parity_counts = parity.get("inputs", {}), parity.get("counts", {})
    parity_ok = (
        parity.get("sourceFixturesUnchanged") is True
        and parity_counts == {"total": 6, "parityPassed": 6, "semanticPassed": 6}
        and parity_inputs.get("contentSha256") == content_sha
        and parity_inputs.get("fixtureManifestSha256") == fixtures_sha
        and parity_inputs.get("runtimeSha256") == args.runtime_module_sha
        and parity_inputs.get("wasmSha256") == args.wasm_sha
    )
    checks.append({"name": "final-bundle-standalone-api-parity", "path": args.parity, "passed": parity_ok, "detail": parity_counts})

    native = load(args.native)
    native_ok = nested_count_ok(native) and native.get("runtimeSha256") == args.native_sha
    checks.append({"name": "native-cql-matrix", "path": args.native, "passed": native_ok, "detail": native.get("counts")})

    node = load(args.node)
    node_ok = nested_count_ok(node) and node.get("wasmNodeSha256") == args.wasm_sha
    checks.append({"name": "public-node-wasm-one-hot-matrix", "path": args.node, "passed": node_ok, "detail": node.get("counts")})

    run002 = load(args.run002)
    run002_ok = nested_count_ok(run002) and run002.get("nativeSha256") == args.native_sha
    checks.append({"name": "portable-run002-cql-matrix", "path": args.run002, "passed": run002_ok, "detail": run002.get("counts")})

    loader = load(args.package_loader)
    loader_ok = (
        loader.get("packageSha256") == package_sha
        and loader.get("executableContentSha256") == content_sha
        and loader.get("packageExampleBundleCount") == 6
        and loader.get("executableBundleResourceCount") == 0
        and loader.get("testResult") == "passed (1 test)"
    )
    checks.append({"name": "package-fixture-knowledge-boundary", "path": args.package_loader, "passed": loader_ok, "detail": {key: loader.get(key) for key in ("packageExampleBundleCount", "executableBundleResourceCount", "testResult")}})

    gates = args.unsupported_gate + [
        {"name": "final-official-fhir-validation", "status": "pending-external-evidence", "reason": "This component verifier does not accept earlier validation of a different resource count or bundle hash."},
        {"name": "workbench-imported-snapshot-api-replay", "status": "pending-external-evidence", "reason": "Requires the separate authenticated Workbench replay evidence."},
        {"name": "authenticated-browser-snapshot", "status": "pending-external-evidence", "reason": "Owned and verified separately by the Workbench/browser workstream."},
        {"name": "full-track-two-engine", "status": "unsupported", "reason": "Not established by local RH runtime component checks."},
    ]
    report = {
        "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "Bounded final-artifact runtime component acceptance. A true componentPassed result does not claim full Connectathon acceptance.",
        "boundInputs": {"content": {"path": args.content, "sha256": content_sha}, "fixtures": {"path": args.fixtures, "sha256": fixtures_sha}, "package": {"path": args.package, "sha256": package_sha}, "nativeSha256": args.native_sha, "wasmSha256": args.wasm_sha, "runtimeModuleSha256": args.runtime_module_sha},
        "componentChecks": checks,
        "componentPassed": all(check["passed"] for check in checks),
        "unsupportedGates": gates,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["componentPassed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
