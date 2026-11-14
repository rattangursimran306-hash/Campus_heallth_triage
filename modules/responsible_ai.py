"""
Responsible AI & Clinical Governance Module.
Implements ethical AI safeguards:
- Strict non-diagnostic guardrails
- Human-in-the-loop clinical override verification
- Uncertainty & data incompleteness scoring
- Patient privacy / PII masking
- Audit logging for all administrative decisions
"""
from typing import Dict, Any, List, Optional, Tuple
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    NON_DIAGNOSTIC_DISCLAIMER,
    EMERGENCY_ESCALATION_NOTICE,
    PRIORITY_EMERGENCY,
    PRIORITY_INSUFFICIENT,
)
from database.db import record_audit_log, record_scheduling_history


class ResponsibleAI:
    """Governance and ethical guardrails manager."""

    @staticmethod
    def get_mandatory_disclaimer() -> str:
        """Return the official institutional non-diagnostic disclaimer."""
        return NON_DIAGNOSTIC_DISCLAIMER

    @staticmethod
    def get_emergency_notice() -> str:
        """Return the red-flag emergency escalation protocol notice."""
        return EMERGENCY_ESCALATION_NOTICE

    @staticmethod
    def mask_patient_pii(patient: Dict[str, Any], viewer_role: str = "Triage Nurse") -> Dict[str, Any]:
        """
        Mask Personally Identifiable Information (PII) for privacy protection.
        Full names and contact numbers are masked for non-clinical or public roles.
        """
        masked = dict(patient)
        name = masked.get("full_name", "")
        contact = masked.get("contact", "")

        if viewer_role in ("Public / Student Preview", "Research Observer"):
            # Anonymize name: "Ananya Sharma" -> "A. S***"
            parts = name.split()
            if len(parts) >= 2:
                masked["full_name"] = f"{parts[0][0]}. {parts[1][0]}***"
            elif len(parts) == 1 and len(parts[0]) > 1:
                masked["full_name"] = f"{parts[0][0]}***"
            else:
                masked["full_name"] = "Anonymous"

            # Mask contact: "+91-9876543210" -> "******3210"
            if contact:
                masked["contact"] = "******" + contact[-4:] if len(contact) >= 4 else "******"

        return masked

    @staticmethod
    def assess_uncertainty(patient_data: Dict[str, Any], triage_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate uncertainty and data ambiguity in patient presentation.
        Returns uncertainty score (0.0 - 1.0), risk flags, and human intervention recommendations.
        """
        flags = []
        score = 0.0

        symptoms = patient_data.get("symptoms", [])
        duration = patient_data.get("duration_days")
        pain = patient_data.get("pain_scale", 0)
        temp = patient_data.get("temperature_c")
        desc = patient_data.get("additional_description", "")

        # 1. Missing duration
        if duration is None or duration == 0:
            flags.append("Symptom duration is unspecified or 0 days.")
            score += 0.3

        # 2. Vague descriptions or self-reported "other" without pre-defined categories
        if any("Other:" in s for s in symptoms) and len(symptoms) == 1:
            flags.append("Patient only entered custom text without selecting verified symptom categories.")
            score += 0.25

        # 3. Discrepancy: high pain score without specific emergency symptoms
        if pain >= 8 and triage_result.get("category") not in (PRIORITY_EMERGENCY, "URGENT REVIEW", "HIGH PRIORITY REVIEW"):
            flags.append(f"High subjective pain score ({pain}/10) recorded with subacute symptom profile.")
            score += 0.3

        # 4. Borderline temperature
        if temp is not None and 37.8 <= temp < 38.3:
            flags.append(f"Borderline pyrexia ({temp}°C) requires re-measurement upon clinic arrival.")
            score += 0.15

        # 5. Fallback rule activated
        if triage_result.get("winning_rule_id") == "R-INSUFFICIENT-FALLBACK":
            flags.append("No predefined rule triggered. Full manual assessment required.")
            score += 0.5

        final_score = min(1.0, round(score, 2))
        requires_interview = final_score >= 0.4 or triage_result.get("category") == PRIORITY_INSUFFICIENT

        return {
            "uncertainty_score": final_score,
            "uncertainty_level": "HIGH" if final_score >= 0.5 else ("MODERATE" if final_score >= 0.25 else "LOW"),
            "uncertainty_flags": flags,
            "requires_human_interview": requires_interview,
            "recommendation": (
                "Direct triage nurse intake interview mandatory before confirming queue position."
                if requires_interview else "Standard automated decision-support confidence satisfied."
            ),
        }

    @staticmethod
    def validate_manual_override(
        old_priority: str,
        new_priority: str,
        justification: str,
        admin_user: str,
        patient_id: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Ensure human oversight accountability.
        Requires meaningful clinical justification (minimum 10 chars) for any priority modification.
        """
        if not justification or len(justification.strip()) < 10:
            return False, "Clinical justification for manual override is mandatory and must contain at least 10 characters."

        if old_priority == new_priority:
            return False, "New priority is identical to current priority. No change needed."

        # Record into audit trail
        record_audit_log(
            admin_user=admin_user,
            action_type="PRIORITY_OVERRIDE",
            patient_id=patient_id,
            details=f"Priority manually overridden from [{old_priority}] to [{new_priority}]. Justification: {justification.strip()}",
        )

        record_scheduling_history(
            patient_id=patient_id,
            action="MANUAL_OVERRIDE",
            old_slot=None,
            new_slot=None,
            old_priority=old_priority,
            new_priority=new_priority,
            reason=justification.strip(),
            changed_by=admin_user,
        )

        return True, None
