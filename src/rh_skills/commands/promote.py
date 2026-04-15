"""rh-skills promote — Promote artifacts between lifecycle levels."""

import io
import os
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.common import (
    append_topic_event,
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
        "artifact_type": "eligibility-criteria",
        "keywords": ("criteria", "eligibility", "screen"),
        "section": "criteria",
        "key_question": "Which patients qualify for the recommended intervention or workflow?",
    },
    {
        "artifact_type": "exclusions",
        "keywords": ("exclusion", "contraind", "avoid"),
        "section": "exclusions",
        "key_question": "Which patients or situations should be excluded?",
    },
    {
        "artifact_type": "risk-factors",
        "keywords": ("risk", "factor"),
        "section": "factors",
        "key_question": "Which risk factors materially change clinical decisions?",
    },
    {
        "artifact_type": "decision-points",
        "keywords": ("decision", "threshold", "diagnostic"),
        "section": "decision_points",
        "key_question": "Which decision points or thresholds govern next actions?",
    },
    {
        "artifact_type": "workflow-steps",
        "keywords": ("workflow", "pathway", "algorithm", "step"),
        "section": "workflow",
        "key_question": "What workflow steps should the team follow?",
    },
    {
        "artifact_type": "terminology-value-sets",
        "keywords": ("terminology", "value-set", "valueset", "code"),
        "section": "terminology",
        "key_question": "Which terminology or value sets must remain consistent downstream?",
    },
    {
        "artifact_type": "measure-logic",
        "keywords": ("measure", "numerator", "denominator", "quality"),
        "section": "measure_logic",
        "key_question": "What measure logic or reporting rules should be preserved?",
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
    return topic_dir(topic) / "process" / "plans" / "extract-plan.md"


def _formalize_plan_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "formalize-plan.md"


def _load_extract_plan(topic: str) -> dict:
    plan_path = _extract_plan_path(topic)
    if not plan_path.exists():
        raise click.UsageError(
            f"No plan found: {plan_path}. Run 'rh-skills promote plan {topic}' first."
        )
    plan = _parse_markdown_frontmatter(plan_path)
    if not plan:
        raise click.UsageError(f"Plan frontmatter missing or invalid: {plan_path}")
    return plan


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
            "extract-plan.md is not approved. Review and update the plan before implement."
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
        "eligibility-criteria",
        "exclusions",
        "risk-factors",
        "decision-points",
        "workflow-steps",
    }:
        required_sections.append("actions")
    if "terminology-value-sets" in artifact_types:
        required_sections.append("value_sets")
    if "measure-logic" in artifact_types:
        required_sections.append("measures")

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
        lines.extend([
            f"## {artifact['name']}",
            "",
            f"- Type: `{artifact['artifact_type']}`",
            f"- Eligible structured inputs: {', '.join(artifact['input_artifacts'])}",
            f"- Rationale: {artifact['rationale']}",
            f"- Required computable sections: {', '.join(artifact['required_sections'])}",
            f"- Implementation target: `{'yes' if artifact['implementation_target'] else 'no'}`",
            "- Unresolved modeling notes: review input overlap, omitted alternates, and downstream export assumptions before implementation.",
            f"- Reviewer decision: `{artifact['reviewer_decision']}`",
            "- Approval notes: _pending reviewer input_",
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
    entries: list[dict] = []
    for raw in raw_conflicts:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 3:
            raise click.UsageError(
                "--conflict must use 'issue|source|statement' or "
                "'issue|source|statement|preferred_source|preferred_rationale'"
            )
        issue, source, statement = parts[:3]
        entry = {
            "issue": issue,
            "positions": [{"source": source, "statement": statement}],
        }
        if len(parts) >= 5:
            entry["preferred_interpretation"] = {
                "source": parts[3],
                "rationale": parts[4],
            }
        entries.append(entry)
    return entries


def _build_sections(
    required_sections: tuple[str, ...],
    clinical_question: str | None,
    evidence_refs: tuple[str, ...],
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
            sections[name] = []
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
        "domain": "",
        "description": "",
        "derived_from": list(source),
        "artifact_type": artifact_type or "evidence-summary",
        "clinical_question": clinical_question or "",
        "sections": _build_sections(required_sections, clinical_question, evidence_refs),
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
        normalized_path = normalized_root / f"{source['name']}.md"
        if normalized_path.exists():
            records.append({
                "name": source["name"],
                "path": normalized_path,
                "relative_path": f"sources/normalized/{source['name']}.md",
                "content": normalized_path.read_text(),
            })
    return records


def _infer_artifact_profile(source_name: str, content: str) -> dict:
    haystack = f"{source_name} {content[:1000]}".lower()
    for profile in EXTRACT_ARTIFACT_PROFILES:
        if any(keyword in haystack for keyword in profile["keywords"]):
            return profile
    return {
        "artifact_type": "evidence-summary",
        "section": "summary_points",
        "key_question": "What evidence should be preserved for downstream reasoning?",
    }


def _group_sources_for_extract_plan(source_records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for record in source_records:
        profile = _infer_artifact_profile(record["name"], record["content"])
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
        group["sources"].append(record)
    return list(grouped.values())


def _build_plan_artifact_entry(group: dict) -> dict:
    source_names = [record["name"] for record in group["sources"]]
    source_files = [record["relative_path"] for record in group["sources"]]
    source_count = len(source_files)
    artifact_name = group["artifact_type"]
    if source_count == 1:
        artifact_name = _slugify(source_names[0])

    unresolved_conflicts: list[str] = []
    if source_count > 1:
        unresolved_conflicts.append(
            "Multiple normalized sources contribute to this artifact; confirm that thresholds, timing, and terminology align before derive."
        )
    if any(
        keyword in record["content"].lower()
        for record in group["sources"]
        for keyword in ("however", "conflict", "differ", "disagree", "uncertain", "versus", "vs.")
    ):
        unresolved_conflicts.append(
            "At least one contributing source contains potentially conflicting or qualified guidance that requires reviewer confirmation."
        )

    required_sections = ["summary", group["section"], "evidence_traceability"]
    if unresolved_conflicts:
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
        "unresolved_conflicts": unresolved_conflicts,
        "reviewer_decision": "pending-review",
        "approval_notes": "",
    }


def _render_extract_plan(topic: str, artifacts: list[dict], has_concepts: bool) -> str:
    frontmatter = {
        "topic": topic,
        "plan_type": "extract",
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
        f"- Proposed artifacts: {len(artifacts)}",
        f"- Concepts file present: {'yes' if has_concepts else 'no'}",
        "- Claim-level traceability is required for every extracted rule, criterion, or summary claim.",
        "- Reviewer action required: update plan status and per-artifact decisions before implementation.",
        "",
        "# Proposed Artifacts",
        "",
    ]

    for artifact in artifacts:
        lines.extend([
            f"## {artifact['name']}",
            "",
            f"- Type: `{artifact['artifact_type']}`",
            f"- Source coverage: {', '.join(artifact['source_files'])}",
            f"- Rationale: {artifact['rationale']}",
            f"- Key questions: {', '.join(artifact['key_questions'])}",
            f"- Required sections: {', '.join(artifact['required_sections'])}",
        ])
        if artifact["unresolved_conflicts"]:
            lines.append("- Unresolved conflicts:")
            lines.extend([f"  - {item}" for item in artifact["unresolved_conflicts"]])
        else:
            lines.append("- Unresolved conflicts: none identified during deterministic planning")
        lines.extend([
            f"- Reviewer decision: `{artifact['reviewer_decision']}`",
            "- Approval notes: _pending reviewer input_",
            "",
        ])

    lines.extend([
        "# Cross-Artifact Issues",
        "",
        "- Confirm artifact boundaries avoid duplicate extraction across overlapping source sets.",
        "- Confirm terminology and threshold language are consistent across approved artifacts.",
        "",
        "# Implementation Readiness",
        "",
        "- Current plan status: `pending-review`",
        "- Implement MUST NOT proceed until the plan status is `approved`.",
        "- Every artifact intended for implementation must have `reviewer_decision: approved`.",
        "",
    ])
    return "\n".join(lines)


def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke LLM or return stub response."""
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    if provider == "stub":
        stub = os.environ.get("RH_STUB_RESPONSE", "Stub response")
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
    """Write topics/<topic>/process/plans/extract-plan.md from normalized sources."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan_path = _extract_plan_path(topic)
    if plan_path.exists() and not force:
        log_warn("extract-plan.md already exists. Re-run with --force to overwrite it.")
        return

    source_records = _normalized_source_records(tracking, topic)
    if not source_records:
        log_warn("No normalized sources found. Run rh-inf-ingest first.")
        return

    grouped = _group_sources_for_extract_plan(source_records)
    artifacts = [_build_plan_artifact_entry(group) for group in grouped]
    concepts_path = topic_dir(topic) / "process" / "concepts.yaml"
    plan_text = _render_extract_plan(topic, artifacts, concepts_path.exists())

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan_text)

    append_topic_event(
        tracking,
        topic,
        "extract_planned",
        f"Wrote extract plan: topics/{topic}/process/plans/extract-plan.md",
    )
    save_tracking(tracking)
    log_info(f"Created: {plan_path}")


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

    # Validate each source exists in tracking
    registered_sources = {s["name"] for s in tracking.get("sources", [])}
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

        l2_file = td / "structured" / f"{artifact_name}.yaml"

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
        topic_entry["structured"].append({
            "name": artifact_name,
            "file": f"topics/{topic}/structured/{artifact_name}.yaml",
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
