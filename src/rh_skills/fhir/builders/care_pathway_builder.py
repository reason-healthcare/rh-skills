"""Care pathway formalization to FHIR PlanDefinition resources.

Generates Pathway PlanDefinitions (clinical-protocol) and Strategy PlanDefinitions
(event-driven) from L2 care pathway artifacts following CPG-on-FHIR patterns.
"""

from typing import Any, Dict, List, Optional
import logging
from .base import FHIRBuilder
from .condition_hoister import ConditionHoister
from .strategy_builder import (
    derive_strategies_from_pathway,
    derive_strategy_transitions,
    validate_pathway_decision_table_alignment,
    collect_strategy_events
)

logger = logging.getLogger(__name__)


class CarePathwayBuilder(FHIRBuilder):
    """Builds FHIR resources from L2 care pathway artifacts.
    
    Generates:
    - One Pathway PlanDefinition (clinical-protocol type)
    - One Strategy PlanDefinition per phase (event-driven type)
    - References Recommendation PlanDefinitions from decision tables
    """

    def __init__(
        self,
        topic_id: str,
        artifact_id: str,
        decision_table_id: Optional[str] = None,
        *,
        library_id: str | None = None,
        base_url: str = "http://fhir.org/guides/reasonhealth",
        version: str = "1.0.0",
        status: str = "draft",
    ):
        """Initialize builder.
        
        Args:
            topic_id: Topic identifier for canonical URLs
            artifact_id: Care pathway artifact identifier
            decision_table_id: Optional source decision table ID (for auto-generated pathways)
        """
        super().__init__(topic_id, base_url, library_id=library_id, version=version, status=status)
        self.artifact_id = artifact_id
        self.decision_table_id = decision_table_id
        self.hoister = ConditionHoister(topic_id) if decision_table_id else None

    def build_all_resources(
        self, 
        care_pathway: Dict[str, Any],
        decision_table: Optional[Dict[str, Any]] = None,
        generate_strategies: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Build all FHIR resources from care pathway.
        
        Args:
            care_pathway: L2 care pathway artifact
            decision_table: Optional source decision table (for auto-generated pathways)
            generate_strategies: If True, generate Strategy PlanDefinitions (3-level)
            
        Returns:
            Dictionary with keys: 'PlanDefinition' (pathway + optional strategy PDs)
        """
        # Care pathway artifacts have metadata and sections at top level
        # Validation happens in build methods as needed
        
        # Check if auto-generated
        metadata = care_pathway.get('metadata', {})
        is_auto_generated = metadata.get('auto_generated', False)
        
        # Validate phase alignment if generating strategies
        if generate_strategies and decision_table:
            alignment_issues = validate_pathway_decision_table_alignment(
                care_pathway, 
                decision_table,
                strict=False
            )
            # Log warnings but don't fail
            for warning in alignment_issues.get('warnings', []):
                logger.warning(f"Phase alignment: {warning['message']}")
        
        # Analyze conditions if decision table provided
        classifications = None
        pathway_evidence_claim_index = self.build_evidence_claim_index(care_pathway)
        decision_table_claim_index = self.build_evidence_claim_index(decision_table) if decision_table else {}
        if decision_table and self.hoister:
            classifications = self.hoister.analyze_decision_table(decision_table)
        
        # Build pathway
        if generate_strategies and decision_table:
            # 3-level hierarchy with strategies
            strategies = derive_strategies_from_pathway(care_pathway)
            strategies = derive_strategy_transitions(care_pathway, strategies)
            strategies_with_events = []
            for strategy in strategies:
                strategy_events = collect_strategy_events(strategy, decision_table)
                if strategy_events:
                    enriched = dict(strategy)
                    enriched["_events"] = strategy_events
                    strategies_with_events.append(enriched)

            if not strategies_with_events:
                logger.warning(
                    "Hierarchical care-pathway requested strategy generation, "
                    "but no decision-table events aligned to pathway phases. "
                    "Falling back to flat pathway formalization."
                )
                pathway_pd = self.build_pathway(
                    care_pathway,
                    classifications,
                    decision_table,
                    pathway_evidence_claim_index,
                    decision_table_claim_index,
                )
                result_pds = [pathway_pd]
                return {
                    'PlanDefinition': result_pds
                }
            
            pathway_pd = self.build_pathway_with_strategies(
                care_pathway, 
                strategies_with_events,
                classifications, 
                decision_table,
                pathway_evidence_claim_index,
                decision_table_claim_index,
            )
            
            strategy_pds = self._build_strategy_plan_definitions(
                strategies_with_events, 
                decision_table,
                classifications,
                decision_table_claim_index,
            )
            
            result_pds = [pathway_pd] + strategy_pds
        else:
            # 2-level flat structure (current behavior)
            pathway_pd = self.build_pathway(
                care_pathway,
                classifications,
                decision_table,
                pathway_evidence_claim_index,
                decision_table_claim_index,
            )
            result_pds = [pathway_pd]
        
        return {
            'PlanDefinition': result_pds
        }

    def build_pathway(
        self,
        care_pathway: Dict[str, Any],
        classifications: Optional[Dict[str, Any]] = None,
        decision_table: Optional[Dict[str, Any]] = None,
        evidence_claim_index: Optional[Dict[str, Dict[str, Any]]] = None,
        decision_table_claim_index: Optional[Dict[str, Dict[str, Any]]] = None,
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
        decision_table_rules = decision_table.get('sections', {}).get('rules', []) if decision_table else []
        
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
        
        # Build nested action tree directly (no separate strategy PlanDefinitions)
        actions = []
        for idx, phase in enumerate(phases):
            phase_id = phase['id']
            
            # Build nested actions from substeps
            phase_action = self._build_phase_action(
                phase,
                care_pathway,
                classifications,
                decision_table,
                evidence_claim_index,
                decision_table_claim_index,
                decision_table_rules,
            )
            
            # Add relatedAction for sequencing (phase N+1 comes after phase N)
            if idx > 0:
                previous_phase_id = phases[idx - 1]['id']
                phase_action["relatedAction"] = [{
                    "actionId": previous_phase_id,
                    "relationship": "after-end"
                }]
            
            actions.append(phase_action)
        
        # Build Pathway PlanDefinition
        pathway_pd = {
            "resourceType": "PlanDefinition",
            "id": pathway_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-pathwaydefinition"]
            },
            "url": self.build_canonical_url("PlanDefinition", pathway_id),
            "version": metadata.get('version', self.version),
            "name": self._to_pascal_case(pathway_id),
            "title": metadata.get('title', pathway_id),
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/plan-definition-type",
                    "code": "clinical-protocol"
                }]
            },
            "status": self.status,
            "description": metadata.get('description', ''),
            "useContext": use_context,
            "library": [self.build_canonical_url("Library", self.library_id)],
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
    
    def _build_phase_action(
        self,
        phase: Dict[str, Any],
        care_pathway: Dict[str, Any],
        classifications: Optional[Dict[str, Any]],
        decision_table: Optional[Dict[str, Any]],
        evidence_claim_index: Optional[Dict[str, Dict[str, Any]]],
        decision_table_claim_index: Optional[Dict[str, Dict[str, Any]]],
        decision_table_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build nested action for a pathway phase.
        
        Auto-links events from decision table based on rule.phase field.
        Decision-table rules can optionally declare which phase they belong to:
          rules:
            - id: r1
              event: e1
              phase: planning      # Optional: declares this rule/event belongs to 'planning' phase
        
        Args:
            phase: Phase/step dictionary from care pathway
            care_pathway: Full care pathway artifact
            classifications: Optional condition classifications
            decision_table: Optional source decision table
            
        Returns:
            Action dictionary with nested actions for linked events
        """
        phase_id = phase['id']
        child_actions = []
        
        # If decision table provided, auto-derive linked events by rule.phase field
        if decision_table:
            source_decision_table = care_pathway.get('decision_table') or self.decision_table_id
            rules = decision_table.get('sections', {}).get('rules', [])
            events = decision_table.get('sections', {}).get('events', [])
            
            # Group rules by event to handle multiple branches per event
            rules_by_event = {}
            for rule in rules:
                rule_phase = rule.get('phase')
                if rule_phase == phase_id:
                    event_id = rule.get('event')
                    if not event_id:
                        raise ValueError(
                            f"Rule with phase '{phase_id}' is missing 'event' field. "
                            f"Rule: {rule}. L2 requires event references."
                        )
                    
                    if event_id not in rules_by_event:
                        rules_by_event[event_id] = []
                    rules_by_event[event_id].append(rule)
            
            # For each unique event, create ONE action with branches for each rule
            for event_id, event_rules in rules_by_event.items():
                event_details = next((e for e in events if e.get('id') == event_id), {})
                evidence_ids, strength = self._collect_rule_metadata(event_rules)
                
                # Construct PlanDefinition ID from decision table + event
                if source_decision_table:
                    recommendation_id = f"{source_decision_table}-{event_id}"
                else:
                    recommendation_id = event_id
                
                # Build FHIR canonical URL pointing to the recommendation PlanDefinition
                canonical_url = self.build_canonical_url("PlanDefinition", recommendation_id)
                
                # Create parent action for this event
                event_action = {
                    "id": f"{phase_id}-{event_id}",
                    "title": event_details.get('label') or event_id,
                    "description": event_details.get('description', ''),
                    "definitionCanonical": canonical_url
                }
                event_action = self._apply_recommendation_metadata(
                    event_action,
                    evidence_ids,
                    strength,
                    decision_table_claim_index,
                )
                
                # If multiple rules for same event, create nested branches for each rule
                if len(event_rules) > 1:
                    branches = []
                    for idx, rule in enumerate(event_rules, 1):
                        branch_action = {
                            "id": f"{event_id}-branch-{idx}",
                            "title": f"Branch {idx}: {rule.get('action', event_id)}"
                        }
                        
                        # Add condition from rule's when clause if available
                        when_clause = rule.get('when')
                        if when_clause:
                            # Convert L2 when conditions to FHIR condition
                            condition_expr = self._build_condition_expression(when_clause)
                            if condition_expr:
                                branch_action["condition"] = [condition_expr]
                        
                        # Add reference to action details if available
                        if rule.get('then'):
                            branch_action["description"] = f"Actions: {', '.join(rule.get('then', []))}"
                        
                        branches.append(branch_action)
                    
                    event_action["action"] = branches
                    logger.debug(f"Created event '{event_id}' with {len(branches)} decision branches")
                
                child_actions.append(event_action)
        
        # Build phase action with nested child actions (if any)
        phase_action = {
            "id": phase_id,
            "title": phase.get('label') or phase.get('code') or phase_id,
            "description": phase.get('description', '')
        }
        
        # Only add child actions if any were linked from decision table
        if child_actions:
            phase_action["action"] = child_actions
        
        phase_evidence_ids = phase.get("evidence_traceability_ids") or []
        phase_strength = phase.get("recommendation_strength") or phase.get("strength_of_recommendation")
        phase_action = self._apply_recommendation_metadata(
            phase_action,
            [str(claim_id).strip() for claim_id in phase_evidence_ids if str(claim_id or "").strip()],
            phase_strength if isinstance(phase_strength, str) else str(phase_strength or "").strip() or None,
            evidence_claim_index,
        )
        if decision_table_rules:
            linked_rules = [
                rule
                for rule in decision_table_rules
                if isinstance(rule, dict) and str(rule.get("phase") or "").strip() == phase_id
            ]
            linked_evidence_ids, _linked_strength = self._collect_rule_metadata(linked_rules)
            linked_docs = self.build_evidence_related_artifacts(
                linked_evidence_ids,
                decision_table_claim_index,
            )
            if linked_docs:
                existing_docs = phase_action.get("documentation") or []
                phase_action["documentation"] = [*existing_docs, *linked_docs]
        
        # Add phase-level conditions if available
        if classifications and self.hoister:
            phase_conditions = self.hoister.get_strategy_conditions(classifications, phase_id)
            if phase_conditions:
                phase_action["condition"] = [
                    self.build_condition_element(cond_id)
                    for cond_id in phase_conditions
                ]
        
        return phase_action

    def _collect_rule_metadata(
        self,
        rules: List[Dict[str, Any]],
    ) -> tuple[list[str], str | None]:
        """Collect evidence traceability ids and a shared recommendation strength."""
        evidence_ids: list[str] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            for claim_id in rule.get("evidence_traceability_ids") or []:
                claim = str(claim_id or "").strip()
                if claim:
                    evidence_ids.append(claim)

        unique_ids = list(dict.fromkeys(evidence_ids))
        strength = self.select_strength_of_recommendation(rules)
        return unique_ids, strength

    def _apply_recommendation_metadata(
        self,
        action: Dict[str, Any],
        evidence_ids: list[str],
        strength: str | None,
        evidence_claim_index: Dict[str, Dict[str, Any]] | None,
        *,
        include_strength_extension: bool = False,
    ) -> Dict[str, Any]:
        """Attach evidence citations and optionally recommendation strength to an action."""
        if include_strength_extension:
            recommendation_ext = self.build_strength_of_recommendation_extension(strength)
            if recommendation_ext:
                existing_ext = action.get("extension") or []
                action["extension"] = [*existing_ext, recommendation_ext]

        evidence_related = self.build_evidence_related_artifacts(
            evidence_ids,
            evidence_claim_index,
        )
        if evidence_related:
            existing_docs = action.get("documentation") or []
            action["documentation"] = [*existing_docs, *evidence_related]

        return action
    
    def _build_condition_expression(self, when_clause: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert L2 when clause to FHIR condition element.
        
        Args:
            when_clause: Dictionary of condition expressions
            
        Returns:
            FHIR condition element or None
        """
        if not when_clause:
            return None
        
        # Convert condition dict to readable expression
        # e.g., {'has-established-crs-criteria': True} → "has-established-crs-criteria = true"
        expressions = []
        for key, value in when_clause.items():
            if isinstance(value, bool):
                expr = f"{key} = {str(value).lower()}"
            else:
                expr = f"{key} = {value}"
            expressions.append(expr)
        
        if expressions:
            return {
                "kind": "applicability",
                "language": "text/plain",
                "expression": " AND ".join(expressions) if len(expressions) > 1 else expressions[0]
            }
        
        return None

    def build_pathway_with_strategies(
        self,
        care_pathway: Dict[str, Any],
        strategies: List[Dict[str, Any]],
        classifications: Optional[Dict[str, Any]] = None,
        decision_table: Optional[Dict[str, Any]] = None,
        evidence_claim_index: Optional[Dict[str, Dict[str, Any]]] = None,
        decision_table_claim_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build Pathway PlanDefinition that references Strategy PlanDefinitions.
        
        For 3-level hierarchy: Pathway → Strategy → Recommendation
        
        Args:
            care_pathway: L2 care pathway artifact
            strategies: Derived strategy definitions
            classifications: Optional condition classifications
            decision_table: Optional source decision table
            
        Returns:
            PlanDefinition resource referencing strategies
        """
        # Build the pathway with strategy references instead of direct events
        pathway_pd = self.build_pathway(
            care_pathway,
            classifications,
            decision_table,
            evidence_claim_index,
            decision_table_claim_index,
        )
        
        # Replace nested actions with strategy references
        if strategies:
            strategy_lookup = {
                strategy["id"]: strategy
                for strategy in strategies
                if isinstance(strategy, dict) and strategy.get("id")
            }
            phase_lookup = {
                step["id"]: step
                for step in care_pathway.get("sections", {}).get("steps", [])
                if isinstance(step, dict) and step.get("id")
            }
            decision_table_rules = decision_table.get("sections", {}).get("rules", []) if decision_table else []
            pathway_pd['action'] = [
                {
                    'id': strategy['id'],
                    'title': strategy['label'],
                    'description': strategy['description'],
                    'definitionCanonical': self.build_canonical_url(
                        'PlanDefinition', 
                        f"{self.artifact_id}-{strategy['id']}"
                    ),
                    'relatedAction': strategy.get('transitions', [])
                }
                for strategy in strategies
            ]
            for action in pathway_pd["action"]:
                strategy = strategy_lookup.get(action.get("id"))
                if not strategy:
                    continue
                phase_steps = [
                    phase_lookup.get(str(phase_id).strip())
                    for phase_id in strategy.get("phases", [])
                ]
                phase_rules = [step for step in phase_steps if isinstance(step, dict)]
                evidence_ids, strength = self._collect_rule_metadata(phase_rules)
                self._apply_recommendation_metadata(
                    action,
                    evidence_ids,
                    strength,
                    evidence_claim_index,
                )
                if decision_table:
                    strategy_events = collect_strategy_events(strategy, decision_table)
                    strategy_event_ids = {
                        str(event.get("id") or "").strip()
                        for event in strategy_events
                        if isinstance(event, dict) and str(event.get("id") or "").strip()
                    }
                    linked_rules = [
                        rule
                        for rule in decision_table_rules
                        if isinstance(rule, dict) and str(rule.get("event") or "").strip() in strategy_event_ids
                    ]
                    linked_evidence_ids, _linked_strength = self._collect_rule_metadata(linked_rules)
                    linked_docs = self.build_evidence_related_artifacts(
                        linked_evidence_ids,
                        decision_table_claim_index,
                    )
                    if linked_docs:
                        existing_docs = action.get("documentation") or []
                        action["documentation"] = [*existing_docs, *linked_docs]
        
        return pathway_pd

    def _build_strategy_plan_definitions(
        self,
        strategies: List[Dict[str, Any]],
        decision_table: Dict[str, Any],
        classifications: Optional[Dict[str, Any]] = None,
        decision_table_claim_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Build Strategy PlanDefinitions for each strategy.
        
        Strategy PlanDefinitions are workflow-definition type that group
        related recommendations and encapsulate decision logic for a phase.
        
        Args:
            strategies: Derived strategy definitions
            decision_table: L2 decision-table artifact
            classifications: Optional condition classifications
            
        Returns:
            List of Strategy PlanDefinition resources
        """
        strategy_pds = []
        rules = decision_table.get('sections', {}).get('rules', [])
        rules_by_event: Dict[str, List[Dict[str, Any]]] = {}
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            event_id = str(rule.get('event') or "").strip()
            if not event_id:
                continue
            rules_by_event.setdefault(event_id, []).append(rule)
        
        for strategy in strategies:
            strategy_id = strategy['id']
            
            # Collect events for this strategy
            strategy_events = strategy.get('_events') or collect_strategy_events(strategy, decision_table)
            
            # Build Strategy PlanDefinition
            strategy_pd = {
                'resourceType': 'PlanDefinition',
                'id': f"{self.artifact_id}-{strategy_id}",
                'meta': {
                    'profile': [
                        'http://hl7.org/fhir/uv/cpg/StructureDefinition/cpg-strategydefinition'
                    ]
                },
                'url': self.build_canonical_url(
                    'PlanDefinition', 
                    f"{self.artifact_id}-{strategy_id}"
                ),
                'version': self.version,
                'name': self._to_pascal_case(f"{self.artifact_id}-{strategy_id}"),
                'title': strategy['label'],
                'type': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/plan-definition-type',
                        'code': 'workflow-definition'
                    }]
                },
                'status': self.status,
                'description': strategy['description'],
                'action': []  # Will be populated with recommendation references
            }
            
            # Add actor if specified
            if strategy.get('actor'):
                strategy_pd['meta']['extension'] = [{
                    'url': 'http://hl7.org/fhir/StructureDefinition/workflow-businessProcess',
                    'valueCodeableConcept': {
                        'text': strategy['actor']
                    }
                }]
            
            # Build nested actions for each event
            source_decision_table = self.decision_table_id or 'decision-table'
            
            for event in strategy_events:
                event_id = event['id']
                event_rules = rules_by_event.get(event_id, [])
                evidence_ids, strength = self._collect_rule_metadata(event_rules)
                
                event_action = {
                    'id': event_id,
                    'title': event.get('label', event_id),
                    'description': event.get('description', ''),
                    'definitionCanonical': self.build_canonical_url(
                        'PlanDefinition',
                        f"{source_decision_table}-{event_id}"
                    )
                }
                self._apply_recommendation_metadata(
                    event_action,
                    evidence_ids,
                    strength,
                    decision_table_claim_index,
                )
                
                strategy_pd['action'].append(event_action)
            
            strategy_pds.append(strategy_pd)
        
        logger.info(f"Built {len(strategy_pds)} strategy PlanDefinitions")
        return strategy_pds
    
