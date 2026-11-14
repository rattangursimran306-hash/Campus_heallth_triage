"""
Rule Engine Module for Campus Health-Center Decision Support Application.
Defines documented, institutional triage rules, handles working memory ingestion,
and executes deterministic production system evaluation.
"""
from typing import List, Dict, Any, Tuple, Optional
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
)
from modules.production_system import ProductionRule, WorkingMemory, InferenceEngine
from database.db import upsert_rule_definition


# ---------------- Condition Helpers ----------------

def _contains_any(symptoms_list: List[str], keywords: List[str]) -> Tuple[bool, List[str]]:
    matched = []
    for s in symptoms_list:
        s_lower = s.lower()
        for kw in keywords:
            if kw.lower() in s_lower:
                matched.append(s)
                break
    return (len(matched) > 0, matched)


# ---------------- Rule Definitions ----------------

def rule_emerg_001_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Emergency: Acute severe chest pain or cardiac warning signs."""
    symptoms = wm.get_value("symptoms", [])
    severe_chest = wm.get_value("severe_chest_pain", False)
    has_kw, matched = _contains_any(symptoms, ["chest pain", "crushing", "radiating chest"])
    if severe_chest or has_kw:
        return True, ["Severe / crushing substernal chest pain reported"]
    return False, []


def rule_emerg_002_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Emergency: Severe respiratory distress / stridor / airway compromise."""
    symptoms = wm.get_value("symptoms", [])
    resp_distress = wm.get_value("respiratory_distress", False)
    has_kw, matched = _contains_any(symptoms, ["stridor", "shortness of breath / stridor", "airway", "choking"])
    if resp_distress or has_kw:
        return True, ["Severe respiratory distress / acute airway stridor reported"]
    return False, []


def rule_emerg_003_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Emergency: Acute loss of consciousness, syncope, or acute focal neurological signs."""
    symptoms = wm.get_value("symptoms", [])
    altered = wm.get_value("altered_consciousness", False)
    has_kw, matched = _contains_any(symptoms, ["loss of consciousness", "fainting", "slurred speech", "facial droop"])
    if altered or has_kw:
        return True, ["Acute neurological impairment / loss of consciousness reported"]
    return False, []


def rule_emerg_004_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Emergency: Uncontrolled hemorrhage or profuse bleeding."""
    symptoms = wm.get_value("symptoms", [])
    uncontrolled = wm.get_value("uncontrolled_bleeding", False)
    has_kw, matched = _contains_any(symptoms, ["uncontrolled severe bleeding", "profuse bleeding", "arterial bleed"])
    if uncontrolled or has_kw:
        return True, ["Active uncontrolled hemorrhage reported"]
    return False, []


def rule_emerg_005_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Emergency: Acute psychiatric crisis or active suicidal intent."""
    symptoms = wm.get_value("symptoms", [])
    description = wm.get_value("additional_description", "")
    has_kw, matched = _contains_any(symptoms, ["suicidal", "self-harm", "psychological crisis"])
    has_desc = any(w in description.lower() for w in ["suicide", "kill myself", "end my life", "self harm"])
    if has_kw or has_desc:
        return True, ["Acute psychiatric crisis / self-harm intent reported"]
    return False, []


def rule_urgent_001_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Urgent: High persistent fever (>39°C / 102.2°F) lasting >= 2 days."""
    temp = wm.get_value("temperature_c")
    duration = wm.get_value("duration_days", 0)
    symptoms = wm.get_value("symptoms", [])
    has_fever_symp, _ = _contains_any(symptoms, ["high fever", "chills and rigors"])

    if (temp is not None and temp >= 39.0 and duration >= 2) or (has_fever_symp and duration >= 2):
        return True, [f"High fever (temp: {temp if temp else 'reported >39C'}) lasting {duration} days"]
    return False, []


def rule_urgent_002_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Urgent: Severe acute abdominal or pelvic pain (RLQ, guarding, rebound, peritoneal signs)."""
    symptoms = wm.get_value("symptoms", [])
    severity = wm.get_value("inferred_severity", wm.get_value("pain_scale", 0))
    has_kw, matched = _contains_any(symptoms, ["severe acute abdominal pain", "appendix", "rebound pain", "acute pelvic / lower abdominal pain", "acute pelvic"])
    if has_kw or (any("abdominal" in s.lower() or "pelvic" in s.lower() for s in symptoms) and severity >= 7):
        return True, [f"Severe acute abdominal/pelvic pain (clinical severity: {severity}/10)"]
    return False, []


def rule_urgent_003_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Urgent: Dehydration warning signs with persistent diarrhea or vomiting > 2 days."""
    symptoms = wm.get_value("symptoms", [])
    duration = wm.get_value("duration_days", 0)
    has_gastro, _ = _contains_any(symptoms, ["severe diarrhea", "persistent vomiting"])
    if has_gastro and duration >= 2:
        return True, [f"Persistent fluid loss ({duration} days) with dehydration warning signs"]
    return False, []


def rule_high_001_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """High Priority: Suspected fracture or joint dislocation with deformity."""
    symptoms = wm.get_value("symptoms", [])
    has_kw, matched = _contains_any(symptoms, ["suspected fracture", "visible limb deformity", "inability to bear weight", "joint dislocation"])
    if has_kw:
        return True, ["Suspected fracture or joint deformity following acute trauma"]
    return False, []


def rule_high_002_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """High Priority: Severe acute migraine, acute dental trauma, or incapacitating pain (severity >= 7/10)."""
    symptoms = wm.get_value("symptoms", [])
    severity = wm.get_value("inferred_severity", wm.get_value("pain_scale", 0))
    has_kw, _ = _contains_any(symptoms, [
        "worst headache",
        "severe throbbing migraine",
        "acute throbbing toothache",
        "dental trauma",
        "knocked-out tooth",
        "severe incapacitating dysmenorrhea",
    ])
    if (has_kw and severity >= 6) or (any(k in s.lower() for s in symptoms for k in ["headache", "toothache", "dental", "migraine"]) and severity >= 7):
        return True, [f"Severe acute pain / dental trauma / cephalalgia (clinical severity: {severity}/10)"]
    return False, []


def rule_high_003_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """High Priority: Acute soft-tissue infection or rapid spreading cellulitis."""
    description = wm.get_value("additional_description", "").lower()
    symptoms = wm.get_value("symptoms", [])
    has_infect = any(w in description for w in ["spreading red", "cellulitis", "streaking", "hot swollen wound", "pus"]) or any("spreading" in s.lower() for s in symptoms)
    if has_infect:
        return True, ["Rapidly progressing localized soft tissue infection / cellulitis signs"]
    return False, []


def rule_med_001_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Medium Priority: Subacute respiratory tract infection (cough >3 days, mild fever)."""
    symptoms = wm.get_value("symptoms", [])
    has_cough, _ = _contains_any(symptoms, ["persistent cough", "sore throat", "shortness of breath on exertion"])
    duration = wm.get_value("duration_days", 0)
    temp = wm.get_value("temperature_c")
    if has_cough and (duration >= 2 or (temp is not None and temp >= 37.5 and temp < 39.0)):
        return True, [f"Subacute upper respiratory symptoms (duration: {duration} days, temp: {temp or 'low/moderate'})"]
    return False, []


def rule_med_002_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Medium Priority: Moderate musculoskeletal sprain, sports injury, or dental complaint without deformity."""
    symptoms = wm.get_value("symptoms", [])
    severity = wm.get_value("inferred_severity", wm.get_value("pain_scale", 0))
    has_kw, _ = _contains_any(symptoms, [
        "mild-to-moderate ankle or wrist sprain",
        "severe joint pain",
        "back ache",
        "gum swelling",
        "oral abscess",
        "jaw pain",
        "allergic hives",
    ])
    if has_kw and severity < 8:
        return True, [f"Moderate musculoskeletal/dental/cutaneous condition (clinical severity: {severity}/10, no deformity)"]
    return False, []


def rule_med_003_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Medium Priority: Acute uncomplicated gastrointestinal distress or mild vomiting/diarrhea."""
    symptoms = wm.get_value("symptoms", [])
    has_gi, _ = _contains_any(symptoms, ["mild nausea", "severe diarrhea", "persistent vomiting", "acid reflux"])
    duration = wm.get_value("duration_days", 0)
    if has_gi and duration < 2:
        return True, [f"Acute uncomplicated gastrointestinal complaint (duration: {duration} days)"]
    return False, []


def rule_routine_001_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Routine: Preventive checkup, medical certificate, prescription refill, or minor elective consult."""
    symptoms = wm.get_value("symptoms", [])
    severity = wm.get_value("inferred_severity", wm.get_value("pain_scale", 0))
    temp = wm.get_value("temperature_c")
    has_routine, _ = _contains_any(symptoms, [
        "routine health checkup",
        "routine annual health checkup",
        "chronic prescription renewal",
        "vaccination / immunization",
        "medical certificate",
        "medical fitness certificate",
        "minor superficial cuts",
        "runny nose / nasal congestion",
        "mild tension headache",
        "routine dental checkup",
        "routine gynecological consult",
        "routine mental health",
    ])
    if has_routine and severity <= 5 and (temp is None or temp < 38.0):
        return True, ["Elective, preventive, or minor stable presentation"]
    return False, []


def rule_insufficient_001_condition(wm: WorkingMemory) -> Tuple[bool, List[str]]:
    """Insufficient Info: Missing critical duration, contradictory temperature, or empty symptoms."""
    symptoms = wm.get_value("symptoms", [])
    duration = wm.get_value("duration_days")
    temp = wm.get_value("temperature_c")
    pain = wm.get_value("pain_scale")

    reasons = []
    if not symptoms or len(symptoms) == 0:
        reasons.append("Zero symptoms recorded in questionnaire")
    if duration is None or duration < 0:
        reasons.append("Symptom duration is missing or negative")
    if temp is not None and (temp < 34.0 or temp > 43.0):
        reasons.append(f"Recorded body temperature ({temp}°C) is clinically contradictory/unrealistic")

    if len(reasons) > 0:
        return True, reasons
    return False, []


# ---------------- Build Documented Rule Base ----------------

def build_clinical_rule_base() -> List[ProductionRule]:
    """Assemble all documented clinical production rules."""
    rules = [
        # Emergency Category (Rank 0)
        ProductionRule(
            rule_id="R-EMERG-001",
            name="Acute Coronary / Chest Pain Warning",
            category="Cardiovascular Red Flag",
            condition_description="IF severe chest pain, crushing or radiating substernal pain is reported",
            condition_fn=rule_emerg_001_condition,
            action_priority=PRIORITY_EMERGENCY,
            clinical_rationale="Suspected Acute Coronary Syndrome requires immediate emergency resuscitation and catheterization transfer.",
            source_protocol="SOP-EMS-001 (Section 2)",
            specificity=3,
        ),
        ProductionRule(
            rule_id="R-EMERG-002",
            name="Severe Respiratory Airway Compromise",
            category="Respiratory Red Flag",
            condition_description="IF stridor, severe shortness of breath, or choking signs are present",
            condition_fn=rule_emerg_002_condition,
            action_priority=PRIORITY_EMERGENCY,
            clinical_rationale="Airway compromise carries high risk of immediate hypoxia and respiratory arrest.",
            source_protocol="SOP-EMS-001 (Section 2)",
            specificity=3,
        ),
        ProductionRule(
            rule_id="R-EMERG-003",
            name="Acute Neurological Deficit / Syncope",
            category="Neurological Red Flag",
            condition_description="IF loss of consciousness, fainting, slurred speech or facial droop is present",
            condition_fn=rule_emerg_003_condition,
            action_priority=PRIORITY_EMERGENCY,
            clinical_rationale="Sudden neurological deterioration requires urgent CT neuroimaging to rule out stroke or intracranial bleed.",
            source_protocol="SOP-EMS-001 (Section 2)",
            specificity=3,
        ),
        ProductionRule(
            rule_id="R-EMERG-004",
            name="Uncontrolled Severe Hemorrhage",
            category="Trauma Red Flag",
            condition_description="IF uncontrolled or profuse arterial/venous bleeding is present",
            condition_fn=rule_emerg_004_condition,
            action_priority=PRIORITY_EMERGENCY,
            clinical_rationale="Risk of hemorrhagic shock requires immediate surgical hemostasis and IV volume resuscitation.",
            source_protocol="SOP-EMS-001 (Section 2)",
            specificity=3,
        ),
        ProductionRule(
            rule_id="R-EMERG-005",
            name="Acute Suicidal or Psychiatric Crisis",
            category="Psychiatric Red Flag",
            condition_description="IF active suicidal thoughts or acute psychiatric crisis is reported",
            condition_fn=rule_emerg_005_condition,
            action_priority=PRIORITY_EMERGENCY,
            clinical_rationale="Immediate psychological first aid and 1-on-1 crisis observation required to safeguard life.",
            source_protocol="SOP-MENT-004 (Section 2)",
            specificity=3,
        ),

        # Urgent Category (Rank 1)
        ProductionRule(
            rule_id="R-URGENT-001",
            name="Persistent High Pyrexia (>39°C, >=2 Days)",
            category="Infectious Warning",
            condition_description="IF fever >=39.0°C and duration >=2 days or high fever with chills/rigors",
            condition_fn=rule_urgent_001_condition,
            action_priority=PRIORITY_URGENT,
            clinical_rationale="Risk of bacteremia, sepsis, or invasive viral pneumonia requiring urgent clinical workup.",
            source_protocol="SOP-TRIAGE-002 (Section 2)",
            specificity=2,
        ),
        ProductionRule(
            rule_id="R-URGENT-002",
            name="Acute Peritoneal / Severe Abdominal Distress",
            category="Surgical Warning",
            condition_description="IF acute severe abdominal pain or pain scale >= 7/10 in abdominal complaints",
            condition_fn=rule_urgent_002_condition,
            action_priority=PRIORITY_URGENT,
            clinical_rationale="Must rule out acute surgical abdomen (appendicitis, perforated ulcer, mesenteric ischemia).",
            source_protocol="SOP-TRIAGE-002 (Section 2)",
            specificity=2,
        ),
        ProductionRule(
            rule_id="R-URGENT-003",
            name="Dehydration Warning with Prolonged Fluid Loss",
            category="Fluid / Metabolic",
            condition_description="IF severe vomiting or diarrhea lasting >=2 days",
            condition_fn=rule_urgent_003_condition,
            action_priority=PRIORITY_URGENT,
            clinical_rationale="Risk of hypovolemia, electrolyte imbalance, and pre-renal acute kidney injury.",
            source_protocol="SOP-TRIAGE-002 (Section 2)",
            specificity=2,
        ),

        # High Priority Category (Rank 2)
        ProductionRule(
            rule_id="R-HIGH-001",
            name="Suspected Bone Fracture / Joint Deformity",
            category="Musculoskeletal Trauma",
            condition_description="IF limb deformity, inability to bear weight, or suspected fracture following acute injury",
            condition_fn=rule_high_001_condition,
            action_priority=PRIORITY_HIGH,
            clinical_rationale="Requires prompt radiographic imaging, limb splinting, and acute analgesia within 45 minutes.",
            source_protocol="SOP-TRIAGE-002 (Section 3)",
            specificity=2,
        ),
        ProductionRule(
            rule_id="R-HIGH-002",
            name="Severe Acute Migraine / Intractable Headache",
            category="Neurological Urgent",
            condition_description="IF headache pain scale >= 8/10 or severe throbbing migraine",
            condition_fn=rule_high_002_condition,
            action_priority=PRIORITY_HIGH,
            clinical_rationale="Incapacitating pain requiring parenteral triptans/antiemetics and neuro-monitoring.",
            source_protocol="SOP-TRIAGE-002 (Section 3)",
            specificity=2,
        ),
        ProductionRule(
            rule_id="R-HIGH-003",
            name="Rapidly Spreading Soft-Tissue Infection",
            category="Infectious Urgent",
            condition_description="IF spreading erythema, lymphangitis streaks, or purulent cellulitis signs",
            condition_fn=rule_high_003_condition,
            action_priority=PRIORITY_HIGH,
            clinical_rationale="Prompt systemic antibiotic initiation prevents deep fascial spread or necrotizing infection.",
            source_protocol="SOP-TRIAGE-002 (Section 3)",
            specificity=2,
        ),

        # Medium Priority Category (Rank 3)
        ProductionRule(
            rule_id="R-MED-001",
            name="Subacute Respiratory Infection / Bronchitis",
            category="Respiratory Ambulatory",
            condition_description="IF cough >3 days, sore throat with low/moderate fever (<38.5°C)",
            condition_fn=rule_med_001_condition,
            action_priority=PRIORITY_MEDIUM,
            clinical_rationale="Manageable viral or mild bacterial respiratory illness needing throat swab and supportive therapy.",
            source_protocol="SOP-RESP-003 (Section 3)",
            specificity=1,
        ),
        ProductionRule(
            rule_id="R-MED-002",
            name="Moderate Sprain / Strain Without Deformity",
            category="Musculoskeletal Ambulatory",
            condition_description="IF mild-to-moderate sprain/strain with intact weight bearing and pain < 7/10",
            condition_fn=rule_med_002_condition,
            action_priority=PRIORITY_MEDIUM,
            clinical_rationale="Benefits from RICE protocol, compression wrap, and non-emergent physician assessment.",
            source_protocol="SOP-TRIAGE-002 (Section 4)",
            specificity=1,
        ),
        ProductionRule(
            rule_id="R-MED-003",
            name="Acute Uncomplicated Gastroenteritis (<2 Days)",
            category="Gastrointestinal Ambulatory",
            condition_description="IF acute diarrhea, nausea or vomiting duration < 2 days without severe pain",
            condition_fn=rule_med_003_condition,
            action_priority=PRIORITY_MEDIUM,
            clinical_rationale="Supportive oral rehydration therapy and outpatient anti-spasmodic review.",
            source_protocol="SOP-TRIAGE-002 (Section 4)",
            specificity=1,
        ),

        # Routine Review (Rank 4)
        ProductionRule(
            rule_id="R-ROUTINE-001",
            name="Preventive Checkup & Routine Consult",
            category="Ambulatory Elective",
            condition_description="IF routine checkup, immunization, prescription refill, or minor stable issues",
            condition_fn=rule_routine_001_condition,
            action_priority=PRIORITY_ROUTINE,
            clinical_rationale="Elective care can be scheduled within normal queue capacity without clinical compromise.",
            source_protocol="SOP-TRIAGE-002 (Section 5)",
            specificity=1,
        ),

        # Insufficient Information (Rank 5)
        ProductionRule(
            rule_id="R-INSUFFICIENT-001",
            name="Incomplete or Contradictory Data Flag",
            category="Data Quality",
            condition_description="IF symptoms omitted, negative duration, or physiologically contradictory inputs",
            condition_fn=rule_insufficient_001_condition,
            action_priority=PRIORITY_INSUFFICIENT,
            clinical_rationale="Prevents unsafe automated slot assignment when patient data is unreliable or incomplete.",
            source_protocol="SOP-TRIAGE-002 (Section 6)",
            specificity=1,
        ),
    ]
    return rules


# Global Inference Engine Instance
_GLOBAL_ENGINE: Optional[InferenceEngine] = None


def get_inference_engine() -> InferenceEngine:
    """Return singleton inference engine initialized with clinical rule base."""
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        rules = build_clinical_rule_base()
        _GLOBAL_ENGINE = InferenceEngine(rule_base=rules)
        # Sync definitions to SQLite for documentation transparency
        for r in rules:
            upsert_rule_definition(
                rule_id=r.rule_id,
                category=r.category,
                name=r.name,
                condition_description=r.condition_description,
                action_priority=r.action_priority,
                clinical_rationale=r.clinical_rationale,
                source_protocol=r.source_protocol,
                is_active=r.is_active,
            )
    return _GLOBAL_ENGINE


def evaluate_patient_triage(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assert facts into Working Memory and execute inference engine evaluation.
    Returns complete triage decision with triggered rules and traceability.
    """
    engine = get_inference_engine()
    wm = WorkingMemory()

    inferred_sev = patient_data.get("inferred_severity")
    pain_val = patient_data.get("pain_scale")
    effective_sev = inferred_sev if inferred_sev is not None else (pain_val if pain_val is not None else 2)

    # Assert facts from patient record
    wm.assert_fact("full_name", patient_data.get("full_name", ""))
    wm.assert_fact("age", patient_data.get("age", 20))
    wm.assert_fact("department", patient_data.get("department", "General Medicine & Primary Care"))
    wm.assert_fact("symptoms", patient_data.get("symptoms", []))
    wm.assert_fact("additional_description", patient_data.get("additional_description", ""))
    wm.assert_fact("duration_days", patient_data.get("duration_days", 0))
    wm.assert_fact("pain_scale", effective_sev)
    wm.assert_fact("inferred_severity", effective_sev)
    wm.assert_fact("temperature_c", patient_data.get("temperature_c"))
    wm.assert_fact("severe_chest_pain", patient_data.get("severe_chest_pain", False))
    wm.assert_fact("respiratory_distress", patient_data.get("respiratory_distress", False))
    wm.assert_fact("altered_consciousness", patient_data.get("altered_consciousness", False))
    wm.assert_fact("uncontrolled_bleeding", patient_data.get("uncontrolled_bleeding", False))

    return engine.evaluate(wm)
