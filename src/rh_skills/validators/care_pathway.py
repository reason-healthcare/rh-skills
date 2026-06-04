"""
Care pathway validation

Validates care-pathway artifacts for:
- Required field completeness
- Flat step model (optional parent_id + applicability_condition)
- Optional rule/action linkage to decision-table logic
- L2/L3 boundary enforcement (no FHIR-specific fields at L2)
- Transition integrity
"""

from typing import Dict, List, Tuple, Any, Set


def _check_fhir_field_leakage(data: dict, path: str = "") -> List[str]:
    """Recursively check for FHIR-specific fields at L2 level."""
    fhir_fields = []
    legacy_fields = {
        "event_id",
        "event_ref",
        "fhir_plan_definition_id",
        "is_leaf",
        "next",
        "order",
        "step",
        "sub_pathway_reference",
        "substep",
        "substeps",
    }
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check for forbidden field names
            if key.startswith("fhir_"):
                fhir_fields.append(current_path)
            elif key in legacy_fields:
                fhir_fields.append(current_path)
            
            # Recurse into nested structures
            fhir_fields.extend(_check_fhir_field_leakage(value, current_path))
    
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            current_path = f"{path}[{idx}]"
            fhir_fields.extend(_check_fhir_field_leakage(item, current_path))
    
    return fhir_fields


def validate_care_pathway(
    artifact_data: dict,
    *,
    emit_callback=None,
) -> Tuple[int, int]:
    """
    Validate care-pathway artifact structure and completeness.
    
    Returns:
        (errors, warnings) tuple
    """
    errors = 0
    warnings = 0
    
    def report_error(msg: str):
        nonlocal errors
        if emit_callback:
            emit_callback("ERROR", msg)
        errors += 1
    
    def report_warn(msg: str):
        nonlocal warnings
        if emit_callback:
            emit_callback("WARN", msg)
        warnings += 1
    
    # Check for FHIR field leakage (L2 should be FHIR-agnostic)
    fhir_leaks = _check_fhir_field_leakage(artifact_data)
    for leak in fhir_leaks:
        field_name = leak.rsplit(".", 1)[-1].split("[", 1)[0]
        if field_name in {"event_id", "event_ref"}:
            report_error(f"  L2 schema violation: forbidden field '{leak}' — use 'event' for L2-native references")
        elif field_name in {"substep"}:
            report_error(f"  L2 schema violation: forbidden field '{leak}' — use 'id' for substep identifiers")
        elif field_name in {"step", "order", "next", "sub_pathway_reference", "is_leaf", "fhir_plan_definition_id"}:
            report_error(f"  L2 schema violation: legacy field '{leak}' — remove it from the care-pathway artifact")
        else:
            report_error(f"  L2 schema violation: FHIR-specific field '{leak}' — remove from L2 artifact")
    
    sections = artifact_data.get("sections", {})
    
    # Validate required sections
    steps = sections.get("steps", [])
    
    if not steps or len(steps) == 0:
        report_error("  care-pathway: steps section is empty")
        return errors, warnings
    
    step_ids: Set[str] = set()
    for idx, phase in enumerate(steps, start=1):
        if not isinstance(phase, dict):
            report_error(f"  care-pathway: phase #{idx} is not a dict")
            continue

        phase_id = phase.get("id")
        if not phase_id:
            report_error(f"  care-pathway: phase #{idx} missing required 'id' field")
            phase_id = f"#{idx}"
        else:
            step_ids.add(phase_id)

        if not phase.get("code") and not phase.get("label"):
            report_error(f"  care-pathway: phase '{phase_id or idx}' missing 'code' or 'label' field")

        if not phase.get("description"):
            report_warn(f"  care-pathway: phase '{phase_id or idx}' missing recommended 'description' field")

        if "substeps" in phase:
            report_error(
                f"  care-pathway: phase '{phase_id}' uses legacy nested 'substeps' — use flat steps with parent_id"
            )

        rule_id = phase.get("rule_id")
        if rule_id is not None and not isinstance(rule_id, str):
            report_error(
                f"  care-pathway: phase '{phase_id or idx}' has non-string rule_id"
            )
        elif isinstance(rule_id, str) and not rule_id.strip():
            report_error(
                f"  care-pathway: phase '{phase_id or idx}' has empty rule_id"
            )

        action_labels = phase.get("action_labels")
        if action_labels is not None:
            if not isinstance(action_labels, list):
                report_error(
                    f"  care-pathway: phase '{phase_id or idx}' action_labels must be a list"
                )
            else:
                for action_idx, action_label in enumerate(action_labels, start=1):
                    if not isinstance(action_label, str) or not action_label.strip():
                        report_error(
                            f"  care-pathway: phase '{phase_id or idx}' action_labels[{action_idx}] must be a non-empty string"
                        )
            if not rule_id:
                report_warn(
                    f"  care-pathway: phase '{phase_id or idx}' uses action_labels without rule_id; "
                    "formalize will treat them as descriptive only"
                )

    # Validate step relationships and transitions
    for idx, phase in enumerate(steps, start=1):
        if not isinstance(phase, dict):
            continue
        phase_id = phase.get("id", f"#{idx}")
        parent_id = phase.get("parent_id")
        if parent_id and parent_id not in step_ids:
            report_error(
                f"  care-pathway: phase '{phase_id}' references unknown parent_id '{parent_id}'"
            )

    transitions = sections.get("transitions", [])
    if transitions and not isinstance(transitions, list):
        report_error("  care-pathway: transitions must be a list")
        return errors, warnings
    for idx, transition in enumerate(transitions or [], start=1):
        if not isinstance(transition, dict):
            report_error(f"  care-pathway: transition #{idx} is not a dict")
            continue
        from_id = transition.get("from_id")
        to_id = transition.get("to_id")
        if not from_id or not to_id:
            report_error(f"  care-pathway: transition #{idx} missing from_id or to_id")
            continue
        if from_id not in step_ids:
            report_error(f"  care-pathway: transition #{idx} references unknown from_id '{from_id}'")
        if to_id not in step_ids:
            report_error(f"  care-pathway: transition #{idx} references unknown to_id '{to_id}'")

    return errors, warnings
