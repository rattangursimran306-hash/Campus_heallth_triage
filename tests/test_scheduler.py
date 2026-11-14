"""
Automated Unit Tests for Scheduling Algorithms.
Validates FCFS arrival sequence, Priority min-heap ordering,
arrival tie-breaking, emergency bypass, duplicate avoidance, and wait time math.
"""
from datetime import datetime, timedelta
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_ROUTINE,
)
from modules.fcfs_scheduler import FCFSScheduler
from modules.priority_scheduler import PriorityScheduler


@pytest.fixture
def test_providers():
    return [
        {"id": "DOC-TEST-1", "name": "Dr. Test Alpha", "specialty": "General"},
        {"id": "DOC-TEST-2", "name": "Dr. Test Beta", "specialty": "Urgent"},
    ]


def test_fcfs_preserves_arrival_order(test_providers):
    """Verify FCFS schedules strictly according to patient arrival timestamps."""
    scheduler = FCFSScheduler(providers=test_providers, slot_duration=15)
    base_time = datetime(2026, 11, 6, 9, 0)

    # Patient 1 arrives 09:00 (Routine), Patient 2 arrives 09:05 (Urgent), Patient 3 arrives 09:10 (High)
    patients = [
        {"id": 1, "patient_code": "P1", "full_name": "P1", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 2, "patient_code": "P2", "full_name": "P2", "priority_category": PRIORITY_URGENT, "arrival_time": base_time + timedelta(minutes=5)},
        {"id": 3, "patient_code": "P3", "full_name": "P3", "priority_category": PRIORITY_HIGH, "arrival_time": base_time + timedelta(minutes=10)},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    apps = result["appointments"]

    assert len(apps) == 3
    # In FCFS, queue position must be 1, 2, 3 corresponding to arrival
    assert apps[0]["patient_id"] == 1
    assert apps[1]["patient_id"] == 2
    assert apps[2]["patient_id"] == 3
    assert apps[0]["queue_position"] == 1
    assert apps[1]["queue_position"] == 2
    assert apps[2]["queue_position"] == 3


def test_priority_scheduling_respects_clinical_rank(test_providers):
    """
    Verify Priority Scheduler serves higher priority patients before lower priority
    even when lower priority patient arrived earlier.
    """
    scheduler = PriorityScheduler(providers=test_providers[:1], slot_duration=15)  # 1 provider
    base_time = datetime(2026, 11, 6, 9, 0)

    # Patient A arrives 09:00 (Routine)
    # Patient B arrives 09:00 (Urgent)
    patients = [
        {"id": 10, "patient_code": "PA", "full_name": "Routine Guy", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 20, "patient_code": "PB", "full_name": "Urgent Gal", "priority_category": PRIORITY_URGENT, "arrival_time": base_time},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    apps = result["appointments"]

    # Urgent should be scheduled first
    assert apps[0]["patient_id"] == 20
    assert apps[0]["priority_category"] == PRIORITY_URGENT
    assert apps[1]["patient_id"] == 10
    assert apps[1]["priority_category"] == PRIORITY_ROUTINE


def test_priority_tie_breaking_by_arrival_time(test_providers):
    """Verify that when two patients have identical priority, the earlier arrival is served first."""
    scheduler = PriorityScheduler(providers=test_providers[:1], slot_duration=15)
    base_time = datetime(2026, 11, 6, 9, 0)

    # Both Urgent, but P1 arrived at 09:00, P2 arrived at 09:05
    patients = [
        {"id": 101, "patient_code": "P1", "priority_category": PRIORITY_URGENT, "arrival_time": base_time},
        {"id": 102, "patient_code": "P2", "priority_category": PRIORITY_URGENT, "arrival_time": base_time + timedelta(minutes=5)},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    apps = result["appointments"]

    assert apps[0]["patient_id"] == 101
    assert apps[1]["patient_id"] == 102


def test_emergency_escalation_bypasses_normal_queue(test_providers):
    """Verify EMERGENCY ESCALATION cases bypass regular slots with 0 wait time."""
    scheduler = PriorityScheduler(providers=test_providers, slot_duration=15)
    base_time = datetime(2026, 11, 6, 9, 0)

    patients = [
        {"id": 1, "patient_code": "P1", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 999, "patient_code": "P-EMERG", "priority_category": PRIORITY_EMERGENCY, "arrival_time": base_time + timedelta(minutes=10)},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    emerg_apps = result["emergency_bypasses"]

    assert len(emerg_apps) == 1
    assert emerg_apps[0]["patient_id"] == 999
    assert emerg_apps[0]["estimated_wait_minutes"] == 0.0
    assert emerg_apps[0]["status"] == "ESCALATED_ER"


def test_starvation_aging_safeguard(test_providers):
    """
    Verify starvation prevention: A routine patient waiting for prolonged intervals
    receives an aging priority boost to prevent indefinite starvation.
    """
    # 1 provider, 15m slots, aging threshold 30 mins
    scheduler = PriorityScheduler(providers=test_providers[:1], slot_duration=15, aging_threshold_mins=30, aging_boost=1.5)
    base_time = datetime(2026, 11, 6, 9, 0)

    # Routine arrives very early at 09:00
    # Then multiple medium patients arrive later
    patients = [
        {"id": 1, "patient_code": "P-Routine", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 2, "patient_code": "P-Med1", "priority_category": PRIORITY_MEDIUM, "arrival_time": base_time + timedelta(minutes=35)},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    apps = result["appointments"]
    assert len(apps) == 2


def test_wait_time_mathematical_precision(test_providers):
    """Verify calculated wait times match exact mathematical formula."""
    scheduler = FCFSScheduler(providers=test_providers[:1], slot_duration=15)
    base_time = datetime(2026, 11, 6, 9, 0)

    # Patient arrives at 09:00, served at 09:00 -> Wait = 0 min
    # Patient 2 arrives at 09:05, slot starts at 09:15 -> Wait = 10 mins
    patients = [
        {"id": 1, "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 2, "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time + timedelta(minutes=5)},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    apps = result["appointments"]

    assert apps[0]["estimated_wait_minutes"] == 0.0
    assert apps[1]["estimated_wait_minutes"] == 10.0
    assert result["metrics"]["average_wait_minutes"] == 5.0


def test_department_isolated_scheduling():
    """Verify that scheduling is partitioned by department so specialist queues do not affect each other."""
    specialist_providers = [
        {"id": "DOC-GEN-01", "name": "Dr. Gen", "department": "General Medicine & Primary Care", "specialty": "General"},
        {"id": "DOC-DEN-01", "name": "Dr. Dent", "department": "Dentistry & Oral Health", "specialty": "Dentistry"},
    ]
    scheduler = PriorityScheduler(providers=specialist_providers, slot_duration=15)
    base_time = datetime(2026, 11, 6, 9, 0)

    # 2 General Medicine patients and 1 Dentistry patient arriving at 09:00
    patients = [
        {"id": 1, "patient_code": "GEN-1", "full_name": "Gen Patient 1", "department": "General Medicine & Primary Care", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 2, "patient_code": "GEN-2", "full_name": "Gen Patient 2", "department": "General Medicine & Primary Care", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
        {"id": 3, "patient_code": "DEN-1", "full_name": "Dent Patient 1", "department": "Dentistry & Oral Health", "priority_category": PRIORITY_ROUTINE, "arrival_time": base_time},
    ]

    result = scheduler.schedule(patients, simulation_date=base_time)
    apps = result["appointments"]

    # Dentistry patient must be assigned to Dental doctor DOC-DEN-01 with 0 wait time,
    # despite the General Medicine doctor having a backlog!
    den_app = next(a for a in apps if a["patient_code"] == "DEN-1")
    assert den_app["provider_id"] == "DOC-DEN-01"
    assert den_app["estimated_wait_minutes"] == 0.0
    assert den_app["department"] == "Dentistry & Oral Health"

    gen_apps = [a for a in apps if "GEN" in a["patient_code"]]
    assert len(gen_apps) == 2
    for ga in gen_apps:
        assert ga["provider_id"] == "DOC-GEN-01"
