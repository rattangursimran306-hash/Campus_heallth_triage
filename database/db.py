"""
Database access module for Campus Health-Center Decision Support Application.
Provides thread-safe SQLite connection handling, schema migration, and repository methods.
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Ensure base directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATABASE_PATH, DEFAULT_ADMIN_USERS

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def get_db_connection() -> sqlite3.Connection:
    """Return an SQLite connection configured with WAL mode and row factory."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(force_recreate: bool = False) -> None:
    """Initialize database tables from schema.sql, apply migrations, and seed default admins."""
    if force_recreate and DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    conn = get_db_connection()
    with conn:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        # Check and apply migrations for department and inferred_severity
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(Patients)")
        cols = [r["name"] for r in cur.fetchall()]
        if "department" not in cols:
            conn.execute("ALTER TABLE Patients ADD COLUMN department TEXT DEFAULT 'General Medicine & Primary Care'")

        cur.execute("PRAGMA table_info(Symptom_Reports)")
        s_cols = [r["name"] for r in cur.fetchall()]
        if "inferred_severity" not in s_cols:
            conn.execute("ALTER TABLE Symptom_Reports ADD COLUMN inferred_severity INTEGER DEFAULT 1")

        cur.execute("PRAGMA table_info(Appointments)")
        a_cols = [r["name"] for r in cur.fetchall()]
        if "department" not in a_cols:
            conn.execute("ALTER TABLE Appointments ADD COLUMN department TEXT DEFAULT 'General Medicine & Primary Care'")

        # Seed default admin users if none exist
        cur.execute("SELECT COUNT(*) as cnt FROM Admin_Users")
        if cur.fetchone()["cnt"] == 0:
            for user in DEFAULT_ADMIN_USERS:
                pwd_hash = hashlib.sha256(user["password"].encode("utf-8")).hexdigest()
                cur.execute(
                    """
                    INSERT INTO Admin_Users (username, full_name, role, password_hash)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user["username"], user["name"], user["role"], pwd_hash),
                )
    conn.close()


def purge_patient_data() -> None:
    """Completely wipe all patient, symptom, triage, appointment, and history records."""
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM Appointments")
        conn.execute("DELETE FROM Triggered_Rules")
        conn.execute("DELETE FROM Symptom_Reports")
        conn.execute("DELETE FROM Scheduling_History")
        conn.execute("DELETE FROM Patients")
        conn.execute("DELETE FROM Audit_Logs")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('Patients', 'Symptom_Reports', 'Triggered_Rules', 'Appointments', 'Scheduling_History', 'Audit_Logs')")
        conn.execute(
            """
            INSERT INTO Audit_Logs (admin_user, action_type, details)
            VALUES ('SYSTEM', 'CLEAN_STATE_INITIALIZED', 'All synthetic demo records removed. System is clean and ready for live intake.')
            """
        )
    conn.execute("VACUUM")
    conn.close()


# ---------------- Patient Repository ----------------

def insert_patient(
    patient_code: str,
    full_name: str,
    age: int,
    gender: Optional[str] = None,
    contact: Optional[str] = None,
    department: str = "General Medicine & Primary Care",
) -> int:
    """Insert a new patient and return the generated ID."""
    conn = get_db_connection()
    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO Patients (patient_code, full_name, age, gender, contact, department)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_code, full_name, age, gender, contact, department),
        )
        patient_id = cur.lastrowid
    conn.close()
    return patient_id


def insert_symptom_report(
    patient_id: int,
    symptoms: List[str],
    additional_description: str,
    duration_days: float,
    pain_scale: int = 0,
    inferred_severity: int = 1,
    temperature_c: Optional[float] = None,
    respiratory_distress: bool = False,
    altered_consciousness: bool = False,
    severe_chest_pain: bool = False,
    uncontrolled_bleeding: bool = False,
) -> int:
    """Record patient self-reported symptoms and vital signs."""
    conn = get_db_connection()
    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO Symptom_Reports (
                patient_id, symptoms_json, additional_description, duration_days,
                pain_scale, inferred_severity, temperature_c, respiratory_distress,
                altered_consciousness, severe_chest_pain, uncontrolled_bleeding
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                json.dumps(symptoms),
                additional_description,
                duration_days,
                pain_scale,
                inferred_severity,
                temperature_c,
                1 if respiratory_distress else 0,
                1 if altered_consciousness else 0,
                1 if severe_chest_pain else 0,
                1 if uncontrolled_bleeding else 0,
            ),
        )
        report_id = cur.lastrowid
    conn.close()
    return report_id


# ---------------- Rules & Triage Repository ----------------

def upsert_rule_definition(
    rule_id: str,
    category: str,
    name: str,
    condition_description: str,
    action_priority: str,
    clinical_rationale: str,
    source_protocol: str,
    is_active: bool = True,
) -> None:
    """Insert or update a documented clinical rule."""
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO Rule_Definitions (
                rule_id, category, name, condition_description, action_priority,
                clinical_rationale, source_protocol, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rule_id) DO UPDATE SET
                category=excluded.category,
                name=excluded.name,
                condition_description=excluded.condition_description,
                action_priority=excluded.action_priority,
                clinical_rationale=excluded.clinical_rationale,
                source_protocol=excluded.source_protocol,
                is_active=excluded.is_active
            """,
            (rule_id, category, name, condition_description, action_priority, clinical_rationale, source_protocol, 1 if is_active else 0),
        )
    conn.close()


def record_triggered_rules(patient_id: int, triggered_list: List[Dict[str, Any]]) -> None:
    """Store triggered rules for a patient evaluation session."""
    conn = get_db_connection()
    with conn:
        # Clear previous records for this patient to ensure fresh run consistency
        conn.execute("DELETE FROM Triggered_Rules WHERE patient_id = ?", (patient_id,))
        for tr in triggered_list:
            conn.execute(
                """
                INSERT INTO Triggered_Rules (patient_id, rule_id, explanation, facts_matched_json, is_conflict_winner)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    tr["rule_id"],
                    tr["explanation"],
                    json.dumps(tr.get("facts_matched", [])),
                    1 if tr.get("is_conflict_winner", False) else 0,
                ),
            )
    conn.close()


# ---------------- Appointments & Scheduling Repository ----------------

def insert_appointment(
    patient_id: int,
    slot_start: str,
    slot_end: str,
    provider_id: str,
    provider_name: str,
    priority_category: str,
    algorithm: str,
    queue_position: Optional[int] = None,
    estimated_wait_minutes: Optional[float] = None,
    status: str = "SCHEDULED",
    department: str = "General Medicine & Primary Care",
) -> int:
    """Insert or replace an allocated appointment with department tag."""
    conn = get_db_connection()
    with conn:
        cur = conn.cursor()
        # Delete existing active appointment for this algorithm to avoid duplicates
        cur.execute("DELETE FROM Appointments WHERE patient_id = ? AND algorithm = ?", (patient_id, algorithm))
        cur.execute(
            """
            INSERT INTO Appointments (
                patient_id, slot_start, slot_end, provider_id, provider_name,
                priority_category, status, algorithm, queue_position, estimated_wait_minutes, department
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                slot_start,
                slot_end,
                provider_id,
                provider_name,
                priority_category,
                status,
                algorithm,
                queue_position,
                estimated_wait_minutes,
                department,
            ),
        )
        appointment_id = cur.lastrowid
    conn.close()
    return appointment_id


def update_appointment_status(appointment_id: int, new_status: str, admin_user: str, reason: str = "") -> None:
    """Update status of an appointment with audit log entry."""
    conn = get_db_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM Appointments WHERE id = ?", (appointment_id,))
        app = cur.fetchone()
        if not app:
            conn.close()
            raise ValueError(f"Appointment with ID {appointment_id} does not exist.")

        old_status = app["status"]
        patient_id = app["patient_id"]
        cur.execute("UPDATE Appointments SET status = ? WHERE id = ?", (new_status, appointment_id))
    conn.close()

    # Record audit log after closing previous connection to prevent lock
    record_audit_log(
        admin_user=admin_user,
        action_type="STATUS_UPDATE",
        patient_id=patient_id,
        details=f"Appointment {appointment_id} status changed from {old_status} to {new_status}. Reason: {reason}",
    )


def record_scheduling_history(
    patient_id: int,
    action: str,
    old_slot: Optional[str],
    new_slot: Optional[str],
    old_priority: Optional[str],
    new_priority: Optional[str],
    reason: str,
    changed_by: str,
) -> None:
    """Record manual or algorithmic changes to scheduling."""
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO Scheduling_History (
                patient_id, action, old_slot, new_slot, old_priority, new_priority, reason, changed_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (patient_id, action, old_slot, new_slot, old_priority, new_priority, reason, changed_by),
        )
    conn.close()


# ---------------- Audit Logs & Governance ----------------

def record_audit_log(admin_user: str, action_type: str, patient_id: Optional[int], details: str, ip_address: str = "127.0.0.1") -> int:
    """Record an immutable action in the audit log."""
    conn = get_db_connection()
    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO Audit_Logs (admin_user, action_type, patient_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_user, action_type, patient_id, details, ip_address),
        )
        log_id = cur.lastrowid
    conn.close()
    return log_id


def get_audit_logs(limit: int = 150) -> List[Dict[str, Any]]:
    """Retrieve recent audit logs ordered by timestamp descending."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.*, p.patient_code, p.full_name as patient_name
        FROM Audit_Logs a
        LEFT JOIN Patients p ON a.patient_id = p.id
        ORDER BY a.timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------- Read Queries for Dashboard ----------------

def get_all_patients_with_triage(department: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve full patient listing with latest symptoms, triggered rules, and appointments.
    Optionally filtered by department.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT
            p.id, p.patient_code, p.full_name, p.age, p.gender, p.contact, p.department, p.created_at,
            s.symptoms_json, s.additional_description, s.duration_days, s.pain_scale, s.inferred_severity, s.temperature_c,
            s.respiratory_distress, s.altered_consciousness, s.severe_chest_pain, s.uncontrolled_bleeding,
            tr.rule_id as winning_rule_id, tr.explanation as winning_explanation,
            rd.action_priority as priority_category, rd.name as rule_name,
            ap.id as appointment_id, ap.slot_start, ap.slot_end, ap.provider_id, ap.provider_name,
            ap.department as appointment_department, ap.status as appointment_status,
            ap.algorithm, ap.queue_position, ap.estimated_wait_minutes
        FROM Patients p
        LEFT JOIN Symptom_Reports s ON p.id = s.patient_id
        LEFT JOIN Triggered_Rules tr ON p.id = tr.patient_id AND tr.is_conflict_winner = 1
        LEFT JOIN Rule_Definitions rd ON tr.rule_id = rd.rule_id
        LEFT JOIN Appointments ap ON p.id = ap.patient_id AND ap.algorithm = 'PRIORITY_AGENT'
    """
    params = []
    if department and department != "ALL" and department != "All Departments":
        query += " WHERE p.department = ?"
        params.append(department)

    query += " ORDER BY p.id DESC"
    cur.execute(query, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    for r in rows:
        if r.get("symptoms_json"):
            try:
                r["symptoms"] = json.loads(r["symptoms_json"])
            except Exception:
                r["symptoms"] = []
        else:
            r["symptoms"] = []
    return rows


def get_patient_details(patient_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve comprehensive profile of a single patient including all triggered rules."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = cur.fetchone()
    if not patient:
        conn.close()
        return None

    patient_dict = dict(patient)

    # Symptoms
    cur.execute("SELECT * FROM Symptom_Reports WHERE patient_id = ? ORDER BY id DESC LIMIT 1", (patient_id,))
    symptom = cur.fetchone()
    patient_dict["symptom_report"] = dict(symptom) if symptom else {}
    if patient_dict["symptom_report"].get("symptoms_json"):
        patient_dict["symptom_report"]["symptoms"] = json.loads(patient_dict["symptom_report"]["symptoms_json"])
    else:
        patient_dict["symptom_report"]["symptoms"] = []

    # Triggered rules
    cur.execute(
        """
        SELECT tr.*, rd.name as rule_name, rd.category, rd.action_priority, rd.clinical_rationale, rd.source_protocol
        FROM Triggered_Rules tr
        JOIN Rule_Definitions rd ON tr.rule_id = rd.rule_id
        WHERE tr.patient_id = ?
        ORDER BY tr.is_conflict_winner DESC, tr.id ASC
        """,
        (patient_id,),
    )
    patient_dict["triggered_rules"] = [dict(r) for r in cur.fetchall()]

    # Appointments
    cur.execute("SELECT * FROM Appointments WHERE patient_id = ?", (patient_id,))
    patient_dict["appointments"] = [dict(r) for r in cur.fetchall()]

    # History
    cur.execute("SELECT * FROM Scheduling_History WHERE patient_id = ? ORDER BY changed_at DESC", (patient_id,))
    patient_dict["scheduling_history"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return patient_dict


def get_dashboard_kpis(department: Optional[str] = None) -> Dict[str, Any]:
    """Calculate real-time operational KPIs for the administrative overview, optionally filtered by department."""
    conn = get_db_connection()
    cur = conn.cursor()

    dept_filter = department if (department and department != "ALL" and department != "All Departments") else None

    if dept_filter:
        cur.execute("SELECT COUNT(*) as total_patients FROM Patients WHERE department = ?", (dept_filter,))
        total_patients = cur.fetchone()["total_patients"]

        cur.execute(
            """
            SELECT COUNT(*) as awaiting_review
            FROM Appointments ap
            JOIN Patients p ON ap.patient_id = p.id
            WHERE ap.status IN ('SCHEDULED', 'IN_PROGRESS')
              AND ap.algorithm = 'PRIORITY_AGENT'
              AND p.department = ?
            """,
            (dept_filter,),
        )
        awaiting_review = cur.fetchone()["awaiting_review"]

        cur.execute(
            """
            SELECT COUNT(*) as emergency_count
            FROM Appointments ap
            JOIN Patients p ON ap.patient_id = p.id
            WHERE ap.priority_category = 'EMERGENCY ESCALATION'
              AND ap.algorithm = 'PRIORITY_AGENT'
              AND p.department = ?
            """,
            (dept_filter,),
        )
        emergency_count = cur.fetchone()["emergency_count"]

        cur.execute(
            """
            SELECT COUNT(*) as high_priority_count
            FROM Appointments ap
            JOIN Patients p ON ap.patient_id = p.id
            WHERE ap.priority_category IN ('URGENT REVIEW', 'HIGH PRIORITY REVIEW')
              AND ap.algorithm = 'PRIORITY_AGENT'
              AND p.department = ?
            """,
            (dept_filter,),
        )
        high_priority_count = cur.fetchone()["high_priority_count"]

        cur.execute(
            """
            SELECT COUNT(*) as completed_count
            FROM Appointments ap
            JOIN Patients p ON ap.patient_id = p.id
            WHERE ap.status = 'COMPLETED'
              AND ap.algorithm = 'PRIORITY_AGENT'
              AND p.department = ?
            """,
            (dept_filter,),
        )
        completed_count = cur.fetchone()["completed_count"]

        cur.execute(
            """
            SELECT AVG(ap.estimated_wait_minutes) as avg_wait
            FROM Appointments ap
            JOIN Patients p ON ap.patient_id = p.id
            WHERE ap.algorithm = 'PRIORITY_AGENT'
              AND ap.priority_category != 'EMERGENCY ESCALATION'
              AND p.department = ?
            """,
            (dept_filter,),
        )
        avg_wait = cur.fetchone()["avg_wait"] or 0.0
    else:
        cur.execute("SELECT COUNT(*) as total_patients FROM Patients")
        total_patients = cur.fetchone()["total_patients"]

        cur.execute(
            """
            SELECT COUNT(*) as awaiting_review
            FROM Appointments
            WHERE status IN ('SCHEDULED', 'IN_PROGRESS') AND algorithm = 'PRIORITY_AGENT'
            """
        )
        awaiting_review = cur.fetchone()["awaiting_review"]

        cur.execute(
            """
            SELECT COUNT(*) as emergency_count
            FROM Appointments
            WHERE priority_category = 'EMERGENCY ESCALATION' AND algorithm = 'PRIORITY_AGENT'
            """
        )
        emergency_count = cur.fetchone()["emergency_count"]

        cur.execute(
            """
            SELECT COUNT(*) as high_priority_count
            FROM Appointments
            WHERE priority_category IN ('URGENT REVIEW', 'HIGH PRIORITY REVIEW') AND algorithm = 'PRIORITY_AGENT'
            """
        )
        high_priority_count = cur.fetchone()["high_priority_count"]

        cur.execute(
            """
            SELECT COUNT(*) as completed_count
            FROM Appointments
            WHERE status = 'COMPLETED' AND algorithm = 'PRIORITY_AGENT'
            """
        )
        completed_count = cur.fetchone()["completed_count"]

        cur.execute(
            """
            SELECT AVG(estimated_wait_minutes) as avg_wait
            FROM Appointments
            WHERE algorithm = 'PRIORITY_AGENT' AND priority_category != 'EMERGENCY ESCALATION'
            """
        )
        avg_wait = cur.fetchone()["avg_wait"] or 0.0

    conn.close()
    return {
        "total_patients": total_patients,
        "awaiting_review": awaiting_review,
        "emergency_count": emergency_count,
        "high_priority_count": high_priority_count,
        "completed_count": completed_count,
        "avg_wait_minutes": round(avg_wait, 1),
    }


def get_doctor_roster_stats(department: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve real-time workload statistics for healthcare providers,
    including queued patients, current consultation, and estimated waiting time.
    """
    from config import HEALTHCARE_PROVIDERS
    conn = get_db_connection()
    cur = conn.cursor()

    dept_filter = department if (department and department != "ALL" and department != "All Departments") else None
    matched_providers = [p for p in HEALTHCARE_PROVIDERS if not dept_filter or p.get("department") == dept_filter]

    roster_list = []
    for prov in matched_providers:
        prov_id = prov["id"]
        # Fetch active scheduled / in-progress appointments for this provider
        cur.execute(
            """
            SELECT ap.*, p.patient_code, p.full_name as patient_name
            FROM Appointments ap
            JOIN Patients p ON ap.patient_id = p.id
            WHERE ap.provider_id = ? AND ap.status IN ('SCHEDULED', 'IN_PROGRESS') AND ap.algorithm = 'PRIORITY_AGENT'
            ORDER BY ap.slot_start ASC
            """,
            (prov_id,),
        )
        active_apps = [dict(r) for r in cur.fetchall()]
        active_count = len(active_apps)
        total_wait_backlog = sum(a.get("estimated_wait_minutes", 0.0) or 0.0 for a in active_apps)
        avg_wait = round(total_wait_backlog / active_count, 1) if active_count > 0 else 0.0

        next_slot = active_apps[0]["slot_start"] if active_apps else "Available Now"
        status_label = "In Consultation" if any(a["status"] == "IN_PROGRESS" for a in active_apps) else ("Accepting Patients" if active_count < 4 else "High Load")

        roster_list.append({
            "id": prov["id"],
            "name": prov["name"],
            "department": prov.get("department", "General Medicine"),
            "specialty": prov.get("specialty", "General"),
            "active_patients_count": active_count,
            "estimated_wait_minutes": avg_wait,
            "next_slot": next_slot,
            "status_label": status_label,
            "active_appointments": active_apps,
        })

    conn.close()
    return roster_list
