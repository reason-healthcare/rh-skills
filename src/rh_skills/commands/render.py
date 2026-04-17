"""rh-skills render — generate human-readable views from L2 structured artifacts."""

from itertools import product as itertools_product
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.common import topic_dir

# Type → required section keys (validated at render time)
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "clinical-frame": ["frames"],
    "decision-table": ["conditions", "actions", "rules"],
    "assessment": ["instrument", "items", "scoring"],
    "policy": ["applicability", "criteria", "actions"],
}


def _validate_sections(sections: dict | None, artifact_type: str) -> None:
    """Raise UsageError if type-specific required sections are missing."""
    required = REQUIRED_SECTIONS.get(artifact_type)
    if not required:
        return
    if not sections:
        raise click.UsageError(
            f"Artifact type '{artifact_type}' requires sections: {', '.join(required)} — "
            "but 'sections' key is missing or empty"
        )
    missing = [key for key in required if key not in sections]
    if missing:
        raise click.UsageError(
            f"Missing required sections for '{artifact_type}': {', '.join(missing)}"
        )


# ── Renderers ───────────────────────────────────────────────────────────────────


def _render_generic_summary(data: dict, views_dir: Path) -> list[str]:
    """Render a generic metadata + sections summary for any artifact type."""
    lines = [f"# {data.get('title', data.get('name', 'Untitled'))}", ""]
    for field in ("id", "title", "domain", "description", "artifact_type", "clinical_question"):
        val = data.get(field)
        if val:
            lines.append(f"**{field}**: {val}")
    lines.append("")

    sections = data.get("sections", {})
    if isinstance(sections, dict):
        for key, val in sections.items():
            lines.append(f"## {key}")
            lines.append("")
            if isinstance(val, list):
                for item in val:
                    lines.append(f"- {item}")
            elif isinstance(val, dict):
                for k, v in val.items():
                    lines.append(f"- **{k}**: {v}")
            else:
                lines.append(str(val))
            lines.append("")

    out = views_dir / "summary.md"
    out.write_text("\n".join(lines) + "\n")
    return [str(out)]


def _render_clinical_frame(data: dict, views_dir: Path) -> list[str]:
    """Render PICOTS summary table from clinical-frame sections."""
    frames = data["sections"]["frames"]
    lines = [f"# PICOTS Summary — {data.get('title', data.get('name', ''))}", ""]
    lines.append("| ID | Population | Intervention | Comparison | Outcomes | Timing | Setting |")
    lines.append("|---|---|---|---|---|---|---|")
    for frame in frames:
        outcomes = "; ".join(frame.get("outcomes", []))
        lines.append(
            f"| {frame.get('id', '')} "
            f"| {frame.get('population', '')} "
            f"| {frame.get('intervention', '')} "
            f"| {frame.get('comparison', '')} "
            f"| {outcomes} "
            f"| {frame.get('timing', '')} "
            f"| {frame.get('setting', '')} |"
        )
    out = views_dir / "picots-summary.md"
    out.write_text("\n".join(lines) + "\n")
    return [str(out)]


def _render_assessment(data: dict, views_dir: Path) -> list[str]:
    """Render questionnaire items and scoring summary."""
    sections = data["sections"]
    written: list[str] = []

    # Questionnaire
    instrument = sections["instrument"]
    items = sections["items"]
    lines = [f"# {instrument.get('name', 'Assessment')}", ""]
    lines.append(f"**Purpose**: {instrument.get('purpose', 'N/A')}")
    lines.append(f"**Population**: {instrument.get('population', 'N/A')}")
    lines.append("")
    for i, item in enumerate(items, 1):
        lines.append(f"**{i}. {item.get('text', '')}** ({item.get('type', 'text')})")
        for opt in item.get("options", []):
            lines.append(f"   - [{opt.get('value', '')}] {opt.get('label', '')}")
        lines.append("")
    out = views_dir / "questionnaire.md"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    # Scoring summary
    scoring = sections["scoring"]
    lines = [f"# Scoring — {instrument.get('name', 'Assessment')}", ""]
    lines.append(f"**Method**: {scoring.get('method', 'N/A')}")
    lines.append("")
    lines.append("| Range | Interpretation |")
    lines.append("|---|---|")
    for r in scoring.get("ranges", []):
        lines.append(f"| {r.get('range', '')} | {r.get('interpretation', '')} |")
    out = views_dir / "scoring-summary.md"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    return written


def _render_policy(data: dict, views_dir: Path) -> list[str]:
    """Render criteria flowchart (mermaid) and requirements checklist."""
    sections = data["sections"]
    written: list[str] = []

    # Mermaid criteria flowchart
    criteria = sections.get("criteria", [])
    actions = sections.get("actions", {})
    lines = ["flowchart TD"]
    lines.append("    Start([Request Received])")
    for i, crit in enumerate(criteria):
        cid = crit.get("id", f"cr{i}")
        label = crit.get("description", "Check")
        req_type = crit.get("requirement_type", "clinical")
        lines.append(f"    {cid}{{{label}}}")
        if i == 0:
            lines.append(f"    Start --> {cid}")
        else:
            prev_id = criteria[i - 1].get("id", f"cr{i - 1}")
            lines.append(f"    {prev_id} -->|Met| {cid}")

    last_id = criteria[-1].get("id", "cr0") if criteria else "Start"
    lines.append(f"    {last_id} -->|Met| Approve([Approve])")
    lines.append(f"    {last_id} -->|Not Met| Deny([Deny])")
    if actions.get("pend"):
        lines.append(f"    {last_id} -->|Insufficient Info| Pend([Pend for Review])")

    out = views_dir / "criteria-flowchart.mmd"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    # Requirements checklist
    lines = [f"# Requirements Checklist — {data.get('title', data.get('name', ''))}", ""]
    for crit in criteria:
        lines.append(f"- [ ] **{crit.get('id', '?')}** [{crit.get('requirement_type', '')}]: {crit.get('description', '')}")
        lines.append(f"  - Rule: {crit.get('rule', 'N/A')}")
    lines.append("")
    lines.append("## Actions")
    for action_name in ("approve", "deny", "pend"):
        action = actions.get(action_name, {})
        if action:
            lines.append(f"- **{action_name.title()}**: {action.get('conditions', 'N/A')}")
    out = views_dir / "requirements-checklist.md"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    return written


def _check_completeness(conditions: list[dict], rules: list[dict]) -> dict:
    """Compute decision-table completeness per Shiffman model.

    Returns dict with: total_space, covered, complete (bool),
    missing (list of combos), contradictions (list), large_table_warning (bool).
    """
    if not conditions:
        return {"total_space": 0, "covered": 0, "complete": True,
                "missing": [], "contradictions": [], "large_table_warning": False}

    cond_ids = [c["id"] for c in conditions]
    cond_values = {c["id"]: c["values"] for c in conditions}
    moduli = [len(cond_values[cid]) for cid in cond_ids]
    total_space = 1
    for m in moduli:
        total_space *= m
    large_warning = total_space > 1024

    # Expand each rule's coverage
    expanded: dict[tuple, list[str]] = {}  # combo → list of rule IDs
    total_covered = 0
    for rule in rules:
        when = rule.get("when", {})
        then_actions = rule.get("then", [])
        rule_id = rule.get("id", "?")

        # Build per-condition value lists (dash = all values)
        per_cond: list[list[str]] = []
        coverage = 1
        for cid in cond_ids:
            val = when.get(cid, "-")
            if val == "-":
                per_cond.append(cond_values[cid])
                coverage *= len(cond_values[cid])
            else:
                per_cond.append([val])
        total_covered += coverage

        for combo in itertools_product(*per_cond):
            expanded.setdefault(combo, []).append(rule_id)

    # Find missing
    missing: list[dict] = []
    all_combos = list(itertools_product(*[cond_values[cid] for cid in cond_ids]))
    for combo in all_combos:
        if combo not in expanded:
            missing.append(dict(zip(cond_ids, combo)))

    # Find contradictions: same combo mapped by multiple rules
    contradictions: list[dict] = []
    for combo, rule_ids in expanded.items():
        if len(rule_ids) > 1:
            contradictions.append({
                "combination": dict(zip(cond_ids, combo)),
                "rules": rule_ids,
            })

    return {
        "total_space": total_space,
        "covered": total_covered,
        "complete": len(missing) == 0,
        "missing": missing,
        "contradictions": contradictions,
        "large_table_warning": large_warning,
    }


def _render_decision_table(data: dict, views_dir: Path) -> list[str]:
    """Render decision-table views: rules table, mermaid tree, completeness report."""
    sections = data["sections"]
    conditions = sections["conditions"]
    actions = sections["actions"]
    rules = sections["rules"]
    written: list[str] = []

    action_map = {a["id"]: a.get("label", a["id"]) for a in actions}
    cond_map = {c["id"]: c.get("label", c["id"]) for c in conditions}

    # Rules table
    cond_ids = [c["id"] for c in conditions]
    lines = [f"# Decision Table — {data.get('title', data.get('name', ''))}", ""]
    header = "| Rule |"
    sep = "|---|"
    for cid in cond_ids:
        header += f" {cond_map[cid]} |"
        sep += "---|"
    header += " Actions |"
    sep += "---|"
    lines.append(header)
    lines.append(sep)
    for rule in rules:
        when = rule.get("when", {})
        then = rule.get("then", [])
        row = f"| {rule.get('id', '?')} |"
        for cid in cond_ids:
            val = when.get(cid, "-")
            row += f" {val} |"
        action_labels = ", ".join(action_map.get(a, a) for a in then)
        row += f" {action_labels} |"
        lines.append(row)
    out = views_dir / "rules-table.md"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    # Mermaid decision tree
    lines = ["flowchart TD"]
    for i, cond in enumerate(conditions):
        cid = cond["id"]
        label = cond_map[cid]
        lines.append(f"    {cid}{{{label}?}}")
        if i == 0:
            lines.append(f"    Start([Start]) --> {cid}")
        else:
            prev = conditions[i - 1]["id"]
            for val in conditions[i - 1]["values"]:
                lines.append(f"    {prev} -->|{val}| {cid}")
    # Add action nodes for last condition
    if conditions:
        last_cond = conditions[-1]
        for val in last_cond["values"]:
            lines.append(f"    {last_cond['id']} -->|{val}| action_{val}([Action])")
    out = views_dir / "decision-tree.mmd"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    # Completeness report
    result = _check_completeness(conditions, rules)
    lines = [f"# Completeness Report — {data.get('title', data.get('name', ''))}", ""]
    lines.append(f"**Total decision space**: {result['total_space']}")
    lines.append(f"**Rules coverage**: {result['covered']}")
    lines.append(f"**Complete**: {'Yes' if result['complete'] else 'No'}")
    lines.append("")
    if result["large_table_warning"]:
        lines.append("> ⚠️ Large table warning: decision space exceeds 1024 combinations")
        lines.append("")
    if result["missing"]:
        lines.append("## Missing Combinations")
        lines.append("")
        for combo in result["missing"]:
            parts = ", ".join(f"{cond_map.get(k, k)}={v}" for k, v in combo.items())
            lines.append(f"- {parts}")
        lines.append("")
    if result["contradictions"]:
        lines.append("## Contradictions")
        lines.append("")
        for cont in result["contradictions"]:
            parts = ", ".join(f"{cond_map.get(k, k)}={v}" for k, v in cont["combination"].items())
            lines.append(f"- {parts} — rules: {', '.join(cont['rules'])}")
        lines.append("")
    out = views_dir / "completeness-report.md"
    out.write_text("\n".join(lines) + "\n")
    written.append(str(out))

    return written


# ── Dispatcher ──────────────────────────────────────────────────────────────────

RENDERERS: dict[str, callable] = {
    "clinical-frame": _render_clinical_frame,
    "decision-table": _render_decision_table,
    "assessment": _render_assessment,
    "policy": _render_policy,
}


@click.command("render")
@click.argument("topic")
@click.argument("artifact")
def render(topic: str, artifact: str) -> None:
    """Generate human-readable views from an L2 structured artifact."""
    td = topic_dir(topic)
    artifact_file = td / "structured" / artifact / f"{artifact}.yaml"
    if not artifact_file.exists():
        click.echo(f"Artifact not found: {artifact_file}", err=True)
        raise SystemExit(1)

    y = YAML(typ="safe")
    data = y.load(artifact_file.read_text())

    artifact_type = data.get("artifact_type", "")
    sections = data.get("sections")
    _validate_sections(sections, artifact_type)

    views_dir = artifact_file.parent / "views"
    views_dir.mkdir(parents=True, exist_ok=True)

    renderer = RENDERERS.get(artifact_type, _render_generic_summary)
    written = renderer(data, views_dir)

    click.echo(f"Rendered {len(written)} view(s) for '{artifact}' ({artifact_type or 'generic'}):")
    for path in written:
        click.echo(f"  {path}")
