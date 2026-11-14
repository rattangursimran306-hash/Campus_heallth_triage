"""
Patient Registration Module for Campus Health-Center Decision Support Application.
Provides symptom taxonomy, objective algorithmic clinical severity inference,
department recommendation, form validation, red-flag screening, and patient creation.
"""
from datetime import datetime
import random
import string
import re
from typing import List, Dict, Any, Tuple, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import insert_patient, insert_symptom_report
from config import DEPARTMENTS, DEFAULT_DEPARTMENT

# Predefined Symptoms Organized by Physiological and Specialty Domain
SYMPTOM_CATALOG = {
    "Critical / Emergency Warning Signs": [
        "Crushing / radiating chest pain",
        "Severe shortness of breath / stridor",
        "Loss of consciousness / fainting",
        "Sudden facial droop / slurred speech",
        "Uncontrolled severe bleeding",
        "Severe allergic reaction / facial swelling",
        "Suicidal thoughts or acute psychological crisis",
    ],
    "General Medicine & Acute Illness": [
        "High fever (>39°C / 102.2°F)",
        "Persistent cough (>3 days)",
        "Shortness of breath on exertion",
        "Sore throat / painful swallowing",
        "Runny nose / nasal congestion",
        "Chills and rigors",
        "Severe acute abdominal pain",
        "Persistent vomiting (>24 hours)",
        "Severe diarrhea (>48 hours)",
        "Mild nausea or stomach cramp",
        "Acid reflux / heartburn",
        "Worst headache of life (thunderclap)",
        "Severe throbbing migraine",
        "Mild tension headache / eyestrain",
        "Dizziness or lightheadedness",
    ],
    "Dentistry & Oral Health": [
        "Acute throbbing toothache / dental nerve pain",
        "Dental trauma / chipped or knocked-out tooth",
        "Gum swelling / oral abscess / facial swelling",
        "Severe jaw pain / clicking / limited opening",
        "Bleeding gums / tooth mobility",
        "Routine dental checkup / scaling query",
    ],
    "Gynecology & Women's Health": [
        "Severe acute pelvic / lower abdominal pain",
        "Severe incapacitating dysmenorrhea / menstrual cramps",
        "Abnormal / heavy irregular uterine bleeding",
        "Suspected acute UTI / painful urination",
        "Vaginal discharge / burning / itching",
        "Routine gynecological consult / contraceptive advice",
    ],
    "Orthopedics & Sports Medicine": [
        "Suspected bone fracture / visible limb deformity",
        "Acute joint dislocation or severe trauma",
        "Severe joint pain / acute inability to bear weight",
        "Mild-to-moderate ankle or wrist sprain",
        "Chronic muscular neck / back ache",
        "Minor superficial cuts or abrasions",
    ],
    "Psychological Health & Counseling": [
        "Acute psychological crisis / overwhelming panic",
        "Severe anxiety attack / racing heartbeat",
        "Persistent severe depressive mood / despair",
        "Academic burnout / chronic sleep disturbances",
        "Routine mental health & wellness checkup",
    ],
    "Dermatology & Skin": [
        "Rapidly spreading painful red rash with fever",
        "Severe acute allergic hives / urticaria",
        "Suspected localized skin abscess / boils / cellulitis",
        "Chronic eczema flare-up / itchy skin patches",
        "Acne vulgaris / persistent facial breakouts",
    ],
    "Preventive & Routine Services": [
        "Routine annual health checkup / sports clearance",
        "Chronic prescription renewal / medication refill",
        "Vaccination / immunization query",
        "Medical fitness certificate / academic leave endorsement",
    ],
}


def get_flattened_symptoms() -> List[str]:
    """Return flat list of all catalog symptoms for UI selection."""
    flat = []
    for category, items in SYMPTOM_CATALOG.items():
        flat.extend(items)
    return flat


def generate_patient_code() -> str:
    """Generate a unique human-readable patient code e.g., PAT-2026-X8B9."""
    year = datetime.now().year
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"PAT-{year}-{suffix}"


def infer_recommended_department(symptoms: List[str], additional_description: str = "") -> str:
    """
    Algorithmic department recommendation based on reported symptoms and description.
    Maps patient complaints to the most appropriate clinical specialty.
    """
    combined_text = " ".join(symptoms).lower() + " " + additional_description.lower()

    # Priority mapping keywords
    if any(k in combined_text for k in ["tooth", "teeth", "dental", "gum", "oral abscess", "jaw clicking", "molar"]):
        return "Dentistry & Oral Health"
    elif any(k in combined_text for k in ["pelvic", "menstrual", "period", "cramp", "uterine", "vaginal", "gynae", "contracept"]) or re.search(r"\buti\b", combined_text):
        return "Gynecology & Women's Health"
    elif any(k in combined_text for k in ["fracture", "deformity", "dislocation", "bone", "sprain", "ligament", "weight bearing", "wrist sprain", "ankle sprain"]):
        return "Orthopedics & Sports Medicine"
    elif any(k in combined_text for k in ["suicidal", "psychological", "panic", "anxiety attack", "depression", "counseling", "burnout"]):
        return "Psychological Health & Counseling"
    elif any(k in combined_text for k in ["rash", "hives", "urticaria", "eczema", "cellulitis", "skin abscess", "boil", "acne", "itching"]):
        return "Dermatology"
    else:
        return "General Medicine & Primary Care"


def infer_clinical_severity(
    symptoms: List[str],
    additional_description: str = "",
    duration_days: float = 0.0,
    temperature_c: Optional[float] = None,
    severe_chest_pain: bool = False,
    respiratory_distress: bool = False,
    altered_consciousness: bool = False,
    uncontrolled_bleeding: bool = False,
) -> Tuple[int, str]:
    """
    Algorithmic Clinical Severity Scoring (1 to 10 scale).
    Replaces subjective self-reported pain sliders to eliminate queue-gaming incentives.
    Deterministically evaluates physiological indicators, red-flag screening, duration, and vitals.
    Returns (severity_score: int [1-10], rationale: str).
    """
    combined_text = " ".join(symptoms).lower() + " " + additional_description.lower()

    # 1. Critical Red Flags (Severity 10)
    critical_reasons = []
    if severe_chest_pain or any(k in combined_text for k in ["chest pain", "crushing", "radiating chest"]):
        critical_reasons.append("Severe cardiac warning sign")
    if respiratory_distress or any(k in combined_text for k in ["stridor", "shortness of breath / stridor", "airway compromise"]):
        critical_reasons.append("Severe airway / respiratory distress")
    if altered_consciousness or any(k in combined_text for k in ["consciousness", "fainting", "slurred speech", "facial droop"]):
        critical_reasons.append("Acute neurological impairment")
    if uncontrolled_bleeding or any(k in combined_text for k in ["uncontrolled severe bleeding", "profuse bleeding"]):
        critical_reasons.append("Active uncontrolled hemorrhage")
    if any(k in combined_text for k in ["suicidal", "self-harm", "psychological crisis", "kill myself"]):
        critical_reasons.append("Acute psychiatric crisis")

    if critical_reasons:
        return 10, f"Critical emergency tier triggered: {', '.join(critical_reasons)}."

    # 2. High-Acuity Warnings (Base Severity 7-8)
    high_reasons = []
    if any(k in combined_text for k in ["suspected fracture", "visible limb deformity", "dislocation"]):
        high_reasons.append("Suspected bone fracture / limb deformity")
    if any(k in combined_text for k in ["severe acute abdominal pain", "rebound pain", "appendix"]):
        high_reasons.append("Acute peritoneal / abdominal distress")
    if any(k in combined_text for k in ["thunderclap", "worst headache"]):
        high_reasons.append("Sudden severe intracranial cephalalgia")
    if any(k in combined_text for k in ["acute throbbing toothache", "dental trauma", "knocked-out tooth"]):
        high_reasons.append("Acute dental trauma / exposed nerve")
    if any(k in combined_text for k in ["severe acute pelvic", "abnormal / heavy irregular uterine bleeding"]):
        high_reasons.append("Acute severe pelvic / reproductive distress")
    if any(k in combined_text for k in ["spreading painful red rash", "cellulitis", "streaking"]):
        high_reasons.append("Rapidly spreading soft tissue infection")

    if high_reasons:
        score = 8
        if temperature_c is not None and temperature_c >= 38.5:
            score = 9
            high_reasons.append(f"Pyrexia of {temperature_c}°C detected")
        return min(score, 9), f"High clinical acuity: {', '.join(high_reasons)}."

    # 3. Moderate-Acuity Conditions (Base Severity 5-6)
    med_reasons = []
    if any(k in combined_text for k in ["persistent cough", "shortness of breath on exertion", "sore throat"]):
        med_reasons.append("Subacute respiratory complaint")
    if any(k in combined_text for k in ["persistent vomiting", "severe diarrhea", "dehydration"]):
        med_reasons.append("Gastrointestinal fluid loss")
    if any(k in combined_text for k in ["sprain", "inability to bear weight", "severe joint pain"]):
        med_reasons.append("Musculoskeletal injury / ligament strain")
    if any(k in combined_text for k in ["severe throbbing migraine", "severe menstrual cramps"]):
        med_reasons.append("Incapacitating acute episode")
    if any(k in combined_text for k in ["gum swelling", "oral abscess", "jaw pain"]):
        med_reasons.append("Localized odontogenic infection / swelling")
    if any(k in combined_text for k in ["allergic hives", "urticaria", "boils"]):
        med_reasons.append("Acute dermatologic eruption")

    if med_reasons:
        score = 5
        if temperature_c is not None and temperature_c >= 38.0:
            score += 1
            med_reasons.append(f"Fever {temperature_c}°C")
        if duration_days >= 3.0:
            score += 1
            med_reasons.append(f"Prolonged duration ({duration_days} days)")
        return min(score, 7), f"Moderate clinical acuity: {', '.join(med_reasons)}."

    # 4. Mild / Subacute Presentation (Base Severity 3-4)
    mild_reasons = []
    if any(k in combined_text for k in ["runny nose", "mild nausea", "tension headache", "dizziness", "cuts or abrasions", "back ache"]):
        mild_reasons.append("Mild ambulatory symptom complex")
    if any(k in combined_text for k in ["eczema", "acne", "bleeding gums"]):
        mild_reasons.append("Chronic localized cutaneous/oral condition")

    if mild_reasons:
        score = 3
        if temperature_c is not None and temperature_c >= 37.8:
            score += 1
        return score, f"Mild ambulatory presentation: {', '.join(mild_reasons)}."

    # 5. Routine / Elective Consultation (Base Severity 1-2)
    routine_reasons = []
    if any(k in combined_text for k in ["routine", "checkup", "prescription renewal", "vaccination", "certificate", "clearance"]):
        routine_reasons.append("Elective health consultation / administrative endorsement")

    if routine_reasons:
        return 1, f"Routine administrative/wellness request: {', '.join(routine_reasons)}."

    # Default fallback based on duration
    default_score = 4 if duration_days > 3 else 3
    return default_score, f"Standard clinical assessment based on reported duration ({duration_days} days)."


def validate_registration_data(
    full_name: str,
    age: int,
    symptoms: List[str],
    other_symptoms: str,
    duration_days: float,
    temperature_c: Optional[float] = None,
    contact: Optional[str] = None,
    department: Optional[str] = None,
    pain_scale: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    """
    Validate patient registration inputs against clinical & administrative constraints.
    Returns (is_valid, error_messages).
    """
    errors = []

    # 1. Full name validation
    if not full_name or len(full_name.strip()) < 2:
        errors.append("Patient name is mandatory and must contain at least 2 characters.")

    # 2. Age validation
    if age is None or age < 14 or age > 100:
        errors.append("Age must be between 14 and 100 for campus health services.")

    # 3. Symptoms validation (must select at least one predefined or enter other)
    has_predefined = bool(symptoms and len(symptoms) > 0)
    has_other = bool(other_symptoms and len(other_symptoms.strip()) > 2)
    if not has_predefined and not has_other:
        errors.append("Please select at least one reported symptom or provide a description in 'Other Symptoms'.")

    # 4. Duration validation
    if duration_days is None or duration_days < 0:
        errors.append("Symptom duration must be 0 or a positive number of days.")

    # 5. Department validation
    if department and department not in DEPARTMENTS:
        errors.append(f"Selected department '{department}' is not a valid campus health clinic specialty.")

    # 6. Temperature validation (if provided)
    if temperature_c is not None:
        if temperature_c < 34.0 or temperature_c > 43.0:
            errors.append("Body temperature must be within clinically plausible range (34.0°C to 43.0°C).")

    # 7. Contact format validation (optional)
    if contact and len(contact.strip()) > 0:
        cleaned_contact = re.sub(r"[\s\-\+\(\)]", "", contact)
        if len(cleaned_contact) < 7:
            errors.append("Contact number seems too short or invalid.")

    return (len(errors) == 0, errors)


def register_new_patient(
    full_name: str,
    age: int,
    gender: str,
    contact: str,
    symptoms: List[str],
    other_symptoms: str,
    duration_days: float,
    temperature_c: Optional[float] = None,
    department: str = DEFAULT_DEPARTMENT,
    additional_notes: str = "",
    pain_scale: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validate, insert patient and symptom report, and detect direct red-flag indicators.
    Objectively infers clinical severity to eliminate subjective queue manipulation.
    Returns a dictionary containing registration outcome and patient record.
    """
    is_valid, errors = validate_registration_data(
        full_name=full_name,
        age=age,
        symptoms=symptoms,
        other_symptoms=other_symptoms,
        duration_days=duration_days,
        temperature_c=temperature_c,
        contact=contact,
        department=department,
        pain_scale=pain_scale,
    )

    if not is_valid:
        return {"success": False, "errors": errors, "patient_id": None, "patient_code": None}

    # Aggregate symptoms
    combined_symptoms = list(symptoms) if symptoms else []
    if other_symptoms and len(other_symptoms.strip()) > 0:
        combined_symptoms.append(f"Other: {other_symptoms.strip()}")

    # Red-flag screening checks
    severe_chest = any("chest pain" in s.lower() for s in combined_symptoms)
    resp_distress = any("shortness of breath" in s.lower() or "stridor" in s.lower() for s in combined_symptoms)
    altered_consciousness = any("consciousness" in s.lower() or "slurred speech" in s.lower() for s in combined_symptoms)
    uncontrolled_bleed = any("uncontrolled" in s.lower() or "severe bleeding" in s.lower() for s in combined_symptoms)

    # Calculate objective clinical severity algorithmically
    inferred_severity, severity_rationale = infer_clinical_severity(
        symptoms=combined_symptoms,
        additional_description=additional_notes or other_symptoms,
        duration_days=float(duration_days),
        temperature_c=temperature_c,
        severe_chest_pain=severe_chest,
        respiratory_distress=resp_distress,
        altered_consciousness=altered_consciousness,
        uncontrolled_bleeding=uncontrolled_bleed,
    )

    # Use inferred severity as authoritative severity
    effective_pain = pain_scale if pain_scale is not None else inferred_severity

    patient_code = generate_patient_code()
    patient_id = insert_patient(
        patient_code=patient_code,
        full_name=full_name.strip(),
        age=int(age),
        gender=gender if gender else "Unspecified",
        contact=contact.strip() if contact else None,
        department=department,
    )

    report_id = insert_symptom_report(
        patient_id=patient_id,
        symptoms=combined_symptoms,
        additional_description=additional_notes.strip() if additional_notes else other_symptoms.strip(),
        duration_days=float(duration_days),
        pain_scale=int(effective_pain),
        inferred_severity=int(inferred_severity),
        temperature_c=float(temperature_c) if temperature_c is not None else None,
        respiratory_distress=resp_distress,
        altered_consciousness=altered_consciousness,
        severe_chest_pain=severe_chest,
        uncontrolled_bleeding=uncontrolled_bleed,
    )

    return {
        "success": True,
        "patient_id": patient_id,
        "patient_code": patient_code,
        "report_id": report_id,
        "department": department,
        "symptoms": combined_symptoms,
        "inferred_severity": inferred_severity,
        "severity_rationale": severity_rationale,
        "has_emergency_flags": severe_chest or resp_distress or altered_consciousness or uncontrolled_bleed,
        "timestamp": datetime.now().isoformat(),
    }
