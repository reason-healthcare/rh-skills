"""rh-skills promote — Promote artifacts between lifecycle levels."""

import io
import sys
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.common import (
    append_topic_event,
    config_value,
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
        "section": "assessment",
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
    return topic_dir(topic) / "process" / "plans" / "formalize-plan.md"


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
    plan = _parse_markdown_frontmatter(plan_path)
    if not plan:
        raise click.UsageError(f"Plan frontmatter missing or invalid: {plan_path}")
    return plan


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


def _formalize_required_sections(artifacts: list[dict]) -> list[str]:
    required_sections = ["pathways"]
    artifact_types = {artifact.get("artifact_type") for artifact in artifacts}

    if artifact_types & {
        "decision-table",
        "care-pathway",
        "policy",
    }:
        required_sections.append("actions")
    if "terminology" in artifact_types:
        required_sections.append("value_sets")
    if "measure" in artifact_types:
        required_sections.append("measures")
    if "assessment" in artifact_types:
        required_sections.append("assessments")

    deduped: list[str] = []
    for section in required_sections:
        if section not in deduped:
            deduped.append(section)
    return deduped


def _build_formalize_artifacts(topic: str, eligible_inputs: list[dict]) -> list[dict]:
    candidate = {
        "name": f"{topic}-pathway",
        "artifact_type": "pathway-package",
        "input_artifacts": [artifact["name"] for artifact in eligible_inputs],
        "rationale": (
            f"Combines {len(eligible_inputs)} approved structured artifact(s) into "
            "one primary pathway-oriented computable package."
        ),
        "required_sections": _formalize_required_sections(eligible_inputs),
        "implementation_target": True,
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }

    return [candidate]


def _render_formalize_plan(topic: str, artifacts: list[dict], blocked_inputs: list[str]) -> str:
    frontmatter = {
        "topic": topic,
        "plan_type": "formalize",
        "status": "pending-review",
        "reviewer": "",
        "reviewed_at": None,
        "artifacts": artifacts,
    }
    frontmatter_buf = io.StringIO()
    _yaml_rt().dump(frontmatter, frontmatter_buf)

    lines = [
        "---",
        frontmatter_buf.getvalue().rstrip(),
        "---",
        "",
        "# Review Summary",
        "",
        f"- Topic: `{topic}`",
        f"- Proposed computable artifacts: {len(artifacts)}",
        f"- Primary implementation target: `{next(artifact['name'] for artifact in artifacts if artifact['implementation_target'])}`",
        "- Eligible structured inputs are limited to extract-approved artifacts that still pass validation.",
        "- Reviewer action required: approve the plan and the single implementation target before formalization.",
        "",
        "# Proposed Artifacts",
        "",
    ]

    for artifact in artifacts:
        decision = artifact.get("reviewer_decision", "pending-review")
        decision_icon = _DECISION_ICON.get(decision, "⏳")
        notes_text = artifact.get("approval_notes") or "_pending reviewer input_"
        lines.extend([
            f"## {artifact.get('name', 'unknown')}",
            "",
            f"- Type: `{artifact.get('artifact_type', 'unknown')}`",
            f"- Eligible structured inputs: {', '.join(artifact.get('input_artifacts', []))}",
            f"- Rationale: {artifact.get('rationale', '')}",
            f"- Required computable sections: {', '.join(artifact.get('required_sections', []))}",
            f"- Implementation target: `{'yes' if artifact.get('implementation_target') else 'no'}`",
            "- Unresolved modeling notes: review input overlap, omitted alternates, and downstream export assumptions before implementation.",
            f"- Reviewer decision: {decision_icon} `{decision}`",
            f"- Approval notes: {notes_text}",
            "",
        ])

    lines.extend([
        "# Cross-Artifact Issues",
        "",
    ])
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
        "- Implement MUST NOT proceed until `status: approved` and the single target has `reviewer_decision: approved`.",
        "- All `input_artifacts[]` entries must still exist in `topics/<topic>/structured/` and pass validation at implement time.",
        "",
    ])
    return "\n".join(lines)


def _approved_formalize_target(topic: str) -> dict:
    plan = _load_formalize_plan(topic)
    if plan.get("status") != "approved":
        raise click.UsageError(
            "formalize-plan.md is not approved. Review and update the plan before implement."
        )

    artifacts = plan.get("artifacts", []) or []
    targets = [artifact for artifact in artifacts if artifact.get("implementation_target") is True]
    if len(targets) != 1:
        raise click.UsageError(
            "formalize-plan.md must mark exactly one artifact as implementation_target: true."
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


def _build_plan_artifact_entry(group: dict) -> dict:
    source_names = [record["name"] for record in group["sources"]]
    source_files = [record["relative_path"] for record in group["sources"]]
    source_count = len(source_files)
    artifact_name = group["artifact_type"]

    plan_conflicts: list[dict] = []
    if source_count > 1:
        plan_conflicts.append({
            "conflict": "Multiple normalized sources contribute to this artifact; confirm that thresholds, timing, and terminology align before derive.",
            "resolution": "",
        })
    if any(
        keyword in record["content"].lower()
        for record in group["sources"]
        for keyword in ("however", "conflict", "differ", "disagree", "uncertain", "versus", "vs.")
    ):
        plan_conflicts.append({
            "conflict": "At least one contributing source contains potentially conflicting or qualified guidance that requires reviewer confirmation.",
            "resolution": "",
        })

    required_sections = ["summary", group["section"], "evidence_traceability"]
    if plan_conflicts:
        required_sections.append("conflicts")

    rationale = (
        f"Synthesizes {source_count} normalized source(s) contributing to {group['artifact_type']} for review and downstream formalization."
    )
    return {
        "name": artifact_name,
        "artifact_type": group["artifact_type"],
        "source_files": source_files,
        "rationale": rationale,
        "key_questions": [group["key_question"]],
        "required_sections": required_sections,
        "conflicts": plan_conflicts,
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
            f"- Source coverage: {', '.join(artifact.get('source_files', []))}",
            f"- Rationale: {artifact.get('rationale', '')}",
            f"- Key questions: {', '.join(artifact.get('key_questions', []))}",
            f"- Required sections: {', '.join(artifact.get('required_sections', []))}",
        ])
        conflicts = artifact.get("conflicts") or []
        if conflicts:
            lines.append("- Conflicts:")
            for item in conflicts:
                c = item.get("conflict", item) if isinstance(item, dict) else item
                r = item.get("resolution", "") if isinstance(item, dict) else ""
                lines.append(f"  - **Conflict:** {c}")
                lines.append(f"    - **Resolution:** {r if r else '_pending_'}")
        else:
            lines.append("- Conflicts: none identified during deterministic planning")
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


def _apply_artifact_decision(
    plan: dict, artifact_name: str, decision: str, notes: str = "",
    add_conflicts: tuple[str, ...] = (),
    add_sources: tuple[str, ...] = (),
) -> None:
    """Mutate plan in-place: set reviewer_decision, optional notes, append conflicts/sources."""
    for artifact in plan.get("artifacts", []) or []:
        if artifact.get("name") == artifact_name:
            artifact["reviewer_decision"] = decision
            if notes:
                artifact["approval_notes"] = notes
            if add_conflicts:
                existing = artifact.get("conflicts") or []
                new_entries = []
                for raw in add_conflicts:
                    parts = raw.split("|", 1)
                    new_entries.append({
                        "conflict": parts[0].strip(),
                        "resolution": parts[1].strip() if len(parts) > 1 else "",
                    })
                artifact["conflicts"] = existing + new_entries
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
            conflicts = artifact.get("conflicts") or []
            click.echo(f"  Artifact : {name}")
            click.echo(f"  Type     : {art_type}")
            click.echo(f"  Sources  : {sources}")
            click.echo(f"  Question : {key_q}")
            if conflicts:
                for item in conflicts:
                    c = item.get("conflict", item) if isinstance(item, dict) else item
                    click.echo(f"  Conflict : {c}")

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
    """Invoke LLM or return stub response."""
    provider = config_value("LLM_PROVIDER", "ollama")
    if provider == "stub":
        stub = config_value("RH_STUB_RESPONSE", "Stub response")
        return stub
    raise click.ClickException(
        f"LLM provider '{provider}' not available in Python port — use LLM_PROVIDER=stub for testing"
    )


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
    artifacts = [_build_plan_artifact_entry(group) for group in grouped]
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
    help="Append a conflict to the artifact's conflicts list. Use 'conflict text' or 'conflict|resolution' format (repeatable).",
)
@click.option(
    "--add-source", "add_sources", multiple=True, metavar="SLUG",
    help="Add a missing source slug to the artifact's source_files list (repeatable).",
)
@click.option("--reviewer", default=None, help="Reviewer name written to plan header.")
@click.option(
    "--review-summary", "review_summary", default=None,
    help="Plan-level review summary written to extract-plan.yaml (required when conflicts exist).",
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
        # Re-read from disk so any --artifact changes written by a prior or concurrent
        # invocation are reflected before we write the finalized plan.
        if artifact_name:
            # We just wrote above — plan in memory is already up-to-date.
            pass
        else:
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

    if not artifact_name and not finalize:
        if not sys.stdin.isatty():
            raise click.UsageError(
                "stdin is not a TTY — use --artifact NAME --decision DECISION for non-interactive approval, "
                "or --finalize to set plan status."
            )
        _interactive_approve(plan, plan_path, readout_path, reviewer)


@promote.command("formalize-plan")
@click.argument("topic")
@click.option("--force", is_flag=True, help="Overwrite an existing formalize-plan.md")
def formalize_plan(topic, force):
    """Write topics/<topic>/process/plans/formalize-plan.md from approved L2 artifacts."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan_path = _formalize_plan_path(topic)
    if plan_path.exists() and not force:
        log_warn("formalize-plan.md already exists. Re-run with --force to overwrite it.")
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

    plan_text = _render_formalize_plan(
        topic,
        _build_formalize_artifacts(topic, eligible_inputs),
        blocked_inputs,
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan_text)

    append_topic_event(
        tracking,
        topic,
        "formalize_planned",
        f"Wrote formalize plan: topics/{topic}/process/plans/formalize-plan.md",
    )
    save_tracking(tracking)
    log_info(f"Created: {plan_path}")


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
            l2_file.write_text(llm_output + "\n")

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
    """
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
        l3_file.write_text(llm_output + "\n")

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
