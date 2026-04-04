"""hi validate — Validate an artifact against its level schema."""

import click
from ruamel.yaml import YAML

from hi.common import (
    load_schema,
    log_error,
    log_warn,
    require_tracking,
    require_topic,
    schemas_dir,
    topic_dir,
)

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


def _get_nested(data: dict, field_path: str):
    """Retrieve a nested field using dot notation (e.g. 'metadata.id')."""
    parts = field_path.split(".")
    val = data
    for part in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val


@click.command()
@click.argument("topic", required=False)
@click.argument("level", required=False)
@click.argument("artifact", required=False)
@click.option("--plan", "plan_path", default=None, type=click.Path(),
              help="Path to a discovery-plan.md to validate (FR-019 checks)")
def validate(topic, level, artifact, plan_path):
    """Validate an artifact against its schema.

    LEVEL: l2 | structured | l3 | computable

    With --plan: validate a discovery-plan.md for structural completeness (FR-019).
    """
    if plan_path:
        _validate_discovery_plan(plan_path)
        return

    if not all([topic, level, artifact]):
        raise click.UsageError(
            "Provide TOPIC LEVEL ARTIFACT arguments, or use --plan <path> for discovery plan validation"
        )
    # Map level to directory and schema
    if level in ("l2", "structured"):
        artifact_subdir = "structured"
        schema_name = "l2-schema.yaml"
    elif level in ("l3", "computable"):
        artifact_subdir = "computable"
        schema_name = "l3-schema.yaml"
    else:
        raise click.UsageError(
            f"Level must be l2/structured or l3/computable (got: {level})"
        )

    td = topic_dir(topic)
    if not td.exists():
        raise click.UsageError(f"Topic '{topic}' not found")

    artifact_file = td / artifact_subdir / f"{artifact}.yaml"
    if not artifact_file.exists():
        raise click.UsageError(f"Artifact not found: {artifact_file}")

    schema_path = schemas_dir() / schema_name
    if not schema_path.exists():
        raise click.UsageError(f"Schema not found: {schema_path}")

    schema = load_schema(schema_name)

    from ruamel.yaml import YAML
    y = YAML()
    with open(artifact_file) as f:
        artifact_data = y.load(f)

    if artifact_data is None:
        artifact_data = {}

    required_fields = schema.get("required_fields", [])
    optional_fields = schema.get("optional_fields", [])

    click.echo(f"Validating {topic}/{level}/{artifact}...")

    errors = 0
    for field in required_fields:
        val = _get_nested(artifact_data, field)
        if val is None or val == "" or (isinstance(val, list) and len(val) == 0):
            log_error(f"  MISSING required field: {field}")
            errors += 1

    warnings = 0
    for field in optional_fields:
        val = _get_nested(artifact_data, field)
        if val is None or val == "":
            log_warn(f"  optional field not set: {field}")
            warnings += 1

    if errors > 0:
        click.echo(f"INVALID — {errors} required field(s) missing")
        raise SystemExit(1)

    if warnings > 0:
        click.echo(f"VALID (with {warnings} optional field warning(s))", err=True)
    click.echo(f"VALID — {artifact_file}")


def _validate_discovery_plan(plan_path: str) -> None:
    """Validate a discovery-plan.md per FR-019 checks. Read-only — no file writes."""
    from pathlib import Path

    path = Path(plan_path)
    if not path.exists():
        click.echo(f"✗ Plan file not found: {plan_path}")
        raise SystemExit(1)

    # Parse YAML frontmatter delimited by ---
    content = path.read_text()
    frontmatter_str = _extract_frontmatter(content)
    if frontmatter_str is None:
        click.echo("✗ No YAML frontmatter found (expected --- delimiters)")
        raise SystemExit(1)

    y = YAML(typ="safe")
    try:
        data = y.load(frontmatter_str)
    except Exception as e:
        click.echo(f"✗ YAML parse error: {e}")
        raise SystemExit(1)

    if not isinstance(data, dict):
        click.echo("✗ Frontmatter parsed but is not a mapping")
        raise SystemExit(1)

    errors = 0
    warnings = 0

    click.echo(f"Validating discovery plan: {plan_path}\n")

    # (a) YAML parses successfully — already done above
    click.echo("✓ Frontmatter parses as valid YAML")

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

    # Summary
    click.echo("")
    if errors > 0:
        click.echo(f"INVALID — {errors} check(s) failed, {warnings} warning(s)")
        raise SystemExit(1)
    elif warnings > 0:
        click.echo(f"VALID — all mandatory checks passed ({warnings} warning(s))")
    else:
        click.echo("VALID — all checks passed")


def _extract_frontmatter(content: str) -> str | None:
    """Extract YAML frontmatter between first pair of --- delimiters."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return None
    return "\n".join(lines[1:end])
