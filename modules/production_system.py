"""
Production System Engine for Campus Health-Center Decision Support Application.
Implements classical AI production system architecture:
- Working Memory (stores patient facts and symptoms)
- Rule Base (clinical & administrative IF-THEN rules)
- Forward-Chaining Inference Engine
- Multi-criterion Conflict Resolution Strategy
- Traceability and Explanation Generator
"""
from typing import List, Dict, Any, Callable, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_ROUTINE,
    PRIORITY_INSUFFICIENT,
    PRIORITY_RANKS,
)


@dataclass
class Fact:
    """Represents a discrete verified fact or symptom state in Working Memory."""
    attribute: str
    value: Any
    confidence: float = 1.0
    source: str = "PATIENT_REPORT"

    def __hash__(self):
        return hash((self.attribute, str(self.value)))

    def __eq__(self, other):
        if not isinstance(other, Fact):
            return False
        return self.attribute == other.attribute and self.value == other.value


class WorkingMemory:
    """Working Memory storing asserted facts during patient triage evaluation."""
    def __init__(self):
        self._facts: Dict[str, Fact] = {}

    def assert_fact(self, attribute: str, value: Any, confidence: float = 1.0, source: str = "PATIENT_REPORT") -> None:
        """Add or update a fact in working memory."""
        self._facts[attribute] = Fact(attribute=attribute, value=value, confidence=confidence, source=source)

    def retract_fact(self, attribute: str) -> None:
        """Remove a fact from working memory."""
        self._facts.pop(attribute, None)

    def get_fact(self, attribute: str) -> Optional[Fact]:
        """Retrieve a specific fact by attribute name."""
        return self._facts.get(attribute)

    def get_value(self, attribute: str, default: Any = None) -> Any:
        """Retrieve the value of an attribute or return default."""
        fact = self._facts.get(attribute)
        return fact.value if fact else default

    def has_fact(self, attribute: str) -> bool:
        """Check if attribute is asserted."""
        return attribute in self._facts

    def all_facts(self) -> Dict[str, Any]:
        """Return a dictionary of all active facts and their values."""
        return {k: v.value for k, v in self._facts.items()}

    def clear(self) -> None:
        """Clear all facts."""
        self._facts.clear()


@dataclass
class ProductionRule:
    """Definition of an IF-THEN clinical triage production rule."""
    rule_id: str
    name: str
    category: str
    condition_description: str
    condition_fn: Callable[[WorkingMemory], Tuple[bool, List[str]]]
    action_priority: str
    clinical_rationale: str
    source_protocol: str
    specificity: int = 1  # Number of specific conditions checked (used for conflict resolution)
    is_active: bool = True

    @property
    def priority_rank(self) -> int:
        """Numeric rank from config (0 = Highest / Emergency)."""
        return PRIORITY_RANKS.get(self.action_priority, 99)


class InferenceEngine:
    """
    Forward-chaining inference engine with conflict resolution.
    Evaluates rules against Working Memory, records activations, and selects winner.
    """
    def __init__(self, rule_base: Optional[List[ProductionRule]] = None):
        self.rule_base: List[ProductionRule] = rule_base or []
        self.execution_log: List[Dict[str, Any]] = []

    def add_rule(self, rule: ProductionRule) -> None:
        """Register a new production rule in the rule base."""
        self.rule_base.append(rule)

    def evaluate(self, working_memory: WorkingMemory) -> Dict[str, Any]:
        """
        Execute forward-chaining cycle:
        1. Match: evaluate condition_fn of all active rules against working memory.
        2. Conflict Set: collect all rules whose condition evaluates to True.
        3. Conflict Resolution: order conflict set by:
           - Priority Rank (Emergency < Urgent < High < Medium < Routine < Insufficient)
           - Specificity (more specific rules take precedence)
           - Rule ID stability
        4. Select Conflict Winner: highest priority rule determines the primary review category.
        5. Return structured evaluation outcome with explanation traces.
        """
        conflict_set: List[Dict[str, Any]] = []

        # 1. Match phase
        for rule in self.rule_base:
            if not rule.is_active:
                continue

            matches, matched_facts = rule.condition_fn(working_memory)
            if matches:
                conflict_set.append({
                    "rule": rule,
                    "matched_facts": matched_facts,
                    "priority_rank": rule.priority_rank,
                    "specificity": rule.specificity,
                })

        # If no rules fired (e.g. invalid or empty inputs)
        if not conflict_set:
            fallback_explanation = (
                "No documented clinical rules were satisfied by the provided symptom profile. "
                "Flagged for human triage nurse review to prevent unclassified patient risk."
            )
            return {
                "category": PRIORITY_INSUFFICIENT,
                "priority_rank": PRIORITY_RANKS[PRIORITY_INSUFFICIENT],
                "winning_rule_id": "R-INSUFFICIENT-FALLBACK",
                "winning_rule_name": "Fallback Unclassified Triage Review",
                "explanation": fallback_explanation,
                "triggered_rules": [{
                    "rule_id": "R-INSUFFICIENT-FALLBACK",
                    "name": "Fallback Unclassified Triage Review",
                    "action_priority": PRIORITY_INSUFFICIENT,
                    "explanation": fallback_explanation,
                    "matched_facts": ["No matching rule satisfied"],
                    "clinical_rationale": "Safety fallback: cases without documented rule matches require manual nurse intake.",
                    "source_protocol": "CHS-TRIAGE-FALLBACK-001",
                    "is_conflict_winner": True,
                }],
                "conflict_set_size": 0,
            }

        # 2. Conflict Resolution Strategy
        # Safety principle: If contradictory or insufficient information is detected,
        # it overrides non-emergency categories so staff can clarify before automated routing.
        has_emergency = any(item["rule"].action_priority == PRIORITY_EMERGENCY for item in conflict_set)
        has_insufficient = any(item["rule"].action_priority == PRIORITY_INSUFFICIENT for item in conflict_set)

        if has_insufficient and not has_emergency:
            # Place INSUFFICIENT rule at top of conflict set
            conflict_set.sort(key=lambda item: (0 if item["rule"].action_priority == PRIORITY_INSUFFICIENT else 1, item["priority_rank"], -item["specificity"]))
        else:
            # Standard Sort key: (priority_rank ASC, specificity DESC, rule_id ASC)
            conflict_set.sort(key=lambda item: (item["priority_rank"], -item["specificity"], item["rule"].rule_id))

        winner_item = conflict_set[0]
        winning_rule: ProductionRule = winner_item["rule"]

        # 3. Assemble detailed triggered rules with explanations
        triggered_rules_details = []
        for idx, item in enumerate(conflict_set):
            r: ProductionRule = item["rule"]
            is_winner = (idx == 0)
            explanation = (
                f"Rule [{r.rule_id}] triggered because: {', '.join(item['matched_facts'])}. "
                f"Assigned priority: '{r.action_priority}'. "
                f"Clinical rationale: {r.clinical_rationale} (Protocol: {r.source_protocol})."
            )
            if not is_winner:
                explanation += f" (Superseded in conflict resolution by higher-priority rule [{winning_rule.rule_id}])."

            triggered_rules_details.append({
                "rule_id": r.rule_id,
                "name": r.name,
                "action_priority": r.action_priority,
                "priority_rank": r.priority_rank,
                "explanation": explanation,
                "matched_facts": item["matched_facts"],
                "clinical_rationale": r.clinical_rationale,
                "source_protocol": r.source_protocol,
                "is_conflict_winner": is_winner,
            })

        winning_explanation = (
            f"PRIMARY TRIAGE DECISION: Classified as [{winning_rule.action_priority}] under rule [{winning_rule.rule_id}: {winning_rule.name}]. "
            f"Key matching criteria: {', '.join(winner_item['matched_facts'])}. "
            f"Reference Standard: {winning_rule.source_protocol}."
        )

        return {
            "category": winning_rule.action_priority,
            "priority_rank": winning_rule.priority_rank,
            "winning_rule_id": winning_rule.rule_id,
            "winning_rule_name": winning_rule.name,
            "explanation": winning_explanation,
            "triggered_rules": triggered_rules_details,
            "conflict_set_size": len(conflict_set),
            "all_winning_facts": winner_item["matched_facts"],
        }
