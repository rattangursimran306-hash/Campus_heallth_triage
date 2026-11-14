"""
Seed Data Generator for Campus Health-Center Decision Support Application.
Generates realistic, de-identified synthetic patient cohorts across all clinical categories,
seeds documented rules, schedules appointments, and creates initial audit records.
"""
from datetime import datetime, timedelta
import random
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
from database.db import (
    init_db,
    insert_patient,
    insert_symptom_report,
    record_triggered_rules,
    insert_appointment,
    record_audit_log,
    record_scheduling_history,
)
from modules.rule_engine import evaluate_patient_triage
from modules.priority_scheduler import PriorityScheduler
from modules.patient_registration import infer_recommended_department, infer_clinical_severity

SYNTHETIC_NAMES = [
    ("Aarav Mehta", 20, "Male"),
    ("Sneha Roy", 19, "Female"),
    ("Rohan Verma", 22, "Male"),
    ("Priya Nair", 21, "Female"),
    ("Aditya Rao", 24, "Male"),
    ("Ananya Sen", 20, "Female"),
    ("Kavya Iyer", 23, "Female"),
    ("Rahul Kapoor", 18, "Male"),
    ("Ishaan Das", 25, "Male"),
    ("Tanvi Joshi", 21, "Female"),
    ("Vikram Singhania", 22, "Male"),
    ("Divya Menon", 19, "Female"),
    ("Manish Tiwari", 26, "Male"),
    ("Pooja Hegde", 20, "Female"),
    ("Siddharth Malhotra", 23, "Male"),
    ("Neha Deshmukh", 22, "Female"),
    ("Arjun Nambiar", 24, "Male"),
    ("Ritika Gupta", 20, "Female"),
    ("Devansh Saxena", 19, "Male"),
    ("Meera Kulkarni", 21, "Female"),
    ("Harsh Vardhan", 22, "Male"),
    ("Shreya Bhat", 20, "Female"),
    ("Karan Gill", 25, "Male"),
    ("Anjali Pillai", 19, "Female"),
    ("Naveen Reddy", 27, "Male"),
    ("Simran Kaur", 21, "Female"),
    ("Varun Dhawan", 23, "Male"),
    ("Deepika Patel", 22, "Female"),
    ("Pranav Shah", 20, "Male"),
    ("Sanya Mirza", 24, "Female"),
    ("Akash Banerjee", 21, "Male"),
    ("Rhea Chakraborty", 20, "Female"),
    ("Gautam Gambhir", 26, "Male"),
    ("Swati Mishra", 22, "Female"),
    ("Abhishek Bachchan", 23, "Male"),
    ("Tara Sutaria", 19, "Female"),
    ("Mohit Suri", 24, "Male"),
    ("Kriti Sanon", 21, "Female"),
    ("Zaid Khan", 22, "Male"),
    ("Fatima Sana", 20, "Female"),
    ("Gaurav Chopra", 28, "Male"),
    ("Bhavna Vasudev", 23, "Female"),
    ("Mayank Agarwal", 21, "Male"),
    ("Pallavi Joshi", 25, "Female"),
    ("Ashwin Kumar", 22, "Male"),
    ("Lavanya Tripathy", 19, "Female"),
    ("Surya Narayanan", 24, "Male"),
    ("Trisha Krishnan", 20, "Female"),
    ("Karthik Aryan", 21, "Male"),
    ("Radhika Madan", 22, "Female"),
]

# Profiles designed to systematically trigger all categories
SYNTHETIC_PROFILES = [
    # Emergencies (Red Flags)
    {
        "symptoms": ["Crushing / radiating chest pain", "Severe shortness of breath / stridor"],
        "desc": "Sudden heavy pressure behind breastbone radiating down left arm, cold sweating.",
        "duration": 0.1, "pain": 9, "temp": 37.1,
        "chest": True, "resp": True, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Severe shortness of breath / stridor"],
        "desc": "Acute asthma exacerbation, inhaler not relieving wheezing, struggling to complete words.",
        "duration": 0.2, "pain": 8, "temp": 36.8,
        "chest": False, "resp": True, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Loss of consciousness / fainting", "Sudden facial droop / slurred speech"],
        "desc": "Student collapsed during lecture, regained consciousness but speech is noticeably slurred.",
        "duration": 0.1, "pain": 5, "temp": 37.0,
        "chest": False, "resp": False, "altered": True, "bleed": False
    },
    {
        "symptoms": ["Uncontrolled severe bleeding"],
        "desc": "Deep glass laceration to forearm in chemistry laboratory, profuse spurting blood.",
        "duration": 0.05, "pain": 9, "temp": 36.9,
        "chest": False, "resp": False, "altered": False, "bleed": True
    },
    {
        "symptoms": ["Suicidal thoughts or acute psychological crisis"],
        "desc": "Reporting extreme hopelessness, overwhelming despair, active thoughts of self harm.",
        "duration": 1.0, "pain": 7, "temp": 36.7,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },

    # Urgent Review
    {
        "symptoms": ["High fever (>39°C / 102.2°F)", "Chills and rigors"],
        "desc": "Severe fever spikes for 3 consecutive days, shaking chills, body aches.",
        "duration": 3.0, "pain": 7, "temp": 39.4,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Severe acute abdominal pain"],
        "desc": "Sharp excruciating pain in right lower quadrant with nausea, cannot walk straight.",
        "duration": 0.8, "pain": 8, "temp": 38.2,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Severe diarrhea (>48 hours)", "Persistent vomiting (>24 hours)"],
        "desc": "Unable to keep any water down for over 48 hours, extreme weakness and dry mouth.",
        "duration": 2.5, "pain": 6, "temp": 37.8,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },

    # High Priority Review
    {
        "symptoms": ["Suspected fracture / visible limb deformity"],
        "desc": "Bad tackle in campus football match, visible deformity of right wrist with intense swelling.",
        "duration": 0.1, "pain": 8, "temp": 36.7,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Severe throbbing migraine", "Worst headache of life (thunderclap)"],
        "desc": "Incapacitating unilateral throbbing headache, photophobia, nausea, pain scale 9/10.",
        "duration": 0.5, "pain": 9, "temp": 37.0,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Severe joint pain / acute inability to bear weight"],
        "desc": "Severe ankle swelling following basketball rebound, completely unable to bear weight.",
        "duration": 0.2, "pain": 7, "temp": 36.9,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },

    # Medium Priority Review
    {
        "symptoms": ["Persistent cough (>3 days)", "Sore throat / painful swallowing"],
        "desc": "Dry barking cough for 4 days, mild fever in the evenings, throat irritation.",
        "duration": 4.0, "pain": 4, "temp": 38.0,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Mild-to-moderate ankle or wrist sprain"],
        "desc": "Twisted ankle on hostel stairs yesterday, mild swelling, can still limp slowly.",
        "duration": 1.2, "pain": 5, "temp": 36.8,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Mild nausea or stomach cramp"],
        "desc": "Ate spicy canteen food last night, stomach cramps and loose stools this morning.",
        "duration": 0.7, "pain": 4, "temp": 37.0,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },

    # Routine Review
    {
        "symptoms": ["Routine health checkup / sports physical"],
        "desc": "Need general medical fitness certificate for university badminton team trials.",
        "duration": 10.0, "pain": 0, "temp": 36.6,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Chronic prescription renewal"],
        "desc": "Need refill for maintenance inhaler and allergy medication for chronic asthma.",
        "duration": 30.0, "pain": 0, "temp": 36.6,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Vaccination / immunization query"],
        "desc": "Query regarding Hepatitis B booster dose and influenza vaccine availability.",
        "duration": 5.0, "pain": 0, "temp": 36.5,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Minor superficial cuts or abrasions", "Runny nose / nasal congestion"],
        "desc": "Scraped knee while jogging, superficial graze, needs cleaning and bandaging.",
        "duration": 0.5, "pain": 2, "temp": 36.8,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },

    # Insufficient Information / Missing Data
    {
        "symptoms": [],
        "desc": "Student submitted form with no specific symptoms selected.",
        "duration": 0.0, "pain": 0, "temp": None,
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
    {
        "symptoms": ["Other: Feeling vaguely unwell"],
        "desc": "Unspecified weakness, no duration or temperature provided.",
        "duration": 0.0, "pain": 0, "temp": 44.5,  # Unrealistic contradictory temp
        "chest": False, "resp": False, "altered": False, "bleed": False
    },
]


def seed_database(num_patients: int = 50) -> None:
    """Populate database with synthetic patients, triage evaluations, and initial schedule."""
    print(f"Initializing database and seeding {num_patients} synthetic patient records...")
    init_db(force_recreate=True)

    today = datetime.now()
    base_arrival = today.replace(hour=8, minute=30, second=0, microsecond=0)

    patient_records_for_scheduling = []

    for i in range(num_patients):
        name_tuple = SYNTHETIC_NAMES[i % len(SYNTHETIC_NAMES)]
        profile = SYNTHETIC_PROFILES[i % len(SYNTHETIC_PROFILES)]

        # Stagger arrival times between 08:30 and 11:30 (every 3 to 5 minutes)
        arrival_time = base_arrival + timedelta(minutes=int(i * 3.5))

        patient_code = f"PAT-2026-{1000 + i}"
        full_name = f"{name_tuple[0]} (Demo #{i+1})"
        age = name_tuple[1]
        gender = name_tuple[2]
        contact = f"+91-98{random.randint(10000000, 99999999)}"
        dept = infer_recommended_department(profile["symptoms"], profile["desc"])

        inferred_sev, _ = infer_clinical_severity(
            symptoms=profile["symptoms"],
            additional_description=profile["desc"],
            duration_days=profile["duration"],
            temperature_c=profile["temp"],
            severe_chest_pain=profile["chest"],
            respiratory_distress=profile["resp"],
            altered_consciousness=profile["altered"],
            uncontrolled_bleeding=profile["bleed"],
        )

        patient_id = insert_patient(
            patient_code=patient_code,
            full_name=full_name,
            age=age,
            gender=gender,
            contact=contact,
            department=dept,
        )

        insert_symptom_report(
            patient_id=patient_id,
            symptoms=profile["symptoms"],
            additional_description=profile["desc"],
            duration_days=profile["duration"],
            pain_scale=profile["pain"],
            inferred_severity=inferred_sev,
            temperature_c=profile["temp"],
            respiratory_distress=profile["resp"],
            altered_consciousness=profile["altered"],
            severe_chest_pain=profile["chest"],
            uncontrolled_bleeding=profile["bleed"],
        )

        # Evaluate rules
        patient_data = {
            "id": patient_id,
            "patient_code": patient_code,
            "full_name": full_name,
            "age": age,
            "department": dept,
            "symptoms": profile["symptoms"],
            "additional_description": profile["desc"],
            "duration_days": profile["duration"],
            "pain_scale": profile["pain"],
            "inferred_severity": inferred_sev,
            "temperature_c": profile["temp"],
            "severe_chest_pain": profile["chest"],
            "respiratory_distress": profile["resp"],
            "altered_consciousness": profile["altered"],
            "uncontrolled_bleeding": profile["bleed"],
            "created_at": arrival_time,
        }

        triage_result = evaluate_patient_triage(patient_data)
        record_triggered_rules(patient_id, triage_result["triggered_rules"])

        patient_records_for_scheduling.append({
            "id": patient_id,
            "patient_code": patient_code,
            "full_name": full_name,
            "department": dept,
            "priority_category": triage_result["category"],
            "arrival_time": arrival_time,
        })

    # Schedule with Priority Scheduler
    prio_scheduler = PriorityScheduler()
    prio_result = prio_scheduler.schedule(patient_records_for_scheduling, simulation_date=today)

    for app in prio_result["appointments"]:
        # Mark first 5 non-emergency appointments as COMPLETED for realistic dashboard stats
        status = "COMPLETED" if app["queue_position"] in (1, 2, 3) else app["status"]

        insert_appointment(
            patient_id=app["patient_id"],
            slot_start=app["slot_start"],
            slot_end=app["slot_end"],
            provider_id=app["provider_id"],
            provider_name=app["provider_name"],
            priority_category=app["priority_category"],
            algorithm="PRIORITY_AGENT",
            queue_position=app["queue_position"],
            estimated_wait_minutes=app["estimated_wait_minutes"],
            status=status,
            department=app.get("department", "General Medicine & Primary Care"),
        )

    # Initial Audit Logs
    record_audit_log(
        admin_user="system_init",
        action_type="SYSTEM_BOOTSTRAP",
        patient_id=None,
        details=f"System initialized with {num_patients} synthetic patient records across all triage categories.",
    )

    record_audit_log(
        admin_user="nurse_kelly",
        action_type="PRIORITY_OVERRIDE",
        patient_id=6,
        details="Manual override: Promoted patient PAT-2026-1005 from MEDIUM to HIGH based on clinical visual paleness and tachycardia.",
    )

    print(f"Successfully seeded {num_patients} patients with complete triage and appointments!")


if __name__ == "__main__":
    seed_database()
