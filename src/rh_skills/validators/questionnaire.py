"""Validation and FHIR mapping helpers for authored Questionnaire metadata."""

from __future__ import annotations

from typing import Any


SDC_OBSERVATION_EXTRACTION_PROFILE = (
    "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-extr-obsn"
)
SDC_OBSERVATION_EXTRACTION_EXTENSION = (
    "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-observationExtract"
)
SDC_OBSERVATION_CATEGORY_EXTENSION = (
    "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-observation-extract-category"
)
ARTIFACT_VERSION_ALGORITHM_EXTENSION = (
    "http://hl7.org/fhir/StructureDefinition/artifact-versionAlgorithm"
)


def normalize_observation_extraction(instrument: Any) -> dict[str, Any] | None:
    """Validate and normalize the explicitly authored SDC extraction contract.

    The L2 input intentionally models only the supported profile, enable flag,
    and category Coding. It does not accept arbitrary FHIR extensions or raw
    Questionnaire JSON passthrough.
    """
    if not isinstance(instrument, dict) or "observation_extraction" not in instrument:
        return None

    config = instrument["observation_extraction"]
    if not isinstance(config, dict):
        raise ValueError("Assessment instrument observation_extraction must be an object")

    unknown = set(config) - {"profile", "enabled", "category"}
    if unknown:
        raise ValueError(
            "Assessment instrument observation_extraction has unsupported field(s): "
            + ", ".join(sorted(unknown))
        )

    profile = config.get("profile")
    if not isinstance(profile, str) or "|" not in profile:
        raise ValueError(
            "Assessment instrument observation_extraction.profile must be the SDC profile canonical|version"
        )
    profile_url, profile_version = profile.rsplit("|", 1)
    if profile_url != SDC_OBSERVATION_EXTRACTION_PROFILE or not profile_version.strip():
        raise ValueError(
            "Assessment instrument observation_extraction.profile must use the SDC observation extraction profile canonical|version"
        )

    enabled = config.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("Assessment instrument observation_extraction.enabled must be a Boolean")

    category = config.get("category")
    if enabled and not isinstance(category, dict):
        raise ValueError(
            "Assessment instrument observation_extraction.category is required when extraction is enabled"
        )
    if category is not None:
        if not isinstance(category, dict):
            raise ValueError("Assessment instrument observation_extraction.category must be an object")
        unknown_category_fields = set(category) - {"system", "code", "display"}
        if unknown_category_fields:
            raise ValueError(
                "Assessment instrument observation_extraction.category has unsupported field(s): "
                + ", ".join(sorted(unknown_category_fields))
            )
        if any(
            not isinstance(category.get(field), str) or not category[field].strip()
            for field in ("system", "code", "display")
        ):
            raise ValueError(
                "Assessment instrument observation_extraction.category requires non-empty system, code, and display strings"
            )

    return {
        "enabled": enabled,
        "profile": profile,
        "category": dict(category) if isinstance(category, dict) else None,
    }


def observation_extraction_questionnaire_fields(config: dict[str, Any] | None) -> dict[str, Any]:
    """Return the authored SDC fields to merge into a Questionnaire resource."""
    if not config or not config["enabled"]:
        return {"meta_profile": [], "extension": []}
    category = config["category"]
    return {
        "meta_profile": [config["profile"]],
        "extension": [
            {
                "url": SDC_OBSERVATION_EXTRACTION_EXTENSION,
                "valueBoolean": True,
            },
            {
                "url": SDC_OBSERVATION_CATEGORY_EXTENSION,
                "valueCodeableConcept": {"coding": [category]},
            },
        ],
    }


def normalize_questionnaire_version_algorithm(instrument: Any) -> dict[str, str] | None:
    """Validate and preserve an explicitly authored Questionnaire version algorithm Coding."""
    if not isinstance(instrument, dict) or "version_algorithm" not in instrument:
        return None
    coding = instrument["version_algorithm"]
    if not isinstance(coding, dict):
        raise ValueError("Assessment instrument version_algorithm must be a Coding object")
    unknown = set(coding) - {"system", "code", "display"}
    if unknown:
        raise ValueError(
            "Assessment instrument version_algorithm has unsupported field(s): "
            + ", ".join(sorted(unknown))
        )
    normalized: dict[str, str] = {}
    for field in ("system", "code", "display"):
        if field not in coding:
            continue
        value = coding[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Assessment instrument version_algorithm.{field} must be a non-empty string")
        normalized[field] = value
    for field in ("system", "code"):
        if field not in normalized:
            raise ValueError(f"Assessment instrument version_algorithm.{field} is required")
    return normalized


def questionnaire_metadata_fields(instrument: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return strict L2-derived meta/extension fields and extraction config."""
    extraction = normalize_observation_extraction(instrument)
    fields = observation_extraction_questionnaire_fields(extraction)
    algorithm = normalize_questionnaire_version_algorithm(instrument)
    if extraction and extraction["enabled"] and not algorithm:
        raise ValueError(
            "Assessment instrument version_algorithm is required when SDC Observation extraction is enabled"
        )
    if algorithm:
        fields["extension"] = [
            {
                "url": ARTIFACT_VERSION_ALGORITHM_EXTENSION,
                "valueCoding": algorithm,
            },
            *fields["extension"],
        ]
    return fields, extraction


def validate_observation_extraction_items(items: Any, config: dict[str, Any] | None) -> None:
    """Validate the Boolean, versioned-Coding subset supported by extraction."""
    if not config or not config["enabled"]:
        return
    if not isinstance(items, list) or not items:
        raise ValueError(
            "Enabled SDC Observation extraction requires at least one assessment item"
        )

    seen_link_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"SDC extraction assessment item #{index} must be an object")
        link_id = item.get("id")
        if not isinstance(link_id, str) or not link_id.strip():
            raise ValueError(f"SDC extraction assessment item #{index} requires a non-empty id/linkId")
        if link_id in seen_link_ids:
            raise ValueError(f"SDC extraction assessment item linkId {link_id!r} is duplicated")
        seen_link_ids.add(link_id)
        if item.get("type") != "boolean":
            raise ValueError(
                f"SDC Observation extraction supports Boolean items only; {link_id!r} is not type boolean"
            )

        codings = item.get("code")
        if isinstance(codings, dict):
            codings = [codings]
        if not isinstance(codings, list) or len(codings) != 1 or not isinstance(codings[0], dict):
            raise ValueError(
                f"SDC extraction item {link_id!r} requires exactly one reviewed Coding"
            )
        coding = codings[0]
        for field in ("system", "version", "code", "display"):
            if not isinstance(coding.get(field), str) or not coding[field].strip():
                raise ValueError(
                    f"SDC extraction item {link_id!r} Coding requires non-empty {field}"
                )
