"""hi validate — Validate an artifact against its level schema."""

import click

from hi.common import (
    load_schema,
    log_error,
    log_warn,
    require_tracking,
    require_topic,
    schemas_dir,
    topic_dir,
)


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
@click.argument("topic")
@click.argument("level")
@click.argument("artifact")
def validate(topic, level, artifact):
    """Validate an artifact against its schema.

    LEVEL: l2 | structured | l3 | computable
    """
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
