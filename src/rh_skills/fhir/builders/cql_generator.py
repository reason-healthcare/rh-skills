"""
CQL Library Generator for CPG-on-FHIR formalization.

Generates FHIR Library resources with CQL content from L2 condition definitions.
Integrates with ConditionMerger for topic-level deduplication.
Supports composite workflow states for state-based action tree formalization.
"""

from typing import Dict, Any, List, Set, Tuple
from collections import Counter
from .base import FHIRBuilder


class CQLGenerator(FHIRBuilder):
    """Generate CQL Library resources from L2 condition definitions.
    
    Creates a single topic-level Library resource containing all deduplicated
    conditions from decision tables in the topic.
    
    **Current Implementation**: Stub CQL with TODO markers
    **Future Enhancement**: LLM-based expansion of CQL stubs to full expressions
    """
    
    def __init__(
        self,
        topic_id: str,
        library_id: str | None = None,
        version: str = "1.0.0",
        *,
        base_url: str = "http://fhir.org/guides/reasonhealth",
        status: str = "draft",
    ):
        """Initialize CQL generator.
        
        Args:
            topic_id: Topic identifier (used for Library ID and canonical URL)
            version: Library version number
        """
        super().__init__(topic_id, base_url, library_id=library_id, version=version, status=status)
    
    def generate_library(
        self,
        conditions: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
        rules: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate FHIR Library resource with CQL content.
        
        Args:
            conditions: List of condition dictionaries from ConditionMerger
            metadata: Optional metadata (title, description, etc.)
            rules: Optional list of rules for composite state detection
            
        Returns:
            FHIR Library resource dictionary
        """
        metadata = metadata or {}
        
        # Build CQL library content
        cql_content = self._build_cql_library(conditions, metadata, rules)
        
        # Create FHIR Library resource
        library = {
            "resourceType": "Library",
            "id": self.library_id,
            "url": self.build_canonical_url("Library", self.library_id),
            "version": self.version,
            "name": self._to_cql_identifier(self.library_id),
            "title": metadata.get("title", f"{self._to_title_case(self.library_id)} Clinical Logic"),
            "status": self.status,
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/library-type",
                    "code": "logic-library",
                    "display": "Logic Library"
                }]
            },
            "description": metadata.get(
                "description",
                f"CQL logic library for {self.library_id}. Contains condition definitions from structured logic artifacts."
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
        metadata: Dict[str, Any],
        rules: List[Dict[str, Any]] = None
    ) -> str:
        """Build CQL library content with condition definitions.
        
        Args:
            conditions: List of condition dictionaries
            metadata: Library metadata
            rules: Optional list of rules for composite state detection
            
        Returns:
            CQL library as string
        """
        library_name = self._to_cql_identifier(self.library_id)
        
        cql_lines = [
            f"library {library_name} version '{self.version}'",
            "",
            "using FHIR version '4.0.1'",
            "include FHIRHelpers version '4.0.1' called FHIRHelpers",
            "",
            "context Patient",
            ""
        ]
        
        # Detect composite workflow states if rules provided
        composite_states = []
        if rules:
            composite_states = self._detect_composite_workflow_states(conditions, rules)
        
        # Section 1: Atomic condition definitions
        if conditions:
            cql_lines.append("// ═══════════════════════════════════════════════")
            cql_lines.append("// Atomic Conditions")
            cql_lines.append("// ═══════════════════════════════════════════════")
            cql_lines.append("")
            for condition in conditions:
                cql_def = self._build_condition_definition(condition)
                cql_lines.append(cql_def)
                cql_lines.append("")
        
        # Section 2: Composite workflow states
        if composite_states:
            cql_lines.append("// ═══════════════════════════════════════════════")
            cql_lines.append("// Composite Workflow States")
            cql_lines.append("// ═══════════════════════════════════════════════")
            cql_lines.append("")
            for state in composite_states:
                cql_def = self._build_composite_state_definition(state)
                cql_lines.append(cql_def)
                cql_lines.append("")
        
        return "\n".join(cql_lines)
    
    def _detect_composite_workflow_states(
        self,
        conditions: List[Dict[str, Any]],
        rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect composite workflow states from frequently co-occurring conditions.
        
        Analyzes rules to find conditions that appear together frequently,
        indicating they represent a workflow state boundary (e.g., diagnosis
        established, surgical candidacy met).
        
        Args:
            conditions: List of atomic condition dictionaries
            rules: List of rule dictionaries from L2 decision table
            
        Returns:
            List of composite state dictionaries with:
            - name: State name (e.g., "DiagnosisConfirmed")
            - components: List of condition IDs
            - description: Human-readable description
        """
        # Index conditions by ID
        condition_index = {c.get('id'): c for c in conditions if c.get('id')}
        
        # Track condition co-occurrence patterns
        condition_sets: List[Tuple[str, ...]] = []
        condition_frequency: Counter = Counter()
        
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            
            when_clause = rule.get('when')
            if not when_clause or not isinstance(when_clause, dict):
                continue
            
            # Extract conditions that are set to "true" (positive assertions)
            positive_conditions = tuple(sorted([
                cond_id for cond_id, value in when_clause.items()
                if value == "true" and cond_id in condition_index
            ]))
            
            if len(positive_conditions) >= 2:  # Multi-condition patterns
                condition_sets.append(positive_conditions)
            
            # Track individual condition frequency
            for cond_id in positive_conditions:
                condition_frequency[cond_id] += 1
        
        # Find composite states
        composite_states: List[Dict[str, Any]] = []
        seen_patterns: Set[Tuple[str, ...]] = set()
        
        # Strategy 1: Find condition sets that appear exactly (surgical candidacy)
        exact_patterns = Counter(condition_sets)
        for pattern, count in exact_patterns.items():
            if len(pattern) >= 2:
                state = self._create_composite_state(pattern, condition_index)
                if state:
                    composite_states.append(state)
                    seen_patterns.add(pattern)
        
        # Strategy 2: Find persistent prerequisites (appear in 50%+ of rules)
        min_frequency = max(2, len(rules) // 2)
        persistent_conditions = [
            cond_id for cond_id, freq in condition_frequency.items()
            if freq >= min_frequency
        ]
        
        # Group persistent conditions with their common co-occurring conditions
        for base_cond in persistent_conditions:
            # Find conditions that co-occur with this base condition
            co_occurring: Counter = Counter()
            for cond_set in condition_sets:
                if base_cond in cond_set:
                    for other_cond in cond_set:
                        if other_cond != base_cond:
                            co_occurring[other_cond] += 1
            
            # If we find 1-2 conditions that consistently appear with base,
            # create a composite state
            common_companions = [
                cond_id for cond_id, freq in co_occurring.items()
                if freq >= 2
            ]
            
            if common_companions:
                # Create composite of base + most common companion(s)
                pattern = tuple(sorted([base_cond] + common_companions[:2]))
                if pattern not in seen_patterns and len(pattern) >= 2:
                    state = self._create_composite_state(pattern, condition_index)
                    if state:
                        composite_states.append(state)
                        seen_patterns.add(pattern)
        
        # Deduplicate and merge related states
        composite_states = self._merge_related_states(composite_states)
        
        return composite_states
    
    def _create_composite_state(
        self,
        condition_ids: Tuple[str, ...],
        condition_index: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any] | None:
        """Create a composite state definition from condition IDs.
        
        Args:
            condition_ids: Tuple of condition IDs that form the state
            condition_index: Index of condition ID -> condition dict
            
        Returns:
            Composite state dictionary or None if invalid
        """
        if not condition_ids:
            return None

        # Generate state name from components
        component_names = []
        for cond_id in condition_ids:
            condition = condition_index.get(cond_id)
            if not condition:
                continue
            cql_name = self._to_cql_identifier(cond_id)
            component_names.append(cql_name)
        
        if not component_names:
            return None
        
        # Create composite name
        # Special handling for common clinical workflow patterns
        component_set = set(condition_ids)
        
        # Surgical candidacy = diagnosis + QOL + objective findings + failed medical + no contraindications + acceptance
        if all(cid in component_set for cid in [
            'has-crs-diagnosis', 'qol-impairment-documented', 'objective-findings-documented',
            'medical-therapy-inadequate', 'no-contraindications-to-surgery', 'patient-accepts-risks-benefits'
        ]):
            state_name = "SurgicalCandidacyEstablished"
            description = "All surgical candidacy criteria are met"
        # Diagnosis confirmation = diagnosis + objective findings
        elif 'has-crs-diagnosis' in component_set and 'objective-findings-documented' in component_set and len(component_set) == 2:
            state_name = "DiagnosisConfirmed"
            description = "CRS diagnosis confirmed with objective findings"
        # Generic: combine names
        else:
            if len(component_names) == 2:
                state_name = f"{component_names[0]}And{component_names[1]}"
            elif len(component_names) == 3:
                state_name = f"{component_names[0]}And{component_names[1]}And{component_names[2]}"
            else:
                state_name = "And".join(component_names[:2]) + "Etc"
            
            labels = [condition_index[cid].get('label', cid) for cid in condition_ids]
            description = " AND ".join(labels)
        
        return {
            "name": state_name,
            "components": list(condition_ids),
            "description": description,
        }

    def _merge_related_states(
        self,
        states: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge composite states that are subsets of each other.
        
        If state A is a subset of state B, keep B and drop A.
        
        Args:
            states: List of composite state dicts
            
        Returns:
            Deduplicated list of states
        """
        if not states:
            return states
        
        # Sort by component count (descending) to keep larger sets
        sorted_states = sorted(states, key=lambda s: len(s.get('components', [])), reverse=True)
        
        result: List[Dict[str, Any]] = []
        seen_components: List[Set[str]] = []
        
        for state in sorted_states:
            components = set(state.get('components', []))
            
            # Check if this is a subset of an already-added state
            is_subset = any(components <= existing for existing in seen_components)
            
            if not is_subset:
                result.append(state)
                seen_components.append(components)
        
        return result
    
    def _build_composite_state_definition(self, state: Dict[str, Any]) -> str:
        """Build CQL definition for a composite workflow state.
        
        Args:
            state: Composite state dictionary with name, components, description
            
        Returns:
            CQL define statement
        """
        name = state.get('name', 'UnknownState')
        components = state.get('components', [])
        description = state.get('description', '')
        
        # Convert component IDs to CQL identifiers
        cql_components = [self._to_cql_identifier(cid) for cid in components]
        
        # Build composite expression
        expression = " and ".join(cql_components)
        
        lines = [
            f"// {description}",
            f"define \"{name}\":",
            f"  {expression}",
            "",
            f"define \"Not{name}\":",
            f"  not {name}"
        ]
        
        return "\n".join(lines)
    
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
        data_elements = condition.get('data_elements') or []

        if isinstance(data_elements, list) and data_elements:
            feature_lines = []
            feature_identifiers = []
            for data_element in data_elements:
                if not isinstance(data_element, dict):
                    continue
                feature_name = self._to_cql_identifier(
                    str(data_element.get('label') or data_element.get('id') or 'feature')
                    .lower()
                    .replace(' ', '-')
                )
                feature_identifiers.append(feature_name)
                feature_description = (
                    data_element.get('description')
                    or data_element.get('label')
                    or data_element.get('id')
                    or 'feature'
                )
                feature_lines.extend(self._build_data_element_definition(feature_name, data_element, feature_description))

            composite_operator = " and " if len(feature_identifiers) > 1 else ""
            composite_expression = composite_operator.join(f'"{name}"' for name in feature_identifiers) or "null"
            feature_lines.extend([
                f'// Condition: {condition.get("label", cond_id)}',
                f'define "{cql_identifier}":',
                f"  {composite_expression}",
            ])
            return "\n".join(feature_lines)
        
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

    def _build_data_element_definition(
        self,
        feature_name: str,
        data_element: Dict[str, Any],
        feature_description: str,
    ) -> List[str]:
        """Build a more structured stub define for a feature-level data element."""
        data_type = str(data_element.get("data_type") or "").strip().lower()
        label_text = " ".join(
            str(data_element.get(field) or "")
            for field in ("label", "description", "id")
        ).lower()

        if data_type in {"diagnosis", "condition"} or "diagnosis" in label_text:
            return [
                f"// Feature: {feature_description}",
                f"// TODO: Constrain to the correct diagnosis code and require active clinicalStatus when appropriate.",
                f'define "{feature_name}":',
                "  exists([Condition] C)",
                "",
            ]

        if data_type in {"patient-reported", "assessment"} or any(
            token in label_text for token in ("quality of life", "questionnaire", "survey", "score", "snot", "burden")
        ):
            return [
                f"// Feature: {feature_description}",
                "// TODO: Use the specific questionnaire or patient-reported instrument named by the guideline.",
                "// TODO: Replace this stub with the explicit score/threshold that qualifies the recommendation.",
                "// TODO: Prefer clinically complete observations (for example final/amended/corrected results).",
                f'define "{feature_name}":',
                "  exists([Observation] O)",
                "",
            ]

        if data_type == "history" or "12 week" in label_text or "duration" in label_text:
            return [
                f"// Feature: {feature_description}",
                "// TODO: Compute the required duration window explicitly (for example >= 12 weeks).",
                f'define "{feature_name}":',
                "  exists([Observation] O)",
                "",
            ]

        if data_type in {"imaging", "finding", "symptom", "procedure"}:
            return [
                f"// Feature: {feature_description}",
                "// TODO: Constrain to the specific coded finding/procedure/evidence named by the guideline.",
                f'define "{feature_name}":',
                "  exists([Observation] O)",
                "",
            ]

        return [
            f"// Feature: {feature_description}",
            "// TODO: Replace with the specific FHIR retrieve, code set, status, and threshold required by the guideline.",
            f'define "{feature_name}":',
            "  exists([Observation] O)",
            "",
        ]
    
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
