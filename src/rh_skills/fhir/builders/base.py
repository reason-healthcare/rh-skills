"""Base builder utilities for FHIR resource generation."""

from typing import Any, Dict, List, Optional


class FHIRBuilder:
    """Base class for FHIR resource builders."""

    def __init__(self, topic_id: str):
        """Initialize builder with topic context.
        
        Args:
            topic_id: Topic identifier for canonical URL generation
        """
        self.topic_id = topic_id
        self.base_url = "http://fhir.org/guides/reasonhealth"  # TODO: make configurable

    def build_canonical_url(self, resource_type: str, resource_id: str) -> str:
        """Build canonical URL for a FHIR resource.
        
        Args:
            resource_type: FHIR resource type (PlanDefinition, Library, ActivityDefinition)
            resource_id: Resource identifier
            
        Returns:
            Canonical URL string
        """
        return f"{self.base_url}/{resource_type}/{resource_id}"

    def build_cql_expression(self, condition_id: str) -> Dict[str, Any]:
        """Build CQL expression reference for a condition.
        
        Args:
            condition_id: Condition identifier from L2 artifact
            
        Returns:
            FHIR Expression structure with CQL reference
        """
        # Convert kebab-case to PascalCase for CQL identifier
        cql_identifier = self._to_pascal_case(condition_id)
        
        return {
            "language": "text/cql-identifier",
            "expression": cql_identifier,
            "reference": f"{self.build_canonical_url('Library', self.topic_id)}#{cql_identifier}"
        }

    def build_condition_element(self, condition_id: str, kind: str = "applicability") -> Dict[str, Any]:
        """Build FHIR condition element.
        
        Args:
            condition_id: Condition identifier from L2 artifact
            kind: Condition kind (applicability, start, stop)
            
        Returns:
            FHIR PlanDefinition.action.condition structure
        """
        return {
            "kind": kind,
            "expression": self.build_cql_expression(condition_id)
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
