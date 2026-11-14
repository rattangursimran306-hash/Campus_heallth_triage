"""
Automated Unit Tests for Responsible AI & Clinical Governance Safeguards.
Validates non-diagnostic disclaimers, uncertainty scoring,
mandatory clinical justification for manual overrides, and PII masking.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.responsible_ai import ResponsibleAI
from config import (
    NON_DIAGNOSTIC_DISCLAIMER,
    EMERGENCY_ESCALATION_NOTICE,
    PRIORITY_ROUTINE,
    PRIORITY_HIGH,
)


def test_mandatory_disclaimer_content():
    """Verify official non-diagnostic notice is properly formed."""
    disc = ResponsibleAI.get_mandatory_disclaimer()
    assert "decision-support prototype" in disc
    assert "does not provide medical diagnoses" in disc
    assert "authorized healthcare personnel" in disc


def test_emergency_notice_content():
    """Verify red-flag emergency escalation guidance contains EMS hotline contacts."""
    notice = ResponsibleAI.get_emergency_notice()
    assert "IMMEDIATE EMERGENCY ESCALATION" in notice
    assert "Ext. 911" in notice


def test_uncertainty_assessment_missing_duration():
    """Verify patient with missing duration receives uncertainty score penalty."""
    patient = {
        "symptoms": ["Runny nose / nasal congestion"],
        "duration_days": 0,
        "pain_scale": 1,
        "temperature_c": 36.8,
    }
    triage = {"category": PRIORITY_ROUTINE, "winning_rule_id": "R-ROUTINE-001"}

    unc = ResponsibleAI.assess_uncertainty(patient, triage)
    assert unc["uncertainty_score"] > 0.0
    assert any("duration" in f.lower() for f in unc["uncertainty_flags"])


def test_manual_override_validation_requires_justification():
    """Verify manual override is rejected if justification is too short or missing."""
    is_valid, err = ResponsibleAI.validate_manual_override(
        old_priority=PRIORITY_ROUTINE,
        new_priority=PRIORITY_HIGH,
        justification="short",
        admin_user="nurse_kelly",
        patient_id=1,
    )
    assert is_valid is False
    assert "at least 10 characters" in err


def test_manual_override_validation_rejects_identical_priority():
    """Verify override is rejected if new priority equals old priority."""
    is_valid, err = ResponsibleAI.validate_manual_override(
        old_priority=PRIORITY_ROUTINE,
        new_priority=PRIORITY_ROUTINE,
        justification="Patient insists on seeing doctor right now.",
        admin_user="nurse_kelly",
        patient_id=1,
    )
    assert is_valid is False
    assert "identical" in err.lower()


def test_manual_override_valid():
    """Verify valid clinical override succeeds."""
    is_valid, err = ResponsibleAI.validate_manual_override(
        old_priority=PRIORITY_ROUTINE,
        new_priority=PRIORITY_HIGH,
        justification="Observed marked facial pallor and active profuse perspiration on arrival.",
        admin_user="nurse_kelly",
        patient_id=1,
    )
    assert is_valid is True
    assert err is None


def test_pii_masking_for_public_role():
    """Verify Personally Identifiable Information (name, contact) is masked for public viewers."""
    raw_patient = {
        "full_name": "Aarav Mehta",
        "contact": "+91-9876543210",
        "age": 20,
    }
    masked = ResponsibleAI.mask_patient_pii(raw_patient, viewer_role="Public / Student Preview")

    assert masked["full_name"] == "A. M***"
    assert masked["contact"] == "******3210"
    assert masked["age"] == 20
