"""
Priority Agent Module for Campus Health-Center Decision Support Application.
Acts as the central intelligent decision coordinator:
- Coordinates patient intake and production rule evaluation
- Dispatches scheduling allocation (Priority Queue vs FCFS baseline)
- Records triggered rules, explanations, and appointment slots into SQLite
- Runs comparative empirical benchmarks and computes Urgent Wait Reduction %
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.rule_engine import evaluate_patient_triage
from modules.fcfs_scheduler import FCFSScheduler
from modules.priority_scheduler import PriorityScheduler
from database.db import (
    record_triggered_rules,
    insert_appointment,
    record_scheduling_history,
    get_all_patients_with_triage,
)


class PriorityAgent:
    """Intelligent agent orchestrating clinical triage and slot allocation."""

    def __init__(self):
        self.priority_scheduler = PriorityScheduler()
        self.fcfs_scheduler = FCFSScheduler()

    def process_patient_triage_and_schedule(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        End-to-end workflow for a single incoming patient:
        1. Evaluate symptoms through production rule engine.
        2. Record triggered rules and explanations in database.
        3. Allocate appointment slot via Priority Scheduler.
        4. Save appointment to database.
        """
        patient_id = patient_data["id"]

        # 1. Rule evaluation
        triage_result = evaluate_patient_triage(patient_data)
        category = triage_result["category"]

        # 2. Persist triggered rules in database
        record_triggered_rules(patient_id, triage_result["triggered_rules"])

        # 3. Schedule with Priority Scheduler
        # Prepare patient payload with arrival time
        arrival_dt = patient_data.get("created_at")
        if isinstance(arrival_dt, str):
            try:
                arrival_dt = datetime.fromisoformat(arrival_dt)
            except Exception:
                arrival_dt = datetime.now()
        elif not isinstance(arrival_dt, datetime):
            arrival_dt = datetime.now()

        dept = patient_data.get("department", "General Medicine & Primary Care")
        patient_sched_payload = [
            {
                "id": patient_id,
                "patient_code": patient_data.get("patient_code", f"PAT-{patient_id}"),
                "full_name": patient_data.get("full_name", "Anonymous"),
                "department": dept,
                "priority_category": category,
                "arrival_time": arrival_dt,
            }
        ]

        sched_outcome = self.priority_scheduler.schedule(patient_sched_payload)
        appointment = sched_outcome["appointments"][0] if sched_outcome["appointments"] else None

        appointment_id = None
        if appointment:
            appointment_id = insert_appointment(
                patient_id=patient_id,
                slot_start=appointment["slot_start"],
                slot_end=appointment["slot_end"],
                provider_id=appointment["provider_id"],
                provider_name=appointment["provider_name"],
                priority_category=appointment["priority_category"],
                algorithm="PRIORITY_AGENT",
                queue_position=appointment["queue_position"],
                estimated_wait_minutes=appointment["estimated_wait_minutes"],
                status=appointment["status"],
                department=appointment.get("department", dept),
            )

            record_scheduling_history(
                patient_id=patient_id,
                action="INITIAL_ALLOCATION",
                old_slot=None,
                new_slot=f"{appointment['slot_start']} with {appointment['provider_name']}",
                old_priority=None,
                new_priority=category,
                reason=appointment["allocation_reason"],
                changed_by="SYSTEM_PRIORITY_AGENT",
            )

        return {
            "patient_id": patient_id,
            "triage_result": triage_result,
            "appointment": appointment,
            "appointment_id": appointment_id,
        }

    def run_comparative_simulation(self, patient_cohort: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run both FCFS and Priority-Based schedulers on an identical patient dataset.
        Computes side-by-side metrics and mathematical wait time reduction.
        """
        if not patient_cohort:
            return {"error": "Patient cohort is empty."}

        # 1. Run FCFS
        fcfs_result = self.fcfs_scheduler.schedule(patient_cohort)

        # 2. Run Priority Scheduler
        priority_result = self.priority_scheduler.schedule(patient_cohort)

        # 3. Calculate Comparative Metrics
        fcfs_metrics = fcfs_result["metrics"]
        prio_metrics = priority_result["metrics"]

        fcfs_urgent_wait = fcfs_metrics.get("urgent_average_wait_minutes", 0.0)
        prio_urgent_wait = prio_metrics.get("urgent_average_wait_minutes", 0.0)

        # Urgent wait reduction formula:
        # ((FCFS Urgent - Priority Urgent) / FCFS Urgent) * 100
        if fcfs_urgent_wait > 0.001:
            urgent_wait_reduction_pct = ((fcfs_urgent_wait - prio_urgent_wait) / fcfs_urgent_wait) * 100.0
        else:
            urgent_wait_reduction_pct = 0.0

        # General average wait difference
        fcfs_avg_wait = fcfs_metrics.get("average_wait_minutes", 0.0)
        prio_avg_wait = prio_metrics.get("average_wait_minutes", 0.0)
        avg_wait_diff = fcfs_avg_wait - prio_avg_wait

        return {
            "fcfs": {
                "appointments": fcfs_result["appointments"],
                "metrics": fcfs_metrics,
            },
            "priority": {
                "appointments": priority_result["appointments"],
                "metrics": prio_metrics,
            },
            "comparison": {
                "urgent_wait_reduction_pct": round(urgent_wait_reduction_pct, 1),
                "fcfs_urgent_avg_wait": fcfs_urgent_wait,
                "priority_urgent_avg_wait": prio_urgent_wait,
                "urgent_minutes_saved": round(fcfs_urgent_wait - prio_urgent_wait, 1),
                "fcfs_overall_avg_wait": fcfs_avg_wait,
                "priority_overall_avg_wait": prio_avg_wait,
                "urgent_cases_delayed_fcfs": fcfs_metrics.get("urgent_cases_delayed", 0),
                "urgent_cases_delayed_priority": prio_metrics.get("urgent_cases_delayed", 0),
                "total_patients": len(patient_cohort),
            },
        }
