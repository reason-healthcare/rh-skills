"""
Decision table validation

Validates decision-table artifacts for:
- Condition coverage and reuse patterns
- Event sequencing consistency
- Pre-requisite condition detection
- Evidence traceability completeness
- FHIR mapping completeness
"""

from typing import Dict, List, Tuple, Any, Set


def validate_decision_table(
    artifact_data: dict,
    *,
    emit_callback=None,
) -> Tuple[int, int]:
    """
    Validate decision-table artifact structure and completeness.
    
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
    
    sections = artifact_data.get("sections", {})
    
    # Validate required sections exist
    events = sections.get("events", [])
    conditions = sections.get("conditions", [])
    actions = sections.get("actions", [])
    rules = sections.get("rules", [])
    pathway_phases = sections.get("pathway_phases")
    
    if not events or len(events) == 0:
        report_error("  decision-table: events section is empty")
        return errors, warnings
    
    if not conditions or len(conditions) == 0:
        report_warn("  decision-table: conditions section is empty (no conditional logic?)")
    
    if not actions or len(actions) == 0:
        report_error("  decision-table: actions section is empty")
        return errors, warnings
    
    if not rules or len(rules) == 0:
        report_error("  decision-table: rules section is empty")
        return errors, warnings
    
    # Build lookup maps
    event_ids = {e["id"] for e in events if isinstance(e, dict) and "id" in e}
    condition_ids = {c["id"] for c in conditions if isinstance(c, dict) and "id" in c}
    action_ids = {a["id"] for a in actions if isinstance(a, dict) and "id" in a}
    
    # Validate pathway_phases if present
    if pathway_phases:
        if not isinstance(pathway_phases, list) or len(pathway_phases) == 0:
            report_error("  decision-table: pathway_phases present but empty or invalid")
        else:
            phase_ids = {p["id"] for p in pathway_phases if isinstance(p, dict) and "id" in p}
            
            # Check that events reference valid phases
            for event in events:
                if not isinstance(event, dict):
                    continue
                phase = event.get("phase")
                if phase and phase not in phase_ids:
                    report_error(
                        f"  decision-table: event '{event.get('id')}' references "
                        f"unknown phase '{phase}'"
                    )
            
            # Check that all events with pathway_phases have phase assignment
            for event in events:
                if not isinstance(event, dict):
                    continue
                if not event.get("phase"):
                    report_warn(
                        f"  decision-table: event '{event.get('id')}' has no phase assignment "
                        f"(pathway_phases present but event.phase missing)"
                    )
    
    # Validate rules reference valid events, conditions, actions
    condition_usage: Dict[str, int] = {}  # Track how often each condition is used
    
    for idx, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            report_error(f"  decision-table: rule #{idx} is not a dict")
            continue
        
        rule_id = rule.get("id", f"#{idx}")
        
        # Check event reference
        event = rule.get("event")
        if not event:
            report_error(f"  decision-table: rule '{rule_id}' missing event field")
        elif event not in event_ids:
            report_error(f"  decision-table: rule '{rule_id}' references unknown event '{event}'")
        
        # Check conditions (when clause)
        when_clause = rule.get("when", {})
        if isinstance(when_clause, dict):
            for cond_id in when_clause.keys():
                if cond_id not in condition_ids:
                    report_error(
                        f"  decision-table: rule '{rule_id}' references unknown condition '{cond_id}'"
                    )
                else:
                    condition_usage[cond_id] = condition_usage.get(cond_id, 0) + 1
        
        # Check action reference
        action = rule.get("action")
        if not action:
            report_error(f"  decision-table: rule '{rule_id}' missing action field")
        elif action not in action_ids:
            report_error(f"  decision-table: rule '{rule_id}' references unknown action '{action}'")
        
        # Check rationale (evidence traceability)
        if not rule.get("rationale"):
            report_warn(f"  decision-table: rule '{rule_id}' missing rationale field")
    
    # Check for orphaned conditions (defined but never used)
    for cond_id in condition_ids:
        if cond_id not in condition_usage:
            report_warn(
                f"  decision-table: condition '{cond_id}' defined but never used in rules "
                f"(consider removing or add to rules)"
            )
    
    # Detect potential condition reuse opportunities
    # (warn if similar condition descriptions exist)
    condition_descriptions = {}
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        cond_id = condition.get("id")
        desc = condition.get("description", "").lower().strip()
        if desc and cond_id:
            if desc in condition_descriptions:
                report_warn(
                    f"  decision-table: conditions '{condition_descriptions[desc]}' and '{cond_id}' "
                    f"have identical descriptions (possible duplication?)"
                )
            else:
                condition_descriptions[desc] = cond_id
    
    # Check FHIR mapping completeness
    fhir_mapping = artifact_data.get("fhir_mapping", {})
    if not fhir_mapping:
        report_warn("  decision-table: fhir_mapping section missing")
    else:
        required_fhir_fields = ["profile", "plan_definition_type", "library", "subject"]
        for field in required_fhir_fields:
            if not fhir_mapping.get(field):
                report_warn(f"  decision-table: fhir_mapping.{field} missing")
    
    # Check actions have FHIR activity definition IDs
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if not action.get("fhir_activity_definition"):
            report_warn(
                f"  decision-table: action '{action_id}' missing fhir_activity_definition "
                f"(required for formalization)"
            )
    
    return errors, warnings
