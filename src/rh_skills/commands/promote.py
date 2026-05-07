"""rh-skills promote — Promote artifacts between lifecycle levels."""

import csv
import hashlib
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
from rh_skills.commands.validate import (
    validate_artifact_file,
)

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
        "section": ["events", "conditions", "actions", "rules"],
        "key_question": "What event triggers, conditions, eligibility, exclusions, and actions form the decision logic?",
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


def _concept_review_csv_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "concepts-review.csv"


def _concept_review_meta_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "concepts-review-meta.yaml"


def _concept_artifact_path(topic: str) -> Path:
    return topic_dir(topic) / "structured" / "concepts.yaml"


_CONCEPT_CSV_FIELDNAMES = [
    "concept_name", "concept_type", "sources", "context", "lookup_query", "lookup_notes",
    "system", "code", "display", "distance",
    "confidence (high/medium/low)", "code status (approve/reject)", "remove concept (true/false)", "comment",
]


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _csv_checksum(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_concept_review_meta(topic: str) -> dict:
    meta_path = _concept_review_meta_path(topic)
    if not meta_path.exists():
        raise click.UsageError(
            f"No concept review found. Run 'rh-skills promote plan {topic}' first."
        )
    data = _yaml_safe().load(meta_path.read_text()) or {}
    if not isinstance(data, dict):
        raise click.UsageError(f"Concept review meta is invalid: {meta_path}")
    return data


def _write_concept_review_meta(topic: str, meta: dict) -> Path:
    meta_path = _concept_review_meta_path(topic)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    _yaml_rt().dump(meta, buf)
    meta_path.write_text(buf.getvalue())
    return meta_path


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
    _require_concept_review_approved(plan)
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


def _require_concept_review_approved(plan: dict) -> None:
    concept_review = plan.get("concept_review") or {}
    if not concept_review:
        return
    topic = plan.get("topic", "<topic>")
    meta_path = _concept_review_meta_path(topic)
    if meta_path.exists():
        meta = _yaml_safe().load(meta_path.read_text()) or {}
        status = meta.get("status", "pending-review")
    else:
        status = concept_review.get("status", "pending-review")
    if status != "approved":
        raise click.UsageError(
            f"Concept review is not approved — finalization is blocked. "
            f"Edit topics/{topic}/process/plans/concepts-review.csv then run: "
            f"'rh-skills promote concept review {topic} --finalize --reviewer <name>'."
        )


def _concern_text(item: object) -> str:
    """Return the human-readable concern/conflict description from an entry."""
    if isinstance(item, dict):
        return item.get("concern") or item.get("conflict") or item.get("issue") or str(item)
    return str(item)


def _collect_open_concerns(topic: str) -> list[dict]:
    """Return all unresolved concern entries across extract and formalize plans.

    Each entry is a dict with keys:
      plan_type, artifact, index, concern, resolution
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
                        "concern": _concern_text(item),
                        "resolution": resolution,
                    })
    return results


def _set_concern_resolution(plan: dict, artifact_name: str, index: int, resolution: str) -> None:
    """Mutate plan in-place: set resolution on concerns[index] or conflicts[index]."""
    for artifact in plan.get("artifacts") or []:
        if artifact.get("name") == artifact_name:
            # extract plans use 'concerns'; formalize plans use 'conflicts'
            field = "concerns" if "concerns" in artifact else "conflicts"
            items = artifact.get(field) or []
            if index < 0 or index >= len(items):
                raise click.UsageError(
                    f"Concern index {index} out of range for artifact '{artifact_name}' "
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


def _parse_concerns(raw_concerns: tuple[str, ...]) -> list[dict]:
    """Parse --concern flags into concern entries.

    Flags with the same issue are merged into one entry with multiple positions.
    The preferred_interpretation comes from whichever flag supplies it.

    Formats:
      issue|source|statement
      issue|source|statement|preferred_source|preferred_rationale
    """
    merged: dict[str, dict] = {}
    for raw in raw_concerns:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 3:
            raise click.UsageError(
                "--concern must use 'issue|source|statement' or "
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


def _load_body_file(path: str) -> dict:
    data = _yaml_safe().load(Path(path).read_text()) or {}
    if not isinstance(data, dict):
        raise click.UsageError("--body-file must contain a YAML mapping at the top level")
    return data


def _canonicalize_evidence_refs(entries: list[dict]) -> set[tuple[str, str, str, str]]:
    canonical: set[tuple[str, str, str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        claim_id = entry.get("claim_id")
        statement = entry.get("statement")
        if not claim_id or not statement:
            continue
        for evidence in entry.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            source = evidence.get("source")
            locator = evidence.get("locator")
            if source and locator:
                canonical.add((claim_id, statement, source, locator))
    return canonical


def _canonicalize_concerns(concerns: list[dict]) -> dict[str, dict]:
    canonical: dict[str, dict] = {}
    for concern in concerns:
        if not isinstance(concern, dict):
            continue
        issue = concern.get("issue")
        if not issue:
            continue
        positions = []
        for position in concern.get("positions") or []:
            if not isinstance(position, dict):
                continue
            source = position.get("source")
            statement = position.get("statement")
            if source and statement:
                positions.append((source, statement))
        preferred = concern.get("preferred_interpretation") or {}
        canonical[issue] = {
            "positions": set(positions),
            "preferred_source": preferred.get("source"),
            "preferred_rationale": preferred.get("rationale"),
        }
    return canonical


def _validate_body_file_consistency(
    *,
    artifact_name: str,
    source: tuple[str, ...],
    artifact_type: str | None,
    clinical_question: str | None,
    required_sections: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    concerns: tuple[str, ...],
    body: dict,
) -> None:
    body_id = body.get("id")
    if body_id and body_id != artifact_name:
        raise click.UsageError(
            f"--body-file id '{body_id}' does not match artifact name '{artifact_name}'"
        )

    body_name = body.get("name")
    if body_name and body_name != artifact_name:
        raise click.UsageError(
            f"--body-file name '{body_name}' does not match artifact name '{artifact_name}'"
        )

    body_sources = body.get("derived_from")
    if body_sources is not None:
        if not isinstance(body_sources, list):
            raise click.UsageError("--body-file derived_from must be a list")
        if set(body_sources) != set(source):
            raise click.UsageError(
                "--body-file derived_from does not match --source values: "
                f"expected {sorted(source)}, got {sorted(body_sources)}"
            )

    if artifact_type and body.get("artifact_type") and body["artifact_type"] != artifact_type:
        raise click.UsageError(
            "--artifact-type does not match --body-file artifact_type: "
            f"expected '{artifact_type}', got '{body['artifact_type']}'"
        )

    if clinical_question and body.get("clinical_question") and body["clinical_question"] != clinical_question:
        raise click.UsageError("--clinical-question does not match --body-file clinical_question")

    if required_sections:
        sections = body.get("sections")
        if not isinstance(sections, dict):
            raise click.UsageError(
                "--required-section was provided, but --body-file sections is missing or invalid"
            )
        missing_sections = [name for name in required_sections if name not in sections]
        if missing_sections:
            raise click.UsageError(
                "--required-section values are missing from --body-file sections: "
                + ", ".join(missing_sections)
            )

    if evidence_refs:
        expected_refs = {
            (entry["claim_id"], entry["statement"], ev["source"], ev["locator"])
            for entry in _parse_evidence_refs(evidence_refs)
            for ev in entry["evidence"]
        }
        actual_refs = _canonicalize_evidence_refs(body.get("sections", {}).get("evidence_traceability", []))
        missing_refs = expected_refs - actual_refs
        if missing_refs:
            raise click.UsageError(
                "--evidence-ref values do not match --body-file evidence_traceability entries"
            )

    if concerns:
        expected_conflicts = _canonicalize_concerns(_parse_concerns(concerns))
        actual_conflicts = _canonicalize_concerns(body.get("concerns") or body.get("conflicts") or [])
        mismatched_issues: list[str] = []
        for issue, expected in expected_conflicts.items():
            actual = actual_conflicts.get(issue)
            if actual is None:
                mismatched_issues.append(issue)
                continue
            if not expected["positions"].issubset(actual["positions"]):
                mismatched_issues.append(issue)
                continue
            if expected["preferred_source"] and expected["preferred_source"] != actual["preferred_source"]:
                mismatched_issues.append(issue)
                continue
            if expected["preferred_rationale"] and expected["preferred_rationale"] != actual["preferred_rationale"]:
                mismatched_issues.append(issue)
        if mismatched_issues:
            raise click.UsageError(
                "--concern values do not match --body-file concerns for issue(s): "
                + ", ".join(sorted(mismatched_issues))
            )


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
    "events": [{"id": "event-001", "label": "<stub: triggering event>", "description": "<stub: event description>"}],
    "conditions": [{"id": "cond-001", "label": "<stub: condition>", "values": ["Yes", "No"]}],
    "rules": [{"id": "rule-001", "event": "event-001", "when": {"cond-001": "Yes"}, "then": ["approve"]},
              {"id": "rule-002", "event": "event-001", "when": {"cond-001": "No"}, "then": ["deny"]}],
    # care-pathway sections
    "steps": [{"step": 1, "description": "<stub: step>", "actor": "<stub: actor>", "next": 2}],
    "triggers": [{"id": "trigger-001", "description": "<stub: trigger event>"}],
    # terminology sections
    "value_sets": [{"id": "vs-001", "name": "<stub: value set>", "system": "<stub: system>", "codes": []}],
    "concept_maps": [{"id": "cm-001", "source_system": "<stub: source>", "target_system": "<stub: target>",
                      "mappings": [{"source_code": "<stub>", "target_code": "<stub>", "equivalence": "equivalent"}]}],
    "concerns": [{"issue": "<stub: concern>", "disposition": "<stub: disposition>"}],
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
    concern_refs: tuple[str, ...],
    artifact_type: str | None = None,
) -> dict:
    section_names = list(required_sections) if required_sections else ["summary"]
    evidence_entries = _parse_evidence_refs(evidence_refs)
    concern_entries = _parse_concerns(concern_refs)
    if evidence_entries and "evidence_traceability" not in section_names:
        section_names.append("evidence_traceability")
    if concern_entries and "concerns" not in section_names:
        section_names.append("concerns")

    sections: dict = {}
    for name in section_names:
        if name == "summary":
            sections[name] = clinical_question or ""
        elif name == "evidence_traceability":
            sections[name] = evidence_entries
        elif name == "concerns":
            sections[name] = [
                {"issue": entry["issue"], "disposition": "<pending reviewer resolution>"}
                for entry in concern_entries
                if isinstance(entry, dict) and entry.get("issue")
            ]
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
    concerns: tuple[str, ...],
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
        "sections": _build_sections(required_sections, clinical_question, evidence_refs, concerns, artifact_type),
        "concerns": _parse_concerns(concerns),
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


def _collect_frontmatter_concepts(source_records: list[dict]) -> list[dict]:
    """Return deduplicated concepts aggregated from normalized front matter."""
    deduped: dict[tuple[str, str], dict] = {}
    for record in source_records:
        frontmatter = _parse_markdown_frontmatter(record["path"])
        concepts = frontmatter.get("concepts") or []
        if not isinstance(concepts, list):
            continue
        for concept in concepts:
            if not isinstance(concept, dict):
                continue
            name = str(concept.get("name") or "").strip()
            concept_type = str(concept.get("type") or "").strip()
            if not name or not concept_type:
                continue
            key = (name.casefold(), concept_type.casefold())
            entry = deduped.setdefault(
                key,
                {
                    "name": name,
                    "type": concept_type,
                    "sources": [],
                    "source_files": [],
                    "context": "",
                },
            )
            if record["name"] not in entry["sources"]:
                entry["sources"].append(record["name"])
            if record["relative_path"] not in entry["source_files"]:
                entry["source_files"].append(record["relative_path"])
            if not entry["context"]:
                ctx = str(concept.get("context") or "").strip()
                if ctx:
                    entry["context"] = ctx
    return sorted(
        deduped.values(),
        key=lambda item: (item["name"].casefold(), item["type"].casefold()),
    )


def _build_concept_review(topic: str, concepts: list[dict]) -> dict | None:
    if not concepts:
        return None
    # Collect the deduplicated set of source file paths across all concepts
    source_files: list[str] = []
    seen: set[str] = set()
    for c in concepts:
        for sf in c.get("source_files") or []:
            if sf not in seen:
                source_files.append(sf)
                seen.add(sf)
    return {
        "source_files": source_files,
        "status": "pending-review",
        "concept_count": len(concepts),
        "review_artifact": f"topics/{topic}/process/plans/concepts-review.csv",
        "final_artifact": f"topics/{topic}/structured/concepts.yaml",
    }


def _build_concept_review_csvs(topic: str, concepts: list[dict]) -> tuple[Path, Path]:
    """Write concepts-review.csv and concepts-review-meta.yaml.

    One row per concept (placeholder — no candidates yet). concept enrich adds
    candidate rows per concept. Returns (csv_path, meta_path).
    """
    csv_path = _concept_review_csv_path(topic)
    rows = [
        {
            "concept_name": c["name"],
            "concept_type": c["type"],
            "sources": "; ".join(c.get("sources") or []),
            "context": c.get("context") or "",
            "lookup_query": c["name"],
            "lookup_notes": "",
            "system": "",
            "code": "",
            "display": "",
            "distance": "",
            "confidence (high/medium/low)": "",
            "code status (approve/reject)": "",
            "remove concept (true/false)": "",
            "comment": "",
        }
        for c in concepts
    ]
    _write_csv(csv_path, rows, _CONCEPT_CSV_FIELDNAMES)
    meta: dict = {
        "topic": topic,
        "status": "pending-review",
        "generated_at": now_iso(),
        "reviewed_at": None,
        "reviewer": "",
        "csv_checksum": _csv_checksum(csv_path),
        "final_artifact": f"topics/{topic}/structured/concepts.yaml",
    }
    meta_path = _write_concept_review_meta(topic, meta)
    return csv_path, meta_path


def _write_concepts_l2_artifact_from_csv(topic: str, tracking: dict) -> Path:
    """Build and write concepts.yaml from concepts-review.csv."""
    csv_path = _concept_review_csv_path(topic)
    meta = _load_concept_review_meta(topic)
    csv_rows = _load_csv(csv_path)

    # Collect per-concept metadata, excluded set, and approved codes
    concept_meta: dict[str, dict] = {}   # name → {type, sources, comment}
    excluded_concepts: set[str] = set()
    approved_by_concept: dict[str, list[dict]] = {}

    for row in csv_rows:
        name = row.get("concept_name", "").strip()
        if not name:
            continue
        if name not in concept_meta:
            concept_meta[name] = {
                "type": row.get("concept_type", "").strip(),
                "sources": [s.strip() for s in row.get("sources", "").split(";") if s.strip()],
                "comment": row.get("comment", "").strip(),
            }
        if row.get("remove concept (true/false)", "").strip().lower() in ("true", "y", "yes"):
            excluded_concepts.add(name)
        if row.get("code status (approve/reject)", "").strip().lower() in ("approve", "y", "yes") and name not in excluded_concepts:
            approved_by_concept.setdefault(name, [])
            system = row.get("system", "").strip()
            code = row.get("code", "").strip()
            display = row.get("display", "").strip()
            if system and code:
                key = (system.casefold(), code.casefold())
                if not any(
                    (e["system"].casefold(), e["code"].casefold()) == key
                    for e in approved_by_concept[name]
                ):
                    approved_by_concept[name].append(
                        {k: v for k, v in {"system": system, "code": code, "display": display}.items() if v}
                    )

    # Build concept rows: all non-excluded concepts, with or without codes
    concept_rows = []
    for name, info in concept_meta.items():
        if name in excluded_concepts:
            continue
        concept_row: dict = {"name": name, "type": info["type"]}
        codes = approved_by_concept.get(name, [])
        if codes:
            concept_row["codes"] = codes
        if info.get("comment"):
            concept_row["notes"] = info["comment"]
        concept_rows.append(concept_row)

    # derived_from: union of all non-excluded concept sources
    all_sources: set[str] = set()
    for name, info in concept_meta.items():
        if name not in excluded_concepts:
            all_sources.update(info.get("sources", []))
    derived_from = sorted(all_sources)

    artifact = {
        "id": "concepts",
        "name": "concepts",
        "title": f"{_human_title(topic)} Concept Catalog",
        "version": "1.0.0",
        "status": "draft",
        "domain": "terminology",
        "description": (
            "Deduplicated concept catalog derived from topic concept annotations "
            "and reviewed for standardized coding."
        ),
        "derived_from": derived_from,
        "artifact_type": "terminology",
        "review_status": meta.get("status", "pending-review"),
        "sections": {
            "summary": (
                "Terminology review output derived from topic concept annotations. "
                "Each concept was deduplicated across sources before human review."
            ),
        },
        "concepts": concept_rows,
    }
    artifact_path = _concept_artifact_path(topic)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    _yaml_rt().dump(artifact, buf)
    artifact_path.write_text(buf.getvalue())

    checksum = sha256_file(artifact_path)
    topic_entry = require_topic(tracking, topic)
    structured = topic_entry.setdefault("structured", [])
    entry = next((item for item in structured if item.get("name") == "concepts"), None)
    payload = {
        "name": "concepts",
        "file": f"topics/{topic}/structured/concepts.yaml",
        "created_at": now_iso(),
        "checksum": checksum,
        "derived_from": derived_from,
        "artifact_type": "terminology",
    }
    if entry is None:
        structured.append(payload)
    else:
        entry.update(payload)
    append_topic_event(
        tracking,
        topic,
        "structured_derived",
        "Derived concepts terminology artifact from CSV review",
    )
    save_tracking(tracking)
    return artifact_path


def _sync_plan_concept_review(topic: str, meta: dict) -> None:
    plan_path = _extract_plan_path(topic)
    readout_path = _extract_readout_path(topic)
    if not plan_path.exists():
        return
    plan = _yaml_safe().load(plan_path.read_text()) or {}
    if not isinstance(plan, dict):
        return
    concept_review = plan.get("concept_review") or {}
    if not concept_review:
        return
    concept_review["status"] = meta.get("status", concept_review.get("status", "pending-review"))
    concept_review["review_artifact"] = meta.get("review_artifact", concept_review.get("review_artifact", ""))
    concept_review["final_artifact"] = meta.get("final_artifact", concept_review.get("final_artifact", ""))
    if meta.get("reviewer"):
        concept_review["reviewer"] = meta["reviewer"]
    if meta.get("reviewed_at"):
        concept_review["reviewed_at"] = meta["reviewed_at"]
    plan["concept_review"] = concept_review
    _write_plan_and_readout(plan_path, readout_path, plan)


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
    "decision-table": "Encodes event-condition-action clinical decision logic for CDS rule formalization.",
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
    "decision-table": "event triggers, condition thresholds, action triggers, and decision criteria",
    "care-pathway": "step sequencing, timing windows, and actor responsibilities",
    "terminology": "code coverage, concept boundaries, and preferred terms",
    "measure": "population definitions, scoring logic, and measurement period",
    "assessment": "item wording, response options, and scoring ranges",
    "policy": "coverage criteria, authorization requirements, and payer definitions",
}


def _identify_group_concerns(group: dict) -> list[dict]:
    """Call LLM to surface specific clinical concerns for this artifact group.

    In offline mode (no LLM, no agent content) returns [] — reviewer adds
    concerns via --add-concern at approve time.
    In agent mode (RH_STUB_RESPONSE set) or LLM mode, parses the response as
    a YAML list of {concern, resolution} items.
    """
    if _is_offline_mode():
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
        required_sections.append("concerns")

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


def _render_extract_plan(topic: str, artifacts: list[dict], concept_review: dict | None) -> str:
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
    if concept_review:
        plan["concept_review"] = concept_review
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
    concept_review = plan.get("concept_review") or {}

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
    if concept_review:
        source_files = concept_review.get('source_files') or []
        lines.append(
            f"- Concept review: `{concept_review.get('status', 'pending-review')}` "
            f"({concept_review.get('concept_count', 0)} deduplicated concept(s) from {len(source_files)} source(s))"
        )
        lines.append(f"- MCP lookup completed: `{concept_review.get('lookup_completed', False)}`")
    if review_summary:
        lines.append(f"- Notes: {review_summary}")
    if status != "approved":
        lines.append(f"- Reviewer action required: run `rh-skills promote approve {topic}`")
    lines.append("")

    if concept_review:
        source_files = concept_review.get('source_files') or []
        source_display = ', '.join(f'`{sf}`' for sf in source_files) if source_files else '_none_'
        lines.extend([
            "# Concept Review",
            "",
            f"- Source files: {source_display}",
            f"- Review artifact: `{concept_review.get('review_artifact', '')}`",
            f"- Final artifact target: `{concept_review.get('final_artifact', '')}`",
            f"- MCP enrichment command: `rh-skills promote concept enrich {topic} --concept <name> --candidate <system|code|display>`",
            f"- Review command: `rh-skills promote concept review {topic}`",
            "- Lookup policy: use ReasonHub MCP for standardized codes; when a high-confidence match is found, review descendants only.",
            "",
        ])

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


@contextmanager
def _lock_concept_review(review_path: Path):
    """Serialize concurrent concept enrich/review writes via an exclusive file lock."""
    lock_path = review_path.with_suffix(".lock")
    lock_fd = lock_path.open("w")
    try:
        lock_file(lock_fd)
        yield
    finally:
        unlock_file(lock_fd)
        lock_fd.close()


def _apply_artifact_decision(
    plan: dict, artifact_name: str, decision: str, notes: str = "",
    add_concerns: tuple[str, ...] = (),
    add_sources: tuple[str, ...] = (),
) -> None:
    """Mutate plan in-place: set reviewer_decision, optional notes, append concerns/sources."""
    for artifact in plan.get("artifacts", []) or []:
        if artifact.get("name") == artifact_name:
            artifact["reviewer_decision"] = decision
            if notes:
                artifact["approval_notes"] = notes
            if add_concerns:
                existing = artifact.get("concerns") or []
                new_entries = []
                for raw in add_concerns:
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
        _require_concept_review_approved(plan)
        rev = reviewer or plan.get("reviewer") or ""
        if not rev:
            rev = click.prompt("Reviewer name", default="")
        plan["status"] = "approved"
        plan["reviewer"] = rev
        plan["reviewed_at"] = now_iso()

    _write_plan_and_readout(plan_path, readout_path, plan)
    approved = sum(1 for a in artifacts if a.get("reviewer_decision") == "approved")
    log_info(f"Plan updated: {approved}/{len(artifacts)} artifact(s) approved, status={plan['status']}")


def _is_offline_mode() -> bool:
    """Return True when no LLM is configured and the agent has not injected content.

    Offline mode: LLM_PROVIDER is unset/stub AND RH_STUB_RESPONSE is not set.
    Agent mode:   LLM_PROVIDER is unset/stub BUT RH_STUB_RESPONSE IS set
                  (the agent is the reasoning layer; it injects content via the env var).
    LLM mode:     LLM_PROVIDER is set to a real provider (anthropic, openai, ollama).
    """
    return (
        config_value("LLM_PROVIDER", "stub") == "stub"
        and config_value("RH_STUB_RESPONSE", None) is None
    )


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


@promote.group()
def concept():
    """Manage concept coding review for a topic (enrich, review, write)."""


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
    frontmatter_concepts = _collect_frontmatter_concepts(source_records)
    concept_review = _build_concept_review(topic, frontmatter_concepts)

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_yaml = _render_extract_plan(topic, artifacts, concept_review)
    plan_path.write_text(plan_yaml)
    plan = _yaml_safe().load(plan_yaml)
    _extract_readout_path(topic).write_text(_render_extract_readout(plan))
    if frontmatter_concepts:
        csv_path, meta_path = _build_concept_review_csvs(topic, frontmatter_concepts)
        log_info(f"Created: {csv_path}")
        log_info(f"Created: {meta_path}")

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
    if frontmatter_concepts:
        click.echo(f"  2. Enrich concepts    : rh-skills promote concept enrich {topic} --concept <name> --candidate <system|code|display>")
        click.echo(f"  3. Edit the CSV       : open topics/{topic}/process/plans/concepts-review.csv")
        click.echo(f"  4. Finalize review    : rh-skills promote concept review {topic} --finalize --reviewer <name>")
        click.echo(f"  5. Write concepts.yaml: rh-skills promote concept write {topic}  (during implement)")
        click.echo(f"  6. Approve artifacts  : rh-inf-extract approve {topic}")
        click.echo(f"  7. Run extraction     : rh-inf-extract implement {topic}")
    else:
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
    "--add-concern", "add_concerns", multiple=True, metavar="TEXT",
    help="Append a concern to the artifact's concerns list. Use 'concern text' or 'concern|resolution' format (repeatable).",
)
@click.option(
    "--add-conflict", "add_concerns", multiple=True, metavar="TEXT", hidden=True,
    help="Deprecated alias for --add-concern.",
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
def approve(topic, artifact_name, decision, notes, add_concerns, add_sources, reviewer, review_summary, finalize):
    """Record reviewer decisions on extract-plan.yaml artifacts.

    \b
    Non-interactive (AI agent / script):
      # Approve one artifact and finalize in a single atomic call (recommended):
      rh-skills promote approve TOPIC --artifact NAME --decision approved --finalize [--reviewer NAME]

      # Record a cross-source concern and finalize:
      rh-skills promote approve TOPIC --artifact NAME --decision approved \\
        --add-concern "HbA1c threshold: ADA <7.0% vs AACE ≤6.5%" --finalize

      # Add a source the planner omitted (e.g. planner split conflicting sources):
      rh-skills promote approve TOPIC --artifact NAME --decision approved \\
        --add-source aace-guidelines-2022 --add-concern "HbA1c target" --finalize

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
                _apply_artifact_decision(plan, artifact_name, decision, notes, add_concerns, add_sources)
                if review_summary is not None:
                    plan["review_summary"] = review_summary
                _write_plan_and_readout(plan_path, readout_path, plan)
                log_info(f"Artifact '{artifact_name}' → {_DECISION_ICON.get(decision, '')} {decision}")

            if finalize:
                if not artifact_name:
                    # Re-read so we see writes from prior locked invocations.
                    plan = _yaml_safe().load(plan_path.read_text())
                _require_concept_review_approved(plan)
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


_CONFIDENCE_LABELS = {"high", "medium", "low"}


def _confidence_from_distance(distance: float) -> str:
    """Infer a confidence label from a numeric distance score (lower = closer match)."""
    if distance < 0.25:
        return "high"
    if distance < 0.50:
        return "medium"
    return "low"


def _parse_candidate_flag(value: str) -> dict:
    """Parse 'system|code|display[|distance[|confidence]]' into a candidate dict.

    distance   — numeric float (lower = closer match); returned by MCP tools
    confidence — optional string label: high | medium | low
    """
    parts = value.split("|", 4)
    if len(parts) < 3 or not parts[0].strip() or not parts[1].strip():
        raise click.UsageError(
            f"--candidate value must be 'system|code|display[|distance[|confidence]]', got: {value!r}"
        )
    entry: dict = {
        "system": parts[0].strip(),
        "code": parts[1].strip(),
        "display": parts[2].strip(),
    }
    if len(parts) >= 4 and parts[3].strip():
        try:
            entry["distance"] = float(parts[3].strip())
        except ValueError:
            raise click.UsageError(
                f"distance must be a number, got: {parts[3]!r} in {value!r}"
            )
    if len(parts) >= 5 and parts[4].strip():
        confidence = parts[4].strip().lower()
        if confidence not in _CONFIDENCE_LABELS:
            raise click.UsageError(
                f"confidence must be one of {sorted(_CONFIDENCE_LABELS)}, "
                f"got: {parts[4]!r} in {value!r}"
            )
        entry["confidence"] = confidence
    elif "distance" in entry:
        entry["confidence"] = _confidence_from_distance(entry["distance"])
    return entry


def _parse_code_flag(value: str) -> dict:
    """Parse 'system|code|display' flag into a dict. Raises UsageError if malformed."""
    parts = value.split("|", 2)
    if len(parts) != 3 or not parts[0].strip() or not parts[1].strip():
        raise click.UsageError(
            f"--code / --related-code value must be 'system|code|display', got: {value!r}"
        )
    return {"system": parts[0].strip(), "code": parts[1].strip(), "display": parts[2].strip()}


def _parse_reject_candidate_flag(value: str) -> dict:
    """Parse 'system|code[|display[|reason]]' reject-candidate flag into a dict.

    Only system and code are required; display and rejection_reason are optional.
    """
    parts = value.split("|", 3)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        raise click.UsageError(
            f"--reject-candidate value must be 'system|code[|display[|reason]]', got: {value!r}"
        )
    result: dict = {"system": parts[0].strip(), "code": parts[1].strip()}
    if len(parts) >= 3 and parts[2].strip():
        result["display"] = parts[2].strip()
    if len(parts) == 4 and parts[3].strip():
        result["rejection_reason"] = parts[3].strip()
    return result


def _normalize_candidate_identity(candidate: object) -> dict[str, str]:
    """Return normalized system/code/display fields for heterogeneous candidate payloads."""
    if not isinstance(candidate, dict):
        return {"system": "", "code": "", "display": ""}

    coding = candidate.get("coding")
    if not isinstance(coding, dict):
        coding = {}

    system = str(
        candidate.get("system")
        or candidate.get("system_uri")
        or candidate.get("system_url")
        or coding.get("system")
        or ""
    ).strip()
    code = str(
        candidate.get("code")
        or candidate.get("value")
        or coding.get("code")
        or ""
    ).strip()
    display = str(
        candidate.get("display")
        or candidate.get("name")
        or candidate.get("label")
        or coding.get("display")
        or ""
    ).strip()
    return {
        "system": system,
        "code": code,
        "display": display,
    }


def _render_candidate_line(candidate: object) -> str:
    normalized = _normalize_candidate_identity(candidate)
    system = normalized["system"] or "[system missing]"
    code = normalized["code"] or "[code missing]"
    display = normalized["display"] or "[display missing]"
    return f"{system} {code} - {display}"


def _candidate_related_items(candidate: object) -> list[dict]:
    if not isinstance(candidate, dict):
        return []
    related = candidate.get("related_candidates")
    if not isinstance(related, list):
        return []
    return [item for item in related if isinstance(item, dict)]


def _related_candidates_for_code(code_entry: dict, candidates: list[dict]) -> list[dict]:
    target_system = str(code_entry.get("system") or "").strip().casefold()
    target_code = str(code_entry.get("code") or "").strip().casefold()
    for candidate in candidates:
        normalized = _normalize_candidate_identity(candidate)
        if (
            normalized["system"].casefold() == target_system
            and normalized["code"].casefold() == target_code
        ):
            return _candidate_related_items(candidate)
    return []


@concept.command("enrich")
@click.argument("topic")
@click.option("--concept", "concept_name", required=True, metavar="NAME", help="Concept name to enrich.")
@click.option("--type", "concept_type", default=None, metavar="TYPE", help="Concept type when the name is ambiguous.")
@click.option(
    "--candidate",
    "raw_candidates",
    multiple=True,
    type=click.STRING,
    metavar="TEXT",
    help="MCP candidate to record. Format: 'system|code|display[|distance[|confidence]]'. Repeatable — pass once per candidate. Omit when MCP returned no results.",
)
@click.option("--lookup-query", "lookup_query", default=None, metavar="TEXT", help="Search query used. Defaults to concept name.")
@click.option("--lookup-notes", "lookup_notes", default=None, metavar="TEXT", help="Optional notes from the MCP lookup.")
@click.option("--reset", "reset", is_flag=True, help="Clear existing candidate rows and restore placeholder. Use alone or before re-adding candidates.")
def enrich_concepts(topic, concept_name, concept_type, raw_candidates, lookup_query, lookup_notes, reset):
    """Record RH MCP candidates for a concept in the concepts-review.csv.

    \b
    Non-interactive (AI agent):
      # Record one candidate:
      rh-skills promote concept enrich <topic> \\
        --concept "Hypertension" \\
        --candidate "SNOMED-CT|38341003|Hypertensive disorder, systemic arterial (disorder)|0.02|high" \\
        --lookup-query "Hypertension"

      # Multiple candidates in a single call:
      rh-skills promote concept enrich <topic> \\
        --concept "Hypertension" \\
        --candidate "SNOMED-CT|38341003|Hypertensive disorder|0.02|high" \\
        --candidate "ICD-10|I10|Essential (primary) hypertension|0.05"

      # MCP returned no results — still call to record lookup notes:
      rh-skills promote concept enrich <topic> --concept "Rare finding" \\
        --lookup-notes "No results found in SNOMED or ICD-10"

      # Start fresh for a concept:
      rh-skills promote concept enrich <topic> --concept "Hypertension" --reset
    """
    require_topic(require_tracking(), topic)
    csv_path = _concept_review_csv_path(topic)
    if not csv_path.exists():
        raise click.UsageError(
            f"No concept review CSV found. Run 'rh-skills promote plan {topic}' first."
        )
    remaining = 0
    appended_count = 0
    with _lock_concept_review(csv_path):
        meta = _load_concept_review_meta(topic)
        if meta.get("status") == "approved":
            raise click.UsageError("Concept review is already approved; re-plan if you need to change candidates.")

        rows = _load_csv(csv_path)
        concept_row_list = [r for r in rows if r.get("concept_name", "").strip() == concept_name]
        if not concept_row_list:
            raise click.UsageError(f"Concept '{concept_name}' not found in concepts-review.csv.")

        first_row = concept_row_list[0]
        meta_type = first_row.get("concept_type", "")
        meta_sources = first_row.get("sources", "")
        effective_lookup_query = lookup_query or first_row.get("lookup_query") or concept_name

        if reset:
            placeholder = {
                "concept_name": concept_name,
                "concept_type": meta_type,
                "sources": meta_sources,
                "context": first_row.get("context", ""),
                "lookup_query": effective_lookup_query,
                "lookup_notes": lookup_notes or "",
                "system": "", "code": "", "display": "",
                "distance": "", "confidence (high/medium/low)": "",
                "code status (approve/reject)": "", "remove concept (true/false)": "", "comment": "",
            }
            other_rows = [r for r in rows if r.get("concept_name", "").strip() != concept_name]
            rows = other_rows + [placeholder]
            if not raw_candidates:
                _write_csv(csv_path, rows, _CONCEPT_CSV_FIELDNAMES)
                meta["csv_checksum"] = _csv_checksum(csv_path)
                _write_concept_review_meta(topic, meta)
                log_info(f"Reset candidates for '{concept_name}'.")
                return
            concept_row_list = [placeholder]

        existing_candidate_rows = [
            r for r in concept_row_list
            if r.get("system", "").strip() or r.get("code", "").strip()
        ]
        placeholder_rows = [
            r for r in concept_row_list
            if not r.get("system", "").strip() and not r.get("code", "").strip()
        ]

        _CONF_RANK = {"high": 2, "medium": 1, "low": 0}
        for raw_candidate in raw_candidates:
            entry = _parse_candidate_flag(raw_candidate)
            norm_new = _normalize_candidate_identity(entry)
            new_system = norm_new["system"]
            new_code = norm_new["code"]
            new_display = norm_new["display"]
            new_dist = entry.get("distance")
            new_conf_str = str(entry.get("confidence", "")).lower()
            if not new_conf_str and entry.get("distance") is not None:
                new_conf_str = _confidence_from_distance(float(entry["distance"]))
            new_conf = _CONF_RANK.get(new_conf_str, -1)

            dup_row = next(
                (
                    r for r in existing_candidate_rows
                    if r.get("system", "").strip().casefold() == new_system.casefold()
                    and r.get("code", "").strip().casefold() == new_code.casefold()
                ),
                None,
            )
            if dup_row is not None:
                old_dist_str = dup_row.get("distance", "")
                old_conf = _CONF_RANK.get(dup_row.get("confidence (high/medium/low)", "").lower(), -1)
                try:
                    old_dist = float(old_dist_str) if old_dist_str else None
                    new_dist_f = float(new_dist) if new_dist is not None else None
                except (ValueError, TypeError):
                    old_dist = None
                    new_dist_f = None
                new_is_better = False
                if new_dist_f is not None and old_dist is not None:
                    new_is_better = new_dist_f < old_dist or (new_dist_f == old_dist and new_conf > old_conf)
                elif new_dist_f is not None and old_dist is None:
                    new_is_better = True
                elif new_conf > old_conf:
                    new_is_better = True
                if new_is_better:
                    dup_row["display"] = new_display or dup_row.get("display", "")
                    dup_row["distance"] = str(new_dist) if new_dist is not None else ""
                    dup_row["confidence (high/medium/low)"] = new_conf_str
                    log_info(f"Updated candidate {new_system}|{new_code} with better entry.")
                else:
                    log_info(f"Skipped duplicate {new_system}|{new_code} — existing retained.")
            else:
                new_row: dict = {
                    "concept_name": concept_name,
                    "concept_type": meta_type,
                    "sources": meta_sources,
                    "context": first_row.get("context", ""),
                    "lookup_query": effective_lookup_query,
                    "lookup_notes": (
                        lookup_notes if lookup_notes is not None
                        else first_row.get("lookup_notes", "")
                    ),
                    "system": new_system,
                    "code": new_code,
                    "display": new_display,
                    "distance": str(new_dist) if new_dist is not None else "",
                    "confidence (high/medium/low)": new_conf_str,
                    "code status (approve/reject)": "",
                    "remove concept (true/false)": "",
                    "comment": "",
                }
                existing_candidate_rows.append(new_row)
                appended_count += 1

        for r in existing_candidate_rows:
            r["lookup_query"] = effective_lookup_query
            if lookup_notes is not None:
                r["lookup_notes"] = lookup_notes

        if existing_candidate_rows:
            updated_concept_rows: list[dict] = existing_candidate_rows
        else:
            for r in placeholder_rows:
                r["lookup_query"] = effective_lookup_query
                if lookup_notes is not None:
                    r["lookup_notes"] = lookup_notes
            updated_concept_rows = placeholder_rows

        other_rows = [r for r in rows if r.get("concept_name", "").strip() != concept_name]
        rows = other_rows + updated_concept_rows
        _write_csv(csv_path, rows, _CONCEPT_CSV_FIELDNAMES)
        meta["csv_checksum"] = _csv_checksum(csv_path)
        _write_concept_review_meta(topic, meta)

        all_concept_names = {r.get("concept_name", "").strip() for r in rows if r.get("concept_name", "").strip()}
        remaining = sum(
            1 for name in all_concept_names
            if not any(r.get("system", "").strip() for r in rows if r.get("concept_name", "").strip() == name)
        )

    if raw_candidates:
        action = f"appended {appended_count} candidate(s)"
    else:
        action = "updated lookup metadata"
    log_info(
        f"Recorded MCP candidates for '{concept_name}'"
        + (f" ({concept_type})" if concept_type else "")
        + f" — {action}; {remaining} concept(s) still without candidates."
    )


@concept.command("review")
@click.argument("topic")
@click.option("--concept", "concept_name", default=None, metavar="NAME", help="Concept name to update.")
@click.option("--approved", "approved_val", default=None, metavar="y", help="Set approved=y on all candidate rows for the concept.")
@click.option("--exclude", "exclude", is_flag=True, help="Set exclude=y on the first row for the concept (removes it from concepts.yaml).")
@click.option("--note", default="", metavar="TEXT", help="Set comment on the first row for the concept.")
@click.option("--finalize", is_flag=True, help="Seal the review (status: approved). Requires --reviewer.")
@click.option("--reviewer", default=None, metavar="NAME", help="Reviewer name. Required for --finalize.")
@click.option("--force", is_flag=True, help="Bypass the checksum unchanged warning during --finalize.")
def review_concepts(topic, concept_name, approved_val, exclude, note, finalize, reviewer, force):
    """Update concept decisions in concepts-review.csv, then finalize.

    \b
    Non-interactive (AI agent):
      # Approve all candidate rows for a concept:
      rh-skills promote concept review <topic> --concept "Hypertension" --approved y

      # Exclude a concept from concepts.yaml:
      rh-skills promote concept review <topic> --concept "Rare finding" --exclude

      # Add a comment to a concept:
      rh-skills promote concept review <topic> --concept "Hypertension" --note "Confirmed SNOMED"

      # Finalize (seal the review):
      rh-skills promote concept review <topic> --finalize --reviewer "taylor"

      # Force-finalize even if CSV is unchanged:
      rh-skills promote concept review <topic> --finalize --reviewer "taylor" --force
    """
    if not concept_name and not finalize:
        raise click.UsageError(
            "Provide --concept with --approved, --exclude, or --note; or use --finalize."
        )

    require_topic(require_tracking(), topic)
    csv_path = _concept_review_csv_path(topic)
    if not csv_path.exists():
        raise click.UsageError(
            f"No concept review CSV found. Run 'rh-skills promote plan {topic}' first."
        )

    # --- per-concept update ---
    if concept_name:
        if not approved_val and not exclude and not note:
            raise click.UsageError("--concept requires at least one of --approved, --exclude, or --note.")
        with _lock_concept_review(csv_path):
            meta = _load_concept_review_meta(topic)
            if meta.get("status") == "approved":
                raise click.UsageError("Concept review is already approved.")
            rows = _load_csv(csv_path)
            concept_rows = [r for r in rows if r.get("concept_name", "").strip() == concept_name]
            if not concept_rows:
                raise click.UsageError(f"Concept '{concept_name}' not found in concepts-review.csv.")
            if approved_val and approved_val.lower() in ("y", "yes", "approve"):
                for r in concept_rows:
                    if r.get("system", "").strip() or r.get("code", "").strip():
                        r["code status (approve/reject)"] = "approve"
            if exclude:
                concept_rows[0]["remove concept (true/false)"] = "true"
            if note:
                concept_rows[0]["comment"] = note
            _write_csv(csv_path, rows, _CONCEPT_CSV_FIELDNAMES)
            meta["csv_checksum"] = _csv_checksum(csv_path)
            _write_concept_review_meta(topic, meta)
        actions = []
        if approved_val and approved_val.lower() == "y":
            actions.append("approved")
        if exclude:
            actions.append("excluded")
        if note:
            actions.append("note set")
        log_info(f"Updated '{concept_name}': {', '.join(actions)}.")

    # --- finalize ---
    if finalize:
        if not reviewer:
            raise click.UsageError("--reviewer is required for --finalize.")
        meta = _load_concept_review_meta(topic)
        if meta.get("status") == "approved":
            raise click.UsageError("Concept review is already approved.")
        current_checksum = _csv_checksum(csv_path)
        if not force and current_checksum == meta.get("csv_checksum"):
            raise click.UsageError(
                "CSV is unchanged since it was generated — no human edits detected. "
                "Edit the CSV (approve or exclude rows) then re-run, or use --force to bypass."
            )
        rows = _load_csv(csv_path)
        all_concept_names = {r.get("concept_name", "").strip() for r in rows if r.get("concept_name", "").strip()}
        all_excluded = all(
            any(r.get("remove concept (true/false)", "").strip().lower() in ("true", "y", "yes") for r in rows if r.get("concept_name", "").strip() == name)
            for name in all_concept_names
        )
        if all_excluded:
            log_warn("All concepts are excluded — concepts.yaml will be empty.")
        meta["status"] = "approved"
        meta["reviewer"] = reviewer
        meta["reviewed_at"] = now_iso()
        meta["csv_checksum"] = current_checksum
        meta["review_artifact"] = str(csv_path)
        _write_concept_review_meta(topic, meta)
        _sync_plan_concept_review(topic, meta)
        log_info(
            f"Concept review finalized by '{reviewer}'. "
            f"Run 'rh-skills promote concept write {topic}' during implement to write concepts.yaml."
        )


@concept.command("write")
@click.argument("topic")
def write_concepts(topic):
    """Write topics/<topic>/structured/concepts.yaml from the approved concept review CSV.

    Requires concept review to be finalized (status: approved).
    Call this during implement mode after the extract plan is approved.
    """
    tracking = require_tracking()
    require_topic(tracking, topic)

    meta = _load_concept_review_meta(topic)
    if meta.get("status") != "approved":
        raise click.UsageError(
            "Concept review is not approved. "
            f"Run 'rh-skills promote concept review {topic} --finalize --reviewer <name>' first."
        )

    artifact_path = _write_concepts_l2_artifact_from_csv(topic, tracking)
    log_info(f"Created: {artifact_path}")


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
@click.option("--concern", "concerns", multiple=True,
              help="Concern in 'issue|source|statement[|preferred_source|preferred_rationale]' format")
@click.option("--conflict", "concerns", multiple=True, hidden=True,
              help="Deprecated alias for --concern.")
@click.option("--body-file", default=None, type=click.Path(exists=True, readable=True),
              help="Path to a YAML file containing the complete artifact body; repeated content flags become consistency checks")
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
    concerns,
    body_file,
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
        body_data = _load_body_file(body_file) if body_file else None
        if body_data is not None:
            _validate_body_file_consistency(
                artifact_name=artifact_name,
                source=source,
                artifact_type=artifact_type,
                clinical_question=clinical_question,
                required_sections=required_sections,
                evidence_refs=evidence_refs,
                concerns=concerns,
                body=body_data,
            )

        effective_artifact_type = (
            artifact_type
            or (body_data.get("artifact_type") if body_data is not None else None)
            or "evidence-summary"
        )
        user_prompt = (
            f"Source L1 artifact name: {', '.join(source)}\n"
            f"Generate L2 artifact: {artifact_name}\n"
            f"Artifact type: {effective_artifact_type}\n"
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

        l2_file = td / "structured" / artifact_name / f"{artifact_name}.yaml"
        l2_file.parent.mkdir(parents=True, exist_ok=True)

        if body_file:
            # Agent-provided artifact body — read file directly, skip LLM and scaffold.
            body_text = Path(body_file).read_text()
            l2_file.write_text(_sanitize_yaml(body_text + "\n"))
        elif _is_offline_mode():
            # No LLM and no agent-provided body — write a scaffold with placeholders.
            l2_file.write_text(
                _build_stub_l2_artifact(
                    artifact_name,
                    source,
                    effective_artifact_type,
                    clinical_question,
                    required_sections,
                    evidence_refs,
                    concerns,
                )
            )
        else:
            llm_output = _invoke_llm(system_prompt, user_prompt)
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
            "artifact_type": effective_artifact_type,
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


def _print_open_concerns(topic: str) -> None:
    """List open (unresolved) concerns across extract and formalize plans.

    Scans both extract-plan.yaml and formalize-plan.yaml (whichever exist) and
    reports every concern/conflict entry whose resolution field is empty or absent.
    Exit code 0 in all cases; use the output to decide whether to proceed.
    """
    open_concerns = _collect_open_concerns(topic)
    if not open_concerns:
        click.echo(f"No open concerns for topic '{topic}'.")
        return

    click.echo(f"Open concerns for topic '{topic}':\n")
    for concern in open_concerns:
        click.echo(
            f"  plan={concern['plan_type']}  artifact={concern['artifact']}  index={concern['index']}"
        )
        click.echo(f"    Concern   : {concern['concern']}")
        click.echo(f"    Resolution: {concern['resolution'] or '_pending_'}")
        click.echo()

    click.echo(
        f"Total: {len(open_concerns)} open concern(s). "
        "Use 'rh-skills promote resolve-concern' to record resolutions."
    )


@promote.command("concerns")
@click.argument("topic")
def concerns(topic):
    """List open (unresolved) concerns across extract and formalize plans.

    Scans both extract-plan.yaml and formalize-plan.yaml (whichever exist) and
    reports every concern/conflict entry whose resolution field is empty or absent.
    Exit code 0 in all cases; use the output to decide whether to proceed.

    Example (agent workflow):
      rh-skills promote concerns diabetes-ccm

    Each concern line includes: plan type, artifact name, index, concern text.
    Use 'resolve-concern' to record a resolution.
    """
    _print_open_concerns(topic)


@promote.command("conflicts", hidden=True)
@click.argument("topic")
def conflicts(topic):
    """Deprecated alias for `concerns`."""
    _print_open_concerns(topic)


def _resolve_concern(
    topic: str,
    artifact_name: str,
    concern_index: int,
    resolution: str,
    plan_type: str,
) -> None:
    if plan_type == "extract":
        plan_path = _extract_plan_path(topic)
        readout_path = _extract_readout_path(topic)
        load_fn = _load_extract_plan
    else:
        plan_path = _formalize_plan_path(topic)
        readout_path = _formalize_readout_path(topic)
        load_fn = _load_formalize_plan

    plan = load_fn(topic)
    _set_concern_resolution(plan, artifact_name, concern_index, resolution)

    if plan_type == "extract":
        _write_plan_and_readout(plan_path, readout_path, plan)
    else:
        blocked_inputs: list[str] = []
        try:
            _, blocked_inputs = _eligible_formalize_inputs(topic)
        except Exception:
            pass
        _write_formalize_plan_and_readout(topic, plan, blocked_inputs)

    remaining = _collect_open_concerns(topic)
    remaining_this_plan = [c for c in remaining if c["plan_type"] == plan_type]
    click.echo(
        f"Resolved concern {concern_index} on '{artifact_name}' "
        f"in {plan_type}-plan.yaml."
    )
    if remaining_this_plan:
        click.echo(
            f"{len(remaining_this_plan)} open concern(s) remain in {plan_type}-plan.yaml."
        )
    else:
        click.echo(f"No open concerns remain in {plan_type}-plan.yaml.")


@promote.command("resolve-concern")
@click.argument("topic")
@click.option(
    "--artifact", "artifact_name", required=True, metavar="NAME",
    help="Name of the artifact containing the concern.",
)
@click.option(
    "--index", "concern_index", required=True, type=int, metavar="N",
    help="0-based index of the concern entry within the artifact's concerns/conflicts list.",
)
@click.option(
    "--resolution", required=True, metavar="TEXT",
    help="Resolution text to record for this concern.",
)
@click.option(
    "--plan", "plan_type", required=True,
    type=click.Choice(["extract", "formalize"]),
    help="Which plan file to update (extract-plan.yaml or formalize-plan.yaml).",
)
def resolve_concern(topic, artifact_name, concern_index, resolution, plan_type):
    """Record the resolution for a specific concern entry.

    Use 'rh-skills promote concerns <topic>' first to list open concerns and
    their indices, then call this command for each one.

    Example:
      # List open concerns first:
      rh-skills promote concerns diabetes-ccm

      # Then resolve each by plan/artifact/index:
      rh-skills promote resolve-concern diabetes-ccm \\
        --plan extract --artifact screening-decisions --index 0 \\
        --resolution "ADA 2024 is the primary guideline; USPSTF framing is supplementary."
    """
    _resolve_concern(topic, artifact_name, concern_index, resolution, plan_type)


@promote.command("resolve-conflict", hidden=True)
@click.argument("topic")
@click.option(
    "--artifact", "artifact_name", required=True, metavar="NAME",
    help="Name of the artifact containing the concern.",
)
@click.option(
    "--index", "concern_index", required=True, type=int, metavar="N",
    help="0-based index of the concern entry within the artifact's concerns/conflicts list.",
)
@click.option(
    "--resolution", required=True, metavar="TEXT",
    help="Resolution text to record for this concern.",
)
@click.option(
    "--plan", "plan_type", required=True,
    type=click.Choice(["extract", "formalize"]),
    help="Which plan file to update (extract-plan.yaml or formalize-plan.yaml).",
)
def resolve_conflict(topic, artifact_name, concern_index, resolution, plan_type):
    """Deprecated alias for `resolve-concern`."""
    _resolve_concern(topic, artifact_name, concern_index, resolution, plan_type)
