"""
Decision table validation.

Canonical L2 contract (no legacy aliases):
- sections.pathway_phases (when present) is the only supported phase model location
- events are primary; events may use optional trigger and phase (no phase_order,
  no trigger_type)
- conditions.values[] use explicit "Yes"/"No" values
- every condition is backed by one or more sections.data_elements[] entries
- actions use kind (intent optional)
- rules use phase (optional), not pathway_phase, and must reference event/then;
  when is optional for unconditional event-driven rules
"""

from typing import Dict, List, Tuple, Any, Set

_FHIR_TRIGGER_TYPES = {
    "named-event",
    "periodic",
    "data-changed",
    "data-added",
    "data-modified",
    "data-removed",
    "data-accessed",
    "data-access-ended",
}

_EVIDENCE_STRENGTH_VALUES = {
    "high",
    "moderate",
    "low",
    "very-low",
    "consensus",
    "insufficient",
}
_PROVENANCE_SOURCES = {"source_direct", "inferred"}


def _check_fhir_field_leakage(data: dict, path: str = "") -> List[str]:
    """Recursively check for FHIR-specific fields at L2 level."""
    fhir_fields = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check for forbidden field names
            if key.startswith("fhir_"):
                fhir_fields.append(current_path)
            elif key in ("rule_id", "event_id", "pathway_phase", "phase_order"):
                fhir_fields.append(f"{current_path} (use '{key.replace('_id', '')}' instead)")
            
            # Recurse into nested structures
            fhir_fields.extend(_check_fhir_field_leakage(value, current_path))
    
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            current_path = f"{path}[{idx}]"
            fhir_fields.extend(_check_fhir_field_leakage(item, current_path))
    
    return fhir_fields


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

    def _is_allowed_condition_value(value: Any) -> bool:
        return isinstance(value, str) and value.strip() in {"Yes", "No"}

    # Check for FHIR field leakage (L2 should be FHIR-agnostic)
    fhir_leaks = _check_fhir_field_leakage(artifact_data)
    for leak in fhir_leaks:
        if "rule_id" in leak or "event_id" in leak:
            report_error(f"  L2 schema violation: forbidden field '{leak}' — remove FHIR-specific naming")
        else:
            report_error(f"  L2 schema violation: FHIR-specific field '{leak}' — remove from L2 artifact")
    
    sections = artifact_data.get("sections", {})
    top_level_phases = artifact_data.get("pathway_phases")
    if top_level_phases is not None:
        report_error("  decision-table: legacy top-level 'pathway_phases' is not supported — move to sections.pathway_phases")
    
    # Validate required sections exist
    events = sections.get("events", [])
    conditions = sections.get("conditions", [])
    data_elements = sections.get("data_elements", [])
    actions = sections.get("actions", [])
    rules = sections.get("rules", [])
    pathway_phases = sections.get("pathway_phases")
    evidence_traceability = sections.get("evidence_traceability") or []
    
    if not events or len(events) == 0:
        report_error("  decision-table: events section is empty")
        return errors, warnings
    
    if not conditions or len(conditions) == 0:
        report_warn("  decision-table: conditions section is empty (no conditional logic?)")
    elif not data_elements or len(data_elements) == 0:
        report_error("  decision-table: data_elements section is empty (each condition needs supporting data elements)")
        return errors, warnings
    
    if not actions or len(actions) == 0:
        report_error("  decision-table: actions section is empty")
        return errors, warnings
    
    if not rules or len(rules) == 0:
        report_error("  decision-table: rules section is empty")
        return errors, warnings

    claim_ids: set[str] = set()
    if evidence_traceability:
        if not isinstance(evidence_traceability, list):
            report_error("  decision-table: evidence_traceability must be a list when present")
        else:
            for idx, entry in enumerate(evidence_traceability, start=1):
                if not isinstance(entry, dict):
                    continue
                claim_id = str(entry.get("claim_id") or "").strip()
                if claim_id:
                    claim_ids.add(claim_id)
                strength = entry.get("strength")
                if strength is None or str(strength).strip() == "":
                    report_warn(
                        f"  decision-table: evidence_traceability entry #{idx} missing recommended 'strength' field"
                    )
                    continue
                normalized_strength = str(strength).strip().lower()
                if normalized_strength not in _EVIDENCE_STRENGTH_VALUES:
                    report_error(
                        f"  decision-table: evidence_traceability entry #{idx} has invalid strength '{strength}' "
                        f"(allowed: {', '.join(sorted(_EVIDENCE_STRENGTH_VALUES))})"
                    )

    def _validate_traceability_links(
        *,
        owner_label: str,
        owner_type: str,
        traceability_ids: Any,
    ) -> None:
        if traceability_ids is None:
            if owner_type == "rule":
                report_error(
                    f"  decision-table: {owner_type} '{owner_label}' missing required evidence_traceability_ids[] link(s)"
                )
            else:
                report_warn(
                    f"  decision-table: {owner_type} '{owner_label}' missing recommended evidence_traceability_ids[] link(s)"
                )
            return
        if not isinstance(traceability_ids, list) or not traceability_ids:
            report_error(
                f"  decision-table: {owner_type} '{owner_label}' evidence_traceability_ids must be a non-empty list"
            )
            return
        for idx, claim_id in enumerate(traceability_ids, start=1):
            if not isinstance(claim_id, str) or not claim_id.strip():
                report_error(
                    f"  decision-table: {owner_type} '{owner_label}' evidence_traceability_ids[{idx}] must be a non-empty string"
                )
                continue
            if claim_ids and claim_id.strip() not in claim_ids:
                report_error(
                    f"  decision-table: {owner_type} '{owner_label}' references unknown evidence claim_id '{claim_id.strip()}'"
                )

    def _validate_provenance(
        *,
        owner_label: str,
        owner_type: str,
        provenance: Any,
        traceability_ids: Any,
    ) -> None:
        if provenance is None:
            report_warn(
                f"  decision-table: {owner_type} '{owner_label}' missing recommended provenance metadata"
            )
            return
        if not isinstance(provenance, dict):
            report_error(
                f"  decision-table: {owner_type} '{owner_label}' provenance must be an object when present"
            )
            return
        source = str(provenance.get("source") or "").strip()
        if not source:
            report_error(
                f"  decision-table: {owner_type} '{owner_label}' provenance.source is required when provenance is present"
            )
            return
        if source not in _PROVENANCE_SOURCES:
            report_error(
                f"  decision-table: {owner_type} '{owner_label}' provenance.source '{source}' is invalid "
                f"(allowed: {', '.join(sorted(_PROVENANCE_SOURCES))})"
            )
            return
        if source == "inferred":
            rationale = str(provenance.get("rationale") or "").strip()
            if not rationale:
                report_error(
                    f"  decision-table: {owner_type} '{owner_label}' inferred provenance requires provenance.rationale"
                )
            if not isinstance(traceability_ids, list) or not traceability_ids:
                report_error(
                    f"  decision-table: {owner_type} '{owner_label}' inferred provenance requires non-empty evidence_traceability_ids[]"
                )
    
    # Build lookup maps
    event_ids = {e["id"] for e in events if isinstance(e, dict) and "id" in e}
    condition_ids = {c["id"] for c in conditions if isinstance(c, dict) and "id" in c}
    action_ids = {a["id"] for a in actions if isinstance(a, dict) and "id" in a}
    
    # Validate pathway_phases if present
    phase_ids: Set[str] = set()
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
                    report_error(
                        f"  decision-table: event '{event.get('id')}' has no phase assignment "
                        f"(pathway_phases present but event.phase missing)"
                    )

    # Validate event contract
    for idx, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            report_error(f"  decision-table: event #{idx} is not a dict")
            continue
        event_id = event.get("id", f"#{idx}")
        if event.get("phase_order") is not None:
            report_error(f"  decision-table: event '{event_id}' uses legacy 'phase_order' — remove it")
        if event.get("trigger_type") is not None:
            report_error(
                f"  decision-table: event '{event_id}' uses legacy 'trigger_type' — use event.trigger.type"
            )
        trigger = event.get("trigger")
        if trigger is not None:
            if not isinstance(trigger, dict):
                report_error(f"  decision-table: event '{event_id}' trigger must be an object when present")
            else:
                trigger_type = trigger.get("type")
                if not isinstance(trigger_type, str) or not trigger_type.strip():
                    report_error(f"  decision-table: event '{event_id}' trigger.type is required when trigger is present")
                elif trigger_type not in _FHIR_TRIGGER_TYPES:
                    report_error(
                        f"  decision-table: event '{event_id}' trigger.type '{trigger_type}' is not a supported FHIR trigger type"
                    )
                if trigger_type == "named-event":
                    name = trigger.get("name")
                    if not isinstance(name, str) or not name.strip():
                        report_error(
                            f"  decision-table: event '{event_id}' named-event trigger requires trigger.name"
                        )
                resource_criteria = trigger.get("resource_criteria")
                if resource_criteria is not None and not isinstance(resource_criteria, dict):
                    report_error(
                        f"  decision-table: event '{event_id}' trigger.resource_criteria must be an object when present"
                    )
                timing_window = trigger.get("timing_window")
                if timing_window is not None and not isinstance(timing_window, dict):
                    report_error(
                        f"  decision-table: event '{event_id}' trigger.timing_window must be an object when present"
                    )

    # Validate condition contract
    for idx, condition in enumerate(conditions, start=1):
        if not isinstance(condition, dict):
            report_error(f"  decision-table: condition #{idx} is not a dict")
            continue
        cond_id = condition.get("id", f"#{idx}")
        values = condition.get("values")
        if not isinstance(values, list) or not values:
            report_error(f"  decision-table: condition '{cond_id}' missing required values[]")
            continue
        if not all(_is_allowed_condition_value(v) for v in values):
            report_error(
                f"  decision-table: condition '{cond_id}' values[] must use canonical Yes/No values"
            )

        if condition.get("derivation") is not None:
            report_error(
                f"  decision-table: condition '{cond_id}' uses unsupported 'derivation' — list decomposed criteria explicitly in rules.when{{}}"
            )

    # Validate data element contract
    condition_data_map: Dict[str, int] = {}
    data_element_ids: set[str] = set()
    for idx, data_element in enumerate(data_elements, start=1):
        if not isinstance(data_element, dict):
            report_error(f"  decision-table: data element #{idx} is not a dict")
            continue
        data_element_id = data_element.get("id", f"#{idx}")
        data_element_ids.add(data_element_id)
        condition_id = data_element.get("condition_id")
        if not condition_id:
            report_error(f"  decision-table: data element '{data_element_id}' missing required condition_id")
        elif condition_id not in condition_ids:
            report_error(
                f"  decision-table: data element '{data_element_id}' references unknown condition '{condition_id}'"
            )
        else:
            condition_data_map[condition_id] = condition_data_map.get(condition_id, 0) + 1
        if not data_element.get("label"):
            report_error(f"  decision-table: data element '{data_element_id}' missing required label")

    for cond_id in condition_ids:
        if condition_data_map.get(cond_id, 0) == 0:
            report_error(
                f"  decision-table: condition '{cond_id}' has no corresponding data_elements entry"
            )

    child_action_counts: Dict[str, int] = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        parent_action_id = action.get("parent_action_id")
        if isinstance(parent_action_id, str) and parent_action_id.strip():
            child_action_counts[parent_action_id.strip()] = child_action_counts.get(parent_action_id.strip(), 0) + 1

    # Validate action contract
    for idx, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            report_error(f"  decision-table: action #{idx} is not a dict")
            continue
        action_id = action.get("id", f"#{idx}")
        if action.get("type") is not None:
            report_error(f"  decision-table: action '{action_id}' uses forbidden 'type' — use canonical 'kind'")
        if not action.get("kind"):
            report_error(f"  decision-table: action '{action_id}' missing required 'kind' field")
        parent_action_id = action.get("parent_action_id")
        if parent_action_id:
            if parent_action_id == action_id:
                report_error(f"  decision-table: action '{action_id}' cannot parent itself")
            elif parent_action_id not in action_ids:
                report_error(
                    f"  decision-table: action '{action_id}' references unknown parent_action_id '{parent_action_id}'"
                )
        produces_conditions = action.get("produces_conditions")
        if produces_conditions is not None:
            if not isinstance(produces_conditions, list) or not produces_conditions:
                report_error(
                    f"  decision-table: action '{action_id}' produces_conditions must be a non-empty list when present"
                )
            else:
                for cond_id in produces_conditions:
                    if cond_id not in condition_ids:
                        report_error(
                            f"  decision-table: action '{action_id}' references unknown produced condition '{cond_id}'"
                        )
        produces_data_elements = action.get("produces_data_elements")
        if produces_data_elements is not None:
            if not isinstance(produces_data_elements, list) or not produces_data_elements:
                report_error(
                    f"  decision-table: action '{action_id}' produces_data_elements must be a non-empty list when present"
                )
            else:
                for data_element_id in produces_data_elements:
                    if data_element_id not in data_element_ids:
                        report_error(
                            f"  decision-table: action '{action_id}' references unknown produced data element '{data_element_id}'"
                        )
        assessment_artifact = action.get("assessment_artifact")
        if assessment_artifact is not None and not isinstance(assessment_artifact, str):
            report_error(
                f"  decision-table: action '{action_id}' assessment_artifact must be a string when present"
            )
        has_children = child_action_counts.get(str(action_id), 0) > 0
        if not has_children:
            concept_refs = action.get("concept_refs")
            code = action.get("code")
            codings = action.get("codings")
            has_concept_refs = isinstance(concept_refs, list) and any(
                isinstance(ref, str) and ref.strip() for ref in concept_refs
            )
            has_code = isinstance(code, dict) and any(
                str(code.get(field) or "").strip() for field in ("code", "display", "system")
            )
            has_codings = isinstance(codings, list) and any(
                isinstance(entry, dict) and str(entry.get("code") or "").strip()
                for entry in codings
            )
            if not (has_concept_refs or has_code or has_codings):
                report_warn(
                    f"  decision-table: leaf action '{action_id}' is missing recommended concept_refs[] or code/codings[] terminology linkage"
                )
        _validate_traceability_links(
            owner_label=str(action_id),
            owner_type="action",
            traceability_ids=action.get("evidence_traceability_ids"),
        )
        _validate_provenance(
            owner_label=str(action_id),
            owner_type="action",
            provenance=action.get("provenance"),
            traceability_ids=action.get("evidence_traceability_ids"),
        )
    
    # Validate rules reference valid events, conditions, actions
    condition_usage: Dict[str, int] = {}  # Track how often each condition is used
    rules_with_phase = 0  # Track how many rules have phase assignments
    
    for idx, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            report_error(f"  decision-table: rule #{idx} is not a dict")
            continue
        
        # Check for required 'id' field
        rule_id = rule.get("id")
        if not rule_id:
            report_error(f"  decision-table: rule #{idx} missing required 'id' field")
            rule_id = f"#{idx}"
        
        # Check event reference (required)
        event = rule.get("event")
        if not event:
            report_error(f"  decision-table: rule '{rule_id}' missing required 'event' field")
        elif event not in event_ids:
            report_error(f"  decision-table: rule '{rule_id}' references unknown event '{event}'")
        
        # Check optional 'when' clause
        when_clause = rule.get("when")
        if when_clause is None:
            when_clause = {}
        if isinstance(when_clause, dict):
            # Empty dict {} is valid for unconditional rules (always applies)
            for cond_id in when_clause.keys():
                if cond_id not in condition_ids:
                    report_error(
                        f"  decision-table: rule '{rule_id}' references unknown condition '{cond_id}'"
                    )
                else:
                    condition_usage[cond_id] = condition_usage.get(cond_id, 0) + 1
        
        # Check required 'then' clause
        then_clause = rule.get("then")
        if not then_clause:
            report_error(f"  decision-table: rule '{rule_id}' missing required 'then' field")
        elif isinstance(then_clause, list):
            for action_ref in then_clause:
                if action_ref not in action_ids:
                    report_error(f"  decision-table: rule '{rule_id}' references unknown action '{action_ref}'")
        
        # Check recommended 'action' field (singular display label)
        if not rule.get("action"):
            report_warn(f"  decision-table: rule '{rule_id}' missing recommended 'action' field (singular label)")
        
        # Check recommended 'rationale' field (evidence traceability)
        if not rule.get("rationale"):
            report_warn(f"  decision-table: rule '{rule_id}' missing recommended 'rationale' field")
        _validate_traceability_links(
            owner_label=str(rule_id),
            owner_type="rule",
            traceability_ids=rule.get("evidence_traceability_ids"),
        )
        _validate_provenance(
            owner_label=str(rule_id),
            owner_type="rule",
            provenance=rule.get("provenance"),
            traceability_ids=rule.get("evidence_traceability_ids"),
        )
        
        # Check 'phase' field if pathway_phases present
        if rule.get("pathway_phase") is not None:
            report_error(
                f"  decision-table: rule '{rule_id}' uses legacy 'pathway_phase' — use 'phase'"
            )
        rule_phase = rule.get("phase")
        if rule_phase:
            rules_with_phase += 1
            if phase_ids and rule_phase not in phase_ids:
                report_error(
                    f"  decision-table: rule '{rule_id}' references unknown phase '{rule_phase}' "
                    f"(not in pathway_phases)"
                )
        elif phase_ids:
            # pathway_phases defined but this rule has no phase assignment
            report_warn(
                f"  decision-table: rule '{rule_id}' has no phase assignment "
                f"(pathway_phases present but rule.phase missing)"
            )
    
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
    
    return errors, warnings
