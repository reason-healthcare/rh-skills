"""Topic-level condition merging for CPG-on-FHIR formalization.

This module implements condition deduplication across multiple decision tables
within the same topic, ensuring a single CQL Library is shared.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


class ConditionMerger:
    """Deduplicates conditions across multiple decision tables in a topic.
    
    When a topic has multiple decision tables (e.g., CRS has surgical, diagnostic,
    and follow-up tables), they often share conditions (e.g., has-crs-dx). This
    class ensures conditions are defined once in a single topic-level Library.
    """

    def __init__(self, topic_id: str):
        """Initialize merger for a topic.
        
        Args:
            topic_id: Topic identifier for Library canonical URL
        """
        self.topic_id = topic_id
        self._conditions: Dict[str, Dict[str, Any]] = {}  # condition_id → condition data
        self._sources: Dict[str, List[str]] = defaultdict(list)  # condition_id → [decision_table_ids]

    def register_conditions(self, decision_table_id: str, conditions: List[Dict[str, Any]]) -> None:
        """Register conditions from a decision table.
        
        Args:
            decision_table_id: Decision table identifier
            conditions: List of condition dictionaries from L2 artifact sections.conditions
        """
        for condition in conditions:
            cond_id = condition['id']
            
            # Track which decision tables use this condition
            self._sources[cond_id].append(decision_table_id)
            
            # Store condition data (or verify consistency if already seen)
            if cond_id in self._conditions:
                self._validate_condition_consistency(cond_id, condition)
            else:
                self._conditions[cond_id] = condition

    def get_merged_conditions(self) -> List[Dict[str, Any]]:
        """Get deduplicated list of all conditions across registered decision tables.
        
        Returns:
            List of condition dictionaries (one per unique condition_id)
        """
        return list(self._conditions.values())

    def get_condition_sources(self, condition_id: str) -> List[str]:
        """Get list of decision tables that use a specific condition.
        
        Args:
            condition_id: Condition identifier
            
        Returns:
            List of decision table IDs that reference this condition
        """
        return self._sources.get(condition_id, [])

    def get_shared_conditions(self) -> List[Dict[str, Any]]:
        """Get conditions used by multiple decision tables.
        
        Returns:
            List of condition dictionaries used by 2+ decision tables
        """
        return [
            self._conditions[cond_id]
            for cond_id, sources in self._sources.items()
            if len(sources) > 1
        ]

    def get_unique_conditions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get conditions unique to each decision table.
        
        Returns:
            Dictionary mapping decision_table_id → [conditions used only by that table]
        """
        result = defaultdict(list)
        
        for cond_id, sources in self._sources.items():
            if len(sources) == 1:
                dt_id = sources[0]
                result[dt_id].append(self._conditions[cond_id])
        
        return dict(result)

    def generate_library_id(self) -> str:
        """Generate Library resource ID for this topic.
        
        Returns:
            Library resource ID (e.g., 'chronic-rhinosinusitis')
        """
        return self.topic_id

    def generate_merge_report(self) -> str:
        """Generate human-readable report of condition merging.
        
        Useful for CLI reporting and debugging.
        
        Returns:
            Formatted report string
        """
        lines = [f"# Condition Merge Report: {self.topic_id}\n"]
        
        shared = self.get_shared_conditions()
        unique = self.get_unique_conditions()
        total = len(self._conditions)
        
        lines.append(f"## Summary")
        lines.append(f"  - Total unique conditions: {total}")
        lines.append(f"  - Shared across tables: {len(shared)}")
        lines.append(f"  - Decision tables: {len(set(sum(self._sources.values(), [])))}\n")
        
        if shared:
            lines.append("## Shared Conditions (Used by Multiple Decision Tables)\n")
            for condition in shared:
                cond_id = condition['id']
                sources = self._sources[cond_id]
                lines.append(f"  - **{cond_id}**")
                lines.append(f"    Used by: {', '.join(sources)}")
                lines.append(f"    Description: {condition.get('description', 'N/A')}\n")
        
        if unique:
            lines.append("## Unique Conditions (Single Decision Table)\n")
            for dt_id, conditions in unique.items():
                lines.append(f"  - **{dt_id}** ({len(conditions)} unique conditions)")
                for condition in conditions:
                    lines.append(f"    - {condition['id']}: {condition.get('description', 'N/A')}")
                lines.append("")
        
        lines.append("## Deduplication Benefit")
        total_before = sum(len(sources) for sources in self._sources.values())
        total_after = len(self._conditions)
        saved = total_before - total_after
        lines.append(f"  - Conditions before merging: {total_before}")
        lines.append(f"  - Conditions after merging: {total_after}")
        lines.append(f"  - Duplicates eliminated: {saved} ({100 * saved / total_before if total_before > 0 else 0:.1f}%)")
        
        return '\n'.join(lines)

    def _validate_condition_consistency(self, condition_id: str, new_condition: Dict[str, Any]) -> None:
        """Validate that duplicate condition definitions are semantically equivalent.
        
        Args:
            condition_id: Condition identifier
            new_condition: New condition data to validate against existing
            
        Raises:
            ValueError: If condition definitions conflict
        """
        existing = self._conditions[condition_id]
        
        # Check if descriptions match (or are semantically equivalent)
        existing_desc = existing.get('description', '').strip().lower()
        new_desc = new_condition.get('description', '').strip().lower()
        
        if existing_desc != new_desc:
            # Allow minor variations (punctuation, whitespace)
            if self._normalize_text(existing_desc) != self._normalize_text(new_desc):
                raise ValueError(
                    f"Condition '{condition_id}' has conflicting definitions:\n"
                    f"  Existing: {existing.get('description')}\n"
                    f"  New: {new_condition.get('description')}\n"
                    f"  Sources: {self._sources[condition_id]}"
                )
        
        # Check if CQL stubs match (if present)
        existing_cql = existing.get('cql_stub', '').strip()
        new_cql = new_condition.get('cql_stub', '').strip()
        
        if existing_cql and new_cql and existing_cql != new_cql:
            raise ValueError(
                f"Condition '{condition_id}' has conflicting CQL stubs:\n"
                f"  Existing: {existing_cql}\n"
                f"  New: {new_cql}\n"
                f"  Sources: {self._sources[condition_id]}"
            )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (remove punctuation, extra whitespace).
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        import re
        # Remove punctuation except hyphens in compound words
        text = re.sub(r'[^\w\s-]', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.lower()
