"""
Patient Queue & Interactive Triage Review Module.
Updated with custom palette (#3368A0, #66A3BF, #C8DFDB, #F2EFE7),
welcoming empty states, and intuitive clinical decision-support controls.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import (
    get_all_patients_with_triage,
    get_patient_details,
    update_appointment_status,
)
from modules.responsible_ai import ResponsibleAI
from modules.rag_engine import get_rag_engine
from config import (
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_ROUTINE,
    PRIORITY_INSUFFICIENT,
    PRIORITY_COLORS,
    PALETTE,
    DEPARTMENTS,
)


def render_patient_queue_tab(current_user: str = "triage_nurse", user_role: str = "Triage Nurse"):
    """Render the prioritized patient queue and interactive clinical review drawer."""
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h2 style="color: #3368A0; margin: 0 0 0.3rem 0; font-weight: 800;">📋 Live Prioritized Patient Queue</h2>
            <p style="color: #55728F; margin: 0; font-size: 0.95rem;">
                Patients are sorted automatically by clinical review priority using our forward-chaining rule engine and priority queue.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    all_patients = get_all_patients_with_triage()

    # 1. Empty State Handling
    if not all_patients:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-state-icon">🩺</div>
                <div class="empty-state-title">No Patients Awaiting Review</div>
                <div class="empty-state-desc">
                    The queue is currently empty. Whenever a student or campus member submits their self-reported symptoms,
                    the priority scheduler will automatically assign their position, urgency flag, and consultation slot.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        qcol1, qcol2, qcol3 = st.columns([1, 1.4, 1])
        with qcol2:
            st.info("💡 **Ready to add a patient?** Navigate to **📝 Register New Patient** in the sidebar to simulate or register a new intake.")
        return

    # 2. Search & Filter Bar
    with st.expander("🔍 Filter & Search Options", expanded=True):
        fcol1, fcol2, fcol3, fcol4 = st.columns([1.8, 1.3, 1.3, 1.6])
        with fcol1:
            search_query = st.text_input("Search Patient (Name, ID, or Symptom):", placeholder="e.g. chest, PAT-2026, fever").strip().lower()
        with fcol2:
            priority_filter = st.selectbox(
                "Filter by Priority Tier:",
                options=["ALL", PRIORITY_EMERGENCY, PRIORITY_URGENT, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_ROUTINE, PRIORITY_INSUFFICIENT],
            )
        with fcol3:
            status_filter = st.selectbox(
                "Filter by Status:",
                options=["ALL", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "ESCALATED_ER"],
            )
        with fcol4:
            department_filter = st.selectbox(
                "Filter by Department:",
                options=["ALL"] + DEPARTMENTS,
            )

    # Filter patients
    filtered_patients = []
    for p in all_patients:
        symptoms_str = " ".join(p.get("symptoms", [])).lower()
        p_code = p.get("patient_code", "").lower()
        p_name = p.get("full_name", "").lower()
        matches_search = (
            not search_query
            or search_query in p_code
            or search_query in p_name
            or search_query in symptoms_str
        )
        cat = p.get("priority_category", "ROUTINE REVIEW")
        matches_priority = (priority_filter == "ALL" or cat == priority_filter)
        status = p.get("appointment_status", "SCHEDULED")
        matches_status = (status_filter == "ALL" or status == status_filter)
        matches_dept = (department_filter == "ALL" or p.get("department") == department_filter)

        if matches_search and matches_priority and matches_status and matches_dept:
            filtered_patients.append(p)

    st.markdown(f"**Showing {len(filtered_patients)} of {len(all_patients)} registered patients**")

    # 3. Main Queue Table
    table_rows = []
    for p in filtered_patients:
        cat = p.get("priority_category", "ROUTINE REVIEW")
        table_rows.append({
            "Queue #": p.get("queue_position") if p.get("queue_position") is not None else "ER",
            "Patient ID": p.get("patient_code"),
            "Name": p.get("full_name"),
            "Department": p.get("department", "General Medicine"),
            "Age": p.get("age"),
            "Priority Tier": cat,
            "Primary Rule": p.get("winning_rule_id", "N/A"),
            "Slot Start": p.get("slot_start", "Immediate EMS"),
            "Doctor / Bay": p.get("provider_name", "EMS Acute Bay"),
            "Wait (mins)": p.get("estimated_wait_minutes", 0.0),
            "Status": p.get("appointment_status", "SCHEDULED"),
            "Internal ID": p.get("id"),
        })

    df_display = pd.DataFrame(table_rows)
    st.dataframe(
        df_display.drop(columns=["Internal ID"]),
        use_container_width=True,
        hide_index=True,
        height=300,
    )

    st.markdown("---")

    # 4. Interactive Patient Inspector & Human-in-the-Loop Actions
    st.markdown("### 🔎 Patient Case Inspector & Clinical Controls")
    patient_options = {
        f"{p['patient_code']} — {p['full_name']} ({p.get('priority_category', 'ROUTINE')})": p["id"]
        for p in filtered_patients
    }

    if not patient_options:
        st.info("No matching patient records found.")
        return

    selected_label = st.selectbox("Select Patient to Inspect & Review:", options=list(patient_options.keys()))
    selected_patient_id = patient_options[selected_label]

    details = get_patient_details(selected_patient_id)
    if not details:
        st.error("Patient details not found.")
        return

    symptom_report = details.get("symptom_report", {})
    category = details.get("appointments", [{}])[0].get("priority_category") if details.get("appointments") else "ROUTINE REVIEW"
    triggered_rules = details.get("triggered_rules", [])
    appointment = details.get("appointments", [{}])[0] if details.get("appointments") else {}

    # Uncertainty Assessment
    patient_eval_payload = {
        "symptoms": symptom_report.get("symptoms", []),
        "duration_days": symptom_report.get("duration_days"),
        "pain_scale": symptom_report.get("pain_scale", 0),
        "temperature_c": symptom_report.get("temperature_c"),
        "additional_description": symptom_report.get("additional_description", ""),
    }
    winning_rule_meta = triggered_rules[0] if triggered_rules else {}
    triage_meta = {"category": category, "winning_rule_id": winning_rule_meta.get("rule_id", "")}
    uncertainty_report = ResponsibleAI.assess_uncertainty(patient_eval_payload, triage_meta)

    # 3-Column Layout: Facts | Rule Rationale & Evidence | Staff Controls
    dcol1, dcol2, dcol3 = st.columns([1, 1.25, 1.1])

    with dcol1:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1.5px solid #C8DFDB; border-radius: 10px; padding: 1.1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
                <h4 style="color: #3368A0; margin-top: 0; font-size: 1.1rem;">👤 Intake Profile</h4>
                <b>Patient ID:</b> <code style="background: #EAF2F7; color: #3368A0;">{details['patient_code']}</code><br>
                <b>Name:</b> {details['full_name']}<br>
                <b>Department:</b> <span style="color: #3368A0; font-weight: 700;">{details.get('department', 'General Medicine')}</span><br>
                <b>Age / Gender:</b> {details['age']} yrs / {details.get('gender', 'N/A')}<br>
                <b>Contact:</b> {details.get('contact', 'Not Provided')}<br>
                <hr style="border: 0; border-top: 1px solid #C8DFDB; margin: 0.8rem 0;">
                <h4 style="color: #3368A0; margin: 0 0 0.4rem 0; font-size: 1.0rem;">🩺 Reported Symptoms</h4>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for symp in symptom_report.get("symptoms", []):
            st.markdown(f"- 🔴 **{symp}**" if "chest" in symp.lower() or "stridor" in symp.lower() else f"- 🔹 {symp}")
        severity_score = symptom_report.get("inferred_severity") or symptom_report.get("pain_scale", 1)
        st.caption(f"**Duration:** {symptom_report.get('duration_days', 0)} days | **Inferred Severity:** {severity_score}/10 (Objective) | **Temp:** {symptom_report.get('temperature_c', 'N/A')} °C")
        if symptom_report.get("additional_description"):
            st.caption(f"*Notes:* \"{symptom_report.get('additional_description')}\"")

    with dcol2:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1.5px solid #C8DFDB; border-radius: 10px; padding: 1.1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
                <h4 style="color: #3368A0; margin-top: 0; font-size: 1.1rem;">🧠 Production Rule Trace</h4>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if triggered_rules:
            for tr in triggered_rules:
                is_win = tr.get("is_conflict_winner", False)
                border = "#D9534F" if is_win and "EMERGENCY" in tr["action_priority"] else ("#3368A0" if is_win else "#C8DFDB")
                badge_text = "👑 SELECTED TIER" if is_win else "↳ SUPERSEDED"
                st.markdown(
                    f"""
                    <div style="border-left: 4px solid {border}; background: #FFFFFF; border: 1px solid #C8DFDB; border-left-width: 4px; padding: 0.7rem 0.9rem; border-radius: 6px; margin: 0.5rem 0;">
                        <div style="display: flex; justify-content: space-between;">
                            <b style="color: #3368A0;">Rule [{tr['rule_id']}]</b>
                            <span style="font-size: 0.74rem; font-weight: 700; color: {border};">{badge_text}</span>
                        </div>
                        <div style="font-size: 0.84rem; margin-top: 0.25rem;">{tr['explanation']}</div>
                        <div style="font-size: 0.76rem; color: #66A3BF; margin-top: 0.25rem;"><b>Protocol:</b> {tr.get('source_protocol', 'Campus Protocol')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # RAG Evidence
        rag = get_rag_engine()
        evidence = rag.generate_grounded_evidence(
            patient_symptoms=symptom_report.get("symptoms", []),
            additional_notes=symptom_report.get("additional_description", ""),
            winning_rule=winning_rule_meta,
        )
        st.markdown("#### 📚 Grounded Guidelines (RAG)")
        st.markdown(evidence["summary"])

    with dcol3:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1.5px solid #C8DFDB; border-radius: 10px; padding: 1.1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
                <h4 style="color: #3368A0; margin-top: 0; font-size: 1.1rem;">⚡ Staff Actions</h4>
                <b>Active Staff:</b> {current_user} ({user_role})<br>
                <b>Status:</b> <code style="color: #3368A0;">{appointment.get('status', 'SCHEDULED')}</code><br>
                <b>Slot Time:</b> {appointment.get('slot_start', 'Immediate')}<br>
                <b>Assigned Provider:</b> {appointment.get('provider_name', 'EMS Bay')}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### 1. Status Update")
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("Mark In Progress", key=f"prog_{selected_patient_id}"):
                if appointment.get("id"):
                    update_appointment_status(appointment["id"], "IN_PROGRESS", admin_user=current_user, reason="Consultation started.")
                    st.success("Updated to IN_PROGRESS.")
                    st.rerun()
        with bcol2:
            if st.button("Mark Completed", key=f"comp_{selected_patient_id}"):
                if appointment.get("id"):
                    update_appointment_status(appointment["id"], "COMPLETED", admin_user=current_user, reason="Consultation completed.")
                    st.success("Updated to COMPLETED.")
                    st.rerun()

        if category == PRIORITY_EMERGENCY and appointment.get("status") != "ESCALATED_ER":
            if st.button("🚨 Log EMS ER Transfer", key=f"er_{selected_patient_id}"):
                if appointment.get("id"):
                    update_appointment_status(appointment["id"], "ESCALATED_ER", admin_user=current_user, reason="Ambulance ER transfer.")
                    st.success("Emergency Transfer Logged.")
                    st.rerun()

        st.markdown("---")
        st.markdown("##### 2. Manual Priority Override")
        new_priority = st.selectbox(
            "Change Priority Tier:",
            options=[PRIORITY_EMERGENCY, PRIORITY_URGENT, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_ROUTINE, PRIORITY_INSUFFICIENT],
            index=[PRIORITY_EMERGENCY, PRIORITY_URGENT, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_ROUTINE, PRIORITY_INSUFFICIENT].index(category) if category in [PRIORITY_EMERGENCY, PRIORITY_URGENT, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_ROUTINE, PRIORITY_INSUFFICIENT] else 4,
            key=f"prio_sel_{selected_patient_id}",
        )
        override_reason = st.text_area(
            "Clinical Justification (Required):",
            placeholder="Document clinical reason for manual override...",
            key=f"reason_{selected_patient_id}",
        )
        if st.button("Apply Override", key=f"btn_override_{selected_patient_id}"):
            is_valid, err = ResponsibleAI.validate_manual_override(
                old_priority=category,
                new_priority=new_priority,
                justification=override_reason,
                admin_user=current_user,
                patient_id=selected_patient_id,
            )
            if not is_valid:
                st.error(err)
            else:
                st.success(f"Priority changed to {new_priority}. Audit log updated.")
                st.rerun()
