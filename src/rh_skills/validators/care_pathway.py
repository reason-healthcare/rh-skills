"""
Care pathway validation

Validates care-pathway artifacts for:
- Required field completeness
- Flat step model (optional parent_id + applicability_condition)
- Optional rule/action linkage to decision-table logic
- L2/L3 boundary enforcement (no FHIR-specific fields at L2)
- Transition integrity
"""

import re
from typing import Dict, List, Tuple, Any, Set

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

    def _semantic_tokens(*values: str) -> set[str]:
        tokens: set[str] = set()
        for value in values:
            for token in re.split(r"[^a-z0-9]+", str(value or "").lower()):
                if len(token) >= 3:
                    tokens.add(token)
        return tokens

    def _step_rule_refs(phase: dict) -> list[str]:
        refs: list[str] = []
        rule_id = phase.get("rule_id")
        if isinstance(rule_id, str) and rule_id.strip():
            refs.append(rule_id.strip())
        rule_ids = phase.get("rule_ids")
        if isinstance(rule_ids, list):
            for value in rule_ids:
                if isinstance(value, str) and value.strip():
                    refs.append(value.strip())
        seen: set[str] = set()
        deduped: list[str] = []
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                deduped.append(ref)
        return deduped
    
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
    evidence_traceability = sections.get("evidence_traceability") or []
    claim_ids: set[str] = set()
    if evidence_traceability:
        if not isinstance(evidence_traceability, list):
            report_error("  care-pathway: evidence_traceability must be a list when present")
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
                        f"  care-pathway: evidence_traceability entry #{idx} missing recommended 'strength' field"
                    )
                    continue
                normalized_strength = str(strength).strip().lower()
                if normalized_strength not in _EVIDENCE_STRENGTH_VALUES:
                    report_error(
                        f"  care-pathway: evidence_traceability entry #{idx} has invalid strength '{strength}' "
                        f"(allowed: {', '.join(sorted(_EVIDENCE_STRENGTH_VALUES))})"
                    )
    
    # Validate required sections
    steps = sections.get("steps", [])
    
    if not steps or len(steps) == 0:
        report_error("  care-pathway: steps section is empty")
        return errors, warnings
    
    step_ids: Set[str] = set()
    child_map: Dict[str, List[dict]] = {}
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

        parent_id = phase.get("parent_id")
        if isinstance(parent_id, str) and parent_id.strip():
            child_map.setdefault(parent_id.strip(), []).append(phase)

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
        rule_ids = phase.get("rule_ids")
        if rule_ids is not None:
            if not isinstance(rule_ids, list):
                report_error(
                    f"  care-pathway: phase '{phase_id or idx}' rule_ids must be a list"
                )
            elif not rule_ids:
                report_error(
                    f"  care-pathway: phase '{phase_id or idx}' rule_ids must not be empty"
                )
            else:
                for rule_idx, linked_rule_id in enumerate(rule_ids, start=1):
                    if not isinstance(linked_rule_id, str) or not linked_rule_id.strip():
                        report_error(
                            f"  care-pathway: phase '{phase_id or idx}' rule_ids[{rule_idx}] must be a non-empty string"
                        )
        if rule_id and isinstance(rule_ids, list) and rule_ids:
            report_error(
                f"  care-pathway: phase '{phase_id or idx}' must use either rule_id or rule_ids, not both"
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
            if not _step_rule_refs(phase):
                report_warn(
                    f"  care-pathway: phase '{phase_id or idx}' uses action_labels without rule_id/rule_ids; "
                    "formalize will treat them as descriptive only"
                )

        recommendation_like = bool(_step_rule_refs(phase)) or bool(action_labels)
        if recommendation_like:
            traceability_ids = phase.get("evidence_traceability_ids")
            if traceability_ids is None:
                report_error(
                    f"  care-pathway: phase '{phase_id or idx}' missing required evidence_traceability_ids[] link(s)"
                )
            elif not isinstance(traceability_ids, list) or not traceability_ids:
                report_error(
                    f"  care-pathway: phase '{phase_id or idx}' evidence_traceability_ids must be a non-empty list"
                )
            else:
                for trace_idx, claim_id in enumerate(traceability_ids, start=1):
                    if not isinstance(claim_id, str) or not claim_id.strip():
                        report_error(
                            f"  care-pathway: phase '{phase_id or idx}' evidence_traceability_ids[{trace_idx}] must be a non-empty string"
                        )
                        continue
                    if claim_ids and claim_id.strip() not in claim_ids:
                        report_error(
                            f"  care-pathway: phase '{phase_id or idx}' references unknown evidence claim_id '{claim_id.strip()}'"
                        )

            provenance = phase.get("provenance")
            if provenance is None:
                report_warn(
                    f"  care-pathway: phase '{phase_id or idx}' missing recommended provenance metadata"
                )
            elif not isinstance(provenance, dict):
                report_error(
                    f"  care-pathway: phase '{phase_id or idx}' provenance must be an object when present"
                )
            else:
                source = str(provenance.get("source") or "").strip()
                if not source:
                    report_error(
                        f"  care-pathway: phase '{phase_id or idx}' provenance.source is required when provenance is present"
                    )
                elif source not in _PROVENANCE_SOURCES:
                    report_error(
                        f"  care-pathway: phase '{phase_id or idx}' provenance.source '{source}' is invalid "
                        f"(allowed: {', '.join(sorted(_PROVENANCE_SOURCES))})"
                    )
                elif source == "inferred":
                    rationale = str(provenance.get("rationale") or "").strip()
                    if not rationale:
                        report_error(
                            f"  care-pathway: phase '{phase_id or idx}' inferred provenance requires provenance.rationale"
                        )
                    if not isinstance(traceability_ids, list) or not traceability_ids:
                        report_error(
                            f"  care-pathway: phase '{phase_id or idx}' inferred provenance requires non-empty evidence_traceability_ids[]"
                        )

            if isinstance(action_labels, list) and action_labels:
                step_tokens = _semantic_tokens(
                    str(phase.get("id") or ""),
                    str(phase.get("label") or ""),
                    str(phase.get("description") or ""),
                )
                action_tokens = _semantic_tokens(*[str(label) for label in action_labels])
                if step_tokens and action_tokens and len(step_tokens & action_tokens) == 0:
                    report_warn(
                        f"  care-pathway: phase '{phase_id or idx}' action_labels may be semantically misaligned with step intent"
                    )

    for idx, phase in enumerate(steps, start=1):
        if not isinstance(phase, dict):
            continue
        phase_id = str(phase.get("id") or f"#{idx}")
        rule_refs = _step_rule_refs(phase)
        if not rule_refs:
            continue
        child_steps = child_map.get(phase_id) or []
        if child_steps:
            child_ids = [
                str(child.get("id") or "<unknown>")
                for child in child_steps
                if isinstance(child, dict)
            ]
            report_error(
                f"  care-pathway: phase '{phase_id}' links to rule(s) '{', '.join(rule_refs)}' but also contains child steps "
                f"({', '.join(child_ids)}) — rule-linked pathway steps must be leaves; push recommendation linkage down to the appropriate child step and leave wrapper phases unlinked"
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
