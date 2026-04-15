"""rh-skills list — List all topics in the repository."""

import json

import click

from rh_skills.common import tracking_file


def _compute_stage(sources_count: int, structured_count: int, computable_count: int) -> str:
    if computable_count > 0:
        return "l3-computable"
    if structured_count > 0:
        return "l2-semi-structured"
    if sources_count > 0:
        return "l1-discovery"
    return "initialized"


@click.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON array")
@click.option("--stage", default=None, help="Filter by lifecycle stage")
def list_(as_json, stage):
    """List all topics in the repository."""
    tf = tracking_file()
    if not tf.exists():
        if as_json:
            click.echo("[]")
        else:
            click.echo("No tracking.yaml found")
        return

    from ruamel.yaml import YAML
    y = YAML()
    with open(tf) as f:
        tracking = y.load(f)

    topics = tracking.get("topics", [])
    sources_count = len(tracking.get("sources", []))

    results = []
    for topic in topics:
        structured_count = len(topic.get("structured", []))
        computable_count = len(topic.get("computable", []))
        topic_stage = _compute_stage(sources_count, structured_count, computable_count)

        if stage and topic_stage != stage:
            continue

        results.append({
            "name": topic.get("name", ""),
            "title": topic.get("title", ""),
            "stage": topic_stage,
            "sources": sources_count,
            "structured": structured_count,
            "computable": computable_count,
        })

    if as_json:
        click.echo(json.dumps(results))
        return

    if not results:
        suffix = f" with stage: {stage}" if stage else ""
        click.echo(f"No topics found{suffix}")
        return

    for r in results:
        click.echo(
            f"{r['name']:<30}  {r['stage']:<22} "
            f"L1:{r['sources']:<3} L2:{r['structured']:<3} L3:{r['computable']}"
        )
