"""Condition hoisting algorithm for CPG-on-FHIR formalization.

This module implements automatic condition classification to determine the
appropriate level (pathway-context, strategy, recommendation, action) for
placing conditions in the CPG resource hierarchy.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class ConditionHoister:
    """Analyzes L2 decision tables to classify conditions for optimal placement.
    
    Implements condition hoisting to avoid redundant logic evaluation:
    - Pathway-context: Population-defining conditions (useContext, not actual conditions)
    - Strategy-level: Phase entry gates (used by all events in a phase)
    - Recommendation-level: Event pre-requisites (used by all rules for one event)
    - Action-level: Branch criteria (unique to single rule)
    """

    def __init__(self, topic_id: str):
        """Initialize hoister with topic context.
        
        Args:
            topic_id: Topic identifier for population context detection
        """
        self.topic_id = topic_id

    def analyze_decision_table(self, decision_table: Dict[str, Any]) -> Dict[str, Union[str, Tuple[str, List[str]]]]:
        """Analyze decision table to classify all conditions.
        
        Args:
            decision_table: L2 decision table artifact
            
        Returns:
            Dictionary mapping condition_id to classification:
            - 'pathway-context': Population-defining (useContext)
            - 'strategy': Phase-level (or tuple ('strategy', [phase_ids]))
            - ('recommendation', event_id): Event-level
            - 'action': Rule-level
        """
        sections = decision_table.get('sections', {})
        rules = sections.get('rules', [])
        events = {e['id']: e for e in sections.get('events', [])}
        pathway_phases = sections.get('pathway_phases', [])
        
        # Track condition usage
        condition_usage = defaultdict(lambda: {
            'rules': [],
            'events': set(),
            'phases': set()
        })
        
        for rule in rules:
            rule_id = rule.get('id')
            if not rule_id:
                continue
            event_id = rule.get('event')
            when_clause = rule.get('when', {})
            
            for cond_id in when_clause.keys():
                condition_usage[cond_id]['rules'].append(rule_id)
                condition_usage[cond_id]['events'].add(event_id)
                
                # Track phase if event has phase metadata
                event = events.get(event_id, {})
                phase = event.get('phase')
                if phase:
                    condition_usage[cond_id]['phases'].add(phase)
        
        # Classify each condition
        classifications = {}
        total_events = len(events)
        total_phases = len(pathway_phases) if pathway_phases else 0
        
        for cond_id, usage in condition_usage.items():
            num_events = len(usage['events'])
            num_phases = len(usage['phases'])
            num_rules = len(usage['rules'])
            
            # Check if this is a population-defining condition
            if self._is_population_context(cond_id, decision_table):
                classifications[cond_id] = 'pathway-context'
            
            # Check if used across multiple phases (strategy-level)
            elif num_phases > 1:
                classifications[cond_id] = ('strategy', sorted(list(usage['phases'])))
            
            # Check if used by multiple rules for same event (recommendation-level)
            elif num_events == 1 and num_rules > 1:
                event_id = list(usage['events'])[0]
                classifications[cond_id] = ('recommendation', event_id)
            
            # Otherwise it's action-level (single rule branch criterion)
            else:
                classifications[cond_id] = 'action'
        
        return classifications

    def get_pathway_context_conditions(self, classifications: Dict[str, Any]) -> List[str]:
        """Extract pathway-context conditions from classifications.
        
        Args:
            classifications: Output from analyze_decision_table()
            
        Returns:
            List of condition IDs classified as pathway-context
        """
        return [
            cond_id for cond_id, classification in classifications.items()
            if classification == 'pathway-context'
        ]

    def get_strategy_conditions(self, classifications: Dict[str, Any], phase_id: str) -> List[str]:
        """Extract strategy-level conditions for a specific phase.
        
        Args:
            classifications: Output from analyze_decision_table()
            phase_id: Phase identifier to filter by
            
        Returns:
            List of condition IDs applicable to this phase
        """
        result = []
        for cond_id, classification in classifications.items():
            if isinstance(classification, tuple) and classification[0] == 'strategy':
                phase_ids = classification[1]
                if phase_id in phase_ids:
                    result.append(cond_id)
        return result

    def get_recommendation_conditions(self, classifications: Dict[str, Any], event_id: str) -> List[str]:
        """Extract recommendation-level conditions for a specific event.
        
        Args:
            classifications: Output from analyze_decision_table()
            event_id: Event identifier to filter by
            
        Returns:
            List of condition IDs applicable to this event
        """
        result = []
        for cond_id, classification in classifications.items():
            if isinstance(classification, tuple) and classification[0] == 'recommendation':
                if classification[1] == event_id:
                    result.append(cond_id)
        return result

    def get_action_conditions(self, classifications: Dict[str, Any], rule: Dict[str, Any]) -> List[str]:
        """Extract action-level conditions for a specific rule.
        
        Args:
            classifications: Output from analyze_decision_table()
            rule: Rule dictionary from L2 artifact
            
        Returns:
            List of condition IDs unique to this rule
        """
        result = []
        when_clause = rule.get('when', {})
        
        for cond_id in when_clause.keys():
            if classifications.get(cond_id) == 'action':
                result.append(cond_id)
        
        return result

    def _is_population_context(self, condition_id: str, decision_table: Dict[str, Any]) -> bool:
        """Determine if a condition defines the patient population.
        
        Population-defining conditions are expressed as useContext in Pathway
        PlanDefinitions, not as actual conditions. Examples:
        - has-crs-dx (defines CRS population)
        - has-diabetes-dx (defines diabetes population)
        
        Heuristics:
        1. Condition description mentions "diagnosis" or "has <topic>"
        2. Condition ID matches topic pattern (e.g., has-crs-dx for CRS topic)
        3. Marked in L2 metadata as population_context: true
        
        Args:
            condition_id: Condition identifier
            decision_table: L2 decision table artifact
            
        Returns:
            True if condition should be population context
        """
        # Check explicit metadata flag
        sections = decision_table.get('sections', {})
        conditions = sections.get('conditions', [])
        condition = next((c for c in conditions if c['id'] == condition_id), None)
        
        if condition and condition.get('population_context', False):
            return True

        topic_tokens = [token for token in self.topic_id.split('-') if token]
        topic_phrase = " ".join(topic_tokens)
        topic_acronym = "".join(token[0] for token in topic_tokens if token)
        
        # Heuristic: condition ID contains "has-<topic>-dx" pattern
        # Example: has-crs-dx, has-diabetes-dx, has-hypertension-dx
        if condition_id.startswith('has-') and condition_id.endswith('-dx'):
            topic_fragment = condition_id.replace('has-', '').replace('-dx', '')
            if topic_fragment in self.topic_id:
                return True
            if topic_acronym and topic_fragment == topic_acronym:
                return True
            topic_compact = "".join(topic_tokens)
            if topic_fragment and topic_compact:
                idx = 0
                for char in topic_compact:
                    if idx < len(topic_fragment) and char == topic_fragment[idx]:
                        idx += 1
                if idx == len(topic_fragment):
                    return True

        # Heuristic: condition description mentions "diagnosis of <topic>"
        if condition:
            description = condition.get('description', '').lower()
            if 'diagnosis' in description and topic_phrase in description:
                return True
            if 'diagnosis' in description and topic_acronym and topic_acronym in description:
                return True

        return False

    def generate_hoisting_report(self, decision_table: Dict[str, Any]) -> str:
        """Generate human-readable report of condition classifications.
        
        Useful for CLI --show-hoisting flag.
        
        Args:
            decision_table: L2 decision table artifact
            
        Returns:
            Formatted report string
        """
        classifications = self.analyze_decision_table(decision_table)
        
        # Group by classification type
        by_type = defaultdict(list)
        for cond_id, classification in classifications.items():
            if isinstance(classification, tuple):
                by_type[classification[0]].append((cond_id, classification))
            else:
                by_type[classification].append(cond_id)
        
        lines = ["# Condition Hoisting Analysis\n"]
        
        # Pathway-context
        if 'pathway-context' in by_type:
            lines.append("## Pathway-Context (Population Definition)")
            lines.append("These conditions define who the pathway applies to (useContext):\n")
            for cond_id in by_type['pathway-context']:
                lines.append(f"  - {cond_id}")
            lines.append("")
        
        # Strategy-level
        if 'strategy' in by_type:
            lines.append("## Strategy-Level (Phase Entry Gates)")
            lines.append("These conditions gate entry to specific phases:\n")
            for cond_id, (_, phases) in by_type['strategy']:
                lines.append(f"  - {cond_id} → phases: {', '.join(phases)}")
            lines.append("")
        
        # Recommendation-level
        if 'recommendation' in by_type:
            lines.append("## Recommendation-Level (Event Pre-requisites)")
            lines.append("These conditions apply to all rules for specific events:\n")
            for cond_id, (_, event_id) in by_type['recommendation']:
                lines.append(f"  - {cond_id} → event: {event_id}")
            lines.append("")
        
        # Action-level
        if 'action' in by_type:
            lines.append("## Action-Level (Branch Criteria)")
            lines.append("These conditions are unique to individual rules:\n")
            for cond_id in by_type['action']:
                lines.append(f"  - {cond_id}")
            lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append(f"  - Pathway-context: {len(by_type.get('pathway-context', []))}")
        lines.append(f"  - Strategy-level: {len(by_type.get('strategy', []))}")
        lines.append(f"  - Recommendation-level: {len(by_type.get('recommendation', []))}")
        lines.append(f"  - Action-level: {len(by_type.get('action', []))}")
        
        return '\n'.join(lines)
