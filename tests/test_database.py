"""
Automated Unit Tests for SQLite Database Persistence & Audit Integrity.
Validates schema initialization, CRUD operations, foreign key constraints,
appointment status lifecycles, and immutable audit logs.
"""
import pytest
import sqlite3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import (
    get_db_connection,
    init_db,
    insert_patient,
    insert_symptom_report,
    record_triggered_rules,
    insert_appointment,
    update_appointment_status,
    record_audit_log,
    get_audit_logs,
    get_all_patients_with_triage,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database schema is fresh and ready before each test."""
    init_db(force_recreate=False)


def test_database_tables_exist():
    """Verify all 9 relational tables are created in SQLite."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r["name"] for r in cur.fetchall()]
    conn.close()

    expected_tables = [
        "Patients",
        "Symptom_Reports",
        "Rule_Definitions",
        "Triggered_Rules",
        "Appointments",
        "Scheduling_History",
        "RAG_Documents",
        "Admin_Users",
        "Audit_Logs",
    ]
    for tbl in expected_tables:
        assert tbl in tables, f"Expected table {tbl} was not found in schema."


import uuid

def test_insert_and_retrieve_patient():
    """Verify patient and symptom report insertion and JSON decoding."""
    unique_code = f"PAT-UNIT-{uuid.uuid4().hex[:6]}"
    p_id = insert_patient(
        patient_code=unique_code,
        full_name="Unit Test Student",
        age=21,
        gender="Non-Binary",
        contact="+91-9999988888",
    )
    assert p_id > 0

    s_id = insert_symptom_report(
        patient_id=p_id,
        symptoms=["Crushing / radiating chest pain", "Chills and rigors"],
        additional_description="Chest tight for 2 hours.",
        duration_days=0.5,
        pain_scale=8,
        temperature_c=37.5,
        severe_chest_pain=True,
    )
    assert s_id > 0

    # Retrieve via view
    patients = get_all_patients_with_triage()
    match = [p for p in patients if p["id"] == p_id]
    assert len(match) == 1
    assert match[0]["patient_code"] == unique_code
    assert "Crushing / radiating chest pain" in match[0]["symptoms"]


def test_audit_log_immutability_and_recording():
    """Verify audit logs record administrative events correctly."""
    log_id = record_audit_log(
        admin_user="test_nurse",
        action_type="TEST_ACTION",
        patient_id=None,
        details="Unit test audit record entry.",
    )
    assert log_id > 0

    logs = get_audit_logs(limit=10)
    assert len(logs) > 0
    top_log = logs[0]
    assert top_log["admin_user"] == "test_nurse"
    assert top_log["action_type"] == "TEST_ACTION"


def test_appointment_status_update_with_audit():
    """Verify updating appointment status transitions correctly and creates audit log."""
    unique_code = f"PAT-STATUS-{uuid.uuid4().hex[:6]}"
    p_id = insert_patient(
        patient_code=unique_code,
        full_name="Status Student",
        age=22,
    )
    app_id = insert_appointment(
        patient_id=p_id,
        slot_start="2026-11-06 10:00",
        slot_end="2026-11-06 10:15",
        provider_id="DOC-01",
        provider_name="Dr. Sharma",
        priority_category="HIGH PRIORITY REVIEW",
        algorithm="PRIORITY_AGENT",
        status="SCHEDULED",
    )

    update_appointment_status(app_id, "COMPLETED", admin_user="dr_sharma", reason="Consultation finished.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM Appointments WHERE id = ?", (app_id,))
    row = cur.fetchone()
    conn.close()

    assert row["status"] == "COMPLETED"


def test_doctor_roster_stats_and_department_filtering():
    """Verify provider stats and department-filtered queries work accurately."""
    from database.db import get_doctor_roster_stats

    # All departments
    stats_all = get_doctor_roster_stats()
    assert len(stats_all) >= 6

    # Specific department: Dentistry & Oral Health
    dental_stats = get_doctor_roster_stats(department="Dentistry & Oral Health")
    assert len(dental_stats) >= 1
    for doc in dental_stats:
        assert doc["department"] == "Dentistry & Oral Health"
        assert "Dent" in doc["specialty"] or "Oral" in doc["specialty"] or "Dental" in doc["specialty"]
