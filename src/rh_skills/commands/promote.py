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
        "section": ["events", "conditions", "data_elements", "actions", "rules"],
        "key_question": "What recommendation-scoped triggers, local conditions, and actions form the decision logic?",
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


def _concepts_csv_dir(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "concepts"


def _concept_csv_path(topic: str, concept_name: str) -> Path:
    slug = _slugify(concept_name)
    return _concepts_csv_dir(topic) / f"{slug}.csv"


def _concept_review_meta_path(topic: str) -> Path:
    return topic_dir(topic) / "process" / "plans" / "concepts-review-meta.yaml"


def _concept_artifact_path(topic: str) -> Path:
    return topic_dir(topic) / "structured" / "concepts" / "concepts.yaml"


_CONCEPT_CSV_FIELDNAMES = [
    "concept_name", "concept_type", "role", "sources", "context", "lookup_query", "lookup_notes",
    "system", "code", "display", "distance",
    "confidence", "include/exclude", "comments",
    "row_type", "relation", "related_code",
]

# Core data fields for Individual Codes section of per-concept CSVs.
_CONCEPT_CODE_CORE_FIELDS = [
    "include/exclude", "system", "code", "display", "distance",
    "confidence", "row_type", "relation", "related_code", "comments",
]

# Fields for Expansions section of per-concept CSVs.
_EXPANSION_FIELDS = ["include/exclude", "system", "expansion", "rationale"]

_INSTRUCTIONS_ROWS = [
    [
        "Instructions:",
        (
            "You can approve expansions or individual codes. "
            "Approving an expansion is an intentional valueset, whereas individual codes are extensional rules."
        ),
    ],
    [
        "",
        "The expansions are shown naturally in the individual codes table as of {date} with version {version}",
    ],
    [
        "",
        (
            "If you choose to include an expansion and individual codes, "
            "both rules will apply, however the resulting set will be deduplicated."
        ),
    ],
]


def _write_concept_csv(path: Path, meta_dict: dict, rows: list[dict], expansion_rows: list[dict] | None = None) -> None:
    """Write a per-concept CSV in the sectioned review format.

    The file has three logical sections:
    1. Metadata rows (key,value pairs padded to 10 columns)
    2. Instructions block (3 rows)
    3. Expansions section (header + zero or more expansion rows)
    4. Individual Codes section (header + code rows)

    Related rows carry an explicit ``related_code`` value rather than using
    structural column indentation.
    """
    if expansion_rows is None:
        expansion_rows = []
    _META_KEYS = ["concept_name", "concept_type", "role", "sources", "context", "lookup_query", "lookup_notes"]
    _PAD_WIDTH = 10  # total columns per metadata row

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Metadata rows
        for key in _META_KEYS:
            value = meta_dict.get(key, "")
            row = [key, value] + [""] * (_PAD_WIDTH - 2)
            writer.writerow(row)
        # Blank row
        writer.writerow([""] * _PAD_WIDTH)
        # Instructions
        for instr_row in _INSTRUCTIONS_ROWS:
            writer.writerow(instr_row + [""] * (_PAD_WIDTH - len(instr_row)))
        # Blank row
        writer.writerow([""] * _PAD_WIDTH)
        # Expansions section
        writer.writerow(["Expansions:"] + [""] * (_PAD_WIDTH - 1))
        writer.writerow(_EXPANSION_FIELDS + [""] * (_PAD_WIDTH - len(_EXPANSION_FIELDS)))
        for exp_row in expansion_rows:
            writer.writerow([exp_row.get(f, "") for f in _EXPANSION_FIELDS] + [""] * (_PAD_WIDTH - len(_EXPANSION_FIELDS)))
        # Blank row
        writer.writerow([""] * _PAD_WIDTH)
        # Individual Codes section
        writer.writerow(["Individual Codes:"] + [""] * (_PAD_WIDTH - 1))
        writer.writerow(_CONCEPT_CODE_CORE_FIELDS)
        for row in rows:
            writer.writerow([row.get(f, "") for f in _CONCEPT_CODE_CORE_FIELDS])


def _load_concept_csv(path: Path) -> tuple[dict, list[dict], list[dict]]:
    """Load a per-concept CSV.

    Returns ``(meta_dict, code_rows, expansion_rows)``.
    Returns ``({}, [], [])`` if the file is missing.

    Supports two formats:

    **New sectioned format** (written by current _write_concept_csv):
    - First 7 rows are plain ``key,value,...`` metadata rows.
    - Followed by an instructions block, blank rows, ``Expansions:`` section,
      and ``Individual Codes:`` section.
    - Expansion rows are collected between the ``include/exclude,system,expansion,rationale``
      header and the blank row that precedes ``Individual Codes:``.
    - Code rows are collected after the ``include/exclude,system,code,...`` header.

    **Legacy format** (old structural-indentation format with ``#key,value`` comment lines):
    - Lines starting with ``#`` are parsed as metadata.
    - Remaining lines use the old structurally-indented layout (offset 1/2) or
      legacy flat layout.
    - Column names are normalized to the current field names:
        ``approved (y/n)`` → ``include/exclude`` (y → include, n → exclude, blank → blank)
        ``comment`` → ``comments``
        ``confidence (high/medium/low)`` → ``confidence``
      The ``method`` column is dropped.
    - An empty ``expansion_rows`` list is returned.
    """
    if not path.exists():
        return {}, [], []

    raw_text = path.read_text(encoding="utf-8")
    all_lines = raw_text.splitlines(keepends=True)

    # ── Detect format ─────────────────────────────────────────────────────────
    is_legacy = any(line.startswith("#") for line in all_lines if line.strip())

    if is_legacy:
        # ── Legacy #key,value format ──────────────────────────────────────────
        meta_dict: dict = {}
        data_lines: list[str] = []
        for line in all_lines:
            if line.startswith("#"):
                stripped = line.lstrip("#").rstrip("\n")
                idx = stripped.find(",")
                if idx >= 0:
                    meta_dict[stripped[:idx]] = stripped[idx + 1:]
            else:
                data_lines.append(line)
        raw_rows = list(csv.reader(io.StringIO("".join(data_lines))))
        _LEGACY_CORE = [
            "system", "code", "display", "distance",
            "confidence (high/medium/low)", "approved (y/n)", "comment",
            "row_type", "method", "relation",
        ]
        code_rows: list[dict] = []
        for raw in raw_rows:
            if not raw:
                continue
            if "system" in raw:
                continue
            if len(raw) >= 2 and raw[0] == "" and raw[1] == "":
                values = raw[2:]
            elif raw and raw[0] == "":
                values = raw[1:]
            elif raw and raw[0] in ("", "0") and len(raw) > 1 and raw[1].startswith("http"):
                values = raw[1:]
            else:
                values = raw
            row = dict(zip(_LEGACY_CORE, values))
            for field in _LEGACY_CORE:
                row.setdefault(field, "")
            # Normalize legacy column names
            approved_raw = row.pop("approved (y/n)", "").strip().lower()
            if approved_raw in ("y", "yes", "approve", "approved"):
                row["include/exclude"] = "include"
            elif approved_raw in ("n", "no", "reject", "rejected", "exclude", "excluded"):
                row["include/exclude"] = "exclude"
            else:
                row["include/exclude"] = ""
            row["comments"] = row.pop("comment", "")
            conf_raw = row.pop("confidence (high/medium/low)", "").strip()
            row["confidence"] = conf_raw
            row.pop("method", None)
            row.setdefault("related_code", "")
            for field in _CONCEPT_CODE_CORE_FIELDS:
                row.setdefault(field, "")
            code_rows.append(row)
        return meta_dict, code_rows, []

    # ── New sectioned format ──────────────────────────────────────────────────
    _META_KEYS = ["concept_name", "concept_type", "role", "sources", "context", "lookup_query", "lookup_notes"]
    raw_rows = list(csv.reader(io.StringIO(raw_text)))

    # Collect metadata from first 7 non-empty rows (key,value,...).
    meta_dict = {}
    row_idx = 0
    keys_collected = 0
    while row_idx < len(raw_rows) and keys_collected < len(_META_KEYS):
        row = raw_rows[row_idx]
        row_idx += 1
        if not any(c.strip() for c in row):
            continue
        key = row[0].strip() if row else ""
        val = row[1].strip() if len(row) > 1 else ""
        if key in _META_KEYS:
            meta_dict[key] = val
            keys_collected += 1

    # Scan for section markers
    expansion_rows: list[dict] = []
    code_rows = []
    in_expansions = False
    in_codes = False
    expansions_header_seen = False
    codes_header_seen = False

    for row in raw_rows[row_idx:]:
        # Normalize: strip trailing empties
        stripped = [c for c in row]
        first_cell = stripped[0].strip() if stripped else ""

        # Section markers
        if first_cell == "Expansions:":
            in_expansions = True
            in_codes = False
            expansions_header_seen = False
            continue
        if first_cell == "Individual Codes:":
            in_codes = True
            in_expansions = False
            codes_header_seen = False
            continue

        # Skip blank rows
        if not any(c.strip() for c in stripped):
            continue

        # Expansions section
        if in_expansions:
            if not expansions_header_seen:
                # The header row contains "include/exclude" as first non-empty cell
                if first_cell in ("include/exclude", "include"):
                    expansions_header_seen = True
                continue
            exp_row = dict(zip(_EXPANSION_FIELDS, stripped))
            for f in _EXPANSION_FIELDS:
                exp_row.setdefault(f, "")
            expansion_rows.append(exp_row)
            continue

        # Individual Codes section
        if in_codes:
            if not codes_header_seen:
                if first_cell in ("include/exclude", "include"):
                    codes_header_seen = True
                continue
            row_dict = dict(zip(_CONCEPT_CODE_CORE_FIELDS, stripped))
            for f in _CONCEPT_CODE_CORE_FIELDS:
                row_dict.setdefault(f, "")
            code_rows.append(row_dict)

    return meta_dict, code_rows, expansion_rows


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


def _approved_concepts_formalize_artifact(
    topic: str,
    tracked_structured: dict[str, dict],
    approved_extract_names: set[str],
) -> dict | None:
    """Return the legacy concept-review terminology artifact when it should formalize.

    `concept write` produces a valid L2 terminology artifact at
    `structured/concepts/concepts.yaml`, but that artifact is derived from the
    approved concept review rather than from an explicit extract-plan artifact
    row. New extract plans should include an explicit `concepts` terminology
    artifact; this fallback preserves compatibility for older plans.
    """
    if "concepts" in approved_extract_names:
        return None

    tracked_entry = tracked_structured.get("concepts")
    if tracked_entry is None:
        return None

    meta_path = _concept_review_meta_path(topic)
    if not meta_path.exists():
        return None

    meta = _yaml_safe().load(meta_path.read_text()) or {}
    if not isinstance(meta, dict) or meta.get("status") != "approved":
        return None

    source_files = meta.get("source_files") or []
    if not isinstance(source_files, list):
        source_files = []

    return {
        "name": "concepts",
        "artifact_type": "terminology",
        "source_files": source_files,
        "rationale": (
            "Formalizable terminology package derived from the approved "
            "concept review output."
        ),
        "key_questions": [
            "What codes and terminology define the reviewed clinical concepts?",
        ],
        "required_sections": ["summary", "value_sets"],
        "concerns": [],
        "reviewer_decision": "approved",
        "approval_notes": "Auto-included from approved concept review output.",
    }


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
            f"Edit CSVs in topics/{topic}/process/plans/concepts/ then run: "
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
    approved_extract_names = {
        artifact.get("name")
        for artifact in approved_extract
        if artifact.get("name")
    }
    concepts_artifact = _approved_concepts_formalize_artifact(
        topic,
        tracked_structured,
        approved_extract_names,
    )
    candidate_inputs = list(approved_extract)
    if concepts_artifact is not None:
        candidate_inputs.append(concepts_artifact)

    eligible: list[dict] = []
    blocked: list[str] = []
    for artifact in candidate_inputs:
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
            if _passes_minimal_formalize_input_checks(topic, name):
                eligible.append(artifact)
            else:
                blocked.append(f"{name} ({exc.message})")
            continue
        if errors > 0:
            if _passes_minimal_formalize_input_checks(topic, name):
                eligible.append(artifact)
            else:
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
        "supporting": ["ActivityDefinition", "Library"],
        "l3_targets": ["PlanDefinition (eca-rule)", "ActivityDefinition", "Library (CQL)"],
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


def _formalize_candidate_name(topic: str, strategy: str, inputs: list[dict]) -> str:
    """Return the formalize-plan artifact name for a strategy/input set."""
    if strategy == "terminology" and len(inputs) == 1:
        input_name = inputs[0].get("name")
        if input_name:
            return input_name
    return f"{topic}-{strategy}"


def _formalize_source_artifact(inputs: list[dict]) -> str | None:
    """Return the CLI artifact name used to run formalize for this plan entry."""
    if len(inputs) == 1:
        name = inputs[0].get("name")
        return str(name) if name else None
    return None


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
            "name": _formalize_candidate_name(topic, strategy, eligible_inputs),
            "source_artifact": _formalize_source_artifact(eligible_inputs),
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
            "name": _formalize_candidate_name(topic, atype, inputs),
            "source_artifact": _formalize_source_artifact(inputs),
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
        f"> To record approval decisions, run: `rh-skills promote formalize-approve {topic}`.",
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
            f"- Source artifact: `{artifact.get('source_artifact') or '_review required_'}`",
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
            if not _passes_minimal_formalize_input_checks(topic, input_name):
                invalid_inputs.append(f"{input_name} ({exc.message})")
            continue
        if errors > 0:
            if not _passes_minimal_formalize_input_checks(topic, input_name):
                invalid_inputs.append(f"{input_name} (fails validation)")

    if invalid_inputs:
        raise click.UsageError(
            "Formalize inputs are missing or invalid: " + ", ".join(invalid_inputs)
        )

    return target


def _passes_minimal_formalize_input_checks(topic: str, artifact_name: str) -> bool:
    """Compatibility checks for legacy L2 artifacts used by formalize planning.

    Requires:
    - artifact file resolves and parses as YAML mapping
    - sections contains summary and evidence_traceability
    """
    artifact_path = topic_dir(topic) / "structured" / artifact_name / f"{artifact_name}.yaml"
    if not artifact_path.exists():
        artifact_path = topic_dir(topic) / "structured" / f"{artifact_name}.yaml"

    if not artifact_path.exists():
        return False

    parsed = _yaml_safe().load(artifact_path.read_text()) or {}
    if not isinstance(parsed, dict):
        return False
    sections = parsed.get("sections")
    if not isinstance(sections, dict):
        return False
    evidence = sections.get("evidence_traceability")
    return isinstance(evidence, list) and len(evidence) > 0


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


def _dump_yaml_text(data: dict) -> str:
    buf = io.StringIO()
    _yaml_rt().dump(data, buf)
    return buf.getvalue().rstrip() + "\n"


def _merge_body_file_completion(
    body: dict,
    llm_output: str,
    required_sections: tuple[str, ...],
) -> str:
    """Merge agent-completed content back into a body-init scaffold.

    Agents sometimes return a partial artifact body or place section content at
    the top level. Preserve scaffold metadata and lift recognized section keys
    back under ``sections`` so the completed artifact stays on the L2 contract.
    """
    raw_output = _sanitize_yaml(llm_output + "\n")
    try:
        parsed = _yaml_safe().load(raw_output) or {}
    except Exception:
        return raw_output
    if not isinstance(parsed, dict):
        return raw_output

    merged = dict(body)
    section_names = set(required_sections)
    if not section_names:
        body_sections = body.get("sections")
        if isinstance(body_sections, dict):
            section_names = set(body_sections.keys())

    parsed_sections = parsed.get("sections")
    lifted_sections: dict[str, object] = {}
    if isinstance(parsed_sections, dict):
        lifted_sections.update(parsed_sections)
    for key, value in parsed.items():
        if key == "sections":
            continue
        if key in section_names:
            lifted_sections[key] = value
        else:
            merged[key] = value

    body_sections = body.get("sections")
    merged_sections = dict(body_sections) if isinstance(body_sections, dict) else {}
    if lifted_sections:
        merged_sections.update(lifted_sections)
    transitions = merged_sections.get("transitions")
    if isinstance(transitions, list):
        normalized_transitions = []
        for transition in transitions:
            if isinstance(transition, dict):
                updated = dict(transition)
                if "from_id" not in updated and "from" in updated:
                    updated["from_id"] = updated.pop("from")
                if "to_id" not in updated and "to" in updated:
                    updated["to_id"] = updated.pop("to")
                normalized_transitions.append(updated)
            else:
                normalized_transitions.append(transition)
        merged_sections["transitions"] = normalized_transitions
    if merged_sections:
        merged["sections"] = merged_sections

    for key in ("id", "name", "artifact_type", "clinical_question", "derived_from"):
        if key in body and body.get(key) is not None:
            merged[key] = body[key]

    return _dump_yaml_text(merged)


_RELATED_ARTIFACT_CONTEXT: dict[str, tuple[str, ...]] = {
    "decision-table": ("care-pathway",),
    "care-pathway": ("decision-table",),
}


def _load_related_structured_context(topic: str, artifact_type: str | None) -> list[tuple[str, dict]]:
    """Load aligned sibling structured artifacts to improve cross-artifact coherence."""
    if not artifact_type:
        return []
    related_types = _RELATED_ARTIFACT_CONTEXT.get(artifact_type, ())
    if not related_types:
        return []

    td = topic_dir(topic) / "structured"
    contexts: list[tuple[str, dict]] = []
    for related_type in related_types:
        path = td / related_type / f"{related_type}.yaml"
        if not path.exists():
            continue
        try:
            data = _yaml_safe().load(path.read_text()) or {}
        except Exception:
            continue
        if isinstance(data, dict):
            contexts.append((related_type, data))
    return contexts


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
        raise click.UsageError(
            f"--clinical-question does not match --body-file clinical_question: "
            f"flag='{clinical_question}', body-file='{body['clinical_question']}'"
        )

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
    "events": [{
        "id": "event-001",
        "label": "<stub: recommendation trigger>",
        "description": "<stub: evaluation moment for this recommendation>",
        "trigger": {
            "type": "named-event",
            "name": "<stub: event name>",
        },
    }],
    "conditions": [{"id": "cond-001", "label": "<stub: condition>", "values": ["Yes", "No"]}],
    "data_elements": [{
        "id": "de-001",
        "condition_id": "cond-001",
        "label": "<stub: reviewed finding or history item>",
        "description": "<stub: evidence item gathered or reviewed during the broader recommendation>",
        "data_type": "finding",
    }, {
        "id": "de-002",
        "condition_id": "cond-001",
        "label": "<stub: score, result, or structured assessment output>",
        "description": "<stub: concrete result produced by a child task>",
        "data_type": "assessment",
    }],
    "rules": [{"id": "rule-001", "event": "event-001", "then": ["broader-action", "review-supporting-data", "perform-structured-task"]},
              {"id": "rule-002", "event": "event-001", "when": {"cond-001": "Yes"}, "then": ["recommend-action"]},
              {"id": "rule-003", "event": "event-001", "when": {"cond-001": "No"}, "then": ["do-not-perform-action"]}],
    # care-pathway sections
    "steps": [{
        "id": "main-pathway",
        "label": "<stub: overarching pathway>",
        "description": "<stub: top-level clinical pathway>",
        "actor": "<stub: primary actor>",
    }, {
        "id": "phase-001",
        "label": "<stub: major phase or branch>",
        "description": "<stub: major stage of the pathway>",
        "actor": "<stub: responsible actor>",
        "parent_id": "main-pathway",
    }, {
        "id": "phase-002",
        "label": "<stub: separate phase or coordination branch>",
        "description": "<stub: separate branch when downstream timing or trigger differs>",
        "actor": "<stub: responsible actor>",
        "parent_id": "main-pathway",
    }],
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
            return [
                {
                    "id": "broader-action",
                    "label": "<stub: broader recommended action>",
                    "description": "<stub: overall recommendation that may contain broken-down tasks>",
                    "kind": "ServiceRequest",
                },
                {
                    "id": "review-supporting-data",
                    "label": "<stub: child task to review or obtain supporting data>",
                    "description": "<stub: distinct operational task under the broader recommendation>",
                    "kind": "ServiceRequest",
                    "parent_action_id": "broader-action",
                    "produces_data_elements": ["de-001"],
                },
                {
                    "id": "perform-structured-task",
                    "label": "<stub: child task using a structured instrument or other discrete workflow step>",
                    "description": "<stub: separate child task that produces a concrete result>",
                    "kind": "ServiceRequest",
                    "parent_action_id": "broader-action",
                    "produces_data_elements": ["de-002"],
                    "assessment_artifact": "<stub: linked assessment artifact when applicable>",
                },
                {
                    "id": "recommend-action",
                    "label": "<stub: recommended action>",
                    "description": "<stub: what should be done when the rule applies>",
                    "kind": "ServiceRequest",
                },
                {
                    "id": "do-not-perform-action",
                    "label": "<stub: action to avoid or withhold>",
                    "description": "<stub: what should not be done when the rule applies>",
                    "kind": "ServiceRequest",
                    "do_not_perform": True,
                },
            ]
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
    source: tuple[str, ...] = (),
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
            sections[name] = evidence_entries or [{
                "claim_id": "claim-001",
                "statement": "Placeholder evidence traceability entry for scaffold generation.",
                "evidence": [{
                    "source": source[0] if source else "unknown-source",
                    "locator": "Placeholder locator",
                }],
            }]
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
        "sections": _build_sections(required_sections, clinical_question, evidence_refs, concerns, source, artifact_type),
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
            # Normalize role to a list
            raw_role = concept.get("role")
            if raw_role is None:
                role_list: list[str] = []
            elif isinstance(raw_role, list):
                role_list = [str(r).strip() for r in raw_role if r]
            else:
                role_list = [str(raw_role).strip()]
            # Dedup by (name, type) — roles are unioned across sources
            key = (name.casefold(), concept_type.casefold())
            entry = deduped.setdefault(
                key,
                {
                    "name": name,
                    "type": concept_type,
                    "role": [],
                    "sources": [],
                    "source_files": [],
                    "context": "",
                },
            )
            for r in role_list:
                if r not in entry["role"]:
                    entry["role"].append(r)
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
        "review_artifact": f"topics/{topic}/process/plans/concepts/",
        "final_artifact": f"topics/{topic}/structured/concepts/concepts.yaml",
    }


def _build_concepts_extract_artifact_entry(concept_review: dict) -> dict:
    """Return the explicit extract-plan row for the concept-review terminology package."""
    source_files = concept_review.get("source_files") or []
    source_count = len(source_files)
    return {
        "name": "concepts",
        "artifact_type": "terminology",
        "custom_artifact_type": None,
        "source_files": source_files,
        "purpose": "Defines the reviewed terminology package for downstream ValueSet and ConceptMap formalization.",
        "rationale": (
            f"Packages {source_count} normalized source(s) worth of reviewed concept coding "
            "into an explicit L2 terminology artifact."
        ),
        "key_questions": [
            "What reviewed codes and terminology define the clinical concepts for this topic?",
        ],
        "required_sections": ["summary", "value_sets"],
        "concerns": [],
        "reviewer_decision": "pending-review",
        "approval_notes": "Materialized by `rh-skills promote concept write` after concept review finalization.",
    }


def _build_concept_review_csvs(topic: str, concepts: list[dict]) -> tuple[Path, Path]:
    """Write one per-concept CSV and concepts-review-meta.yaml.

    Each concept gets its own CSV under process/plans/concepts/<slug>.csv with
    #key,value metadata comment lines at the top and no code rows yet.
    concept enrich adds candidate rows. Returns (concepts_dir, meta_path).
    """
    checksums: dict = {}
    for c in concepts:
        meta_dict = {
            "concept_name": c["name"],
            "concept_type": c["type"],
            "role": ";".join(c.get("role") or []),
            "sources": ";".join(c.get("sources") or []),
            "context": c.get("context") or "",
            "lookup_query": c["name"],
            "lookup_notes": "",
        }
        csv_path = _concept_csv_path(topic, c["name"])
        _write_concept_csv(csv_path, meta_dict, [])
        checksums[_slugify(c["name"])] = _csv_checksum(csv_path)
    concepts_dir = _concepts_csv_dir(topic)
    source_files: list[str] = []
    seen_sources: set[str] = set()
    for concept in concepts:
        for source_file in concept.get("source_files") or []:
            if source_file not in seen_sources:
                source_files.append(source_file)
                seen_sources.add(source_file)

    meta: dict = {
        "topic": topic,
        "status": "pending-review",
        "generated_at": now_iso(),
        "reviewed_at": None,
        "reviewer": "",
        "checksums": checksums,
        "source_files": source_files,
        "final_artifact": f"topics/{topic}/structured/concepts/concepts.yaml",
    }
    meta_path = _write_concept_review_meta(topic, meta)
    return concepts_dir, meta_path


def _write_concepts_l2_artifact_from_csv(topic: str, tracking: dict) -> Path:
    """Build and write concepts.yaml from per-concept CSVs."""
    concepts_dir = _concepts_csv_dir(topic)
    meta = _load_concept_review_meta(topic)

    # Collect concept data from each per-concept CSV (sorted for determinism)
    concept_order: list[str] = []
    concept_meta: dict[str, dict] = {}   # name → {type, role, sources, context}
    approved_by_concept: dict[str, list[dict]] = {}

    expansions_by_concept: dict[str, list[dict]] = {}

    for csv_path in sorted(concepts_dir.glob("*.csv")):
        csv_meta, rows, exp_rows = _load_concept_csv(csv_path)
        name = csv_meta.get("concept_name", "").strip()
        if not name:
            continue

        role_raw = csv_meta.get("role", "").strip()
        role_val: list[str] = [r.strip() for r in role_raw.split(";") if r.strip()]
        sources_raw = csv_meta.get("sources", "").strip()
        concept_meta[name] = {
            "type": csv_meta.get("concept_type", "").strip(),
            "role": role_val,
            "sources": [s.strip() for s in sources_raw.split(";") if s.strip()],
            "context": csv_meta.get("context", "").strip(),
        }
        concept_order.append(name)

        # Collect included expansion rows
        included_expansions: list[dict] = []
        for exp_row in exp_rows:
            inc = exp_row.get("include/exclude", "").strip().lower()
            if inc == "include":
                entry: dict = {}
                if exp_row.get("system", "").strip():
                    entry["system"] = exp_row["system"].strip()
                if exp_row.get("expansion", "").strip():
                    raw_expansion = exp_row["expansion"].strip()
                    exp_rel_code = raw_expansion.split("|", 1)
                    if len(exp_rel_code) == 2:
                        entry["relation"] = exp_rel_code[0].strip()
                        entry["code"] = exp_rel_code[1].strip()
                    else:
                        entry["expansion"] = raw_expansion
                if exp_row.get("rationale", "").strip():
                    entry["rationale"] = exp_row["rationale"].strip()
                if entry:
                    included_expansions.append(entry)
        if included_expansions:
            expansions_by_concept[name] = included_expansions

        # Collect approved candidate rows and their related rows
        # Related rows are linked via the explicit related_code field.
        # Build parent_key → entry map for attaching related rows.
        approved_by_concept.setdefault(name, [])
        parent_entries: dict[str, dict] = {}  # code.casefold() → entry

        for row in rows:
            row_type = row.get("row_type", "").strip().lower()
            is_included = row.get("include/exclude", "").strip().lower() == "include"
            system = row.get("system", "").strip()
            code = row.get("code", "").strip()
            display = row.get("display", "").strip()

            if row_type == "related":
                # Attach to the referenced parent code if parent was approved
                related_code_val = row.get("related_code", "").strip()
                parent_key = related_code_val.casefold() if related_code_val else ""
                parent_entry = parent_entries.get(parent_key)
                if parent_entry is not None and is_included and system and code:
                    rel_entry: dict = {k: v for k, v in {"system": system, "code": code, "display": display}.items() if v}
                    relation = row.get("relation", "").strip()
                    if relation:
                        rel_entry["relation"] = relation
                    parent_entry.setdefault("related", []).append(rel_entry)
                continue

            if not is_included or not system or not code:
                continue

            cand_key = (system.casefold(), code.casefold())
            if not any(
                (e["system"].casefold(), e["code"].casefold()) == cand_key
                for e in approved_by_concept[name]
            ):
                cand_entry: dict = {k: v for k, v in {"system": system, "code": code, "display": display}.items() if v}
                cand_entry["_key"] = code.casefold()
                approved_by_concept[name].append(cand_entry)
                parent_entries[code.casefold()] = cand_entry

    # Build concept rows and a thin value-set manifest that references them.
    #
    # concepts[] remains the authoritative terminology catalog: approved codes,
    # approved expansions, roles, and source context live there. sections.value_sets[]
    # declares which computable ValueSets should be emitted without duplicating
    # the code content in a second structure.
    concept_rows = []
    value_set_rows = []
    for name in concept_order:
        info = concept_meta[name]
        concept_id = _slugify(name)
        concept_row: dict = {"id": concept_id, "name": name, "type": info["type"]}
        if info.get("role"):
            concept_row["role"] = info["role"]
        if info.get("context"):
            concept_row["context"] = info["context"]
        codes_raw = approved_by_concept.get(name, [])
        if codes_raw:
            # Strip internal _key before writing
            codes_clean = []
            for entry in codes_raw:
                clean = {k: v for k, v in entry.items() if k != "_key"}
                codes_clean.append(clean)
            concept_row["codes"] = codes_clean
        if name in expansions_by_concept:
            concept_row["expansions"] = expansions_by_concept[name]
        has_approved_content = bool(concept_row.get("codes")) or bool(concept_row.get("expansions"))
        if not has_approved_content:
            continue
        concept_rows.append(concept_row)
        value_set_rows.append({
            "id": concept_id,
            "name": name,
            "concept_refs": [concept_id],
        })

    # derived_from: union of all concept sources
    all_sources: set[str] = set()
    for info in concept_meta.values():
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
            "value_sets": value_set_rows,
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
        "file": f"topics/{topic}/structured/concepts/concepts.yaml",
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
        "concepts_written",
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
    "decision-table": "recommendation triggers, local applicability conditions, recommendation actions, and decision criteria",
    "care-pathway": "step sequencing, timing windows, and actor responsibilities",
    "terminology": "code coverage, concept boundaries, and preferred terms",
    "measure": "population definitions, scoring logic, and measurement period",
    "assessment": "item wording, response options, and scoring ranges",
    "policy": "coverage criteria, authorization requirements, and payer definitions",
}


_ARTIFACT_PROMPT_GUIDANCE: dict[str, str] = {
    "decision-table": """\
Decision-table extraction guidance:
- Use recommendation-scoped events, not broad pathway phases, as the primary trigger units.
- Keep `when` values local to the recommendation being evaluated rather than restating general pathway progression.
- Use canonical `Yes` / `No` values in `conditions.values[]` and `rules.when{}`.
- For every condition/question in `conditions[]`, add one or more `data_elements[]`
  entries that name the patient features or clinical data needed to answer it.
- Prefer `conditions[]` to represent the decision variables or clinical
  conclusions that appear in rules.
- When the source describes multi-part criteria, keep the higher-level
  condition in `conditions[]` and represent the underlying patient features in
  `data_elements[]` rather than turning every feature into its own condition.
- If the source says “at this step, do X” or “during this phase, assess/review/obtain Y,”
  prefer an event-driven rule with `event + then` and no `when`.
- Do not gate verification, assessment, review, or evidence-gathering actions on
  the same confirmed state they are intended to establish.
- When the source describes a broader recommended action that contains distinct
  operational tasks, model the broader recommendation as the parent action and
  add separate child actions for the broken-down tasks when the source treats
  them as operationally separate.
- Use a child action for distinct tasks such as administering a questionnaire,
  reviewing imaging, reviewing prior therapy history, ordering a prerequisite
  study, or carrying out a separate counseling step. Group closely related work
  into one child action when the source does not require finer separation.
- When one guideline segment describes sequential reasoning in a single pathway,
  prefer one decision-table with staged events over child tables. Use earlier
  actions to establish later branch conditions, then gate later events on those
  conditions.
- Use `actions[].produces_conditions[]` when an action explicitly establishes a
  later branch condition.
- Use `actions[].produces_data_elements[]` when an action produces a concrete
  finding, score, or other evidence item that later logic consumes.
- Do not model the result of a child task as a prerequisite for doing the task
  itself. If the task obtains a score, finding, or result, make that
  result a `data_elements[]` entry and link it from the action with
  `produces_data_elements[]`.
- Use `actions[].parent_action_id` when a supporting action belongs under a
  broader parent action rather than standing alone.
- Use `actions[].assessment_artifact` when an action explicitly administers or
  reviews a structured questionnaire or assessment instrument that should later
  formalize to a Questionnaire.
- For later recommendation branches, use explicit assessed states from the
  source rather than inventing a generic summary condition when the guideline
  does not name one.
- Use canonical `kind` for actions; do not emit legacy action `type`.
- Keep `events[]` at the level of major workflow contexts or decision moments.
  Do not create a separate event for every child task or narrow sub-step when
  those activities still belong to the same broader staged context.
- Use `event.trigger` only when there is an explicit formal trigger. Omit it
  when the event itself is the full workflow context.
- If several recommendations share the same workflow moment, keep one event and
  express the finer distinction through separate rules and child actions rather
  than proliferating near-duplicate events.
- If the narrative clearly groups recommendations by care phase, optionally define `sections.pathway_phases[]` as the canonical phase model and keep that grouping in `event.phase` and/or `rule.phase` without turning phases themselves into events.
- Prefer one clinically explicit rule per recommendation branch, with `action` as a short human label and `rationale` as the recommendation basis.
- When a recommendation belongs to a recognizable phase such as assessment, planning, intraoperative, or postoperative care, populate `rule.phase`.
- When the logic reads as a sequence such as verify -> assess -> recommend,
  keep that as staged events in one table unless a later stage becomes too
  large or internally complex to remain readable as a single decision-table.""",
    "care-pathway": """\
Care-pathway extraction guidance:
- Model the clinical sequence as flat `steps[]` with optional `parent_id`; do not use nested `substeps[]`.
- When the source describes one overarching patient journey with major phases, include a top-level pathway step and make the major phases children via `parent_id`.
- Use care-pathway for sequencing, actor ownership, and transitions; keep recommendation logic itself in the decision-table artifact.
- Keep top-level steps clinically meaningful and stable; reserve leaf steps for meaningful sub-phases, not every individual recommendation.
- When different parts of the pathway activate at different workflow moments, represent them as separate sibling branches under the same parent pathway rather than forcing one linear sequence.
- Use a separate branch for coordination work such as scheduling follow-up when it has a different trigger or timing from assessment, planning, or completed follow-up.
- Do not create a separate pathway step for intervention execution when the source is really describing preservice planning or ordering logic; keep the execution detail under the planning branch unless the guideline truly treats it as its own clinical stage.
- Use `transitions[]` only for actual clinical progression dependencies between steps.""",
}


def _artifact_prompt_guidance(artifact_type: str | None) -> str:
    if not artifact_type:
        return ""
    return _ARTIFACT_PROMPT_GUIDANCE.get(artifact_type, "")


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
            f"- MCP enrichment command: `rh-skills promote concept enrich {topic} <name> --candidate <system|code|display>`",
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
    if concept_review:
        artifacts.append(_build_concepts_extract_artifact_entry(concept_review))

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_yaml = _render_extract_plan(topic, artifacts, concept_review)
    plan_path.write_text(plan_yaml)
    plan = _yaml_safe().load(plan_yaml)
    _extract_readout_path(topic).write_text(_render_extract_readout(plan))
    if frontmatter_concepts:
        concepts_dir, meta_path = _build_concept_review_csvs(topic, frontmatter_concepts)
        log_info(f"Created: {concepts_dir}")
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
        click.echo(f"  2. Enrich concepts    : rh-skills promote concept enrich {topic} <name> --candidate <system|code|display>")
        click.echo(f"  3. Edit the CSVs      : open topics/{topic}/process/plans/concepts/")
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


def _validate_system_uri(system: str, context: str = "--candidate") -> None:
    """Raise UsageError if system is not a URI (must start with http:// or https://).

    Use the system URI returned by reasonhub-codesystem_lookup — never pass
    short names like 'SNOMED-CT', 'LOINC', 'ICD-10', or 'RxNorm'.
    """
    if not (system.startswith("http://") or system.startswith("https://")):
        raise click.UsageError(
            f"{context}: system must be a canonical URI (e.g. 'http://snomed.info/sct'), "
            f"got: {system!r}. Use the system URI returned by reasonhub-codesystem_lookup."
        )


_EXTRACT_BASE_ONTOLOGY_RELATIONS = {
    "is_a",
    "finding_site",
    "associated_morphology",
    "causative_agent",
}
_EXTRACT_CONDITIONAL_ONTOLOGY_RELATIONS = {"due_to"}
_EXTRACT_ALLOWED_ONTOLOGY_RELATIONS = (
    _EXTRACT_BASE_ONTOLOGY_RELATIONS | _EXTRACT_CONDITIONAL_ONTOLOGY_RELATIONS
)

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
    system = parts[0].strip()
    _validate_system_uri(system)
    entry: dict = {
        "system": system,
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
@click.argument("concept_name", metavar="NAME")
@click.option(
    "--source",
    "source",
    default="mcp",
    type=click.Choice(["mcp", "custom"], case_sensitive=False),
    help="Source of candidates: 'mcp' (default, MCP lookup) or 'custom' (manual/no-code concept).",
)
@click.option("--type", "concept_type", default=None, metavar="TYPE", help="SNOMED semantic tag (e.g. finding | disorder | procedure). Required when --source custom and the concept is new.")
@click.option(
    "--candidate",
    "raw_candidates",
    multiple=True,
    type=click.STRING,
    metavar="TEXT",
    help="MCP candidate to record. Format: 'system|code|display[|distance[|confidence]]'. Repeatable. Only valid with --source mcp.",
)
@click.option(
    "--related-candidate",
    "raw_related_candidates",
    multiple=True,
    type=click.STRING,
    metavar="TEXT",
    help=(
        "Related code linked to a specific parent candidate. "
        "Format: 'PARENT_CODE|system|code|display[|relation]' where PARENT_CODE is the code value of an existing candidate row "
        "and relation is an ontology predicate (e.g. is_a, finding_site, associated_morphology, causative_agent, due_to). "
        "Repeatable. Only valid with --source mcp."
    ),
)
@click.option("--lookup-query", "lookup_query", default=None, metavar="TEXT", help="Search query used. Defaults to concept name. Only valid with --source mcp.")
@click.option("--lookup-notes", "lookup_notes", default=None, metavar="TEXT", help="Optional notes from the MCP lookup. Only valid with --source mcp.")
@click.option(
    "--expansion",
    "raw_expansions",
    multiple=True,
    type=click.STRING,
    metavar="TEXT",
    help="Expansion row to append. Format: 'system|relation|code[|rationale]' where relation is an ontology predicate (e.g. is_a, finding_site). Repeatable.",
)
@click.option("--reset", "reset", is_flag=True, help="Clear existing candidate rows and restore placeholder. Use alone or before re-adding candidates.")
def enrich_concepts(topic, concept_name, source, concept_type, raw_candidates, raw_related_candidates, lookup_query, lookup_notes, raw_expansions, reset):
    """Enrich a concept with MCP candidates, custom placeholder, or expansion expressions.

    \b
    --source mcp (default): record RH MCP lookup candidates.
      rh-skills promote concept enrich <topic> \\
        --concept "Hypertension" \\
        --candidate "http://snomed.info/sct|38341003|Hypertensive disorder, systemic arterial (disorder)|0.02|high" \\
        --lookup-query "Hypertension"

    \b
    --source custom: create a new concept with no MCP candidates (custom/manual concept).
      rh-skills promote concept enrich <topic> \\
        --concept "Frailty" --source custom --type finding

    \b
    Both sources: add an intensional expansion expression.
      rh-skills promote concept enrich <topic> \\
        --concept "Hypertension" \\
        --expansion "http://snomed.info/sct|<<38341003|All subtypes of hypertension"

    \b
    Combined in one call (mcp source):
      rh-skills promote concept enrich <topic> \\
        --concept "Hypertension" \\
        --candidate "http://snomed.info/sct|38341003|Hypertensive disorder" \\
        --expansion "http://snomed.info/sct|<<38341003|All subtypes"

    \b
    Reset candidates:
      rh-skills promote concept enrich <topic> --concept "Hypertension" --reset
    """
    source = source.lower()

    # --candidate / --related-candidate / --lookup-* are MCP-only
    if source == "custom":
        if raw_candidates:
            raise click.UsageError("--candidate is not valid with --source custom.")
        if raw_related_candidates:
            raise click.UsageError("--related-candidate is not valid with --source custom.")
        if lookup_query:
            raise click.UsageError("--lookup-query is not valid with --source custom.")
        if lookup_notes:
            raise click.UsageError("--lookup-notes is not valid with --source custom.")

    require_topic(require_tracking(), topic)
    meta = _load_concept_review_meta(topic)
    if meta.get("status") == "approved":
        raise click.UsageError("Concept review is already approved.")

    csv_path = _concept_csv_path(topic, concept_name)

    # --source custom: create the CSV if it doesn't exist yet (replaces `concept add`)
    if source == "custom" and not csv_path.exists():
        if not concept_type:
            raise click.UsageError("--type is required when --source custom and the concept does not yet exist.")
        concepts_dir = _concepts_csv_dir(topic)
        if not concepts_dir.exists():
            raise click.UsageError(
                f"No concept CSVs found. Run 'rh-skills promote plan {topic}' first."
            )
        existing_slugs = {p.stem for p in concepts_dir.glob("*.csv")}
        if _slugify(concept_name) in existing_slugs:
            raise click.UsageError(
                f"Concept '{concept_name}' already exists in the concept CSVs."
            )
        with _lock_concept_review(csv_path):
            csv_meta_new = {
                "concept_name": concept_name,
                "concept_type": concept_type,
                "role": "",
                "sources": "custom",
                "context": "",
                "lookup_query": concept_name,
                "lookup_notes": "",
            }
            expansion_rows_new: list[dict] = []
            for raw_exp in raw_expansions:
                exp_parts = raw_exp.split("|", 3)
                exp_system = exp_parts[0].strip() if len(exp_parts) > 0 else ""
                exp_relation = exp_parts[1].strip() if len(exp_parts) > 1 else ""
                exp_code = exp_parts[2].strip() if len(exp_parts) > 2 else ""
                exp_rationale = exp_parts[3].strip() if len(exp_parts) > 3 else ""
                if not exp_system or not exp_relation or not exp_code:
                    raise click.UsageError(
                        f"--expansion value must be 'system|relation|code[|rationale]', got: {raw_exp!r}"
                    )
                expansion_rows_new.append({
                    "include/exclude": "",
                    "system": exp_system,
                    "expansion": f"{exp_relation}|{exp_code}",
                    "rationale": exp_rationale,
                })
            _write_concept_csv(csv_path, csv_meta_new, [], expansion_rows=expansion_rows_new)
            checksums = meta.get("checksums") or {}
            checksums[_slugify(concept_name)] = _csv_checksum(csv_path)
            meta["checksums"] = checksums
            _write_concept_review_meta(topic, meta)
        log_info(
            f"Added custom concept '{concept_name}' (type: {concept_type})"
            + (f" with {len(expansion_rows_new)} expansion(s)." if expansion_rows_new else ".")
        )
        return

    # --source mcp (or custom with existing CSV): CSV must exist
    if source == "custom":
        # CSV already exists — user should use --source mcp to add candidates/expansions to it
        raise click.UsageError(
            f"Concept '{concept_name}' already exists. "
            f"Use --source mcp (the default) to add candidates or expansions to an existing concept."
        )
    if not csv_path.exists():
        raise click.UsageError(
            f"No concept CSV found for '{concept_name}'. "
            f"Run 'rh-skills promote plan {topic}' first, or use --source custom to create a new concept."
        )
    remaining = 0
    appended_count = 0
    with _lock_concept_review(csv_path):
        meta = _load_concept_review_meta(topic)
        if meta.get("status") == "approved":
            raise click.UsageError("Concept review is already approved; re-plan if you need to change candidates.")

        csv_meta, rows, expansion_rows = _load_concept_csv(csv_path)
        effective_lookup_query = lookup_query or csv_meta.get("lookup_query") or concept_name

        if reset:
            if not raw_candidates:
                csv_meta["lookup_query"] = effective_lookup_query
                if lookup_notes is not None:
                    csv_meta["lookup_notes"] = lookup_notes
                _write_concept_csv(csv_path, csv_meta, [])
                checksums = meta.get("checksums") or {}
                checksums[_slugify(concept_name)] = _csv_checksum(csv_path)
                meta["checksums"] = checksums
                _write_concept_review_meta(topic, meta)
                log_info(f"Reset candidates for '{concept_name}'.")
                return
            rows = []

        existing_candidate_rows = [
            r for r in rows
            if r.get("row_type", "").strip().lower() in ("candidate", "")
            and (r.get("system", "").strip() or r.get("code", "").strip())
        ]
        # Related rows are keyed by the code they belong to — rebuild from explicit related_code field
        existing_related_by_parent: dict[str, list[dict]] = {}
        for r in rows:
            if r.get("row_type", "").strip().lower() == "related":
                rel_code_val = r.get("related_code", "").strip().casefold()
                # Fall back to scanning for last candidate if related_code is missing (old CSVs)
                if not rel_code_val:
                    pass  # handled below
                else:
                    # Reconstruct parent key (system|code) by matching related_code to existing candidates
                    parent_cand = next(
                        (c for c in rows if c.get("code", "").strip().casefold() == rel_code_val), None
                    )
                    if parent_cand:
                        pk = (
                            parent_cand.get("system", "").strip().casefold()
                            + "|"
                            + parent_cand.get("code", "").strip().casefold()
                        )
                        existing_related_by_parent.setdefault(pk, []).append(r)
        # For any related row that had no related_code, fall back to positional order
        current_parent_key: str = ""
        for r in rows:
            rt = r.get("row_type", "").strip().lower()
            if rt in ("candidate", "") and (r.get("system", "").strip() or r.get("code", "").strip()):
                current_parent_key = (
                    r.get("system", "").strip().casefold() + "|" + r.get("code", "").strip().casefold()
                )
            elif rt == "related" and not r.get("related_code", "").strip():
                if current_parent_key:
                    existing_related_by_parent.setdefault(current_parent_key, []).append(r)

        _CONF_RANK = {"high": 2, "medium": 1, "low": 0}
        last_appended_key: str = ""
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
            parent_key = new_system.casefold() + "|" + new_code.casefold()

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
                old_conf = _CONF_RANK.get(dup_row.get("confidence", "").lower(), -1)
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
                    dup_row["confidence"] = new_conf_str
                    log_info(f"Updated candidate {new_system}|{new_code} with better entry.")
                else:
                    log_info(f"Skipped duplicate {new_system}|{new_code} — existing retained.")
            else:
                new_row: dict = {
                    "include/exclude": "",
                    "system": new_system,
                    "code": new_code,
                    "display": new_display,
                    "distance": str(new_dist) if new_dist is not None else "",
                    "confidence": new_conf_str,
                    "row_type": "candidate",
                    "relation": "",
                    "related_code": "",
                    "comments": "",
                }
                existing_candidate_rows.append(new_row)
                appended_count += 1
            last_appended_key = parent_key

        # Process --related-candidate flags; format: PARENT_CODE|system|code|display[|relation]
        for raw_rel in raw_related_candidates:
            parts = raw_rel.split("|")
            rel_parent_code = parts[0].strip() if len(parts) > 0 else ""
            rel_system = parts[1].strip() if len(parts) > 1 else ""
            rel_code = parts[2].strip() if len(parts) > 2 else ""
            rel_display = parts[3].strip() if len(parts) > 3 else ""
            rel_relation = parts[4].strip() if len(parts) > 4 else "is_a"
            if not rel_parent_code or not rel_system or not rel_code:
                continue
            parent_row = next(
                (
                    r for r in existing_candidate_rows
                    if r.get("code", "").strip().casefold() == rel_parent_code.casefold()
                ),
                None,
            )
            if parent_row is None:
                raise click.UsageError(
                    f"--related-candidate: parent code '{rel_parent_code}' not found in candidate rows for '{concept_name}'."
                )
            parent_key = (
                parent_row.get("system", "").strip().casefold()
                + "|"
                + parent_row.get("code", "").strip().casefold()
            )
            rel_row: dict = {
                "include/exclude": "",
                "system": rel_system,
                "code": rel_code,
                "display": rel_display,
                "distance": "",
                "confidence": "",
                "row_type": "related",
                "relation": rel_relation,
                "related_code": parent_row.get("code", "").strip(),
                "comments": "",
            }
            existing_related_by_parent.setdefault(parent_key, []).append(rel_row)

        # Update lookup metadata on csv_meta
        csv_meta["lookup_query"] = effective_lookup_query
        if lookup_notes is not None:
            csv_meta["lookup_notes"] = lookup_notes

        # Append any --expansion rows (dedup by system+relation+code)
        existing_exp_keys = {
            (r.get("system", "").strip().casefold(), r.get("expansion", "").strip().casefold())
            for r in expansion_rows
        }
        appended_exp_count = 0
        for raw_exp in raw_expansions:
            exp_parts = raw_exp.split("|", 3)
            exp_system = exp_parts[0].strip() if len(exp_parts) > 0 else ""
            exp_relation = exp_parts[1].strip() if len(exp_parts) > 1 else ""
            exp_code = exp_parts[2].strip() if len(exp_parts) > 2 else ""
            exp_rationale = exp_parts[3].strip() if len(exp_parts) > 3 else ""
            if not exp_system or not exp_relation or not exp_code:
                raise click.UsageError(
                    f"--expansion value must be 'system|relation|code[|rationale]', got: {raw_exp!r}"
                )
            exp_expr = f"{exp_relation}|{exp_code}"
            key = (exp_system.casefold(), exp_expr.casefold())
            if key in existing_exp_keys:
                log_info(f"Skipped duplicate expansion {exp_system}|{exp_expr} — existing retained.")
                continue
            expansion_rows.append({
                "include/exclude": "",
                "system": exp_system,
                "expansion": exp_expr,
                "rationale": exp_rationale,
            })
            existing_exp_keys.add(key)
            appended_exp_count += 1

        if appended_exp_count > 0 and not raw_related_candidates:
            click.echo(
                "Warning: Expansion rule recorded without any --related-candidate rows. "
                "Run 'concept enrich' with --related-candidate to add concrete codes for this expansion.",
                err=True,
            )

        # Rebuild rows: interleave candidate rows with their related rows
        updated_rows: list[dict] = []
        for cand_row in existing_candidate_rows:
            updated_rows.append(cand_row)
            parent_key = (
                cand_row.get("system", "").strip().casefold()
                + "|"
                + cand_row.get("code", "").strip().casefold()
            )
            for rel_row in existing_related_by_parent.get(parent_key, []):
                updated_rows.append(rel_row)

        _write_concept_csv(csv_path, csv_meta, updated_rows, expansion_rows=expansion_rows)
        checksums = meta.get("checksums") or {}
        checksums[_slugify(concept_name)] = _csv_checksum(csv_path)
        meta["checksums"] = checksums
        _write_concept_review_meta(topic, meta)

        concepts_dir = _concepts_csv_dir(topic)
        remaining = sum(
            1 for p in concepts_dir.glob("*.csv")
            if not any(
                r.get("system", "").strip()
                for r in _load_concept_csv(p)[1]  # index 1 = code_rows
            )
        )

    parts_done: list[str] = []
    if raw_candidates:
        parts_done.append(f"{appended_count} candidate(s)")
    if appended_exp_count:
        parts_done.append(f"{appended_exp_count} expansion(s)")
    if not parts_done:
        parts_done.append("lookup metadata updated")
    log_info(
        f"Enriched '{concept_name}'"
        + (f" ({concept_type})" if concept_type else "")
        + f" — {', '.join(parts_done)}; {remaining} concept(s) still without candidates."
    )


@concept.command("review")
@click.argument("topic")
@click.argument("concept_name", metavar="NAME", required=False, default=None)
@click.option("--approve-all", "approve_all", is_flag=True, help="Set approved=y on all candidate and related rows for the concept.")
@click.option("--exclude-all", "exclude_all", is_flag=True, help="Set approved=n on all candidate and related rows for the concept.")
@click.option("--approve-code", "approve_codes", multiple=True, metavar="CODE", help="Set approved=y on the row matching this code value.")
@click.option("--exclude-code", "exclude_codes", multiple=True, metavar="CODE", help="Set approved=n on the row matching this code value.")
@click.option("--approve-related", "approve_related", multiple=True, metavar="PARENT_CODE|RELATED_CODE", help="Set include on the related row matching this PARENT_CODE|RELATED_CODE pair. Repeatable.")
@click.option("--exclude-related", "exclude_related", multiple=True, metavar="PARENT_CODE|RELATED_CODE", help="Set exclude on the related row matching this PARENT_CODE|RELATED_CODE pair. Repeatable.")
@click.option("--approve-expansion", "approve_expansions", multiple=True, metavar="SYSTEM|RELATION|CODE", help="Set include on the expansion row matching this SYSTEM|RELATION|CODE triple. Repeatable.")
@click.option("--exclude-expansion", "exclude_expansions", multiple=True, metavar="SYSTEM|RELATION|CODE", help="Set exclude on the expansion row matching this SYSTEM|RELATION|CODE triple. Repeatable.")
@click.option("--note", default="", metavar="TEXT", help="Set comment on the first row for the concept.")
@click.option("--finalize", is_flag=True, help="Seal the review (status: approved). Requires --reviewer.")
@click.option("--reviewer", default=None, metavar="NAME", help="Reviewer name. Required for --finalize.")
@click.option("--force", is_flag=True, help="Bypass the checksum unchanged warning during --finalize.")
def review_concepts(topic, concept_name, approve_all, exclude_all, approve_codes, exclude_codes, approve_related, exclude_related, approve_expansions, exclude_expansions, note, finalize, reviewer, force):
    """Update concept decisions in concepts-review.csv, then finalize.

    \b
    Non-interactive (AI agent):
      # Approve all candidate rows for a concept:
      rh-skills promote concept review <topic> --concept "Hypertension" --approve-all

      # Exclude all candidate rows for a concept:
      rh-skills promote concept review <topic> --concept "Hypertension" --exclude-all

      # Approve or exclude a specific code:
      rh-skills promote concept review <topic> --concept "Hypertension" --approve-code 38341003
      rh-skills promote concept review <topic> --concept "Hypertension" --exclude-code I10

      # Add a comment to a concept:
      rh-skills promote concept review <topic> --concept "Hypertension" --note "Confirmed SNOMED"

      # Finalize (seal the review):
      rh-skills promote concept review <topic> --finalize --reviewer "taylor"

      # Force-finalize even if CSV is unchanged:
      rh-skills promote concept review <topic> --finalize --reviewer "taylor" --force
    """
    if not concept_name and not finalize:
        raise click.UsageError(
            "Provide a concept NAME with at least one of --approve-all, --exclude-all, --approve-code, --exclude-code, --approve-related, --exclude-related, --approve-expansion, --exclude-expansion, or --note; or use --finalize."
        )

    require_topic(require_tracking(), topic)
    concepts_dir = _concepts_csv_dir(topic)
    if not concepts_dir.exists():
        raise click.UsageError(
            f"No concept CSVs found. Run 'rh-skills promote plan {topic}' first."
        )

    # --- per-concept update ---
    if concept_name:
        if not approve_all and not exclude_all and not approve_codes and not exclude_codes and not approve_related and not exclude_related and not approve_expansions and not exclude_expansions and not note:
            raise click.UsageError("concept NAME requires at least one of --approve-all, --exclude-all, --approve-code, --exclude-code, --approve-related, --exclude-related, --approve-expansion, --exclude-expansion, or --note.")
        csv_path = _concept_csv_path(topic, concept_name)
        if not csv_path.exists():
            raise click.UsageError(f"Concept '{concept_name}' not found.")
        with _lock_concept_review(csv_path):
            meta = _load_concept_review_meta(topic)
            if meta.get("status") == "approved":
                raise click.UsageError("Concept review is already approved.")
            csv_meta, rows, expansion_rows = _load_concept_csv(csv_path)
            if approve_all:
                for r in rows:
                    if r.get("system", "").strip() or r.get("code", "").strip():
                        r["include/exclude"] = "include"
            if exclude_all:
                for r in rows:
                    if r.get("system", "").strip() or r.get("code", "").strip():
                        r["include/exclude"] = "exclude"
            for code_val in approve_codes:
                for r in rows:
                    if r.get("code", "").strip() == code_val.strip():
                        r["include/exclude"] = "include"
            for code_val in exclude_codes:
                for r in rows:
                    if r.get("code", "").strip() == code_val.strip():
                        r["include/exclude"] = "exclude"
            for pair in approve_related:
                rel_parts = pair.split("|", 1)
                parent_c = rel_parts[0].strip() if rel_parts else ""
                related_c = rel_parts[1].strip() if len(rel_parts) > 1 else ""
                for r in rows:
                    if (
                        r.get("row_type", "").strip().lower() == "related"
                        and r.get("related_code", "").strip().casefold() == parent_c.casefold()
                        and r.get("code", "").strip().casefold() == related_c.casefold()
                    ):
                        r["include/exclude"] = "include"
            for pair in exclude_related:
                rel_parts = pair.split("|", 1)
                parent_c = rel_parts[0].strip() if rel_parts else ""
                related_c = rel_parts[1].strip() if len(rel_parts) > 1 else ""
                for r in rows:
                    if (
                        r.get("row_type", "").strip().lower() == "related"
                        and r.get("related_code", "").strip().casefold() == parent_c.casefold()
                        and r.get("code", "").strip().casefold() == related_c.casefold()
                    ):
                        r["include/exclude"] = "exclude"
            for pair in approve_expansions:
                exp_parts = pair.split("|", 2)
                exp_sys = exp_parts[0].strip() if exp_parts else ""
                exp_rel = exp_parts[1].strip() if len(exp_parts) > 1 else ""
                exp_code = exp_parts[2].strip() if len(exp_parts) > 2 else ""
                exp_expr = f"{exp_rel}|{exp_code}" if exp_rel and exp_code else ""
                for er in expansion_rows:
                    if (
                        er.get("system", "").strip().casefold() == exp_sys.casefold()
                        and er.get("expansion", "").strip().casefold() == exp_expr.casefold()
                    ):
                        er["include/exclude"] = "include"
            for pair in exclude_expansions:
                exp_parts = pair.split("|", 2)
                exp_sys = exp_parts[0].strip() if exp_parts else ""
                exp_rel = exp_parts[1].strip() if len(exp_parts) > 1 else ""
                exp_code = exp_parts[2].strip() if len(exp_parts) > 2 else ""
                exp_expr = f"{exp_rel}|{exp_code}" if exp_rel and exp_code else ""
                for er in expansion_rows:
                    if (
                        er.get("system", "").strip().casefold() == exp_sys.casefold()
                        and er.get("expansion", "").strip().casefold() == exp_expr.casefold()
                    ):
                        er["include/exclude"] = "exclude"
            if note:
                if rows:
                    rows[0]["comments"] = note
                else:
                    csv_meta["comments"] = note
            _write_concept_csv(csv_path, csv_meta, rows, expansion_rows=expansion_rows)
            checksums = meta.get("checksums") or {}
            checksums[_slugify(concept_name)] = _csv_checksum(csv_path)
            meta["checksums"] = checksums
            _write_concept_review_meta(topic, meta)
        actions = []
        if approve_all:
            actions.append("approve-all")
        if exclude_all:
            actions.append("exclude-all")
        if approve_codes:
            actions.append(f"approve-code: {', '.join(approve_codes)}")
        if exclude_codes:
            actions.append(f"exclude-code: {', '.join(exclude_codes)}")
        if approve_related:
            actions.append(f"approve-related: {', '.join(approve_related)}")
        if exclude_related:
            actions.append(f"exclude-related: {', '.join(exclude_related)}")
        if approve_expansions:
            actions.append(f"approve-expansion: {', '.join(approve_expansions)}")
        if exclude_expansions:
            actions.append(f"exclude-expansion: {', '.join(exclude_expansions)}")
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

        invalid_related_rows: list[str] = []
        _VALID_DECISION = {"include", "exclude"}
        missing_status: list[str] = []

        all_csv_paths = sorted(concepts_dir.glob("*.csv"))
        for csv_path in all_csv_paths:
            csv_meta, rows, _ = _load_concept_csv(csv_path)
            n = csv_meta.get("concept_name", csv_path.stem)
            for r in rows:
                has_code = bool(r.get("system", "").strip() or r.get("code", "").strip())
                if not has_code:
                    continue
                if r.get("row_type", "").strip().lower() == "related":
                    decision_val = r.get("include/exclude", "").strip().lower()
                    if decision_val == "include":
                        relation = r.get("relation", "").strip().lower()
                        if relation not in _EXTRACT_ALLOWED_ONTOLOGY_RELATIONS:
                            invalid_related_rows.append(
                                f"{n!r} (code: {r.get('code', '').strip() or '?'}, relation: {relation or '<empty>'})"
                            )
                if r.get("row_type", "").strip().lower() == "related":
                    continue
                status_val = r.get("include/exclude", "").strip().lower()
                if status_val not in _VALID_DECISION:
                    code_id = r.get("code", "").strip() or r.get("system", "").strip()
                    missing_status.append(f"{n!r} (candidate code: {code_id})")

        if missing_status:
            raise click.UsageError(
                "Cannot finalize: the following code rows are missing a valid 'include/exclude' decision "
                "(must be 'include' or 'exclude'):\n  " + "\n  ".join(missing_status)
            )
        if invalid_related_rows:
            raise click.UsageError(
                "Cannot finalize: approved related rows must use extract-stage ontology policy "
                "(allowed ontology predicates only):\n  "
                + "\n  ".join(invalid_related_rows)
            )
        checksums: dict = {}
        for csv_path in all_csv_paths:
            checksums[csv_path.stem] = _csv_checksum(csv_path)
        meta["status"] = "approved"
        meta["reviewer"] = reviewer
        meta["reviewed_at"] = now_iso()
        meta["checksums"] = checksums
        meta["review_artifact"] = f"topics/{topic}/process/plans/concepts/"
        _write_concept_review_meta(topic, meta)
        _sync_plan_concept_review(topic, meta)
        tracking = require_tracking()
        append_topic_event(
            tracking,
            topic,
            "concept_review_approved",
            f"Concept review finalized by '{reviewer}'",
        )
        save_tracking(tracking)
        log_info(
            f"Concept review finalized by '{reviewer}'. "
            f"Run 'rh-skills promote concept write {topic}' during implement to write concepts.yaml."
        )


@concept.command("write")
@click.argument("topic")
def write_concepts(topic):
    """Write topics/<topic>/structured/concepts/concepts.yaml from the approved concept review CSV.

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
    click.echo(f"  1. Review the readout  : cat topics/{topic}/process/plans/formalize-plan-readout.md")
    click.echo(f"  2. Approve the target  : rh-skills promote formalize-approve {topic}")
    click.echo(f"  3. Run formalization   : rh-inf-formalize implement {topic}")


def _apply_formalize_artifact_decision(
    plan: dict,
    artifact_name: str,
    decision: str,
    notes: str = "",
    set_target: bool = False,
) -> None:
    """Mutate formalize plan in-place: set reviewer_decision and optional fields.

    ``set_target`` clears implementation_target on all other artifacts and sets
    it to True on the named one.
    """
    artifact = next(
        (a for a in (plan.get("artifacts") or []) if a.get("name") == artifact_name),
        None,
    )
    if artifact is None:
        available = [a.get("name") for a in (plan.get("artifacts") or [])]
        raise click.UsageError(
            f"Artifact '{artifact_name}' not found in formalize-plan.yaml. "
            f"Available: {available}"
        )
    artifact["reviewer_decision"] = decision
    if notes:
        artifact["approval_notes"] = notes
    if set_target:
        for a in (plan.get("artifacts") or []):
            a["implementation_target"] = a.get("name") == artifact_name


def _require_formalize_impl_target(plan: dict) -> None:
    """Raise UsageError if the plan does not have exactly one implementation_target."""
    artifacts = plan.get("artifacts") or []
    targets = [a for a in artifacts if a.get("implementation_target") is True]
    if len(targets) == 0:
        names = ", ".join(a.get("name", "?") for a in artifacts)
        raise click.UsageError(
            "No artifact is marked implementation_target: true. "
            f"Use --set-target with --artifact to designate one. Artifacts: {names}"
        )
    if len(targets) > 1:
        names = ", ".join(a.get("name", "?") for a in targets)
        raise click.UsageError(
            f"Multiple artifacts marked implementation_target: true ({names}). "
            "Exactly one is required."
        )


def _interactive_formalize_approve(
    plan: dict,
    plan_path: Path,
    readout_path: Path,
    topic: str,
    reviewer: str | None,
) -> None:
    """Walk pending formalize artifacts interactively and optionally finalize."""
    artifacts = plan.get("artifacts") or []
    pending = [a for a in artifacts if a.get("reviewer_decision") == "pending-review"]

    target_set = any(a.get("implementation_target") for a in artifacts)

    if not pending:
        click.echo("No artifacts pending review.")
    else:
        click.echo(f"\nReviewing {len(pending)} pending artifact(s) for topic '{topic}':\n")
        for artifact in pending:
            name = artifact.get("name", "")
            strategy = artifact.get("strategy", "")
            art_type = artifact.get("artifact_type", "")
            l3_targets = artifact.get("l3_targets") or []
            inputs = artifact.get("input_artifacts") or []
            rationale = artifact.get("rationale", "")
            is_target = artifact.get("implementation_target", False)

            click.echo(f"  Artifact     : {name}")
            click.echo(f"  Type         : {art_type}")
            click.echo(f"  Strategy     : {strategy}")
            click.echo(f"  L3 targets   : {', '.join(l3_targets) or '(none)'}")
            click.echo(f"  Inputs       : {', '.join(inputs) or '(none)'}")
            if rationale:
                click.echo(f"  Rationale    : {rationale[:120]}{'...' if len(rationale) > 120 else ''}")
            click.echo(f"  Impl target  : {'yes' if is_target else 'no'}")

            choice = click.prompt(
                "  Decision",
                type=click.Choice(["approved", "rejected", "needs-revision", "skip"]),
                default="approved",
            )
            if choice == "skip":
                click.echo("  Skipped.\n")
                continue

            notes = click.prompt(
                "  Notes (optional, Enter to skip)", default="", show_default=False
            )

            # Implementation target assignment
            set_target = False
            if choice == "approved" and not target_set:
                set_target = click.confirm(
                    "  Mark as implementation target?", default=True
                )
                if set_target:
                    target_set = True
            elif choice == "approved" and not is_target and target_set:
                set_target = click.confirm(
                    "  Override current implementation target with this artifact?",
                    default=False,
                )
                if set_target:
                    pass  # _apply will clear others

            _apply_formalize_artifact_decision(plan, name, choice, notes, set_target)
            icon = _DECISION_ICON.get(choice, "")
            target_label = " [impl target]" if set_target else ""
            click.echo(f"  → {icon} {choice}{target_label}\n")

    all_decided = all(a.get("reviewer_decision") != "pending-review" for a in artifacts)
    if all_decided and click.confirm("Finalize plan as approved?", default=True):
        try:
            _require_formalize_impl_target(plan)
        except click.UsageError as exc:
            click.echo(f"  ✗ Cannot finalize: {exc.format_message()}", err=True)
            click.echo("  Re-run and mark an approved artifact as the implementation target.")
        else:
            rev = reviewer or plan.get("reviewer") or ""
            if not rev:
                rev = click.prompt("Reviewer name", default="")
            plan["status"] = "approved"
            plan["reviewer"] = rev
            plan["reviewed_at"] = now_iso()

    blocked: list[str] = []  # blocked_inputs not tracked post-creation; pass empty
    _write_formalize_plan_and_readout(plan_path, readout_path, topic, plan, blocked)
    approved = sum(1 for a in artifacts if a.get("reviewer_decision") == "approved")
    log_info(
        f"Plan updated: {approved}/{len(artifacts)} artifact(s) approved, "
        f"status={plan.get('status', 'pending-review')}"
    )


@promote.command("formalize-approve")
@click.argument("topic")
@click.option(
    "--artifact", "artifact_name", default=None, metavar="NAME",
    help="Artifact name to decide on (non-interactive).",
)
@click.option(
    "--decision",
    type=click.Choice(["approved", "rejected", "needs-revision"]),
    default=None,
    help="Decision for --artifact.",
)
@click.option("--notes", default="", help="Approval notes (used with --artifact).")
@click.option(
    "--set-target", "set_target", is_flag=True, default=False,
    help="Mark --artifact as the implementation_target (clears any existing target).",
)
@click.option("--reviewer", default=None, help="Reviewer name written to plan header.")
@click.option(
    "--finalize", is_flag=True,
    help="Set plan status to 'approved' and record reviewer/timestamp.",
)
def formalize_approve(
    topic: str,
    artifact_name: str | None,
    decision: str | None,
    notes: str,
    set_target: bool,
    reviewer: str | None,
    finalize: bool,
) -> None:
    """Record reviewer decisions on formalize-plan.yaml artifacts.

    \b
    Non-interactive (AI agent / script):
      # Approve, mark as implementation target, and finalize in one call:
      rh-skills promote formalize-approve TOPIC \\
        --artifact NAME --decision approved --set-target --finalize [--reviewer NAME]

      # Approve without changing the target:
      rh-skills promote formalize-approve TOPIC --artifact NAME --decision approved

      # Finalize separately (after all artifacts are decided):
      rh-skills promote formalize-approve TOPIC --finalize [--reviewer NAME]

    Interactive (human terminal):
      rh-skills promote formalize-approve TOPIC
    """
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan_path = _formalize_plan_path(topic)
    readout_path = _formalize_readout_path(topic)
    if not plan_path.exists():
        raise click.UsageError(
            f"No formalize plan found. Run 'rh-skills promote formalize-plan {topic}' first."
        )

    if artifact_name or finalize:
        with _lock_plan(plan_path):
            plan = _load_formalize_plan(topic)

            if artifact_name:
                if not decision:
                    raise click.UsageError(
                        "--decision is required when --artifact is specified."
                    )
                _apply_formalize_artifact_decision(
                    plan, artifact_name, decision, notes, set_target
                )
                icon = _DECISION_ICON.get(decision, "")
                target_label = " [impl target]" if set_target else ""
                log_info(f"Artifact '{artifact_name}' → {icon} {decision}{target_label}")

            if finalize:
                if not artifact_name:
                    plan = _load_formalize_plan(topic)
                _require_formalize_impl_target(plan)
                rev = reviewer or plan.get("reviewer") or ""
                plan["status"] = "approved"
                plan["reviewer"] = rev
                plan["reviewed_at"] = now_iso()
                approved = sum(
                    1 for a in (plan.get("artifacts") or [])
                    if a.get("reviewer_decision") == "approved"
                )
                total = len(plan.get("artifacts") or [])
                log_info(
                    f"Plan finalized: status=approved, {approved}/{total} artifact(s) approved"
                )

            blocked: list[str] = []
            _write_formalize_plan_and_readout(
                plan_path, readout_path, topic, plan, blocked
            )
        return

    if not sys.stdin.isatty():
        raise click.UsageError(
            "stdin is not a TTY — use --artifact NAME --decision DECISION for "
            "non-interactive approval, or --finalize to set plan status."
        )
    plan = _load_formalize_plan(topic)
    _interactive_formalize_approve(plan, plan_path, readout_path, topic, reviewer)

@promote.command("body-init")
@click.argument("topic")
@click.argument("name")
@click.option("--output", default=None,
              help="Output path; defaults to topics/<topic>/process/tmp/<name>.yaml")
@click.option("--force", is_flag=True, help="Overwrite existing file")
def body_init(topic, name, output, force):
    """Write a pre-populated body-file scaffold from extract-plan.yaml.

    Reads artifact_type, derived_from, clinical_question, and required_sections
    from the approved plan artifact and writes a structurally correct YAML scaffold
    to topics/<topic>/process/tmp/<name>.yaml (or --output).
    Fill in clinical content, then pass the file to 'rh-skills promote derive --body-file'.
    """
    tracking = require_tracking()
    require_topic(tracking, topic)

    plan = _load_extract_plan(topic)

    artifact_entry = next(
        (a for a in (plan.get("artifacts") or []) if a.get("name") == name),
        None,
    )
    if artifact_entry is None:
        available = ", ".join(
            a.get("name", "?") for a in (plan.get("artifacts") or [])
        )
        raise click.UsageError(
            f"Artifact '{name}' not found in extract-plan.yaml."
            + (f" Available: {available}" if available else "")
        )

    artifact_type = artifact_entry.get("artifact_type") or "evidence-summary"
    if artifact_entry.get("name") == "concepts" and artifact_type == "terminology":
        raise click.UsageError(
            "Artifact 'concepts' is the explicit terminology package from concept review. "
            f"Use 'rh-skills promote concept write {topic}' instead of body-init/derive."
        )

    # Convert plan source_files (paths like sources/normalized/<slug>.md) → bare slugs
    source_files = artifact_entry.get("source_files") or []
    sources: tuple[str, ...] = tuple(Path(sf).stem for sf in source_files)

    key_questions = artifact_entry.get("key_questions") or []
    clinical_question = key_questions[0] if key_questions else ""

    required_sections: tuple[str, ...] = tuple(artifact_entry.get("required_sections") or [])

    # Convert plan concerns (list of dicts with 'issue') to concern-flag strings
    # so the scaffold's sections.concerns block is pre-populated
    plan_concerns = artifact_entry.get("concerns") or []
    concern_strings: tuple[str, ...] = tuple(
        f"{c['issue']}|{sources[0] if sources else ''}|<stub: position>"
        for c in plan_concerns
        if isinstance(c, dict) and c.get("issue")
    )

    scaffold = _build_stub_l2_artifact(
        artifact_name=name,
        source=sources,
        artifact_type=artifact_type,
        clinical_question=clinical_question,
        required_sections=required_sections,
        evidence_refs=(),
        concerns=concern_strings,
    )

    if output:
        out_path = Path(output)
    else:
        out_path = topic_dir(topic) / "process" / "tmp" / f"{name}.yaml"

    if out_path.exists() and not force:
        raise click.UsageError(
            f"{out_path} already exists. Use --force to overwrite."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(scaffold)
    log_info(f"Created: {out_path}")

    click.echo(f"\nFill in clinical content, then run:")
    click.echo(f"  rh-skills promote derive {topic} {name} \\")
    click.echo(f"    --body-file {out_path}")
    click.echo(f"\nNote: artifact_type and derived_from are read from the body file. Do not change id or name.")


@promote.command()
@click.argument("topic")
@click.argument("name")
@click.option("--source", required=False, multiple=True, help="L1 source name (can repeat). Optional when --body-file is provided — derived_from is read from the body file.")
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
@click.option("--force", is_flag=True, help="Overwrite an existing structured artifact and refresh its tracking entry")
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
    force,
    dry_run,
):
    """Promote L1 source(s) to L2 structured artifact(s)."""
    tracking = require_tracking()
    require_topic(tracking, topic)

    # Resolve effective sources: --source flags take precedence; fall back to
    # derived_from in the body file so the agent doesn't have to repeat provenance.
    if not source and body_file:
        _body_preview = _load_body_file(body_file)
        body_derived = _body_preview.get("derived_from") or []
        if not body_derived:
            raise click.UsageError(
                "--source is required when --body-file does not contain a non-empty derived_from list"
            )
        source = tuple(body_derived)
    elif not source:
        raise click.UsageError("--source is required when --body-file is not provided")

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

    offline_mode = _is_offline_mode()
    normalized_source_map = {
        record["name"]: record
        for record in _normalized_source_records(tracking, topic)
    }
    body_text = Path(body_file).read_text() if body_file else None

    base_system_prompt = """\
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
        artifact_guidance = _artifact_prompt_guidance(effective_artifact_type)
        system_prompt = (
            f"{base_system_prompt}\n\n{artifact_guidance}"
            if artifact_guidance else
            base_system_prompt
        )
        related_contexts = _load_related_structured_context(topic, effective_artifact_type)

        if artifact_name == "concepts":
            raise click.UsageError(
                "Artifact 'concepts' is the explicit terminology package from concept review. "
                f"Use 'rh-skills promote concept write {topic}' instead of derive --force."
            )

        user_prompt_parts = [
            f"Source L1 artifact name: {', '.join(source)}\n"
            f"Generate L2 artifact: {artifact_name}\n"
            f"Artifact type: {effective_artifact_type}\n"
            f"Clinical question: {clinical_question or ''}"
        ]
        source_records = [
            normalized_source_map[src]
            for src in source
            if src in normalized_source_map
        ]
        if source_records:
            source_blocks = "\n\n".join(
                f"### Source: `{record['name']}`\n{record['content'][:12000]}"
                for record in source_records
            )
            user_prompt_parts.append(
                "Normalized source content:\n"
                f"{source_blocks}"
            )
        if related_contexts and not offline_mode:
            related_blocks = []
            for related_name, related_data in related_contexts:
                related_blocks.append(
                    f"### Related structured artifact: `{related_name}`\n"
                    f"{_dump_yaml_text(related_data).rstrip()}"
                )
            user_prompt_parts.append(
                "Related structured artifact context (read-only alignment reference, do not copy verbatim):\n"
                + "\n\n".join(related_blocks)
            )
        if body_text is not None and not offline_mode:
            user_prompt_parts.append(
                "Draft YAML to complete:\n"
                f"{body_text.rstrip()}"
            )
            user_prompt_parts.append(
                "Complete the draft YAML using the normalized source content. "
                "Preserve correct top-level metadata from the draft unless it conflicts with the command flags. "
                "Use any related structured artifact only to keep decomposition and phase boundaries aligned; do not copy its content verbatim. "
                "Replace any `<stub: ...>` placeholders with real content. "
                f"Fill required sections completely: {', '.join(required_sections) or 'summary'}. "
                "Do not move type-specific content to the top level; keep it under `sections:`. "
                "Return the full final YAML document."
            )
        user_prompt = "\n\n".join(user_prompt_parts)

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

        if l2_file.exists() and not force:
            raise click.UsageError(
                f"{l2_file} already exists. Use --force to overwrite only this artifact."
            )

        if body_text is not None and offline_mode:
            # Offline mode: keep passthrough behavior for deterministic scaffold iteration.
            l2_file.write_text(_sanitize_yaml(body_text + "\n"))
        elif offline_mode:
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
            if body_data is not None:
                l2_file.write_text(
                    _merge_body_file_completion(body_data, llm_output, required_sections)
                )
            else:
                l2_file.write_text(_sanitize_yaml(llm_output + "\n"))

        timestamp = now_iso()
        checksum = sha256_file(l2_file)
        topic_entry = require_topic(tracking, topic)
        structured_entries = topic_entry.setdefault("structured", [])
        record = {
            "name": artifact_name,
            "file": f"topics/{topic}/structured/{artifact_name}/{artifact_name}.yaml",
            "created_at": timestamp,
            "checksum": checksum,
            "derived_from": list(source),
            "artifact_type": effective_artifact_type,
        }
        replaced = False
        for idx, entry in enumerate(structured_entries):
            if entry.get("name") == artifact_name:
                structured_entries[idx] = record
                replaced = True
                break
        if not replaced:
            structured_entries.append(record)
        event_desc = (
            f"Re-derived {artifact_name} from {', '.join(source)}"
            if replaced else
            f"Derived {artifact_name} from {', '.join(source)}"
        )
        append_topic_event(tracking, topic, "structured_derived", event_desc)
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
