"""Base builder utilities for FHIR resource generation."""

from typing import Any, Dict, List, Optional


class FHIRBuilder:
    """Base class for FHIR resource builders."""

    def __init__(
        self,
        topic_id: str,
        base_url: str = "http://fhir.org/guides/reasonhealth",
        *,
        library_id: str | None = None,
        version: str = "1.0.0",
        status: str = "draft",
    ):
        """Initialize builder with topic context.
        
        Args:
            topic_id: Topic identifier for canonical URL generation
        """
        self.topic_id = topic_id
        self.library_id = library_id or topic_id
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.status = status

    def build_canonical_url(self, resource_type: str, resource_id: str) -> str:
        """Build canonical URL for a FHIR resource.
        
        Args:
            resource_type: FHIR resource type (PlanDefinition, Library, ActivityDefinition)
            resource_id: Resource identifier
            
        Returns:
            Canonical URL string
        """
        return f"{self.base_url}/{resource_type}/{resource_id}"

    def build_evidence_claim_index(self, artifact: Dict[str, Any] | None) -> Dict[str, Dict[str, Any]]:
        """Index evidence_traceability claims by claim_id."""
        if not isinstance(artifact, dict):
            return {}

        sections = artifact.get("sections") or {}
        claims = sections.get("evidence_traceability") or []
        if not isinstance(claims, list):
            return {}

        claim_index: Dict[str, Dict[str, Any]] = {}
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_id = str(claim.get("claim_id") or "").strip()
            if claim_id:
                claim_index[claim_id] = claim
        return claim_index

    def build_evidence_related_artifacts(
        self,
        evidence_ids: list[str] | None,
        evidence_claim_index: Dict[str, Dict[str, Any]] | None = None,
    ) -> list[Dict[str, Any]]:
        """Build RelatedArtifact documentation entries for evidence traceability."""
        if not evidence_ids or not isinstance(evidence_ids, list):
            return []

        claim_index = evidence_claim_index or {}
        related_artifacts: list[Dict[str, Any]] = []
        for evidence_id in evidence_ids:
            claim_id = str(evidence_id or "").strip()
            if not claim_id:
                continue
            claim = claim_index.get(claim_id)
            if not claim:
                continue

            statement = str(claim.get("statement") or "").strip()
            citation_parts: list[str] = []
            if statement:
                citation_parts.append(statement)
            evidence_entries = claim.get("evidence") or []
            if isinstance(evidence_entries, list) and evidence_entries:
                evidence_bits: list[str] = []
                for evidence in evidence_entries:
                    if not isinstance(evidence, dict):
                        continue
                    source = str(evidence.get("source") or "").strip()
                    locator = str(evidence.get("locator") or "").strip()
                    if source and locator:
                        evidence_bits.append(f"{source}: {locator}")
                    elif source:
                        evidence_bits.append(source)
                    elif locator:
                        evidence_bits.append(locator)
                if evidence_bits:
                    citation_parts.append("Evidence: " + "; ".join(evidence_bits))

            related_artifact: Dict[str, Any] = {
                "type": "citation",
                "label": claim_id,
            }
            related_artifact["citation"] = " ".join(citation_parts) if citation_parts else claim_id
            related_artifacts.append(related_artifact)

        return related_artifacts

    def build_strength_of_recommendation_extension(self, value: Any) -> Dict[str, Any] | None:
        """Build a cqf-strengthOfRecommendation extension from an explicit value."""
        strength = str(value or "").strip().lower()
        if strength not in {"strong", "weak"}:
            return None

        return {
            "url": "http://hl7.org/fhir/StructureDefinition/cqf-strengthOfRecommendation",
            "valueCodeableConcept": {
                "coding": [{
                    "system": "http://hl7.org/fhir/recommendation-strength",
                    "code": strength,
                }],
            },
        }

    def select_strength_of_recommendation(
        self,
        items: list[Dict[str, Any]] | None,
        *,
        field_names: tuple[str, ...] = ("recommendation_strength", "strength_of_recommendation"),
    ) -> str | None:
        """Return a shared strong/weak recommendation strength when all items agree."""
        if not items:
            return None

        strengths: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            for field_name in field_names:
                normalized = str(item.get(field_name) or "").strip().lower()
                if normalized in {"strong", "weak"}:
                    strengths.add(normalized)
                    break

        if len(strengths) == 1:
            return next(iter(strengths))
        return None

    def build_cql_expression(self, condition_id: str, value: str | bool = None) -> Dict[str, Any]:
        """Build CQL expression reference for a condition with optional polarity.
        
        Args:
            condition_id: Condition identifier from L2 artifact
            value: Optional condition value (true/false for polarity)
            
        Returns:
            FHIR Expression structure with CQL reference
        """
        # Convert kebab-case to PascalCase for CQL identifier
        cql_identifier = self._to_pascal_case(condition_id)
        
        # Handle polarity for canonical decision-table values and booleans.
        normalized = value.strip().lower() if isinstance(value, str) else value
        if normalized is not None and normalized in ("false", False, "no"):
            expression = f"not {cql_identifier}"
        else:
            expression = cql_identifier
        
        return {
            "language": "text/cql-identifier",
            "expression": expression,
            "reference": f"{self.build_canonical_url('Library', self.library_id)}#{cql_identifier}"
        }

    def build_condition_element(self, condition_id: str, value: str | bool = None, kind: str = "applicability") -> Dict[str, Any]:
        """Build FHIR condition element with optional polarity.
        
        Args:
            condition_id: Condition identifier from L2 artifact
            value: Optional condition value for polarity (true/false)
            kind: Condition kind (applicability, start, stop)
            
        Returns:
            FHIR PlanDefinition.action.condition structure
        """
        return {
            "kind": kind,
            "expression": self.build_cql_expression(condition_id, value)
        }

    def _to_pascal_case(self, kebab_str: str) -> str:
        """Convert kebab-case to PascalCase for CQL identifiers.
        
        Args:
            kebab_str: Kebab-case string (e.g., 'has-crs-dx')
            
        Returns:
            PascalCase string (e.g., 'HasCrsDx')
        """
        return ''.join(word.capitalize() for word in kebab_str.split('-'))

    def _to_camel_case(self, kebab_str: str) -> str:
        """Convert kebab-case to camelCase for FHIR IDs.
        
        Args:
            kebab_str: Kebab-case string (e.g., 'surgical-decision')
            
        Returns:
            camelCase string (e.g., 'surgicalDecision')
        """
        words = kebab_str.split('-')
        return words[0] + ''.join(word.capitalize() for word in words[1:])

    def validate_artifact_structure(self, artifact: Dict[str, Any], required_sections: List[str]) -> bool:
        """Validate L2 artifact has required sections.
        
        Args:
            artifact: L2 artifact dictionary
            required_sections: List of required section names
            
        Returns:
            True if all required sections present
            
        Raises:
            ValueError: If required sections missing
        """
        sections = artifact.get('sections', {})
        missing = [s for s in required_sections if s not in sections]
        
        if missing:
            raise ValueError(f"L2 artifact missing required sections: {missing}")
        
        return True
