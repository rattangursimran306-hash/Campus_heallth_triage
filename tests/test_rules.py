"""
Automated Unit Tests for Production System & Clinical Triage Rule Engine.
Validates 100% deterministic rule activation, conflict resolution,
missing data handling, and non-diagnostic explanation generation.
"""
import pytest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_ROUTINE,
    PRIORITY_INSUFFICIENT,
)
from modules.rule_engine import evaluate_patient_triage, build_clinical_rule_base
from modules.production_system import WorkingMemory, InferenceEngine


@pytest.fixture
def base_patient():
    return {
        "id": 1,
        "patient_code": "PAT-TEST-001",
        "full_name": "Test Student",
        "age": 20,
        "symptoms": [],
        "additional_description": "",
        "duration_days": 1.0,
        "pain_scale": 2,
        "temperature_c": 36.8,
        "severe_chest_pain": False,
        "respiratory_distress": False,
        "altered_consciousness": False,
        "uncontrolled_bleeding": False,
    }


def test_rule_emerg_001_chest_pain(base_patient):
    """Test R-EMERG-001: Acute chest pain triggers EMERGENCY ESCALATION."""
    base_patient["symptoms"] = ["Crushing / radiating chest pain"]
    base_patient["severe_chest_pain"] = True

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_EMERGENCY
    assert result["winning_rule_id"] == "R-EMERG-001"
    assert "chest pain" in result["explanation"].lower()
    assert result["conflict_set_size"] >= 1


def test_rule_emerg_002_respiratory_distress(base_patient):
    """Test R-EMERG-002: Stridor and severe dyspnea trigger EMERGENCY ESCALATION."""
    base_patient["symptoms"] = ["Severe shortness of breath / stridor"]
    base_patient["respiratory_distress"] = True

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_EMERGENCY
    assert result["winning_rule_id"] == "R-EMERG-002"


def test_rule_emerg_003_neurological_deficit(base_patient):
    """Test R-EMERG-003: Syncope / slurred speech triggers EMERGENCY ESCALATION."""
    base_patient["symptoms"] = ["Loss of consciousness / fainting"]
    base_patient["altered_consciousness"] = True

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_EMERGENCY
    assert result["winning_rule_id"] == "R-EMERG-003"


def test_rule_urgent_001_high_fever(base_patient):
    """Test R-URGENT-001: High fever >= 39°C lasting >= 2 days."""
    base_patient["symptoms"] = ["High fever (>39°C / 102.2°F)", "Chills and rigors"]
    base_patient["temperature_c"] = 39.5
    base_patient["duration_days"] = 3.0

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_URGENT
    assert result["winning_rule_id"] == "R-URGENT-001"


def test_rule_urgent_002_acute_abdominal_pain(base_patient):
    """Test R-URGENT-002: Severe acute abdominal pain."""
    base_patient["symptoms"] = ["Severe acute abdominal pain"]
    base_patient["pain_scale"] = 8

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_URGENT
    assert result["winning_rule_id"] == "R-URGENT-002"


def test_rule_high_001_fracture_deformity(base_patient):
    """Test R-HIGH-001: Suspected bone fracture or joint deformity."""
    base_patient["symptoms"] = ["Suspected fracture / visible limb deformity"]
    base_patient["pain_scale"] = 7

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_HIGH
    assert result["winning_rule_id"] == "R-HIGH-001"


def test_rule_med_001_subacute_cough(base_patient):
    """Test R-MED-001: Cough > 3 days with mild fever."""
    base_patient["symptoms"] = ["Persistent cough (>3 days)"]
    base_patient["duration_days"] = 4.0
    base_patient["temperature_c"] = 37.8

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_MEDIUM
    assert result["winning_rule_id"] == "R-MED-001"


def test_rule_routine_001_checkup(base_patient):
    """Test R-ROUTINE-001: Preventive checkup, prescription renewal, or minor abrasions."""
    base_patient["symptoms"] = ["Routine health checkup / sports physical"]
    base_patient["pain_scale"] = 0

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_ROUTINE
    assert result["winning_rule_id"] == "R-ROUTINE-001"


def test_rule_insufficient_001_empty_symptoms(base_patient):
    """Test R-INSUFFICIENT-001: Missing symptoms flags INSUFFICIENT INFORMATION."""
    base_patient["symptoms"] = []
    base_patient["additional_description"] = ""

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_INSUFFICIENT


def test_rule_insufficient_001_contradictory_temp(base_patient):
    """Test contradictory temperature input (> 43.0°C)."""
    base_patient["symptoms"] = ["Mild nausea or stomach cramp"]
    base_patient["temperature_c"] = 44.5  # Incompatible with survival

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_INSUFFICIENT


def test_conflict_resolution_emergency_over_routine(base_patient):
    """
    Test Conflict Resolution: When multiple rules fire (e.g. routine checkup + chest pain),
    Emergency Escalation MUST take precedence over Routine Review.
    """
    base_patient["symptoms"] = [
        "Routine health checkup / sports physical",
        "Crushing / radiating chest pain",
    ]
    base_patient["severe_chest_pain"] = True

    result = evaluate_patient_triage(base_patient)
    assert result["category"] == PRIORITY_EMERGENCY
    assert result["winning_rule_id"] == "R-EMERG-001"
    assert result["conflict_set_size"] >= 2

    # Check that superseded rule is marked as not winning
    winner_found = False
    superseded_found = False
    for tr in result["triggered_rules"]:
        if tr["is_conflict_winner"]:
            winner_found = True
            assert tr["rule_id"] == "R-EMERG-001"
        else:
            superseded_found = True
            assert "Superseded in conflict resolution" in tr["explanation"]

    assert winner_found and superseded_found


def test_all_documented_rules_have_explanations():
    """Verify that every single documented rule has clinical rationale and source protocol."""
    rules = build_clinical_rule_base()
    assert len(rules) >= 12
    for r in rules:
        assert r.rule_id
        assert r.name
        assert r.clinical_rationale
        assert r.source_protocol
        assert r.action_priority in [
            PRIORITY_EMERGENCY,
            PRIORITY_URGENT,
            PRIORITY_HIGH,
            PRIORITY_MEDIUM,
            PRIORITY_ROUTINE,
            PRIORITY_INSUFFICIENT,
        ]


def test_infer_clinical_severity_replaces_subjective_slider():
    """Verify objective algorithmic severity calculation prevents queue-gaming."""
    from modules.patient_registration import infer_clinical_severity

    # Emergency chest pain -> Severity 10
    score, reason = infer_clinical_severity(
        symptoms=["Crushing / radiating chest pain"],
        severe_chest_pain=True,
    )
    assert score == 10
    assert "Emergency" in reason or "Critical" in reason

    # High acuity fracture -> Severity 8
    score, reason = infer_clinical_severity(
        symptoms=["Suspected bone fracture / visible limb deformity"],
    )
    assert score >= 8

    # High fever modifier increases severity
    score_fever, _ = infer_clinical_severity(
        symptoms=["Persistent cough (>3 days)"],
        temperature_c=39.2,
        duration_days=3.0,
    )
    score_no_fever, _ = infer_clinical_severity(
        symptoms=["Persistent cough (>3 days)"],
        temperature_c=36.8,
        duration_days=3.0,
    )
    assert score_fever > score_no_fever

    # Routine checkup -> Severity 1
    score, _ = infer_clinical_severity(
        symptoms=["Routine annual health checkup / sports clearance"],
    )
    assert score <= 2


def test_infer_recommended_department():
    """Verify department recommendation maps complaints to appropriate specialty."""
    from modules.patient_registration import infer_recommended_department

    assert infer_recommended_department(["Acute throbbing toothache / dental nerve pain"]) == "Dentistry & Oral Health"
    assert infer_recommended_department(["Severe acute pelvic / lower abdominal pain"]) == "Gynecology & Women's Health"
    assert infer_recommended_department(["Suspected bone fracture / visible limb deformity"]) == "Orthopedics & Sports Medicine"
    assert infer_recommended_department(["Academic burnout / chronic sleep disturbances"]) == "Psychological Health & Counseling"
    assert infer_recommended_department(["Rapidly spreading painful red rash with fever"]) == "Dermatology"
    assert infer_recommended_department(["Routine annual health checkup / sports clearance"]) == "General Medicine & Primary Care"
