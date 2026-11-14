"""
First-Come, First-Served (FCFS) Scheduler Module.
Provides baseline sequential appointment scheduling strictly based on arrival timestamps,
partitioned by clinical department for comparative evaluation against Priority-Based scheduling.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    HEALTHCARE_PROVIDERS,
    CLINIC_START_HOUR,
    SLOT_DURATION_MINUTES,
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    RECOMMENDED_MAX_WAIT_MINUTES,
    DEFAULT_DEPARTMENT,
)


class FCFSScheduler:
    """FCFS Scheduler allocating provider slots in strict arrival sequence per department."""

    def __init__(self, providers: List[Dict[str, str]] = None, slot_duration: int = SLOT_DURATION_MINUTES):
        self.providers = providers or HEALTHCARE_PROVIDERS
        self.slot_duration = slot_duration

    def schedule(self, patients: List[Dict[str, Any]], simulation_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Schedule all patients in strict arrival order (FCFS) partitioned by department.
        Allocates slots across providers designated for each department sequentially.
        """
        if not patients:
            return {"appointments": [], "metrics": self._empty_metrics(), "unserved_patients": []}

        # Normalize and sort patients by arrival time
        normalized = []
        for p in patients:
            arr = p["arrival_time"]
            if not isinstance(arr, datetime):
                arr = datetime.fromisoformat(str(arr))
            p_copy = dict(p)
            p_copy["_arr_dt"] = arr
            if "department" not in p_copy or not p_copy["department"]:
                p_copy["department"] = DEFAULT_DEPARTMENT
            normalized.append(p_copy)

        normalized.sort(key=lambda p: p["_arr_dt"])

        base_date = simulation_date or normalized[0]["_arr_dt"]
        clinic_start = base_date.replace(hour=CLINIC_START_HOUR, minute=0, second=0, microsecond=0)

        # Partition by department
        dept_groups: Dict[str, List[Dict[str, Any]]] = {}
        for p in normalized:
            dept = p["department"]
            dept_groups.setdefault(dept, []).append(p)

        all_appointments = []
        unserved = []

        for dept_name, dept_patients in dept_groups.items():
            dept_provs = [prov for prov in self.providers if prov.get("department") == dept_name]
            if not dept_provs:
                fallback_provs = [prov for prov in self.providers if prov.get("department") == DEFAULT_DEPARTMENT]
                dept_provs = fallback_provs if fallback_provs else self.providers

            provider_availability = {prov["id"]: clinic_start for prov in dept_provs}
            provider_names = {prov["id"]: prov["name"] for prov in dept_provs}

            for queue_pos, patient in enumerate(dept_patients, start=1):
                p_arrival = patient["_arr_dt"]
                earliest_prov_id = min(provider_availability, key=provider_availability.get)
                earliest_prov_time = provider_availability[earliest_prov_id]

                slot_start = max(p_arrival, earliest_prov_time)
                slot_end = slot_start + timedelta(minutes=self.slot_duration)
                provider_availability[earliest_prov_id] = slot_end

                wait_minutes = max(0.0, (slot_start - p_arrival).total_seconds() / 60.0)
                priority_cat = patient.get("priority_category", "ROUTINE REVIEW")
                max_recommended = RECOMMENDED_MAX_WAIT_MINUTES.get(priority_cat, 120)
                is_delayed = wait_minutes > max_recommended

                appointment_record = {
                    "patient_id": patient["id"],
                    "patient_code": patient.get("patient_code", f"PAT-{patient['id']}"),
                    "patient_name": patient.get("full_name", "Anonymous"),
                    "department": dept_name,
                    "priority_category": priority_cat,
                    "arrival_time": p_arrival.isoformat(),
                    "slot_start": slot_start.strftime("%Y-%m-%d %H:%M"),
                    "slot_end": slot_end.strftime("%Y-%m-%d %H:%M"),
                    "provider_id": earliest_prov_id,
                    "provider_name": provider_names[earliest_prov_id],
                    "queue_position": queue_pos,
                    "estimated_wait_minutes": round(wait_minutes, 1),
                    "is_clinically_delayed": is_delayed,
                    "max_recommended_wait": max_recommended,
                    "algorithm": "FCFS",
                    "allocation_reason": f"FCFS: Allocated in order of arrival for {dept_name} (Pos #{queue_pos}).",
                    "status": "SCHEDULED",
                }
                all_appointments.append(appointment_record)

        all_appointments.sort(key=lambda a: (a["slot_start"], a["queue_position"]))
        metrics = self._calculate_metrics(all_appointments)
        return {
            "appointments": all_appointments,
            "metrics": metrics,
            "unserved_patients": unserved,
        }

    def _calculate_metrics(self, appointments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute empirical scheduling performance metrics."""
        if not appointments:
            return self._empty_metrics()

        wait_times = [a["estimated_wait_minutes"] for a in appointments]
        urgent_waits = [
            a["estimated_wait_minutes"]
            for a in appointments
            if a["priority_category"] in (PRIORITY_EMERGENCY, PRIORITY_URGENT)
        ]

        delayed_urgent_count = sum(
            1 for a in appointments
            if a["priority_category"] in (PRIORITY_EMERGENCY, PRIORITY_URGENT) and a["is_clinically_delayed"]
        )

        category_breakdown = {}
        for a in appointments:
            cat = a["priority_category"]
            category_breakdown.setdefault(cat, []).append(a["estimated_wait_minutes"])

        category_averages = {
            cat: round(sum(waits) / len(waits), 1)
            for cat, waits in category_breakdown.items()
        }

        return {
            "algorithm": "FCFS",
            "total_patients_served": len(appointments),
            "average_wait_minutes": round(sum(wait_times) / len(wait_times), 1),
            "urgent_average_wait_minutes": round(sum(urgent_waits) / len(urgent_waits), 1) if urgent_waits else 0.0,
            "maximum_wait_minutes": round(max(wait_times), 1),
            "minimum_wait_minutes": round(min(wait_times), 1),
            "urgent_cases_delayed": delayed_urgent_count,
            "category_average_waits": category_averages,
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "algorithm": "FCFS",
            "total_patients_served": 0,
            "average_wait_minutes": 0.0,
            "urgent_average_wait_minutes": 0.0,
            "maximum_wait_minutes": 0.0,
            "minimum_wait_minutes": 0.0,
            "urgent_cases_delayed": 0,
            "category_average_waits": {},
        }
