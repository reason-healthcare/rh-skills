"""rh-skills validate — Validate an artifact against its level schema."""

from pathlib import Path

import click
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rh_skills.common import (
    load_schema,
    log_error,
    log_warn,
    require_tracking,
    require_topic,
    schemas_dir,
    topic_dir,
)


def _yaml_safe() -> YAML:
    return YAML(typ="safe")

VALID_EVIDENCE_LEVELS = {
    # GRADE letter grades (reference.md primary taxonomy)
    "grade-a", "grade-b", "grade-c", "grade-d",
    # USPSTF grades
    "uspstf-a", "uspstf-b", "uspstf-c", "uspstf-d", "uspstf-i",
    # Study-level Oxford numeric grades
    "ia", "ib", "iia", "iib", "iii", "iv", "v",
    # Other
    "expert-consensus", "reference-standard", "n/a",
}
VALID_SOURCE_TYPES = {
    # Guidelines and standards
    "guideline", "clinical-guideline",
    # Study types
    "systematic-review", "rct", "cohort-study", "case-control",
    "cross-sectional", "case-report", "expert-opinion",
    # Terminology and value sets
    "terminology", "value-set",
    # Measures and programs
    "measure-library", "quality-measure", "government-program",
    # FHIR and interoperability
    "fhir-ig", "cds-library",
    # Social determinants
    "sdoh-assessment",
    # Economics and registries
    "health-economics", "registry",
    # Literature
    "pubmed-article",
    # Catchall
    "textbook", "document", "other",
}
VALID_ACCESS_VALUES = {"open", "authenticated", "manual"}


def _get_nested(data: dict, field_path: str):
    """Retrieve a nested field using dot notation (e.g. 'metadata.id')."""
    parts = field_path.split(".")
    val = data
    for part in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val


def _parse_markdown_frontmatter(path) -> dict:
    raw = path.read_text()
    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        return {}
    data = _yaml_safe().load(parts[1]) or {}
    return data if isinstance(data, dict) else {}


def _normalized_source_to_name(path_str: str) -> str:
    return Path(path_str).stem


def _report_error(message: str, *, emit: bool) -> None:
    if emit:
        log_error(message)


def _report_warn(message: str, *, emit: bool) -> None:
    if emit:
        log_warn(message)


def _collect_stub_paths(value, path: str = "") -> list[str]:
    """Walk nested dicts/lists and return dotted paths of any string containing '<stub:'."""
    stubs = []
    if isinstance(value, str) and "<stub:" in value:
        stubs.append(path)
    elif isinstance(value, dict):
        for k, v in value.items():
            stubs.extend(_collect_stub_paths(v, f"{path}.{k}" if path else k))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            stubs.extend(_collect_stub_paths(item, f"{path}[{i}]"))
    return stubs


def _validate_extract_artifact(
    topic: str,
    artifact: str,
    artifact_data: dict,
    *,
    emit: bool = True,
) -> tuple[int, int]:
    plan_path = topic_dir(topic) / "process" / "plans" / "extract-plan.yaml"
    if not plan_path.exists():
        # fall back to legacy .md format for backward compatibility
        plan_path = topic_dir(topic) / "process" / "plans" / "extract-plan.md"
    if not plan_path.exists():
        return 0, 0

    if plan_path.suffix == ".yaml":
        plan = _yaml_safe().load(plan_path.read_text()) or {}
    else:
        plan = _parse_markdown_frontmatter(plan_path)
    artifacts = plan.get("artifacts", []) or []
    plan_entry = next((entry for entry in artifacts if entry.get("name") == artifact), None)
    if plan_entry is None:
        if any(key in artifact_data for key in ("artifact_type", "clinical_question", "sections", "conflicts")):
            _report_warn("  extract-plan.yaml exists but this artifact is not listed there", emit=emit)
            return 0, 1
        return 0, 0

    errors = 0
    warnings = 0

    if not artifact_data.get("artifact_type"):
        _report_error("  MISSING extract field: artifact_type", emit=emit)
        errors += 1

    if not artifact_data.get("clinical_question"):
        _report_error("  MISSING extract field: clinical_question", emit=emit)
        errors += 1

    sections = artifact_data.get("sections")
    if not isinstance(sections, dict) or not sections:
        _report_error("  MISSING extract field: sections", emit=emit)
        return errors + 1, warnings

    expected_sources = {
        _normalized_source_to_name(path)
        for path in plan_entry.get("source_files", []) or []
    }
    actual_sources = set(artifact_data.get("derived_from") or [])
    if expected_sources and expected_sources != actual_sources:
        _report_error(
            "  derived_from does not match approved plan sources: "
            f"expected {sorted(expected_sources)}, got {sorted(actual_sources)}",
            emit=emit,
        )
        errors += 1

    for section_name in plan_entry.get("required_sections", []) or []:
        if section_name not in sections:
            _report_error(f"  MISSING required extract section: sections.{section_name}", emit=emit)
            errors += 1

    if "evidence_traceability" in (plan_entry.get("required_sections", []) or []):
        refs = sections.get("evidence_traceability") or []
        if not isinstance(refs, list) or not refs:
            _report_error("  MISSING evidence traceability entries", emit=emit)
            errors += 1
        else:
            for idx, entry in enumerate(refs, start=1):
                if not isinstance(entry, dict):
                    _report_error(f"  INVALID evidence traceability entry #{idx}", emit=emit)
                    errors += 1
                    continue
                if not entry.get("claim_id") or not entry.get("statement"):
                    _report_error(
                        f"  MISSING claim_id or statement in evidence traceability entry #{idx}",
                        emit=emit,
                    )
                    errors += 1
                evidence = entry.get("evidence") or []
                if not isinstance(evidence, list) or not evidence:
                    _report_error(
                        f"  MISSING evidence list in evidence traceability entry #{idx}",
                        emit=emit,
                    )
                    errors += 1
                else:
                    for ev in evidence:
                        if not ev.get("source") or not ev.get("locator"):
                            _report_error(
                                f"  MISSING source or locator in evidence traceability entry #{idx}",
                                emit=emit,
                            )
                            errors += 1

    plan_conflicts = plan_entry.get("conflicts", []) or []
    conflicts = artifact_data.get("conflicts") or []
    if plan_conflicts and not conflicts:
        _report_error("  MISSING conflicts[] despite conflicts listed in approved plan", emit=emit)
        errors += 1
    elif conflicts and not isinstance(conflicts, list):
        _report_error("  conflicts must be a list", emit=emit)
        errors += 1

    stub_paths = _collect_stub_paths(sections, path="sections")
    for stub_path in stub_paths:
        _report_error(
            f"  UNRESOLVED stub value at {stub_path} — re-derive with RH_STUB_RESPONSE containing real content",
            emit=emit,
        )
        errors += 1

    return errors, warnings


def _is_non_empty_list(value) -> bool:
    return isinstance(value, list) and len(value) > 0


def _validate_required_section_completeness(
    section_name: str,
    section_value,
    *,
    emit: bool,
) -> int:
    errors = 0

    if section_name == "pathways":
        if not _is_non_empty_list(section_value):
            _report_error("  MISSING required formalize section content: pathways", emit=emit)
            return 1
        if not any(_is_non_empty_list(pathway.get("steps")) for pathway in section_value if isinstance(pathway, dict)):
            _report_error("  INCOMPLETE formalize section: pathways require at least one pathway with steps", emit=emit)
            errors += 1
    elif section_name == "actions":
        if not _is_non_empty_list(section_value):
            _report_error("  MISSING required formalize section content: actions", emit=emit)
            return 1
        if not any(
            isinstance(action, dict)
            and action.get("intent")
            and (action.get("description") or _is_non_empty_list(action.get("conditions")))
            for action in section_value
        ):
            _report_error(
                "  INCOMPLETE formalize section: actions require intent and description or conditions",
                emit=emit,
            )
            errors += 1
    elif section_name == "value_sets":
        if not _is_non_empty_list(section_value):
            _report_error("  MISSING required formalize section content: value_sets", emit=emit)
            return 1
        if not any(_is_non_empty_list(value_set.get("codes")) for value_set in section_value if isinstance(value_set, dict)):
            _report_error("  INCOMPLETE formalize section: value_sets require coded entries", emit=emit)
            errors += 1
    elif section_name == "measures":
        if not _is_non_empty_list(section_value):
            _report_error("  MISSING required formalize section content: measures", emit=emit)
            return 1
        if not any(
            isinstance(measure, dict) and measure.get("numerator") and measure.get("denominator")
            for measure in section_value
        ):
            _report_error(
                "  INCOMPLETE formalize section: measures require numerator and denominator",
                emit=emit,
            )
            errors += 1
    elif section_name == "libraries":
        if not _is_non_empty_list(section_value):
            _report_error("  MISSING required formalize section content: libraries", emit=emit)
            return 1
        if not any(
            isinstance(library, dict) and library.get("language") and library.get("content")
            for library in section_value
        ):
            _report_error(
                "  INCOMPLETE formalize section: libraries require language and content",
                emit=emit,
            )
            errors += 1
    elif section_name == "assessments":
        if not _is_non_empty_list(section_value):
            _report_error("  MISSING required formalize section content: assessments", emit=emit)
            return 1
        if not any(_is_non_empty_list(assessment.get("items")) for assessment in section_value if isinstance(assessment, dict)):
            _report_error("  INCOMPLETE formalize section: assessments require items", emit=emit)
            errors += 1

    return errors


def _validate_formalize_artifact(
    topic: str,
    artifact: str,
    artifact_data: dict,
    *,
    emit: bool = True,
) -> tuple[int, int]:
    plan_path = topic_dir(topic) / "process" / "plans" / "formalize-plan.md"
    if not plan_path.exists():
        return 0, 0

    plan = _parse_markdown_frontmatter(plan_path)
    if plan.get("status") != "approved":
        return 0, 0

    artifacts = plan.get("artifacts", []) or []
    target_entry = next(
        (
            entry for entry in artifacts
            if entry.get("name") == artifact and entry.get("implementation_target") is True
        ),
        None,
    )
    if target_entry is None:
        if artifact_data.get("converged_from"):
            _report_warn(
                "  formalize-plan.md exists but this artifact is not the approved implementation target",
                emit=emit,
            )
            return 0, 1
        return 0, 0

    errors = 0
    warnings = 0

    if target_entry.get("reviewer_decision") != "approved":
        _report_error(
            "  formalize-plan.md target is not approved for implementation",
            emit=emit,
        )
        errors += 1

    expected_inputs = target_entry.get("input_artifacts", []) or []
    actual_inputs = artifact_data.get("converged_from") or []
    if not actual_inputs:
        _report_error("  MISSING formalize field: converged_from", emit=emit)
        errors += 1
    elif expected_inputs != actual_inputs:
        _report_error(
            "  converged_from does not match approved formalize plan inputs: "
            f"expected {expected_inputs}, got {actual_inputs}",
            emit=emit,
        )
        errors += 1

    # Strategy match check
    plan_strategy = target_entry.get("strategy", "")
    actual_strategy = artifact_data.get("strategy", "")
    if plan_strategy and actual_strategy and plan_strategy != actual_strategy:
        _report_error(
            f"  strategy mismatch: plan says '{plan_strategy}', tracking says '{actual_strategy}'",
            emit=emit,
        )
        errors += 1

    for section_name in target_entry.get("required_sections", []) or []:
        if section_name not in artifact_data:
            _report_error(f"  MISSING required formalize section: {section_name}", emit=emit)
            errors += 1
            continue
        errors += _validate_required_section_completeness(
            section_name,
            artifact_data.get(section_name),
            emit=emit,
        )

    # L3 FHIR JSON file validation
    fhir_errors, fhir_warnings = _validate_fhir_json_files(
        topic, artifact, target_entry, emit=emit,
    )
    errors += fhir_errors
    warnings += fhir_warnings

    return errors, warnings


def _validate_fhir_json_files(
    topic: str,
    artifact: str,
    target_entry: dict,
    *,
    emit: bool = True,
) -> tuple[int, int]:
    """Validate FHIR JSON files in computable/ against per-resource-type rules."""
    import json as _json
    from rh_skills.fhir.validate import validate_resource

    errors = 0
    warnings = 0

    computable_dir = topic_dir(topic) / "computable"
    if not computable_dir.exists():
        return 0, 0

    # Check that all l3_targets have at least one generated file
    l3_targets = target_entry.get("l3_targets", []) or []
    json_files = list(computable_dir.glob("*.json"))

    if not json_files:
        if l3_targets:
            _report_error(
                f"  No FHIR JSON files found in computable/ but plan expects: {l3_targets}",
                emit=emit,
            )
            errors += 1
        return errors, warnings

    # Map resourceType from filenames to check l3_targets coverage
    found_types: set[str] = set()
    for json_file in json_files:
        try:
            resource = _json.loads(json_file.read_text())
        except (ValueError, OSError):
            _report_error(f"  Cannot parse FHIR JSON: {json_file.name}", emit=emit)
            errors += 1
            continue

        rt = resource.get("resourceType", "")
        found_types.add(rt)

        # Run structural validation
        resource_errors = validate_resource(resource)
        for err in resource_errors:
            _report_error(f"  {json_file.name}: {err}", emit=emit)
            errors += 1

    # Check l3_targets coverage (strip qualifiers like "(eca-rule)")
    for target in l3_targets:
        base_type = target.split("(")[0].strip().split(" ")[0]
        if base_type not in found_types:
            _report_warn(
                f"  L3 target '{target}' has no generated file in computable/",
                emit=emit,
            )
            warnings += 1

    return errors, warnings


def _validate_l3_fhir_json(
    topic: str,
    artifact: str,
    *,
    emit: bool = True,
) -> tuple[int, int]:
    """Validate FHIR JSON files in computable/ that match the artifact name.

    Searches computable/ for *.json files whose stem contains the artifact
    name (e.g. ``Questionnaire-phq9-instrument.json`` matches
    ``phq9-instrument``). Falls back to all *.json files if none match.
    Runs validate_resource() on each found file.
    """
    import json as _json
    from rh_skills.fhir.validate import validate_resource

    td = topic_dir(topic)
    if not td.exists():
        raise click.UsageError(f"Topic '{topic}' not found")

    computable_dir = td / "computable"
    if not computable_dir.exists():
        raise click.UsageError(
            f"No computable/ directory found for topic '{topic}'. "
            "Run 'rh-skills formalize' to generate FHIR resources first."
        )

    all_json = sorted(computable_dir.glob("*.json"))
    if not all_json:
        raise click.UsageError(
            f"No FHIR JSON files found in {computable_dir}. "
            "Run 'rh-skills formalize' to generate FHIR resources first."
        )

    # Filter to files whose stem contains the artifact name.
    matching = [f for f in all_json if artifact.lower() in f.stem.lower()]
    if not matching:
        _report_warn(
            f"  No JSON files matching '{artifact}' in computable/ — validating all {len(all_json)} file(s)",
            emit=emit,
        )
        matching = all_json

    errors = 0
    warnings = 0
    for json_file in matching:
        try:
            resource = _json.loads(json_file.read_text())
        except (ValueError, OSError) as exc:
            _report_error(f"  Cannot parse FHIR JSON {json_file.name}: {exc}", emit=emit)
            errors += 1
            continue

        resource_errors = validate_resource(resource)
        for err in resource_errors:
            _report_error(f"  {json_file.name}: {err}", emit=emit)
            errors += 1

    return errors, warnings


def validate_artifact_file(
    topic: str,
    level: str,
    artifact: str,
    *,
    emit: bool = True,
) -> tuple[int, int]:
    if level in ("l2", "structured"):
        td = topic_dir(topic)
        if not td.exists():
            raise click.UsageError(f"Topic '{topic}' not found")

        artifact_file = td / "structured" / artifact / f"{artifact}.yaml"
        if not artifact_file.exists():
            raise click.UsageError(f"Artifact not found: {artifact_file}")

        schema_path = schemas_dir() / "l2-schema.yaml"
        if not schema_path.exists():
            raise click.UsageError(f"Schema not found: {schema_path}")

        schema = load_schema("l2-schema.yaml")

        y = YAML()
        try:
            with open(artifact_file) as f:
                artifact_data = y.load(f)
        except YAMLError as exc:
            _report_error(
                f"  YAML parse error in {artifact_file.name}: {exc}\n"
                "  Hint: values starting with '>' or '<' must be quoted. "
                "Example: threshold: \">=190 mg/dL\" (not: threshold: >=190 mg/dL)",
                emit=emit,
            )
            return 1, 0

        if artifact_data is None:
            artifact_data = {}

        required_fields = schema.get("required_fields", [])
        optional_fields = schema.get("optional_fields", [])

        errors = 0
        for field in required_fields:
            val = _get_nested(artifact_data, field)
            if val is None or val == "" or (isinstance(val, list) and len(val) == 0):
                _report_error(f"  MISSING required field: {field}", emit=emit)
                errors += 1

        warnings = 0
        for field in optional_fields:
            val = _get_nested(artifact_data, field)
            if val is None or val == "":
                _report_warn(f"  optional field not set: {field}", emit=emit)
                warnings += 1

        if errors > 0:
            return errors, warnings

        extract_errors, extract_warnings = _validate_extract_artifact(
            topic, artifact, artifact_data, emit=emit,
        )
        errors += extract_errors
        warnings += extract_warnings
        return errors, warnings

    elif level in ("l3", "computable"):
        return _validate_l3_fhir_json(topic, artifact, emit=emit)

    else:
        raise click.UsageError(
            f"Level must be l2/structured or l3/computable (got: {level})"
        )


@click.command()
@click.argument("topic", required=False)
@click.argument("level", required=False)
@click.argument("artifact", required=False)
@click.option("--plan", "plan_path", default=None, type=click.Path(allow_dash=True),
              help="Path to a discovery-plan.yaml to validate, or - to read from stdin (FR-019 checks)")
@click.option("--check-urls", is_flag=True, default=False,
              help="HTTP-check every source URL in the plan and report broken links (requires network)")
def validate(topic, level, artifact, plan_path, check_urls):
    """Validate an artifact against its schema.

    LEVEL: l2 | structured | l3 | computable

    With --plan: validate a discovery-plan.yaml for structural completeness (FR-019).
    Pass - as the path to read the plan from stdin:

    \b
      cat discovery-plan.yaml | rh-skills validate --plan -
      rh-skills validate --plan - < discovery-plan.yaml
    """
    if plan_path:
        _validate_discovery_plan(plan_path, check_urls=check_urls)
        return

    if topic and level and artifact is None and level not in ("l2", "structured", "l3", "computable"):
        artifact = level
        level = "l2"

    if not all([topic, level, artifact]):
        raise click.UsageError(
            "Provide TOPIC LEVEL ARTIFACT arguments, or use --plan <path> for discovery plan validation"
        )
    click.echo(f"Validating {topic}/{level}/{artifact}...")
    errors, warnings = validate_artifact_file(topic, level, artifact, emit=True)
    if level in ("l2", "structured"):
        artifact_display = topic_dir(topic) / "structured" / artifact / f"{artifact}.yaml"
    else:
        artifact_display = topic_dir(topic) / "computable" / f"*{artifact}*.json"
    if errors > 0:
        click.echo(f"INVALID — {errors} required field(s) missing")
        raise SystemExit(1)
    if warnings > 0:
        click.echo(f"VALID (with {warnings} optional field warning(s)) — {artifact_display}")
    else:
        click.echo(f"VALID — {artifact_display}")


def _validate_discovery_plan(plan_path: str, *, check_urls: bool = False) -> None:
    """Validate a discovery-plan.yaml per FR-019 checks. Read-only — no file writes."""
    import sys
    from pathlib import Path

    if plan_path == "-":
        label = "<stdin>"
        try:
            raw = sys.stdin.read()
        except Exception as e:
            click.echo(f"✗ Failed to read stdin: {e}")
            raise SystemExit(1)
    else:
        path = Path(plan_path)
        label = str(plan_path)
        if not path.exists():
            click.echo(f"✗ Plan file not found: {plan_path}")
            raise SystemExit(1)
        raw = path.read_text()

    y = YAML(typ="safe")
    try:
        data = y.load(raw)
    except Exception as e:
        click.echo(f"✗ YAML parse error: {e}")
        raise SystemExit(1)

    if not isinstance(data, dict):
        click.echo("✗ File parsed but is not a YAML mapping")
        raise SystemExit(1)

    errors = 0
    warnings = 0

    click.echo(f"Validating discovery plan: {label}\n")

    # (a) YAML parses successfully — already done above
    click.echo("✓ Parses as valid YAML")

    # (b) sources[] count 5–25
    sources = data.get("sources", []) or []
    count = len(sources)
    if count < 5:
        click.echo(f"✗ Source count too low: {count} (minimum 5)")
        errors += 1
    elif count > 25:
        click.echo(f"✗ Source count too high: {count} (maximum 25)")
        errors += 1
    else:
        click.echo(f"✓ Source count: {count} (within 5–25 range)")

    # (c) At least one terminology source
    has_terminology = any(s.get("type") == "terminology" for s in sources)
    if not has_terminology:
        click.echo("✗ No terminology source (SNOMED/LOINC/ICD/RxNorm) — required for L3 computable output")
        errors += 1
    else:
        click.echo("✓ Terminology source present")

    # (d) Every entry has non-empty rationale
    missing_rationale = [s.get("name", f"[index {i}]") for i, s in enumerate(sources)
                         if not s.get("rationale")]
    if missing_rationale:
        for name in missing_rationale:
            click.echo(f"✗ Missing rationale: {name}")
        errors += len(missing_rationale)
    else:
        click.echo("✓ All entries have rationale")

    # (e) Every entry has non-empty search_terms[]
    missing_search_terms = [s.get("name", f"[index {i}]") for i, s in enumerate(sources)
                            if not s.get("search_terms")]
    if missing_search_terms:
        for name in missing_search_terms:
            click.echo(f"✗ Missing search_terms: {name}")
        errors += len(missing_search_terms)
    else:
        click.echo("✓ All entries have search_terms")

    # (f) Every evidence_level is from the allowed set
    invalid_levels = [(s.get("name", f"[index {i}]"), s.get("evidence_level"))
                      for i, s in enumerate(sources)
                      if s.get("evidence_level") not in VALID_EVIDENCE_LEVELS]
    if invalid_levels:
        for name, level in invalid_levels:
            click.echo(f"✗ Invalid evidence_level '{level}' on: {name}")
        errors += len(invalid_levels)
    else:
        click.echo("✓ All evidence levels are valid")

    # (g) Every type is from the allowed set (warning only for unknown types)
    unknown_types = [(s.get("name", f"[index {i}]"), s.get("type"))
                     for i, s in enumerate(sources)
                     if s.get("type") not in VALID_SOURCE_TYPES]
    if unknown_types:
        for name, stype in unknown_types:
            click.echo(f"⚠ Unknown source type '{stype}' on: {name} (not in taxonomy — review)")
        warnings += len(unknown_types)
    else:
        click.echo("✓ All source types are from the taxonomy")

    # (h) health-economics source — warning only
    has_health_econ = any(s.get("type") == "health-economics" for s in sources)
    if not has_health_econ:
        click.echo(
            "⚠ No health-economics source found — recommended for chronic conditions "
            "and preventive interventions"
        )
        warnings += 1

    # (i-access) access values — warning only for invalid values when present
    invalid_access = [(s.get("name", f"[index {i}]"), s.get("access"))
                      for i, s in enumerate(sources)
                      if s.get("access") and s.get("access") not in VALID_ACCESS_VALUES]
    if invalid_access:
        for name, acc in invalid_access:
            click.echo(
                f"⚠ Unknown access value '{acc}' on: {name} "
                f"(expected: open | authenticated | manual)"
            )
        warnings += len(invalid_access)

    # (i) Optional URL checking
    if check_urls:
        url_errors, url_warnings = _check_plan_urls(sources)
        errors += url_errors
        warnings += url_warnings

    # Summary
    click.echo("")
    if errors > 0:
        click.echo(f"INVALID — {errors} check(s) failed, {warnings} warning(s)")
        raise SystemExit(1)
    elif warnings > 0:
        click.echo(f"VALID — all mandatory checks passed ({warnings} warning(s))")
    else:
        click.echo("VALID — all checks passed")


def _check_plan_urls(sources: list) -> tuple[int, int]:
    """HTTP-check every url field in the source list. Returns (errors, warnings)."""
    try:
        import httpx
    except ImportError:
        click.echo("⚠ httpx not available — skipping URL checks")
        return 0, 1

    errors = 0
    warnings = 0
    click.echo("\nChecking source URLs…")
    for s in sources:
        url = s.get("url") or s.get("access_url")
        name = s.get("name", url or "[unnamed]")
        if not url:
            click.echo(f"  ⚠ No URL: {name}")
            warnings += 1
            continue
        try:
            r = httpx.head(url, timeout=10, follow_redirects=True)
            if r.status_code == 405:
                # HEAD not allowed — fall back to GET with streaming
                r = httpx.get(url, timeout=10, follow_redirects=True)
            if r.status_code >= 400:
                click.echo(f"  ✗ HTTP {r.status_code}: {name}  {url}")
                errors += 1
            else:
                click.echo(f"  ✓ {r.status_code}: {name}")
        except Exception as e:
            click.echo(f"  ✗ Network error ({e}): {name}  {url}")
            errors += 1
    return errors, warnings
