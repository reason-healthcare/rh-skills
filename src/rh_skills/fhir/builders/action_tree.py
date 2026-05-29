"""
Action tree utilities for state-based formalization.

Provides prerequisite hoisting, state-based action tree building,
and unmet/met state branch detection for sequential workflows.
"""

from typing import List, Dict, Any, Set, Tuple, Optional


def hoist_shared_prerequisites(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analyze sibling actions and hoist shared conditions to parent.
    
    Example:
    Before:
        action:
          - id: a1, condition: [DiagnosisConfirmed, PurulentPresent]
          - id: a2, condition: [DiagnosisConfirmed, PurulentAbsent]
    
    After:
        condition: [DiagnosisConfirmed]
        action:
          - id: a1, condition: [PurulentPresent]
          - id: a2, condition: [PurulentAbsent]
    
    Args:
        actions: List of sibling action dictionaries
        
    Returns:
        Modified list of actions with parent holding shared conditions
    """
    if not actions or len(actions) < 2:
        return actions
    
    # Recursively hoist in child actions first
    for action in actions:
        if 'action' in action and isinstance(action['action'], list):
            action['action'] = hoist_shared_prerequisites(action['action'])
    
    # Extract conditions from all sibling actions
    action_conditions: List[Set[str]] = []
    for action in actions:
        conditions = action.get('condition', [])
        if not isinstance(conditions, list):
            conditions = []
        
        # Extract expression strings from condition objects
        cond_expressions = set()
        for cond in conditions:
            if isinstance(cond, dict):
                expr = cond.get('expression', {})
                if isinstance(expr, dict):
                    cond_expr = expr.get('expression', '')
                elif isinstance(expr, str):
                    cond_expr = expr
                else:
                    cond_expr = ''
                if cond_expr:
                    cond_expressions.add(cond_expr)
        
        action_conditions.append(cond_expressions)
    
    # Find conditions common to ALL sibling actions
    if not action_conditions:
        return actions
    
    shared_conditions = action_conditions[0].intersection(*action_conditions[1:])
    
    if not shared_conditions:
        return actions
    
    # Collect one example of each shared condition object
    shared_cond_objects = []
    for shared_expr in sorted(shared_conditions):  # Sort for deterministic order
        # Find the first condition object matching this expression
        for action in actions:
            for cond in action.get('condition', []):
                if isinstance(cond, dict):
                    expr = cond.get('expression', {})
                    if isinstance(expr, dict):
                        cond_expr = expr.get('expression', '')
                    elif isinstance(expr, str):
                        cond_expr = expr
                    else:
                        continue
                    
                    if cond_expr == shared_expr:
                        shared_cond_objects.append(cond)
                        break
            if any(c.get('expression', {}).get('expression') == shared_expr for c in shared_cond_objects):
                break
    
    # Remove shared conditions from children
    for action in actions:
        conditions = action.get('condition', [])
        if not isinstance(conditions, list):
            continue
        
        # Filter out shared conditions
        remaining_conditions = []
        for cond in conditions:
            if isinstance(cond, dict):
                expr = cond.get('expression', {})
                if isinstance(expr, dict):
                    cond_expr = expr.get('expression', '')
                elif isinstance(expr, str):
                    cond_expr = expr
                else:
                    cond_expr = ''
                
                if cond_expr and cond_expr not in shared_conditions:
                    remaining_conditions.append(cond)
        
        if remaining_conditions:
            action['condition'] = remaining_conditions
        elif 'condition' in action:
            del action['condition']
    
    # Wrap actions in a parent with shared prerequisites
    parent_wrapper = {
        'id': 'shared-prerequisites',
        'title': 'Shared Prerequisites',
        'condition': shared_cond_objects,
        'action': actions
    }
    
    return [parent_wrapper]


def build_state_based_action_tree(
    rules: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    conditions: Dict[str, Any],
    canonical_base: str
) -> List[Dict[str, Any]]:
    """
    Build nested action tree with state-based branching from decision table rules.
    
    Returns action[] structure with:
    - State-based branches (unmet/met siblings)
    - Hoisted shared prerequisites
    - Executable endpoints at leaves
    
    Args:
        rules: List of L2 decision table rules
        events: List of L2 decision table events
        conditions: Dict of condition_id -> condition definition
        canonical_base: Canonical URL base for references
        
    Returns:
        Nested action tree structure
    """
    # Group rules by event
    rules_by_event: Dict[str, List[Dict[str, Any]]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        event_id = rule.get('event')
        if event_id:
            if event_id not in rules_by_event:
                rules_by_event[event_id] = []
            rules_by_event[event_id].append(rule)
    
    # Build action tree
    actions = []
    
    for event in events:
        if not isinstance(event, dict):
            continue
        
        event_id = event.get('id')
        event_rules = rules_by_event.get(event_id, [])
        
        if not event_rules:
            continue
        
        # Analyze rules for this event
        # Group by workflow state (shared when conditions)
        state_groups = _group_rules_by_workflow_state(event_rules)
        
        # Build nested actions for each state group
        event_actions = []
        for state in state_groups:
            state_action = _build_state_action(state, canonical_base)
            if state_action:
                event_actions.append(state_action)
        
        # Hoist shared prerequisites within this event
        event_actions = hoist_shared_prerequisites(event_actions)
        
        # Create event-level action
        event_action = {
            'id': str(event_id),
            'title': event.get('label', f"Event {event_id}"),
            'description': event.get('description', ''),
        }
        
        if event_actions:
            event_action['action'] = event_actions
        
        actions.append(event_action)
    
    return actions


def _group_rules_by_workflow_state(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group rules by shared workflow state (when conditions).
    
    Args:
        rules: List of rules for a single event
        
    Returns:
        List of state group dicts with shared conditions and rules
    """
    # Simple grouping: each unique when clause is a separate state
    state_groups = []
    
    for rule in rules:
        when_clause = rule.get('when', {})
        
        # Serialize when clause for comparison
        when_key = frozenset(when_clause.items()) if isinstance(when_clause, dict) else frozenset()
        
        # Find existing group or create new
        found_group = None
        for group in state_groups:
            if group['when_key'] == when_key:
                found_group = group
                break
        
        if found_group:
            found_group['rules'].append(rule)
        else:
            state_groups.append({
                'when_key': when_key,
                'when_clause': when_clause,
                'rules': [rule]
            })
    
    return state_groups


def _build_state_action(state: Dict[str, Any], canonical_base: str) -> Dict[str, Any] | None:
    """
    Build action for a workflow state group.
    
    Args:
        state: State group dict with when_clause and rules
        canonical_base: Canonical URL base
        
    Returns:
        Action dict or None
    """
    rules = state.get('rules', [])
    if not rules:
        return None
    
    # Use first rule for base metadata
    first_rule = rules[0]
    rule_id = first_rule.get('id', 'unknown')
    
    action = {
        'id': str(rule_id),
        'title': first_rule.get('name', f"Rule {rule_id}"),
        'description': first_rule.get('rationale', ''),
    }
    
    # Add conditions from when clause
    when_clause = state.get('when_clause', {})
    if when_clause and isinstance(when_clause, dict):
        conditions = []
        for cond_id, value in when_clause.items():
            # Convert to CQL expression
            cql_name = _to_cql_identifier(cond_id)
            
            # Handle polarity
            if value == "false" or value == False:
                expression = f"not {cql_name}"
            else:
                expression = cql_name
            
            conditions.append({
                'kind': 'applicability',
                'expression': {
                    'language': 'text/cql-identifier',
                    'expression': expression
                }
            })
        
        if conditions:
            action['condition'] = conditions
    
    # Add executable actions from then clause
    then_actions = first_rule.get('then', [])
    if then_actions and isinstance(then_actions, list):
        child_actions = []
        for action_ref in then_actions:
            child_actions.append({
                'id': _to_kebab_case(str(action_ref)),
                'title': str(action_ref).replace('-', ' ').title(),
                'definitionCanonical': f"{canonical_base}/ActivityDefinition/{_to_kebab_case(str(action_ref))}"
            })
        
        if child_actions:
            action['action'] = child_actions
    
    return action


def _to_cql_identifier(kebab_id: str) -> str:
    """Convert kebab-case to PascalCase CQL identifier."""
    words = str(kebab_id).split('-')
    return ''.join(word.capitalize() for word in words)


def _to_kebab_case(text: str) -> str:
    """Convert text to kebab-case."""
    return text.lower().replace('_', '-').replace(' ', '-')


def detect_workflow_state_groups(rules: List[Dict[str, Any]], composite_states: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Detect workflow state groups for unmet/met sibling branch generation.
    
    Analyzes rules to identify:
    1. Which composite states are present in the rule set
    2. Which rules represent "establishing" the state (triggered, low prerequisites)
    3. Which rules depend on the state being established (many prerequisites)
    
    Returns state groups:
        {
            'SurgicalCandidacyEstablished': {
                'composite_state': 'SurgicalCandidacyEstablished',
                'unmet_rules': [r1],  # rules that establish the state
                'met_rules': [r4, r5, r6]  # rules that depend on state
            }
        }
    
    Args:
        rules: List of L2 rule dictionaries with when clauses
        composite_states: List of composite state names (PascalCase)
        
    Returns:
        Dictionary mapping state names to {composite_state, unmet_rules, met_rules}
    """
    state_groups = {}
    
    # Group rules by decision type and condition count
    triggered_rules = []
    branching_rules = []
    
    for rule in rules:
        decision_type = rule.get('decision_type', 'branching')
        when_clause = rule.get('when', {})
        condition_count = len(when_clause) if isinstance(when_clause, dict) else 0
        
        if decision_type == 'triggered' or condition_count == 0:
            triggered_rules.append(rule)
        else:
            branching_rules.append(rule)
    
    # For each composite state, check if it divides the rules
    for state_name in composite_states:
        # Find rules that would benefit from this composite state
        # (rules with 4+ conditions are likely using a composite)
        complex_rules = [r for r in branching_rules if len(r.get('when', {})) >= 4]
        simple_rules = [r for r in branching_rules if len(r.get('when', {})) < 4 and len(r.get('when', {})) > 0]
        
        if complex_rules and triggered_rules:
            # This looks like a state transition pattern
            state_groups[state_name] = {
                'composite_state': state_name,
                'unmet_rules': triggered_rules.copy(),  # triggered actions establish state
                'met_rules': complex_rules + simple_rules  # complex rules depend on state
            }
            break  # Use the first matching composite state
    
    return state_groups


def build_unmet_met_branches(
    state_name: str,
    unmet_rules: List[Dict[str, Any]],
    met_rules: List[Dict[str, Any]],
    build_action_fn,
) -> List[Dict[str, Any]]:
    """
    Build unmet/met sibling branch structure for a workflow state.
    
    Creates two sibling actions:
    1. NotStateName (unmet) -> executable actions that establish state
    2. StateName (met) -> branching logic that depends on state
    
    Example output:
        [
            {
                'id': 'not-surgical-candidacy-established',
                'condition': [{'expression': 'not SurgicalCandidacyEstablished'}],
                'action': [...]  # executable actions from unmet_rules
            },
            {
                'id': 'surgical-candidacy-established',
                'condition': [{'expression': 'SurgicalCandidacyEstablished'}],
                'action': [...]  # branching actions from met_rules
            }
        ]
    
    Args:
        state_name: Composite state name (PascalCase)
        unmet_rules: Rules that establish the state
        met_rules: Rules that depend on the state
        build_action_fn: Function(rule) -> action dict
        
    Returns:
        List of two sibling actions (unmet, met)
    """
    import re
    
    # Convert state name to kebab-case for IDs
    state_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', state_name).lower()
    
    branches = []
    
    # UNMET branch (state not yet established)
    if unmet_rules:
        unmet_actions = []
        for rule in unmet_rules:
            action = build_action_fn(rule)
            unmet_actions.append(action)
        
        unmet_branch = {
            'id': f'not-{state_kebab}',
            'title': f'Not {state_name}',
            'condition': [{
                'kind': 'applicability',
                'expression': {
                    'language': 'text/cql-identifier',
                    'expression': f'not {state_name}'
                }
            }],
            'action': unmet_actions
        }
        branches.append(unmet_branch)
    
    # MET branch (state already established)
    if met_rules:
        met_actions = []
        for rule in met_rules:
            action = build_action_fn(rule)
            met_actions.append(action)
        
        # Apply hoisting within the met branch
        met_actions = hoist_shared_prerequisites(met_actions)
        
        met_branch = {
            'id': state_kebab,
            'title': state_name,
            'condition': [{
                'kind': 'applicability',
                'expression': {
                    'language': 'text/cql-identifier',
                    'expression': state_name
                }
            }],
            'action': met_actions
        }
        branches.append(met_branch)
    
    return branches
