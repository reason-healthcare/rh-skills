"""rh-skills formalize — Convert L2 structured artifacts to FHIR R4 JSON."""

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import click
from ruamel.yaml import YAML

from rh_skills.commands.formalize_config import load_formalize_config
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


# ── CQL Content Embedding ─────────────────────────────────────────────────────

def _find_best_cql(cql_files: list[Path], lib_name: str) -> Path | None:
    """Return the CQL file that best matches a Library resource name."""
    if not cql_files:
        return None
    if len(cql_files) == 1:
        return cql_files[0]
    for f in cql_files:
        if f.stem == lib_name:
            return f
    lib_lower = lib_name.lower()
    for f in cql_files:
        if f.stem.lower() == lib_lower:
            return f
    return cql_files[0]


def _embed_cql_in_library(library_path: Path, computable_dir: Path) -> bool:
    """Embed the best-matching CQL file as a base64 content item in a Library JSON.

    Returns True if a CQL file was found and embedded, False otherwise.
    """
    cql_files = sorted(computable_dir.glob("*.cql"))
    if not cql_files:
        return False

    resource = json.loads(library_path.read_text())
    if resource.get("resourceType") != "Library":
        return False

    cql_file = _find_best_cql(cql_files, resource.get("name", ""))
    if cql_file is None:
        return False

    b64 = base64.b64encode(cql_file.read_bytes()).decode("ascii")
    content = [c for c in resource.get("content", []) if c.get("contentType") != "text/cql"]
    content.append({"contentType": "text/cql", "data": b64})
    resource["content"] = content
    library_path.write_text(json.dumps(resource, indent=2) + "\n")
    return True


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


def _build_system_prompt(artifact_type: str, strategy: dict, cfg: dict) -> str:
    """Build a type-specific system prompt for FHIR JSON generation."""
    primary = strategy["primary"]
    supporting = strategy.get("supporting", [])
    all_types = [primary] + supporting
    canonical = cfg["canonical"]
    version = cfg["version"]
    status = cfg["status"]

    return f"""\
You are a healthcare informatics specialist. Your task is to convert a \
semi-structured L2 YAML artifact of type '{artifact_type}' into FHIR R4 JSON resources.

You MUST produce a JSON array of FHIR R4 resources. The primary resource type \
is {primary}. Supporting resource types: {', '.join(supporting) or 'none'}.

Each resource in the array MUST have:
- "resourceType": one of {all_types}
- "id": kebab-case identifier
- "url": canonical URL ({canonical}/<ResourceType>/<id>)
- "version": "{version}"
- "status": "{status}"
- "date": today's date (YYYY-MM-DD)
- "name": PascalCase machine name
- "title": human-readable title

For CQL: If the artifact contains structured logic (decision rules, measure populations), \
generate a companion CQL library with compilable expressions. Use 'library <Name> version "{version}"', \
'using FHIR version "4.0.1"', 'include FHIRHelpers version "4.0.1"', 'context Patient'. \
If logic is too ambiguous, use '// TODO: <reason>' stubs.

For terminology: If MCP tools are unavailable, use "TODO:MCP-UNREACHABLE" as placeholder codes.

Output ONLY the JSON array. No markdown fences, no explanation."""


def _patch_measure_library_references(resources: list[dict]) -> None:
    """Ensure every Measure in the list references its companion Library by canonical URL.

    Called after both stub-build and LLM-parse paths so the field is always populated.
    """
    library_urls = [
        r["url"]
        for r in resources
        if r.get("resourceType") == "Library" and r.get("url")
    ]
    for resource in resources:
        if resource.get("resourceType") != "Measure":
            continue
        existing = resource.get("library") or []
        # Treat null / empty list as missing
        if not existing and library_urls:
            resource["library"] = library_urls


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
    cfg: dict,
) -> list[dict]:
    """Build stub FHIR resources when LLM_PROVIDER=stub."""
    primary = strategy["primary"]
    supporting = strategy.get("supporting", [])
    resource_id = to_kebab_case(artifact_name)
    today = today_date()
    canonical = cfg["canonical"]
    version = cfg["version"]
    status = cfg["status"]

    resources = []

    # Primary resource
    primary_resource: dict = {
        "resourceType": primary,
        "id": resource_id,
        "url": f"{canonical}/{primary}/{resource_id}",
        "version": version,
        "status": status,
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
        # Populate Measure.library with the canonical URL of the companion Library
        if "Library" in supporting:
            lib_id = f"{resource_id}-{to_kebab_case('Library')}"
            primary_resource["library"] = [f"{canonical}/Library/{lib_id}"]
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
            "url": f"{canonical}/{sup_type}/{sup_id}",
            "version": version,
            "status": status,
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

    # Load formalize config — required before generating artifacts
    td = topic_dir(topic)
    cfg = load_formalize_config(td)
    if cfg is None:
        click.echo(
            f"Error: formalize-config.yaml not found for topic '{topic}'.\n"
            f"Run:  rh-skills formalize-config {topic}",
            err=True,
        )
        sys.exit(2)

    # Load L2 YAML content
    l2_file = td / "structured" / f"{artifact}.yaml"
    l2_content = ""
    if l2_file.exists():
        l2_content = l2_file.read_text()

    # Build prompts and invoke LLM
    system_prompt = _build_system_prompt(artifact_type, strategy, cfg)
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
        resources = _build_stub_resources(artifact, artifact_type, strategy, topic, cfg)
    else:
        resources = _parse_llm_response(llm_output)
        if not resources:
            click.echo("Error: Failed to parse LLM response as FHIR JSON", err=True)
            sys.exit(2)

    # Ensure Measure.library references companion Library resources
    _patch_measure_library_references(resources)

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

    # Embed CQL source as base64 content in any Library JSON that was written,
    # then emit a guidance note if no CQL file was found.
    if "Library" in strategy.get("supporting", []) or strategy["primary"] == "Library":
        library_files = [
            computable_dir / Path(f).name
            for f in written_files
            if Path(f).name.startswith("Library-")
        ]
        embedded_any = False
        for lib_path in library_files:
            if lib_path.exists() and _embed_cql_in_library(lib_path, computable_dir):
                cql_used = _find_best_cql(sorted(computable_dir.glob("*.cql")), "")
                click.echo(f"  ✓ Embedded CQL source in {lib_path.name}")
                embedded_any = True
        if not embedded_any:
            cql_name = "".join(w.capitalize() for w in to_kebab_case(artifact).split("-")) + "Logic"
            click.echo(
                f"  ℹ  No .cql file found in computable/ — use `rh-inf-cql` (author mode) to author"
                f" the CQL library, then re-run `rh-skills formalize` to embed it in the Library JSON",
                err=True,
            )

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
