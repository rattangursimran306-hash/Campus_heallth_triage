"""
Dashboard Overview View for Campus Health-Center Decision Support Application.
Updated with custom palette: #3368A0, #66A3BF, #C8DFDB, #F2EFE7,
and clean empty states for an intuitive, simplified user experience.
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import get_dashboard_kpis, get_all_patients_with_triage
from dashboard.visualizations import (
    plot_category_distribution_donut,
    plot_provider_workload_bars,
)
from config import PRIORITY_EMERGENCY, PALETTE, DEPARTMENTS


def render_overview_tab():
    """Render the central operations overview dashboard with department filtering."""
    # 1. Header & Department Filter
    fcol_l, fcol_r = st.columns([2.5, 1.5])
    with fcol_l:
        st.markdown(
            """
            <div style="margin-bottom: 0.8rem;">
                <h2 style="color: #3368A0; margin: 0 0 0.3rem 0; font-weight: 800;">🏥 Clinical Operations & Triage Overview</h2>
                <p style="color: #55728F; margin: 0; font-size: 0.95rem;">
                    Real-time decision support for campus healthcare staff. Non-diagnostic priority queue monitoring & slot allocation.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fcol_r:
        selected_dept = st.selectbox(
            "🏥 Filter Overview by Specialty:",
            options=["All Departments"] + DEPARTMENTS,
            index=0,
            help="Filter queue metrics and patient volume for a specific clinical department.",
        )

    dept_filter = None if selected_dept == "All Departments" else selected_dept

    # 2. Fetch live KPIs and patients filtered by department
    kpis = get_dashboard_kpis(dept_filter)
    patients = get_all_patients_with_triage(dept_filter)

    if dept_filter:
        st.caption(f"🔎 Filter active: Showing operational metrics strictly for **{dept_filter}**.")

    # 3. Emergency Escalation Banner (Active Alert)
    emergency_patients = [
        p for p in patients
        if p.get("priority_category") == PRIORITY_EMERGENCY and p.get("appointment_status") != "COMPLETED"
    ]

    if emergency_patients:
        st.markdown(
            f"""
            <div class="alert-ticker-emergency">
                🚨 <b>ACTIVE EMERGENCY ESCALATION:</b> &nbsp;
                {len(emergency_patients)} patient(s) flagged with critical life-safety warning signs.
                Immediate EMS transfer or Acute Bay stabilization required.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. KPI Cards Grid
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-label">Total Registered</div>
                <div class="metric-card-value">{kpis['total_patients']}</div>
                <div class="metric-card-subtext">Active Cohort</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-label">Awaiting Review</div>
                <div class="metric-card-value" style="color: #66A3BF;">{kpis['awaiting_review']}</div>
                <div class="metric-card-subtext">In Clinic Queue</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4.5px solid #D9534F;">
                <div class="metric-card-label">Emergency Flags</div>
                <div class="metric-card-value" style="color: #D9534F;">{kpis['emergency_count']}</div>
                <div class="metric-card-subtext">Direct Bypass (0m)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4.5px solid #E67E22;">
                <div class="metric-card-label">High Priority</div>
                <div class="metric-card-value" style="color: #E67E22;">{kpis['high_priority_count']}</div>
                <div class="metric-card-subtext">&lt; 45m Target</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col5:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left: 4.5px solid #48A388;">
                <div class="metric-card-label">Completed</div>
                <div class="metric-card-value" style="color: #48A388;">{kpis['completed_count']}</div>
                <div class="metric-card-subtext">Evaluated Visits</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col6:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-label">Avg Wait Time</div>
                <div class="metric-card-value" style="color: #3368A0;">{kpis['avg_wait_minutes']}<span style="font-size: 1rem;">m</span></div>
                <div class="metric-card-subtext">Priority Scheduling</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Main Section: Visualizations or Friendly Empty State
    if not patients:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-state-icon">📋</div>
                <div class="empty-state-title">Clinic Queue is Currently Clear</div>
                <div class="empty-state-desc">
                    All demo records have been cleared. As students and staff complete their intake,
                    their non-diagnostic triage priorities, rule explanations, and doctor slots will appear here in real time.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        ecol1, ecol2, ecol3 = st.columns([1, 1.2, 1])
        with ecol2:
            st.info("💡 **Ready to test?** Click **📝 Register New Patient** in the left sidebar to add a patient and watch the triage engine evaluate them instantly.")

    else:
        chart_col1, chart_col2 = st.columns([1.1, 0.9])
        with chart_col1:
            st.plotly_chart(plot_category_distribution_donut(patients), use_container_width=True)
        with chart_col2:
            st.plotly_chart(plot_provider_workload_bars(patients), use_container_width=True)

        st.markdown("### 📋 Recent Queue Activity")
        display_data = []
        for p in patients[:8]:
            cat = p.get("priority_category", "ROUTINE REVIEW")
            display_data.append({
                "Patient ID": p["patient_code"],
                "Patient Name": p["full_name"],
                "Department": p.get("department", "General Medicine"),
                "Priority Category": cat,
                "Reported Symptoms": ", ".join(p.get("symptoms", []))[:45] + ("..." if len(", ".join(p.get("symptoms", []))) > 45 else ""),
                "Winning Rule": p.get("winning_rule_id", "N/A"),
                "Slot Time": p.get("slot_start", "Immediate EMS"),
                "Wait (mins)": p.get("estimated_wait_minutes", 0.0),
                "Status": p.get("appointment_status", "SCHEDULED"),
            })
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
