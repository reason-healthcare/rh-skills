#!/usr/bin/env python3
"""Run a bounded durable Connectathon acceptance replay for one named run.

Required core: native CQL matrices (the exact configured oracle count) and
direct public Node/WASM execution. Service replays are opt-in because they need
an already authenticated Workbench or a running standalone server. Browser,
FHIR-validator, SDC, and second-engine evidence are never inferred from this
command.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import os
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand(value: str, roots: dict[str, str]) -> str:
    for name, root in roots.items():
        value = value.replace("${" + name + "}", root)
    return value


def run_command(
    command: list[str], cwd: Path, output: Path, environment: dict[str, str] | None = None
) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, env=environment
    )
    output.write_text(result.stdout + ("\nSTDERR:\n" + result.stderr if result.stderr else ""))
    text = result.stdout + result.stderr
    matches = [tuple(map(int, match)) for match in re.findall(r"(\d+)\s*/\s*(\d+)", text)]
    matches.extend((int(count), int(count)) for count in re.findall(r"PASS\s+[—-]\s+(\d+)\s+assertion", text))
    return {"command": command, "exitCode": result.returncode, "counts": matches, "log": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rh-skills-bin", default="rh-skills")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--with-standalone", metavar="URL")
    parser.add_argument("--with-workbench", metavar="URL")
    parser.add_argument("--workbench-config", type=Path)
    parser.add_argument("--workbench-cookie-env", default="WORKBENCH_COOKIE")
    parser.add_argument("--oracle-root", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    roots = {"REPO_ROOT": str(args.repo_root.resolve()), "RUNTIME_ROOT": str(args.runtime_root.resolve())}
    workspace = Path(expand(config["workspace"], roots))
    content = Path(expand(config["content"], roots))
    fixtures = Path(expand(config["fixtures"], roots))
    runtime = Path(expand(config["runtime"], roots))
    args.output.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    native_environment = os.environ.copy()
    native_environment["RH_CLI_PATH"] = str(args.runtime_root.resolve() / "target/debug/rh")
    for matrix in config["nativeCql"]:
        command = [args.rh_skills_bin, "cql", "test", config["topic"], matrix["library"]]
        result = run_command(
            command, workspace, args.output / f"native-{matrix['library']}.log", native_environment
        )
        observed_total = sum(total for _, total in result["counts"])
        observed_passed = sum(passed for passed, _ in result["counts"])
        passed = result["exitCode"] == 0 and observed_total == matrix["expected"] and observed_passed == matrix["expected"]
        checks.append({"name": f"native-cql:{matrix['library']}", "status": "pass" if passed else "fail", "expected": matrix["expected"], "observed": {"passed": observed_passed, "total": observed_total}, **result})
    direct_output = args.output / "direct-node"
    direct_command = [args.node_bin, str(args.repo_root / "docs/connectathon/tools/verify-direct-node.mjs"), "--content", str(content), "--runtime", str(runtime), "--oracle-root", str(args.oracle_root), "--profile", config["run"], "--output", str(direct_output)]
    direct = run_command(direct_command, workspace, args.output / "direct-node.log")
    direct_report_path = direct_output / "results.json"
    direct_report = json.loads(direct_report_path.read_text()) if direct_report_path.exists() else {}
    direct_passed = direct["exitCode"] == 0 and direct_report.get("counts", {}).get("failed") == 0 and direct_report.get("counts", {}).get("total") == direct_report.get("expectedChecks")
    checks.append({"name": "direct-public-node-wasm-semantic", "status": "pass" if direct_passed else "fail", "report": str(direct_report_path), **direct})
    optional = []
    if args.with_standalone:
            report_dir = args.output / "standalone-api-parity"
            command = [args.node_bin, str(args.repo_root / "docs/connectathon/tools/vendor/verify-standalone-api-parity.mjs"), "--content", str(content), "--plan", config["plan"], "--fixtures", str(fixtures), "--assertion-root", str(args.oracle_root / "cases"), "--evaluation-date", "2026-06-15T09:20:00Z", "--output", str(report_dir), "--standalone", args.with_standalone, "--runtime", str(runtime), "--guidance-json", json.dumps(config["guidance"])]
            result = run_command(command, workspace, args.output / "standalone-api-parity.log")
            optional.append({"name": "standalone-api-parity", "status": "pass" if result["exitCode"] == 0 else "fail", **result})
    else:
        optional.append({"name": "standalone-api-parity", "status": "not_run", "reason": "pass --with-standalone URL to rerun"})
    if args.with_workbench:
        if not args.workbench_config:
            optional.append({"name": "workbench-api-matrix", "status": "fail", "reason": "--workbench-config is required for the requested Workbench replay"})
        elif not os.environ.get(args.workbench_cookie_env):
            optional.append({"name": "workbench-api-matrix", "status": "fail", "reason": f"{args.workbench_cookie_env} is required and is never written to evidence"})
        else:
            workbench_config = json.loads(args.workbench_config.read_text())
            workbench_config.update({"baseUrl": args.with_workbench, "contentPath": str(content), "fixtureIndexPath": str(fixtures), "assertionRoot": str(args.oracle_root / "cases"), "runtimePath": str(runtime)})
            generated_config = args.output / "workbench-api-matrix-config.json"
            generated_config.write_text(json.dumps(workbench_config, indent=2) + "\n")
            verifier_environment = os.environ.copy()
            verifier_environment["WORKBENCH_COOKIE"] = os.environ[
                args.workbench_cookie_env
            ]
            result = run_command(
                [args.node_bin, str(args.repo_root / "docs/connectathon/tools/vendor/verify-workbench-api-matrix.mjs"), "--config", str(generated_config), "--output", str(args.output / "workbench-api-matrix")],
                workspace,
                args.output / "workbench-api-matrix.log",
                verifier_environment,
            )
            optional.append({"name": "workbench-api-matrix", "status": "pass" if result["exitCode"] == 0 else "fail", **result})
    else:
        optional.append({"name": "workbench-api-matrix", "status": "not_run", "reason": "pass --with-workbench URL, --workbench-config, and an authenticated cookie to rerun"})
    report = {"checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "run": config["run"], "scope": "Required core invokes native CQL and direct Node/WASM only. Optional service replays and external evidence are not converted into a full-track pass.", "inputs": {"workspace": str(workspace), "content": {"path": str(content), "sha256": sha256(content)}, "fixtures": {"path": str(fixtures), "sha256": sha256(fixtures)}, "runtime": {"path": str(runtime), "sha256": sha256(runtime)}}, "core": checks, "corePassed": all(item["status"] == "pass" for item in checks), "optional": optional, "external": [{"name": "authenticated-browser", "status": "not_run"}, {"name": "official-fhir-validation", "status": "not_run"}, {"name": "manual-clinical-review", "status": "not_run"}, {"name": "SDC-extraction", "status": "unsupported"}, {"name": "second-engine-parity", "status": "unsupported"}]}
    report_path = args.output / "acceptance-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    requested_service_failed = any(item["status"] == "fail" for item in optional)
    return 0 if report["corePassed"] and not requested_service_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
