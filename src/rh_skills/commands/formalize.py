"""rh-skills formalize — Convert L2 structured artifacts to FHIR R4 JSON."""

import hashlib
import json
import re
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
    today_date,
    topic_dir,
)
from rh_skills.fhir.normalize import (
    ALLOWED_RESOURCE_TYPES,
    normalize_resource,
    to_kebab_case,
)
from rh_skills.fhir.validate import validate_resource


# ── Strategy Registry ──────────────────────────────────────────────────────────

STRATEGY_REGISTRY: dict[str, dict] = {
    "evidence-summary": {
        "primary": "Evidence",
        "supporting": ["EvidenceVariable", "Citation"],
        "description": "Evidence + EvidenceVariable + Citation",
    },
    "decision-table": {
        "primary": "PlanDefinition",
        "supporting": ["Library"],
        "description": "PlanDefinition (eca-rule) + Library (CQL)",
    },
    "care-pathway": {
        "primary": "PlanDefinition",
        "supporting": ["ActivityDefinition"],
        "description": "PlanDefinition (clinical-protocol) + ActivityDefinition",
    },
    "terminology": {
        "primary": "ValueSet",
        "supporting": ["ConceptMap"],
        "description": "ValueSet + ConceptMap",
    },
    "measure": {
        "primary": "Measure",
        "supporting": ["Library"],
        "description": "Measure + Library (CQL)",
    },
    "assessment": {
        "primary": "Questionnaire",
        "supporting": [],
        "description": "Questionnaire",
    },
    "policy": {
        "primary": "PlanDefinition",
        "supporting": ["Questionnaire"],
        "description": "PlanDefinition (eca-rule) + Questionnaire (DTR)",
    },
}

GENERIC_STRATEGY = {
    "primary": "PlanDefinition",
    "supporting": [],
    "description": "generic pathway-package (fallback)",
}


def _get_strategy(artifact_type: str) -> tuple[dict, bool]:
    """Return (strategy_dict, is_fallback)."""
    if artifact_type in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[artifact_type], False
    return GENERIC_STRATEGY, True


# ── LLM Integration ───────────────────────────────────────────────────────────

def _invoke_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke LLM or return stub response."""
    provider = config_value("LLM_PROVIDER", "stub")
    if provider == "stub":
        stub = config_value("RH_STUB_RESPONSE", "Stub response")
        return stub
    raise click.ClickException(
        f"LLM provider '{provider}' not available — set LLM_PROVIDER to a supported provider"
    )


def _build_system_prompt(artifact_type: str, strategy: dict) -> str:
    """Build a type-specific system prompt for FHIR JSON generation."""
    primary = strategy["primary"]
    supporting = strategy.get("supporting", [])
    all_types = [primary] + supporting

    return f"""\
You are a healthcare informatics specialist. Your task is to convert a \
semi-structured L2 YAML artifact of type '{artifact_type}' into FHIR R4 JSON resources.

You MUST produce a JSON array of FHIR R4 resources. The primary resource type \
is {primary}. Supporting resource types: {', '.join(supporting) or 'none'}.

Each resource in the array MUST have:
- "resourceType": one of {all_types}
- "id": kebab-case identifier
- "url": canonical URL (http://example.org/fhir/<ResourceType>/<id>)
- "version": "1.0.0"
- "status": "draft"
- "date": today's date (YYYY-MM-DD)
- "name": PascalCase machine name
- "title": human-readable title

For CQL: If the artifact contains structured logic (decision rules, measure populations), \
generate a companion CQL library with compilable expressions. Use 'library <Name> version "1.0.0"', \
'using FHIR version "4.0.1"', 'include FHIRHelpers version "4.0.1"', 'context Patient'. \
If logic is too ambiguous, use '// TODO: <reason>' stubs.

For terminology: If MCP tools are unavailable, use "TODO:MCP-UNREACHABLE" as placeholder codes.

Output ONLY the JSON array. No markdown fences, no explanation."""


def _parse_llm_response(raw: str) -> list[dict]:
    """Parse LLM response into list of FHIR resource dicts.

    Handles:
    - Direct JSON array
    - Markdown-fenced JSON (```json ... ```)
    - Single object (wraps in list)
    """
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, list):
        return [r for r in parsed if isinstance(r, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _build_stub_resources(
    artifact_name: str,
    artifact_type: str,
    strategy: dict,
    topic: str,
) -> list[dict]:
    """Build stub FHIR resources when LLM_PROVIDER=stub."""
    primary = strategy["primary"]
    supporting = strategy.get("supporting", [])
    resource_id = to_kebab_case(artifact_name)
    today = today_date()

    resources = []

    # Primary resource
    primary_resource: dict = {
        "resourceType": primary,
        "id": resource_id,
        "url": f"http://example.org/fhir/{primary}/{resource_id}",
        "version": "1.0.0",
        "status": "draft",
        "date": today,
        "name": "".join(w.capitalize() for w in resource_id.split("-")),
        "title": artifact_name.replace("-", " ").title(),
    }

    # Add type-specific required fields for stubs
    if primary == "PlanDefinition":
        plan_type = "eca-rule" if artifact_type in ("decision-table", "policy") else "clinical-protocol"
        primary_resource["type"] = {"coding": [{"code": plan_type}]}
        primary_resource["action"] = [{"title": "Initial action", "description": "Stub action"}]
    elif primary == "Measure":
        primary_resource["scoring"] = {"coding": [{"code": "proportion"}]}
        primary_resource["group"] = [{
            "population": [
                {"code": {"coding": [{"code": "numerator"}]}, "criteria": {"language": "text/cql", "expression": "Numerator"}},
                {"code": {"coding": [{"code": "denominator"}]}, "criteria": {"language": "text/cql", "expression": "Denominator"}},
            ],
        }]
    elif primary == "Questionnaire":
        primary_resource["item"] = [{"linkId": "q1", "text": "Stub question", "type": "choice"}]
    elif primary == "ValueSet":
        primary_resource["compose"] = {"include": [{"system": "http://snomed.info/sct", "concept": [{"code": "TODO:PLACEHOLDER"}]}]}
    elif primary == "Evidence":
        primary_resource["certainty"] = [{"rating": {"coding": [{"code": "moderate"}]}}]

    resources.append(primary_resource)

    # Supporting resources
    for sup_type in supporting:
        sup_id = f"{resource_id}-{to_kebab_case(sup_type)}"
        sup_resource: dict = {
            "resourceType": sup_type,
            "id": sup_id,
            "url": f"http://example.org/fhir/{sup_type}/{sup_id}",
            "version": "1.0.0",
            "status": "draft",
            "date": today,
            "name": "".join(w.capitalize() for w in sup_id.split("-")),
            "title": f"{artifact_name} {sup_type}".replace("-", " ").title(),
        }
        # Required fields for stubs
        if sup_type == "Library":
            sup_resource["type"] = {"coding": [{"code": "logic-library"}]}
        elif sup_type == "EvidenceVariable":
            sup_resource["characteristic"] = [{"description": "Stub characteristic"}]
        elif sup_type == "ActivityDefinition":
            sup_resource["kind"] = "ServiceRequest"
        elif sup_type == "ConceptMap":
            sup_resource["group"] = [{"source": "http://example.org", "target": "http://example.org", "element": []}]
        elif sup_type == "Questionnaire":
            sup_resource["item"] = [{"linkId": "q1", "text": "Stub DTR question", "type": "choice"}]

        resources.append(sup_resource)

    return resources


# ── Click Command ──────────────────────────────────────────────────────────────

@click.command("formalize")
@click.argument("topic")
@click.argument("artifact")
@click.option("--dry-run", is_flag=True, help="Print strategy selection without writing files")
@click.option("--force", is_flag=True, help="Overwrite existing computable files for this artifact")
def formalize(topic, artifact, dry_run, force):
    """Convert an L2 structured artifact to FHIR R4 JSON resources.

    Reads the L2 artifact, selects a type-specific strategy, generates
    FHIR JSON + CQL via LLM, normalizes, and writes to computable/.
    """
    tracking = require_tracking()
    topic_entry = require_topic(tracking, topic)

    # Validate artifact exists in structured
    structured = topic_entry.get("structured", [])
    artifact_entry = next(
        (a for a in structured if a.get("name") == artifact),
        None,
    )
    if artifact_entry is None:
        raise click.UsageError(
            f"L2 artifact '{artifact}' not found in topic '{topic}'"
        )

    # Read artifact_type from L2 artifact
    artifact_type = artifact_entry.get("artifact_type", "unknown")

    # Select strategy
    strategy, is_fallback = _get_strategy(artifact_type)
    if is_fallback:
        log_warn(
            f"Unknown artifact type '{artifact_type}'; "
            "falling back to generic pathway-package strategy"
        )

    if dry_run:
        click.echo(f"--- DRY RUN: formalize '{artifact}' ---")
        click.echo(f"Strategy: {strategy['description']} ({'fallback' if is_fallback else artifact_type})")
        click.echo(f"Primary: {strategy['primary']}")
        if strategy.get("supporting"):
            click.echo(f"Supporting: {', '.join(strategy['supporting'])}")
        return

    # Load L2 YAML content
    td = topic_dir(topic)
    l2_file = td / "structured" / f"{artifact}.yaml"
    l2_content = ""
    if l2_file.exists():
        l2_content = l2_file.read_text()

    # Build prompts and invoke LLM
    system_prompt = _build_system_prompt(artifact_type, strategy)
    user_prompt = (
        f"Artifact name: {artifact}\n"
        f"Artifact type: {artifact_type}\n"
        f"Topic: {topic}\n"
        f"Date: {today_date()}\n\n"
        f"L2 Content:\n{l2_content}"
    )

    click.echo(f"Formalizing '{artifact}' using {strategy['description']} strategy...")

    llm_output = _invoke_llm(system_prompt, user_prompt)

    # Parse response
    if llm_output == "Stub response":
        resources = _build_stub_resources(artifact, artifact_type, strategy, topic)
    else:
        resources = _parse_llm_response(llm_output)
        if not resources:
            click.echo("Error: Failed to parse LLM response as FHIR JSON", err=True)
            sys.exit(2)

    # Normalize + validate
    computable_dir = td / "computable"
    computable_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    checksums: dict[str, str] = {}
    warnings: list[str] = []
    failures: list[str] = []

    for resource in resources:
        normalize_resource(resource)
        norm_warnings = resource.pop("_normalization_warnings", [])
        warnings.extend(norm_warnings)

        validation_errors = validate_resource(resource)
        if validation_errors:
            for e in validation_errors:
                if "MCP-UNREACHABLE" in e:
                    warnings.append(f"  ⚠ {resource.get('resourceType', '?')}/{resource.get('id', '?')}: {e}")
                else:
                    warnings.append(f"  ⚠ {resource.get('resourceType', '?')}/{resource.get('id', '?')}: {e}")

        rt = resource.get("resourceType", "Unknown")
        rid = resource.get("id", "unknown")
        fname = f"{rt}-{rid}.json"
        fpath = computable_dir / fname

        if fpath.exists() and not force:
            failures.append(f"  ✗ {fname} already exists (use --force to overwrite)")
            continue

        try:
            fpath.write_text(json.dumps(resource, indent=2) + "\n")
            rel_path = f"topics/{topic}/computable/{fname}"
            written_files.append(rel_path)
            checksums[rel_path] = sha256_file(fpath)
            click.echo(f"  ✓ {fname}")
        except OSError as exc:
            failures.append(f"  ✗ {fname}: {exc}")

    # Generate CQL stub if strategy involves Library
    if "Library" in strategy.get("supporting", []) or strategy["primary"] == "Library":
        cql_name = "".join(w.capitalize() for w in to_kebab_case(artifact).split("-")) + "Logic"
        cql_fname = f"{cql_name}.cql"
        cql_path = computable_dir / cql_fname

        if not cql_path.exists() or force:
            cql_content = (
                f'library {cql_name} version \'1.0.0\'\n'
                f'\n'
                f'using FHIR version \'4.0.1\'\n'
                f'include FHIRHelpers version \'4.0.1\'\n'
                f'\n'
                f'context Patient\n'
                f'\n'
                f'// TODO: Add expressions for {artifact}\n'
            )
            cql_path.write_text(cql_content)
            rel_path = f"topics/{topic}/computable/{cql_fname}"
            written_files.append(rel_path)
            checksums[rel_path] = sha256_file(cql_path)
            click.echo(f"  ✓ {cql_fname}")

    # Report warnings
    for w in warnings:
        click.echo(w, err=True)

    # Report failures
    for f in failures:
        click.echo(f, err=True)

    if not written_files:
        click.echo("Error: No files were written", err=True)
        sys.exit(2)

    # Update tracking
    timestamp = now_iso()
    topic_entry.setdefault("computable", []).append({
        "name": artifact,
        "files": written_files,
        "created_at": timestamp,
        "checksums": checksums,
        "converged_from": [artifact],
        "strategy": artifact_type if not is_fallback else "generic",
    })

    resource_count = len(written_files)
    strategy_label = artifact_type if not is_fallback else "generic"
    append_topic_event(
        tracking, topic, "computable_converged",
        f"Formalized '{artifact}' using {strategy_label} strategy → {resource_count} resources",
    )
    save_tracking(tracking)

    click.echo(f"\nWrote {resource_count} files to topics/{topic}/computable/")
    click.echo("Event: computable_converged")

    if failures:
        sys.exit(1)
