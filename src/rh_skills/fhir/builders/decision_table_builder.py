"""Decision table formalization to FHIR PlanDefinition resources.

Generates Recommendation PlanDefinitions (eca-rule) and ActivityDefinitions
from L2 decision table artifacts following CPG-on-FHIR patterns.

Supports state-based action trees with prerequisite hoisting.
"""

from typing import Any, Dict, List, Optional, Set
from .base import FHIRBuilder
from .condition_hoister import ConditionHoister
from .action_tree import hoist_shared_prerequisites


class DecisionTableBuilder(FHIRBuilder):
    """Builds FHIR resources from L2 decision table artifacts.
    
    Generates:
    - One Recommendation PlanDefinition per event (eca-rule type)
    - One ActivityDefinition per unique action
    - Registers conditions with ConditionMerger for topic-level Library
    """

    def __init__(
        self,
        topic_id: str,
        artifact_id: str,
        condition_merger=None,
        *,
        library_id: str | None = None,
        base_url: str = "http://fhir.org/guides/reasonhealth",
        version: str = "1.0.0",
        status: str = "draft",
    ):
        """Initialize builder.
        
        Args:
            topic_id: Topic identifier for canonical URLs
            artifact_id: Decision table artifact identifier
            condition_merger: Optional ConditionMerger for topic-level deduplication
        """
        super().__init__(topic_id, base_url, library_id=library_id, version=version, status=status)
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
        
        Uses state-based action tree with unmet/met branches and prerequisite hoisting
        to avoid duplicating shared conditions across sibling actions.
        
        Args:
            event: Event dictionary from L2 artifact
            rules: Rules for this event
            classifications: Condition classifications
            decision_table: Full decision table for context
            
        Returns:
            PlanDefinition resource (eca-rule type)
        """
        from .action_tree import detect_workflow_state_groups, build_unmet_met_branches
        
        event_id = event['id']
        
        # Build PlanDefinition ID
        pd_id = event.get('fhir_plan_definition_id', f"{self.artifact_id}-{event_id}")
        
        # Check if we have composite states available
        composite_states = decision_table.get('_composite_states', [])
        
        # Detect if this event has a state-based workflow pattern
        state_groups = detect_workflow_state_groups(rules, composite_states) if composite_states else {}
        
        # Build actions - either state-based or flat
        if state_groups:
            # Use unmet/met state branch pattern
            state_name = list(state_groups.keys())[0]
            state_group = state_groups[state_name]
            
            # Build action function for unmet/met branches (captures self, classifications, decision_table)
            def build_action(rule):
                return self._build_simple_action_from_rule(rule)
            
            actions = build_unmet_met_branches(
                state_name=state_name,
                unmet_rules=state_group['unmet_rules'],
                met_rules=state_group['met_rules'],
                build_action_fn=build_action
            )
        else:
            # Fall back to flat actions with standard hoisting
            actions = self._build_state_based_actions(rules, classifications, decision_table)
            # Hoist shared prerequisites among sibling actions
            actions = hoist_shared_prerequisites(actions)
        
        # Build PlanDefinition
        plan_definition = {
            "resourceType": "PlanDefinition",
            "id": pd_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-recommendationdefinition"]
            },
            "url": self.build_canonical_url("PlanDefinition", pd_id),
            "version": decision_table.get('version', self.version),
            "name": self._to_pascal_case(pd_id),
            "title": event.get('label', event_id),
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/plan-definition-type",
                    "code": "eca-rule"
                }]
            },
            "status": self.status,
            "description": event.get('description', f"Recommendation for {event.get('label', event_id)}"),
            "library": [self.build_canonical_url("Library", self.library_id)],
            "action": actions
        }
        
        # Add source reference
        plan_definition["relatedArtifact"] = [{
            "type": "derived-from",
            "label": f"Decision table: {self.artifact_id}",
            "citation": decision_table.get('citation', '')
        }]
        
        return plan_definition
    
    def _extract_shared_prerequisites(self, rules: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract conditions that are shared across ALL rules with the SAME value.
        
        Args:
            rules: List of rules for this event
            
        Returns:
            Dictionary of condition_id -> value for truly shared prerequisites
        """
        if not rules:
            return {}
        
        # Build set of (condition_id, value) tuples for each rule
        rule_conditions = []
        for rule in rules:
            when_clause = rule.get('when', {})
            if not when_clause or not isinstance(when_clause, dict):
                # Rule with empty when clause - can't have shared prerequisites
                return {}
            
            rule_cond_set = set((cond_id, value) for cond_id, value in when_clause.items())
            rule_conditions.append(rule_cond_set)
        
        if not rule_conditions:
            return {}
        
        # Find intersection - conditions present with same value in ALL rules
        shared_cond_tuples = rule_conditions[0].intersection(*rule_conditions[1:])
        
        # Convert back to dict
        return dict(shared_cond_tuples)
    
    def _build_state_based_actions(
        self,
        rules: List[Dict[str, Any]],
        classifications: Dict[str, Any],
        decision_table: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build state-based action tree from rules.
        
        Builds actions directly from rules with their when conditions,
        then applies prerequisite hoisting to remove duplicates.
        
        Args:
            rules: Rules for a single event
            classifications: Condition classifications
            decision_table: Full decision table for context
            
        Returns:
            List of actions with state-based branching
        """
        actions = []
        
        # Build one action per rule with full when conditions
        for rule in rules:
            action = self._build_simple_action_from_rule(rule)
            actions.append(action)
        
        # Prerequisite hoisting will remove shared conditions
        # (done at the caller level in _build_recommendation_for_event)
        
        return actions
    
    def _build_simple_action_from_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Build action directly from rule with all its when conditions.
        
        Args:
            rule: L2 rule dictionary
            
        Returns:
            PlanDefinition.action structure
        """
        rule_id = rule.get('id')
        if not rule_id:
            rule_id = 'rule'
        then_actions = rule.get('then', [])
        when_conditions = rule.get('when', {})
        
        # Build action structure
        action = {
            "id": rule_id,
            "title": rule.get('name', rule_id),
            "description": rule.get('rationale', '')
        }
        
        # Add ALL when conditions from the rule
        if when_conditions and isinstance(when_conditions, dict):
            conditions = []
            for cond_id, value in when_conditions.items():
                conditions.append(self.build_condition_element(cond_id, value))
            
            if conditions:
                action["condition"] = conditions
        
        # Handle then[] array
        if then_actions and isinstance(then_actions, list):
            if len(then_actions) == 1:
                # Single action - add definitionCanonical directly
                action["definitionCanonical"] = self.build_canonical_url(
                    "ActivityDefinition", then_actions[0]
                )
            else:
                # Multiple actions - create child action[] WITHOUT definitionCanonical on parent
                # This follows the rule: action may branch OR be executable, but not both
                child_actions = []
                for action_ref in then_actions:
                    child_actions.append({
                        "id": f"{rule_id}-{action_ref}",
                        "title": str(action_ref).replace('-', ' ').title(),
                        "definitionCanonical": self.build_canonical_url(
                            "ActivityDefinition", action_ref
                        )
                    })
                action["action"] = child_actions
        
        # Add documentation if present
        if rule.get('evidence'):
            action["documentation"] = [{
                "type": "documentation",
                "label": rule['evidence'].get('source_locator', 'Evidence')
            }]
        
        return action
    
    def _group_rules_by_state(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group rules by their workflow state (when clause).
        
        Args:
            rules: List of rules for a single event
            
        Returns:
            List of state groups with shared when conditions
        """
        state_groups = []
        state_counter = 0
        
        for rule in rules:
            when_clause = rule.get('when', {})
            
            # Normalize empty when to empty dict
            if not when_clause or not isinstance(when_clause, dict):
                when_clause = {}
            
            # Find existing group with same when clause
            found_group = None
            for group in state_groups:
                if group['when_conditions'] == when_clause:
                    found_group = group
                    break
            
            if found_group:
                found_group['rules'].append(rule)
            else:
                state_counter += 1
                state_groups.append({
                    'state_id': state_counter,
                    'when_conditions': when_clause,
                    'rules': [rule]
                })
        
        return state_groups
    
    def _build_action_from_rule(
        self,
        rule: Dict[str, Any],
        classifications: Dict[str, Any],
        shared_when_conditions: Dict[str, str]
    ) -> Dict[str, Any]:
        """Build single action from a rule.
        
        Args:
            rule: L2 rule dictionary
            classifications: Condition classifications
            shared_when_conditions: When conditions already handled by parent
            
        Returns:
            PlanDefinition.action structure
        """
        rule_id = rule.get('id')
        if not rule_id:
            rule_id = 'rule'
        then_actions = rule.get('then', [])
        when_conditions = rule.get('when', {})
        
        # Build action structure
        action = {
            "id": rule_id,
            "title": rule.get('name', rule_id),
            "description": rule.get('rationale', '')
        }
        
        # Add when conditions directly from the rule (incremental ones will be handled by hoisting later)
        if when_conditions and isinstance(when_conditions, dict):
            conditions = []
            for cond_id, value in when_conditions.items():
                # Skip shared conditions (already on parent)
                if cond_id in shared_when_conditions and shared_when_conditions[cond_id] == value:
                    continue
                
                conditions.append(self.build_condition_element(cond_id, value))
            
            if conditions:
                action["condition"] = conditions
        
        # Handle then[] array
        if then_actions and isinstance(then_actions, list):
            if len(then_actions) == 1:
                # Single action - add definitionCanonical directly
                action["definitionCanonical"] = self.build_canonical_url(
                    "ActivityDefinition", then_actions[0]
                )
            else:
                # Multiple actions - create child action[] WITHOUT definitionCanonical on parent
                # This follows the rule: action may branch OR be executable, but not both
                child_actions = []
                for action_ref in then_actions:
                    child_actions.append({
                        "id": f"{rule_id}-{action_ref}",
                        "title": str(action_ref).replace('-', ' ').title(),
                        "definitionCanonical": self.build_canonical_url(
                            "ActivityDefinition", action_ref
                        )
                    })
                action["action"] = child_actions
        
        # Add documentation if present
        if rule.get('evidence'):
            action["documentation"] = [{
                "type": "documentation",
                "label": rule['evidence'].get('source_locator', 'Evidence')
            }]
        
        return action

    def _build_actions_from_rule(self, rule: Dict[str, Any], classifications: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build PlanDefinition.action entries from a rule's then[] array.
        
        Args:
            rule: L2 rule with then[] array of action IDs
            classifications: Condition classifications
            
        Returns:
            List of PlanDefinition.action structures (one per action in then[])
        """
        rule_id = rule.get('id')
        if not rule_id:
            rule_id = 'rule'
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
        
        # Map L2 action type to FHIR request resource type
        action_type = str(action.get('kind') or '').strip().lower()
        kind_mapping = {
            'order': 'ServiceRequest',
            'assessment': 'ServiceRequest',
            'diagnostic-test': 'ServiceRequest',
            'task': 'Task',
            'communication': 'CommunicationRequest',
            'procedure': 'Procedure',
            'medication': 'MedicationRequest',
        }
        kind = kind_mapping.get(action_type, 'ServiceRequest')
        title = action.get('label') or action.get('code') or action_id
        
        activity_definition = {
            "resourceType": "ActivityDefinition",
            "id": action_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-computableactivity"]
            },
            "url": self.build_canonical_url("ActivityDefinition", action_id),
            "version": decision_table.get('version', self.version),
            "name": self._to_pascal_case(action_id),
            "title": title,
            "status": self.status,
            "description": action.get('description', title),
            "kind": kind
        }
        
        if action.get("do_not_perform") is True:
            activity_definition["doNotPerform"] = True

        if kind in {"ServiceRequest", "CommunicationRequest", "MedicationRequest"}:
            activity_definition["intent"] = str(action.get("intent") or "proposal")
        
        return activity_definition
