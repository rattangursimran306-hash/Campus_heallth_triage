"""
Campus Health-Center Triage and Appointment Allocation Assistant.
Main Streamlit Application — Streamlined & User-Friendly Edition.

Branding Color Palette:
- Primary Deep Blue: #3368A0
- Secondary Ocean Blue: #66A3BF
- Border / Soft Sage: #C8DFDB
- Canvas Background: #F2EFE7

5 Simplified Workspaces:
1. 🏥 Clinic Queue & Overview (Unified Dashboard, Queue, & Doctor Rosters)
2. 📝 Register New Patient (Simple 3-Step Intake & Instant Triage Feedback)
3. ⚖️ Scheduling Comparison (FCFS vs. Priority Queue with In-Memory Demo)
4. 📚 Health Guidelines & RAG Search (Grounded Protocol Search & Uploads)
5. 🛠️ System Governance & Tests (Pytest Suite, Rule Base, Audit Logs, Settings)
"""
import streamlit as st
import pandas as pd
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

# Set Page Config
st.set_page_config(
    page_title="Campus Health Decision-Support Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Root directory setup
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from config import (
    NON_DIAGNOSTIC_DISCLAIMER,
    EMERGENCY_ESCALATION_NOTICE,
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_ROUTINE,
    PRIORITY_INSUFFICIENT,
    PRIORITY_COLORS,
    HEALTHCARE_PROVIDERS,
    PALETTE,
    DEPARTMENTS,
    DEFAULT_DEPARTMENT,
)
from database.db import (
    init_db,
    purge_patient_data,
    get_all_patients_with_triage,
    get_audit_logs,
    get_doctor_roster_stats,
)
from database.seed_data import seed_database
from modules.patient_registration import (
    SYMPTOM_CATALOG,
    get_flattened_symptoms,
    register_new_patient,
    infer_recommended_department,
)
from modules.priority_agent import PriorityAgent
from modules.rule_engine import evaluate_patient_triage, build_clinical_rule_base
from modules.explanation_engine import format_explanation_markdown
from modules.rag_engine import get_rag_engine
from modules.responsible_ai import ResponsibleAI

# Dashboard views
from dashboard.overview import render_overview_tab
from dashboard.patient_queue import render_patient_queue_tab
from dashboard.analytics import render_analytics_tab


# ---------------- Inject Custom CSS ----------------
def load_custom_css():
    css_path = APP_DIR / "assets" / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_custom_css()

# Ensure database tables exist
init_db(force_recreate=False)


# ---------------- Sidebar Navigation ----------------
st.sidebar.markdown(
    """
    <div style="text-align: center; padding: 0.6rem 0 1.2rem 0;">
        <span style="font-size: 2.3rem;">🏥</span>
        <h2 style="color: #FFFFFF; margin: 0.2rem 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.02em;">Campus Health</h2>
        <span style="font-size: 0.82rem; color: #C8DFDB; font-weight: 600;">Triage & Scheduling Assistant</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Role Switcher
st.sidebar.markdown("### 👤 User Persona")
user_role = st.sidebar.selectbox(
    "Active Staff Profile:",
    options=["Triage Nurse", "Chief Medical Officer", "Clinic Administrator", "Public / Student Preview"],
    index=0,
)
active_user = {
    "Triage Nurse": "nurse_kelly",
    "Chief Medical Officer": "dr_sharma",
    "Clinic Administrator": "admin_zhao",
    "Public / Student Preview": "student_guest",
}[user_role]

st.sidebar.markdown("---")

# 5 Simplified Navigation Sections
NAVIGATION_SECTIONS = [
    "🏥 Clinic Queue & Overview",
    "📝 Register New Patient",
    "⚖️ Scheduling Comparison",
    "📚 Health Guidelines & RAG",
    "🛠️ System Governance & Tests",
]

selected_view = st.sidebar.radio("Navigation Menu:", options=NAVIGATION_SECTIONS, index=0)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="background: rgba(200, 223, 219, 0.12); border: 1px solid rgba(200, 223, 219, 0.25); border-radius: 8px; padding: 0.65rem 0.8rem; font-size: 0.78rem; color: #E2ECE9;">
        <span style="color: #48A388; font-weight: bold;">● System Online</span><br>
        <span style="color: #C8DFDB;">Campus Health Triage & Scheduling v2.2</span>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------- Top Clinical Disclaimer Banner ----------------
st.markdown(
    f"""
    <div class="disclaimer-banner">
        ⚠️ <b>ADMINISTRATIVE NON-DIAGNOSTIC NOTICE:</b> {NON_DIAGNOSTIC_DISCLAIMER}
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================================
# WORKSPACE 1: CLINIC QUEUE & OVERVIEW (UNIFIED COMMAND CENTER)
# =========================================================================
if selected_view == "🏥 Clinic Queue & Overview":
    sub_tab1, sub_tab2 = st.tabs(["📊 Clinic Overview & Live Queue", "🗓️ Doctor Rosters & Consultations"])

    with sub_tab1:
        render_overview_tab()
        st.markdown("<br>", unsafe_allow_html=True)
        render_patient_queue_tab(current_user=active_user, user_role=user_role)

    with sub_tab2:
        st.markdown("### 🗓️ On-Duty Doctor Rosters & Consultation Schedules")
        st.markdown("Specialty-specific doctor availability, active queued patient counts, and independent waiting times.")

        rcol_l, rcol_r = st.columns([2.5, 1.5])
        with rcol_l:
            st.caption("Filter doctors and schedules by clinical specialty:")
        with rcol_r:
            selected_roster_dept = st.selectbox(
                "Filter by Department / Specialty:",
                options=["All Departments"] + DEPARTMENTS,
                index=0,
                key="doctor_roster_dept_filter",
            )

        roster_filter = None if selected_roster_dept == "All Departments" else selected_roster_dept
        doctor_stats = get_doctor_roster_stats(roster_filter)
        patients = get_all_patients_with_triage(roster_filter)
        active_apps = [p for p in patients if p.get("slot_start") and p.get("slot_start") != "Immediate EMS"]

        pcol1, pcol2 = st.columns([1.2, 1.6])
        with pcol1:
            st.markdown(f"#### 🩺 Healthcare Providers ({len(doctor_stats)})")
            for prov in doctor_stats:
                status_color = "#D9534F" if prov["status_label"] == "High Load" else ("#48A388" if prov["status_label"] == "Accepting Patients" else "#3368A0")
                st.markdown(
                    f"""
                    <div style="background: #FFFFFF; border: 1.5px solid #C8DFDB; border-radius: 10px; padding: 0.95rem; margin-bottom: 0.85rem; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <b style="color: #3368A0; font-size: 1.05rem;">{prov['name']}</b>
                                <span style="font-size: 0.76rem; color: #55728F; margin-left: 0.3rem;">({prov['id']})</span><br>
                                <span style="color: #162D4A; font-weight: 600; font-size: 0.82rem;">🏢 {prov['department']}</span><br>
                                <small style="color: #66A3BF; font-weight: 600;">Specialty: {prov['specialty']}</small>
                            </div>
                            <span style="background: {status_color}18; color: {status_color}; border: 1px solid {status_color}40; padding: 0.2rem 0.55rem; border-radius: 999px; font-weight: 700; font-size: 0.72rem;">
                                {prov['status_label']}
                            </span>
                        </div>
                        <hr style="border: 0; border-top: 1px solid #C8DFDB; margin: 0.6rem 0;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.83rem;">
                            <span>Active Queued Patients: <b style="color: #3368A0;">{prov['active_patients_count']}</b></span>
                            <span>Est. Wait: <b style="color: #3368A0;">{prov['estimated_wait_minutes']}m</b></span>
                        </div>
                        <div style="font-size: 0.78rem; color: #55728F; margin-top: 0.3rem;">
                            Next Available Slot: <b>{prov['next_slot']}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with pcol2:
            st.markdown(f"#### 📋 Booked Appointments ({len(active_apps)})")
            if active_apps:
                slot_df = pd.DataFrame([
                    {
                        "Slot Time": a["slot_start"],
                        "Patient ID": a["patient_code"],
                        "Patient Name": a["full_name"],
                        "Department": a.get("department", "General"),
                        "Provider": a["provider_name"],
                        "Priority Tier": a["priority_category"],
                        "Wait": f"{a.get('estimated_wait_minutes', 0.0)}m",
                        "Status": a["appointment_status"],
                    }
                    for a in sorted(active_apps, key=lambda x: str(x.get("slot_start", "")))
                ])
                st.dataframe(slot_df, use_container_width=True, hide_index=True)
            else:
                st.markdown(
                    """
                    <div class="empty-state-card" style="padding: 1.8rem 1rem;">
                        <div class="empty-state-icon">🗓️</div>
                        <div class="empty-state-title" style="font-size: 1.1rem;">No Active Bookings in this Specialty</div>
                        <div class="empty-state-desc" style="font-size: 0.88rem;">
                            As patients register for this department and receive their priority flags, consultation slots will be scheduled independently here.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# =========================================================================
# WORKSPACE 2: REGISTER NEW PATIENT (3-STEP INTAKE)
# =========================================================================
elif selected_view == "📝 Register New Patient":
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h2 style="color: #3368A0; margin: 0 0 0.3rem 0; font-weight: 800;">📝 New Patient Intake & Priority Triage</h2>
            <p style="color: #55728F; margin: 0; font-size: 0.95rem;">
                Step-by-step patient registration. The system assigns non-diagnostic review flags and allocates appointment slots.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Step Wizard Visual Indicator
    st.markdown(
        """
        <div class="step-indicator">
            <div class="step-item active">Step 1: Patient Details</div>
            <div class="step-item active">Step 2: Symptoms & Vitals</div>
            <div class="step-item">Step 3: Instant Triage Allocation</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("simplified_intake_form", clear_on_submit=False):
        # Step 1
        st.markdown("#### 👤 Step 1: Patient Information")
        c1, c2, c3 = st.columns([2, 1, 1.5])
        with c1:
            full_name = st.text_input("Patient Full Name *", placeholder="e.g. Priya Nair")
        with c2:
            age = st.number_input("Age *", min_value=14, max_value=99, value=20)
        with c3:
            gender = st.selectbox("Gender", options=["Unspecified", "Female", "Male", "Non-Binary", "Other"])

        c_contact, c_dept = st.columns([1.5, 2])
        with c_contact:
            contact = st.text_input("Contact Phone / Email (Optional)", placeholder="e.g. +91-9876543210")
        with c_dept:
            selected_dept = st.selectbox(
                "Requested Clinical Department / Specialty *",
                options=DEPARTMENTS,
                index=0,
                help="Appointments and queue waiting times are isolated per department so specialized doctors are booked directly.",
            )

        st.markdown("---")

        # Step 2
        st.markdown("#### 🩺 Step 2: Symptoms & Health Indicators")
        st.caption("Select any symptoms experienced across clinical domains. Emergency signs are marked with 🚨 and trigger immediate escalation.")

        selected_symptoms = []
        for category, items in SYMPTOM_CATALOG.items():
            is_critical = ("Critical" in category or "Warning" in category)
            with st.expander(f"{'🚨' if is_critical else '📌'} {category}", expanded=is_critical):
                cols = st.columns(2)
                for idx, item in enumerate(items):
                    col = cols[idx % 2]
                    label = f"**{item}**" if is_critical else item
                    if col.checkbox(label, key=f"symp_{item}"):
                        selected_symptoms.append(item)

        other_symptom = st.text_input("Other Unlisted Symptoms (if any):", placeholder="e.g. Tooth sensitivity to cold liquids")

        st.markdown("##### Clinical Vitals & Objective Severity")
        st.info("🛡️ **Objective Severity Safeguard:** In accordance with institutional clinical governance, acuity is algorithmically evaluated from reported symptoms, duration, temperature, and red flags. Subjective pain sliders have been removed to eliminate queue-gaming and ensure fair, safe scheduling.")
        vcol1, vcol2 = st.columns(2)
        with vcol1:
            duration_days = st.number_input("Symptom Duration (Days) *", min_value=0.0, max_value=365.0, value=1.0, step=0.5)
        with vcol2:
            temperature_input = st.number_input("Body Temperature (°C, Optional)", min_value=34.0, max_value=43.0, value=37.0, step=0.1)

        additional_notes = st.text_area("Additional Clinical Notes / Context:", placeholder="Onset details, triggers, relevant context...")

        st.markdown("<br>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("⚡ Step 3: Submit Intake & Calculate Triage Priority", use_container_width=True)

    if submit_btn:
        reg_result = register_new_patient(
            full_name=full_name,
            age=age,
            gender=gender,
            contact=contact,
            department=selected_dept,
            symptoms=selected_symptoms,
            other_symptoms=other_symptom,
            duration_days=duration_days,
            temperature_c=temperature_input,
            additional_notes=additional_notes,
        )

        if not reg_result["success"]:
            for err in reg_result["errors"]:
                st.error(f"❌ {err}")
        else:
            # Process triage and priority scheduling
            agent = PriorityAgent()
            patient_payload = {
                "id": reg_result["patient_id"],
                "patient_code": reg_result["patient_code"],
                "full_name": full_name,
                "age": age,
                "department": reg_result["department"],
                "symptoms": reg_result["symptoms"],
                "inferred_severity": reg_result["inferred_severity"],
                "additional_description": additional_notes or other_symptom,
                "duration_days": duration_days,
                "temperature_c": temperature_input,
                "severe_chest_pain": any("chest pain" in s.lower() for s in reg_result["symptoms"]),
                "respiratory_distress": any("stridor" in s.lower() or "shortness of breath" in s.lower() for s in reg_result["symptoms"]),
                "altered_consciousness": any("consciousness" in s.lower() or "slurred" in s.lower() for s in reg_result["symptoms"]),
                "uncontrolled_bleeding": any("uncontrolled" in s.lower() or "severe bleeding" in s.lower() for s in reg_result["symptoms"]),
                "created_at": datetime.now(),
            }

            outcome = agent.process_patient_triage_and_schedule(patient_payload)
            triage_res = outcome["triage_result"]
            app = outcome["appointment"]
            cat = triage_res["category"]
            color_data = PRIORITY_COLORS.get(cat, {"bg": "#FFFFFF", "text": "#162D4A", "border": "#C8DFDB"})

            # Result Presentation Card
            st.markdown(
                f"""
                <div style="background-color: {color_data['bg']}; border: 1.5px solid {color_data['border']}; border-left: 6px solid {color_data['border']}; padding: 1.3rem; border-radius: 12px; margin: 1.2rem 0; box-shadow: 0 4px 14px rgba(0,0,0,0.04);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="color: {color_data['text']}; margin: 0; font-size: 1.3rem;">Triage Priority Tier: {cat}</h3>
                        <span style="background: {color_data['border']}; color: #FFFFFF; padding: 0.35rem 0.85rem; border-radius: 999px; font-weight: 700; font-size: 0.85rem;">
                            Rule [{triage_res['winning_rule_id']}]
                        </span>
                    </div>
                    <p style="margin: 0.8rem 0 0.4rem 0; color: {color_data['text']}; font-size: 0.98rem; line-height: 1.5;">
                        <b>Clinical Reasoning:</b> {triage_res['explanation']}
                    </p>
                    <div style="margin-top: 0.6rem; padding: 0.6rem; background: rgba(255,255,255,0.7); border-radius: 6px; font-size: 0.86rem; color: #162D4A;">
                        <b>Department:</b> {reg_result['department']} &nbsp;|&nbsp;
                        <b>Inferred Severity:</b> <span style="font-weight:700; color:{color_data['border']};">{reg_result['inferred_severity']}/10</span> ({reg_result['severity_rationale']})
                    </div>
                    <small style="color: #55728F; display: block; margin-top: 0.5rem;">Patient ID: <b>{reg_result['patient_code']}</b> | Registered: {datetime.now().strftime('%H:%M:%S')}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if cat == PRIORITY_EMERGENCY:
                st.error(EMERGENCY_ESCALATION_NOTICE)
            elif app:
                st.success(
                    f"📅 **Allocated Specialist Appointment:** "
                    f"Slot **{app['slot_start']}** with **{app['provider_name']}** "
                    f"({app.get('department', reg_result['department'])}, "
                    f"Queue Position #{app['queue_position']}, "
                    f"Estimated Wait: {app['estimated_wait_minutes']} mins)"
                )



# =========================================================================
# WORKSPACE 3: SCHEDULING COMPARISON (FCFS vs. PRIORITY QUEUE)
# =========================================================================
elif selected_view == "⚖️ Scheduling Comparison":
    render_analytics_tab()


# =========================================================================
# WORKSPACE 4: HEALTH GUIDELINES & RAG SEARCH
# =========================================================================
elif selected_view == "📚 Health Guidelines & RAG":
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h2 style="color: #3368A0; margin: 0 0 0.3rem 0; font-weight: 800;">📚 Health Guidelines & RAG Evidence</h2>
            <p style="color: #55728F; margin: 0; font-size: 0.95rem;">
                Search institution-approved clinical guidelines, emergency escalation SOPs, and WHO protocols.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rag = get_rag_engine()
    rcol1, rcol2 = st.columns([1.3, 1])

    with rcol1:
        st.markdown("#### 🔎 Search Active Protocols")
        search_query = st.text_input("Enter clinical query or symptom combination:", placeholder="e.g. chest pain warning protocol, asthma wheezing").strip()

        if search_query:
            results = rag.retrieve(search_query, top_k=4)
            if results:
                st.markdown(f"**Found {len(results)} relevant guideline sections:**")
                for r in results:
                    st.markdown(
                        f"""
                        <div style="background: #FFFFFF; border: 1.5px solid #C8DFDB; border-left: 5px solid #3368A0; padding: 0.9rem 1.1rem; border-radius: 8px; margin-bottom: 0.8rem; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                            <b style="color: #3368A0; font-size: 1.05rem;">{r['title']}</b><br>
                            <span style="color: #66A3BF; font-size: 0.82rem; font-weight: 700;">{r['filename']} (Section {r['chunk_index']}) | Relevance Score: {r['score']:.3f}</span>
                            <p style="margin-top: 0.4rem; font-size: 0.88rem; color: #162D4A; line-height: 1.5;">{r['text']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No matching clinical guideline passages met the retrieval threshold.")

    with rcol2:
        st.markdown("#### 📁 Active Protocol Documents")
        for fn in rag.indexed_files:
            st.markdown(
                f"""
                <div style="background: #FFFFFF; border: 1px solid #C8DFDB; border-radius: 6px; padding: 0.6rem 0.8rem; margin-bottom: 0.4rem; font-size: 0.86rem; color: #3368A0;">
                    📄 <b>{fn}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.caption(f"Total Chunks Indexed in Local Vector Store: **{len(rag.chunks)} chunks** (100% offline).")

        st.markdown("---")
        st.markdown("#### 📤 Upload New Protocol Document")
        uploaded_file = st.file_uploader("Upload Guideline (TXT or MD):", type=["txt", "md"])
        if uploaded_file is not None:
            if st.button("Index Uploaded Protocol"):
                content = uploaded_file.read()
                res = rag.add_document(uploaded_file.name, content)
                st.success(f"Indexed `{uploaded_file.name}`! Total chunks now: {res['total_chunks']}")
                st.rerun()


# =========================================================================
# WORKSPACE 5: SYSTEM GOVERNANCE, TESTS & SETTINGS
# =========================================================================
elif selected_view == "🛠️ System Governance & Tests":
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h2 style="color: #3368A0; margin: 0 0 0.3rem 0; font-weight: 800;">🛠️ System Governance, Tests & Configuration</h2>
            <p style="color: #55728F; margin: 0; font-size: 0.95rem;">
                Automated test verification, clinical rule base catalog, immutable audit trail, and operational settings.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t1, t2, t3, t4 = st.tabs([
        "🧪 Automated Test Runner",
        "🧠 Production Rule Base",
        "🛡️ Immutable Audit Logs",
        "⚙️ Clinic Settings & Data Reset",
    ])

    # Tab 1: Pytest Runner
    with t1:
        st.markdown("### 🧪 In-App Automated Pytest Suite")
        st.markdown("Verify the 35 unit and integration tests covering the Rule Engine, Schedulers, RAG, Database, and Responsible AI.")

        if st.button("🚀 Run Pytest Test Suite Now"):
            with st.spinner("Running tests..."):
                pytest_bin = str(APP_DIR / ".venv" / "bin" / "pytest")
                tests_dir = str(APP_DIR / "tests")
                try:
                    res = subprocess.run([pytest_bin, tests_dir, "-v", "--tb=short"], capture_output=True, text=True, timeout=60)
                    out = res.stdout + "\n" + res.stderr
                    if res.returncode == 0:
                        st.success("🎉 ALL 35 TEST CASES PASSED WITH 100% SUCCESS RATE!")
                    else:
                        st.error("Some test cases encountered failures.")
                    st.text_area("Pytest Terminal Output:", value=out, height=340)
                except Exception as e:
                    st.error(f"Error running tests: {e}")
        else:
            st.info("Click the button above to run all 35 automated tests directly from this interface.")

    # Tab 2: Clinical Rule Catalog
    with t2:
        st.markdown("### 🧠 Documented Institutional Production Rules")
        st.caption("Deterministic IF-THEN rules powering the inference engine:")
        rules = build_clinical_rule_base()
        rule_table = [
            {
                "Rule ID": r.rule_id,
                "Name": r.name,
                "Category": r.category,
                "IF Condition": r.condition_description,
                "THEN Priority": r.action_priority,
                "Clinical Rationale": r.clinical_rationale,
                "Protocol": r.source_protocol,
            }
            for r in rules
        ]
        st.dataframe(pd.DataFrame(rule_table), use_container_width=True, hide_index=True)

    # Tab 3: Audit Trail
    with t3:
        st.markdown("### 🛡️ Immutable Audit Trail & Decision Logs")
        st.caption("Every system initialization, status change, and staff override is recorded with timestamps:")
        logs = get_audit_logs(limit=100)
        if logs:
            log_df = pd.DataFrame([
                {
                    "Log ID": l["id"],
                    "Timestamp": l["timestamp"],
                    "Admin User": l["admin_user"],
                    "Action Type": l["action_type"],
                    "Patient ID": l.get("patient_code", "N/A"),
                    "Details": l["details"],
                }
                for l in logs
            ])
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info("No audit logs found.")

    # Tab 4: Settings & Data Purge
    with t4:
        st.markdown("### ⚙️ Operational Parameters & Data Management")
        scol1, scol2 = st.columns(2)
        with scol1:
            st.markdown("#### ⏱️ Scheduling Safeguards")
            st.number_input("Starvation Aging Threshold (Minutes):", value=30, min_value=10, max_value=120)
            st.number_input("Priority Boost per Interval:", value=0.5, min_value=0.1, max_value=2.0, step=0.1)
            st.time_input("Clinic Opening Time:", value=datetime.strptime("09:00", "%H:%M").time())
            st.time_input("Clinic Closing Time:", value=datetime.strptime("17:00", "%H:%M").time())

        with scol2:
            st.markdown("#### 🗑️ Data Management (Clean State)")
            st.caption("Remove all patient records, symptoms, and appointment logs to keep the system clean:")
            if st.button("🗑️ Purge All Patient Data (Reset to Clean State)"):
                purge_patient_data()
                st.success("All patient records successfully purged! System is in pristine clean state.")
                st.rerun()

            st.markdown("---")
            st.caption("Opt-in demo data (only if you want to test with 50 synthetic records later):")
            if st.button("🌱 Populate 50 Demo Patients (Optional)"):
                with st.spinner("Seeding demo records..."):
                    seed_database(num_patients=50)
                    st.success("Demo dataset populated! You can purge it at any time using the button above.")
                    st.rerun()
