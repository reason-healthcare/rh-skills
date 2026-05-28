"""
derive.py - Auto-derive artifacts from existing L2 structured artifacts

Currently supports:
- Care pathway derivation from decision tables with pathway_phases metadata
"""

import click
from pathlib import Path
from ruamel.yaml import YAML
from typing import Dict, List, Any
from datetime import datetime

yaml = YAML()
yaml.preserve_quotes = True
yaml.default_flow_style = False
yaml.width = 4096


@click.group()
def derive():
    """Auto-derive artifacts from structured artifacts."""
    pass


@derive.command("pathway")
@click.option(
    "--from-decision-table",
    required=True,
    help="Decision table artifact ID (e.g., crs-surgical-management)",
)
@click.option(
    "--pathway-id",
    help="ID for generated pathway (default: <decision-table-id>-pathway)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing pathway if present",
)
def derive_pathway(from_decision_table: str, pathway_id: str, force: bool):
    """
    Auto-generate care pathway from decision table with pathway_phases metadata.
    
    Reads pathway_phases and events from the source decision table and generates
    a care-pathway artifact with phases and substeps.
    
    Example:
        rh-skills derive pathway --from-decision-table crs-surgical-management
    """
    
    # Find decision table file
    topics_dir = Path("topics")
    if not topics_dir.exists():
        click.echo("Error: topics/ directory not found. Run from repository root.", err=True)
        return 1
    
    # Search for decision table
    dt_path = None
    topic_dir = None
    for topic in topics_dir.iterdir():
        if not topic.is_dir():
            continue
        structured_dir = topic / "structured"
        if not structured_dir.exists():
            continue
        
        # Check for decision table directory
        dt_dir = structured_dir / from_decision_table
        dt_file = dt_dir / f"{from_decision_table}.yaml"
        if dt_file.exists():
            dt_path = dt_file
            topic_dir = topic
            break
    
    if not dt_path:
        click.echo(f"Error: Decision table '{from_decision_table}' not found in topics/*/structured/", err=True)
        return 1
    
    # Load decision table
    click.echo(f"Loading decision table: {dt_path}")
    with open(dt_path) as f:
        dt_data = yaml.load(f)
    
    # Validate decision table has pathway_phases
    if "sections" not in dt_data:
        click.echo("Error: Decision table missing 'sections' field", err=True)
        return 1
    
    sections = dt_data["sections"]
    if "pathway_phases" not in sections:
        click.echo(
            f"Error: Decision table '{from_decision_table}' lacks pathway_phases metadata.\n"
            "Only decision tables with temporal workflow structure can auto-generate pathways.\n"
            "For diagnostic, screening, or treatment optimization guidelines, manually author the pathway.",
            err=True
        )
        return 1
    
    pathway_phases = sections["pathway_phases"]
    
    if not pathway_phases or len(pathway_phases) == 0:
        click.echo("Error: pathway_phases is empty", err=True)
        return 1
    
    # Extract events
    if "events" not in sections:
        click.echo("Error: Decision table missing 'events' section", err=True)
        return 1
    
    events = sections["events"]
    
    # Group events by phase
    events_by_phase = {}
    for event in events:
        phase_id = event.get("phase")
        if not phase_id:
            click.echo(f"Warning: Event '{event.get('id')}' has no phase field, skipping", err=True)
            continue
        
        if phase_id not in events_by_phase:
            events_by_phase[phase_id] = []
        
        events_by_phase[phase_id].append(event)
    
    # Sort events within each phase by phase_order
    for phase_id in events_by_phase:
        events_by_phase[phase_id].sort(key=lambda e: e.get("phase_order", 999))
    
    # Generate pathway ID
    if not pathway_id:
        pathway_id = f"{from_decision_table}-pathway"
    
    # Check if pathway already exists
    pathway_dir = topic_dir / "structured" / pathway_id
    pathway_file = pathway_dir / f"{pathway_id}.yaml"
    
    if pathway_file.exists() and not force:
        click.echo(
            f"Error: Pathway '{pathway_id}' already exists at {pathway_file}\n"
            f"Use --force to overwrite",
            err=True
        )
        return 1
    
    # Build pathway data
    pathway_data = {
        "id": pathway_id,
        "name": pathway_id,
        "title": f"Pathway For {dt_data.get('title', from_decision_table)}",
        "version": "0.1.0",
        "status": "draft",
        "domain": dt_data.get("domain", "clinical"),
        "description": (
            f"Auto-generated care pathway from {from_decision_table} decision table.\n"
            f"Organizes clinical decision points into workflow phases.\n"
            f"\n"
            f"NOTE: This artifact is auto-generated. Do not edit manually.\n"
            f"Regenerate using: rh-skills derive pathway --from-decision-table {from_decision_table} --force"
        ),
        "derived_from": [from_decision_table],
        "artifact_type": "care-pathway",
        "clinical_question": f"How should the {dt_data.get('domain', 'clinical')} workflow be organized across care phases?",
        "fhir_mapping": {
            "profile": "http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-pathwaydefinition",
            "plan_definition_type": "clinical-protocol",
            "library": from_decision_table,
            "subject": "Patient",
            "auto_generated": True,
            "source_artifact": from_decision_table,
            "generation_timestamp": datetime.utcnow().isoformat() + "Z",
        },
        "sections": {
            "summary": (
                f"This pathway organizes the {dt_data.get('domain', 'clinical')} care continuum "
                f"into {len(pathway_phases)} clinical phases. Each phase contains decision points "
                f"and activities derived from the {from_decision_table} decision table."
            ),
            "evidence_traceability": dt_data.get("sections", {}).get("evidence_traceability", {}),
        }
    }
    
    # Build steps from phases
    steps = []
    for phase_idx, phase in enumerate(pathway_phases, start=1):
        phase_id = phase["id"]
        phase_events = events_by_phase.get(phase_id, [])
        
        # Build substeps from events
        substeps = []
        for event_idx, event in enumerate(phase_events, start=1):
            substeps.append({
                "substep": f"{phase_idx}.{event_idx}",
                "description": event.get("label", event.get("description", event["id"])),
                "event_id": event["id"],
                "fhir_plan_definition_id": event.get("fhir_plan_definition_id"),
            })
        
        steps.append({
            "step": phase_idx,
            "id": phase_id,
            "code": phase.get("label", phase_id),
            "description": phase.get("description", ""),
            "order": phase.get("order", phase_idx),
            "actor": "Clinician",
            "next": phase_idx + 1 if phase_idx < len(pathway_phases) else None,
            "substeps": substeps,
        })
    
    pathway_data["sections"]["steps"] = steps
    
    # Create pathway directory and write file
    pathway_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"Writing pathway: {pathway_file}")
    with open(pathway_file, "w") as f:
        yaml.dump(pathway_data, f)
    
    click.echo(f"✓ Care pathway '{pathway_id}' generated successfully")
    click.echo(f"  Source: {from_decision_table}")
    click.echo(f"  Phases: {len(pathway_phases)}")
    click.echo(f"  Events: {sum(len(events_by_phase.get(p['id'], [])) for p in pathway_phases)}")
    click.echo(f"  Location: {pathway_file}")
    
    return 0
