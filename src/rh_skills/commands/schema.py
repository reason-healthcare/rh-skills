"""rh-skills schema — Show schemas and valid vocabularies for RH Skills artifacts."""

import json

import click

from rh_skills.commands.validate import VALID_EVIDENCE_LEVELS, VALID_SOURCE_TYPES, VALID_ACCESS_VALUES
from rh_skills.common import load_schema


_DISCOVERY_PLAN_SCHEMA = {
    "artifact": "discovery-plan",
    "description": "discovery-plan.yaml — L1 source evidence plan consumed by rh-inf-ingest",
    "top_level_fields": {
        "topic": "string — topic slug, e.g. diabetes-ccm (required)",
        "sources": "list of source entries (required, 5–25 items)",
    },
    "source_entry_fields": {
        "name": "string — unique kebab-case identifier (required)",
        "type": "string — source type from taxonomy (required, see source_types)",
        "title": "string — human-readable title (required)",
        "url": "string — canonical URL to the source (required when access: open)",
        "rationale": "string — why this source is included (required)",
        "evidence_level": "string — from evidence_levels vocabulary (required)",
        "search_terms": "list of strings — terms used to find this source (required)",
        "access": "string — open | authenticated | manual (optional)",
        "year": "string or int — publication year (optional)",
        "authors": "list of strings (optional)",
        "notes": "string — additional context (optional)",
    },
    "source_types": sorted(VALID_SOURCE_TYPES),
    "evidence_levels": sorted(VALID_EVIDENCE_LEVELS),
    "access_values": sorted(VALID_ACCESS_VALUES),
    "validation_checks": [
        "YAML parses successfully",
        "sources[] count between 5 and 25",
        "at least one 'terminology' type source present",
        "every entry has non-empty rationale",
        "every entry has non-empty search_terms",
        "every evidence_level is from the allowed vocabulary",
        "every type is from the allowed taxonomy (warning if unknown)",
        "access value, if present, is open|authenticated|manual (warning if unknown)",
        "at least one 'health-economics' source (warning if missing)",
    ],
    "validate_command": "rh-skills validate --plan <path>  OR  rh-skills validate --plan -  (stdin)",
}


_SCHEMAS = {
    "discovery-plan": _DISCOVERY_PLAN_SCHEMA,
    "extract-plan": "extract-plan-schema.yaml",
    "l2": "l2-schema.yaml",
    "structured": "l2-schema.yaml",
    "l3": "l3-schema.yaml",
    "computable": "l3-schema.yaml",
}

_ALIASES = {
    "structured": "l2",
    "computable": "l3",
}


@click.group()
def schema():
    """Show schemas and valid vocabularies for RH Skills artifacts."""


@schema.command()
@click.argument("artifact_type", metavar="TYPE")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
def show(artifact_type, as_json):
    """Show schema and valid vocabulary for an artifact type.

    \b
    Types:
      discovery-plan   Fields and vocabulary for discovery-plan.yaml
      extract-plan     Fields and vocabulary for extract-plan.yaml
      l2 / structured  Required/optional fields for L2 structured artifacts
      l3 / computable  Required/optional fields for L3 computable artifacts

    \b
    Examples:
      rh-skills schema show discovery-plan
      rh-skills schema show extract-plan
      rh-skills schema show l2
      rh-skills schema show l3
    """
    key = artifact_type.lower()
    canonical = _ALIASES.get(key, key)

    if canonical not in _SCHEMAS:
        available = "  ".join(sorted(set(_ALIASES) | {"discovery-plan", "extract-plan", "l2", "l3"}))
        raise click.UsageError(
            f"Unknown artifact type: '{artifact_type}'\n"
            f"Available types: {available}"
        )

    schema_ref = _SCHEMAS[canonical]

    if canonical == "discovery-plan":
        data = schema_ref
    elif isinstance(schema_ref, str):
        data = load_schema(schema_ref)
        data["artifact"] = canonical
    else:
        data = schema_ref

    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    _print_schema(canonical, data)


def _print_schema(artifact_type: str, data: dict) -> None:
    if artifact_type == "discovery-plan":
        _print_discovery_plan_schema(data)
    else:
        _print_artifact_schema(artifact_type, data)


def _print_discovery_plan_schema(data: dict) -> None:
    click.echo(f"\n{data['description']}\n")

    click.echo("Top-level fields:")
    for field, desc in data["top_level_fields"].items():
        click.echo(f"  {field:<20} {desc}")

    click.echo("\nSource entry fields:")
    for field, desc in data["source_entry_fields"].items():
        click.echo(f"  {field:<20} {desc}")

    click.echo(f"\nValid source types ({len(data['source_types'])}):")
    cols = _columnize(data["source_types"], width=4)
    for row in cols:
        click.echo("  " + "  ".join(f"{v:<30}" for v in row))

    click.echo(f"\nValid evidence levels ({len(data['evidence_levels'])}):")
    click.echo("  " + "  ".join(data["evidence_levels"]))

    click.echo(f"\nValid access values ({len(data['access_values'])}):")
    click.echo("  " + "  ".join(data["access_values"]))

    click.echo("\nValidation checks:")
    for check in data["validation_checks"]:
        click.echo(f"  • {check}")

    click.echo(f"\nValidate with: {data['validate_command']}")


def _print_artifact_schema(artifact_type: str, data: dict) -> None:
    label = "L2 Structured" if artifact_type == "l2" else "L3 Computable"
    click.echo(f"\n{label} artifact schema (schema_version {data.get('schema_version', '?')})\n")

    required = data.get("required_fields", [])
    optional = data.get("optional_fields", [])
    optional_sections = data.get("optional_sections", {})
    status_values = data.get("status_values", [])

    if required:
        click.echo("Required fields:")
        for f in required:
            click.echo(f"  {f}")

    if optional:
        click.echo("\nOptional fields:")
        for f in optional:
            click.echo(f"  {f}")

    if optional_sections:
        click.echo("\nOptional sections:")
        for section, info in optional_sections.items():
            if isinstance(info, dict):
                fhir = info.get("fhir_equivalent", "")
                desc = info.get("description", "")
                fhir_note = f"  (FHIR: {fhir})" if fhir else ""
                click.echo(f"  {section:<18} {desc}{fhir_note}")
                fields = info.get("fields", [])
                if fields:
                    click.echo(f"    fields: {', '.join(fields)}")
            else:
                click.echo(f"  {section}")

    if status_values:
        click.echo(f"\nValid status values: {', '.join(status_values)}")

    click.echo(f"\nValidate with: rh-skills validate <topic> {artifact_type} <artifact-name>")


def _columnize(items: list, width: int = 4) -> list[list]:
    """Split a flat list into rows of `width` columns."""
    return [items[i:i + width] for i in range(0, len(items), width)]
