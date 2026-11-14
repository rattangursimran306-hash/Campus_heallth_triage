"""
Priority-Based Scheduling Agent Module.
Implements intelligent min-heap (heapq) priority queue scheduling with:
- Approved clinical priority category ordering
- Arrival timestamp tie-breaking
- Emergency escalation direct bypass (zero clinic queue delay)
- Starvation aging safeguards (dynamic priority promotion for long waits)
- Provider slot capacity tracking partitioned by Department / Specialty
"""
import heapq
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    HEALTHCARE_PROVIDERS,
    CLINIC_START_HOUR,
    SLOT_DURATION_MINUTES,
    PRIORITY_RANKS,
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    RECOMMENDED_MAX_WAIT_MINUTES,
    STARVATION_AGING_THRESHOLD_MINS,
    STARVATION_AGING_BOOST_PER_INTERVAL,
    DEFAULT_DEPARTMENT,
)


class PriorityScheduler:
    """Priority Queue Scheduler powered by Python heapq with starvation prevention and department isolation."""

    def __init__(
        self,
        providers: List[Dict[str, str]] = None,
        slot_duration: int = SLOT_DURATION_MINUTES,
        aging_threshold_mins: int = STARVATION_AGING_THRESHOLD_MINS,
        aging_boost: float = STARVATION_AGING_BOOST_PER_INTERVAL,
    ):
        self.providers = providers or HEALTHCARE_PROVIDERS
        self.slot_duration = slot_duration
        self.aging_threshold_mins = aging_threshold_mins
        self.aging_boost = aging_boost

    def schedule(self, patients: List[Dict[str, Any]], simulation_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Execute Priority-Based appointment scheduling partitioned by clinical department.
        Emergency cases bypass ordinary queues; other patients are processed via min-heap.
        Specialist queues (Dentistry, Gynecology, Orthopedics, etc.) operate independently.
        """
        if not patients:
            return {"appointments": [], "metrics": self._empty_metrics(), "emergency_bypasses": []}

        # Normalize arrival times
        normalized_patients = []
        for p in patients:
            arr = p["arrival_time"]
            if not isinstance(arr, datetime):
                arr = datetime.fromisoformat(str(arr))
            p_copy = dict(p)
            p_copy["_arr_dt"] = arr
            if "department" not in p_copy or not p_copy["department"]:
                p_copy["department"] = DEFAULT_DEPARTMENT
            normalized_patients.append(p_copy)

        # Sort by arrival time initially
        normalized_patients.sort(key=lambda p: p["_arr_dt"])

        base_date = simulation_date or normalized_patients[0]["_arr_dt"]
        clinic_start = base_date.replace(hour=CLINIC_START_HOUR, minute=0, second=0, microsecond=0)

        # Partition patients by department
        dept_groups: Dict[str, List[Dict[str, Any]]] = {}
        for p in normalized_patients:
            dept = p["department"]
            dept_groups.setdefault(dept, []).append(p)

        all_appointments = []
        all_emergency = []

        # Schedule each department independently
        for dept_name, dept_patients in dept_groups.items():
            dept_provs = [prov for prov in self.providers if prov.get("department") == dept_name]
            if not dept_provs:
                # If no provider specifically tagged with this department, check fallback
                fallback_provs = [prov for prov in self.providers if prov.get("department") == DEFAULT_DEPARTMENT]
                dept_provs = fallback_provs if fallback_provs else self.providers

            dept_res = self._schedule_department_cohort(dept_patients, dept_provs, clinic_start, dept_name)
            all_appointments.extend(dept_res["appointments"])
            all_emergency.extend(dept_res["emergency_bypasses"])

        # Sort all appointments chronologically for display
        all_appointments.sort(key=lambda a: (a["slot_start"], a["queue_position"]))

        metrics = self._calculate_metrics(all_appointments)
        return {
            "appointments": all_appointments,
            "metrics": metrics,
            "emergency_bypasses": all_emergency,
        }

    def _schedule_department_cohort(
        self,
        patients: List[Dict[str, Any]],
        providers: List[Dict[str, Any]],
        clinic_start: datetime,
        dept_name: str,
    ) -> Dict[str, Any]:
        """Schedule a single department's cohort against its designated specialist providers."""
        emergency_appointments = []
        schedulable_patients = []

        for p in patients:
            cat = p.get("priority_category", "ROUTINE REVIEW")
            if cat == PRIORITY_EMERGENCY:
                arr = p["_arr_dt"]
                emergency_appointments.append({
                    "patient_id": p["id"],
                    "patient_code": p.get("patient_code", f"PAT-{p['id']}"),
                    "patient_name": p.get("full_name", "Anonymous"),
                    "department": dept_name,
                    "priority_category": PRIORITY_EMERGENCY,
                    "arrival_time": arr.isoformat(),
                    "slot_start": arr.strftime("%Y-%m-%d %H:%M"),
                    "slot_end": (arr + timedelta(minutes=self.slot_duration)).strftime("%Y-%m-%d %H:%M"),
                    "provider_id": "EMS-BAY",
                    "provider_name": f"Emergency Medical Bay ({dept_name})",
                    "queue_position": 0,
                    "estimated_wait_minutes": 0.0,
                    "is_clinically_delayed": False,
                    "max_recommended_wait": 0,
                    "algorithm": "PRIORITY_AGENT",
                    "allocation_reason": "EMERGENCY BYPASS: Immediate acute stabilization & ER transfer protocol activated.",
                    "status": "ESCALATED_ER",
                })
            else:
                schedulable_patients.append(p)

        provider_availability = {prov["id"]: clinic_start for prov in providers}
        provider_names = {prov["id"]: prov["name"] for prov in providers}

        regular_appointments = []
        queue_counter = 0
        unassigned = list(schedulable_patients)
        current_time = clinic_start
        queue_pos = 1

        while unassigned:
            earliest_prov_id = min(provider_availability, key=provider_availability.get)
            earliest_prov_time = provider_availability[earliest_prov_id]

            horizon_time = max(current_time, earliest_prov_time)
            ready_patients = [p for p in unassigned if p["_arr_dt"] <= horizon_time]

            if not ready_patients:
                next_patient = min(unassigned, key=lambda p: p["_arr_dt"])
                horizon_time = next_patient["_arr_dt"]
                ready_patients = [p for p in unassigned if p["_arr_dt"] <= horizon_time]

            heap = []
            for p in ready_patients:
                base_rank = PRIORITY_RANKS.get(p.get("priority_category", "ROUTINE REVIEW"), 4)
                arr = p["_arr_dt"]
                wait_so_far = max(0.0, (horizon_time - arr).total_seconds() / 60.0)

                aging_intervals = int(wait_so_far / self.aging_threshold_mins) if self.aging_threshold_mins > 0 else 0
                effective_rank = max(0.5, base_rank - (aging_intervals * self.aging_boost))

                queue_counter += 1
                heapq.heappush(heap, (effective_rank, arr, queue_counter, p, aging_intervals))

            effective_rank, arr, _, chosen_p, aging_intervals = heapq.heappop(heap)
            unassigned.remove(chosen_p)

            slot_start = max(chosen_p["_arr_dt"], earliest_prov_time)
            slot_end = slot_start + timedelta(minutes=self.slot_duration)
            provider_availability[earliest_prov_id] = slot_end
            current_time = slot_start

            wait_minutes = max(0.0, (slot_start - chosen_p["_arr_dt"]).total_seconds() / 60.0)
            priority_cat = chosen_p.get("priority_category", "ROUTINE REVIEW")
            max_recommended = RECOMMENDED_MAX_WAIT_MINUTES.get(priority_cat, 120)
            is_delayed = wait_minutes > max_recommended

            reason_parts = [f"Priority: [{priority_cat}] (Rank {PRIORITY_RANKS.get(priority_cat, 4)})"]
            if aging_intervals > 0:
                reason_parts.append(f"Starvation safeguard applied (+{aging_intervals * self.aging_boost} priority boost for {int(wait_so_far)}m wait)")
            reason_parts.append(f"Dept: {dept_name}")
            reason_parts.append(f"Arrival: {chosen_p['_arr_dt'].strftime('%H:%M')}")

            regular_appointments.append({
                "patient_id": chosen_p["id"],
                "patient_code": chosen_p.get("patient_code", f"PAT-{chosen_p['id']}"),
                "patient_name": chosen_p.get("full_name", "Anonymous"),
                "department": dept_name,
                "priority_category": priority_cat,
                "arrival_time": chosen_p["_arr_dt"].isoformat(),
                "slot_start": slot_start.strftime("%Y-%m-%d %H:%M"),
                "slot_end": slot_end.strftime("%Y-%m-%d %H:%M"),
                "provider_id": earliest_prov_id,
                "provider_name": provider_names[earliest_prov_id],
                "queue_position": queue_pos,
                "estimated_wait_minutes": round(wait_minutes, 1),
                "is_clinically_delayed": is_delayed,
                "max_recommended_wait": max_recommended,
                "algorithm": "PRIORITY_AGENT",
                "allocation_reason": " | ".join(reason_parts),
                "status": "SCHEDULED",
            })
            queue_pos += 1

        return {
            "appointments": emergency_appointments + regular_appointments,
            "emergency_bypasses": emergency_appointments,
        }

    def _calculate_metrics(self, appointments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute empirical scheduling performance metrics for Priority Scheduling."""
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
            "algorithm": "PRIORITY_AGENT",
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
            "algorithm": "PRIORITY_AGENT",
            "total_patients_served": 0,
            "average_wait_minutes": 0.0,
            "urgent_average_wait_minutes": 0.0,
            "maximum_wait_minutes": 0.0,
            "minimum_wait_minutes": 0.0,
            "urgent_cases_delayed": 0,
            "category_average_waits": {},
        }
