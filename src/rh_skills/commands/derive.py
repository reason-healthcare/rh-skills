"""
derive.py - Auto-derive artifacts from existing L2 structured artifacts.

Currently supports fallback care-pathway derivation from decision tables with
pathway_phases metadata.
"""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


yaml = YAML()
yaml.preserve_quotes = True
yaml.default_flow_style = False
yaml.width = 4096


def _topics_root() -> Path:
    return Path("topics")


def _find_decision_table(from_decision_table: str) -> tuple[Path | None, Path | None]:
    topics_dir = _topics_root()
    if not topics_dir.exists():
        return None, None

    for topic in topics_dir.iterdir():
        if not topic.is_dir():
            continue
        structured_dir = topic / "structured"
        if not structured_dir.exists():
            continue
        dt_dir = structured_dir / from_decision_table
        dt_file = dt_dir / f"{from_decision_table}.yaml"
        if dt_file.exists():
            return dt_file, topic
    return None, None


def _step_label(text: str) -> str:
    return str(text or "").replace("-", " ").replace("_", " ").strip().title()


def _phase_summary(event_labels: list[str]) -> str:
    if not event_labels:
        return ""
    unique_labels: list[str] = []
    seen: set[str] = set()
    for label in event_labels:
        normalized = str(label or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_labels.append(normalized)
    if not unique_labels:
        return ""
    if len(unique_labels) == 1:
        return f"Includes recommendation context: {unique_labels[0]}."
    return "Includes recommendation contexts: " + ", ".join(unique_labels) + "."


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def derive_pathway(from_decision_table: str, pathway_id: str | None, force: bool):
    """
    Auto-generate a fallback care-pathway scaffold from decision-table phases.

    Reads `sections.pathway_phases[]` and aligned `events[].phase` metadata from
    the source decision table and generates a care-pathway artifact using the
    current flat `steps[]` + `parent_id` model.
    """
    import click

    topics_dir = _topics_root()
    if not topics_dir.exists():
        click.echo("Error: topics/ directory not found. Run from repository root.", err=True)
        raise SystemExit(1)

    dt_path, topic_dir = _find_decision_table(from_decision_table)
    if not dt_path or not topic_dir:
        click.echo(
            f"Error: Decision table '{from_decision_table}' not found in topics/*/structured/",
            err=True,
        )
        raise SystemExit(1)

    click.echo(f"Loading decision table: {dt_path}")
    with open(dt_path) as f:
        dt_data = yaml.load(f) or {}

    sections = dt_data.get("sections")
    if not isinstance(sections, dict):
        click.echo("Error: Decision table missing 'sections' field", err=True)
        raise SystemExit(1)

    pathway_phases = sections.get("pathway_phases")
    if not isinstance(pathway_phases, list) or not pathway_phases:
        click.echo(
            f"Error: Decision table '{from_decision_table}' lacks non-empty pathway_phases metadata.\n"
            "Only decision tables with temporal workflow structure can auto-generate pathways.\n"
            "For diagnostic, screening, or treatment optimization guidelines, manually author the pathway.",
            err=True,
        )
        raise SystemExit(1)

    events = sections.get("events")
    if not isinstance(events, list):
        click.echo("Error: Decision table missing 'events' section", err=True)
        raise SystemExit(1)
    actions = sections.get("actions")
    if not isinstance(actions, list):
        actions = []
    rules = sections.get("rules")
    if not isinstance(rules, list):
        rules = []

    events_by_phase: dict[str, list[dict[str, Any]]] = {}
    event_index: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("id") or "").strip()
        if event_id:
            event_index[event_id] = event
        phase_id = str(event.get("phase") or "").strip()
        if not phase_id:
            continue
        events_by_phase.setdefault(phase_id, []).append(event)

    action_index = {
        str(action.get("id") or "").strip(): action
        for action in actions
        if isinstance(action, dict) and str(action.get("id") or "").strip()
    }
    rules_by_phase: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        phase_id = str(rule.get("phase") or "").strip()
        if not phase_id:
            event = event_index.get(str(rule.get("event") or "").strip()) or {}
            phase_id = str(event.get("phase") or "").strip()
        if not phase_id:
            continue
        rules_by_phase.setdefault(phase_id, []).append(rule)

    if not pathway_id:
        pathway_id = f"{from_decision_table}-pathway"

    pathway_dir = topic_dir / "structured" / pathway_id
    pathway_file = pathway_dir / f"{pathway_id}.yaml"
    if pathway_file.exists() and not force:
        click.echo(
            f"Error: Pathway '{pathway_id}' already exists at {pathway_file}\n"
            "Use --force to overwrite",
            err=True,
        )
        raise SystemExit(1)

    title_source = str(dt_data.get("title") or _step_label(from_decision_table))
    root_label = title_source.removesuffix(" Decision Table").strip() or _step_label(pathway_id)
    root_id = pathway_id

    steps: list[dict[str, Any]] = [{
        "id": root_id,
        "label": root_label,
        "description": (
            f"Overall pathway scaffold derived from decision-table '{from_decision_table}'."
        ),
    }]
    transitions: list[dict[str, Any]] = []
    phase_step_ids: list[str] = []

    for phase in pathway_phases:
        if not isinstance(phase, dict):
            continue
        phase_id = str(phase.get("id") or "").strip()
        if not phase_id:
            continue
        phase_step_ids.append(phase_id)
        phase_description = str(phase.get("description") or "").strip()
        phase_event_labels = [
            str(event.get("label") or event.get("id") or "").strip()
            for event in events_by_phase.get(phase_id, [])
            if isinstance(event, dict)
        ]
        event_summary = _phase_summary(phase_event_labels)
        description_parts = [part for part in [phase_description, event_summary] if part]
        step = {
            "id": phase_id,
            "label": str(phase.get("label") or _step_label(phase_id)),
            "description": " ".join(description_parts).strip() or f"Derived phase '{phase_id}'.",
            "parent_id": root_id,
        }

        phase_rules = rules_by_phase.get(phase_id, [])
        phase_rule_ids = _dedupe_strings([
            str(rule.get("id") or "").strip()
            for rule in phase_rules
            if isinstance(rule, dict)
        ])
        if phase_rule_ids:
            if len(phase_rule_ids) == 1:
                step["rule_id"] = phase_rule_ids[0]
            else:
                step["rule_ids"] = phase_rule_ids

            action_labels: list[str] = []
            evidence_ids: list[str] = []
            for rule in phase_rules:
                if not isinstance(rule, dict):
                    continue
                for claim_id in (rule.get("evidence_traceability_ids") or []):
                    if isinstance(claim_id, str):
                        evidence_ids.append(claim_id)
                for action_id in (rule.get("then") or []):
                    action_def = action_index.get(str(action_id).strip()) or {}
                    action_label = str(action_def.get("label") or action_id or "").strip()
                    if action_label:
                        action_labels.append(action_label)
            deduped_labels = _dedupe_strings(action_labels)
            if deduped_labels:
                step["action_labels"] = deduped_labels
            deduped_evidence_ids = _dedupe_strings(evidence_ids)
            if deduped_evidence_ids:
                step["evidence_traceability_ids"] = deduped_evidence_ids

        steps.append(step)

    for idx in range(len(phase_step_ids) - 1):
        transitions.append({
            "from_id": phase_step_ids[idx],
            "to_id": phase_step_ids[idx + 1],
            "description": "Proceed to the next derived clinical phase.",
        })

    evidence_traceability = sections.get("evidence_traceability")
    if not isinstance(evidence_traceability, list):
        evidence_traceability = []

    pathway_data = {
        "id": pathway_id,
        "name": pathway_id,
        "title": f"Pathway For {title_source}",
        "version": "0.1.0",
        "status": "draft",
        "domain": dt_data.get("domain", "clinical"),
        "description": (
            f"Fallback care-pathway scaffold derived from {from_decision_table} decision table.\n"
            f"Uses the current flat steps model with parent_id hierarchy.\n\n"
            "Use this only when direct care-pathway authoring is struggling to keep "
            "recommendation linkage aligned with the decision-table.\n"
            "Review and refine the generated pathway before use.\n"
            f"Regenerate using: rh-skills promote derive pathway --from-decision-table {from_decision_table} --force"
        ),
        "derived_from": [from_decision_table],
        "artifact_type": "care-pathway",
        "clinical_question": (
            f"How should the {dt_data.get('domain', 'clinical')} workflow be organized across care phases?"
        ),
        "sections": {
            "summary": (
                f"This pathway scaffold organizes the {dt_data.get('domain', 'clinical')} care continuum "
                f"into {len(phase_step_ids)} derived clinical phases from the decision-table phase model."
            ),
            "evidence_traceability": evidence_traceability,
            "steps": steps,
            "transitions": transitions,
        },
        "concerns": [],
    }

    pathway_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Writing pathway: {pathway_file}")
    with open(pathway_file, "w") as f:
        yaml.dump(pathway_data, f)

    click.echo(f"✓ Care pathway '{pathway_id}' generated successfully")
    click.echo(f"  Source: {from_decision_table}")
    click.echo(f"  Phases: {len(phase_step_ids)}")
    click.echo(f"  Phase-linked events observed: {sum(len(events_by_phase.get(p, [])) for p in phase_step_ids)}")
    click.echo(f"  Structure: flat steps[] with parent_id")
    click.echo("  Intended use: fallback scaffold for recommendation-to-pathway alignment repair")
    click.echo(f"  Location: {pathway_file}")
