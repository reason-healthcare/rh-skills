"""rh-skills formalize — Convert L2 structured artifacts to FHIR R4 JSON."""

import base64
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import click
from ruamel.yaml import YAML

from rh_skills.commands.formalize_config import load_formalize_config
from rh_skills.common import (
    append_topic_event,
    config_value,
    log_info,
    log_warn,
    now_iso,
    repo_root,
    require_topic,
    require_tracking,
    save_tracking,
    sha256_file,
    today_date,
    topic_dir,
)
from rh_skills.fhir.normalize import (
    ALLOWED_RESOURCE_TYPES,
    normalize_resource,
    to_kebab_case,
)
from rh_skills.fhir.validate import validate_resource


# ── CQL Content Embedding ─────────────────────────────────────────────────────

def _find_best_cql(cql_files: list[Path], lib_name: str) -> Path | None:
    """Return the CQL file that best matches a Library resource name."""
    if not cql_files:
        return None
    if len(cql_files) == 1:
        return cql_files[0]
    for f in cql_files:
        if f.stem == lib_name:
            return f
    lib_lower = lib_name.lower()
    for f in cql_files:
        if f.stem.lower() == lib_lower:
            return f
    return cql_files[0]


def _embed_cql_in_library(library_path: Path, computable_dir: Path) -> bool:
    """Embed the best-matching CQL file as a base64 content item in a Library JSON.

    Returns True if a CQL file was found and embedded, False otherwise.
    """
    cql_files = sorted(computable_dir.glob("*.cql"))
    if not cql_files:
        return False

    resource = json.loads(library_path.read_text())
    if resource.get("resourceType") != "Library":
        return False

    cql_file = _find_best_cql(cql_files, resource.get("name", ""))
    if cql_file is None:
        return False

    b64 = base64.b64encode(cql_file.read_bytes()).decode("ascii")
    content = [c for c in resource.get("content", []) if c.get("contentType") != "text/cql"]
    content.append({"contentType": "text/cql", "data": b64})
    resource["content"] = content
    library_path.write_text(json.dumps(resource, indent=2, ensure_ascii=False) + "\n")
    return True


# ── Strategy Registry ──────────────────────────────────────────────────────────

STRATEGY_REGISTRY: dict[str, dict] = {
    "evidence-summary": {
        "primary": "Evidence",
        "supporting": ["EvidenceVariable", "Citation"],
        "description": "Evidence + EvidenceVariable + Citation",
    },
    "decision-table": {
        "primary": "PlanDefinition",
        "supporting": ["Library", "ActivityDefinition"],
        "description": "PlanDefinition (eca-rule) + ActivityDefinition + Library (CQL)",
    },
    "care-pathway": {
        "primary": "PlanDefinition",
        "supporting": ["ActivityDefinition"],
        "description": "PlanDefinition (clinical-protocol) + ActivityDefinition",
    },
    "terminology": {
        "primary": "ValueSet",
        "supporting": ["ConceptMap"],
        "description": "ValueSet + ConceptMap",
    },
    "measure": {
        "primary": "Measure",
        "supporting": ["Library"],
        "description": "Measure + Library (CQL)",
    },
    "assessment": {
        "primary": "Questionnaire",
        "supporting": [],
        "description": "Questionnaire",
    },
    "policy": {
        "primary": "PlanDefinition",
        "supporting": ["Questionnaire"],
        "description": "PlanDefinition (eca-rule) + Questionnaire (DTR)",
    },
    # Added in L2 schema update — new artifact types
    "eligibility-criteria": {
        "primary": "EvidenceVariable",
        "supporting": ["ValueSet"],
        "description": "EvidenceVariable (population characteristics) + ValueSet",
    },
    "risk-factors": {
        "primary": "EvidenceVariable",
        "supporting": ["ValueSet"],
        "description": "EvidenceVariable (risk factor characteristics) + ValueSet",
    },
    # custom is intentionally a named fallback so it produces a warning
    # without silently routing through GENERIC_STRATEGY
    "custom": {
        "primary": "PlanDefinition",
        "supporting": [],
        "description": "generic PlanDefinition (custom — reviewer must specify target)",
    },
}

GENERIC_STRATEGY = {
    "primary": "PlanDefinition",
    "supporting": [],
    "description": "generic pathway-package (fallback)",
}


def _get_strategy(artifact_type: str) -> tuple[dict, bool]:
    """Return (strategy_dict, is_fallback).

    ``custom`` is in the registry but treated as a named fallback so callers
    can distinguish it from a genuinely unknown type.
    """
    if artifact_type in STRATEGY_REGISTRY:
        is_named_fallback = artifact_type == "custom"
        return STRATEGY_REGISTRY[artifact_type], is_named_fallback
    return GENERIC_STRATEGY, True


# ── LLM Integration ───────────────────────────────────────────────────────────

def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke LLM or return stub response."""
    provider = config_value("LLM_PROVIDER", "stub")
    if provider == "stub":
        stub = config_value("RH_STUB_RESPONSE", "Stub response")
        return stub
    raise click.ClickException(
        f"LLM provider '{provider}' not available — set LLM_PROVIDER to a supported provider"
    )


def _build_system_prompt(artifact_type: str, strategy: dict, cfg: dict) -> str:
    """Build a type-specific system prompt for FHIR JSON generation."""
    primary = strategy["primary"]
    supporting = strategy.get("supporting", [])
    all_types = [primary] + supporting
    canonical = cfg["canonical"]
    version = cfg["version"]
    status = cfg["status"]

    return f"""\
You are a healthcare informatics specialist. Your task is to convert a \
semi-structured L2 YAML artifact of type '{artifact_type}' into FHIR R4 JSON resources.

You MUST produce a JSON array of FHIR R4 resources. The primary resource type \
is {primary}. Supporting resource types: {', '.join(supporting) or 'none'}.

Each resource in the array MUST have:
- "resourceType": one of {all_types}
- "id": kebab-case identifier
- "url": canonical URL ({canonical}/<ResourceType>/<id>)
- "version": "{version}"
- "status": "{status}"
- "date": today's date (YYYY-MM-DD)
- "name": PascalCase machine name
- "title": human-readable title

Titles and names MUST be specific to the source artifact's clinical intent.
Do NOT use generic placeholders such as "Decision Table Plan",
"Care Pathway Plan", "Assessment Questionnaire", "Library", or
"<ResourceType> Artifact". Prefer the source artifact's metadata.title,
title, or display when present.

Each resource title should include its FHIR artifact type while remaining
semantically detailed for that specific artifact. For example, prefer
"Community-Acquired Pneumonia Triage PlanDefinition" over
"Decision Table Plan", and "Community-Acquired Pneumonia Triage
ActivityDefinition" over "Activity Definition". Companion resources may add
a precise type-specific qualifier when clinically appropriate, but they should
still name the actual FHIR resource type explicitly.

For CQL: If the artifact contains structured logic (decision rules, measure populations), \
generate a companion CQL library with compilable expressions. Use 'library <Name> version "{version}"', \
'using FHIR version "4.0.1"', 'include FHIRHelpers version "4.0.1"', 'context Patient'. \
If logic is too ambiguous, use '// TODO: <reason>' stubs.

For terminology: If MCP tools are unavailable, use "TODO:MCP-UNREACHABLE" as placeholder codes.

Output ONLY the JSON array. No markdown fences, no explanation."""


def _patch_measure_library_references(resources: list[dict]) -> None:
    """Ensure every Measure in the list references its companion Library by canonical URL.

    Called after both stub-build and LLM-parse paths so the field is always populated.
    """
    library_urls = [
        r["url"]
        for r in resources
        if r.get("resourceType") == "Library" and r.get("url")
    ]
    for resource in resources:
        if resource.get("resourceType") != "Measure":
            continue
        existing = resource.get("library") or []
        # Treat null / empty list as missing
        if not existing and library_urls:
            resource["library"] = library_urls


def _questionnaire_item_type(raw_type: str | None) -> str:
    """Map L2 assessment item types to FHIR Questionnaire item types."""
    normalized = str(raw_type or "").strip().lower()
    mapping = {
        "ordinal": "choice",
        "choice": "choice",
        "likert": "choice",
        "boolean": "boolean",
        "numeric": "integer",
        "number": "integer",
        "integer": "integer",
        "text": "string",
        "string": "string",
        "date": "date",
    }
    return mapping.get(normalized, "choice")


def _answer_option_value(option: dict) -> dict | None:
    """Build a FHIR answerOption.value[x] from an L2 option entry."""
    label = option.get("label")
    value = option.get("value", label)
    if label is not None:
        return {
            "valueCoding": {
                "code": str(value if value is not None else label),
                "display": str(label),
            }
        }
    if isinstance(value, bool):
        return {"valueBoolean": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"valueInteger": value}
    if isinstance(value, float):
        return {"valueDecimal": value}
    if value is None:
        return None
    return {"valueString": str(value)}


def _build_questionnaire_items(artifact_name: str, l2_data: dict | None) -> list[dict]:
    """Build Questionnaire.item stubs from L2 assessment sections."""
    sections = (l2_data or {}).get("sections") or {}
    items = sections.get("items") or []
    if not isinstance(items, list):
        items = []

    questionnaire_items: list[dict] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        link_id = str(item.get("id") or f"q{idx}")
        text = str(
            item.get("text")
            or item.get("label")
            or f"{artifact_name.replace('-', ' ').title()} item {idx}"
        )
        questionnaire_item = {
            "linkId": link_id,
            "text": text,
            "type": _questionnaire_item_type(item.get("type")),
        }

        options = item.get("options") or []
        answer_options = []
        if isinstance(options, list):
            for option in options:
                if not isinstance(option, dict):
                    continue
                value = _answer_option_value(option)
                if value is not None:
                    answer_options.append(value)
        if answer_options:
            questionnaire_item["answerOption"] = answer_options

        questionnaire_items.append(questionnaire_item)

    if questionnaire_items:
        return questionnaire_items

    return [{
        "linkId": "q1",
        "text": "Replace with assessment item text",
        "type": "choice",
    }]


def _build_evidence_variable_characteristics(
    artifact_type: str,
    l2_data: dict | None,
) -> list[dict]:
    """Build EvidenceVariable.characteristic stubs from L2 sections."""
    sections = (l2_data or {}).get("sections") or {}
    characteristics: list[dict] = []

    def add_description(value: str | None) -> None:
        if value:
            characteristics.append({"description": value})

    frames = sections.get("frames") or []
    if isinstance(frames, list):
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            add_description(frame.get("population") and f"Population: {frame['population']}")
            add_description(frame.get("intervention") and f"Intervention: {frame['intervention']}")
            add_description(frame.get("comparison") and f"Comparison: {frame['comparison']}")
            outcomes = frame.get("outcomes") or []
            if isinstance(outcomes, list):
                outcome_values = [str(outcome) for outcome in outcomes if outcome]
                if outcome_values:
                    add_description(f"Outcomes: {'; '.join(outcome_values)}")

    risk_factors = sections.get("risk_factors") or []
    if isinstance(risk_factors, list):
        for risk_factor in risk_factors:
            if not isinstance(risk_factor, dict):
                continue
            factor = risk_factor.get("factor") or risk_factor.get("name") or risk_factor.get("id")
            if not factor:
                continue
            extras = [
                str(risk_factor.get("direction")) if risk_factor.get("direction") else "",
                str(risk_factor.get("magnitude")) if risk_factor.get("magnitude") else "",
            ]
            extras = [entry for entry in extras if entry]
            description = f"Risk factor: {factor}"
            if extras:
                description += f" ({'; '.join(extras)})"
            add_description(description)

    for section_name, prefix in (
        ("populations", "Population"),
        ("interventions", "Intervention"),
        ("comparisons", "Comparison"),
        ("outcomes", "Outcome"),
    ):
        entries = sections.get(section_name) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                label = entry.get("description") or entry.get("name") or entry.get("label") or entry.get("id")
            else:
                label = entry
            if label:
                add_description(f"{prefix}: {label}")

    if characteristics:
        return characteristics

    fallback_by_type = {
        "evidence-summary": "Population/intervention/outcome criteria to be refined from the evidence summary",
        "eligibility-criteria": "Eligibility criterion to be refined into coded inclusion or exclusion logic",
        "risk-factors": "Risk factor characteristic to be refined into coded exposure logic",
    }
    return [{"description": fallback_by_type.get(artifact_type, "Characteristic criteria to be refined")}]


def _activity_definition_kind(raw_type: str | None) -> str:
    """Map L2 care-pathway action types to ActivityDefinition.kind."""
    normalized = str(raw_type or "").strip().lower()
    mapping = {
        "order": "ServiceRequest",
        "servicerequest": "ServiceRequest",
        "referral": "ServiceRequest",
        "assessment": "ServiceRequest",
        "communication": "CommunicationRequest",
        "communicationrequest": "CommunicationRequest",
        "medication": "MedicationRequest",
        "medicationrequest": "MedicationRequest",
        "task": "Task",
    }
    return mapping.get(normalized, "ServiceRequest")


def _build_care_pathway_actions(
    artifact_name: str,
    canonical: str,
    activity_definition_id: str,
    l2_data: dict | None,
) -> list[dict]:
    """Build PlanDefinition.action stubs from L2 care-pathway sections."""
    sections = (l2_data or {}).get("sections") or {}
    steps = sections.get("steps") or []
    transitions = sections.get("transitions") or []
    triggers = sections.get("triggers") or []

    if not isinstance(steps, list):
        steps = []
    if not isinstance(transitions, list):
        transitions = []
    if not isinstance(triggers, list):
        triggers = []

    transition_map: dict[str, list[dict]] = {}
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        from_id = transition.get("from_id")
        to_id = transition.get("to_id")
        if not from_id or not to_id:
            continue
        entry = {
            "actionId": str(to_id),
            "relationship": "before-start",
        }
        if transition.get("description"):
            entry["description"] = str(transition["description"])
        if transition.get("condition"):
            entry["offsetDuration"] = {
                "value": 1,
                "unit": "d",
                "system": "http://unitsofmeasure.org",
                "code": "d",
            }
        transition_map.setdefault(str(from_id), []).append(entry)

    actions: list[dict] = []
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or f"step-{idx}")
        title = str(step.get("label") or step.get("title") or f"Step {idx}")
        description = str(
            step.get("description")
            or step.get("label")
            or f"{artifact_name.replace('-', ' ').title()} pathway step {idx}"
        )
        action = {
            "id": step_id,
            "title": title,
            "description": description,
            "definitionCanonical": f"{canonical}/ActivityDefinition/{activity_definition_id}",
        }
        if step_id in transition_map:
            action["relatedAction"] = transition_map[step_id]
        condition_text = step.get("applicability_condition")
        if condition_text:
            action["condition"] = [{
                "kind": "applicability",
                "expression": {
                    "language": "text/fhirpath",
                    "expression": f"true /* {condition_text} */",
                },
            }]
        if idx == 1 and triggers:
            trigger = triggers[0] if isinstance(triggers[0], dict) else {}
            action["trigger"] = [{
                "type": "named-event",
                "name": str(trigger.get("id") or "pathway-entry"),
            }]
        actions.append(action)

    if actions:
        return actions

    return [{
        "title": "Initial action",
        "description": "Stub action",
    }]


def _build_care_pathway_activity_definition(
    artifact_name: str,
    sup_resource: dict,
    l2_data: dict | None,
) -> None:
    """Populate ActivityDefinition stub details from the first care-pathway step."""
    sections = (l2_data or {}).get("sections") or {}
    steps = sections.get("steps") or []
    if not isinstance(steps, list) or not steps:
        sup_resource["kind"] = "ServiceRequest"
        return

    first_step = steps[0] if isinstance(steps[0], dict) else {}
    label = first_step.get("label") or first_step.get("title") or artifact_name.replace("-", " ").title()
    description = first_step.get("description") or f"Activity stub for {label}"
    sup_resource["kind"] = _activity_definition_kind(first_step.get("action_type"))
    sup_resource["title"] = str(label)
    sup_resource["description"] = str(description)
    sup_resource["intent"] = "proposal"


def _decision_table_action_title(action_def: dict) -> str:
    return str(
        action_def.get("label")
        or action_def.get("title")
        or action_def.get("id")
        or "Decision table action"
    )


def _build_decision_table_activity_definitions(cfg: dict, l2_data: dict | None) -> list[dict]:
    """Build one ActivityDefinition per L2 decision-table action."""
    sections = (l2_data or {}).get("sections") or {}
    actions = sections.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    resources: list[dict] = []
    canonical = cfg["canonical"]
    version = cfg["version"]
    status = cfg["status"]
    today = today_date()

    for idx, action_def in enumerate(actions, start=1):
        if not isinstance(action_def, dict):
            continue
        action_id = to_kebab_case(str(action_def.get("id") or f"action-{idx}")) or f"action-{idx}"
        title = _decision_table_action_title(action_def)
        resource: dict = {
            "resourceType": "ActivityDefinition",
            "id": action_id,
            "url": f"{canonical}/ActivityDefinition/{action_id}",
            "version": version,
            "status": status,
            "date": today,
            "name": _pascal_from_kebab(action_id),
            "title": title,
            "description": str(action_def.get("description") or title),
            "kind": _activity_definition_kind(action_def.get("kind") or action_def.get("type")),
            "intent": str(action_def.get("intent") or "proposal"),
        }
        if action_def.get("do_not_perform") is True:
            resource["doNotPerform"] = True

        code = action_def.get("code")
        if isinstance(code, dict):
            coding = {
                "code": str(code.get("code") or action_id),
            }
            if code.get("system"):
                coding["system"] = str(code["system"])
            if code.get("display"):
                coding["display"] = str(code["display"])
            resource["code"] = {"coding": [coding], "text": title}
        else:
            resource["code"] = {"text": title}

        participants = action_def.get("participants") or action_def.get("participant")
        if isinstance(participants, list):
            participant_entries = []
            for participant in participants:
                if isinstance(participant, dict):
                    role = participant.get("role") or participant.get("type")
                else:
                    role = participant
                if role:
                    participant_entries.append({"type": str(role)})
            if participant_entries:
                resource["participant"] = participant_entries

        documentation = action_def.get("documentation") or []
        if isinstance(documentation, list):
            related_artifacts = []
            for entry in documentation:
                if not isinstance(entry, dict):
                    continue
                related = {"type": str(entry.get("type") or "documentation")}
                if entry.get("text"):
                    related["display"] = str(entry["text"])
                related_artifacts.append(related)
            if related_artifacts:
                resource["relatedArtifact"] = related_artifacts

        resources.append(resource)

    return resources


def _build_decision_table_plan_actions(
    artifact_name: str,
    canonical: str,
    l2_data: dict | None,
) -> list[dict]:
    """Build PlanDefinition.action entries from L2 decision-table rules."""
    sections = (l2_data or {}).get("sections") or {}
    events = sections.get("events") or []
    conditions = sections.get("conditions") or []
    actions = sections.get("actions") or []
    rules = sections.get("rules") or []

    event_index = {
        str(event.get("id")): event
        for event in events
        if isinstance(event, dict) and event.get("id")
    } if isinstance(events, list) else {}
    condition_index = {
        str(condition.get("id")): condition
        for condition in conditions
        if isinstance(condition, dict) and condition.get("id")
    } if isinstance(conditions, list) else {}
    action_index = {
        str(action_def.get("id")): action_def
        for action_def in actions
        if isinstance(action_def, dict) and action_def.get("id")
    } if isinstance(actions, list) else {}

    plan_actions: list[dict] = []
    if isinstance(rules, list):
        for idx, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                continue

            event = event_index.get(str(rule.get("event")))
            then_ids = rule.get("then") or []
            child_actions = []
            if isinstance(then_ids, list):
                for action_ref in then_ids:
                    action_def = action_index.get(str(action_ref))
                    action_id = to_kebab_case(str(action_ref))
                    if not action_id:
                        continue
                    title = _decision_table_action_title(action_def or {"id": action_ref})
                    child_actions.append({
                        "id": action_id,
                        "title": title,
                        "description": str((action_def or {}).get("description") or title),
                        "definitionCanonical": f"{canonical}/ActivityDefinition/{action_id}",
                    })

            title_parts = []
            if event and event.get("label"):
                title_parts.append(str(event["label"]))
            if child_actions:
                title_parts.append(child_actions[0]["title"])
            action_entry: dict = {
                "id": str(rule.get("id") or f"rule-{idx}"),
                "title": " — ".join(title_parts) if title_parts else f"{artifact_name.replace('-', ' ').title()} rule {idx}",
                "description": str(rule.get("description") or (event or {}).get("description") or f"Decision rule {idx}"),
            }

            if event:
                trigger = {
                    "type": str(event.get("trigger_type") or "named-event"),
                    "name": str(event.get("id") or f"event-{idx}"),
                }
                action_entry["trigger"] = [trigger]

            when_map = rule.get("when") or {}
            condition_entries = []
            if isinstance(when_map, dict):
                for cond_id, expected in when_map.items():
                    normalized_expected = str(expected or "").strip().lower()
                    if normalized_expected in {"", "n/a", "na", "*"}:
                        continue
                    condition = condition_index.get(str(cond_id), {})
                    cql_name = _condition_label_to_cql_name(
                        str(condition.get("label") or cond_id or "Condition")
                    )
                    expression = {
                        "language": "text/cql-identifier",
                        "expression": cql_name,
                    }
                    if normalized_expected in {"no", "false", "absent"}:
                        expression = {
                            "language": "text/cql-expression",
                            "expression": f"not {cql_name}",
                        }
                    condition_entries.append({
                        "kind": "applicability",
                        "expression": expression,
                    })
            if condition_entries:
                action_entry["condition"] = condition_entries

            if child_actions:
                action_entry["action"] = child_actions

            plan_actions.append(action_entry)

    if plan_actions:
        return plan_actions

    return [{
        "title": "Initial action",
        "description": "Stub action",
    }]


def _load_approved_formalize_target(topic: str) -> dict | None:
    """Return the approved implementation target from formalize-plan.yaml if present."""
    plan_path = topic_dir(topic) / "process" / "plans" / "formalize-plan.yaml"
    if not plan_path.exists():
        return None

    data = YAML(typ="safe").load(plan_path.read_text()) or {}
    if data.get("status") != "approved":
        raise click.UsageError(
            "formalize-plan.yaml is not approved. Review and approve the plan before formalizing."
        )

    artifacts = data.get("artifacts") or []
    targets = [entry for entry in artifacts if entry.get("implementation_target") is True]
    if len(targets) != 1:
        raise click.UsageError(
            "formalize-plan.yaml must mark exactly one artifact as implementation_target: true."
        )

    target = targets[0]
    if target.get("reviewer_decision") != "approved":
        raise click.UsageError(
            "formalize-plan.yaml target is not approved for implementation."
        )
    return target


def _approved_target_source_artifact(target: dict) -> str | None:
    """Return the L2 artifact name that should be passed to `rh-skills formalize`.

    Backward compatibility:
    - Prefer explicit `source_artifact` on the plan entry.
    - Fall back to the legacy `name` field.
    """
    if not isinstance(target, dict):
        return None
    source_artifact = target.get("source_artifact")
    if source_artifact:
        return str(source_artifact)
    legacy_name = target.get("name")
    if legacy_name:
        return str(legacy_name)
    return None


def _parse_llm_response(raw: str) -> list[dict]:
    """Parse LLM response into list of FHIR resource dicts.

    Handles:
    - Direct JSON array
    - Markdown-fenced JSON (```json ... ```)
    - Single object (wraps in list)
    """
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, list):
        return [r for r in parsed if isinstance(r, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _condition_label_to_cql_name(label: str) -> str:
    """Convert a condition label to a CQL define name (PascalCase, no spaces)."""
    words = re.split(r"[^A-Za-z0-9]+", label)
    return "".join(w.capitalize() for w in words if w)


def _pascal_from_kebab(value: str) -> str:
    return "".join(w.capitalize() for w in to_kebab_case(value).split("-") if w)


def _normalize_legacy_system(system: str) -> str:
    normalized = (system or "").strip().lower()
    aliases = {
        "snomed ct": "http://snomed.info/sct",
        "snomed": "http://snomed.info/sct",
        "loinc": "http://loinc.org",
        "icd-10-cm": "http://hl7.org/fhir/sid/icd-10-cm",
        "icd10-cm": "http://hl7.org/fhir/sid/icd-10-cm",
        "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    }
    return aliases.get(normalized, system)


def _group_value_set_codings(codings: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    seen: set[tuple[str, str]] = set()
    for coding in codings:
        system = (coding.get("system") or "").strip()
        code = (coding.get("code") or "").strip()
        if not system or not code:
            continue
        key = (system.casefold(), code.casefold())
        if key in seen:
            continue
        seen.add(key)
        include = grouped.setdefault(system, {"system": system, "concept": []})
        concept_entry = {"code": code}
        display = (coding.get("display") or "").strip()
        if display:
            concept_entry["display"] = display
        include["concept"].append(concept_entry)
    return list(grouped.values())


def _build_terminology_stub_resources(
    artifact_name: str,
    cfg: dict,
    l2_data: dict | None = None,
) -> list[dict]:
    today = today_date()
    canonical = cfg["canonical"]
    version = cfg["version"]
    status = cfg["status"]
    sections = (l2_data or {}).get("sections") or {}
    value_sets = sections.get("value_sets") or []
    concepts = (l2_data or {}).get("concepts") or []
    concept_index = {
        str(c.get("id", "")).strip(): c
        for c in concepts
        if isinstance(c, dict) and str(c.get("id", "")).strip()
    }

    resources: list[dict] = []
    used_ids: defaultdict[str, int] = defaultdict(int)

    if not isinstance(value_sets, list) or not value_sets:
        value_sets = [{"id": artifact_name, "name": artifact_name}]

    for idx, value_set in enumerate(value_sets, start=1):
        if not isinstance(value_set, dict):
            continue
        raw_id = str(value_set.get("id") or value_set.get("name") or f"{artifact_name}-{idx}")
        base_vs_id = to_kebab_case(raw_id) or to_kebab_case(f"{artifact_name}-{idx}")
        used_ids[base_vs_id] += 1
        vs_id = base_vs_id if used_ids[base_vs_id] == 1 else f"{base_vs_id}-{used_ids[base_vs_id]}"
        vs_name = str(value_set.get("name") or value_set.get("title") or raw_id).strip()

        codings: list[dict] = []

        default_system = _normalize_legacy_system(str(value_set.get("system") or "").strip())
        for entry in value_set.get("codes") or []:
            if isinstance(entry, dict):
                codings.append({
                    "system": _normalize_legacy_system(str(entry.get("system") or default_system)),
                    "code": str(entry.get("code") or ""),
                    "display": str(entry.get("display") or ""),
                })
            elif isinstance(entry, str):
                codings.append({"system": default_system, "code": entry, "display": ""})

        for concept_ref in value_set.get("concept_refs") or []:
            concept = concept_index.get(str(concept_ref).strip())
            if not isinstance(concept, dict):
                continue
            for entry in concept.get("codes") or []:
                if isinstance(entry, dict):
                    codings.append({
                        "system": _normalize_legacy_system(str(entry.get("system") or "")),
                        "code": str(entry.get("code") or ""),
                        "display": str(entry.get("display") or ""),
                    })
            for expansion in concept.get("expansions") or []:
                if isinstance(expansion, dict):
                    codings.append({
                        "system": _normalize_legacy_system(str(expansion.get("system") or default_system)),
                        "code": str(expansion.get("code") or ""),
                        "display": "",
                    })

        for concept in value_set.get("concepts") or []:
            if not isinstance(concept, dict):
                continue
            system = _normalize_legacy_system(str(concept.get("system") or default_system))
            code = str(concept.get("code") or "").strip()
            display = str(concept.get("display") or concept.get("term") or "").strip()
            if code:
                codings.append({"system": system, "code": code, "display": display})
            elif display:
                codings.append({
                    "system": system or "http://snomed.info/sct",
                    "code": "TODO:MCP-UNREACHABLE",
                    "display": display,
                })

        includes = _group_value_set_codings(codings)
        if not includes:
            includes = [{
                "system": "http://snomed.info/sct",
                "concept": [{"code": "TODO:MCP-UNREACHABLE"}],
            }]

        resources.append({
            "resourceType": "ValueSet",
            "id": vs_id,
            "url": f"{canonical}/ValueSet/{vs_id}",
            "version": version,
            "status": status,
            "date": today,
            "name": _pascal_from_kebab(vs_id),
            "title": vs_name or artifact_name.replace("-", " ").title(),
            "compose": {"include": includes},
        })

    concept_maps = sections.get("concept_maps") or sections.get("concept_mappings") or []
    if isinstance(concept_maps, list):
        for idx, concept_map in enumerate(concept_maps, start=1):
            if not isinstance(concept_map, dict):
                continue
            raw_id = str(concept_map.get("id") or concept_map.get("name") or f"{artifact_name}-concept-map-{idx}")
            cm_id = to_kebab_case(raw_id) or to_kebab_case(f"{artifact_name}-concept-map-{idx}")
            source_system = str(concept_map.get("source_system") or "http://example.org/source")
            target_system = str(concept_map.get("target_system") or "http://example.org/target")
            resources.append({
                "resourceType": "ConceptMap",
                "id": cm_id,
                "url": f"{canonical}/ConceptMap/{cm_id}",
                "version": version,
                "status": status,
                "date": today,
                "name": _pascal_from_kebab(cm_id),
                "title": str(concept_map.get("name") or raw_id).replace("-", " ").title(),
                "group": [{"source": source_system, "target": target_system, "element": []}],
            })

    return resources


def _build_stub_resources(
    artifact_name: str,
    artifact_type: str,
    strategy: dict,
    topic: str,
    cfg: dict,
    l2_data: dict | None = None,
) -> list[dict]:
    """Build stub FHIR resources when LLM_PROVIDER=stub."""
    primary = strategy["primary"]
    supporting = strategy.get("supporting", [])
    resource_id = to_kebab_case(artifact_name)
    today = today_date()
    canonical = cfg["canonical"]
    version = cfg["version"]
    status = cfg["status"]

    if artifact_type == "terminology":
        return _build_terminology_stub_resources(artifact_name, cfg, l2_data)

    resources = []

    # Primary resource
    primary_resource: dict = {
        "resourceType": primary,
        "id": resource_id,
        "url": f"{canonical}/{primary}/{resource_id}",
        "version": version,
        "status": status,
        "date": today,
        "name": _pascal_from_kebab(resource_id),
        "title": artifact_name.replace("-", " ").title(),
    }

    # Add type-specific required fields for stubs
    if primary == "PlanDefinition":
        plan_type = "eca-rule" if artifact_type in ("decision-table", "policy") else "clinical-protocol"
        primary_resource["type"] = {"coding": [{"code": plan_type}]}
        if artifact_type == "decision-table" and "Library" in supporting:
            lib_id = f"{resource_id}-{to_kebab_case('Library')}"
            primary_resource["library"] = [f"{canonical}/Library/{lib_id}"]
        if artifact_type == "decision-table" and l2_data:
            primary_resource["action"] = _build_decision_table_plan_actions(
                artifact_name,
                canonical,
                l2_data,
            )
        elif artifact_type == "care-pathway":
            activity_definition_id = f"{resource_id}-{to_kebab_case('ActivityDefinition')}"
            primary_resource["action"] = _build_care_pathway_actions(
                artifact_name,
                canonical,
                activity_definition_id,
                l2_data,
            )
        else:
            primary_resource["action"] = [{"title": "Initial action", "description": "Stub action"}]
    elif primary == "Measure":
        primary_resource["scoring"] = {"coding": [{"code": "proportion"}]}
        primary_resource["group"] = [{
            "population": [
                {"code": {"coding": [{"code": "numerator"}]}, "criteria": {"language": "text/cql-identifier", "expression": "Numerator"}},
                {"code": {"coding": [{"code": "denominator"}]}, "criteria": {"language": "text/cql-identifier", "expression": "Denominator"}},
            ],
        }]
        # Populate Measure.library with the canonical URL of the companion Library
        if "Library" in supporting:
            lib_id = f"{resource_id}-{to_kebab_case('Library')}"
            primary_resource["library"] = [f"{canonical}/Library/{lib_id}"]
    elif primary == "Questionnaire":
        primary_resource["item"] = _build_questionnaire_items(artifact_name, l2_data)
    elif primary == "ValueSet":
        primary_resource["compose"] = {"include": [{"system": "http://snomed.info/sct", "concept": [{"code": "TODO:PLACEHOLDER"}]}]}
    elif primary == "Evidence":
        primary_resource["certainty"] = [{"rating": {"coding": [{"code": "moderate"}]}}]
    elif primary == "EvidenceVariable":
        # Used by eligibility-criteria and risk-factors strategies
        primary_resource["characteristic"] = _build_evidence_variable_characteristics(artifact_type, l2_data)

    resources.append(primary_resource)

    if artifact_type == "decision-table":
        resources.extend(_build_decision_table_activity_definitions(cfg, l2_data))

    # Supporting resources
    for sup_type in supporting:
        if artifact_type == "decision-table" and sup_type == "ActivityDefinition":
            continue
        sup_id = f"{resource_id}-{to_kebab_case(sup_type)}"
        sup_resource: dict = {
            "resourceType": sup_type,
            "id": sup_id,
            "url": f"{canonical}/{sup_type}/{sup_id}",
            "version": version,
            "status": status,
            "date": today,
            "name": _pascal_from_kebab(sup_id),
            "title": f"{artifact_name} {sup_type}".replace("-", " ").title(),
        }
        # Required fields for stubs
        if sup_type == "Library":
            sup_resource["type"] = {"coding": [{"code": "logic-library"}]}
        elif sup_type == "EvidenceVariable":
            sup_resource["characteristic"] = _build_evidence_variable_characteristics(artifact_type, l2_data)
        elif sup_type == "ActivityDefinition":
            if artifact_type == "care-pathway":
                _build_care_pathway_activity_definition(artifact_name, sup_resource, l2_data)
            else:
                sup_resource["kind"] = "ServiceRequest"
        elif sup_type == "ConceptMap":
            sup_resource["group"] = [{"source": "http://example.org", "target": "http://example.org", "element": []}]
        elif sup_type == "Questionnaire":
            sup_resource["item"] = [{"linkId": "q1", "text": "Stub DTR question", "type": "choice"}]

        resources.append(sup_resource)

    return resources


# ── Deterministic Builders (CPG-on-FHIR) ──────────────────────────────────────

def _build_with_deterministic_builders(
    artifact: str,
    artifact_type: str,
    topic: str,
    l2_data: dict,
    merger: Any  # ConditionMerger instance
) -> list[dict]:
    """Build FHIR resources using deterministic CPG builders.
    
    Args:
        artifact: Artifact name
        artifact_type: L2 artifact type (decision-table or care-pathway)
        topic: Topic ID
        l2_data: Parsed L2 artifact data
        merger: ConditionMerger instance for topic-level deduplication
        
    Returns:
        List of FHIR resource dictionaries
    """
    from rh_skills.fhir.builders import (
        DecisionTableBuilder,
        CarePathwayBuilder
    )
    
    resources = []
    
    if artifact_type == "decision-table":
        builder = DecisionTableBuilder(topic, artifact, merger)
        result = builder.build_all_resources(l2_data)
        resources.extend(result.get('PlanDefinition', []))
        resources.extend(result.get('ActivityDefinition', []))
        
    elif artifact_type == "care-pathway":
        # Check if auto-generated from decision table
        metadata = l2_data.get('metadata', {})
        decision_table_id = None
        decision_table_data = None
        
        if metadata.get('auto_generated') and metadata.get('derived_from'):
            decision_table_id = metadata['derived_from'][0]
            # TODO: Load decision table data if available
        
        builder = CarePathwayBuilder(topic, artifact, decision_table_id)
        result = builder.build_all_resources(l2_data, decision_table_data)
        resources.extend(result.get('PlanDefinition', []))
    
    return resources


# ── Click Command ──────────────────────────────────────────────────────────────

@click.command("formalize")
@click.argument("topic")
@click.argument("artifact")
@click.option("--dry-run", is_flag=True, help="Print strategy selection without writing files")
@click.option("--force", is_flag=True, help="Overwrite existing computable files for this artifact")
def formalize(topic, artifact, dry_run, force):
    """Convert an L2 structured artifact to FHIR R4 JSON resources.

    Reads the L2 artifact, selects a type-specific strategy, generates
    FHIR JSON + CQL via LLM, normalizes, and writes to computable/.
    """
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    # Validate artifact exists in structured
    structured = topic_entry.get("structured", [])
    artifact_entry = next(
        (a for a in structured if a.get("name") == artifact),
        None,
    )
    if artifact_entry is None:
        raise click.UsageError(
            f"L2 artifact '{artifact}' not found in topic '{topic}'"
        )

    # Read artifact_type from L2 artifact
    artifact_type = artifact_entry.get("artifact_type", "unknown")

    # Select strategy
    strategy, is_fallback = _get_strategy(artifact_type)
    if artifact_type == "custom":
        log_warn(
            f"Artifact type 'custom' has no prescribed FHIR target. "
            "A generic PlanDefinition stub will be produced. "
            "Reviewer must specify the correct L3 target in formalize-plan.yaml."
        )
    elif is_fallback:
        log_warn(
            f"Unknown artifact type '{artifact_type}'; "
            "falling back to generic pathway-package strategy"
        )

    if dry_run:
        click.echo(f"--- DRY RUN: formalize '{artifact}' ---")
        click.echo(f"Strategy: {strategy['description']} ({'fallback' if is_fallback else artifact_type})")
        click.echo(f"Primary: {strategy['primary']}")
        if strategy.get("supporting"):
            click.echo(f"Supporting: {', '.join(strategy['supporting'])}")
        return

    # Load formalize config — required before generating artifacts
    td = topic_dir(topic)
    cfg = load_formalize_config(td)
    if cfg is None:
        click.echo(
            f"Error: formalize-config.yaml not found for topic '{topic}'.\n"
            f"Run:  rh-skills formalize-config {topic}",
            err=True,
        )
        sys.exit(2)

    approved_target = _load_approved_formalize_target(topic)
    approved_source = _approved_target_source_artifact(approved_target) if approved_target is not None else None
    if approved_target is not None and approved_source != artifact:
        raise click.UsageError(
            f"Artifact '{artifact}' is not the approved implementation target in formalize-plan.yaml. "
            f"Target source_artifact: '{approved_source or '<unknown>'}'."
        )

    # Load L2 YAML content — prefer the registered file path from tracking
    _artifact_file = artifact_entry.get("file")
    if _artifact_file:
        l2_file = Path(_artifact_file) if Path(_artifact_file).is_absolute() else (repo_root() / _artifact_file)
        if not l2_file.exists():
            l2_file = td / "structured" / f"{artifact}.yaml"
    else:
        l2_file = td / "structured" / f"{artifact}.yaml"
    l2_content = ""
    l2_data: dict = {}
    if l2_file.exists():
        l2_content = l2_file.read_text()
        _yaml = YAML()
        try:
            l2_data = _yaml.load(l2_content) or {}
        except Exception:
            l2_data = {}

    # Build prompts and invoke LLM
    system_prompt = _build_system_prompt(artifact_type, strategy, cfg)
    user_prompt = (
        f"Artifact name: {artifact}\n"
        f"Artifact type: {artifact_type}\n"
        f"Topic: {topic}\n"
        f"Date: {today_date()}\n\n"
        f"L2 Content:\n{l2_content}"
    )

    click.echo(f"Formalizing '{artifact}' using {strategy['description']} strategy...")
    
    # Use deterministic builders for decision-table and care-pathway
    if artifact_type in ("decision-table", "care-pathway"):
        from rh_skills.fhir.builders import ConditionMerger, CQLGenerator
        merger = ConditionMerger(topic)
        click.echo(f"Using deterministic CPG-on-FHIR builders...")
        resources = _build_with_deterministic_builders(artifact, artifact_type, topic, l2_data, merger)
        
        # Generate Library resource with CQL content
        cql_gen = CQLGenerator(topic, version=cfg.get("version", "1.0.0"))
        conditions = merger.get_merged_conditions()
        
        library_metadata = {
            "title": l2_data.get("title", f"{topic.replace('-', ' ').title()} Clinical Logic"),
            "description": f"CQL logic library for {topic} topic. Contains condition definitions from decision tables.",
            "author": l2_data.get("author")
        }
        
        library_resource = cql_gen.generate_library(conditions, library_metadata)
        resources.append(library_resource)
        
        click.echo(f"Generated Library resource with {len(conditions)} condition definitions")
    else:
        # Use LLM for other artifact types
        system_prompt = _build_system_prompt(artifact_type, strategy, cfg)
        user_prompt = (
            f"Artifact name: {artifact}\n"
            f"Artifact type: {artifact_type}\n"
            f"Topic: {topic}\n"
            f"Date: {today_date()}\n\n"
            f"L2 Content:\n{l2_content}"
        )
        llm_output = _invoke_llm(system_prompt, user_prompt)
        
        # Parse response
        if llm_output == "Stub response":
            resources = _build_stub_resources(artifact, artifact_type, strategy, topic, cfg, l2_data)
        else:
            resources = _parse_llm_response(llm_output)
            if not resources:
                click.echo("Error: Failed to parse LLM response as FHIR JSON", err=True)
                sys.exit(2)

    # Ensure Measure.library references companion Library resources
    _patch_measure_library_references(resources)

    # Normalize + validate
    computable_dir = td / "computable"
    computable_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    checksums: dict[str, str] = {}
    warnings: list[str] = []
    failures: list[str] = []

    for resource in resources:
        normalize_resource(resource)
        norm_warnings = resource.pop("_normalization_warnings", [])
        warnings.extend(norm_warnings)

        validation_errors = validate_resource(resource)
        if validation_errors:
            for e in validation_errors:
                if "MCP-UNREACHABLE" in e:
                    warnings.append(f"  ⚠ {resource.get('resourceType', '?')}/{resource.get('id', '?')}: {e}")
                else:
                    warnings.append(f"  ⚠ {resource.get('resourceType', '?')}/{resource.get('id', '?')}: {e}")

        rt = resource.get("resourceType", "Unknown")
        rid = resource.get("id", "unknown")
        fname = f"{rt}-{rid}.json"
        fpath = computable_dir / fname

        if fpath.exists() and not force:
            failures.append(f"  ✗ {fname} already exists (use --force to overwrite)")
            continue

        try:
            fpath.write_text(json.dumps(resource, indent=2, ensure_ascii=False) + "\n")
            rel_path = f"topics/{topic}/computable/{fname}"
            written_files.append(rel_path)
            checksums[rel_path] = sha256_file(fpath)
            click.echo(f"  ✓ {fname}")
        except OSError as exc:
            failures.append(f"  ✗ {fname}: {exc}")

    # Embed CQL source as base64 content in any Library JSON that was written,
    # then emit a guidance note if no CQL file was found.
    if "Library" in strategy.get("supporting", []) or strategy["primary"] == "Library":
        library_files = [
            computable_dir / Path(f).name
            for f in written_files
            if Path(f).name.startswith("Library-")
        ]
        embedded_any = False
        for lib_path in library_files:
            if lib_path.exists() and _embed_cql_in_library(lib_path, computable_dir):
                cql_used = _find_best_cql(sorted(computable_dir.glob("*.cql")), "")
                click.echo(f"  ✓ Embedded CQL source in {lib_path.name}")
                embedded_any = True
        if not embedded_any:
            cql_name = "".join(w.capitalize() for w in to_kebab_case(artifact).split("-")) + "Logic"
            click.echo(
                f"  ℹ  No .cql file found in computable/ — use `rh-inf-cql` (author mode) to author"
                f" the CQL library, then re-run `rh-skills formalize` to embed it in the Library JSON",
                err=True,
            )

    # Report warnings
    for w in warnings:
        click.echo(w, err=True)

    # Report failures
    for f in failures:
        click.echo(f, err=True)

    if not written_files:
        click.echo("Error: No files were written", err=True)
        sys.exit(2)

    # Update tracking
    timestamp = now_iso()
    new_entry = {
        "name": artifact,
        "files": written_files,
        "created_at": timestamp,
        "checksums": checksums,
        "converged_from": (approved_target.get("input_artifacts") or [artifact]) if approved_target else [artifact],
        "strategy": artifact_type if not is_fallback else "generic",
    }
    existing_entries = topic_entry.get("computable", []) or []
    topic_entry["computable"] = [
        entry for entry in existing_entries if entry.get("name") != artifact
    ] + [new_entry]

    resource_count = len(written_files)
    strategy_label = artifact_type if not is_fallback else "generic"
    append_topic_event(
        tracking, topic, "computable_converged",
        f"Formalized '{artifact}' using {strategy_label} strategy → {resource_count} resources",
    )
    save_tracking(tracking)

    click.echo(f"\nWrote {resource_count} files to topics/{topic}/computable/")
    click.echo("Event: computable_converged")

    if failures:
        sys.exit(1)
