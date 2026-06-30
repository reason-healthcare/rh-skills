"""rh-skills render — generate human-readable views from L2 structured artifacts."""

from importlib.resources import files
from itertools import product as itertools_product
from collections import defaultdict
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, Undefined
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rh_skills.common import (
    resolve_structured_artifact_file,
    topic_dir,
)

# Type → required section keys (validated at render time)
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "evidence-summary": ["summary_points"],
    "decision-table": ["events", "conditions", "data_elements", "actions", "rules"],
    "care-pathway": ["steps"],
    "terminology": ["value_sets"],
    "measure": ["populations"],
    "assessment": ["instrument", "items", "scoring"],
    "policy": ["applicability", "criteria", "actions"],
}

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "render"


def _display_label(item: dict, *, include_id: bool = False) -> str:
    """Return a stable human-readable label for an L2 item."""
    item_id = str(item.get("id") or "").strip()
    label = str(item.get("label") or item.get("title") or item.get("description") or item_id or "?").strip()
    if include_id and item_id:
        return f"{item_id} {label}"
    return label or item_id or "?"


def _ascii_tree_from_nodes(nodes: list[dict]) -> str:
    """Render a prebuilt node forest to an ASCII tree."""
    lines: list[str] = []

    def visit(node: dict, prefix: str, is_last: bool, is_root: bool = False) -> None:
        label = str(node.get("label") or "?")
        if is_root:
            lines.append(label)
        else:
            connector = "`-- " if is_last else "|-- "
            lines.append(f"{prefix}{connector}{label}")
        children = node.get("children") or []
        next_prefix = prefix + ("    " if is_last else "|   ")
        for idx, child in enumerate(children):
            visit(child, next_prefix, idx == len(children) - 1, False)

    for idx, node in enumerate(nodes):
        visit(node, "", idx == len(nodes) - 1, True)
    return "\n".join(lines)


def _care_pathway_tree(steps: list[dict]) -> str:
    """Build an ASCII tree from care-pathway steps using parent_id."""
    if not isinstance(steps, list) or not steps:
        return ""

    step_map = {str(step.get("id") or ""): step for step in steps if isinstance(step, dict)}
    child_map: dict[str | None, list[dict]] = defaultdict(list)
    for step in steps:
        if not isinstance(step, dict):
            continue
        parent_id = step.get("parent_id")
        if isinstance(parent_id, str) and parent_id.strip() and parent_id in step_map:
            child_map[parent_id].append(step)
        else:
            child_map[None].append(step)

    def build_node(step: dict) -> dict:
        step_id = str(step.get("id") or "")
        children = [build_node(child) for child in child_map.get(step_id, [])]
        return {
            "label": _display_label(step),
            "children": children,
        }

    roots = [build_node(step) for step in child_map.get(None, [])]
    return _ascii_tree_from_nodes(roots)


def _care_pathway_transition_rows(sections: dict) -> list[dict]:
    """Resolve care-pathway transition endpoints to display labels."""
    steps = (sections or {}).get("steps") or []
    transitions = (sections or {}).get("transitions") or []
    if not isinstance(steps, list) or not isinstance(transitions, list):
        return []

    step_map = {
        str(step.get("id") or ""): step
        for step in steps
        if isinstance(step, dict) and str(step.get("id") or "").strip()
    }

    rows: list[dict] = []
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        from_id = str(transition.get("from_id") or transition.get("from") or "").strip()
        to_id = str(transition.get("to_id") or transition.get("to") or "").strip()
        from_label = _display_label(step_map[from_id]) if from_id in step_map else (from_id or "-")
        to_label = _display_label(step_map[to_id]) if to_id in step_map else (to_id or "-")
        rows.append({
            "from_label": from_label,
            "to_label": to_label,
            "description": transition.get("description") or "",
        })
    return rows


def _format_condition_value(value) -> str:
    """Render L2 condition/applicability fields as compact report text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        condition_id = value.get("condition_id") or value.get("condition") or value.get("id")
        expected = value.get("value") or value.get("expected") or value.get("equals")
        if condition_id and expected:
            return f"{condition_id} = {expected}"
        if condition_id:
            return str(condition_id)
        return ", ".join(
            f"{key}={_format_condition_value(item)}"
            for key, item in value.items()
            if _format_condition_value(item)
        )
    if isinstance(value, list):
        return "; ".join(
            formatted
            for item in value
            if (formatted := _format_condition_value(item))
        )
    return str(value)


def _applicability_condition_id(entry) -> str | None:
    """Return a condition id from a table/event applicability entry."""
    if isinstance(entry, str) and entry.strip():
        return entry.strip()
    if isinstance(entry, dict):
        for key in ("condition_id", "condition", "id"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _applicability_expected_value(entry) -> str:
    """Return the expected value for a global applicability condition."""
    if isinstance(entry, dict):
        for key in ("value", "expected", "equals"):
            value = entry.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return "Yes"


def _decision_table_applicability_rows(sections: dict) -> list[dict]:
    """Build display rows for decision-table table-level applicability."""
    conditions = sections.get("conditions") or []
    applicability = sections.get("applicability") or []
    if not isinstance(conditions, list) or not isinstance(applicability, list):
        return []

    condition_map = {
        str(condition.get("id") or ""): condition
        for condition in conditions
        if isinstance(condition, dict) and str(condition.get("id") or "").strip()
    }
    rows: list[dict] = []
    for entry in applicability:
        condition_id = _applicability_condition_id(entry)
        if not condition_id:
            continue
        condition = condition_map.get(condition_id, {"id": condition_id})
        rows.append({
            "condition_id": condition_id,
            "label": _display_label(condition, include_id=True),
            "value": _applicability_expected_value(entry),
        })
    return rows


def _decision_table_rule_conditions(sections: dict) -> list[dict]:
    """Return conditions that belong in the per-rule condition matrix."""
    conditions = sections.get("conditions") or []
    rules = sections.get("rules") or []
    applicability = sections.get("applicability") or []
    if not isinstance(conditions, list):
        return []

    applicability_ids = {
        condition_id
        for entry in applicability
        if (condition_id := _applicability_condition_id(entry))
    } if isinstance(applicability, list) else set()

    rule_condition_ids: set[str] = set()
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            when_clause = rule.get("when") or {}
            if isinstance(when_clause, dict):
                rule_condition_ids.update(str(condition_id) for condition_id in when_clause.keys())

    return [
        condition
        for condition in conditions
        if isinstance(condition, dict)
        and str(condition.get("id") or "") not in applicability_ids
        and str(condition.get("id") or "") in rule_condition_ids
    ]


def _care_pathway_step_condition(step: dict) -> str:
    """Return the canonical care-pathway step applicability condition."""
    return _format_condition_value(step.get("applicability_condition")) or "-"


def _care_pathway_step_rows(sections: dict) -> list[dict]:
    """Build normalized rows for the care-pathway step report table."""
    steps = (sections or {}).get("steps") or []
    if not isinstance(steps, list):
        return []
    rows: list[dict] = []
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        rows.append({
            "label": step.get("label") or step.get("title") or step.get("id") or idx,
            "description": step.get("description") or "",
            "condition": _care_pathway_step_condition(step),
            "actor": step.get("actor") or "",
            "parent_id": step.get("parent_id") or "-",
            "rule_id": step.get("rule_id") or ", ".join(str(value) for value in step.get("rule_ids") or []) or "-",
            "action_labels": step.get("action_labels") or [],
        })
    return rows


def _decision_table_tree(sections: dict) -> str:
    """Build an ASCII tree from decision-table events, rules, and action hierarchy."""
    events = sections.get("events") or []
    conditions = sections.get("conditions") or []
    actions = sections.get("actions") or []
    rules = sections.get("rules") or []
    if not isinstance(events, list) or not events:
        return ""

    cond_map = {
        str(cond.get("id") or ""): str(cond.get("label") or cond.get("id") or "?")
        for cond in conditions
        if isinstance(cond, dict)
    }
    action_map = {
        str(action.get("id") or ""): action
        for action in actions
        if isinstance(action, dict) and str(action.get("id") or "").strip()
    }
    child_actions: dict[str | None, list[str]] = defaultdict(list)
    for action_id, action in action_map.items():
        parent_id = action.get("parent_action_id")
        if isinstance(parent_id, str) and parent_id.strip() and parent_id in action_map:
            child_actions[parent_id].append(action_id)
        else:
            child_actions[None].append(action_id)

    rules_by_event: dict[str, list[dict]] = defaultdict(list)
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        event_id = str(rule.get("event") or "").strip()
        if event_id:
            rules_by_event[event_id].append(rule)

    def action_in_scope(action_id: str, scoped_ids: set[str], visiting: set[str] | None = None) -> bool:
        if action_id in scoped_ids:
            return True
        if visiting is None:
            visiting = set()
        if action_id in visiting:
            return False
        visiting.add(action_id)
        try:
            return any(
                action_in_scope(child_id, scoped_ids, visiting)
                for child_id in child_actions.get(action_id, [])
            )
        finally:
            visiting.remove(action_id)

    def build_action_node(action_id: str, scoped_ids: set[str], path: list[str] | None = None) -> dict:
        path = path or []
        if action_id in path:
            return {
                "label": f"{action_id} [cycle omitted]",
                "children": [],
            }
        action = action_map[action_id]
        next_path = path + [action_id]
        children = [
            build_action_node(child_id, scoped_ids, next_path)
            for child_id in child_actions.get(action_id, [])
            if action_in_scope(child_id, scoped_ids)
        ]
        return {
            "label": _display_label(action, include_id=True),
            "children": children,
        }

    def build_rule_node(rule: dict) -> dict:
        when_nodes: list[dict] = []
        when_clause = rule.get("when") or {}
        if isinstance(when_clause, dict):
            for cond_id, value in when_clause.items():
                when_nodes.append({
                    "label": f"When: {cond_map.get(str(cond_id), str(cond_id))} = {value}",
                    "children": [],
                })

        then_ids = [str(aid) for aid in (rule.get("then") or []) if str(aid) in action_map]
        scoped_ids = set(then_ids)
        top_action_ids = [
            action_id for action_id in then_ids
            if str(action_map[action_id].get("parent_action_id") or "") not in scoped_ids
        ]
        then_children = [build_action_node(action_id, scoped_ids) for action_id in top_action_ids]
        children = when_nodes[:]
        if then_children:
            children.append({"label": "Then", "children": then_children})

        rule_label = str(rule.get("action") or rule.get("description") or rule.get("id") or "rule").strip()
        return {"label": f"Rule: {rule_label}", "children": children}

    root_nodes: list[dict] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("id") or "")
        trigger = event.get("trigger") or {}
        trigger_text = ""
        if isinstance(trigger, dict):
            trigger_name = str(trigger.get("name") or "").strip()
            if trigger_name:
                trigger_text = f" [trigger: {trigger_name}]"
        root_nodes.append({
            "label": f"Event: {_display_label(event)}{trigger_text}",
            "children": [build_rule_node(rule) for rule in rules_by_event.get(event_id, [])],
        })

    return _ascii_tree_from_nodes(root_nodes)


def _jinja_env(type_dir: Path) -> Environment:
    """Build a Jinja2 environment scoped to an artifact-type template directory."""
    env = Environment(
        loader=FileSystemLoader(str(type_dir)),
        undefined=Undefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.globals["care_pathway_tree"] = _care_pathway_tree
    env.globals["decision_table_tree"] = _decision_table_tree
    return env


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


def _rule_action_signature(rule: dict) -> tuple[str, ...]:
    """Return a stable action signature for conflict comparisons."""
    then_clause = rule.get("then") or []
    if not isinstance(then_clause, list):
        return ()
    return tuple(str(action_id) for action_id in then_clause)


def _rule_conditions_overlap(rule_a: dict, rule_b: dict, cond_ids: list[str]) -> bool:
    """Return whether two sparse rule predicates can match the same case."""
    event_a = str(rule_a.get("event") or "").strip()
    event_b = str(rule_b.get("event") or "").strip()
    if event_a and event_b and event_a != event_b:
        return False

    when_a = rule_a.get("when") or {}
    when_b = rule_b.get("when") or {}
    if not isinstance(when_a, dict):
        when_a = {}
    if not isinstance(when_b, dict):
        when_b = {}

    for cond_id in cond_ids:
        value_a = when_a.get(cond_id, "-")
        value_b = when_b.get(cond_id, "-")
        if value_a != "-" and value_b != "-" and value_a != value_b:
            return False
    return True


def _sparse_contradictions(conditions: list[dict], rules: list[dict]) -> list[dict]:
    """Find rule pairs with overlapping predicates and different actions."""
    cond_ids = [str(c.get("id") or "") for c in conditions if isinstance(c, dict) and c.get("id")]
    contradictions: list[dict] = []
    for left_idx, rule_a in enumerate(rules):
        if not isinstance(rule_a, dict):
            continue
        for rule_b in rules[left_idx + 1:]:
            if not isinstance(rule_b, dict):
                continue
            if _rule_action_signature(rule_a) == _rule_action_signature(rule_b):
                continue
            if not _rule_conditions_overlap(rule_a, rule_b, cond_ids):
                continue
            contradictions.append({
                "rules": [rule_a.get("id", "?"), rule_b.get("id", "?")],
                "actions": [
                    list(_rule_action_signature(rule_a)),
                    list(_rule_action_signature(rule_b)),
                ],
            })
    return contradictions


def _check_completeness(
    conditions: list[dict],
    rules: list[dict],
    *,
    max_combinations: int = 10_000,
) -> dict:
    """Compute decision-table completeness per Shiffman model."""
    if not conditions:
        return {"total_space": 0, "covered": 0, "complete": True,
                "missing": [], "contradictions": [], "large_table_warning": False,
                "exhaustive": True, "max_combinations": max_combinations}

    cond_ids = [c["id"] for c in conditions]
    cond_values = {c["id"]: c["values"] for c in conditions}
    total_space = 1
    for vals in cond_values.values():
        total_space *= len(vals)
    large_warning = total_space > 1024

    total_covered = 0
    for rule in rules:
        when = rule.get("when", {})
        if not isinstance(when, dict):
            when = {}
        coverage = 1
        for cid in cond_ids:
            val = when.get(cid, "-")
            if val == "-":
                coverage *= len(cond_values[cid])
        total_covered += coverage

    if total_space > max_combinations:
        return {
            "total_space": total_space,
            "covered": total_covered,
            "complete": None,
            "missing": [],
            "contradictions": _sparse_contradictions(conditions, rules),
            "large_table_warning": large_warning,
            "exhaustive": False,
            "max_combinations": max_combinations,
        }

    expanded: dict[tuple, list[dict]] = {}
    for rule in rules:
        when = rule.get("when", {})
        if not isinstance(when, dict):
            when = {}
        per_cond: list[list[str]] = []
        for cid in cond_ids:
            val = when.get(cid, "-")
            if val == "-":
                per_cond.append(cond_values[cid])
            else:
                per_cond.append([val])
        for combo in itertools_product(*per_cond):
            expanded.setdefault(combo, []).append(rule)

    all_combos = list(itertools_product(*[cond_values[cid] for cid in cond_ids]))
    missing = [dict(zip(cond_ids, combo)) for combo in all_combos if combo not in expanded]
    contradictions = [
        {
            "combination": dict(zip(cond_ids, combo)),
            "rules": [rule.get("id", "?") for rule in combo_rules],
        }
        for combo, combo_rules in expanded.items()
        if len({_rule_action_signature(rule) for rule in combo_rules}) > 1
    ]

    return {
        "total_space": total_space,
        "covered": total_covered,
        "complete": len(missing) == 0,
        "missing": missing,
        "contradictions": contradictions,
        "large_table_warning": large_warning,
        "exhaustive": True,
        "max_combinations": max_combinations,
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
        rule_conditions = _decision_table_rule_conditions(sections)
        extra["applicability_rows"] = _decision_table_applicability_rows(sections)
        extra["rule_conditions"] = rule_conditions
    elif artifact_type == "care-pathway":
        sections = data.get("sections") or {}
        extra["pathway_tree"] = _care_pathway_tree(sections.get("steps") or [])
        extra["step_rows"] = _care_pathway_step_rows(sections)
        extra["transition_rows"] = _care_pathway_transition_rows(sections)

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
    artifact_file = resolve_structured_artifact_file(td, artifact)
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
    output_stem = artifact_file.stem

    written = _render_from_templates(data, artifact_dir, output_stem)

    click.echo(f"Rendered {len(written)} view(s) for '{artifact}' ({artifact_type or 'generic'}):")
    for path in written:
        click.echo(f"  {path}")
