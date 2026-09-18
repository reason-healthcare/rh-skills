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
SDC_CALCULATED_EXPRESSION_EXTENSION = (
    "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-calculatedExpression"
)


def _non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Assessment scoring {label} must be a non-empty string")
    return value


def _score_item_code(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("Assessment scoring result.item.code must be one Coding object")
    unknown = set(value) - {"system", "version", "code", "display"}
    if unknown:
        raise ValueError(
            "Assessment scoring result.item.code has unsupported field(s): "
            + ", ".join(sorted(unknown))
        )
    coding: dict[str, str] = {}
    for field in ("system", "version", "code", "display"):
        coding[field] = _non_empty_string(
            value.get(field), f"result.item.code.{field}"
        )
    return coding


def _fhirpath_string(value: str) -> str:
    """Quote a string as a FHIRPath single-quoted literal."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _count_boolean_answers_expression(input_items: list[str]) -> str:
    """Build the bounded FHIRPath expression for a complete Boolean count."""
    predicates: list[str] = []
    counts: list[str] = []
    for link_id in input_items:
        item = f"%resource.item.where(linkId = {_fhirpath_string(link_id)})"
        booleans = f"{item}.answer.value.ofType(boolean)"
        predicates.extend((
            f"{item}.count() = 1",
            f"{item}.answer.count() = 1",
            f"{booleans}.count() = 1",
        ))
        counts.append(f"{booleans}.where($this = true).count()")
    return f"iif({' and '.join(predicates)}, {' + '.join(counts)}, {{}})"


def normalize_assessment_scoring(
    scoring: Any,
    source_items: Any,
    instrument: Any,
    evidence_traceability: Any = None,
) -> dict[str, Any] | None:
    """Validate the optional, source-linked scored Observation contract.

    Assessments without ``scoring.algorithm`` retain their existing behavior.
    The current implementation supports only a bounded count of usable true
    Boolean answers; new methods must be explicitly implemented here before
    an author can request them.
    """
    if not isinstance(scoring, dict) or "algorithm" not in scoring:
        return None

    allowed_scoring = {"algorithm", "result", "classifications"}
    unknown_scoring = set(scoring) - allowed_scoring
    if unknown_scoring:
        raise ValueError(
            "Assessment scoring has unsupported field(s): "
            + ", ".join(sorted(unknown_scoring))
        )

    algorithm = scoring.get("algorithm")
    if not isinstance(algorithm, dict):
        raise ValueError("Assessment scoring.algorithm must be an object")
    algorithm_fields = {
        "method", "input_items", "counted_value", "completion",
        "missing_or_invalid", "evidence_traceability_ids",
    }
    unknown_algorithm = set(algorithm) - algorithm_fields
    if unknown_algorithm:
        raise ValueError(
            "Assessment scoring.algorithm has unsupported field(s): "
            + ", ".join(sorted(unknown_algorithm))
        )
    method = _non_empty_string(algorithm.get("method"), "algorithm.method")
    if method != "count_boolean_answers":
        raise ValueError(
            f"Assessment scoring algorithm {method!r} is unsupported; "
            "currently supported method: count_boolean_answers"
        )
    input_items = algorithm.get("input_items")
    if not isinstance(input_items, list) or not input_items:
        raise ValueError("Assessment scoring.algorithm.input_items must be a non-empty list")
    normalized_inputs: list[str] = []
    for index, item_id in enumerate(input_items, start=1):
        normalized_inputs.append(
            _non_empty_string(item_id, f"algorithm.input_items[{index - 1}]")
        )
    if len(set(normalized_inputs)) != len(normalized_inputs):
        raise ValueError("Assessment scoring.algorithm.input_items must be unique")
    if algorithm.get("counted_value") is not True:
        raise ValueError("Assessment scoring.algorithm.counted_value must be true")
    if algorithm.get("completion") != "all_inputs_usable":
        raise ValueError(
            "Assessment scoring.algorithm.completion must be all_inputs_usable"
        )
    if algorithm.get("missing_or_invalid") != "omit_result":
        raise ValueError(
            "Assessment scoring.algorithm.missing_or_invalid must be omit_result"
        )

    items = source_items if isinstance(source_items, list) else []
    items_by_id = {
        item.get("id"): item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for item_id in normalized_inputs:
        item = items_by_id.get(item_id)
        if item is None:
            raise ValueError(
                f"Assessment scoring input item {item_id!r} does not exist in sections.items"
            )
        if item.get("type") != "boolean":
            raise ValueError(
                f"Assessment scoring input item {item_id!r} must have type boolean"
            )
        if item.get("required") is not True:
            raise ValueError(
                f"Assessment scoring input item {item_id!r} must be required"
            )

    referenced_claims = algorithm.get("evidence_traceability_ids")
    if not isinstance(referenced_claims, list) or not referenced_claims:
        raise ValueError(
            "Assessment scoring.algorithm.evidence_traceability_ids must be a non-empty list"
        )
    referenced_claims = [
        _non_empty_string(claim, "algorithm.evidence_traceability_ids entry")
        for claim in referenced_claims
    ]
    if len(set(referenced_claims)) != len(referenced_claims):
        raise ValueError(
            "Assessment scoring.algorithm.evidence_traceability_ids must be unique"
        )
    known_claims = {
        claim.get("claim_id")
        for claim in (evidence_traceability if isinstance(evidence_traceability, list) else [])
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str)
    }
    if any(claim not in known_claims for claim in referenced_claims):
        raise ValueError(
            "Assessment scoring.algorithm.evidence_traceability_ids must reference "
            "sections.evidence_traceability claim_id values"
        )

    extraction = normalize_observation_extraction(
        instrument if isinstance(instrument, dict) else {}
    )
    if not extraction or not extraction["enabled"]:
        raise ValueError(
            "Structured assessment scoring requires enabled SDC Observation extraction"
        )

    result = scoring.get("result")
    if not isinstance(result, dict) or set(result) != {"item", "range"}:
        raise ValueError(
            "Assessment scoring.result must contain exactly item and range"
        )
    result_item = result.get("item")
    if not isinstance(result_item, dict):
        raise ValueError("Assessment scoring.result.item must be an object")
    unknown_item = set(result_item) - {"id", "text", "type", "code"}
    if unknown_item:
        raise ValueError(
            "Assessment scoring.result.item has unsupported field(s): "
            + ", ".join(sorted(unknown_item))
        )
    item_id = _non_empty_string(result_item.get("id"), "result.item.id")
    item_text = _non_empty_string(result_item.get("text"), "result.item.text")
    if result_item.get("type") != "integer":
        raise ValueError("Assessment scoring.result.item.type must be integer")
    if item_id in items_by_id:
        raise ValueError(
            f"Assessment scoring result item id {item_id!r} duplicates a source item"
        )
    coding = _score_item_code(result_item.get("code"))

    score_range = result.get("range")
    if not isinstance(score_range, dict) or set(score_range) != {"minimum", "maximum"}:
        raise ValueError(
            "Assessment scoring.result.range must contain exactly minimum and maximum"
        )
    minimum = score_range.get("minimum")
    maximum = score_range.get("maximum")
    if (
        not isinstance(minimum, int) or isinstance(minimum, bool)
        or not isinstance(maximum, int) or isinstance(maximum, bool)
        or minimum != 0 or maximum != len(normalized_inputs)
    ):
        raise ValueError(
            "count_boolean_answers range must be minimum 0 and maximum equal to the number of input_items"
        )

    classifications = scoring.get("classifications", [])
    if not isinstance(classifications, list):
        raise ValueError("Assessment scoring.classifications must be a list when present")
    normalized_classifications: list[dict[str, Any]] = []
    seen_classification_ids: set[str] = set()
    for index, classification in enumerate(classifications):
        if not isinstance(classification, dict):
            raise ValueError(f"Assessment scoring.classifications[{index}] must be an object")
        unknown_classification = set(classification) - {
            "id", "label", "operator", "threshold", "evidence_traceability_ids",
        }
        if unknown_classification:
            raise ValueError(
                f"Assessment scoring.classifications[{index}] has unsupported field(s): "
                + ", ".join(sorted(unknown_classification))
            )
        class_id = _non_empty_string(classification.get("id"), f"classifications[{index}].id")
        if class_id in seen_classification_ids:
            raise ValueError(f"Assessment scoring classification id {class_id!r} is duplicated")
        seen_classification_ids.add(class_id)
        label = _non_empty_string(classification.get("label"), f"classifications[{index}].label")
        operator = _non_empty_string(classification.get("operator"), f"classifications[{index}].operator")
        if operator != "greater_than_or_equal":
            raise ValueError(
                f"Assessment scoring classification operator {operator!r} is unsupported; "
                "currently supported operator: greater_than_or_equal"
            )
        threshold = classification.get("threshold")
        if not isinstance(threshold, int) or isinstance(threshold, bool) or not minimum <= threshold <= maximum:
            raise ValueError(
                f"Assessment scoring classification {class_id!r} threshold must be an integer within the score range"
            )
        refs = classification.get("evidence_traceability_ids")
        if not isinstance(refs, list) or not refs:
            raise ValueError(
                f"Assessment scoring classification {class_id!r} requires evidence_traceability_ids"
            )
        refs = [_non_empty_string(ref, f"classifications[{index}].evidence_traceability_ids entry") for ref in refs]
        if any(ref not in known_claims for ref in refs):
            raise ValueError(
                f"Assessment scoring classification {class_id!r} evidence references unknown claim_id"
            )
        normalized_classifications.append({
            "id": class_id,
            "label": label,
            "operator": operator,
            "threshold": threshold,
            "evidence_traceability_ids": refs,
        })

    return {
        "algorithm": {
            "method": method,
            "input_items": normalized_inputs,
            "counted_value": True,
            "completion": "all_inputs_usable",
            "missing_or_invalid": "omit_result",
            "evidence_traceability_ids": referenced_claims,
        },
        "result": {
            "item": {
                "id": item_id,
                "text": item_text,
                "type": "integer",
                "code": coding,
            },
            "range": {"minimum": minimum, "maximum": maximum},
        },
        "classifications": normalized_classifications,
        "expression": _count_boolean_answers_expression(normalized_inputs),
    }


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
