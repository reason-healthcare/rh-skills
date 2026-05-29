"""Decision table formalization to FHIR PlanDefinition resources.

Generates Recommendation PlanDefinitions (eca-rule) and ActivityDefinitions
from L2 decision table artifacts following CPG-on-FHIR patterns.
"""

from typing import Any, Dict, List, Optional
from .base import FHIRBuilder
from .condition_hoister import ConditionHoister


class DecisionTableBuilder(FHIRBuilder):
    """Builds FHIR resources from L2 decision table artifacts.
    
    Generates:
    - One Recommendation PlanDefinition per event (eca-rule type)
    - One ActivityDefinition per unique action
    - Registers conditions with ConditionMerger for topic-level Library
    """

    def __init__(self, topic_id: str, artifact_id: str, condition_merger=None):
        """Initialize builder.
        
        Args:
            topic_id: Topic identifier for canonical URLs
            artifact_id: Decision table artifact identifier
            condition_merger: Optional ConditionMerger for topic-level deduplication
        """
        super().__init__(topic_id)
        self.artifact_id = artifact_id
        self.condition_merger = condition_merger
        self.hoister = ConditionHoister(topic_id)

    def build_all_resources(self, decision_table: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Build all FHIR resources from decision table.
        
        Args:
            decision_table: L2 decision table artifact
            
        Returns:
            Dictionary with keys: 'PlanDefinition', 'ActivityDefinition'
        """
        # Validate structure
        self.validate_artifact_structure(decision_table, ['events', 'conditions', 'actions', 'rules'])
        
        sections = decision_table['sections']
        
        # Register conditions with merger (if provided)
        if self.condition_merger:
            self.condition_merger.register_conditions(self.artifact_id, sections['conditions'])
        
        # Analyze condition hoisting
        classifications = self.hoister.analyze_decision_table(decision_table)
        
        # Build resources
        plan_definitions = self.build_recommendations(decision_table, classifications)
        activity_definitions = self.build_activity_definitions(decision_table)
        
        return {
            'PlanDefinition': plan_definitions,
            'ActivityDefinition': activity_definitions
        }

    def build_recommendations(self, decision_table: Dict[str, Any], classifications: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build Recommendation PlanDefinitions (one per event).
        
        Args:
            decision_table: L2 decision table artifact
            classifications: Condition classifications from ConditionHoister
            
        Returns:
            List of PlanDefinition resources (eca-rule type)
        """
        sections = decision_table['sections']
        events = sections['events']
        rules = sections['rules']
        
        # Group rules by event
        rules_by_event = {}
        for rule in rules:
            event_id = rule['event']
            if event_id not in rules_by_event:
                rules_by_event[event_id] = []
            rules_by_event[event_id].append(rule)
        
        plan_definitions = []
        
        for event in events:
            event_id = event['id']
            event_rules = rules_by_event.get(event_id, [])
            
            if not event_rules:
                # No rules for this event (pure data collection, not decision logic)
                continue
            
            pd = self._build_recommendation_for_event(event, event_rules, classifications, decision_table)
            plan_definitions.append(pd)
        
        return plan_definitions

    def _build_recommendation_for_event(
        self, 
        event: Dict[str, Any], 
        rules: List[Dict[str, Any]], 
        classifications: Dict[str, Any],
        decision_table: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build single Recommendation PlanDefinition for an event.
        
        Args:
            event: Event dictionary from L2 artifact
            rules: Rules for this event
            classifications: Condition classifications
            decision_table: Full decision table for context
            
        Returns:
            PlanDefinition resource (eca-rule type)
        """
        event_id = event['id']
        
        # Get recommendation-level conditions (pre-requisites for all rules)
        rec_conditions = self.hoister.get_recommendation_conditions(classifications, event_id)
        
        # Build PlanDefinition ID
        pd_id = event.get('fhir_plan_definition_id', f"{self.artifact_id}-{event_id}")
        
        # Build actions (one or more per rule, based on then[] array)
        actions = []
        for rule in rules:
            # Each rule can have multiple actions in its then[] array
            rule_actions = self._build_actions_from_rule(rule, classifications)
            actions.extend(rule_actions)
        
        # Build PlanDefinition
        plan_definition = {
            "resourceType": "PlanDefinition",
            "id": pd_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-recommendationdefinition"]
            },
            "url": self.build_canonical_url("PlanDefinition", pd_id),
            "version": decision_table.get('version', '1.0.0'),
            "name": self._to_pascal_case(pd_id),
            "title": event.get('code', event_id),
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/plan-definition-type",
                    "code": "eca-rule"
                }]
            },
            "status": "draft",
            "description": event.get('description', f"Recommendation for {event.get('code', event_id)}"),
            "library": [self.build_canonical_url("Library", self.topic_id)],
            "action": actions
        }
        
        # Add recommendation-level conditions (if any)
        if rec_conditions:
            plan_definition["goal"] = [{
                "description": {"text": "Pre-requisites for this recommendation"},
                "condition": [
                    self.build_condition_element(cond_id)
                    for cond_id in rec_conditions
                ]
            }]
        
        # Add source reference
        plan_definition["relatedArtifact"] = [{
            "type": "derived-from",
            "label": f"Decision table: {self.artifact_id}",
            "citation": decision_table.get('citation', '')
        }]
        
        return plan_definition

    def _build_actions_from_rule(self, rule: Dict[str, Any], classifications: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build PlanDefinition.action entries from a rule's then[] array.
        
        Args:
            rule: L2 rule with then[] array of action IDs
            classifications: Condition classifications
            
        Returns:
            List of PlanDefinition.action structures (one per action in then[])
        """
        rule_id = rule['rule_id']  # Use correct L2 schema field
        then_actions = rule['then']  # L2 schema: array of action IDs
        
        # Get action-level conditions (branch criteria)
        action_conditions = self.hoister.get_action_conditions(classifications, rule)
        
        # Build one action entry per then[] item
        actions = []
        for action_id in then_actions:
            action = {
                "id": f"{rule_id}-{action_id}" if len(then_actions) > 1 else rule_id,
                "title": rule.get('rationale', ''),
                "definitionCanonical": self.build_canonical_url("ActivityDefinition", action_id)
            }
            
            # Add action-level conditions (if any)
            if action_conditions:
                action["condition"] = [
                    self.build_condition_element(cond_id)
                    for cond_id in action_conditions
                ]
            
            # Add documentation
            if rule.get('evidence'):
                action["documentation"] = [{
                    "type": "documentation",
                    "label": rule['evidence'].get('source_locator', 'Evidence')
                }]
            
            actions.append(action)
        
        return actions

    def build_activity_definitions(self, decision_table: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build ActivityDefinitions from decision table actions.
        
        Args:
            decision_table: L2 decision table artifact
            
        Returns:
            List of ActivityDefinition resources
        """
        sections = decision_table['sections']
        actions = sections.get('actions', [])
        
        activity_definitions = []
        
        for action in actions:
            ad = self._build_activity_definition(action, decision_table)
            activity_definitions.append(ad)
        
        return activity_definitions

    def _build_activity_definition(self, action: Dict[str, Any], decision_table: Dict[str, Any]) -> Dict[str, Any]:
        """Build single ActivityDefinition.
        
        Args:
            action: Action dictionary from L2 artifact
            decision_table: Full decision table for context
            
        Returns:
            ActivityDefinition resource
        """
        action_id = action['id']
        
        # Map L2 action_type to FHIR request resource type
        action_type = action.get('type', 'task')
        kind_mapping = {
            'order': 'ServiceRequest',
            'assessment': 'Observation',
            'task': 'Task',
            'communication': 'Communication',
            'procedure': 'Procedure'
        }
        kind = kind_mapping.get(action_type, 'Task')
        
        activity_definition = {
            "resourceType": "ActivityDefinition",
            "id": action_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-computableactivity"]
            },
            "url": self.build_canonical_url("ActivityDefinition", action_id),
            "version": decision_table.get('version', '1.0.0'),
            "name": self._to_pascal_case(action_id),
            "title": action.get('code', action_id),
            "status": "draft",
            "description": action.get('description', ''),
            "kind": kind
        }
        
        # Add intent
        if kind == 'ServiceRequest':
            activity_definition["intent"] = "proposal"
        
        return activity_definition
