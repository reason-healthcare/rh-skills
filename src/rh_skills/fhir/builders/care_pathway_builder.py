"""Care pathway formalization to FHIR PlanDefinition resources.

Generates Pathway PlanDefinitions (clinical-protocol) and Strategy PlanDefinitions
(event-driven) from L2 care pathway artifacts following CPG-on-FHIR patterns.
"""

from typing import Any, Dict, List, Optional
from .base import FHIRBuilder
from .condition_hoister import ConditionHoister


class CarePathwayBuilder(FHIRBuilder):
    """Builds FHIR resources from L2 care pathway artifacts.
    
    Generates:
    - One Pathway PlanDefinition (clinical-protocol type)
    - One Strategy PlanDefinition per phase (event-driven type)
    - References Recommendation PlanDefinitions from decision tables
    """

    def __init__(self, topic_id: str, artifact_id: str, decision_table_id: Optional[str] = None):
        """Initialize builder.
        
        Args:
            topic_id: Topic identifier for canonical URLs
            artifact_id: Care pathway artifact identifier
            decision_table_id: Optional source decision table ID (for auto-generated pathways)
        """
        super().__init__(topic_id)
        self.artifact_id = artifact_id
        self.decision_table_id = decision_table_id
        self.hoister = ConditionHoister(topic_id) if decision_table_id else None

    def build_all_resources(
        self, 
        care_pathway: Dict[str, Any],
        decision_table: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Build all FHIR resources from care pathway.
        
        Args:
            care_pathway: L2 care pathway artifact
            decision_table: Optional source decision table (for auto-generated pathways)
            
        Returns:
            Dictionary with keys: 'PlanDefinition' (list of Pathway + Strategies)
        """
        # Care pathway artifacts have metadata and sections at top level
        # Validation happens in build methods as needed
        
        # Check if auto-generated
        metadata = care_pathway.get('metadata', {})
        is_auto_generated = metadata.get('auto_generated', False)
        
        # Analyze conditions if decision table provided
        classifications = None
        if decision_table and self.hoister:
            classifications = self.hoister.analyze_decision_table(decision_table)
        
        # Build pathway and strategies
        pathway_pd = self.build_pathway(care_pathway, classifications, decision_table)
        strategy_pds = self.build_strategies(care_pathway, classifications, decision_table)
        
        # Combine all PlanDefinitions
        all_plan_definitions = [pathway_pd] + strategy_pds
        
        return {
            'PlanDefinition': all_plan_definitions
        }

    def build_pathway(
        self,
        care_pathway: Dict[str, Any],
        classifications: Optional[Dict[str, Any]] = None,
        decision_table: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build Pathway PlanDefinition (clinical-protocol).
        
        Args:
            care_pathway: L2 care pathway artifact
            classifications: Optional condition classifications from decision table
            decision_table: Optional source decision table
            
        Returns:
            PlanDefinition resource (clinical-protocol type)
        """
        metadata = care_pathway.get('metadata', {})
        sections = care_pathway.get('sections', {})
        phases = sections.get('steps', [])
        
        if not phases:
            raise ValueError(
                f"Care pathway artifact is missing required 'sections.steps' field. "
                f"Found sections keys: {list(sections.keys()) if sections else 'NO SECTIONS'}. "
                f"Top-level keys: {list(care_pathway.keys())}. "
                f"Expected L2 structure: {{sections: {{steps: [{{id, code, description, substeps}}]}}}}. "
                f"If this artifact was extracted, check decision-table-guide.md or care-pathway extraction guidance."
            )
        
        # Build pathway ID
        pathway_id = self.artifact_id
        
        # Build useContext (population definition)
        use_context = []
        topic_display = self.topic_id.replace('-', ' ').title()
        use_context.append({
            "code": {
                "system": "http://terminology.hl7.org/CodeSystem/usage-context-type",
                "code": "focus"
            },
            "valueCodeableConcept": {
                "text": topic_display
            }
        })
        
        # Validate phases have required 'id' field
        if phases and not all('id' in phase for phase in phases):
            missing_ids = [i for i, phase in enumerate(phases) if 'id' not in phase]
            raise ValueError(
                f"Care pathway phases at indices {missing_ids} are missing required 'id' field. "
                f"Expected structure: {{id: 'phase-id', code: 'Phase Title', description: '...', substeps: []}}. "
                f"Phase keys found: {[list(phases[i].keys()) for i in missing_ids[:3]]}"
            )
        
        # Build actions (one per phase/strategy)
        actions = []
        for idx, phase in enumerate(phases):
            phase_id = phase['id']
            strategy_id = f"{pathway_id}-{phase_id}-strategy"
            
            action = {
                "id": phase_id,
                "title": phase.get('code', phase_id),
                "description": phase.get('description', ''),
                "definitionCanonical": self.build_canonical_url("PlanDefinition", strategy_id)
            }
            
            # Add relatedAction for sequencing (phase N+1 comes after phase N)
            if idx > 0:
                previous_phase_id = phases[idx - 1]['id']
                action["relatedAction"] = [{
                    "actionId": previous_phase_id,
                    "relationship": "after-end"
                }]
            
            actions.append(action)
        
        # Build Pathway PlanDefinition
        pathway_pd = {
            "resourceType": "PlanDefinition",
            "id": pathway_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-pathwaydefinition"]
            },
            "url": self.build_canonical_url("PlanDefinition", pathway_id),
            "version": metadata.get('version', '1.0.0'),
            "name": self._to_pascal_case(pathway_id),
            "title": metadata.get('title', pathway_id),
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/plan-definition-type",
                    "code": "clinical-protocol"
                }]
            },
            "status": "draft",
            "description": metadata.get('description', ''),
            "useContext": use_context,
            "library": [self.build_canonical_url("Library", self.topic_id)],
            "action": actions
        }
        
        # Add derivation reference if auto-generated
        if metadata.get('auto_generated') and metadata.get('derived_from'):
            pathway_pd["relatedArtifact"] = [{
                "type": "derived-from",
                "label": f"Auto-generated from decision table: {metadata['derived_from'][0]}",
                "extension": [{
                    "url": "http://fhir.org/guides/reasonhealth/StructureDefinition/auto-generated",
                    "valueBoolean": True
                }]
            }]
        
        return pathway_pd

    def build_strategies(
        self,
        care_pathway: Dict[str, Any],
        classifications: Optional[Dict[str, Any]] = None,
        decision_table: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Build Strategy PlanDefinitions (one per phase).
        
        Args:
            care_pathway: L2 care pathway artifact
            classifications: Optional condition classifications from decision table
            decision_table: Optional source decision table
            
        Returns:
            List of PlanDefinition resources (event-driven type)
        """
        sections = care_pathway.get('sections', {})
        phases = sections.get('steps', [])
        
        if not phases:
            raise ValueError(
                f"Care pathway artifact is missing required 'sections.steps' field. "
                f"Found sections keys: {list(sections.keys()) if sections else 'NO SECTIONS'}. "
                f"Expected L2 structure: {{sections: {{steps: [{{id, code, description, substeps}}]}}}}."
            )
        
        strategy_pds = []
        
        for phase in phases:
            strategy_pd = self._build_strategy_for_phase(
                phase, 
                care_pathway, 
                classifications,
                decision_table
            )
            strategy_pds.append(strategy_pd)
        
        return strategy_pds

    def _build_strategy_for_phase(
        self,
        phase: Dict[str, Any],
        care_pathway: Dict[str, Any],
        classifications: Optional[Dict[str, Any]],
        decision_table: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build single Strategy PlanDefinition for a phase.
        
        Args:
            phase: Phase/step dictionary from care pathway
            care_pathway: Full care pathway artifact
            classifications: Optional condition classifications
            decision_table: Optional source decision table
            
        Returns:
            PlanDefinition resource (event-driven type)
        """
        phase_id = phase['id']
        strategy_id = f"{self.artifact_id}-{phase_id}-strategy"
        
        # Get substeps (events) for this phase
        substeps = phase.get('substeps', [])
        
        # Validate substeps have required L2 fields (not FHIR fields!)
        if substeps and not decision_table:
            for idx, substep in enumerate(substeps):
                if 'event' not in substep:
                    raise ValueError(
                        f"Phase '{phase_id}' substep at index {idx} is missing required 'event' field. "
                        f"Substep keys found: {list(substep.keys())}. "
                        f"Expected L2 schema: {{substep: '1.1', description: '...', event: 'e1'}}. "
                        f"L2 is FHIR-agnostic - use event references, not fhir_definition_canonical."
                    )
        
        # If no substeps but decision_table provided, derive from events in this phase
        if not substeps and decision_table:
            events = decision_table.get('sections', {}).get('events', [])
            # Filter events that belong to this phase
            phase_events = [e for e in events if e.get('phase') == phase_id]
            # Convert events to substep format
            substeps = []
            for event in phase_events:
                event_id = event.get('id', '')
                substeps.append({
                    'id': event_id,
                    'event_ref': event_id,
                    'code': event.get('label', event_id),
                    'description': event.get('description', ''),
                    # Will construct canonical URL in action building below
                })
        
        # Build actions (references to Recommendation PlanDefinitions)
        # Construct FHIR canonical URLs from L2 event references
        actions = []
        
        # Determine source decision table for event resolution
        source_decision_table = care_pathway.get('decision_table') or self.decision_table_id
        
        for substep in substeps:
            # L2 uses 'event' field to reference decision table events
            # Formalize constructs FHIR canonical URLs from these L2 references
            event_id = substep.get('event')
            substep_decision_table = substep.get('decision_table') or source_decision_table
            
            if not event_id:
                raise ValueError(
                    f"Phase '{phase_id}' substep is missing 'event' field. "
                    f"Substep: {substep}. L2 requires event references, not FHIR URLs."
                )
            
            # Construct PlanDefinition ID from decision table + event
            if substep_decision_table:
                action_id = f"{substep_decision_table}-{event_id}"
            else:
                # Fallback: just use event ID (may not resolve correctly)
                action_id = event_id
            
            # Build FHIR canonical URL
            canonical_url = self.build_canonical_url("PlanDefinition", action_id)
            
            action = {
                "id": action_id,
                "title": substep.get('code', action_id),
                "description": substep.get('description', ''),
                "definitionCanonical": canonical_url
            }
            
            actions.append(action)
        
        # Get strategy-level conditions (phase entry gates)
        strategy_conditions = []
        if classifications and self.hoister:
            strategy_conditions = self.hoister.get_strategy_conditions(classifications, phase_id)
        
        # Build Strategy PlanDefinition
        strategy_pd = {
            "resourceType": "PlanDefinition",
            "id": strategy_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-strategydefinition"]
            },
            "url": self.build_canonical_url("PlanDefinition", strategy_id),
            "version": care_pathway.get('metadata', {}).get('version', '1.0.0'),
            "name": self._to_pascal_case(strategy_id),
            "title": f"{phase.get('code', phase_id)} Strategy",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/plan-definition-type",
                    "code": "event-driven"
                }]
            },
            "status": "draft",
            "description": phase.get('description', f"Strategy for {phase.get('code', phase_id)} phase"),
            "library": [self.build_canonical_url("Library", self.topic_id)],
            "action": actions
        }
        
        # Add strategy-level conditions (phase entry gates)
        if strategy_conditions:
            strategy_pd["goal"] = [{
                "description": {"text": f"Phase entry requirements for {phase.get('code', phase_id)}"},
                "condition": [
                    self.build_condition_element(cond_id)
                    for cond_id in strategy_conditions
                ]
            }]
        
        return strategy_pd
