"""Strategy generation from care-pathway parent-child relationships.

Derives Strategy PlanDefinitions from care-pathway parent_id relationships,
enabling 3-level FHIR hierarchy: Pathway → Strategy → Recommendation.
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def _alignment_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return the care-pathway steps that should align to decision-table phases.

    A single top-level root with child phases is structural orchestration, not a
    clinical phase that must appear in the paired decision-table phase model.
    In that common shape, align the decision table against the root's child
    pathway nodes. Otherwise, align against the top-level pathway nodes
    directly.
    """

    top_level_steps = [step for step in steps if step.get('parent_id') is None]
    if len(top_level_steps) != 1:
        return top_level_steps

    root_step = top_level_steps[0]
    child_steps = [step for step in steps if step.get('parent_id') == root_step['id']]
    return child_steps or top_level_steps


def derive_strategies_from_pathway(care_pathway: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract strategy candidates from care-pathway nodes.
    
    Uses care-pathway hierarchy to identify node groupings that may warrant
    separate strategy PlanDefinitions at L3:
    - Pathway level: orchestration, sequencing
    - Strategy level: optional grouped sub-workflows
    - Recommendation level: decision logic
    
    Args:
        care_pathway: L2 care-pathway artifact with phases and parent relationships
        
    Returns:
        List of strategy candidate definitions, each containing:
        - id: strategy ID
        - label: human-readable label
        - description: clinical description
        - actor: responsible actor
        - phases: list of aligned pathway node IDs included
        - child_phases: list of child pathway node IDs
        - order: workflow sequence order
    """
    
    strategies = []
    steps = care_pathway.get('sections', {}).get('steps', [])

    top_level_steps = [step for step in steps if step.get('parent_id') is None]
    step_children = {
        step['id']: [child for child in steps if child.get('parent_id') == step['id']]
        for step in steps
    }

    # If there is a single umbrella root with child pathway nodes, treat the
    # root as pathway orchestration and use the children as strategy candidates.
    # This is still a heuristic: downstream formalize decides whether the
    # resulting candidates are useful enough to materialize as strategies.
    if len(top_level_steps) == 1 and step_children.get(top_level_steps[0]['id']):
        root_step = top_level_steps[0]
        strategy_seed_steps = step_children[root_step['id']]
        parent_phase_id = root_step['id']
    else:
        strategy_seed_steps = top_level_steps
        parent_phase_id = None

    for step in strategy_seed_steps:
        step_id = step['id']
        children = step_children.get(step_id, [])

        strategy = {
            'id': step_id,
            'label': step.get('label', step_id),
            'description': step.get('description', ''),
            'actor': step.get('actor'),
            'order': step.get('order', 0),
            'phases': [step_id] + [c['id'] for c in children],
            'child_phases': [c['id'] for c in children],
            'parent_phase': parent_phase_id,
            'transitions': []
        }

        strategies.append(strategy)
    
    logger.info(f"Derived {len(strategies)} strategies from care-pathway")
    logger.debug(f"Strategies: {[s['id'] for s in strategies]}")
    
    return strategies


def derive_strategy_transitions(care_pathway: Dict[str, Any], 
                                 strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract transition relationships from care-pathway.
    
    Maps care-pathway transitions to strategy-level transitions
    by finding the strategy containing each transition's target phase.
    
    Args:
        care_pathway: L2 care-pathway artifact with transitions
        strategies: Derived strategies from care-pathway
        
    Returns:
        List of updated strategies with transition information
    """
    
    # Build mapping of phase ID to strategy
    phase_to_strategy = {}
    for strategy in strategies:
        for phase_id in strategy['phases']:
            phase_to_strategy[phase_id] = strategy['id']
    
    transitions = care_pathway.get('sections', {}).get('transitions', [])
    
    # Process each transition
    for transition in transitions:
        from_phase = transition['from_id']
        to_phase = transition['to_id']
        description = transition.get('description', '')
        
        # Find the strategy containing the from_phase
        from_strategy_id = phase_to_strategy.get(from_phase)
        to_strategy_id = phase_to_strategy.get(to_phase)
        
        if not from_strategy_id or not to_strategy_id:
            logger.warning(f"Transition {from_phase}→{to_phase} references unknown phase")
            continue
        
        # Only record if transitioning between different strategies
        # (transitions within same strategy are handled internally)
        if from_strategy_id != to_strategy_id:
            # Find strategy and add transition
            strategy = next(
                (s for s in strategies if s['id'] == from_strategy_id), 
                None
            )
            if strategy:
                strategy['transitions'].append({
                    'actionId': to_strategy_id,
                    'relationship': 'before-start',
                    'description': description
                })
    
    return strategies


def validate_pathway_decision_table_alignment(
    care_pathway: Dict[str, Any], 
    decision_table: Dict[str, Any],
    strict: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """Validate alignment between care-pathway phases and decision-table phases.
    
    Checks:
    1. All pathway top-level phases exist in decision-table
    2. No orphaned events (events referencing unknown phases)
    3. No empty phases (top-level phases with no mapped events)
    
    Args:
        care_pathway: L2 care-pathway artifact
        decision_table: L2 decision-table artifact
        strict: If True, raise on errors; if False, return issues list
        
    Returns:
        Dictionary with keys:
        - errors: List of critical issues (phase mismatch)
        - warnings: List of non-critical issues (empty phases)
        - info: List of informational messages
    """
    
    issues = {
        'errors': [],
        'warnings': [],
        'info': []
    }
    
    # Get all phases
    dt_phases = {
        phase['id']: phase
        for phase in decision_table.get('sections', {}).get('pathway_phases', [])
    }
    
    all_cp_steps = care_pathway.get('sections', {}).get('steps', [])
    cp_steps = {
        step['id']: step
        for step in all_cp_steps
    }
    aligned_steps = _alignment_steps(all_cp_steps)
    
    # Get all events and group by phase
    events_by_phase = {}
    for event in decision_table.get('sections', {}).get('events', []):
        phase = event.get('phase')
        if phase not in events_by_phase:
            events_by_phase[phase] = []
        events_by_phase[phase].append(event)
    
    # Check 1: All alignment-relevant pathway phases should be in decision-table.
    # A single top-level root with child phases is structural only and is not
    # required to appear in the decision-table phase model.
    for cp_step in aligned_steps:
        cp_step_id = cp_step['id']
        if cp_step_id not in dt_phases:
            issues['errors'].append({
                'type': 'phase_mismatch',
                'phase_id': cp_step_id,
                'message': f"Phase '{cp_step_id}' defined in care-pathway "
                          f"but not in decision-table phases"
            })
    
    # Check 2: No orphaned events
    for event_phase, events in events_by_phase.items():
        if event_phase not in cp_steps and event_phase not in dt_phases:
            for event in events:
                issues['errors'].append({
                    'type': 'orphaned_event',
                    'event_id': event['id'],
                    'phase': event_phase,
                    'message': f"Event '{event['id']}' references unknown phase '{event_phase}'"
                })
    
    # Check 3: No empty phases among the alignment-relevant pathway phases.
    for cp_step in aligned_steps:
        cp_step_id = cp_step['id']
        event_count = len(events_by_phase.get(cp_step_id, []))
        
        if event_count == 0:
            issues['warnings'].append({
                'type': 'empty_phase',
                'phase_id': cp_step_id,
                'message': f"Phase '{cp_step_id}' has no mapped events "
                          f"(will result in empty nested actions)"
            })
        else:
            issues['info'].append({
                'type': 'phase_ok',
                'phase_id': cp_step_id,
                'event_count': event_count,
                'message': f"Phase '{cp_step_id}' has {event_count} mapped event(s)"
            })
    
    # Handle strict mode
    if strict and issues['errors']:
        error_msgs = '\n'.join([e['message'] for e in issues['errors']])
        raise ValueError(f"Phase alignment validation failed:\n{error_msgs}")
    
    # Log results
    if issues['errors']:
        logger.error(f"Found {len(issues['errors'])} alignment errors")
        for error in issues['errors']:
            logger.error(f"  {error['message']}")
    
    if issues['warnings']:
        logger.warning(f"Found {len(issues['warnings'])} alignment warnings")
        for warning in issues['warnings']:
            logger.warning(f"  {warning['message']}")
    
    logger.info(f"Alignment validation: {len(issues['info'])} phases OK")
    
    return issues


def collect_strategy_events(
    strategy: Dict[str, Any],
    decision_table: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Collect all events that belong to a strategy.
    
    A strategy's events are all events whose 'phase' is in the strategy's
    phases list (including both parent phase and child phases).
    
    Args:
        strategy: Strategy definition from derive_strategies_from_pathway()
        decision_table: L2 decision-table artifact
        
    Returns:
        List of events belonging to this strategy
    """
    
    strategy_phases = set(strategy['phases'])
    strategy_events = []
    
    for event in decision_table.get('sections', {}).get('events', []):
        event_phase = event.get('phase')
        
        if event_phase in strategy_phases:
            strategy_events.append(event)
    
    return strategy_events
