"""hi test — Run LLM-based tests against topic fixtures."""

import json
import os
import re
from pathlib import Path

import click

from hi.common import (
    log_warn,
    now_iso,
    require_topic,
    require_tracking,
    topic_dir,
)


def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke LLM or return stub response."""
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    if provider == "stub":
        return os.environ.get("HI_STUB_RESPONSE", "Stub response")
    raise click.ClickException(
        f"LLM provider '{provider}' not available — use LLM_PROVIDER=stub for testing"
    )


def _compare(actual: str, expected: str, mode: str) -> bool:
    """Compare actual vs expected response using the given mode."""
    if mode == "exact":
        return actual == expected
    elif mode == "contains":
        return expected in actual
    elif mode == "regex":
        return bool(re.search(expected, actual))
    elif mode == "normalized":
        def norm(s):
            return " ".join(s.lower().split())
        return norm(actual) == norm(expected)
    elif mode == "case_insensitive":
        return actual.lower() == expected.lower()
    elif mode == "keywords":
        for kw in expected.splitlines():
            kw = kw.strip()
            if kw and kw.lower() not in actual.lower():
                return False
        return True
    return actual == expected


@click.command(name="test")
@click.argument("topic")
@click.option("--fixture", default=None, help="Run a specific fixture by name")
@click.option(
    "--mode",
    default="exact",
    type=click.Choice(["exact", "contains", "regex", "normalized", "case_insensitive", "keywords"]),
    help="Comparison mode",
)
def test(topic, fixture, mode):
    """Run LLM-based tests against topic fixtures."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    td = topic_dir(topic)
    fixtures_dir = td / "process" / "fixtures"
    results_dir = fixtures_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Collect fixture files
    if fixture:
        f = fixtures_dir / f"{fixture}.yaml"
        if not f.exists():
            raise click.UsageError(f"Fixture not found: {f}")
        fixture_files = [f]
    else:
        fixture_files = sorted(
            p for p in fixtures_dir.glob("*.yaml")
            if not p.is_relative_to(results_dir)
        )

    if not fixture_files:
        log_warn(f"No fixtures found in {fixtures_dir}")
        return

    timestamp = now_iso()
    ts_safe = timestamp.replace(":", "")
    result_file = results_dir / f"{ts_safe}.json"

    passed = 0
    failed = 0
    errored = 0
    results = []

    from ruamel.yaml import YAML
    y = YAML()

    for fixture_file in fixture_files:
        fixture_name = fixture_file.stem

        with open(fixture_file) as f:
            fixture_data = y.load(f)

        if fixture_data is None:
            fixture_data = {}

        system_prompt = fixture_data.get("system_prompt", "")
        user_prompt = fixture_data.get("user_prompt", "")
        expected_response = fixture_data.get("expected_response", "")
        compare_mode = fixture_data.get("compare_mode", mode)

        if not user_prompt or not expected_response:
            log_warn(f"Fixture '{fixture_name}' missing user_prompt or expected_response — skipped")
            continue

        click.echo(f"Running fixture: {fixture_name}...", nl=False)

        try:
            actual_response = _invoke_llm(system_prompt, user_prompt)
            if _compare(actual_response, str(expected_response), compare_mode):
                outcome = "passed"
                passed += 1
                click.echo(" PASSED")
            else:
                outcome = "failed"
                failed += 1
                click.echo(" FAILED")
        except Exception as e:
            outcome = "errored"
            actual_response = str(e)
            errored += 1
            click.echo(" ERRORED")

        results.append({
            "name": fixture_name,
            "outcome": outcome,
            "mode": compare_mode,
            "expected": str(expected_response),
            "actual": actual_response,
        })

    # Write results JSON
    result_data = {
        "topic": topic,
        "timestamp": timestamp,
        "provider": os.environ.get("LLM_PROVIDER", "ollama"),
        "summary": {
            "passed": passed,
            "failed": failed,
            "errored": errored,
        },
        "results": results,
    }

    with open(result_file, "w") as f:
        json.dump(result_data, f, indent=2)

    click.echo(f"\nResults: {passed} passed, {failed} failed, {errored} errored")
    click.echo(f"Report: {result_file}")

    if failed > 0:
        raise SystemExit(1)
