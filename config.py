"""
Configuration module for Campus Health-Center Triage and Appointment Allocation Assistant.
Defines constants, priority ranks, scheduling rules, RAG parameters, and Responsible AI policies.
"""
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "campus_health.db"
DOCUMENTS_DIR = BASE_DIR / "knowledge_base" / "documents"
ASSETS_DIR = BASE_DIR / "assets"

# Priority Review Categories
PRIORITY_EMERGENCY = "EMERGENCY ESCALATION"
PRIORITY_URGENT = "URGENT REVIEW"
PRIORITY_HIGH = "HIGH PRIORITY REVIEW"
PRIORITY_MEDIUM = "MEDIUM PRIORITY REVIEW"
PRIORITY_ROUTINE = "ROUTINE REVIEW"
PRIORITY_INSUFFICIENT = "INSUFFICIENT INFORMATION"

# Numeric Rank (Lower number = Higher Priority)
PRIORITY_RANKS = {
    PRIORITY_EMERGENCY: 0,
    PRIORITY_URGENT: 1,
    PRIORITY_HIGH: 2,
    PRIORITY_MEDIUM: 3,
    PRIORITY_ROUTINE: 4,
    PRIORITY_INSUFFICIENT: 5,
}

# Official Brand Color Palette: 3368A0, 66A3BF, C8DFDB, F2EFE7
PALETTE = {
    "primary": "#3368A0",       # Deep oceanic blue / brand primary
    "secondary": "#66A3BF",     # Medium ocean blue / accents
    "accent_light": "#C8DFDB",  # Soft seafoam sage / card borders & tints
    "bg_canvas": "#F2EFE7",     # Warm light canvas / background
    "text_dark": "#162D4A",     # Accessible high-contrast text
    "card_bg": "#FFFFFF",       # Crisp white card surfaces
}

# UI Display Badges and Color Schemes (Harmonized with official palette)
PRIORITY_COLORS = {
    PRIORITY_EMERGENCY: {"bg": "#FCE8E6", "text": "#8A231C", "border": "#D9534F", "hex": "#D9534F"},
    PRIORITY_URGENT:    {"bg": "#FBEED9", "text": "#874D0E", "border": "#E67E22", "hex": "#E67E22"},
    PRIORITY_HIGH:      {"bg": "#FFF7D6", "text": "#7C5209", "border": "#D4AC0D", "hex": "#D4AC0D"},
    PRIORITY_MEDIUM:    {"bg": "#E1EEEC", "text": "#1E4F5E", "border": "#66A3BF", "hex": "#66A3BF"},
    PRIORITY_ROUTINE:   {"bg": "#E2EFEA", "text": "#185343", "border": "#48A388", "hex": "#48A388"},
    PRIORITY_INSUFFICIENT: {"bg": "#EAE7DF", "text": "#4A463B", "border": "#B8B3A4", "hex": "#B8B3A4"},
}

# Target Clinical Review Timelines (Max Recommended Wait Time in minutes)
RECOMMENDED_MAX_WAIT_MINUTES = {
    PRIORITY_EMERGENCY: 0,       # Immediate ER transfer / bypass ordinary schedule
    PRIORITY_URGENT: 15,        # Within 15 minutes
    PRIORITY_HIGH: 45,          # Within 45 minutes
    PRIORITY_MEDIUM: 120,       # Within 2 hours
    PRIORITY_ROUTINE: 240,      # Within 4 hours
    PRIORITY_INSUFFICIENT: 60,  # Staff review needed
}

# Clinical Departments / Medical Specialties
DEPARTMENTS = [
    "General Medicine & Primary Care",
    "Dentistry & Oral Health",
    "Gynecology & Women's Health",
    "Orthopedics & Sports Medicine",
    "Psychological Health & Counseling",
    "Dermatology",
]

DEFAULT_DEPARTMENT = "General Medicine & Primary Care"

# Clinical / Scheduling Providers Partitioned by Department
HEALTHCARE_PROVIDERS = [
    # General Medicine & Primary Care
    {"id": "DOC-GEN-01", "name": "Dr. Ananya Sharma", "department": "General Medicine & Primary Care", "specialty": "Urgent Care & Acute Illness"},
    {"id": "DOC-GEN-02", "name": "Dr. Vikram Patel", "department": "General Medicine & Primary Care", "specialty": "Campus Primary & Preventive Care"},

    # Dentistry & Oral Health
    {"id": "DOC-DEN-01", "name": "Dr. Rajesh Khanna", "department": "Dentistry & Oral Health", "specialty": "Dental Trauma, Endodontics & Oral Surgery"},
    {"id": "DOC-DEN-02", "name": "Dr. Pooja Iyer", "department": "Dentistry & Oral Health", "specialty": "Restorative & Preventive Dentistry"},

    # Gynecology & Women's Health
    {"id": "DOC-GYN-01", "name": "Dr. Sunita Rao", "department": "Gynecology & Women's Health", "specialty": "Reproductive Health & Clinical Gynecology"},

    # Orthopedics & Sports Medicine
    {"id": "DOC-ORT-01", "name": "Dr. Kabir Mehta", "department": "Orthopedics & Sports Medicine", "specialty": "Trauma, Fractures & Sports Sprains"},

    # Psychological Health & Counseling
    {"id": "DOC-MEN-01", "name": "Counselor Maya Verma", "department": "Psychological Health & Counseling", "specialty": "Crisis Intervention & Student Counseling"},

    # Dermatology
    {"id": "DOC-DER-01", "name": "Dr. Farhan Siddiqui", "department": "Dermatology", "specialty": "Cutaneous Health & Infectious Rashes"},
]

# Appointment Scheduling Parameters
CLINIC_START_HOUR = 9     # 09:00 AM
CLINIC_END_HOUR = 17      # 05:00 PM
SLOT_DURATION_MINUTES = 15
TOTAL_SLOTS_PER_DAY = ((CLINIC_END_HOUR - CLINIC_START_HOUR) * 60) // SLOT_DURATION_MINUTES

# Priority Queue Starvation Safeguards
STARVATION_AGING_THRESHOLD_MINS = 30  # Every 30 mins waited promotes effective priority
STARVATION_AGING_BOOST_PER_INTERVAL = 0.5

# RAG Knowledge Base Parameters
RAG_CHUNK_SIZE = 450
RAG_CHUNK_OVERLAP = 60
RAG_TOP_K = 3
RAG_MIN_SIMILARITY_SCORE = 0.08  # Calibrated for short clinical queries

# Responsible AI Policies & Disclaimers
NON_DIAGNOSTIC_DISCLAIMER = (
    "This application is a decision-support prototype. It does not provide medical diagnoses "
    "or replace qualified healthcare professionals. All clinical decisions and emergency "
    "assessments must be made by authorized healthcare personnel."
)

EMERGENCY_ESCALATION_NOTICE = (
    "CRITICAL WARNING: The reported symptoms meet criteria for IMMEDIATE EMERGENCY ESCALATION. "
    "Do NOT wait in the regular clinic queue. Contact Campus Emergency Medical Services (EMS) "
    "at Ext. 911 / +91-11-2659-6100 immediately or transfer to the nearest Emergency Department."
)

# Admin Default Accounts (Role-Based Access)
DEFAULT_ADMIN_USERS = [
    {"username": "triage_nurse", "name": "Nurse Margaret Kelly", "role": "Triage Nurse", "password": "nurse123!secure"},
    {"username": "chief_physician", "name": "Dr. Ananya Sharma", "role": "Chief Medical Officer", "password": "doc123!secure"},
    {"username": "clinic_admin", "name": "Admin Robert Zhao", "role": "Clinic Administrator", "password": "admin123!secure"},
]
