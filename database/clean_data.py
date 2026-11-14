"""
Standalone script to purge all synthetic and fake data from the SQLite database.
Leaves Rule_Definitions, Admin_Users, and RAG_Documents ready for real intake.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import purge_patient_data, get_dashboard_kpis, get_all_patients_with_triage


def main():
    print("Purging all synthetic and demo data from campus_health.db...")
    purge_patient_data()
    kpis = get_dashboard_kpis()
    patients = get_all_patients_with_triage()
    print("Database purge complete!")
    print(f"Total Patients: {kpis['total_patients']}")
    print(f"Awaiting Review: {kpis['awaiting_review']}")
    print(f"Patient count: {len(patients)}")


if __name__ == "__main__":
    main()
