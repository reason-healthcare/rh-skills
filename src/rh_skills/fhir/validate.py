"""Structural validation for FHIR R4 resources.

Per-resource-type required-field checks.  Returns a list of validation
error strings.  Detects ``TODO:MCP-UNREACHABLE`` placeholders as errors.
"""

from __future__ import annotations

import json
import re
from typing import Any

_MCP_UNREACHABLE_RE = re.compile(r"TODO:MCP-UNREACHABLE", re.IGNORECASE)

# Required-field rules per resourceType.
# Each entry is a list of (json_path_description, check_function) tuples.
# check_function receives the resource dict and returns an error string or None.

def _has_field(resource: dict, field: str, label: str | None = None) -> str | None:
    """Return error if top-level field is missing or empty."""
    val = resource.get(field)
    if val is None or val == "" or val == []:
        return f"Missing required field: {label or field}"
    return None


def _has_nested(resource: dict, path: list[str], label: str) -> str | None:
    """Return error if a nested path is missing."""
    current: Any = resource
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and current:
            current = current[0].get(key) if isinstance(current[0], dict) else None
        else:
            current = None
        if current is None:
            return f"Missing required structure: {label}"
    return None


def _check_plan_definition(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "type", "PlanDefinition.type"):
        errors.append(e)
    if e := _has_field(r, "action", "PlanDefinition.action[]"):
        errors.append(e)
        return errors

    plan_type_code = ""
    plan_type = r.get("type")
    type_codings: list[Any] = []
    if plan_type is not None:
        if not isinstance(plan_type, dict):
            errors.append("PlanDefinition.type must be an object")
        else:
            coding = plan_type.get("coding", [])
            if coding is None:
                type_codings = []
            elif not isinstance(coding, list):
                errors.append("PlanDefinition.type.coding must be an array")
            else:
                type_codings = coding
    if type_codings and isinstance(type_codings[0], dict):
        plan_type_code = str(type_codings[0].get("code", ""))

    if plan_type_code != "eca-rule":
        return errors

    actions = r.get("action", [])
    if not isinstance(actions, list):
        errors.append("PlanDefinition.action must be an array")
        return errors
    has_cql_expression = False

    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"PlanDefinition.action[{i}] must be an object")
            continue

        conditions = action.get("condition", [])
        if not conditions:
            errors.append(
                f"PlanDefinition.action[{i}] missing condition[] for eca-rule"
            )
            continue

        for j, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                errors.append(
                    f"PlanDefinition.action[{i}].condition[{j}] must be an object"
                )
                continue

            kind = condition.get("kind")
            if kind not in {"applicability", "start", "stop"}:
                errors.append(
                    f"PlanDefinition.action[{i}].condition[{j}] has invalid or missing kind"
                )

            expression = condition.get("expression")
            if not isinstance(expression, dict):
                errors.append(
                    f"PlanDefinition.action[{i}].condition[{j}] missing expression"
                )
                continue

            language = expression.get("language")
            expr = expression.get("expression")
            if not language:
                errors.append(
                    f"PlanDefinition.action[{i}].condition[{j}].expression missing language"
                )
            if not expr:
                errors.append(
                    f"PlanDefinition.action[{i}].condition[{j}].expression missing expression"
                )

            if isinstance(language, str) and "cql" in language.lower():
                has_cql_expression = True

    if has_cql_expression and not r.get("library"):
        errors.append(
            "PlanDefinition.library[] is required for eca-rule resources using CQL expressions"
        )
    return errors


def _check_measure(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "group", "Measure.group[]"):
        errors.append(e)
    elif isinstance(r.get("group"), list):
        for i, group in enumerate(r["group"]):
            pops = group.get("population", [])
            if not pops:
                errors.append(f"Measure.group[{i}] missing population[]")
            else:
                pop_codes = {
                    p.get("code", {}).get("coding", [{}])[0].get("code", "")
                    for p in pops if isinstance(p, dict)
                }
                for required in ("numerator", "denominator"):
                    if required not in pop_codes:
                        errors.append(f"Measure.group[{i}] missing {required} population")
    if e := _has_field(r, "scoring", "Measure.scoring"):
        errors.append(e)
    return errors


def _check_questionnaire(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "item", "Questionnaire.item[]"):
        errors.append(e)
    elif isinstance(r.get("item"), list):
        for i, item in enumerate(r["item"]):
            if not item.get("linkId"):
                errors.append(f"Questionnaire.item[{i}] missing linkId")
    return errors


def _check_value_set(r: dict) -> list[str]:
    errors = []
    compose = r.get("compose")
    if not compose or not compose.get("include"):
        errors.append("Missing required structure: ValueSet.compose.include[]")
    return errors


def _check_evidence(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "certainty", "Evidence.certainty[]"):
        errors.append(e)
    return errors


def _check_library(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "type", "Library.type"):
        errors.append(e)
    return errors


def _check_concept_map(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "group", "ConceptMap.group[]"):
        errors.append(e)
    return errors


def _check_activity_definition(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "kind", "ActivityDefinition.kind"):
        errors.append(e)
    return errors


def _check_evidence_variable(r: dict) -> list[str]:
    errors = []
    if e := _has_field(r, "characteristic", "EvidenceVariable.characteristic[]"):
        errors.append(e)
    return errors


_RESOURCE_CHECKERS: dict[str, Any] = {
    "PlanDefinition": _check_plan_definition,
    "Measure": _check_measure,
    "Questionnaire": _check_questionnaire,
    "ValueSet": _check_value_set,
    "Evidence": _check_evidence,
    "Library": _check_library,
    "ConceptMap": _check_concept_map,
    "ActivityDefinition": _check_activity_definition,
    "EvidenceVariable": _check_evidence_variable,
}


def validate_resource(resource: dict) -> list[str]:
    """Validate a FHIR resource dict and return a list of error strings.

    Checks:
    1. ``resourceType`` is present
    2. ``id`` is present
    3. Per-type required-field rules
    4. ``TODO:MCP-UNREACHABLE`` placeholder detection
    """
    errors: list[str] = []

    rt = resource.get("resourceType")
    if not rt:
        errors.append("Missing resourceType")
        return errors  # can't do type-specific checks

    if not resource.get("id"):
        errors.append("Missing id")

    checker = _RESOURCE_CHECKERS.get(rt)
    if checker:
        errors.extend(checker(resource))

    # Scan for MCP-UNREACHABLE placeholders anywhere in the resource
    resource_json = json.dumps(resource)
    mcp_matches = _MCP_UNREACHABLE_RE.findall(resource_json)
    if mcp_matches:
        errors.append(
            f"Contains {len(mcp_matches)} TODO:MCP-UNREACHABLE placeholder(s)"
        )

    return errors


def validate_resources(resources: list[dict]) -> dict[str, list[str]]:
    """Validate multiple resources. Returns {resource_label: [errors]}."""
    results: dict[str, list[str]] = {}
    for r in resources:
        label = f"{r.get('resourceType', 'Unknown')}/{r.get('id', '?')}"
        errs = validate_resource(r)
        if errs:
            results[label] = errs
    return results
