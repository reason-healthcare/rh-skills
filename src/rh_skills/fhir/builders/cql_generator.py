"""
CQL Library Generator for CPG-on-FHIR formalization.

Generates FHIR Library resources with CQL content from L2 condition definitions.
Integrates with ConditionMerger for topic-level deduplication.
"""

from typing import Dict, Any, List
from .base import FHIRBuilder


class CQLGenerator(FHIRBuilder):
    """Generate CQL Library resources from L2 condition definitions.
    
    Creates a single topic-level Library resource containing all deduplicated
    conditions from decision tables in the topic.
    
    **Current Implementation**: Stub CQL with TODO markers
    **Future Enhancement**: LLM-based expansion of CQL stubs to full expressions
    """
    
    def __init__(self, topic_id: str, version: str = "1.0.0"):
        """Initialize CQL generator.
        
        Args:
            topic_id: Topic identifier (used for Library ID and canonical URL)
            version: Library version number
        """
        super().__init__(topic_id)
        self.version = version
    
    def generate_library(
        self,
        conditions: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate FHIR Library resource with CQL content.
        
        Args:
            conditions: List of condition dictionaries from ConditionMerger
            metadata: Optional metadata (title, description, etc.)
            
        Returns:
            FHIR Library resource dictionary
        """
        metadata = metadata or {}
        
        # Build CQL library content
        cql_content = self._build_cql_library(conditions, metadata)
        
        # Create FHIR Library resource
        library = {
            "resourceType": "Library",
            "id": self.topic_id,
            "url": self.build_canonical_url("Library", self.topic_id),
            "version": self.version,
            "name": self._to_cql_identifier(self.topic_id),
            "title": metadata.get("title", f"{self._to_title_case(self.topic_id)} Clinical Logic"),
            "status": "draft",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/library-type",
                    "code": "logic-library",
                    "display": "Logic Library"
                }]
            },
            "description": metadata.get(
                "description",
                f"CQL logic library for {self.topic_id} topic. Contains condition definitions from decision tables."
            ),
            "content": [{
                "contentType": "text/cql",
                "data": self._encode_base64(cql_content)
            }]
        }
        
        # Add optional fields
        if metadata.get("author"):
            library["author"] = [{"name": metadata["author"]}]
        
        if metadata.get("relatedArtifact"):
            library["relatedArtifact"] = metadata["relatedArtifact"]
        
        return library
    
    def _build_cql_library(
        self,
        conditions: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> str:
        """Build CQL library content with condition definitions.
        
        Args:
            conditions: List of condition dictionaries
            metadata: Library metadata
            
        Returns:
            CQL library as string
        """
        library_name = self._to_cql_identifier(self.topic_id)
        
        cql_lines = [
            f"library {library_name} version '{self.version}'",
            "",
            "using FHIR version '4.0.1'",
            "include FHIRHelpers version '4.0.1' called FHIRHelpers",
            "",
            "context Patient",
            ""
        ]
        
        # Add condition definitions
        for condition in conditions:
            cql_def = self._build_condition_definition(condition)
            cql_lines.append(cql_def)
            cql_lines.append("")
        
        return "\n".join(cql_lines)
    
    def _build_condition_definition(self, condition: Dict[str, Any]) -> str:
        """Build CQL definition for a single condition.
        
        **Current**: Returns stub with TODO marker
        **Future**: LLM-based expansion from condition description
        
        Args:
            condition: Condition dictionary with id, label, description, cql_stub
            
        Returns:
            CQL define statement
        """
        cond_id = condition.get('id') or condition.get('condition_id')
        cql_identifier = self._to_cql_identifier(cond_id)
        
        # Check for existing CQL expression
        cql_stub = condition.get('cql_stub') or condition.get('description', '')
        
        # If description contains "CQL:" prefix, extract the CQL expression
        description = condition.get('description', '')
        if 'CQL:' in description:
            # Extract CQL expression from description
            parts = description.split('CQL:')
            if len(parts) > 1:
                cql_expr = parts[1].split('-')[0].strip()
                # Use the extracted expression as a stub
                cql_stub = cql_expr
        
        # Build CQL definition
        # TODO: Implement LLM-based expansion of stubs to full expressions
        if cql_stub:
            return f"define \"{cql_identifier}\":\n  // TODO: Expand from L2: {cql_stub}\n  null"
        else:
            label = condition.get('label', cond_id)
            return f"define \"{cql_identifier}\":\n  // TODO: Implement logic for: {label}\n  null"
    
    def _to_cql_identifier(self, kebab_id: str) -> str:
        """Convert kebab-case ID to CQL-friendly PascalCase identifier.
        
        Args:
            kebab_id: Kebab-case identifier (e.g., 'has-crs-diagnosis')
            
        Returns:
            PascalCase identifier (e.g., 'HasCrsDiagnosis')
        """
        words = kebab_id.split('-')
        return ''.join(word.capitalize() for word in words)
    
    def _to_title_case(self, kebab_id: str) -> str:
        """Convert kebab-case ID to title case.
        
        Args:
            kebab_id: Kebab-case identifier
            
        Returns:
            Title case string
        """
        return ' '.join(word.capitalize() for word in kebab_id.split('-'))
    
    def _encode_base64(self, content: str) -> str:
        """Encode CQL content as base64 for FHIR Library.content.data.
        
        Args:
            content: CQL library content string
            
        Returns:
            Base64-encoded string
        """
        import base64
        return base64.b64encode(content.encode('utf-8')).decode('ascii')


# Future enhancement: LLM-based CQL expansion
def expand_cql_stub_with_llm(stub: str, condition_description: str) -> str:
    """Expand L2 CQL stub to full CQL expression using LLM.
    
    **Not yet implemented** - placeholder for Phase 4 enhancement.
    
    Args:
        stub: L2 CQL stub (e.g., "HasCRSDiagnosis")
        condition_description: Natural language description
        
    Returns:
        Full CQL expression
    """
    # TODO: Implement LLM prompt engineering to expand stubs
    # Prompt should include:
    # - FHIR R4 resource structure
    # - CQL syntax patterns
    # - Condition description and clinical context
    # - Example CQL expressions for similar conditions
    raise NotImplementedError("LLM-based CQL expansion not yet implemented")
