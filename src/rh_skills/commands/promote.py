"""rh-skills promote — Promote artifacts between lifecycle levels."""

import io
import sys
from contextlib import contextmanager
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.common import (
    append_topic_event,
    config_value,
    lock_file,
    log_info,
    log_warn,
    now_iso,
    require_topic,
    require_tracking,
    save_tracking,
    sha256_file,
    sources_root,
    today_date,
    topic_dir,
    unlock_file,
)
from rh_skills.commands.validate import validate_artifact_file

EXTRACT_ARTIFACT_PROFILES = (
    {
        "artifact_type": "evidence-summary",
        "keywords": ("evidence", "risk", "factor", "picot", "pico", "clinical question", "scope", "framing", "finding", "synthesis"),
        "section": "summary_points",
        "key_question": "What does the evidence say, including risk factors and clinical framing?",
    },
    {
        "artifact_type": "decision-table",
        "keywords": ("decision table", "decision", "condition", "action", "rule", "if-then",
                      "threshold", "diagnostic", "criteria", "eligibility", "screen",
                      "exclusion", "contraind", "avoid"),
        "section": "decision_table",
        "key_question": "What conditions, eligibility, exclusions, and actions form the decision logic?",
    },
    {
        "artifact_type": "care-pathway",
        "keywords": ("workflow", "pathway", "step-by-step", "care pathway", "protocol", "order set"),
        "section": "steps",
        "key_question": "In what order do things happen in the care process?",
    },
    {
        "artifact_type": "terminology",
        "keywords": ("terminology", "value-set", "valueset", "code", "concept map"),
        "section": "value_sets",
        "key_question": "What codes and terminology define the clinical concepts?",
    },
    {
        "artifact_type": "measure",
        "keywords": ("measure", "numerator", "denominator", "quality", "performance"),
        "section": "populations",
        "key_question": "How do we know the intervention is working (quality measures)?",
    },
    {
        "artifact_type": "assessment",
        "keywords": ("assessment", "screening", "questionnaire", "instrument", "phq", "gad", "score"),
        "section": ["instrument", "items", "scoring"],
        "key_question": "What assessment instruments or scoring tools are specified?",
    },
    {
        "artifact_type": "policy",
        "keywords": ("policy", "prior auth", "authorization", "coverage", "documentation requirement", "payer"),
        "section": "policy",
        "key_question": "What coverage, authorization, or documentation policies apply?",
    },
)


def _yaml_rt() -> YAML:
    y = YAML()
    y.default_flow_style = False
    y.preserve_quotes = True
    return y


def _yaml_safe() -> YAML:
    return YAML(typ="safe")


def _human_title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-") if part)


def _slugify(value: str) -> str:
    cleaned = [
        char.lower() if char.isalnum() else "-"
        for char in value
    ]
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _parse_markdown_frontmatter(path: Path) -> dict:
    raw = path.read_text()
    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        return {}
    data = _yaml_safe().load(parts[1]) or {}
    return data if isinstance(data, dict) else {}


def _extract_plan_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "extract-plan.yaml"


def _extract_readout_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "extract-plan-readout.md"


def _formalize_plan_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "formalize-plan.yaml"


def _formalize_readout_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "formalize-plan-readout.md"


def _load_extract_plan(topic: str) -> dict:
    plan_path = _extract_plan_path(topic)
    if not plan_path.exists():
        raise click.UsageError(
            f"No plan found: {plan_path}. Run 'rh-skills promote plan {topic}' first."
        )
    data = _yaml_safe().load(plan_path.read_text())
    if not data or not isinstance(data, dict):
        raise click.UsageError(f"Plan is empty or invalid: {plan_path}")
    return data


def _load_formalize_plan(topic: str) -> dict:
    plan_path = _formalize_plan_path(topic)
    if not plan_path.exists():
        raise click.UsageError(
            f"No plan found: {plan_path}. Run 'rh-skills promote formalize-plan {topic}' first."
        )
    data = _yaml_safe().load(plan_path.read_text())
    if not data or not isinstance(data, dict):
        raise click.UsageError(f"Plan is empty or invalid: {plan_path}")
    return data


def _approved_extract_artifacts(topic: str, *, strict: bool = True) -> list[dict]:
    plan = _load_extract_plan(topic)
    if plan.get("status") != "approved":
        raise click.UsageError(
            "extract-plan.yaml is not approved. Review and update the plan before implement."
        )

    approved: list[dict] = []
    blocked: list[str] = []
    for artifact in plan.get("artifacts", []) or []:
        decision = artifact.get("reviewer_decision", "pending-review")
        name = artifact.get("name", "<unnamed-artifact>")
        if decision == "approved":
            approved.append(artifact)
        else:
            blocked.append(f"{name} ({decision})")

    if strict and blocked:
        raise click.UsageError(
            "Artifacts not approved for implementation: " + ", ".join(blocked)
        )
    return approved


def _conflict_text(item: object) -> str:
    """Return the human-readable concern/conflict description from an entry."""
    if isinstance(item, dict):
        return item.get("concern") or item.get("conflict") or item.get("issue") or str(item)
    return str(item)


def _collect_open_conflicts(topic: str) -> list[dict]:
    """Return all unresolved conflict entries across extract and formalize plans.

    Each entry is a dict with keys:
      plan_type, artifact, index, conflict, resolution
    """
    results: list[dict] = []
    candidates = [
        ("extract", _extract_plan_path(topic)),
        ("formalize", _formalize_plan_path(topic)),
    ]
    for plan_type, path in candidates:
        if not path.exists():
            continue
        try:
            plan = _yaml_safe().load(path.read_text())
        except Exception:
            continue
        if not plan or not isinstance(plan, dict):
            continue
        for artifact in plan.get("artifacts") or []:
            name = artifact.get("name", "")
            # extract plans use 'concerns'; formalize plans use 'conflicts'
            items = artifact.get("concerns") or artifact.get("conflicts") or []
            for idx, item in enumerate(items):
                resolution = (item.get("resolution", "") if isinstance(item, dict) else "")
                if not resolution:
                    results.append({
                        "plan_type": plan_type,
                        "artifact": name,
                        "index": idx,
                        "conflict": _conflict_text(item),
                        "resolution": resolution,
                    })
    return results


def _set_conflict_resolution(plan: dict, artifact_name: str, index: int, resolution: str) -> None:
    """Mutate plan in-place: set resolution on concerns[index] or conflicts[index]."""
    for artifact in plan.get("artifacts") or []:
        if artifact.get("name") == artifact_name:
            # extract plans use 'concerns'; formalize plans use 'conflicts'
            field = "concerns" if "concerns" in artifact else "conflicts"
            items = artifact.get(field) or []
            if index < 0 or index >= len(items):
                raise click.UsageError(
                    f"Conflict index {index} out of range for artifact '{artifact_name}' "
                    f"({len(items)} concern(s) present, indices 0–{len(items) - 1})."
                )
            item = items[index]
            if isinstance(item, dict):
                item["resolution"] = resolution
            else:
                concern_key = "concern" if field == "concerns" else "conflict"
                items[index] = {concern_key: str(item), "resolution": resolution}
            artifact[field] = items
            return
    raise click.UsageError(
        f"Artifact '{artifact_name}' not found in plan. "
        f"Available: {[a.get('name') for a in plan.get('artifacts', [])]}"
    )


def _eligible_formalize_inputs(topic: str) -> tuple[list[dict], list[str]]:
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)
    tracked_structured = {artifact["name"]: artifact for artifact in topic_entry.get("structured", [])}
    approved_extract = _approved_extract_artifacts(topic, strict=False)

    eligible: list[dict] = []
    blocked: list[str] = []
    for artifact in approved_extract:
        name = artifact.get("name")
        if not name:
            blocked.append("<unnamed-artifact> (missing name)")
            continue
        if name not in tracked_structured:
            blocked.append(f"{name} (not registered in tracking)")
            continue
        try:
            errors, _warnings = validate_artifact_file(topic, "l2", name, emit=False)
        except click.UsageError as exc:
            blocked.append(f"{name} ({exc.message})")
            continue
        if errors > 0:
            blocked.append(f"{name} (fails validation)")
            continue
        eligible.append(artifact)

    return eligible, blocked


# L2 artifact_type → L3 FHIR target mapping per docs/FORMALIZE_STRATEGIES.md
_L3_TARGET_MAP: dict[str, dict] = {
    "evidence-summary": {
        "primary": "Evidence",
        "supporting": ["EvidenceVariable", "Citation"],
        "l3_targets": ["Evidence", "EvidenceVariable", "Citation"],
    },
    "decision-table": {
        "primary": "PlanDefinition",
        "supporting": ["Library"],
        "l3_targets": ["PlanDefinition (eca-rule)", "Library (CQL)"],
    },
    "care-pathway": {
        "primary": "PlanDefinition",
        "supporting": ["ActivityDefinition"],
        "l3_targets": ["PlanDefinition (clinical-protocol)", "ActivityDefinition"],
    },
    "terminology": {
        "primary": "ValueSet",
        "supporting": ["ConceptMap"],
        "l3_targets": ["ValueSet", "ConceptMap"],
    },
    "measure": {
        "primary": "Measure",
        "supporting": ["Library"],
        "l3_targets": ["Measure", "Library (CQL)"],
    },
    "assessment": {
        "primary": "Questionnaire",
        "supporting": [],
        "l3_targets": ["Questionnaire"],
    },
    "policy": {
        "primary": "PlanDefinition",
        "supporting": ["Questionnaire", "Library"],
        "l3_targets": ["PlanDefinition (eca-rule)", "Questionnaire (DTR)", "Library (CQL)"],
    },
}


def _formalize_required_sections(artifacts: list[dict]) -> list[str]:
    required_sections = []
    artifact_types = {artifact.get("artifact_type") for artifact in artifacts}

    if artifact_types & {"care-pathway"}:
        required_sections.append("pathways")
    if artifact_types & {"decision-table", "care-pathway", "policy"}:
        required_sections.append("actions")
    if "terminology" in artifact_types:
        required_sections.append("value_sets")
    if "measure" in artifact_types:
        required_sections.append("measures")
    if "assessment" in artifact_types:
        required_sections.append("assessments")
    if artifact_types & {"decision-table", "measure", "policy"}:
        required_sections.append("libraries")
    if "evidence-summary" in artifact_types:
        required_sections.append("evidence")

    deduped: list[str] = []
    for section in required_sections:
        if section not in deduped:
            deduped.append(section)
    return deduped


def _build_formalize_artifacts(topic: str, eligible_inputs: list[dict]) -> list[dict]:
    input_types = {a.get("artifact_type", "unknown") for a in eligible_inputs}

    # Single type: one artifact with type-specific strategy
    if len(input_types) == 1:
        strategy = next(iter(input_types))
        target_info = _L3_TARGET_MAP.get(strategy, {})
        l3_targets = target_info.get("l3_targets", ["PlanDefinition"])
        artifact_type = strategy if strategy in _L3_TARGET_MAP else "pathway-package"

        candidate = {
            "name": f"{topic}-{strategy}",
            "artifact_type": artifact_type,
            "strategy": strategy,
            "l3_targets": l3_targets,
            "input_artifacts": [a["name"] for a in eligible_inputs],
            "rationale": (
                f"Combines {len(eligible_inputs)} approved structured artifact(s) "
                f"using '{strategy}' strategy → "
                f"{', '.join(l3_targets)}."
            ),
            "required_sections": _formalize_required_sections(eligible_inputs),
            "implementation_target": True,
            "reviewer_decision": "pending-review",
            "approval_notes": "",
        }
        return [candidate]

    # Multi-type: one artifact per unique type + overlap detection
    artifacts = []
    type_to_inputs: dict[str, list[dict]] = {}
    for a in eligible_inputs:
        atype = a.get("artifact_type", "unknown")
        type_to_inputs.setdefault(atype, []).append(a)

    # Detect resource type overlaps across strategies
    overlaps = _detect_resource_type_overlaps(type_to_inputs)

    first = True
    for atype, inputs in type_to_inputs.items():
        target_info = _L3_TARGET_MAP.get(atype, {})
        l3_targets = target_info.get("l3_targets", ["PlanDefinition"])
        artifact_type = atype if atype in _L3_TARGET_MAP else "pathway-package"

        overlap_notes = ""
        if overlaps:
            relevant = [o for o in overlaps if atype in o["strategies"]]
            if relevant:
                overlap_notes = " ".join(
                    f"⚠ Overlaps with {', '.join(s for s in o['strategies'] if s != atype)} "
                    f"on {o['resource_type']}."
                    for o in relevant
                )

        candidate = {
            "name": f"{topic}-{atype}",
            "artifact_type": artifact_type,
            "strategy": atype,
            "l3_targets": l3_targets,
            "input_artifacts": [a["name"] for a in inputs],
            "rationale": (
                f"Formalizes {len(inputs)} '{atype}' artifact(s) → "
                f"{', '.join(l3_targets)}."
                + (f" {overlap_notes}" if overlap_notes else "")
            ),
            "required_sections": _formalize_required_sections(inputs),
            "implementation_target": first,
            "reviewer_decision": "pending-review",
            "approval_notes": "",
        }
        artifacts.append(candidate)
        first = False

    return artifacts


def _detect_resource_type_overlaps(
    type_to_inputs: dict[str, list[dict]],
) -> list[dict]:
    """Detect when different L2 strategies produce the same FHIR resource type."""
    resource_to_strategies: dict[str, list[str]] = {}
    for atype in type_to_inputs:
        target_info = _L3_TARGET_MAP.get(atype, {})
        primary = target_info.get("primary", "")
        if primary:
            resource_to_strategies.setdefault(primary, []).append(atype)

    return [
        {"resource_type": rt, "strategies": strategies}
        for rt, strategies in resource_to_strategies.items()
        if len(strategies) > 1
    ]


def _build_formalize_plan_dict(topic: str, artifacts: list[dict]) -> dict:
    """Return the formalize plan as a plain dict (written to formalize-plan.yaml)."""
    return {
        "topic": topic,
        "plan_type": "formalize",
        "status": "pending-review",
        "reviewer": "",
        "reviewed_at": None,
        "artifacts": artifacts,
    }


def _render_formalize_readout(topic: str, plan: dict, blocked_inputs: list[str]) -> str:
    """Return human-friendly markdown readout derived from formalize-plan.yaml."""
    artifacts = plan.get("artifacts", []) or []
    status = plan.get("status", "pending-review")
    reviewer = plan.get("reviewer") or ""
    reviewed_at = plan.get("reviewed_at") or ""

    status_icon = "✅ APPROVED" if status == "approved" else "⏳ PENDING REVIEW"

    lines = [
        "> **Note:** This file is a narrative readout derived from `formalize-plan.yaml`.",
        "> It is generated by the `rh-inf-formalize` skill and should not be edited directly.",
        "> The structured plan in `formalize-plan.yaml` is the single source of truth.",
        f"> To record approval decisions, edit `formalize-plan.yaml` and set `status: approved`.",
        "",
        f"**Status: {status_icon}**" + (f" — Reviewer: {reviewer} — {reviewed_at}" if status == "approved" else ""),
        "",
        "# Review Summary",
        "",
        f"- Topic: `{topic}`",
        f"- Proposed computable artifacts: {len(artifacts)}",
    ]

    if artifacts:
        impl_target = next((a["name"] for a in artifacts if a.get("implementation_target")), None)
        if impl_target:
            lines.append(f"- Primary implementation target: `{impl_target}`")
    lines.extend([
        "- Eligible structured inputs are limited to extract-approved artifacts that still pass validation.",
        "- Reviewer action required: approve the plan and the single implementation target before formalization.",
        "",
        "# Proposed Artifacts",
        "",
    ])

    for artifact in artifacts:
        decision = artifact.get("reviewer_decision", "pending-review")
        decision_icon = _DECISION_ICON.get(decision, "⏳")
        notes_text = artifact.get("approval_notes") or "_pending reviewer input_"
        strategy = artifact.get("strategy", "unknown")
        l3_targets = artifact.get("l3_targets", [])
        lines.extend([
            f"## {decision_icon} {artifact.get('name', 'unknown')}",
            "",
            f"- Type: `{artifact.get('artifact_type', 'unknown')}`",
            f"- Strategy: `{strategy}`",
            f"- L3 FHIR targets: {', '.join(l3_targets) if l3_targets else '_none specified_'}",
            f"- Eligible structured inputs: {', '.join(artifact.get('input_artifacts', []))}",
            f"- Rationale: {artifact.get('rationale', '')}",
            f"- Required computable sections: {', '.join(artifact.get('required_sections', []))}",
            f"- Implementation target: `{'yes' if artifact.get('implementation_target') else 'no'}`",
            "- Unresolved modeling notes: review input overlap, omitted alternates, and downstream export assumptions before implementation.",
            f"- Reviewer decision: {decision_icon} `{decision}`",
            f"- Approval notes: {notes_text}",
            "",
        ])

    lines.extend(["# Cross-Artifact Issues", ""])
    if blocked_inputs:
        lines.append("- Inputs excluded from this plan because they are not currently eligible:")
        lines.extend([f"  - {item}" for item in blocked_inputs])
    else:
        lines.append("- No excluded structured inputs were detected during deterministic planning.")
    lines.extend([
        "- Confirm overlapping structured artifacts are intentionally converged into a single pathway-oriented package.",
        "- Confirm any deferred alternate computable package belongs in a future plan revision rather than this implementation run.",
        "",
        "# Implementation Readiness",
        "",
        "- Current plan status: `pending-review`",
        "- Implement MUST NOT proceed until `status: approved` is set in `formalize-plan.yaml` and the single target has `reviewer_decision: approved`.",
        "- All `input_artifacts[]` entries must still exist in `topics/<topic>/structured/` and pass validation at implement time.",
        "",
    ])
    return "\n".join(lines)


def _write_formalize_plan_and_readout(
    plan_path: Path, readout_path: Path, topic: str, plan: dict, blocked_inputs: list[str]
) -> None:
    """Persist formalize-plan.yaml and regenerate the readout from current plan state."""
    buf = io.StringIO()
    _yaml_rt().dump(plan, buf)
    plan_path.write_text(buf.getvalue())
    readout_path.write_text(_render_formalize_readout(topic, plan, blocked_inputs))


def _approved_formalize_target(topic: str) -> dict:
    plan = _load_formalize_plan(topic)
    if plan.get("status") != "approved":
        raise click.UsageError(
            "formalize-plan.yaml is not approved. Review and update the plan before implement."
        )

    artifacts = plan.get("artifacts", []) or []
    targets = [artifact for artifact in artifacts if artifact.get("implementation_target") is True]
    if len(targets) != 1:
        raise click.UsageError(
            "formalize-plan.yaml must mark exactly one artifact as implementation_target: true."
        )

    target = targets[0]
    if target.get("reviewer_decision") != "approved":
        raise click.UsageError(
            f"Artifact '{target.get('name', '<unnamed-artifact>')}' is not approved for implementation."
        )

    input_artifacts = target.get("input_artifacts", []) or []
    if not input_artifacts:
        raise click.UsageError(
            f"Artifact '{target.get('name', '<unnamed-artifact>')}' has no input_artifacts."
        )

    invalid_inputs: list[str] = []
    for input_name in input_artifacts:
        try:
            errors, _warnings = validate_artifact_file(topic, "l2", input_name, emit=False)
        except click.UsageError as exc:
            invalid_inputs.append(f"{input_name} ({exc.message})")
            continue
        if errors > 0:
            invalid_inputs.append(f"{input_name} (fails validation)")

    if invalid_inputs:
        raise click.UsageError(
            "Formalize inputs are missing or invalid: " + ", ".join(invalid_inputs)
        )

    return target


def _parse_evidence_refs(raw_refs: tuple[str, ...]) -> list[dict]:
    entries: list[dict] = []
    for raw in raw_refs:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 4:
            raise click.UsageError(
                "--evidence-ref must use 'claim_id|statement|source|locator'"
            )
        claim_id, statement, source, locator = parts
        entries.append({
            "claim_id": claim_id,
            "statement": statement,
            "evidence": [{"source": source, "locator": locator}],
        })
    return entries


def _parse_conflicts(raw_conflicts: tuple[str, ...]) -> list[dict]:
    """Parse --conflict flags into conflict entries.

    Flags with the same issue are merged into one entry with multiple positions.
    The preferred_interpretation comes from whichever flag supplies it.

    Formats:
      issue|source|statement
      issue|source|statement|preferred_source|preferred_rationale
    """
    merged: dict[str, dict] = {}
    for raw in raw_conflicts:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 3:
            raise click.UsageError(
                "--conflict must use 'issue|source|statement' or "
                "'issue|source|statement|preferred_source|preferred_rationale'"
            )
        issue, source, statement = parts[:3]
        if issue not in merged:
            merged[issue] = {"issue": issue, "positions": []}
        merged[issue]["positions"].append({"source": source, "statement": statement})
        if len(parts) >= 5:
            merged[issue]["preferred_interpretation"] = {
                "source": parts[3],
                "rationale": parts[4],
            }
    return list(merged.values())


# Structurally valid stub shapes for known section names.
# Renderers iterate these as lists/dicts, so they must have the right shape.
_STUB_SECTION_SHAPES: dict[str, object] = {
    # evidence-summary sections
    "summary_points": [{"finding_id": "f-001", "statement": "<stub: finding>", "grade": "<stub: grade>"}],
    "risk_factors": [{"id": "rf-001", "factor": "<stub: factor>", "direction": "increases",
                      "magnitude": "<stub: effect size>", "evidence_quality": "<stub: grade>"}],
    "frames": [{"id": "frame-001", "population": "<stub: population>", "intervention": "<stub: intervention>",
                "comparison": "<stub: comparison>", "outcomes": ["<stub: outcome>"], "timing": "<stub: timing>", "setting": "<stub: setting>"}],
    # decision-table sections (includes absorbed eligibility/exclusion as conditions)
    "conditions": [{"id": "cond-001", "label": "<stub: condition>", "values": ["Yes", "No"]}],
    "rules": [{"id": "rule-001", "when": {"cond-001": "Yes"}, "then": ["approve"]},
              {"id": "rule-002", "when": {"cond-001": "No"}, "then": ["deny"]}],
    # care-pathway sections
    "steps": [{"step": 1, "description": "<stub: step>", "actor": "<stub: actor>", "next": 2}],
    "triggers": [{"id": "trigger-001", "description": "<stub: trigger event>"}],
    # terminology sections
    "value_sets": [{"id": "vs-001", "name": "<stub: value set>", "system": "<stub: system>", "codes": []}],
    "concept_maps": [{"id": "cm-001", "source_system": "<stub: source>", "target_system": "<stub: target>",
                      "mappings": [{"source_code": "<stub>", "target_code": "<stub>", "equivalence": "equivalent"}]}],
    # measure sections
    "populations": [{"id": "pop-001", "type": "initial-population", "description": "<stub: population>"}],
    "scoring": {"method": "proportion", "unit": "percentage"},
    "improvement_notation": "increase",
    # assessment sections
    "instrument": {"name": "<stub: instrument name>", "purpose": "<stub: purpose>", "population": "<stub: population>"},
    "items": [{"id": "item-001", "text": "<stub: item text>", "type": "likert",
               "options": [{"value": 0, "label": "Not at all"}, {"value": 3, "label": "Nearly every day"}]}],
    # policy sections
    "applicability": {"populations": ["<stub: population>"], "service_category": "<stub: service>"},
    "criteria": [{"id": "cr-001", "description": "<stub: criterion>", "requirement_type": "clinical", "rule": "<stub: rule>"}],
}


def _stub_section_value(section_name: str, artifact_type: str | None) -> object:
    """Return a structurally valid stub placeholder for a section.

    The ``actions`` section has different shapes for decision-table (list of
    action dicts) vs policy (dict of approve/deny/pend dicts).  The ``scoring``
    section differs between assessment (ranges) and measure (method/unit).
    """
    if section_name == "actions":
        if artifact_type == "decision-table":
            return [{"id": "approve", "label": "Approve"}, {"id": "deny", "label": "Deny"}]
        if artifact_type == "care-pathway":
            return [{"id": "act-001", "label": "<stub: activity>", "type": "clinical"}]
        # policy (and any other type)
        return {"approve": {"conditions": "<stub: approval conditions>"}, "deny": {"conditions": "<stub: denial conditions>"}}
    if section_name == "scoring":
        if artifact_type == "assessment":
            return {"method": "sum", "range": {"min": 0, "max": 0},
                    "ranges": [{"range": "0-9", "interpretation": "<stub: interpretation>"},
                                {"range": "10+", "interpretation": "<stub: interpretation>"}]}
        # measure
        return _STUB_SECTION_SHAPES.get(section_name, "<stub: scoring>")
    return _STUB_SECTION_SHAPES.get(section_name, f"<stub: populate {section_name} content>")


def _build_sections(
    required_sections: tuple[str, ...],
    clinical_question: str | None,
    evidence_refs: tuple[str, ...],
    artifact_type: str | None = None,
) -> dict:
    section_names = list(required_sections) if required_sections else ["summary"]
    evidence_entries = _parse_evidence_refs(evidence_refs)
    if evidence_entries and "evidence_traceability" not in section_names:
        section_names.append("evidence_traceability")

    sections: dict = {}
    for name in section_names:
        if name == "summary":
            sections[name] = clinical_question or ""
        elif name == "evidence_traceability":
            sections[name] = evidence_entries
        else:
            sections[name] = _stub_section_value(name, artifact_type)
    return sections


def _build_stub_l2_artifact(
    artifact_name: str,
    source: tuple[str, ...],
    artifact_type: str | None,
    clinical_question: str | None,
    required_sections: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    conflicts: tuple[str, ...],
) -> str:
    data = {
        "id": artifact_name,
        "name": artifact_name,
        "title": _human_title(artifact_name),
        "version": "1.0.0",
        "status": "draft",
        "domain": (artifact_type or "clinical").replace("-", " "),
        "description": clinical_question or f"Stub artifact for {artifact_name}.",
        "derived_from": list(source),
        "artifact_type": artifact_type or "evidence-summary",
        "clinical_question": clinical_question or "",
        "sections": _build_sections(required_sections, clinical_question, evidence_refs, artifact_type),
        "conflicts": _parse_conflicts(conflicts),
    }
    buf = io.StringIO()
    _yaml_rt().dump(data, buf)
    return buf.getvalue().rstrip() + "\n"


def _normalized_source_records(tracking: dict, topic: str) -> list[dict]:
    normalized_root = sources_root() / "normalized"
    records: list[dict] = []
    for source in tracking.get("sources", []):
        source_topic = source.get("topic")
        if source_topic not in (None, topic):
            continue
        # Support both `name` (written by ingest) and `id` (used in eval fixtures).
        source_name = source.get("name") or source.get("id", "")
        if not source_name:
            continue
        if source.get("normalized") is False:
            log_warn(f"Source '{source_name}' is not yet normalized — excluding from extract plan. "
                     "Run 'rh-inf-ingest implement' to normalize it first.")
            continue
        normalized_path = normalized_root / f"{source_name}.md"
        if normalized_path.exists():
            records.append({
                "name": source_name,
                "path": normalized_path,
                "relative_path": f"sources/normalized/{source_name}.md",
                "content": normalized_path.read_text(),
            })
    return records


_EVIDENCE_SUMMARY_FALLBACK = {
    "artifact_type": "evidence-summary",
    "section": "summary_points",
    "key_question": "What evidence should be preserved for downstream reasoning?",
}


def _infer_artifact_profiles(source_name: str, content: str) -> list[dict]:
    """Return all matching artifact profiles for a source (many-to-many)."""
    haystack = f"{source_name} {content[:1000]}".lower()
    matched = [
        profile
        for profile in EXTRACT_ARTIFACT_PROFILES
        if any(keyword in haystack for keyword in profile["keywords"])
    ]
    return matched if matched else [_EVIDENCE_SUMMARY_FALLBACK]


def _group_sources_for_extract_plan(source_records: list[dict]) -> list[dict]:
    """Group source records by artifact type — one source may contribute to many types."""
    grouped: dict[str, dict] = {}
    for record in source_records:
        for profile in _infer_artifact_profiles(record["name"], record["content"]):
            artifact_type = profile["artifact_type"]
            group = grouped.setdefault(
                artifact_type,
                {
                    "artifact_type": artifact_type,
                    "section": profile["section"],
                    "key_question": profile["key_question"],
                    "sources": [],
                },
            )
            if record not in group["sources"]:
                group["sources"].append(record)
    return list(grouped.values())


_ARTIFACT_PURPOSES: dict[str, str] = {
    "eligibility-criteria": "Provides population inclusion/exclusion criteria for downstream CDS applicability conditions.",
    "risk-factors": "Captures patient and contextual risk factors for use in risk stratification and decision logic.",
    "evidence-summary": "Synthesizes evidence on clinical outcomes for downstream advisory content and guideline alignment.",
    "decision-table": "Encodes conditional clinical decision logic for CDS rule formalization.",
    "care-pathway": "Maps clinical workflow steps and transitions for protocol-based guidance.",
    "terminology": "Defines value sets and concept maps for semantic interoperability.",
    "measure": "Specifies quality measurement logic for clinical performance tracking.",
    "assessment": "Structures a validated clinical instrument for patient evaluation.",
    "policy": "Captures coverage or authorization rules for policy-driven guidance.",
}


_CONCERN_ALIGNMENT_ASPECTS: dict[str, str] = {
    "eligibility-criteria": "inclusion/exclusion thresholds, age bands, and population definitions",
    "risk-factors": "risk factor definitions, magnitude estimates, and effect direction",
    "evidence-summary": "evidence grades, recommendation strength, and outcome measures",
    "decision-table": "condition thresholds, action triggers, and decision criteria",
    "care-pathway": "step sequencing, timing windows, and actor responsibilities",
    "terminology": "code coverage, concept boundaries, and preferred terms",
    "measure": "population definitions, scoring logic, and measurement period",
    "assessment": "item wording, response options, and scoring ranges",
    "policy": "coverage criteria, authorization requirements, and payer definitions",
}


def _identify_group_concerns(group: dict) -> list[dict]:
    """Call LLM to surface specific clinical concerns for this artifact group.

    Returns [] in stub mode — reviewer adds concerns via --add-conflict at approve time.
    """
    if config_value("LLM_PROVIDER", "stub") == "stub":
        return []

    artifact_type = group["artifact_type"]
    key_question = group.get("key_question", "")
    sources = group["sources"]
    aspect = _CONCERN_ALIGNMENT_ASPECTS.get(
        artifact_type, "clinical values, thresholds, and recommendations"
    )

    source_blocks = "\n\n".join(
        f"### Source: `{r['name']}`\n{r['content'][:3000]}"
        for r in sources
    )
    scope_instruction = (
        "Identify specific cross-source disagreements — values, thresholds, timing, "
        "populations, or recommendations that differ between sources."
        if len(sources) > 1 else
        "Identify specific internal tensions — where the source qualifies, contradicts, "
        "or hedges a clinical value or recommendation."
    )

    system_prompt = (
        "You are a clinical knowledge analyst reviewing normalized source documents. "
        "Identify specific, concrete clinical concerns for a proposed artifact. "
        "Each concern must name exact values or positions that differ or are ambiguous "
        "(e.g., 'Source `ada-2024` specifies HbA1c target <7.0%; source `aace-guidelines` specifies <=6.5%'). "
        "Do NOT generate generic boilerplate. "
        "Respond ONLY with a YAML list — no prose, no explanation:\n"
        "- concern: \"<specific disagreement>\"\n"
        "If no specific concerns exist, return exactly: []"
    )
    user_prompt = (
        f"Artifact type: {artifact_type}\n"
        f"Key clinical question: {key_question}\n"
        f"Focus area: {aspect}\n\n"
        f"{source_blocks}\n\n"
        f"{scope_instruction}\n"
        "Return ONLY a YAML list. Name exact values and the sources they come from."
    )

    try:
        raw = _invoke_llm(system_prompt, user_prompt).strip()
        for fence in ("```yaml", "```yml", "```"):
            if raw.startswith(fence):
                raw = raw[len(fence):].strip()
                if raw.endswith("```"):
                    raw = raw[:-3].strip()
                break
        y = YAML()
        y.preserve_quotes = True
        parsed = y.load(raw)
        if not parsed or not isinstance(parsed, list):
            return []
        return [
            {"concern": str(item["concern"]), "resolution": ""}
            for item in parsed
            if isinstance(item, dict) and item.get("concern")
        ]
    except Exception:
        return []



def _build_plan_artifact_entry(group: dict, concerns: list[dict] | None = None) -> dict:
    source_files = [record["relative_path"] for record in group["sources"]]
    source_count = len(source_files)
    artifact_name = group["artifact_type"]
    plan_concerns = concerns if concerns is not None else []

    section_val = group["section"]
    middle_sections = section_val if isinstance(section_val, list) else [section_val]
    required_sections = ["summary"] + middle_sections + ["evidence_traceability"]
    if plan_concerns:
        required_sections.append("conflicts")

    purpose = _ARTIFACT_PURPOSES.get(
        group["artifact_type"],
        "Provides structured clinical content for downstream formalization.",
    )
    rationale = (
        f"Synthesizes {source_count} normalized source(s) contributing to {group['artifact_type']} for review and downstream formalization."
    )
    return {
        "name": artifact_name,
        "artifact_type": group["artifact_type"],
        "custom_artifact_type": None,
        "source_files": source_files,
        "purpose": purpose,
        "rationale": rationale,
        "key_questions": [group["key_question"]],
        "required_sections": required_sections,
        "concerns": plan_concerns,
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }


def _render_extract_plan(topic: str, artifacts: list[dict], has_concepts: bool) -> str:
    """Return pure-YAML control file content for extract-plan.yaml."""
    plan = {
        "topic": topic,
        "plan_type": "extract",
        "status": "pending-review",
        "reviewer": "",
        "reviewed_at": None,
        "review_summary": "",
        "cross_artifact_issues": [],
        "artifacts": artifacts,
    }
    buf = io.StringIO()
    _yaml_rt().dump(plan, buf)
    return buf.getvalue()


_DECISION_ICON: dict[str, str] = {
    "approved": "✅",
    "rejected": "❌",
    "needs-revision": "🔄",
    "pending-review": "⏳",
}


def _render_extract_readout(plan: dict) -> str:
    """Return human-friendly markdown readout derived from extract-plan.yaml."""
    topic = plan.get("topic", "")
    artifacts = plan.get("artifacts", []) or []
    status = plan.get("status", "pending-review")
    reviewer = plan.get("reviewer") or ""
    reviewed_at = plan.get("reviewed_at") or ""
    review_summary = plan.get("review_summary") or ""
    cross_issues = plan.get("cross_artifact_issues", []) or []

    status_icon = "✅ APPROVED" if status == "approved" else "⏳ PENDING REVIEW"

    lines = [
        "> **Note:** This file is a narrative readout derived from `extract-plan.yaml`.",
        "> It is generated by the `rh-inf-extract` skill and should not be edited directly.",
        "> The structured plan in `extract-plan.yaml` is the single source of truth.",
        f"> To record approval decisions, run: `rh-skills promote approve {topic}`",
        "",
        f"**Status: {status_icon}**" + (f" — Reviewer: {reviewer} — {reviewed_at}" if status == "approved" else ""),
        "",
        "# Review Summary",
        "",
        f"- Topic: `{topic}`",
        f"- Plan status: `{status}`",
        f"- Proposed artifacts: {len(artifacts)}",
    ]
    if review_summary:
        lines.append(f"- Notes: {review_summary}")
    if status != "approved":
        lines.append(f"- Reviewer action required: run `rh-skills promote approve {topic}`")
    lines.append("")

    lines.extend(["# Proposed Artifacts", ""])

    for artifact in artifacts:
        decision = artifact.get("reviewer_decision", "pending-review")
        icon = _DECISION_ICON.get(decision, "⏳")
        notes = artifact.get("approval_notes") or ""
        lines.extend([
            f"## {icon} {artifact.get('name', 'unknown')}",
            "",
            f"- Type: `{artifact.get('artifact_type', 'unknown')}`",
        ])
        if artifact.get("custom_artifact_type"):
            lines.append(f"- Custom type: `{artifact['custom_artifact_type']}`")
        lines.extend([
            f"- Purpose: {artifact.get('purpose', '')}",
            f"- Source coverage: {', '.join(artifact.get('source_files', []))}",
            f"- Rationale: {artifact.get('rationale', '')}",
            f"- Key questions: {', '.join(artifact.get('key_questions', []))}",
            f"- Required sections: {', '.join(artifact.get('required_sections', []))}",
        ])
        concerns = artifact.get("concerns") or []
        if concerns:
            lines.append("- Concerns:")
            for item in concerns:
                c = item.get("concern", item.get("conflict", item)) if isinstance(item, dict) else item
                r = item.get("resolution", "") if isinstance(item, dict) else ""
                lines.append(f"  - **Concern:** {c}")
                lines.append(f"    - **Resolution:** {r if r else '_pending_'}")
        else:
            lines.append("- Concerns: none identified during deterministic planning")
        lines.append(f"- **Reviewer decision: `{decision}`**")
        lines.append(f"- Approval notes: {notes if notes else '_pending reviewer input_'}")
        lines.append("")

    lines.extend(["# Cross-Artifact Issues", ""])
    if cross_issues:
        lines.extend([f"- {issue}" for issue in cross_issues])
    else:
        lines.extend([
            "- Confirm artifact boundaries avoid duplicate extraction across overlapping source sets.",
            "- Confirm terminology and threshold language are consistent across approved artifacts.",
        ])
    lines.append("")

    approved_count = sum(1 for a in artifacts if a.get("reviewer_decision") == "approved")
    lines.extend(["# Implementation Readiness", ""])
    if status == "approved":
        lines.extend([
            f"- Plan status: `approved` — {approved_count}/{len(artifacts)} artifact(s) approved.",
            "- Ready to run: `rh-skills promote implement <topic>`",
        ])
    else:
        lines.extend([
            "- Implement MUST NOT proceed until `status: approved` is set in `extract-plan.yaml`.",
            "- Every artifact intended for implementation must have `reviewer_decision: approved`.",
            f"- Run `rh-skills promote approve {topic}` to record decisions without editing YAML directly.",
        ])
    lines.append("")
    return "\n".join(lines)


def _write_plan_and_readout(plan_path: Path, readout_path: Path, plan: dict) -> None:
    """Persist plan YAML and regenerate the readout from current plan state."""
    buf = io.StringIO()
    _yaml_rt().dump(plan, buf)
    plan_path.write_text(buf.getvalue())
    readout_path.write_text(_render_extract_readout(plan))


@contextmanager
def _lock_plan(plan_path: Path):
    """Serialize concurrent approve calls via an exclusive file lock."""
    lock_path = plan_path.with_suffix(".lock")
    lock_fd = lock_path.open("w")
    try:
        lock_file(lock_fd)
        yield
    finally:
        unlock_file(lock_fd)
        lock_fd.close()


def _apply_artifact_decision(
    plan: dict, artifact_name: str, decision: str, notes: str = "",
    add_conflicts: tuple[str, ...] = (),
    add_sources: tuple[str, ...] = (),
) -> None:
    """Mutate plan in-place: set reviewer_decision, optional notes, append concerns/sources."""
    for artifact in plan.get("artifacts", []) or []:
        if artifact.get("name") == artifact_name:
            artifact["reviewer_decision"] = decision
            if notes:
                artifact["approval_notes"] = notes
            if add_conflicts:
                existing = artifact.get("concerns") or []
                new_entries = []
                for raw in add_conflicts:
                    parts = raw.split("|", 1)
                    new_entries.append({
                        "concern": parts[0].strip(),
                        "resolution": parts[1].strip() if len(parts) > 1 else "",
                    })
                artifact["concerns"] = existing + new_entries
            if add_sources:
                existing_sources = list(artifact.get("source_files") or [])
                for src in add_sources:
                    src = src.strip()
                    if src and src not in existing_sources:
                        existing_sources.append(src)
                artifact["source_files"] = existing_sources
            return
    raise click.UsageError(
        f"Artifact '{artifact_name}' not found in extract-plan.yaml. "
        f"Available: {[a.get('name') for a in plan.get('artifacts', [])]}"
    )


def _interactive_approve(
    plan: dict, plan_path: Path, readout_path: Path, reviewer: str | None
) -> None:
    """Walk pending artifacts interactively and optionally finalize the plan."""
    artifacts = plan.get("artifacts", []) or []
    pending = [a for a in artifacts if a.get("reviewer_decision") == "pending-review"]

    if not pending:
        click.echo("No artifacts pending review.")
    else:
        topic = plan.get("topic", "")
        click.echo(f"\nReviewing {len(pending)} pending artifact(s) for topic '{topic}':\n")
        for artifact in pending:
            name = artifact.get("name", "")
            art_type = artifact.get("artifact_type", "")
            sources = ", ".join(artifact.get("source_files", []))
            key_q = ", ".join(artifact.get("key_questions", []))
            concerns = artifact.get("concerns") or artifact.get("conflicts") or []
            click.echo(f"  Artifact : {name}")
            click.echo(f"  Type     : {art_type}")
            click.echo(f"  Sources  : {sources}")
            click.echo(f"  Question : {key_q}")
            if concerns:
                for item in concerns:
                    c = item.get("concern", item.get("conflict", item)) if isinstance(item, dict) else item
                    click.echo(f"  Concern  : {c}")

            choice = click.prompt(
                "  Decision",
                type=click.Choice(["approved", "rejected", "needs-revision", "skip"]),
                default="approved",
            )
            if choice == "skip":
                click.echo("  Skipped.\n")
                continue

            notes = click.prompt("  Notes (optional, Enter to skip)", default="", show_default=False)
            artifact["reviewer_decision"] = choice
            if notes:
                artifact["approval_notes"] = notes
            click.echo(f"  → {_DECISION_ICON.get(choice, '')} {choice}\n")

    all_decided = all(a.get("reviewer_decision") != "pending-review" for a in artifacts)
    if all_decided and click.confirm("Finalize plan as approved?", default=True):
        rev = reviewer or plan.get("reviewer") or ""
        if not rev:
            rev = click.prompt("Reviewer name", default="")
        plan["status"] = "approved"
        plan["reviewer"] = rev
        plan["reviewed_at"] = now_iso()

    _write_plan_and_readout(plan_path, readout_path, plan)
    approved = sum(1 for a in artifacts if a.get("reviewer_decision") == "approved")
    log_info(f"Plan updated: {approved}/{len(artifacts)} artifact(s) approved, status={plan['status']}")


def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke configured LLM provider, or return stub response."""
    provider = config_value("LLM_PROVIDER", "stub")

    if provider == "stub":
        stub = config_value("RH_STUB_RESPONSE", "Stub response")
        return stub

    if provider == "ollama":
        return _invoke_ollama(system_prompt, user_prompt)

    if provider == "anthropic":
        return _invoke_anthropic(system_prompt, user_prompt)

    if provider in ("openai", "openai-compatible"):
        return _invoke_openai(system_prompt, user_prompt)

    raise click.ClickException(
        f"LLM provider '{provider}' is not supported. "
        "Set LLM_PROVIDER to one of: ollama, anthropic, openai"
    )


def _invoke_ollama(system_prompt: str, user_prompt: str) -> str:
    """Call a local Ollama instance."""
    import httpx

    endpoint = config_value("OLLAMA_ENDPOINT", "http://localhost:11434")
    model = config_value("OLLAMA_MODEL", "mistral")
    url = endpoint.rstrip("/") + "/api/chat"

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        response = httpx.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["message"]["content"]
    except httpx.HTTPError as exc:
        raise click.ClickException(f"Ollama request failed: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise click.ClickException(f"Unexpected Ollama response format: {exc}") from exc


def _invoke_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Call the Anthropic Messages API."""
    import httpx

    api_key = config_value("ANTHROPIC_API_KEY")
    if not api_key:
        raise click.ClickException(
            "ANTHROPIC_API_KEY is not set. Configure it in .rh-skills.toml or as an environment variable."
        )
    model = config_value("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 8096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except httpx.HTTPError as exc:
        raise click.ClickException(f"Anthropic request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise click.ClickException(f"Unexpected Anthropic response format: {exc}") from exc


def _invoke_openai(system_prompt: str, user_prompt: str) -> str:
    """Call an OpenAI-compatible chat completions endpoint."""
    import httpx

    api_key = config_value("OPENAI_API_KEY", "")
    endpoint = config_value("OPENAI_ENDPOINT", "https://api.openai.com/v1/chat/completions")
    model = config_value("OPENAI_MODEL", "gpt-4o-mini")

    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        response = httpx.post(endpoint, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise click.ClickException(f"OpenAI request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise click.ClickException(f"Unexpected OpenAI response format: {exc}") from exc


def _sanitize_yaml(raw_text: str) -> str:
    """Round-trip YAML through ruamel to fix quoting issues.

    LLM-generated YAML often contains unquoted scalars that start with ``>``,
    ``<``, ``>=``, ``<=``, or bare ``-`` which YAML interprets as block-scalar
    indicators or sequence entries.

    Strategy:
    1. **Regex pre-pass** — quote values that match known-dangerous patterns.
    2. **Round-trip** through ruamel.yaml so the output is canonical.

    Returns sanitized text, or the original text if repair still fails.
    """
    import re
    from ruamel.yaml.error import YAMLError as _YE

    # Pre-pass: quote unquoted mapping values starting with >, <, or bare -
    def _quote_value(m):
        prefix = m.group(1)
        value = m.group(2)
        if value.startswith('"') or value.startswith("'"):
            return m.group(0)
        return f'{prefix}"{value}"'

    # Pattern 1: mapping values — `key: <dangerous-value>`
    patched = re.sub(
        r'^( *[A-Za-z_][A-Za-z0-9_-]*: )((?:[><])(?:[^\n]*))$',
        _quote_value,
        raw_text,
        flags=re.MULTILINE,
    )
    # Also quote bare `-` as a mapping value (YAML treats it as sequence)
    patched = re.sub(
        r'^( *[A-Za-z_][A-Za-z0-9_-]*: )(-)$',
        _quote_value,
        patched,
        flags=re.MULTILINE,
    )

    # Pattern 2: sequence entries — `  - <dangerous-value>`
    # Only quote if the value after `- ` starts with > or <
    patched = re.sub(
        r'^( *- )([><][^\n]*)$',
        _quote_value,
        patched,
        flags=re.MULTILINE,
    )

    y = YAML()
    y.preserve_quotes = True
    try:
        data = y.load(patched)
    except _YE:
        return raw_text  # let downstream validate surface the error
    if data is None:
        return raw_text
    buf = io.StringIO()
    y.dump(data, buf)
    return buf.getvalue()


@click.group()
def promote():
    """Promote artifacts between lifecycle levels."""


@promote.command("plan")
@click.argument("topic")
@click.option("--force", is_flag=True, help="Overwrite an existing extract-plan.md")
def plan(topic, force):
    """Write topics/<topic>/process/plans/extract-plan.yaml and extract-plan-readout.md."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan_path = _extract_plan_path(topic)
    if plan_path.exists() and not force:
        log_warn("extract-plan.yaml already exists. Re-run with --force to overwrite it.")
        return

    source_records = _normalized_source_records(tracking, topic)
    if not source_records:
        log_warn("No normalized sources found. Run rh-inf-ingest first.")
        return

    grouped = _group_sources_for_extract_plan(source_records)
    artifacts = []
    for group in grouped:
        concerns = _identify_group_concerns(group)
        artifacts.append(_build_plan_artifact_entry(group, concerns=concerns))
    concepts_path = topic_dir(topic) / "process" / "concepts.yaml"
    has_concepts = concepts_path.exists()

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_yaml = _render_extract_plan(topic, artifacts, has_concepts)
    plan_path.write_text(plan_yaml)
    plan = _yaml_safe().load(plan_yaml)
    _extract_readout_path(topic).write_text(_render_extract_readout(plan))

    append_topic_event(
        tracking,
        topic,
        "extract_planned",
        f"Wrote extract plan: topics/{topic}/process/plans/extract-plan.yaml",
    )
    save_tracking(tracking)
    log_info(f"Created: {plan_path}")
    log_info(f"Created: {_extract_readout_path(topic)}")
    click.echo("\nNext steps:")
    click.echo(f"  1. Review the readout : cat topics/{topic}/process/plans/extract-plan-readout.md")
    click.echo(f"  2. Approve artifacts  : rh-inf-extract approve {topic}")
    click.echo(f"  3. Run extraction     : rh-inf-extract implement {topic}")


@promote.command("approve")
@click.argument("topic")
@click.option(
    "--artifact", "artifact_name", default=None, metavar="NAME",
    help="Artifact name to set decision on (non-interactive).",
)
@click.option(
    "--decision",
    type=click.Choice(["approved", "rejected", "needs-revision"]),
    default=None,
    help="Decision for --artifact.",
)
@click.option("--notes", default="", help="Approval notes (used with --artifact).")
@click.option(
    "--add-conflict", "add_conflicts", multiple=True, metavar="TEXT",
    help="Append a concern to the artifact's concerns list. Use 'concern text' or 'concern|resolution' format (repeatable).",
)
@click.option(
    "--add-source", "add_sources", multiple=True, metavar="SLUG",
    help="Add a missing source slug to the artifact's source_files list (repeatable).",
)
@click.option("--reviewer", default=None, help="Reviewer name written to plan header.")
@click.option(
    "--review-summary", "review_summary", default=None,
    help="Plan-level review summary written to extract-plan.yaml (required when concerns exist).",
)
@click.option(
    "--finalize", is_flag=True,
    help="Set plan status to 'approved' and record reviewer/timestamp.",
)
def approve(topic, artifact_name, decision, notes, add_conflicts, add_sources, reviewer, review_summary, finalize):
    """Record reviewer decisions on extract-plan.yaml artifacts.

    \b
    Non-interactive (AI agent / script):
      # Approve one artifact and finalize in a single atomic call (recommended):
      rh-skills promote approve TOPIC --artifact NAME --decision approved --finalize [--reviewer NAME]

      # Record a cross-source conflict and finalize:
      rh-skills promote approve TOPIC --artifact NAME --decision approved \\
        --add-conflict "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%" --finalize

      # Add a source the planner omitted (e.g. planner split conflicting sources):
      rh-skills promote approve TOPIC --artifact NAME --decision approved \\
        --add-source aace-guidelines-2022 --add-conflict "HbA1c target" --finalize

      # Or as separate sequential calls:
      rh-skills promote approve TOPIC --artifact NAME --decision approved [--notes TEXT]
      rh-skills promote approve TOPIC --finalize [--reviewer NAME]

    Interactive (human terminal):
      rh-skills promote approve TOPIC
    """
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan_path = _extract_plan_path(topic)
    readout_path = _extract_readout_path(topic)
    if not plan_path.exists():
        raise click.UsageError(
            f"No extract plan found. Run 'rh-skills promote plan {topic}' first."
        )

    # Non-interactive path: serialize concurrent approve calls with a file lock
    # so parallel agent invocations don't clobber each other's artifact decisions.
    if artifact_name or finalize:
        with _lock_plan(plan_path):
            plan = _yaml_safe().load(plan_path.read_text())
            if not plan or not isinstance(plan, dict):
                raise click.UsageError(f"Plan is empty or invalid: {plan_path}")

            if artifact_name:
                if not decision:
                    raise click.UsageError("--decision is required when --artifact is specified.")
                _apply_artifact_decision(plan, artifact_name, decision, notes, add_conflicts, add_sources)
                if review_summary is not None:
                    plan["review_summary"] = review_summary
                _write_plan_and_readout(plan_path, readout_path, plan)
                log_info(f"Artifact '{artifact_name}' → {_DECISION_ICON.get(decision, '')} {decision}")

            if finalize:
                if not artifact_name:
                    # Re-read so we see writes from prior locked invocations.
                    plan = _yaml_safe().load(plan_path.read_text())
                rev = reviewer or plan.get("reviewer") or ""
                plan["status"] = "approved"
                plan["reviewer"] = rev
                plan["reviewed_at"] = now_iso()
                if review_summary is not None:
                    plan["review_summary"] = review_summary
                _write_plan_and_readout(plan_path, readout_path, plan)
                approved = sum(1 for a in plan.get("artifacts", []) if a.get("reviewer_decision") == "approved")
                total = len(plan.get("artifacts", []))
                log_info(f"Plan finalized: status=approved, {approved}/{total} artifact(s) approved")
        return

    if not sys.stdin.isatty():
        raise click.UsageError(
            "stdin is not a TTY — use --artifact NAME --decision DECISION for non-interactive approval, "
            "or --finalize to set plan status."
        )
    plan = _yaml_safe().load(plan_path.read_text())
    if not plan or not isinstance(plan, dict):
        raise click.UsageError(f"Plan is empty or invalid: {plan_path}")
    _interactive_approve(plan, plan_path, readout_path, reviewer)


@promote.command("formalize-plan")
@click.argument("topic")
@click.option("--force", is_flag=True, help="Overwrite an existing formalize-plan.yaml")
def formalize_plan(topic, force):
    """Write topics/<topic>/process/plans/formalize-plan.yaml from approved L2 artifacts."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan_path = _formalize_plan_path(topic)
    if plan_path.exists() and not force:
        log_warn("formalize-plan.yaml already exists. Re-run with --force to overwrite it.")
        return

    try:
        eligible_inputs, blocked_inputs = _eligible_formalize_inputs(topic)
    except click.UsageError as exc:
        log_warn(str(exc))
        return

    if not eligible_inputs:
        log_warn(
            "No approved structured artifacts are ready for formalization. "
            "Approve extract artifacts and ensure they pass validation first."
        )
        return

    artifacts = _build_formalize_artifacts(topic, eligible_inputs)
    plan = _build_formalize_plan_dict(topic, artifacts)
    readout_path = _formalize_readout_path(topic)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    _write_formalize_plan_and_readout(plan_path, readout_path, topic, plan, blocked_inputs)

    append_topic_event(
        tracking,
        topic,
        "formalize_planned",
        f"Wrote formalize plan: topics/{topic}/process/plans/formalize-plan.yaml",
    )
    save_tracking(tracking)
    log_info(f"Created: {plan_path}")
    log_info(f"Created: {readout_path}")
    click.echo("\nNext steps:")
    click.echo(f"  1. Review the readout : cat topics/{topic}/process/plans/formalize-plan-readout.md")
    click.echo(f"  2. Approve the target : edit topics/{topic}/process/plans/formalize-plan.yaml")
    click.echo(f"  3. Run formalization  : rh-inf-formalize implement {topic}")


@promote.command()
@click.argument("topic")
@click.argument("name")
@click.option("--source", required=True, multiple=True, help="L1 source name (can repeat)")
@click.option("--count", default=1, help="Number of L2 artifacts to generate")
@click.option("--artifact-type", default=None, help="Extract artifact type for richer L2 output")
@click.option("--clinical-question", default=None, help="Clinical question answered by this artifact")
@click.option("--required-section", "required_sections", multiple=True,
              help="Required section to emit in the L2 artifact (repeatable)")
@click.option("--evidence-ref", "evidence_refs", multiple=True,
              help="Claim evidence in 'claim_id|statement|source|locator' format (repeatable)")
@click.option("--conflict", "conflicts", multiple=True,
              help="Conflict in 'issue|source|statement[|preferred_source|preferred_rationale]' format")
@click.option("--dry-run", is_flag=True, help="Print what would be created without doing it")
def derive(
    topic,
    name,
    source,
    count,
    artifact_type,
    clinical_question,
    required_sections,
    evidence_refs,
    conflicts,
    dry_run,
):
    """Promote L1 source(s) to L2 structured artifact(s)."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    # Validate each source exists in tracking; support both `name` and `id` keys.
    registered_sources = {s.get("name") or s.get("id", "") for s in tracking.get("sources", [])}
    for src in source:
        if src not in registered_sources:
            raise click.UsageError(f"Source '{src}' not found in tracking.yaml sources")

    td = topic_dir(topic)

    if count > 1:
        artifact_names = [f"{name}-{i}" for i in range(1, count + 1)]
    else:
        artifact_names = [name]

    system_prompt = """\
You are a healthcare informatics specialist. Your task is to extract and structure \
clinical knowledge from raw discovery artifacts into a semi-structured YAML format.

The output MUST be valid YAML with these required fields:
  id, name, title, version, status, domain, description, derived_from

Rules:
- id: kebab-case identifier
- name: short machine name (no spaces)
- title: human-readable title
- version: "1.0.0"
- status: draft
- domain: clinical domain (e.g. diabetes, sepsis, hypertension)
- description: clear clinical description (2-4 sentences)
- derived_from: list containing the source L1 artifact name

Output ONLY the YAML block. No markdown fences, no explanation."""

    for artifact_name in artifact_names:
        user_prompt = (
            f"Source L1 artifact name: {', '.join(source)}\n"
            f"Generate L2 artifact: {artifact_name}\n"
            f"Artifact type: {artifact_type or 'evidence-summary'}\n"
            f"Clinical question: {clinical_question or ''}"
        )

        if dry_run:
            click.echo(f"--- DRY RUN: derive prompt for {artifact_name} ---")
            click.echo(f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}")
            continue

        click.echo(f"Deriving L2 artifact: {artifact_name} (from {', '.join(source)})...")

        # Warn when artifact-type overrides the plan name — agents should use
        # matching names (e.g. --artifact-type care-pathway → name care-pathway).
        if artifact_type and artifact_name != artifact_type:
            log_warn(
                f"Artifact name '{artifact_name}' does not match --artifact-type '{artifact_type}'. "
                f"Consider using '{artifact_type}' as the artifact name for consistency."
            )

        llm_output = _invoke_llm(system_prompt, user_prompt)

        l2_file = td / "structured" / artifact_name / f"{artifact_name}.yaml"
        l2_file.parent.mkdir(parents=True, exist_ok=True)

        if llm_output == "Stub response":
            # Write a minimal valid L2 artifact template for stub mode
            l2_file.write_text(
                _build_stub_l2_artifact(
                    artifact_name,
                    source,
                    artifact_type,
                    clinical_question,
                    required_sections,
                    evidence_refs,
                    conflicts,
                )
            )
        else:
            l2_file.write_text(_sanitize_yaml(llm_output + "\n"))

        timestamp = now_iso()
        checksum = sha256_file(l2_file)
        topic_entry = require_topic(tracking, topic)
        topic_entry.setdefault("structured", []).append({
            "name": artifact_name,
            "file": f"topics/{topic}/structured/{artifact_name}/{artifact_name}.yaml",
            "created_at": timestamp,
            "checksum": checksum,
            "derived_from": list(source),
            "artifact_type": artifact_type or "evidence-summary",
        })
        append_topic_event(tracking, topic, "structured_derived", f"Derived {artifact_name} from {', '.join(source)}")
        save_tracking(tracking)

        log_info(f"Created: {l2_file}")


@promote.command()
@click.argument("topic")
@click.argument("sources", nargs=-1, required=True)
@click.option("--dry-run", is_flag=True, help="Print what would be created without doing it")
def combine(topic, sources, dry_run):
    """Promote L2 artifacts to a single L3 computable artifact.

    Sources: all positional args — last one is the target name, rest are L2 source names.
    Example: rh-skills promote combine mytopic l2-a l2-b l3-target

    DEPRECATED: Use 'rh-skills formalize' + 'rh-skills package' instead.
    """
    import warnings
    warnings.warn(
        "promote combine is deprecated. Use 'rh-skills formalize <topic> <artifact>' "
        "for individual FHIR JSON generation and 'rh-skills package <topic>' "
        "for FHIR NPM packaging.",
        DeprecationWarning,
        stacklevel=2,
    )
    log_warn(
        "DEPRECATED: 'promote combine' will be removed in a future release. "
        "Use 'rh-skills formalize' + 'rh-skills package' instead."
    )

    if len(sources) < 2:
        raise click.UsageError("combine requires at least one source and one target name")

    l2_source_names = list(sources[:-1])
    target_name = sources[-1]

    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    # Validate L2 sources exist in tracking
    registered_l2 = {a["name"] for a in topic_entry.get("structured", [])}
    for src in l2_source_names:
        if src not in registered_l2:
            raise click.UsageError(f"L2 artifact '{src}' not found in topic '{topic}'")

    td = topic_dir(topic)
    today = today_date()

    system_prompt = """\
You are a healthcare informatics specialist. Your task is to converge multiple \
semi-structured L2 YAML artifacts into a single computable L3 YAML artifact.

The output MUST be valid YAML with this structure:

artifact_schema_version: "1.0"
metadata:
  id: # kebab-case
  name: # short machine name
  title: # human-readable title
  version: "1.0.0"
  status: draft
  domain: # clinical domain
  created_date: # YYYY-MM-DD
  description: # clear description
converged_from:
  - <l2-artifact-name>

Output ONLY the YAML block. No markdown fences, no explanation."""

    user_prompt = f"Output artifact name (id): {target_name}\nToday's date: {today}\nSources: {', '.join(l2_source_names)}"

    if dry_run:
        click.echo(f"--- DRY RUN: combine prompt for {target_name} ---")
        click.echo(f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}")
        return

    click.echo(f"Combining L2 artifacts into L3: {target_name}...")
    click.echo(f"Sources: {', '.join(l2_source_names)}")

    llm_output = _invoke_llm(system_prompt, user_prompt)

    l3_file = td / "computable" / f"{target_name}.yaml"

    if llm_output == "Stub response":
        l3_file.write_text(f"""\
artifact_schema_version: "1.0"
metadata:
  id: {target_name}
  name: {target_name}
  title: ""
  version: "1.0.0"
  status: draft
  domain: ""
  created_date: {today}
  description: ""
converged_from:
{chr(10).join(f"  - {s}" for s in l2_source_names)}
""")
    else:
        l3_file.write_text(_sanitize_yaml(llm_output + "\n"))

    timestamp = now_iso()
    checksum = sha256_file(l3_file)
    topic_entry["computable"].append({
        "name": target_name,
        "file": f"topics/{topic}/computable/{target_name}.yaml",
        "created_at": timestamp,
        "checksum": checksum,
        "converged_from": l2_source_names,
    })
    append_topic_event(tracking, topic, "computable_converged", f"Converged {target_name} from {', '.join(l2_source_names)}")
    save_tracking(tracking)

    log_info(f"Created: {l3_file}")


@promote.command("conflicts")
@click.argument("topic")
def conflicts(topic):
    """List open (unresolved) conflicts across extract and formalize plans.

    Scans both extract-plan.yaml and formalize-plan.yaml (whichever exist) and
    reports every conflict entry whose resolution field is empty or absent.
    Exit code 0 in all cases; use the output to decide whether to proceed.

    Example (agent workflow):
      rh-skills promote conflicts diabetes-ccm

    Each conflict line includes: plan type, artifact name, index, conflict text.
    Use 'resolve-conflict' to record a resolution.
    """
    open_conflicts = _collect_open_conflicts(topic)
    if not open_conflicts:
        click.echo(f"No open conflicts for topic '{topic}'.")
        return

    click.echo(f"Open conflicts for topic '{topic}':\n")
    for c in open_conflicts:
        click.echo(
            f"  plan={c['plan_type']}  artifact={c['artifact']}  index={c['index']}"
        )
        click.echo(f"    Conflict  : {c['conflict']}")
        click.echo(f"    Resolution: {c['resolution'] or '_pending_'}")
        click.echo()

    click.echo(
        f"Total: {len(open_conflicts)} open conflict(s). "
        "Use 'rh-skills promote resolve-conflict' to record resolutions."
    )


@promote.command("resolve-conflict")
@click.argument("topic")
@click.option(
    "--artifact", "artifact_name", required=True, metavar="NAME",
    help="Name of the artifact containing the conflict.",
)
@click.option(
    "--index", "conflict_index", required=True, type=int, metavar="N",
    help="0-based index of the conflict entry within the artifact's conflicts list.",
)
@click.option(
    "--resolution", required=True, metavar="TEXT",
    help="Resolution text to record for this conflict.",
)
@click.option(
    "--plan", "plan_type", required=True,
    type=click.Choice(["extract", "formalize"]),
    help="Which plan file to update (extract-plan.yaml or formalize-plan.yaml).",
)
def resolve_conflict(topic, artifact_name, conflict_index, resolution, plan_type):
    """Record the resolution for a specific conflict entry.

    Use 'rh-skills promote conflicts <topic>' first to list open conflicts and
    their indices, then call this command for each one.

    Example:
      # List open conflicts first:
      rh-skills promote conflicts diabetes-ccm

      # Then resolve each by plan/artifact/index:
      rh-skills promote resolve-conflict diabetes-ccm \\
        --plan extract --artifact screening-decisions --index 0 \\
        --resolution "ADA 2024 is the primary guideline; USPSTF framing is supplementary."
    """
    if plan_type == "extract":
        plan_path = _extract_plan_path(topic)
        readout_path = _extract_readout_path(topic)
        load_fn = _load_extract_plan
    else:
        plan_path = _formalize_plan_path(topic)
        readout_path = _formalize_readout_path(topic)
        load_fn = _load_formalize_plan

    plan = load_fn(topic)
    _set_conflict_resolution(plan, artifact_name, conflict_index, resolution)

    if plan_type == "extract":
        _write_plan_and_readout(plan_path, readout_path, plan)
    else:
        blocked_inputs: list[str] = []
        try:
            _, blocked_inputs = _eligible_formalize_inputs(topic)
        except Exception:
            pass
        _write_formalize_plan_and_readout(topic, plan, blocked_inputs)

    remaining = _collect_open_conflicts(topic)
    remaining_this_plan = [c for c in remaining if c["plan_type"] == plan_type]
    click.echo(
        f"Resolved conflict {conflict_index} on '{artifact_name}' "
        f"in {plan_type}-plan.yaml."
    )
    if remaining_this_plan:
        click.echo(
            f"{len(remaining_this_plan)} open conflict(s) remain in {plan_type}-plan.yaml."
        )
    else:
        click.echo(f"No open conflicts remain in {plan_type}-plan.yaml.")
