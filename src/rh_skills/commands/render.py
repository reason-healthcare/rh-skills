"""rh-skills render — generate human-readable views from L2 structured artifacts."""

from importlib.resources import files
from itertools import product as itertools_product
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, Undefined
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rh_skills.common import topic_dir

# Type → required section keys (validated at render time)
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "evidence-summary": ["summary_points"],
    "decision-table": ["events", "conditions", "actions", "rules"],
    "care-pathway": ["steps"],
    "terminology": ["value_sets"],
    "measure": ["populations"],
    "assessment": ["instrument", "items", "scoring"],
    "policy": ["applicability", "criteria", "actions"],
}

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "render"
_CONDITION_HEADER_MAX_CHARS = 14
_ACTION_CELL_MAX_CHARS = 24


def _jinja_env(type_dir: Path) -> Environment:
    """Build a Jinja2 environment scoped to an artifact-type template directory."""
    return Environment(
        loader=FileSystemLoader(str(type_dir)),
        undefined=Undefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _validate_sections(sections: dict | None, artifact_type: str) -> None:
    required = REQUIRED_SECTIONS.get(artifact_type)
    if not required:
        return
    if not sections:
        click.echo(
            f"Artifact type '{artifact_type}' requires sections: {', '.join(required)} — "
            "but 'sections' key is missing or empty",
            err=True,
        )
        raise SystemExit(1)
    missing = [key for key in required if key not in sections]
    if missing:
        click.echo(
            f"Missing required sections for '{artifact_type}': {', '.join(missing)}",
            err=True,
        )
        raise SystemExit(1)


# ── Completeness algorithm (pure logic, not a template) ─────────────────────


def _truncate_table_label(text: str, max_chars: int = _CONDITION_HEADER_MAX_CHARS) -> str:
    """Shorten a column label so markdown tables stay readable."""
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    truncated = normalized[: max_chars - 3].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return f"{truncated}..."


def _check_completeness(conditions: list[dict], rules: list[dict]) -> dict:
    """Compute decision-table completeness per Shiffman model."""
    if not conditions:
        return {"total_space": 0, "covered": 0, "complete": True,
                "missing": [], "contradictions": [], "large_table_warning": False}

    cond_ids = [c["id"] for c in conditions]
    cond_values = {c["id"]: c["values"] for c in conditions}
    total_space = 1
    for vals in cond_values.values():
        total_space *= len(vals)
    large_warning = total_space > 1024

    expanded: dict[tuple, list[str]] = {}
    total_covered = 0
    for rule in rules:
        when = rule.get("when", {})
        rule_id = rule.get("id", "?")
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

    all_combos = list(itertools_product(*[cond_values[cid] for cid in cond_ids]))
    missing = [dict(zip(cond_ids, combo)) for combo in all_combos if combo not in expanded]
    contradictions = [
        {"combination": dict(zip(cond_ids, combo)), "rules": rule_ids}
        for combo, rule_ids in expanded.items()
        if len(rule_ids) > 1
    ]

    return {
        "total_space": total_space,
        "covered": total_covered,
        "complete": len(missing) == 0,
        "missing": missing,
        "contradictions": contradictions,
        "large_table_warning": large_warning,
    }


def _build_decision_matrix_context(sections: dict | None) -> dict:
    """Prepare display-friendly context for decision-table markdown rendering."""
    sections = sections or {}
    events = sections.get("events", [])
    conditions = sections.get("conditions", [])
    actions = sections.get("actions", [])
    rules = sections.get("rules", [])

    event_rows = [
        {
            "key": event.get("id", "?"),
            "meaning": event.get("label") or event.get("description") or event.get("id", "?"),
            "description": event.get("description", ""),
        }
        for event in events
    ]
    condition_rows = [
        {
            "key": condition.get("id", "?"),
            "meaning": condition.get("label") or condition.get("id", "?"),
            "rule_header": " ".join(
                part for part in [
                    condition.get("id", "?"),
                    _truncate_table_label(condition.get("label") or condition.get("id", "?")),
                ] if part
            ),
            "values": condition.get("values", []),
        }
        for condition in conditions
    ]
    action_rows = [
        {
            "key": action.get("id", "?"),
            "meaning": action.get("label") or action.get("id", "?"),
            "rule_label": " ".join(
                part for part in [
                    action.get("id", "?"),
                    _truncate_table_label(
                        action.get("label") or action.get("id", "?"),
                        _ACTION_CELL_MAX_CHARS,
                    ),
                ] if part
            ),
        }
        for action in actions
    ]

    event_map = {row["key"]: row["meaning"] for row in event_rows}
    action_rule_map = {row["key"]: row["rule_label"] for row in action_rows}

    rule_rows = []
    for rule in rules:
        when = rule.get("when", {}) if isinstance(rule.get("when"), dict) else {}
        rule_actions = []
        for action_id in rule.get("then", []):
            rule_actions.append(action_rule_map.get(action_id, action_id))
        event_id = rule.get("event")
        event_display = "-"
        if events:
            if event_id:
                event_label = event_map.get(event_id, event_id)
                event_display = f"{event_id} {event_label}" if event_label != event_id else event_id
        rule_rows.append(
            {
                "id": rule.get("id", "?"),
                "event": event_display,
                "condition_values": [when.get(condition.get("id", "?"), "-") for condition in conditions],
                "actions": rule_actions,
            }
        )

    return {
        "event_rows": event_rows,
        "condition_rows": condition_rows,
        "action_rows": action_rows,
        "rule_rows": rule_rows,
    }


# ── Template-driven renderer ─────────────────────────────────────────────────


def _render_from_templates(data: dict, artifact_dir: Path, artifact_name: str) -> list[str]:
    """Render all templates for the artifact's type; fall back to _generic.

    Output files are written directly into *artifact_dir* (no views/ sub-dir)
    and prefixed with ``<artifact_name>-``.
    """
    artifact_type = data.get("artifact_type", "")
    type_dir = _TEMPLATES_DIR / artifact_type
    if not type_dir.is_dir() or not list(type_dir.glob("*.j2")):
        type_dir = _TEMPLATES_DIR / "_generic"

    env = _jinja_env(type_dir)

    # Extra context computed from data (avoids logic in templates)
    extra: dict = {}
    if artifact_type == "decision-table":
        sections = data.get("sections", {})
        extra["decision_matrix"] = _build_decision_matrix_context(sections)
        extra["completeness"] = _check_completeness(
            sections.get("conditions", []),
            sections.get("rules", []),
        )

    written: list[str] = []
    for tmpl_path in sorted(type_dir.glob("*.j2")):
        out_name = tmpl_path.stem  # e.g. "report.md" from "report.md.j2"
        rendered = env.get_template(tmpl_path.name).render(data=data, **extra)
        # Wrap .mmd output in a fenced ```mermaid block inside a .md file
        if out_name.endswith(".mmd"):
            out_name = out_name[:-4] + ".md"
            rendered = f"```mermaid\n{rendered.rstrip()}\n```\n"
        # Prefix with artifact name: e.g. "my-decision-report.md"
        out = artifact_dir / f"{artifact_name}-{out_name}"
        out.write_text(rendered)
        written.append(str(out))

    return written


# ── CLI command ──────────────────────────────────────────────────────────────


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
    try:
        data = y.load(artifact_file.read_text())
    except YAMLError as exc:
        click.echo(
            f"Error: YAML parse error in {artifact_file.name}: {exc}\n"
            "Hint: values starting with '>' or '<' must be quoted. "
            "Example: threshold: \">=190 mg/dL\" (not: threshold: >=190 mg/dL)",
            err=True,
        )
        raise SystemExit(1)

    artifact_type = data.get("artifact_type", "")
    sections = data.get("sections")
    _validate_sections(sections, artifact_type)

    artifact_dir = artifact_file.parent

    written = _render_from_templates(data, artifact_dir, artifact)

    click.echo(f"Rendered {len(written)} view(s) for '{artifact}' ({artifact_type or 'generic'}):")
    for path in written:
        click.echo(f"  {path}")
