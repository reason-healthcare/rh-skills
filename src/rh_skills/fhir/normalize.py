"""Post-LLM normalization for FHIR R4 resources.

Fixes mechanical/structural aspects that LLMs frequently get wrong:
ids, canonical URLs, date formats, version strings, status values,
and resourceType correctness.  Does NOT rewrite clinical content.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# FHIR R4 resource types that formalization may produce.
ALLOWED_RESOURCE_TYPES = frozenset({
    "Evidence",
    "EvidenceVariable",
    "Citation",
    "PlanDefinition",
    "Library",
    "ActivityDefinition",
    "ValueSet",
    "ConceptMap",
    "Measure",
    "Questionnaire",
    "QuestionnaireResponse",
    "ImplementationGuide",
})

_KEBAB_RE = re.compile(r"[^a-z0-9]+")


def to_kebab_case(text: str) -> str:
    """Convert arbitrary text to kebab-case id."""
    return _KEBAB_RE.sub("-", text.lower()).strip("-")


def to_pascal_case(text: str) -> str:
    """Convert kebab-case or space-separated text to PascalCase."""
    return "".join(word.capitalize() for word in re.split(r"[-_ ]+", text) if word)


def canonical_url(resource_type: str, resource_id: str) -> str:
    """Return the canonical URL for a FHIR resource."""
    return f"http://example.org/fhir/{resource_type}/{resource_id}"


def iso_date_today() -> str:
    """Return today's date as ISO 8601 date string (YYYY-MM-DD)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize_resource(resource: dict) -> dict:
    """Normalize a single FHIR resource dict in-place and return it.

    Fixes:
    - ``id``: kebab-case
    - ``url``: canonical URL pattern
    - ``version``: defaults to ``1.0.0``
    - ``status``: defaults to ``draft``
    - ``date``: defaults to today (ISO 8601)
    - ``resourceType``: validated against allowed set
    - ``name``: PascalCase machine-friendly name (if title present)
    """
    rt = resource.get("resourceType", "")
    if rt not in ALLOWED_RESOURCE_TYPES:
        resource.setdefault("_normalization_warnings", []).append(
            f"Unknown resourceType '{rt}'; not in allowed set"
        )

    # id — kebab-case
    raw_id = resource.get("id", "")
    if raw_id:
        resource["id"] = to_kebab_case(raw_id)

    # url — canonical pattern
    if resource.get("id") and rt:
        expected_url = canonical_url(rt, resource["id"])
        if not resource.get("url"):
            resource["url"] = expected_url

    # version
    resource.setdefault("version", "1.0.0")

    # status
    resource.setdefault("status", "draft")

    # date
    if not resource.get("date"):
        resource["date"] = iso_date_today()

    # name — PascalCase from id or title
    if not resource.get("name"):
        source = resource.get("title") or resource.get("id") or ""
        if source:
            resource["name"] = to_pascal_case(source)

    return resource
