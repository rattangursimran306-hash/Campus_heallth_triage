"""
Explanation Engine Module for Campus Health-Center Decision Support Application.
Generates structured, human-readable, auditable explanations for rule-based triage decisions,
including conflict resolution summaries, matched facts, and non-diagnostic disclaimers.
"""
from typing import Dict, Any, List, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    NON_DIAGNOSTIC_DISCLAIMER,
    EMERGENCY_ESCALATION_NOTICE,
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    RECOMMENDED_MAX_WAIT_MINUTES,
)


def format_explanation_markdown(triage_result: Dict[str, Any], patient_data: Dict[str, Any]) -> str:
    """Format an administrative explanation into GitHub-flavored Markdown for UI rendering."""
    category = triage_result.get("category", "UNCLASSIFIED")
    winning_id = triage_result.get("winning_rule_id", "N/A")
    winning_name = triage_result.get("winning_rule_name", "N/A")
    triggered_rules = triage_result.get("triggered_rules", [])
    max_wait = RECOMMENDED_MAX_WAIT_MINUTES.get(category, 60)

    md = []
    md.append(f"### 🛡️ Decision Transparency Report — Patient {patient_data.get('patient_code', 'N/A')}")
    md.append(f"**Assigned Review Tier:** `{category}` (Target Evaluation Window: **Within {max_wait} mins**)")
    md.append("")

    # Emergency Callout
    if category == PRIORITY_EMERGENCY:
        md.append("> [!CAUTION]")
        md.append(f"> **{EMERGENCY_ESCALATION_NOTICE}**")
        md.append("")

    # Winning Rule Section
    md.append("#### 1. Primary Activated Rule")
    md.append(f"- **Rule ID:** `{winning_id}` ({winning_name})")
    md.append(f"- **Facts Matched in Working Memory:** {', '.join(triage_result.get('all_winning_facts', []))}")
    md.append(f"- **Inference Outcome:** {triage_result.get('explanation', '')}")
    md.append("")

    # Competing Rules and Conflict Resolution
    if len(triggered_rules) > 1:
        md.append("#### 2. Conflict Resolution Trace")
        md.append(f"*Total {len(triggered_rules)} clinical rules were satisfied by the reported symptoms. The conflict resolution strategy ordered activations by priority rank and clinical specificity:*")
        md.append("")
        for idx, tr in enumerate(triggered_rules):
            status_icon = "👑 **[Selected Priority]**" if tr.get("is_conflict_winner") else "↳ *[Superseded]*"
            md.append(f"- {status_icon} **`{tr['rule_id']}` ({tr['name']})** → Category: `{tr['action_priority']}`")
            md.append(f"  - *Reasoning:* {tr['explanation']}")
            md.append(f"  - *Reference Protocol:* `{tr.get('source_protocol', 'N/A')}`")
        md.append("")
    else:
        md.append("#### 2. Conflict Resolution Trace")
        md.append("- Single unambiguous rule activation in working memory. No conflicting clinical flags detected.")
        md.append("")

    # Responsible AI & Safety Notice
    md.append("#### 3. Administrative Non-Diagnostic Notice")
    md.append(f"> [!NOTE]\n> {NON_DIAGNOSTIC_DISCLAIMER}")

    return "\n".join(md)


def generate_structured_explanation(triage_result: Dict[str, Any], patient_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate structured dictionary of the explanation for API and database storage."""
    return {
        "category": triage_result.get("category"),
        "priority_rank": triage_result.get("priority_rank"),
        "winning_rule_id": triage_result.get("winning_rule_id"),
        "winning_rule_name": triage_result.get("winning_rule_name"),
        "matched_facts": triage_result.get("all_winning_facts", []),
        "primary_explanation": triage_result.get("explanation"),
        "total_triggered_rules": len(triage_result.get("triggered_rules", [])),
        "conflict_trace": [
            {
                "rule_id": r["rule_id"],
                "name": r["name"],
                "category": r["action_priority"],
                "is_winner": r["is_conflict_winner"],
                "protocol": r.get("source_protocol"),
            }
            for r in triage_result.get("triggered_rules", [])
        ],
        "non_diagnostic_disclaimer": NON_DIAGNOSTIC_DISCLAIMER,
        "is_emergency": triage_result.get("category") == PRIORITY_EMERGENCY,
    }
